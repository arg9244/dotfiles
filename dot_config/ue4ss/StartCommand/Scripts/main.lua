-- =============================================================================
-- Unified Unreal Engine Console-Command Tuner (UE4 / UE5)
-- =============================================================================
-- SCRIPT OVERVIEW:
--   * Combines engine scalability overrides, latency optimizations, and draw-call
--     reductions into a single execution pipeline.
--   * Ensures asynchronous streaming and depth pre-pass remain active.
-- =============================================================================

local UEHelpers = require("UEHelpers")

local CONFIG = {
  -- Delay (in milliseconds) after a level loads before applying commands.
  applyDelayMs = 1500,

  -- Retry delay if the Engine or Kismet System Library is not ready yet.
  retryDelayMs = 2500,

  -- Automatically reapply settings whenever a new level/map is loaded.
  reapplyOnLevelLoad = false,
}

local COMMANDS = {
  ---------------------------------------------------------------------------
  -- 1. Visual Preferences & Image Clarity
  ---------------------------------------------------------------------------
  visual_preferences = {
    -- Post-processing cinematic tonemapper (vignette, film contrast, shadow tint).
    -- Accepted values: 0 (clean image/off), 1 (+contrast), 2 (+vignette), 3 (+shadow tint), 4 (+grain), 5 (full cinematic).
    "r.Tonemapper.Quality 0",

    -- Chromatic Aberration (color fringing and blurring around screen edges).
    -- Accepted values: 0 (off / sharper picture), 1 (on).
    "r.SceneColorFringeQuality 0",

    -- Maximum intensity limit for Chromatic Aberration fringe width percentage.
    -- Accepted values: Float 0.0+ (0.0 = completely off, 1.0+ = increasing width percentage).
    "r.SceneColorFringe.Max 0",

    -- Fast Approximate Anti-Aliasing (FXAA) quality level.
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high), 4 (very high), 5 (max).
    "r.FXAA.Quality 0",

    -- Texture anisotropic filtering (sharpness of textures viewed at oblique angles).
    -- Accepted values: 0, 2, 4, 8, 16 (higher = sharper angled textures).
    "r.MaxAnisotropy 16",

    -- Master Anti-Aliasing scalability group tier for sub-pixel edge smoothing.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.AntiAliasingQuality 2",

    -- Render quality passes for glowing light halos (Bloom).
    -- Accepted values: 0 (off), 1 (low/fast), 2 (medium), 3 (high), 4 (very high), 5 (epic).
    "r.BloomQuality 0",

    -- Camera and velocity object motion blur quality.
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high), 4 (very high).
    "r.MotionBlurQuality 0",

    -- Engine master switch for motion blur post-processing pipelines.
    -- Accepted values: 0 (disabled), 1 (enabled).
    "r.DefaultFeature.MotionBlur 0",

    -- Camera depth of field (background and foreground focal blur).
    -- Accepted values: 0 (off), 1 (low), 2 (high), 3 (very high), 4+ (CircleDOF).
    "r.DepthOfFieldQuality 0",

    -- Lens flare effects around bright light sources (sun halos, anamorphic rings).
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high).
    "r.LensFlareQuality 0",

    -- 3D Volumetric Fog grid density illuminated by light shafts.
    -- Accepted values: 0 (off), 1 (on).
    "r.VolumetricFog 0",

    -- Master switch for real-time 3D volumetric cloud skybox simulation.
    -- Accepted values: 0 (off), 1 (on).
    "r.VolumetricCloud 0",

    -- Vertical Synchronization (locks frame rate to monitor refresh rate).
    -- Accepted values: 0 (off), 1 (on).
    "r.VSync 0",
  },

  ---------------------------------------------------------------------------
  -- 2. Thread Pacing & Frame Latency
  ---------------------------------------------------------------------------
  cpu_and_latency = {
    -- Game thread to Render Hardware Interface (RHI) thread frame synchronization mode.
    -- Accepted values: 0 (sync every frame), 1 (sync on fence / lowest input lag), 2 (no sync).
    "r.GTSyncType 1",

    -- Controls whether the rendering thread is permitted to lag one frame behind the game thread.
    -- Accepted values: 0 (disabled), 1 (enabled / prevents CPU game-thread stalls & stutters).
    "r.OneFrameThreadLag 1",

    -- Controls CPU frame buffering relative to GPU execution completion.
    -- Accepted values: 0 (buffered / higher FPS), 1 (synchronous / forced GPU completion for ultra-low latency).
    "r.FinishCurrentFrame 0",

    -- Internal engine frame rate target cap.
    -- Accepted values: Float 0.0 (uncapped), >0.0 (specific FPS limit cap).
    "t.MaxFPS 60",
  },

  ---------------------------------------------------------------------------
  -- 3. Geometry & Draw Distance (CPU Draw-Call Mitigation)
  ---------------------------------------------------------------------------
  draw_distance_and_geometry = {
    -- Master view distance scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.ViewDistanceQuality 1",

    -- Global object render distance scale multiplier.
    -- Accepted values: Float 0.0+ (0.5 = 50%, 0.7 = 70%, 1.0 = 100% standard distance).
    "r.ViewDistanceScale 0.70",

    -- Minimum detail mode for rendering background decorative props.
    -- Accepted values: 0 (low / essential props only), 1 (medium), 2 (high / all decorative props).
    "r.DetailMode 0",

    -- Static mesh Level of Detail (LOD) distance scaling multiplier.
    -- Accepted values: Float 0.0+ (lower values switch to simplified low-poly LODs closer to camera).
    "r.StaticMeshLODDistanceScale 0.75",

    -- Skeletal mesh Level of Detail (LOD) bias.
    -- Accepted values: Integer (0 = default, >0 = forces lower detail LODs closer to camera, <0 = forces higher detail LODs).
    "r.SkeletalMeshLODBias 0",

    -- Scale factor for the screen radius used in computing discrete LODs for skeletal meshes.
    -- Accepted values: Float 0.25 - 1.0 (lower values switch skeletal meshes to simplified low-poly LODs sooner).
    "r.SkeletalMeshLODRadiusScale 0.75",

    -- Early Z-Pass depth pre-pass rendering mode.
    -- Accepted values: 0 (off), 1 (opaque meshes only), 2 (opaque + masked meshes), 3 (automatic selection).
    "r.EarlyZPass 2",

    -- Includes dynamic moving objects in the early depth pre-pass.
    -- Accepted values: 0 (off / reduces CPU draw-call load), 1 (on).
    "r.EarlyZPassMovable 0",
  },

  ---------------------------------------------------------------------------
  -- 4. Foliage & Grass Density (CPU & Instance Management)
  ---------------------------------------------------------------------------
  foliage_and_grass = {
    -- Master foliage scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.FoliageQuality 1",

    -- Instance density multiplier for placed foliage mesh actors (trees, bushes, shrubs).
    -- Accepted values: Float 0.0+ (0.5 = 50% density, 1.0 = 100% full density).
    "foliage.DensityScale 0.50",

    -- Instance density multiplier for procedural landscape grass materials.
    -- Accepted values: Float 0.0+ (0.5 = 50% density, 1.0 = 100% full density).
    "grass.DensityScale 0.50",
  },

  ---------------------------------------------------------------------------
  -- 5. Shadows & Lighting
  ---------------------------------------------------------------------------
  shadows_and_lighting = {
    -- Master shadow rendering scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.ShadowQuality 1",

    -- Maximum Cascaded Shadow Map (CSM) splits for sun/directional lights.
    -- Accepted values: Integer 1-10 (1 = single cascade, 2 = balanced, 4 = default 4 splits).
    "r.Shadow.CSM.MaxCascades 2",

    -- Smooth transition scale factor between Cascaded Shadow Map (CSM) splits.
    -- Accepted values: Float 1.0+ (2.0 = smooth blending between CSM cascades).
    "r.Shadow.CSM.TransitionScale 2",

    -- Dynamic shadow drawing distance scale multiplier.
    -- Accepted values: Float 0.0+ (0.5 = 50%, 0.65 = 65%, 1.0 = 100% full shadow distance).
    "r.Shadow.DistanceScale 0.65",

    -- Minimum screen-space size threshold required for an object to cast dynamic shadows.
    -- Accepted values: Float 0.0-1.0 (higher values cull more small object shadows).
    "r.Shadow.RadiusThreshold 0.05",

    -- Shadow map filtering, penumbra softness calculation, and quality tier.
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high), 4 (epic), 5 (max).
    "r.ShadowQuality 2",

    -- Maximum resolution map size (in pixels) for per-object dynamic point and spot shadows.
    -- Accepted values: Power-of-two integer (64, 128, 256, 512, 1024, 2048, 4096).
    "r.Shadow.MaxResolution 2048",

    -- Maximum resolution map size (in pixels) for sun/directional Cascaded Shadow Maps.
    -- Accepted values: Power-of-two integer (64, 128, 256, 512, 1024, 2048, 4096).
    "r.Shadow.MaxCSMResolution 4096",

    -- Asynchronous compute execution switch for Screen-Space Ambient Occlusion (SSAO).
    -- Accepted values: 0 (off / graphics queue), 1 (on / uses AMD Async Compute engine).
    "r.AmbientOcclusion.Compute 1",

    -- Master system switch for Unreal Engine 5 Virtual Shadow Maps (VSM).
    -- Accepted values: 0 (off / classic shadow maps), 1 (on / VSM).
    "r.Shadow.Virtual.Enable 0",

    -- Short-range screen-space contact shadows beneath small object edges.
    -- Accepted values: 0 (off), 1 (on).
    "r.ContactShadows 0",
  },

  ---------------------------------------------------------------------------
  -- 6. Particles & Visual Effects (VFX Simulation Management)
  ---------------------------------------------------------------------------
  particles_and_vfx = {
    -- Master Visual Effects (VFX) scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.EffectsQuality 1",

    -- Global quality level tier for Niagara particle visual effects.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "fx.Niagara.QualityLevel 1",

    -- Global spawn count multiplier applied across all active Niagara particle emitters.
    -- Accepted values: Float 0.0+ (0.6 = 60% particle density, 1.0 = 100% full particle spawn).
    "fx.Niagara.GlobalSpawnCountScale 0.60",

    -- Hard cap on the maximum dynamic point lights emitted by Niagara particle effects per frame.
    -- Accepted values: Integer 0-64 (0 = no particle lights, lower values prevent light overlap lag).
    "fx.Niagara.MaxParticleLights 8",

    -- Level of Detail (LOD) reduction bias for legacy Cascade particle systems.
    -- Accepted values: Integer -5 to 5 (positive values shift particles to lower detail tiers sooner).
    "r.ParticleLODBias 1",

    -- Global spawn rate multiplier for legacy Cascade particle emitters.
    -- Accepted values: Float 0.0+ (0.7 = 70% spawn rate, 1.0 = 100% full spawn rate).
    "r.EmitterSpawnRateScale 0.70",
  },

  ---------------------------------------------------------------------------
  -- 7. VRAM & Texture Allocation
  ---------------------------------------------------------------------------
  vram_and_textures = {
    -- Master texture detail scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.TextureQuality 4",

    -- Texture streaming pool VRAM allocation budget in Megabytes (MB).
    -- Accepted values: Integer 0-32768 (set according to available GPU memory limits; 12GB for 16GB GPU).
    "r.Streaming.PoolSize 10240",

    -- Global texture mipmap level bias adjustment.
    -- Accepted values: Float -5.0 to 5.0 (negative = forces higher-res mips, positive = blurrier/faster).
    "r.Streaming.MipBias 0",

    -- Asynchronous disk I/O for texture streaming background loading.
    -- Accepted values: 0 (off / synchronous loading), 1 (on / asynchronous background loading).
    "r.Streaming.AsyncIO 1",

    -- Deferred decal rendering buffer mode (bullet holes, grime, impact marks on dynamic surfaces).
    -- Accepted values: 0 (off), 1 (on).
    "r.DBuffer 1",

    -- Master system toggle switch for rendering decals on world geometry.
    -- Accepted values: 0 (off), 1 (on).
    "r.Decals 1",

    -- Disables checkerboard rendering for Subsurface Scattering (forces full-resolution SSS).
    -- Accepted values: 0 (disabled / full quality SSS), 1 (enabled / half-pixel checkerboard).
    "r.SSS.Checkerboard 0",

    -- Subsurface Scattering buffer resolution format.
    -- Accepted values: 0 (full resolution / sharp skin & translucency), 1 (half resolution).
    "r.sss.halfres 0",

    -- Geometry Buffer (G-Buffer) precision encoding format.
    -- Accepted values: 0 (8-bit profiling), 1 (low precision), 3 (high precision normals / 8-bit packed), 5 (high precision / 10-bit).
    "r.GBufferFormat 3",

    -- Surface shading quality scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.ShadingQuality 2",

    -- Master post-processing feature quality scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.PostProcessQuality 2",
  },

  ---------------------------------------------------------------------------
  -- 8. Ray Tracing & Lumen Overrides
  ---------------------------------------------------------------------------
  lumen_and_raytracing = {
    -- Master switch for Unreal Engine 5 Lumen dynamic global illumination (bounce lighting).
    -- Accepted values: 0 (off / standard ambient lighting), 1 (on / Lumen GI).
    "r.Lumen.DiffuseIndirect.Allow 0",

    -- Master switch for Unreal Engine 5 Lumen dynamic specular reflections.
    -- Accepted values: 0 (off / classic reflections), 1 (on / Lumen reflections).
    "r.Lumen.Reflections.Allow 0",

    -- Hardware Ray Tracing acceleration toggle for Lumen lighting pipelines.
    -- Accepted values: 0 (software ray tracing), 1 (hardware ray tracing).
    "r.Lumen.HardwareRayTracing 0",

    -- Master system switch for hardware Ray Tracing (DXR / RTX).
    -- Accepted values: 0 (off), 1 (on).
    "r.RayTracing.Enable 0",

    -- Hardware ray-traced dynamic global illumination bounce lighting.
    -- Accepted values: 0 (off), 1 (brute force mode), 2 (final gather mode).
    "r.RayTracing.GlobalIllumination 0",

    -- Hardware ray-traced reflections on shiny materials.
    -- Accepted values: 0 (off), 1 (on), 2 (full quality).
    "r.RayTracing.Reflections 0",

    -- Hardware ray-traced ambient occlusion contact shading.
    -- Accepted values: 0 (off), 1 (on).
    "r.RayTracing.AmbientOcclusion 0",

    -- Hardware ray-traced sharp directional, point, and spot shadows.
    -- Accepted values: 0 (off), 1 (on).
    "r.RayTracing.Shadows 0",

    -- Hardware ray-traced reflections and refractions through glass/translucent surfaces.
    -- Accepted values: 0 (off), 1 (on).
    "r.RayTracing.Translucency 0",

    -- Screen-Space Global Illumination (SSGI) quality level.
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high), 4 (very high).
    "r.SSGI.Quality 0",

    -- Master Global Illumination scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.GlobalIlluminationQuality 0",

    -- Master Reflection scalability preset group.
    -- Accepted values: 0 (low), 1 (medium), 2 (high), 3 (epic), 4 (cinematic).
    "sg.ReflectionQuality 2",

    -- Screen-Space Reflection (SSR) rendering quality tier.
    -- Accepted values: 0 (off), 1 (low), 2 (medium), 3 (high), 4 (very high).
    "r.SSR.Quality 4",

    -- Maximum surface roughness limit threshold for rendering screen-space reflections.
    -- Accepted values: Float 0.0 to 1.0 (lower values restrict reflections only to shiny surfaces).
    "r.SSR.MaxRoughness 0.9",

    -- Temporal frame accumulation blurring for screen-space reflection denoisers.
    -- Accepted values: 0 (off / faster / no ghosting), 1 (on / smooth / temporally denoised).
    "r.SSR.Temporal 0",
  },

  ---------------------------------------------------------------------------
  -- 9. Nanite (Virtualized Geometry Overrides)
  ---------------------------------------------------------------------------
  nanite = {
    -- Master rendering switch for Nanite virtualized geometry meshes.
    -- Accepted values: 0 (disabled / forces standard static mesh LOD fallbacks), 1 (enabled).
    "r.Nanite 0",

    -- Forces Nanite rendering off at the execution layer across modern UE5 pipelines.
    -- Accepted values: 0 (disabled / force fallback LODs), 1 (enabled).
    "r.Nanite.ProjectEnabled 0",

    -- Nanite shadow evaluation pass for static and dynamic light sources.
    -- Accepted values: 0 (off), 1 (on).
    "r.Nanite.Shadows 0",

    -- VRAM memory pool budget allocation for Nanite geometry streaming.
    -- Accepted values: Integer 0+ (0 = releases Nanite geometry pool memory allocation).
    "r.Nanite.Streaming.PoolSize 0",
  },
}

-- =============================================================================
-- Execution Logic (DO NOT MODIFY)
-- =============================================================================

local function log(msg)
  print("[main.lua] " .. tostring(msg))
end

local function getKSL()
  local ksl = UEHelpers.GetKismetSystemLibrary()
  if ksl and ksl:IsValid() then
    return ksl
  end
end

local function getEngine()
  local engine = FindFirstOf("Engine")
  if engine and engine:IsValid() then
    return engine
  end
end

local function buildCommandList()
  local cmds = {}

  -- Flatten all categories into a single execution table
  for _, category in pairs(COMMANDS) do
    for _, cmd in ipairs(category) do
      table.insert(cmds, cmd)
    end
  end

  return cmds
end

local function applyCommands(cmds)
  local ksl = getKSL()
  local engine = getEngine()

  if not ksl or not engine then
    return false
  end

  ExecuteInGameThread(function()
    for _, cmd in ipairs(cmds) do
      ksl:ExecuteConsoleCommand(engine, cmd, nil)
    end
  end)

  return true
end

local applyToken = 0

local function scheduleApply(delayMs)
  applyToken = applyToken + 1
  local token = applyToken
  local cmds = buildCommandList()

  ExecuteWithDelay(delayMs or CONFIG.applyDelayMs, function()
    if token ~= applyToken then
      return
    end

    local ok = applyCommands(cmds)

    if not ok then
      log("Engine/KSL not ready yet; retrying.")

      ExecuteWithDelay(CONFIG.retryDelayMs, function()
        if token == applyToken then
          applyCommands(cmds)
        end
      end)
    end
  end)
end

if CONFIG.reapplyOnLevelLoad then
  NotifyOnNewObject("/Script/Engine.Level", function()
    scheduleApply()
  end)
end

-- Initial apply in case the level already exists when this script loads.
scheduleApply(2500)
