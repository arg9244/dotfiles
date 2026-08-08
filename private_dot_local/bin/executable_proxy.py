#!/usr/bin/env python3
"""route-proxy: local mixed SOCKS5 + HTTP proxy driven by proxy.pac.

Listens on a single port and speaks both SOCKS5 and HTTP-proxy protocols,
so any app can point at it as a "mixed" proxy. For every destination it
evaluates the routing rules from proxy.pac - the same file browsers use -
and either connects directly or tunnels through the matching upstream
proxy with an HTTP CONNECT.

Rules live in proxy.pac. Edit that file, restart this server.

The PAC parser is intentionally small: it understands the routes table
format this project uses, i.e.

    const NAME = "PROXY host:port";
    const routes = [
      { proxy: NAME, domains: [ "example.com", ... ] },
      ...
    ];

and fails loudly at startup if the file drifts from that shape.

Usage:
    python3 proxy_server.py [--listen 127.0.0.1:10880] [--pac proxy.pac]
"""

import argparse
import asyncio
import ipaddress
import logging
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("route-proxy")

DIRECT = "DIRECT"
CHUNK = 65536

PROXY_CONST_RE = re.compile(r'const\s+(\w+)\s*=\s*"PROXY\s+([^"]+)"')
ROUTES_BLOCK_RE = re.compile(r"const\s+routes\s*=\s*\[(.*)\];", re.S)
ROUTE_RE = re.compile(r"proxy:\s*(\w+)\s*,\s*domains:\s*\[(.*?)\]", re.S)
DOMAIN_RE = re.compile(r'"([^"]+)"')

HTTP_OK = b"HTTP/1.1 200 Connection established\r\n\r\n"
HTTP_502 = b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
HTTP_400 = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


def load_pac(path):
    """Parse proxy.pac into (proxies, routes) - see module docstring for the shape."""
    text = Path(path).read_text(encoding="utf-8")
    proxies = {name: addr for name, addr in PROXY_CONST_RE.findall(text)}
    block = ROUTES_BLOCK_RE.search(text)
    if not block:
        raise ValueError(f"{path}: could not find 'const routes = [ ... ];'")
    routes = []
    for name, doms in ROUTE_RE.findall(block.group(1)):
        if name not in proxies:
            raise ValueError(f"{path}: route references unknown proxy '{name}'")
        routes.append((name, DOMAIN_RE.findall(doms)))
    if not routes:
        raise ValueError(f"{path}: no routes parsed from the routes table")
    return proxies, routes


def split_host_port(s):
    if s.startswith("["):
        host, _, rest = s[1:].partition("]")
        return host, int(rest.lstrip(":"))
    host, _, port = s.rpartition(":")
    return host, int(port)


class Router:
    """Mirrors proxy.pac matching: host matches a domain when it equals it
    or ends with '.' + domain."""

    def __init__(self, proxies, routes):
        self._upstream = {name: split_host_port(addr) for name, addr in proxies.items()}
        self._routes = [(name, [d.lower() for d in doms]) for name, doms in routes]

    def resolve(self, host):
        h = host.lower()
        for name, domains in self._routes:
            for domain in domains:
                if h == domain or h.endswith("." + domain):
                    return ("PROXY",) + self._upstream[name]
        return (DIRECT,)


def is_private_host(host):
    """True for IP literals that must never go through an upstream proxy."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def decode_host(raw):
    try:
        return raw.decode("idna")
    except UnicodeError:
        return raw.decode("utf-8", "replace")


def socks_reply(code):
    return b"\x05" + bytes([code]) + b"\x00\x01" + b"\x00\x00\x00\x00" + b"\x00\x00"


async def connect_via_upstream(uhost, uport, host, port):
    """Open a CONNECT tunnel to (host, port) through the upstream HTTP proxy."""
    reader, writer = await asyncio.open_connection(uhost, uport)
    try:
        h = host.encode("idna").decode("ascii")
        writer.write(
            f"CONNECT {h}:{port} HTTP/1.1\r\nHost: {h}:{port}\r\n\r\n".encode("ascii")
        )
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        status = head.split(b" ", 2)
        if len(status) < 2 or not status[1].startswith(b"2"):
            raise ConnectionError(
                f"upstream {uhost}:{uport} rejected CONNECT: {head.split(b'\r\n', 1)[0]!r}"
            )
    except Exception:
        writer.close()
        raise
    return reader, writer


async def _pump(src, dst):
    try:
        while True:
            data = await src.read(CHUNK)
            if not data:
                break
            dst.write(data)
            await dst.drain()
        try:
            dst.write_eof()  # half-close; the other direction may keep flowing
        except Exception:
            pass
    except Exception:
        pass


async def tunnel(a_reader, a_writer, b_reader, b_writer):
    await asyncio.gather(_pump(a_reader, b_writer), _pump(b_reader, a_writer))
    for w in (a_writer, b_writer):
        try:
            w.close()
        except Exception:
            pass


def describe(route):
    if route[0] == DIRECT:
        return "DIRECT"
    return f"PROXY {route[1]}:{route[2]}"


async def connect_and_tunnel(reader, writer, host, port, router, *, socks):
    route = (DIRECT,) if is_private_host(host) else router.resolve(host)
    log.info("CONNECT %s:%d -> %s", host, port, describe(route))
    try:
        if route[0] == DIRECT:
            b_reader, b_writer = await asyncio.open_connection(host, port)
        else:
            b_reader, b_writer = await connect_via_upstream(route[1], route[2], host, port)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.info("CONNECT %s:%d failed: %s", host, port, exc)
        if socks:
            if isinstance(exc, ConnectionRefusedError):
                code = 0x05
            elif isinstance(exc, socket.gaierror):
                code = 0x04
            else:
                code = 0x01
            writer.write(socks_reply(code))
        else:
            writer.write(HTTP_502)
        await writer.drain()
        return
    if socks:
        writer.write(socks_reply(0x00))
    else:
        writer.write(HTTP_OK)
    await writer.drain()
    await tunnel(reader, writer, b_reader, b_writer)


async def handle_socks5(reader, writer, router):
    """First byte (0x05) has already been consumed."""
    try:
        nmethods = (await reader.readexactly(1))[0]
        await reader.readexactly(nmethods)
        writer.write(b"\x05\x00")  # no authentication
        await writer.drain()

        _ver, cmd, _rsv, atyp = await reader.readexactly(4)
        if cmd != 0x01:  # only CONNECT is supported (no BIND / UDP ASSOCIATE)
            writer.write(socks_reply(0x07))
            await writer.drain()
            return

        if atyp == 0x01:
            host = socket.inet_ntoa(await reader.readexactly(4))
        elif atyp == 0x03:
            n = (await reader.readexactly(1))[0]
            host = decode_host(await reader.readexactly(n))
        elif atyp == 0x04:
            host = socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
        else:
            writer.write(socks_reply(0x08))  # address type not supported
            await writer.drain()
            return
        port = int.from_bytes(await reader.readexactly(2), "big")
        await connect_and_tunnel(reader, writer, host, port, router, socks=True)
    except (asyncio.IncompleteReadError, ConnectionError):
        pass


def parse_host_header(head):
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"host:"):
            value = line[5:].strip().decode("idna")
            if value.startswith("["):  # IPv6 literal
                host, _, rest = value[1:].partition("]")
                port = rest.lstrip(":")
            elif ":" in value:
                host, _, port = value.rpartition(":")
            else:
                host, port = value, None
            return host, int(port) if port else 80
    return None, 80


async def handle_http(reader, writer, first, router):
    """First byte has already been consumed (it was not 0x05)."""
    try:
        head = first + await reader.readuntil(b"\r\n\r\n")
    except asyncio.IncompleteReadError as exc:
        head = first + exc.partial
        if not head.strip():
            return
    except (ConnectionError, asyncio.LimitOverrunError):
        return

    lines = head.split(b"\r\n")
    try:
        method, target, version = lines[0].split(b" ", 2)
    except ValueError:
        return

    if method == b"CONNECT":
        if target.startswith(b"["):  # IPv6 literal
            host, _, rest = target[1:].partition(b"]")
            port_s = rest[1:] if rest.startswith(b":") else b""
        else:
            host, _, port_s = target.partition(b":")
        if not host:
            return
        try:
            port = int(port_s) if port_s else 443
        except ValueError:
            return
        await connect_and_tunnel(reader, writer, decode_host(host), port, router, socks=False)
        return

    if target.startswith((b"http://", b"https://")):
        try:
            u = urlsplit(target.decode("idna"))
        except UnicodeError:
            writer.write(HTTP_400)
            await writer.drain()
            return
        host = u.hostname or ""
        port = u.port or (443 if u.scheme == "https" else 80)
        absolute = True
        m = re.match(rb"^https?://[^/]*(.*)$", target)
        path_and_query = (m.group(1) if m else b"") or b"/"
    else:
        host, port = parse_host_header(head)
        absolute = False
        path_and_query = target

    if not host:
        writer.write(HTTP_400)
        await writer.drain()
        return

    route = (DIRECT,) if is_private_host(host) else router.resolve(host)
    log.info("%s %s:%d -> %s", method.decode("ascii", "replace"), host, port, describe(route))
    try:
        if route[0] == DIRECT:
            b_reader, b_writer = await asyncio.open_connection(host, port)
        else:
            b_reader, b_writer = await connect_via_upstream(route[1], route[2], host, port)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.info("%s %s:%d failed: %s", method.decode("ascii", "replace"), host, port, exc)
        writer.write(HTTP_502)
        await writer.drain()
        return

    # Rewrite the request line so the receiving end accepts it:
    #  - direct: absolute-form -> origin-form
    #  - via upstream: origin-form -> absolute-form
    if route[0] == DIRECT and absolute:
        lines[0] = method + b" " + path_and_query + b" " + version
    elif route[0] != DIRECT and not absolute:
        lines[0] = (
            method
            + b" http://"
            + host.encode("idna")
            + b":"
            + str(port).encode()
            + path_and_query
            + b" "
            + version
        )

    # HTTP/1.1 requires a Host header when talking to the origin directly
    if route[0] == DIRECT and not any(l.lower().startswith(b"host:") for l in lines[1:]):
        host_header = b"Host: " + host.encode("idna")
        if port != 80:
            host_header += b":" + str(port).encode()
        lines.insert(1, host_header)

    b_writer.write(b"\r\n".join(lines))
    await b_writer.drain()
    await tunnel(reader, writer, b_reader, b_writer)


async def handle_client(reader, writer, router):
    peer = writer.get_extra_info("peername")
    try:
        first = await asyncio.wait_for(reader.readexactly(1), timeout=30)
    except (asyncio.IncompleteReadError, ConnectionError, asyncio.TimeoutError):
        writer.close()
        return
    try:
        if first == b"\x05":
            await handle_socks5(reader, writer, router)
        else:
            await handle_http(reader, writer, first, router)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("error handling client %s", peer)
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def serve(host, port, router):
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, router), host, port
    )
    log.info("listening on %s:%d (SOCKS5 + HTTP)", host, port)
    async with server:
        await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(
        description="Local mixed SOCKS5 + HTTP proxy using proxy.pac routing rules"
    )
    ap.add_argument("--listen", default="127.0.0.1:10880", metavar="HOST:PORT",
                    help="address to listen on (default 127.0.0.1:10880)")
    ap.add_argument("--pac", default="proxy.pac", metavar="PATH",
                    help="PAC file to read rules from (default proxy.pac)")
    ap.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        proxies, routes = load_pac(args.pac)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))

    router = Router(proxies, routes)
    for name, domains in routes:
        log.info("route %-6s (%2d domains) -> PROXY %s", name, len(domains), proxies[name])
    unused = set(proxies) - {n for n, _ in routes}
    if unused:
        log.info("upstreams without routes: %s", ", ".join(sorted(unused)))

    host, _, port_s = args.listen.rpartition(":")
    try:
        asyncio.run(serve(host, int(port_s), router))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
