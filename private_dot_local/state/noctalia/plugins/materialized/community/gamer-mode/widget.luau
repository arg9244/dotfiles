--!nonstrict
--
-- Bar widget: a live metrics label plus a hover tooltip. It owns no state -- it renders
-- whatever the service publishes and sends commands back through `noctalia.state`.

local PANEL_ID = "nomadcxx/gamer-mode:main"
local MIB_PER_GIB = 1024

local M = {}

local metrics = noctalia.state.get("metrics") or { available = false }
local gameMode = noctalia.state.get("game_mode") or { enabled = false, suspended = {} }
local nonceCounter = 0

local function gibibytes(mib)
    return string.format("%.1fG", (tonumber(mib) or 0) / MIB_PER_GIB)
end

local function percent(fraction)
    return string.format("%d%%", math.floor((tonumber(fraction) or 0) * 100 + 0.5))
end

-- withTemp appends a temperature only when there is one to show, so a machine without
-- sensors reads as "GPU 18%" rather than "GPU 18% 0°".
local function withTemp(label, showTemps, temp)
    if showTemps and tonumber(temp) then
        return label .. string.format(" %d°", math.floor(tonumber(temp) + 0.5))
    end
    return label
end

function M.formatTooltip(m, showTemps, gm)
    m = m or {}
    if not m.available then
        return noctalia.tr("widget.tooltip_loading")
    end

    local parts = {
        withTemp("CPU " .. percent(m.cpuPerc), showTemps, m.cpuTemp),
        "RAM " .. gibibytes(m.memUsedMb),
    }
    -- GPU and VRAM segments are omitted entirely when unsupported: an empty reading is
    -- more honest than a zero that looks like an idle GPU.
    if m.gpuAvailable and m.gpuPerc then
        parts[#parts + 1] = withTemp("GPU " .. percent(m.gpuPerc), showTemps, m.gpuTemp)
    end
    if m.vramUsedMb then
        parts[#parts + 1] = "VRAM " .. gibibytes(m.vramUsedMb)
    end

    local tooltip = table.concat(parts, " | ")
    if gm and gm.enabled then
        tooltip = noctalia.tr("notify.enabled_title") .. " | " .. tooltip
    end
    return tooltip
end

-- netRate formats a byte-per-second value compactly for the bar. MB/s gets two
-- decimals below 10M and one at/above (1.67M, 12.3M); K and B stay integer
-- (340K, 52) — they carry enough weight at 0 decimals to read at a glance.
local function netRate(bps)
    local b = tonumber(bps) or 0
    if b >= 1024 * 1024 then
        local mbps = b / (1024 * 1024)
        if mbps < 10 then
            return string.format("%.2fM", mbps)
        else
            return string.format("%.1fM", mbps)
        end
    elseif b >= 1024 then
        return string.format("%.0fK", b / 1024)
    end
    return string.format("%.0f", b)
end

-- formatBarText builds the compact bar label: raw values only, no icons or letter
-- labels. CPU+temp and RAM form one group, GPU+temp and VRAM form another, and the
-- two are separated by extra spacing. Network rates follow with a smaller gap. The
-- full labelled reading stays on the hover tooltip.
function M.formatBarText(m, showTemps)
    m = m or {}
    if not m.available then
        return noctalia.tr("widget.tooltip_loading")
    end

    -- System group: CPU% + temp + RAM
    local system = percent(m.cpuPerc) .. withTemp("", showTemps, m.cpuTemp) .. " " .. gibibytes(m.memUsedMb)

    -- Graphics group: GPU% + temp + VRAM (only when GPU is present)
    local graphics = nil
    if m.gpuAvailable and m.gpuPerc then
        graphics = percent(m.gpuPerc) .. withTemp("", showTemps, m.gpuTemp)
        if m.vramUsedMb then
            graphics = graphics .. " " .. gibibytes(m.vramUsedMb)
        end
    end

    -- Network: RX / TX rates (small gap after the preceding group)
    local network = nil
    if m.netRxPerSec and m.netTxPerSec then
        network = "↓" .. netRate(m.netRxPerSec) .. " ↑" .. netRate(m.netTxPerSec)
    end

    -- System and graphics are distinct groups (3-space gap); network follows
    -- with a smaller 2-space gap.
    local text = system
    if graphics then
        text = text .. "   " .. graphics
    end
    if network then
        text = text .. "  " .. network
    end
    return text
end

-- atThreshold returns true when any supported metric has crossed 90%, so the
-- bar can turn red without opening the panel — matching niri's default warning.
local function atThreshold(m)
    if type(m) ~= "table" or not m.available then
        return false
    end
    return (tonumber(m.cpuPerc) or 0) >= 0.9
        or (tonumber(m.memPerc) or 0) >= 0.9
        or (m.gpuPerc and (tonumber(m.gpuPerc) or 0) >= 0.9)
        or (m.vramPerc and (tonumber(m.vramPerc) or 0) >= 0.9)
end

local function render()
    local showTemps = noctalia.getConfig("show_temps") ~= false
    local baseColor = gameMode.enabled and "primary" or "on_surface"

    barWidget.setTooltip(M.formatTooltip(metrics, showTemps, gameMode))
    barWidget.setText(M.formatBarText(metrics, showTemps))
    -- Red when any metric crosses 90%, otherwise primary (GM on) or on_surface.
    barWidget.setColor(atThreshold(metrics) and "error" or baseColor)
end

local function sendCommand(action)
    nonceCounter = nonceCounter + 1
    noctalia.state.set("command", {
        nonce = noctalia.nowMs() * 1000 + nonceCounter,
        action = action,
    })
end

-- Left-click opens the panel by default. A first click should show what the machine is
-- doing, not suspend a list of programs the user has not read yet.
function M.onClick()
    if (noctalia.getConfig("click_action") or "open_panel") == "toggle" then
        sendCommand("toggle")
    else
        noctalia.togglePanel(PANEL_ID)
    end
end

-- Right-click always toggles, whatever click_action says, so the one-click path stays
-- available without opening the panel first.
function M.onRightClick()
    sendCommand("toggle")
end

noctalia.state.watch("metrics", function(value)
    metrics = type(value) == "table" and value or { available = false }
    render()
end)

noctalia.state.watch("game_mode", function(value)
    gameMode = type(value) == "table" and value or { enabled = false, suspended = {} }
    render()
end)

-- ── shell entry points (must be globals) ──

function onClick()
    M.onClick()
end

function onRightClick()
    M.onRightClick()
end

function onConfigChanged()
    render()
end

render()

return M
