function FindProxyForURL(url, host) {
  // Proxy endpoints — all mixed (HTTP + SOCKS5) ports
  const MITM   = "PROXY 127.0.0.1:10808";
  const FRAG   = "PROXY 127.0.0.1:10809";
  const CFW    = "PROXY 127.0.0.1:7890";
  const THRONE = "PROXY 127.0.0.1:2080"; // defined, no routes assigned yet
  const DIRECT = "DIRECT";

  // Domain routing table — base domains cover all of their subdomains
  const routes = [
    {
      proxy: MITM,
      domains: [
        // YouTube (incl. video delivery, thumbnails, API)
        "youtube.com", "youtube-nocookie.com", "googlevideo.com",
        "ytimg.com", "yt3.ggpht.com", "youtubei.googleapis.com",
        // Reddit (incl. short links, media, streaming)
        "reddit.com", "redd.it", "redditmedia.com", "redditstatic.com",
        "reddit-stream.com", "out.reddit.com"
      ]
    },
    {
      proxy: FRAG,
      domains: [
        // X (incl. legacy Twitter domains, shortener, media)
        "x.com", "twitter.com", "t.co", "twimg.com"
      ]
    },
    {
      proxy: CFW,
      domains: [
        // Discord (incl. CDN, invites, media)
        "discord.com", "discordapp.com", "discordapp.net", "discord.gg",
        // Google Gemini / AI Studio
        "gemini.google.com", "bard.google.com", "aistudio.google.com",
        // Kimi
        "kimi.com", "moonshot.cn",
        // AniList
        "anilist.co",
        // Anime torrent providers
        "animetosho.org", "arm.haglund.dev",
        "nyaa.si",
        "tokyotosho.info"
      ]
    }
  ];

  const lowerHost = host.toLowerCase();

  // Never proxy local/private destinations
  const ip = dnsResolve(lowerHost);
  if (ip &&
      (ip.startsWith("127.") || ip.startsWith("10.") || ip.startsWith("192.168.") ||
       ip.startsWith("169.254.") || /^172\.(1[6-9]|2\d|3[01])\./.test(ip))) {
    return DIRECT;
  }

  function hostMatches(hostname, domain) {
    return hostname === domain || hostname.endsWith("." + domain);
  }

  for (const route of routes) {
    for (const domain of route.domains) {
      if (hostMatches(lowerHost, domain)) {
        return route.proxy;
      }
    }
  }

  // Default: everything else goes direct
  return DIRECT;
}
