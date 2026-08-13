-- ── Mihomo TUN toggle bar widget ─────────────────────────────
-- Left-click: toggle TUN on/off (uses stack from the "stack" setting,
--   or the most recently selected stack from the panel)
-- Right-click: open panel to select TUN stack
-- IPC: noctalia msg plugin reza/mihomo-tun:tun-toggle all toggle

local apiUrl    = noctalia.getConfig("api_url")    or "http://127.0.0.1:9090"
local apiSecret = noctalia.getConfig("api_secret") or ""

-- ── State ───────────────────────────────────────────────────
local tunEnabled = false
local loading    = true
local lastError  = nil
local lastStack  = noctalia.getConfig("stack") or "gVisor"

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
      callback(nil, "HTTP " .. tostring(res.status))
      return
    end
    local configs, err = noctalia.json.decode(res.body)
    if not configs then
      callback(nil, "JSON: " .. err)
      return
    end
    callback(configs.tun)
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

-- ── Rendering ───────────────────────────────────────────────
-- Defined before any function that calls it, so it is in scope
-- as a local upvalue.

local function render()
  if loading then
    barWidget.setGlyph("shield")
    barWidget.setGlyphColor("#9ca3af")
    barWidget.setText("")
    barWidget.setTooltip("Mihomo TUN: loading…")
    return
  end

  if lastError then
    barWidget.setGlyph("alert-triangle")
    barWidget.setGlyphColor("#f59e0b")
    barWidget.setText("")
    barWidget.setTooltip("Mihomo: " .. lastError .. "\nLeft-click to retry")
    return
  end

  if tunEnabled then
    barWidget.setGlyph("shield-check")
    barWidget.setGlyphColor("#4ade80")
    barWidget.setColor("#4ade80")
    barWidget.setText("")
    barWidget.setTooltip("Mihomo TUN: on (" .. lastStack .. ")\nLeft-click to disable\nRight-click for stack options")
  else
    barWidget.setGlyph("shield-x")
    barWidget.setText("")
    barWidget.setTooltip("Mihomo TUN: off\nLeft-click to enable (" .. lastStack .. ")\nRight-click for stack options")
  end
end

-- ── Cross-entry state sync ──────────────────────────────────
-- The panel sets "tun_stack" when the user picks a different stack.
-- This overrides the Settings "stack" dropdown at runtime until the
-- dropdown is changed again (onSettingsChange takes priority).

noctalia.state.watch("tun_stack", function(stack)
  if stack ~= nil then
    lastStack = stack
    render()
  end
end)

-- ── Refresh ─────────────────────────────────────────────────

local function refresh()
  loading = true
  lastError = nil
  render()

  fetchTunState(function(tun, err)
    loading = false
    if err then
      lastError = err
    else
      tunEnabled = tun and tun.enable == true
    end
    render()
  end)
end

-- ── Toggle ──────────────────────────────────────────────────

local function toggleTun()
  -- Don't block on the refresh loading flag; the PATCH will update state.
  -- If tunEnabled is stale, the next refresh will correct the UI.

  if tunEnabled then
    setTun(false, nil, function(ok, err)
      if ok then
        tunEnabled = false
        lastError  = nil
        render()
        noctalia.notify("Mihomo TUN", "TUN disabled")
      else
        lastError = err
        render()
        noctalia.notifyError("Mihomo TUN", "Failed: " .. (err or "unknown"))
      end
    end)
  else
    setTun(true, lastStack, function(ok, err)
      if ok then
        tunEnabled = true
        lastError  = nil
        render()
        noctalia.notify("Mihomo TUN", "TUN enabled (" .. lastStack .. ")")
      else
        lastError = err
        render()
        noctalia.notifyError("Mihomo TUN", "Failed: " .. (err or "unknown"))
      end
    end)
  end
end

-- ── Lifecycle ───────────────────────────────────────────────

function update()
  noctalia.setUpdateInterval(5000)
  refresh()
end

function onClick()
  toggleTun()
end

function onRightClick()
  noctalia.togglePanel("reza/mihomo-tun:panel")
end

function onSettingsChange(key, _value)
  if key == "stack" then
    lastStack = noctalia.getConfig("stack") or "gVisor"
    render()
  end
end

function onIpc(event, _payload)
  if event == "toggle" then
    toggleTun()
  elseif event == "open-panel" then
    noctalia.togglePanel("reza/mihomo-tun:panel")
  end
end
