// =============================================================================
// SECTION 1: PERFORMANCE, HARDWARE ACCELERATION & GRAPHICS
// =============================================================================

// Set font glyph rendering cache size in Skia (in MB)
user_pref("gfx.content.skia-font-cache-size", 20);

// Force hardware WebRender compositor across all rendering pipelines
user_pref("gfx.webrender.all", true);

// Enable native compositor sub-surfaces for lower display latency
user_pref("gfx.webrender.compositor", true);

// Offload HTML5 2D canvas rasterization to the GPU
user_pref("gfx.canvas.accelerated", true);

// Force-enable hardware acceleration layers
user_pref("layers.acceleration.force-enabled", true);

// Enable hardware-accelerated video decoding via VA-API
user_pref("media.ffmpeg.vaapi.enabled", true);

// Prevent color format conversion bottlenecks in hardware video decoding
user_pref("media.ffmpeg.vaapi-drm-format.force", 0);

// Enable low-latency hardware video decoding for real-time streams
user_pref("media.ffmpeg.low-latency.enabled", true);

// Use native system desktop portal for file open and save dialogs
user_pref("widget.use-xdg-desktop-portal.file-picker", 1);

// Enable native fractional scaling protocol on Wayland compositors
user_pref("widget.wayland.fractional-scale.enabled", true);

// Optimize compositor drawing by marking opaque window regions
user_pref("widget.wayland.opaque-region.enabled", true);

// Use Wayland cursor-shape protocol for consistent cursor scaling across displays
user_pref("widget.wayland.cursor-spec-enabled", true);

// Increase image chunk decode size to accelerate image rendering
user_pref("image.mem.decode_bytes_at_a_time", 32768);

// Remove fullscreen enter transition delay
user_pref("full-screen-api.transition-duration.enter", "0 0");

// Remove fullscreen exit transition delay
user_pref("full-screen-api.transition-duration.leave", "0 0");

// Completely disable accessibility engine hooks to save CPU and RAM
user_pref("accessibility.force_disabled", 1);


// =============================================================================
// SECTION 2: AGGRESSIVE CACHING & NETWORK OPTIMIZATION (LOW-BANDWIDTH TUNED)
// =============================================================================

// Enable on-disk HTTP caching
user_pref("browser.cache.disk.enable", true);

// Ensure HTTPS assets and pages are stored to disk cache
user_pref("browser.cache.disk_cache_ssl", true);

// Disable automatic disk cache sizing to enforce manual capacity
user_pref("browser.cache.disk.smart_size.enabled", false);

// Set maximum disk cache capacity to 10 GB (in KB)
user_pref("browser.cache.disk.capacity", 10485760);

// Remove individual file size limit for disk cache (-1 = unlimited; cache everything)
user_pref("browser.cache.disk.max_entry_size", -1);

// Keep up to 32 MB of disk cache index metadata in RAM for fast lookups
user_pref("browser.cache.disk.metadata_memory_limit", 32768);

// Check web server for fresh content only ONCE PER SESSION (0 = once per session)
// Subsequent page loads pull 100% from local cache without contacting the server
user_pref("browser.cache.check_doc_frequency", 0);

// Pause cache writes if available drive storage drops below 5 GB
user_pref("browser.cache.disk.free_space_soft_limit_mb", 5120);

// Hard stop for disk cache operations if drive storage drops below 1 GB
user_pref("browser.cache.disk.free_space_hard_limit_mb", 1024);

// Enable volatile in-memory caching
user_pref("browser.cache.memory.enable", true);

// Allocate up to 2 GB of RAM for volatile in-memory caching (in KB)
user_pref("browser.cache.memory.capacity", 2097152);

// Allow individual assets up to 100 MB to reside directly in memory cache
user_pref("browser.cache.memory.max_entry_size", 102400);

// Enable offline application and service-worker cache
user_pref("browser.cache.offline.enable", true);

// Set offline cache capacity to 1 GB (in KB)
user_pref("browser.cache.offline.capacity", 1048576);

// Keep in-memory image surface cache high to avoid re-decoding images
user_pref("image.mem.surfacecache.max_size_kb", 1048576);

// Retain decoded page states in Back-Forward Cache (bfcache)
user_pref("browser.sessionhistory.max_total_viewers", -1);

// Enable native lazy loading so offscreen images only download when scrolled to
user_pref("dom.image-lazy-loading.enabled", true);

// Enable background preprocessing to speed up IndexedDB reads
user_pref("dom.indexedDB.preprocessing", true);

// Disable Race Cache With Network to strictly favor cache hits over slow connection races
user_pref("network.http.rcwn.enabled", false);

// Prioritize critical render-blocking page resources before fetching background assets
user_pref("network.http.tailing.enabled", true);

// Disable HTTP request socket pacing bursts for immediate packet delivery
user_pref("network.http.pacing.requests.enabled", false);

// Limit speculative urgent TCP connections to preserve connection bandwidth
user_pref("network.http.max-urgent-start-excess-connections", 1);

// Lower maximum redirect hops to truncate circular tracking redirects early
user_pref("network.http.redirection-limit", 10);

// Fall back immediately to IPv4 if dual-stack lookups stall
user_pref("network.http.fast-fallback-to-IPv4", true);

// Ensure HTTP/2 multiplexing protocol is enabled
user_pref("network.http.spdy.enabled.http2", true);

// Enable HTTP/3 (QUIC over UDP) to prevent head-of-line blocking
user_pref("network.http.http3.enable", true);

// Allow servers to advertise alternative service endpoints (such as HTTP/3)
user_pref("network.http.altsvc.enabled", true);

// Keep idle TCP connections active for 5 minutes before probing
user_pref("network.tcp.keepalive.idle_time", 300);

// Set TCP keepalive retry probe interval to 10 seconds
user_pref("network.tcp.keepalive.retry_interval", 10);

// Increase TLS session resumption token cache to avoid full re-handshakes
user_pref("network.ssl_tokens_cache_capacity", 65536);

// Disable TLS channel ID validation checks on session token resumption
user_pref("network.ssl_tokens_cache_use_ssl_channel_id", false);

// Increase network socket buffer cache chunk size to 64 KB
user_pref("network.buffer.cache.size", 65535);

// Set number of network buffer cache chunks
user_pref("network.buffer.cache.count", 48);

// Prevent bufferbloat on slow links: cap global concurrent connections to 256
user_pref("network.http.max-connections", 256);

// Allow up to 8 persistent HTTP keep-alive connections per domain
user_pref("network.http.max-persistent-connections-per-server", 8);

// Reduce initial HTTP connection scheduling delay (in seconds)
user_pref("network.http.request.max-start-delay", 5);

// Cache successful DNS lookup entries for 7 days (in seconds) to avoid DNS round-trips
user_pref("network.dnsCacheExpiration", 604800);

// Expand DNS cache table to hold up to 10,000 domains
user_pref("network.dnsCacheEntries", 10000);

// Allow serving slightly stale DNS records immediately while revalidating in background
user_pref("network.dnsCacheExpirationGracePeriod", 3600);


// =============================================================================
// SECTION 3: MEDIA BUFFERING & STREAMING
// =============================================================================

// Block autoplay of both audio and video to save bandwidth (5 = block audio & video)
user_pref("media.autoplay.default", 5);
user_pref("media.autoplay.blocking_policy", 2);

// Allocate 4 GB for file-backed media cache to hold extended video buffers
user_pref("media.cache_size", 4194304);

// Set maximum size for memory media chunk cache (in KB)
user_pref("media.memory_cache_max_size", 131072);

// Set combined memory limit for active media stream buffers to 2 GB
user_pref("media.memory_caches_combined_limit_kb", 2097152);

// Allow video buffering up to 2 hours ahead when not constrained by player
user_pref("media.cache_readahead_limit", 7200);

// Resume buffering after a seek when buffer drops below 45 minutes
user_pref("media.cache_resume_threshold", 2700);

// Hide the hovering Picture-in-Picture overlay button on video elements
user_pref("media.videocontrols.picture-in-picture.video-toggle.always-show", false);

// Open PDF attachments directly inside Firefox's built-in PDF viewer
user_pref("browser.download.open_pdf_attachments_inline", true);

// Disable JavaScript execution inside the PDF viewer to eliminate exploit surface
user_pref("pdfjs.enableScripting", false);


// =============================================================================
// SECTION 4: WEBRTC & REAL-TIME COMMUNICATIONS
// =============================================================================

// Prevent WebRTC from leaking local private IP addresses during negotiation
user_pref("media.peerconnection.ice.default_address_only", true);

// Suppress host candidate negotiation in WebRTC to hide local interface addresses
user_pref("media.peerconnection.ice.no_host", true);

// Enable VP9 video codec negotiation for high-efficiency WebRTC streaming
user_pref("media.peerconnection.video.vp9_enabled", true);

// Enable zero-copy hardware encoding pipeline for H.264 WebRTC screen sharing
user_pref("media.webrtc.hw.h264.copyless", true);

// Maintain browser window and screen capture capabilities for WebRTC sharing
user_pref("media.getusermedia.browser.enabled", true);

// Support up to 2 stereo channels for microphone capture in WebRTC
user_pref("media.getusermedia.audio.max_channels", 2);

// Disable browser-level Automatic Gain Control to let web apps manage volume
user_pref("media.getusermedia.audio.processing.agc.enabled", false);

// Disable simulated test media streams for webcam and microphone capture
user_pref("media.navigator.streams.fake", false);


// =============================================================================
// SECTION 5: DNS & NETWORK LEAK PREVENTION
// =============================================================================

// Disable Firefox internal TRR to delegate all DNS queries to the system resolver
user_pref("network.trr.mode", 5);

// Prevent Firefox from issuing auxiliary HTTPS/SVCB queries that bypass local DNS
user_pref("network.dns.native-https-query", false);

// Disable IPv6 DNS lookups to prevent timeouts when IPv6 is unroutable
user_pref("network.dns.disableIPv6", true);

// Disable background captive portal detection requests
user_pref("network.captive-portal-service.enabled", false);

// Disable periodic network connectivity checks to Mozilla servers
user_pref("network.connectivity-service.enabled", false);

// Enforce remote DNS resolution through proxy when SOCKS is configured
user_pref("network.proxy.socks_remote_dns", true);

// Block UNC network share paths to prevent local credential and NTLM leaks
user_pref("network.file.disable_unc_paths", true);

// Clear supported GIO/GVFS protocols to close potential proxy bypass vectors
user_pref("network.gio.supported-protocols", "");

// Restrict HTTP authentication dialog prompts triggered by cross-origin subresources
user_pref("network.auth.subresource-http-auth-allow", 1);

// Send only scheme, host, and port in cross-origin HTTP Referer headers
user_pref("network.http.referer.XOriginTrimmingPolicy", 2);

// Do not spoof Referer source to prevent breaking CSRF security protections
user_pref("network.http.referer.spoofSource", false);

// Display internationalized domain names in Punycode to prevent spoofing attacks
user_pref("network.IDN_show_punycode", true);

// Keep speculative asset and parallel prefetching off to prevent starving active downloads
user_pref("network.prefetch-next", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.dns.disablePrefetchFromHTTPS", true);
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.predictor.enabled", false);
user_pref("network.predictor.enable-prefetch", false);

// Clear captive portal detection endpoint URL
user_pref("captivedetect.canonicalURL", "");


// =============================================================================
// SECTION 6: PRIVACY, TRACKING & COOKIE PARTITIONING
// =============================================================================

// Set Enhanced Tracking Protection to Strict mode to enable Total Cookie Protection
user_pref("browser.contentblocking.category", "strict");

// Enforce dynamic first-party cookie isolation (Total Cookie Protection)
user_pref("network.cookie.cookieBehavior", 5);

// Keep default cookie lifetime policy so website logins persist normally
user_pref("network.cookie.lifetimePolicy", 0);

// Partition Web Service Workers by top-level domain to prevent cross-site tracking
user_pref("privacy.partition.serviceWorkers", true);

// Purge state and cookies from bounce-tracking redirect domains
user_pref("privacy.bounceTrackingProtection.enabled", true);

// Enable modern WebCompat-friendly fingerprinting protection
user_pref("privacy.fingerprintingProtection", true);

// Enable automatic stripping of known tracking query tokens from URLs
user_pref("privacy.query_stripping.enabled", true);

// Specify list of tracking query parameters to automatically strip from URLs
user_pref("privacy.query_stripping.strip_list", "__hsfp __hssc __hstc __s _hsenc _openstat dclid fbclid gbraid gclid igshid mc_eid msclkid twclid wbraid");

// Block known cryptocurrency mining scripts from executing
user_pref("privacy.trackingprotection.cryptomining.enabled", true);

// Block known third-party browser fingerprinting scripts
user_pref("privacy.trackingprotection.fingerprinting.enabled", true);

// Prevent pages from detecting installed browser extensions via mozAddonManager
user_pref("privacy.resistFingerprinting.block_mozAddonManager", true);

// Prevent websites from tracking resources injected by extension content scripts
user_pref("privacy.antitracking.isolateContentScriptResources", true);

// Send Global Privacy Control (GPC) opt-out signal to all visited websites
user_pref("privacy.globalprivacycontrol.enabled", true);

// Enable custom browser history settings view in preferences
user_pref("privacy.history.custom", true);

// Request English web page versions to reduce browser locale fingerprinting
user_pref("privacy.spoof_english", 1);

// Maintain tracking protection baseline allow-list to prevent web breakage
user_pref("privacy.trackingprotection.allow_list.baseline.enabled", true);

// Maintain tracking protection convenience allow-list to ensure functional logins
user_pref("privacy.trackingprotection.allow_list.convenience.enabled", true);

// Disable navigator.sendBeacon API to prevent background tracking pings on tab close
user_pref("beacon.enabled", false);


// =============================================================================
// SECTION 7: SECURITY & CERTIFICATES
// =============================================================================

// Upgrade all connections to HTTPS and block unencrypted HTTP fallback
user_pref("dom.security.https_only_mode", true);

// Automatically attempt HTTPS first for all address bar requests
user_pref("dom.security.https_first", true);

// Offer HTTPS alternatives on secure connection error pages
user_pref("dom.security.https_only_mode_error_page_user_suggestions", true);

// Treat servers with unsafe SSL/TLS renegotiation as broken connections
user_pref("security.ssl.treat_unsafe_negotiation_as_broken", true);

// Disable TLS 1.3 0-RTT data to eliminate replay attacks on resumed connections
user_pref("security.tls.enable_0rtt_data", false);

// Disable online OCSP certificate checks (saves latency on slow connections and protects privacy)
user_pref("security.OCSP.enabled", 0);

// Strictly enforce public key pinning (HPKP) to prevent MITM attacks
user_pref("security.cert_pinning.enforcement_level", 2);

// Disable Content Security Policy violation report transmissions
user_pref("security.csp.reporting.enabled", false);

// Require prompt before sharing WebAuthn device attestation data
user_pref("security.webauthn.always_allow_direct_attestation", false);

// Enforce a 1-second delay before security confirmation dialog buttons become clickable
user_pref("security.dialog_enable_delay", 1000);

// Display explicit insecure connection text warning on unencrypted pages
user_pref("security.insecure_connection_text.enabled", true);

// Display advanced technical information on SSL/TLS certificate error pages
user_pref("browser.xul.error_pages.expert_bad_cert", true);

// Prevent uploading file download metadata to remote Safe Browsing servers
user_pref("browser.safebrowsing.downloads.remote.enabled", false);

// Disable local enterprise Data Loss Prevention (DLP) content analysis
user_pref("browser.contentanalysis.enabled", false);

// Set default DLP content analysis action to allow all operations
user_pref("browser.contentanalysis.default_result", 0);

// Disable Windows SSPI authentication mechanisms on non-Windows platforms
user_pref("network.auth.use_sspi", false);


// =============================================================================
// SECTION 8: DOM API & ATTACK SURFACE REDUCTION
// =============================================================================

// Disable Web Vibration API
user_pref("dom.vibrator.enabled", false);

// Disable WebVR and WebXR interfaces
user_pref("dom.vr.enabled", false);

// Disable Web Telephony API
user_pref("dom.telephony.enabled", false);

// Disable device motion and orientation sensors
user_pref("device.sensors.enabled", false);

// Disable device ambient light sensor queries
user_pref("device.sensors.ambientLight.enabled", false);

// Disable Battery Status API
user_pref("dom.battery.enabled", false);

// Disable Gamepad API
user_pref("dom.gamepad.enabled", false);

// Completely disable Web Notifications API
user_pref("dom.webnotifications.enabled", false);

// Completely disable Web Push notification framework
user_pref("dom.push.enabled", false);

// Disable persistent background WebSocket connection to Mozilla Push Service
user_pref("dom.push.connection.enabled", false);

// Allow web applications to display custom context menus
user_pref("dom.event.contextmenu.enabled", true);

// Automatically apply rel="noopener" to links opening in new windows
user_pref("dom.targetBlankNoOpener.enabled", true);

// Disable HTML5 canvas capture stream API
user_pref("canvas.capturestream.enabled", false);

// Prevent web scripts from resizing or repositioning the browser window
user_pref("dom.disable_window_move_resize", true);


// =============================================================================
// SECTION 9: PROCESS & MEMORY MANAGEMENT
// =============================================================================

// Set maximum number of content worker processes for parallel page execution
user_pref("dom.ipc.processCount", 8);

// Set process count limit for site-isolated web content
user_pref("dom.ipc.processCount.webIsolated", 8);

// Expose 12 CPU logical cores to JavaScript navigator.hardwareConcurrency
user_pref("dom.maxHardwareConcurrency", 12);

// Prevent OS scheduler from deprioritizing background tab rendering
user_pref("dom.ipc.processPriorityManager.backgroundUsesLowPriority", false);

// Enable automatic background tab unloading under critical system memory pressure
user_pref("browser.tabs.unloadOnLowMemory", true);

// Keep inactive background tabs in memory for at least 5 minutes before unloading
user_pref("browser.tabs.min_inactive_duration_before_unload", 300000);

// Set system memory commit buffer threshold to 4 GB before initiating tab discard
user_pref("browser.low_commit_space_threshold_mb", 4096);

// Back/forward navigation history stack (retained in memory)
user_pref("browser.sessionhistory.max_entries", 25);

// Set maximum number of closed tabs retained in the undo buffer
user_pref("browser.sessionstore.max_tabs_undo", 25);

// Set maximum number of closed windows retained in the undo buffer
user_pref("browser.sessionstore.max_windows_undo", 5);

// Prevent saving sensitive session data (cookies, POST data) for all sites
user_pref("browser.sessionstore.privacy_level", 2);

// Save session restore state to disk every 3 minutes to reduce drive writes
user_pref("browser.sessionstore.interval", 180000);

// Disable capturing and caching screenshot thumbnails of visited web pages
user_pref("browser.pagethumbnails.capturing_disabled", true);

// Expand database capacity for visited URL history before automatic pruning
user_pref("places.history.expiration.transient_current_max_pages", 1048576);

// Keep Places SQLite history and bookmark databases defragmented
user_pref("storage.vacuum.last.places", 1);

// Relax JavaScript garbage collection frequency threshold to prevent micro-stutter
user_pref("javascript.options.mem.gc_high_frequency_time_limit_ms", 1000);


// =============================================================================
// SECTION 10: TELEMETRY, SHIELD & DATA COLLECTION
// =============================================================================

// Master switch to disable all Mozilla data submission policies
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.usage.uploadEnabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.server", "data:,");
user_pref("toolkit.telemetry.archive.enabled", false);
user_pref("toolkit.telemetry.newProfilePing.enabled", false);
user_pref("toolkit.telemetry.shutdownPingSender.enabled", false);
user_pref("toolkit.telemetry.updatePing.enabled", false);
user_pref("toolkit.telemetry.bhrPing.enabled", false);
user_pref("toolkit.telemetry.firstShutdownPing.enabled", false);
user_pref("toolkit.telemetry.coverage.opt-out", true);
user_pref("toolkit.coverage.opt-out", true);
user_pref("toolkit.coverage.endpoint.base", "");
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("app.normandy.enabled", false);
user_pref("app.normandy.api_url", "");
user_pref("breakpad.reportURL", "");
user_pref("browser.crashReports.unsubmittedCheck.enabled", false);
user_pref("browser.crashReports.unsubmittedCheck.autoSubmit2", false);
user_pref("browser.tabs.crashReporting.sendReport", false);
user_pref("nimbus.rollouts.enabled", false);


// =============================================================================
// SECTION 11: AI, EXPERIMENTS & BROWSER ANNOYANCES
// =============================================================================

user_pref("browser.ai.control.default", "blocked");
user_pref("browser.ml.enable", false);
user_pref("browser.ml.chat.enabled", false);
user_pref("browser.ml.chat.menu", false);
user_pref("browser.ml.linkPreview.enabled", false);
user_pref("browser.tabs.groups.smart.enabled", false);
user_pref("extensions.pocket.enabled", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.preferences.moreFromMozilla", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.discovery.enabled", false);
user_pref("browser.uitour.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);
user_pref("browser.bookmarks.restore_default_bookmarks", false);


// =============================================================================
// SECTION 12: SILENT AUTOMATIC DOWNLOADS
// =============================================================================

user_pref("browser.download.useDownloadDir", true);
user_pref("browser.download.alwaysOpenPanel", false);
user_pref("browser.download.manager.addToRecentDocs", false);
user_pref("browser.download.always_ask_before_handling_new_types", false);
user_pref("browser.download.start_downloads_in_tmp_dir", true);
user_pref("browser.helperApps.deleteTempFileOnExit", true);


// =============================================================================
// SECTION 13: TAB MANAGEMENT, NAVIGATION & UI ERGONOMICS
// =============================================================================

user_pref("browser.tabs.loadBookmarksInTabs", true);
user_pref("browser.tabs.closeWindowWithLastTab", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.tabs.remote.warmup.enabled", true);
user_pref("browser.tabs.tabmanager.enabled", false);
user_pref("browser.tabs.searchclipboardfor.middleclick", false);
user_pref("middlemouse.contentLoadURL", false);
user_pref("browser.link.open_newwindow", 3);
user_pref("browser.link.open_newwindow.restriction", 0);
user_pref("browser.bookmarks.openInTabClosesMenu", false);
user_pref("browser.urlbar.trimURLs", false);
user_pref("browser.urlbar.trimHttps", true);
user_pref("browser.urlbar.untrimOnUserInteraction.featureGate", true);
user_pref("browser.urlbar.showSearchTerms.enabled", false);
user_pref("browser.urlbar.groupLabels.enabled", false);
user_pref("browser.urlbar.autoFill", true);
user_pref("browser.urlbar.doubleClickSelectsAll", true);
user_pref("ui.key.menuAccessKeyFocuses", false);
user_pref("accessibility.typeaheadfind", false);
user_pref("view_source.wrap_long_lines", true);
user_pref("layout.spellcheckDefault", 0);
user_pref("findbar.highlightAll", true);
user_pref("browser.compactmode.show", true);
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("layout.css.prefers-color-scheme.content-override", 2);
user_pref("widget.non-native-theme.use-theme-accent", false);
user_pref("layout.css.font-visibility.standard", 1);
user_pref("layout.css.font-visibility.trackingprotection", 1);
user_pref("browser.display.use_document_fonts", 1);
user_pref("browser.toolbars.bookmarks.visibility", "newtab");


// =============================================================================
// SECTION 14: CREDENTIALS & SEARCH HYGIENE
// =============================================================================

user_pref("signon.rememberSignons", false);
user_pref("signon.autofillForms", false);
user_pref("signon.formlessCapture.enabled", false);
user_pref("signon.privateBrowsingCapture.enabled", false);
user_pref("editor.truncate_user_pastes", false);
user_pref("browser.formfill.enable", false);
user_pref("browser.search.suggest.enabled", false);
user_pref("browser.search.update", false);
user_pref("browser.search.separatePrivateDefault", true);
user_pref("browser.search.separatePrivateDefault.ui.enabled", true);
user_pref("browser.urlbar.suggest.searches", false);
user_pref("browser.urlbar.suggest.engines", false);
user_pref("browser.urlbar.speculativeConnect.enabled", false);
user_pref("browser.urlbar.quicksuggest.enabled", false);
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
user_pref("browser.urlbar.trending.featureGate", false);
user_pref("browser.urlbar.addons.featureGate", false);
user_pref("browser.urlbar.amp.featureGate", false);
user_pref("browser.urlbar.importantDates.featureGate", false);
user_pref("browser.urlbar.market.featureGate", false);
user_pref("browser.urlbar.mdn.featureGate", false);
user_pref("browser.urlbar.weather.featureGate", false);
user_pref("browser.urlbar.wikipedia.featureGate", false);
user_pref("browser.urlbar.yelp.featureGate", false);
user_pref("browser.urlbar.yelpRealtime.featureGate", false);


// =============================================================================
// SECTION 15: EXTENSIONS & COMPATIBILITY
// =============================================================================

user_pref("extensions.getAddons.showPane", false);
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);
user_pref("extensions.postDownloadThirdPartyPrompt", false);
user_pref("extensions.blocklist.enabled", true);
user_pref("extensions.webcompat.enable_shims", true);
user_pref("extensions.webcompat-reporter.enabled", false);
user_pref("extensions.quarantinedDomains.enabled", true);
user_pref("extensions.getAddons.cache.enabled", false);


// =============================================================================
// SECTION 16: NEW TAB PAGE & STARTUP
// =============================================================================

user_pref("browser.aboutConfig.showWarning", false);
user_pref("browser.startup.page", 0);
user_pref("browser.startup.homepage", "chrome://browser/content/blanktab.html");
user_pref("browser.newtabpage.enabled", false);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredCheckboxes", false);
user_pref("browser.newtabpage.activity-stream.default.sites", "");
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
user_pref("browser.newtabpage.activity-stream.telemetry", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.shell.shortcutFavicons", false);
user_pref("browser.profiles.enabled", true);
user_pref("browser.privateWindowSeparation.enabled", false);
user_pref("permissions.default.desktop-notification", 2);
user_pref("permissions.default.geo", 2);
user_pref("permissions.manager.defaultsUrl", "");
user_pref("geo.provider.network.url", "https://beacondb.net/v1/geolocate");
user_pref("geo.provider.ms-windows-location", false);
user_pref("geo.provider.use_corelocation", false);
user_pref("geo.provider.use_geoclue", false);
user_pref("toolkit.winRegisterApplicationRestart", false);
user_pref("devtools.debugger.remote-enabled", false);
user_pref("_user.js.parrot", "START: Oh yes, the Norwegian Blue... what's wrong with it?");


// =============================================================================
// SECTION 17: SMOOTH SCROLLING & INPUT LATENCY
// =============================================================================

user_pref("apz.overscroll.enabled", true);
user_pref("apz.frame_delay.enabled", false);
user_pref("general.smoothScroll", true);
user_pref("mousewheel.min_line_scroll_amount", 10);
user_pref("general.smoothScroll.mouseWheel.durationMinMS", 80);
user_pref("general.smoothScroll.currentVelocityWeighting", "0.15");
user_pref("general.smoothScroll.stopDecelerationWeighting", "0.6");
user_pref("general.smoothScroll.msdPhysics.enabled", false);
user_pref("mousewheel.default.delta_multiplier_y", 275);
user_pref("general.smoothScroll.msdPhysics.continuousMotionMaxDeltaMS", 12);
user_pref("general.smoothScroll.msdPhysics.motionBeginSpringConstant", 600);
user_pref("general.smoothScroll.msdPhysics.regularSpringConstant", 650);
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaMS", 25);
user_pref("general.smoothScroll.msdPhysics.slowdownSpringConstant", 250);
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaRatio", "2");
