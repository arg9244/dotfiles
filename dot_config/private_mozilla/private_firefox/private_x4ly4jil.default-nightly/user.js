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
// SECTION 2: CACHING & NETWORK OPTIMIZATION
// =============================================================================

// Enable on-disk HTTP caching to prevent re-downloading static web assets
user_pref("browser.cache.disk.enable", true);

// Disable automatic disk cache sizing to enforce manual capacity
user_pref("browser.cache.disk.smart_size.enabled", false);

// Set maximum disk cache capacity to 4 GB (in KB)
user_pref("browser.cache.disk.capacity", 4194304);

// Allow individual cached files up to 150 MB to reside in disk cache
user_pref("browser.cache.disk.max_entry_size", 153600);

// Keep up to 16 MB of disk cache index metadata in RAM for fast lookups
user_pref("browser.cache.disk.metadata_memory_limit", 16384);

// Pause cache writes if available drive storage drops below 5 GB
user_pref("browser.cache.disk.free_space_soft_limit_mb", 5120);

// Hard stop for disk cache operations if drive storage drops below 1 GB
user_pref("browser.cache.disk.free_space_hard_limit_mb", 1024);

// Allocate up to 1 GB of RAM for volatile in-memory caching (in KB)
user_pref("browser.cache.memory.capacity", 1048576);

// Allow individual assets up to 50 MB to reside directly in memory cache
user_pref("browser.cache.memory.max_entry_size", 51200);

// Enable native lazy loading so offscreen images only download when scrolled to
user_pref("dom.image-lazy-loading.enabled", true);

// Enable background preprocessing to speed up IndexedDB reads
user_pref("dom.indexedDB.preprocessing", true);

// Prevent pages from tracking detailed asset download timing metrics
user_pref("dom.enable_resource_timing", false);

// Disable Race Cache With Network to prevent redundant network requests
user_pref("network.http.rcwn.enabled", false);

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

// Increase absolute maximum concurrent HTTP network connections
user_pref("network.http.max-connections", 1800);

// Allow up to 10 persistent HTTP keep-alive connections per domain
user_pref("network.http.max-persistent-connections-per-server", 10);

// Reduce initial HTTP connection scheduling delay (in seconds)
user_pref("network.http.request.max-start-delay", 5);

// Cache successful DNS lookup entries for 1 hour (in seconds)
user_pref("network.dnsCacheExpiration", 3600);


// =============================================================================
// SECTION 3: MEDIA BUFFERING & STREAMING
// =============================================================================

// Allocate 2 GB for file-backed media cache to hold extended video buffers
user_pref("media.cache_size", 2097152);

// Set maximum size for memory media chunk cache (in KB)
user_pref("media.memory_cache_max_size", 65536);

// Set combined memory limit for active media stream buffers to 2 GB
user_pref("media.memory_caches_combined_limit_kb", 2097152);

// Allow video buffering up to 1 hour ahead when not constrained by player
user_pref("media.cache_readahead_limit", 3600);

// Resume buffering after a seek when buffer drops below 30 minutes
user_pref("media.cache_resume_threshold", 1800);

// Block all audio and video media from autoplaying across all websites
user_pref("media.autoplay.default", 5);

// Enforce click-to-play media blocking policy across all elements
user_pref("media.autoplay.blocking_policy", 2);

// Block browser extensions from playing or buffering media in background pages
user_pref("media.autoplay.allow-extension-background-pages", false);

// Prevent background tabs from loading or streaming video until focused
user_pref("media.block-autoplay-until-in-foreground", true);

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

// Disable prefetching of pages indicated by link prefetch tags
user_pref("network.prefetch-next", false);

// Disable speculative DNS prefetching on standard web pages
user_pref("network.dns.disablePrefetch", true);

// Disable speculative DNS prefetching on HTTPS web pages
user_pref("network.dns.disablePrefetchFromHTTPS", true);

// Disable speculative parallel TCP connections on link hover
user_pref("network.http.speculative-parallel-limit", 0);

// Disable predictive network pre-allocation agent
user_pref("network.predictor.enabled", false);

// Disable prefetching within the network prediction engine
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

// Disable online OCSP certificate checks to prevent leaking browsing history to CAs
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

// Disable Web Vibration API to prevent rogue sites from triggering device vibration
user_pref("dom.vibrator.enabled", false);

// Disable WebVR and WebXR interfaces to eliminate fingerprinting and memory overhead
user_pref("dom.vr.enabled", false);

// Disable Web Telephony API
user_pref("dom.telephony.enabled", false);

// Disable device motion and orientation sensors
user_pref("device.sensors.enabled", false);

// Disable device ambient light sensor queries
user_pref("device.sensors.ambientLight.enabled", false);

// Disable Battery Status API to prevent fingerprinting battery charge level
user_pref("dom.battery.enabled", false);

// Disable Gamepad API to prevent peripheral enumeration fingerprinting
user_pref("dom.gamepad.enabled", false);

// Completely disable Web Notifications API
user_pref("dom.webnotifications.enabled", false);

// Completely disable Web Push notification framework
user_pref("dom.push.enabled", false);

// Disable persistent background WebSocket connection to Mozilla Push Service
user_pref("dom.push.connection.enabled", false);

// Allow web applications to display custom context menus
user_pref("dom.event.contextmenu.enabled", true);

// Automatically apply rel="noopener" to links opening in new windows for process isolation
user_pref("dom.targetBlankNoOpener.enabled", true);

// Disable HTML5 canvas capture stream API to block canvas-based fingerprinting
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

// Cap back/forward navigation history stack to 15 pages per tab to limit memory use
user_pref("browser.sessionhistory.max_entries", 15);

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

// Disable uploading Firefox Health Reports to Mozilla
user_pref("datareporting.healthreport.uploadEnabled", false);

// Disable uploading daily usage and interaction statistics
user_pref("datareporting.usage.uploadEnabled", false);

// Disable unified telemetry system architecture
user_pref("toolkit.telemetry.unified", false);

// Disable primary application telemetry collection
user_pref("toolkit.telemetry.enabled", false);

// Neutralize telemetry server endpoint URL
user_pref("toolkit.telemetry.server", "data:,");

// Stop archiving past telemetry pings locally on disk
user_pref("toolkit.telemetry.archive.enabled", false);

// Disable telemetry ping dispatched upon creating a new browser profile
user_pref("toolkit.telemetry.newProfilePing.enabled", false);

// Disable telemetry ping dispatched during browser shutdown
user_pref("toolkit.telemetry.shutdownPingSender.enabled", false);

// Disable telemetry ping dispatched after browser updates
user_pref("toolkit.telemetry.updatePing.enabled", false);

// Disable Background Hang Reporter telemetry pings
user_pref("toolkit.telemetry.bhrPing.enabled", false);

// Disable telemetry ping dispatched on the very first browser shutdown
user_pref("toolkit.telemetry.firstShutdownPing.enabled", false);

// Opt out of telemetry code coverage measurement pings
user_pref("toolkit.telemetry.coverage.opt-out", true);

// Disable system telemetry coverage metrics
user_pref("toolkit.coverage.opt-out", true);

// Clear telemetry coverage server endpoint URL
user_pref("toolkit.coverage.endpoint.base", "");

// Disable opt-out Shield studies and feature testing
user_pref("app.shield.optoutstudies.enabled", false);

// Disable Normandy remote experiment and recipe execution service
user_pref("app.normandy.enabled", false);

// Clear Normandy remote recipe server endpoint URL
user_pref("app.normandy.api_url", "");

// Clear crash report submission server URL
user_pref("breakpad.reportURL", "");

// Disable prompt checking for unsubmitted crash reports
user_pref("browser.crashReports.unsubmittedCheck.enabled", false);

// Disable automatic background submission of backlogged crash reports
user_pref("browser.crashReports.unsubmittedCheck.autoSubmit2", false);

// Prevent automatic transmission of crashed tab reports
user_pref("browser.tabs.crashReporting.sendReport", false);

// Disable Nimbus remote experiment and feature rollout framework
user_pref("nimbus.rollouts.enabled", false);


// =============================================================================
// SECTION 11: AI, EXPERIMENTS & BROWSER ANNOYANCES
// =============================================================================

// Block AI features and remote models by default
user_pref("browser.ai.control.default", "blocked");

// Completely disable Firefox on-device machine learning engine
user_pref("browser.ml.enable", false);

// Disable AI chatbot interface in the browser sidebar
user_pref("browser.ml.chat.enabled", false);

// Remove AI chatbot shortcuts and controls from browser menus
user_pref("browser.ml.chat.menu", false);

// Disable AI-generated summary cards in link preview tooltips
user_pref("browser.ml.linkPreview.enabled", false);

// Disable smart AI-assisted automatic tab grouping
user_pref("browser.tabs.groups.smart.enabled", false);

// Completely disable Pocket integration across the browser interface
user_pref("extensions.pocket.enabled", false);

// Disable welcome and onboarding tour pages on new profile creation
user_pref("browser.aboutwelcome.enabled", false);

// Hide "More from Mozilla" promotional section in browser settings
user_pref("browser.preferences.moreFromMozilla", false);

// Prevent Firefox from prompting to check if it is the default browser
user_pref("browser.shell.checkDefaultBrowser", false);

// Disable personalized extension and theme recommendations in about:addons
user_pref("browser.discovery.enabled", false);

// Disable UI Tour framework to prevent remote pages from highlighting UI elements
user_pref("browser.uitour.enabled", false);

// Suppress post-update release notes and what's new splash pages
user_pref("browser.startup.homepage_override.mstone", "ignore");

// Disable Contextual Feature Recommender extension recommendations while browsing
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);

// Disable Contextual Feature Recommender browser feature prompts while browsing
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);

// Prevent Firefox updates from restoring default promotional bookmarks
user_pref("browser.bookmarks.restore_default_bookmarks", false);


// =============================================================================
// SECTION 12: SILENT AUTOMATIC DOWNLOADS
// =============================================================================

// Save downloads directly to the default downloads folder without prompting
user_pref("browser.download.useDownloadDir", true);

// Prevent the downloads popup panel from expanding automatically on download start
user_pref("browser.download.alwaysOpenPanel", false);

// Prevent downloaded files from being added to the operating system recent files list
user_pref("browser.download.manager.addToRecentDocs", false);

// Automatically save newly encountered file types without displaying an action prompt
user_pref("browser.download.always_ask_before_handling_new_types", false);

// Write temporary downloads to system temp directory when opened in external apps
user_pref("browser.download.start_downloads_in_tmp_dir", true);

// Delete temporary downloaded files upon exiting the browser
user_pref("browser.helperApps.deleteTempFileOnExit", true);


// =============================================================================
// SECTION 13: TAB MANAGEMENT, NAVIGATION & UI ERGONOMICS
// =============================================================================

// Open bookmarks in a new tab instead of overwriting the current page
user_pref("browser.tabs.loadBookmarksInTabs", true);

// Prevent closing the last open tab from closing the entire browser window
user_pref("browser.tabs.closeWindowWithLastTab", false);

// Disable confirmation prompt when closing a window containing multiple open tabs
user_pref("browser.tabs.warnOnClose", false);

// Pre-warm background tab processes on tab hover to accelerate tab switching
user_pref("browser.tabs.remote.warmup.enabled", true);

// Hide the drop-down tab manager arrow button on the tab bar
user_pref("browser.tabs.tabmanager.enabled", false);

// Disable middle-clicking the new tab button to load or search clipboard text
user_pref("browser.tabs.searchclipboardfor.middleclick", false);

// Prevent middle-clicking empty page content from executing or opening clipboard URLs
user_pref("middlemouse.contentLoadURL", false);

// Open external links targeting new windows in a new browser tab instead
user_pref("browser.link.open_newwindow", 3);

// Force all window-open methods (including scripted popups) to open in tabs
user_pref("browser.link.open_newwindow.restriction", 0);

// Keep the bookmarks dropdown menu open after opening a bookmark in a new tab
user_pref("browser.bookmarks.openInTabClosesMenu", false);

// Always show full URL protocols (e.g. https://) in the address bar
user_pref("browser.urlbar.trimURLs", false);

// Hide redundant https scheme prefix until the address bar is interacted with
user_pref("browser.urlbar.trimHttps", true);

// Automatically reveal full protocol scheme when clicking inside the address bar
user_pref("browser.urlbar.untrimOnUserInteraction.featureGate", true);

// Display the raw URL in the address bar instead of simplified search query terms
user_pref("browser.urlbar.showSearchTerms.enabled", false);

// Hide category group header labels in the address bar results dropdown
user_pref("browser.urlbar.groupLabels.enabled", false);

// Enable inline domain autocomplete in the address bar without preconnections
user_pref("browser.urlbar.autoFill", true);

// Select the entire URL when double-clicking inside the address bar
user_pref("browser.urlbar.doubleClickSelectsAll", true);

// Prevent tapping the Alt key from jumping keyboard focus to the menu bar
user_pref("ui.key.menuAccessKeyFocuses", false);

// Prevent typing on a page from automatically initiating in-page text search
user_pref("accessibility.typeaheadfind", false);

// Wrap long lines of text by default when viewing page source code
user_pref("view_source.wrap_long_lines", true);

// Disable built-in spellchecker to reduce CPU and background memory overhead
user_pref("layout.spellcheckDefault", 0);

// Highlight all search term matches across the page when opening the find bar
user_pref("findbar.highlightAll", true);

// Restore the compact density option in toolbar customization settings
user_pref("browser.compactmode.show", true);

// Enable loading custom userChrome.css and userContent.css interface stylesheets
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);

// Force dark color scheme mode for web page content
user_pref("layout.css.prefers-color-scheme.content-override", 2);

// Disallow website content from querying or adopting the system accent color
user_pref("widget.non-native-theme.use-theme-accent", false);

// Restrict fonts accessible by web pages to standard system-installed fonts
user_pref("layout.css.font-visibility.standard", 1);

// Restrict font visibility under tracking protection to prevent font fingerprinting
user_pref("layout.css.font-visibility.trackingprotection", 1);

// Allow websites to load custom document and icon web fonts
user_pref("browser.display.use_document_fonts", 1);


// =============================================================================
// SECTION 14: CREDENTIALS & SEARCH HYGIENE
// =============================================================================

// Disable built-in password saving prompts and internal password manager
user_pref("signon.rememberSignons", false);

// Disable automatic filling of saved username and password form fields
user_pref("signon.autofillForms", false);

// Disable capturing login credentials from forms that lack standard form elements
user_pref("signon.formlessCapture.enabled", false);

// Prevent capturing or offering saved credentials inside private browsing windows
user_pref("signon.privateBrowsingCapture.enabled", false);

// Prevent long passwords from being truncated when pasted into input fields
user_pref("editor.truncate_user_pastes", false);

// Disable saving and autocompleting previously typed form and search inputs
user_pref("browser.formfill.enable", false);

// Disable live search suggestions dropdown in the search and address bar
user_pref("browser.search.suggest.enabled", false);

// Disable automatic background updates for installed search engines
user_pref("browser.search.update", false);

// Allow configuring a distinct default search engine for private browsing
user_pref("browser.search.separatePrivateDefault", true);

// Expose separate private search engine selector in browser search preferences
user_pref("browser.search.separatePrivateDefault.ui.enabled", true);

// Exclude search suggestions from address bar drop-down results
user_pref("browser.urlbar.suggest.searches", false);

// Exclude search engine selector shortcuts from address bar suggestions
user_pref("browser.urlbar.suggest.engines", false);

// Disable opening speculative connections to address bar autocompletion targets
user_pref("browser.urlbar.speculativeConnect.enabled", false);

// Disable Firefox Quick Suggest contextual suggestions in the address bar
user_pref("browser.urlbar.quicksuggest.enabled", false);

// Disable non-sponsored Quick Suggest recommendations in the address bar
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);

// Disable sponsored Quick Suggest advertisement suggestions in the address bar
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false);

// Disable trending search suggestions in the address bar dropdown
user_pref("browser.urlbar.trending.featureGate", false);

// Disable extension suggestions in address bar search results
user_pref("browser.urlbar.addons.featureGate", false);

// Disable AMP suggestions in address bar search results
user_pref("browser.urlbar.amp.featureGate", false);

// Disable holiday and important date suggestions in the address bar
user_pref("browser.urlbar.importantDates.featureGate", false);

// Disable stock market suggestions in the address bar
user_pref("browser.urlbar.market.featureGate", false);

// Disable MDN web docs suggestions in the address bar
user_pref("browser.urlbar.mdn.featureGate", false);

// Disable live weather forecast suggestions in the address bar
user_pref("browser.urlbar.weather.featureGate", false);

// Disable Wikipedia rich snippet suggestions in the address bar
user_pref("browser.urlbar.wikipedia.featureGate", false);

// Disable Yelp local business suggestions in the address bar
user_pref("browser.urlbar.yelp.featureGate", false);

// Disable real-time Yelp suggestions in the address bar
user_pref("browser.urlbar.yelpRealtime.featureGate", false);


// =============================================================================
// SECTION 15: EXTENSIONS & COMPATIBILITY
// =============================================================================

// Hide personalized add-on recommendation pane in about:addons
user_pref("extensions.getAddons.showPane", false);

// Disable extension and theme recommendation cards in about:addons
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);

// Prevent bypassing third-party extension installation confirmation prompts
user_pref("extensions.postDownloadThirdPartyPrompt", false);

// Enable Mozilla extension blocklist to automatically deactivate malicious extensions
user_pref("extensions.blocklist.enabled", true);

// Enable SmartBlock compatibility shims to prevent broken pages under strict tracking protection
user_pref("extensions.webcompat.enable_shims", true);

// Disable Web Compatibility Reporter button and telemetry submission tool
user_pref("extensions.webcompat-reporter.enabled", false);

// Enforce extension quarantine list to restrict add-on execution on sensitive domains
user_pref("extensions.quarantinedDomains.enabled", true);

// Disable caching remote add-on metadata repository information locally
user_pref("extensions.getAddons.cache.enabled", false);


// =============================================================================
// SECTION 16: NEW TAB PAGE & STARTUP
// =============================================================================

// Suppress the warning prompt displayed when navigating to about:config
user_pref("browser.aboutConfig.showWarning", false);

// Set browser startup page behavior to display a blank page
user_pref("browser.startup.page", 0);

// Set default homepage and new window target to an internal blank page
user_pref("browser.startup.homepage", "chrome://browser/content/blanktab.html");

// Disable the default Activity Stream new tab page in favor of a blank tab
user_pref("browser.newtabpage.enabled", false);

// Disable sponsored Pocket articles and recommendations on the new tab page
user_pref("browser.newtabpage.activity-stream.showSponsored", false);

// Disable sponsored shortcut tiles on the new tab page
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);

// Hide sponsored content configuration toggles on the new tab page
user_pref("browser.newtabpage.activity-stream.showSponsoredCheckboxes", false);

// Clear default pre-populated top sites from the new tab page
user_pref("browser.newtabpage.activity-stream.default.sites", "");

// Disable telemetry data collection for new tab Activity Stream feeds
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);

// Disable interaction telemetry reporting on the new tab page
user_pref("browser.newtabpage.activity-stream.telemetry", false);

// Disable Top Stories news feed section on the new tab page
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);

// Disable downloading website favicons to temporary files when creating URL shortcuts
user_pref("browser.shell.shortcutFavicons", false);

// Enable browser native profile switcher interface in the primary menu
user_pref("browser.profiles.enabled", true);

// Group private browsing windows together with normal windows in the taskbar
user_pref("browser.privateWindowSeparation.enabled", false);

// Block website desktop notification permission requests by default
user_pref("permissions.default.desktop-notification", 2);

// Block website geolocation access permission requests by default
user_pref("permissions.default.geo", 2);

// Clear remote default permission overrides URL to prevent website permission escalations
user_pref("permissions.manager.defaultsUrl", "");

// Set privacy-friendly BeaconDB endpoint for network geolocation lookups
user_pref("geo.provider.network.url", "https://beacondb.net/v1/geolocate");

// Disable querying Windows location services API for geolocation
user_pref("geo.provider.ms-windows-location", false);

// Disable querying macOS CoreLocation framework for geolocation
user_pref("geo.provider.use_corelocation", false);

// Disable querying Linux Geoclue daemon for geolocation
user_pref("geo.provider.use_geoclue", false);

// Prevent automatic browser restart and session restoration after OS reboot
user_pref("toolkit.winRegisterApplicationRestart", false);

// Disable remote debugging server in developer tools
user_pref("devtools.debugger.remote-enabled", false);

// Sentinel preference to confirm complete and error-free user.js file parsing
user_pref("_user.js.parrot", "START: Oh yes, the Norwegian Blue... what's wrong with it?");


// =============================================================================
// SECTION 17: SMOOTH SCROLLING & INPUT LATENCY
// =============================================================================

// Enable smooth rubber-band overscroll animations at page boundaries
user_pref("apz.overscroll.enabled", true);

// Disable compositor input queue frame delay to reduce mouse and scroll latency
user_pref("apz.frame_delay.enabled", false);

// Enable smooth scrolling animation engine
user_pref("general.smoothScroll", true);

// Set minimum line scroll threshold per mouse wheel tick
user_pref("mousewheel.min_line_scroll_amount", 10);

// Set minimum duration for mouse wheel scroll animations (in ms)
user_pref("general.smoothScroll.mouseWheel.durationMinMS", 80);

// Set current velocity weighting factor for scroll momentum calculation
user_pref("general.smoothScroll.currentVelocityWeighting", "0.15");

// Set deceleration weighting factor when terminating scroll motion
user_pref("general.smoothScroll.stopDecelerationWeighting", "0.6");

// Disable mass-spring-damper physics engine for standard smooth scrolling
user_pref("general.smoothScroll.msdPhysics.enabled", false);

// Set vertical scroll distance multiplier per mouse wheel notch
user_pref("mousewheel.default.delta_multiplier_y", 275);

// Set maximum frame delta time for continuous spring motion physics
user_pref("general.smoothScroll.msdPhysics.continuousMotionMaxDeltaMS", 12);

// Set initial spring tension constant for starting scroll motion
user_pref("general.smoothScroll.msdPhysics.motionBeginSpringConstant", 600);

// Set steady-state spring constant for active scroll movement
user_pref("general.smoothScroll.msdPhysics.regularSpringConstant", 650);

// Set minimum frame delta time before initiating scroll slowdown
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaMS", 25);

// Set spring resistance constant during scroll deceleration
user_pref("general.smoothScroll.msdPhysics.slowdownSpringConstant", 250);

// Set velocity decay ratio for scroll slowdown damping
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaRatio", "2");
