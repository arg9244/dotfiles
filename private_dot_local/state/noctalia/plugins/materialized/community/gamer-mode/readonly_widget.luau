--!nonstrict
--
-- Bar widget: a glyph plus a live metrics row. It owns no state -- it renders
-- whatever the service publishes and sends commands back through `noctalia.state`.
--
-- Each metric segment is a separately coloured label inside a barWidget.render tree,
-- so a single hot reading turns only that segment red rather than the entire bar.
--
-- The glyph is included explicitly because render() replaces the built-in glyph/text
-- row; setGlyph/setText have no visible effect once a render tree is active.

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

-- 80 °C is the level system monitors (btop, lm-sensors) use to flag a warning —
-- CPUs throttle around 85-90 °C and GPUs go critical at 90-105 °C, so 80 is a
-- conservative red flag that fires before sustained heat becomes dangerous.
local TEMP_THRESHOLD_C = 80

-- colorFor returns "error" when a metric fraction is at or above 90%, otherwise the
-- bar's base color. Each metric is evaluated on its own, so only the segment that
-- crossed the threshold turns red.
local function colorFor(fraction, baseColor)
    if fraction ~= nil and (tonumber(fraction) or 0) >= 0.9 then
        return "error"
    end
    return baseColor
end

-- colorForTemp returns "error" when a temperature is at or above 80 °C, otherwise the
-- bar's base color. Temperatures use their own threshold — unlike usage percentages, a
-- 70 °C reading is hot for a CPU but mild for a GPU, so tying them to usage would paint
-- temps red when the chip is busy, not when it is actually hot.
local function colorForTemp(temp, baseColor)
    local celsius = tonumber(temp)
    if celsius ~= nil and celsius >= TEMP_THRESHOLD_C then
        return "error"
    end
    return baseColor
end

-- formatBarSegments returns a list of { text, color } pairs, one per metric segment,
-- each coloured on its own threshold. CPU, RAM, GPU and VRAM usage each turn red at 90 %
-- independently; temperatures turn red at 80 °C independently; network rates have no
-- ceiling to measure against, so they stay at the base colour. Spacing is embedded in
-- the text so the visual format matches the previous single-string layout.
function M.formatBarSegments(m, showTemps, baseColor)
    local segments = {}
    if type(m) ~= "table" or not m.available then
        return segments
    end

    local function add(text, color)
        segments[#segments + 1] = { text = text, color = color }
    end

    -- System group: CPU% + temp + RAM
    add(percent(m.cpuPerc), colorFor(m.cpuPerc, baseColor))
    if showTemps and tonumber(m.cpuTemp) then
        add(withTemp("", showTemps, m.cpuTemp), colorForTemp(m.cpuTemp, baseColor))
    end
    add(" " .. gibibytes(m.memUsedMb), colorFor(m.memPerc, baseColor))

    -- Graphics group: GPU% + temp + VRAM (only when GPU is present)
    if m.gpuAvailable and m.gpuPerc then
        add("   " .. percent(m.gpuPerc), colorFor(m.gpuPerc, baseColor))
        if showTemps and tonumber(m.gpuTemp) then
            add(withTemp("", showTemps, m.gpuTemp), colorForTemp(m.gpuTemp, baseColor))
        end
        if m.vramUsedMb then
            add(" " .. gibibytes(m.vramUsedMb), colorFor(m.vramPerc, baseColor))
        end
    end

    -- Network: RX / TX rates (no percentage — stays at base colour)
    if m.netRxPerSec and m.netTxPerSec then
        add("  " .. "↓" .. netRate(m.netRxPerSec) .. " ↑" .. netRate(m.netTxPerSec), baseColor)
    end

    return segments
end

local function render()
    local showTemps = noctalia.getConfig("show_temps") ~= false
    local baseColor = gameMode.enabled and "primary" or "on_surface"
    local glyph = noctalia.getConfig("glyph") or "device-gamepad-2"

    barWidget.setTooltip(M.formatTooltip(metrics, showTemps, gameMode))

    -- barWidget.render rebuilds the glyph/text row from a ui.* tree. Each metric is a
    -- separate ui.label so the colours are independent. The container matches the bar
    -- orientation: a row on horizontal bars, a column on side bars.
    local container = barWidget.isVertical() and ui.column or ui.row
    local children = {
        ui.glyph({ name = glyph, color = baseColor }),
    }

    if metrics.available then
        for _, seg in ipairs(M.formatBarSegments(metrics, showTemps, baseColor)) do
            table.insert(children, ui.label({ text = seg.text, color = seg.color }))
        end
    end

    barWidget.render(container({ gap = 0, align = "center" }, children))
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
