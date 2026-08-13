-- ── Mihomo TUN stack selection panel ─────────────────────────
-- Opened by right-click on the bar widget.
-- Shows stack options: System, GVisor, Mixed. (On/off is toggled
-- via the bar widget's left-click.) Also includes an IPv6 toggle.

local apiUrl    = noctalia.getConfig("api_url")    or "http://127.0.0.1:9090"
local apiSecret = noctalia.getConfig("api_secret") or ""

-- ── State ───────────────────────────────────────────────────
local tunEnabled = false
local tunStack   = nil
local ipv6Enabled = false
local loading    = true
local lastError  = nil

-- ── Helpers ─────────────────────────────────────────────────

local function authHeaders(contentType)
  local h = {}
  if contentType then
    table.insert(h, "Content-Type: " .. contentType)
  end
  if apiSecret ~= "" then
    table.insert(h, "Authorization: Bearer " .. apiSecret)
  end
  return h
end

local function fetchTunState(callback)
  noctalia.http({
    url      = apiUrl .. "/configs",
    method   = "GET",
    headers  = authHeaders(),
  }, function(res)
    if not res.ok then
      callback(nil, nil, "HTTP " .. tostring(res.status))
      return
    end
    local configs, err = noctalia.json.decode(res.body)
    if not configs then
      callback(nil, nil, "JSON: " .. err)
      return
    end
    callback(configs.tun, configs.ipv6)
  end)
end

local function setTun(enable, stack, callback)
  local tun = { enable = enable }
  if stack then tun.stack = stack end

  noctalia.http({
    url      = apiUrl .. "/configs",
    method   = "PATCH",
    headers  = authHeaders("application/json"),
    body     = noctalia.json.encode({ tun = tun }),
  }, function(res)
    if not res.ok then
      callback(false, "HTTP " .. tostring(res.status))
      return
    end
    callback(true)
  end)
end

local function setIpv6(enable, callback)
  noctalia.http({
    url      = apiUrl .. "/configs",
    method   = "PATCH",
    headers  = authHeaders("application/json"),
    body     = noctalia.json.encode({ ipv6 = enable }),
  }, function(res)
    if not res.ok then
      callback(false, "HTTP " .. tostring(res.status))
      return
    end
    callback(true)
  end)
end

-- ── Stack options ───────────────────────────────────────────

local stacks = {
  { label = "System", glyph = "shield-check", value = "system" },
  { label = "GVisor", glyph = "shield-check", value = "gVisor" },
  { label = "Mixed",  glyph = "shield-check", value = "mixed"  },
}

-- ── Rendering ───────────────────────────────────────────────

local function render()
  local children = {
    ui.label({ text = "TUN Stack", fontSize = 18, fontWeight = "bold" }),
    ui.separator({ thickness = 1, spacing = 8 }),
  }

  for _, s in ipairs(stacks) do
    local highlight
    if tunEnabled then
      highlight = s.value == tunStack
    else
      highlight = s.value == (noctalia.getConfig("stack") or nil)
    end
    table.insert(children, ui.button({
      text      = s.label,
      glyph     = s.glyph,
      glyphSize = 16,
      selected  = highlight,
      variant   = highlight and "primary" or "ghost",
      width     = "fill",
      onClick   = function() selectStack(s.value) end,
    }))
  end

  table.insert(children, ui.separator({ thickness = 1, spacing = 8 }))

  table.insert(children, ui.row({ gap = 8, align = "center", justify = "space_between" }, {
    ui.label({ text = "Allow IPv6", fontSize = 14 }),
    ui.toggle({
      checked  = ipv6Enabled,
      onChange = function(value) toggleIpv6(value == "true") end,
    }),
  }))

  table.insert(children, ui.separator({ thickness = 1, spacing = 8 }))
  table.insert(children, ui.label({ text = "On/off is toggled via the bar widget.", fontSize = 12, color = "#9ca3af" }))

  if loading then
    table.insert(children, ui.label({ text = "Loading…", color = "#9ca3af" }))
  end

  if lastError then
    table.insert(children, ui.label({ text = lastError, color = "#f59e0b" }))
  end

  panel.render(ui.column({ gap = 8, padding = 16 }, children))
end

-- ── Select a stack ──────────────────────────────────────────
-- Enables TUN with the chosen stack and shares the selection
-- with the widget via state so the next toggle-on uses it.

function selectStack(value)
  noctalia.state.set("tun_stack", value)

  setTun(true, value, function(ok, err)
    if ok then
      tunEnabled = true
      tunStack   = value
      lastError  = nil
      render()
      noctalia.notify("Mihomo TUN", "TUN enabled (" .. value .. ")")
    else
      lastError = err
      render()
      noctalia.notifyError("Mihomo TUN", "Failed: " .. (err or "unknown"))
    end
  end)
end

-- ── Toggle IPv6 ─────────────────────────────────────────────

function toggleIpv6(enable)
  setIpv6(enable, function(ok, err)
    if ok then
      ipv6Enabled = enable
      lastError  = nil
      render()
      noctalia.notify("Mihomo TUN", "IPv6 " .. (enable and "enabled" or "disabled"))
    else
      lastError = err
      render()
      noctalia.notifyError("Mihomo TUN", "Failed: " .. (err or "unknown"))
    end
  end)
end

-- ── IPC ────────────────────────────────────────────────────
--   select <stack>  — enable TUN with the given stack
--   ipv6 <true|false> — toggle IPv6

function onIpc(event, payload)
  if event == "select" and payload then
    selectStack(payload)
  elseif event == "ipv6" then
    toggleIpv6(payload == "true")
  end
end

-- ── Lifecycle ───────────────────────────────────────────────

function onOpen(_context)
  loading = true
  lastError = nil
  render()

  fetchTunState(function(tun, ipv6, err)
    loading = false
    if err then
      lastError = err
    else
      if tun then
        tunEnabled = tun.enable == true
        tunStack   = tunEnabled and (tun.stack or nil)
      else
        tunEnabled = false
        tunStack   = nil
      end
      ipv6Enabled = ipv6 == true
    end
    render()
  end)
end

function onClose()
  -- Nothing to clean up
end
