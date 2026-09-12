/****************************************************************************************
 * Betterfox Configuration (Tailored Build)
 * Device: HP EliteBook 2540p (Intel Core i5 M 540, 5.58 GiB RAM, HDD, No Swap/Zram)
 * OS: antiX Linux 21 (Kernel 5.10 / IceWM 4.0.0 X11)
 * Target: Firefox 140 ESR
 ****************************************************************************************/

/****************************************************************************
 * SECTION 1: HARDWARE & OS TUNING (EliteBook 2540p / antiX / No-Swap)     *
****************************************************************************/

/** LOW MEMORY & OOM KILLER SAFEGUARDS (5.58 GiB RAM - NO SWAP/ZRAM) ***/
// Aggressively discard tabs before the Linux OOM-killer abruptly terminates Firefox
user_pref("browser.tabs.unloadOnLowMemory", true);
// Trigger unloader when available memory drops to 20% (~1.1 GB safety cushion)
user_pref("browser.low_commit_space_threshold_percent", 20);
// Unload idle background tabs after 3 minutes (180000ms; default is 10 min)
user_pref("browser.tabs.min_inactive_duration_before_unload", 180000);
// Limit back/forward DOM cache to 2 pages per tab (saves significant RAM)
user_pref("browser.sessionhistory.max_total_viewers", 2);
// Limit isolated web content processes to 2 (reduces multi-process RAM overhead on dual-core)
user_pref("dom.ipc.processCount.webIsolated", 2);
// Don't wake up background tabs on session restore until clicked
user_pref("browser.sessionstore.restore_on_demand", true);
user_pref("browser.sessionstore.restore_pinned_tabs_on_demand", true);

/** HDD ANTI-THRASHING (EXT4 MECHANICAL DRIVE) ***/
// Disable disk cache completely; prevents continuous random disk writes on slow HDD
user_pref("browser.cache.disk.enable", false);
// Write session store every 2 minutes instead of 15 seconds to avoid periodic disk I/O freezes
user_pref("browser.sessionstore.interval", 120000);
// Prevent downloads from polluting system recent documents
user_pref("browser.download.manager.addToRecentDocs", false);

/** GRAPHICS & RENDERER (Intel Ironlake / 1st Gen HD Graphics) ***/
// Accelerated Canvas2D causes crashes or slowdowns on 2010 Intel Gen 5 iGPUs
user_pref("gfx.canvas.accelerated", false);
user_pref("gfx.canvas.accelerated.cache-size", 256);
user_pref("gfx.content.skia-font-cache-size", 20);

/** LINUX / X11 / ICEWM ADJUSTMENTS ***/
// Stop accidental middle-click on empty page area from opening clipboard URL
user_pref("middlemouse.contentLoadURL", false);
// Stop middle-clicking the new-tab button from pasting and searching clipboard
user_pref("browser.tabs.searchclipboardfor.middleclick", false);

/****************************************************************************
 * SECTION 2: FASTFOX (Speed, Pipeline, & Network)                          *
****************************************************************************/

/** GENERAL & RENDERING ***/
user_pref("content.notify.interval", 100000); // 0.10s reflow timer
user_pref("layout.css.grid-template-masonry-value.enabled", true);

/** MEDIA & IMAGE CACHE (Memory Constrained) ***/
user_pref("media.memory_cache_max_size", 65536); // 64 MB
// Kept reasonable to prevent runaway memory usage during video streams
user_pref("media.cache_readahead_limit", 300);   // 5 minutes ahead
user_pref("media.cache_resume_threshold", 120);  // 2 minutes
user_pref("image.mem.decode_bytes_at_a_time", 32768);

/** NETWORK CONNECTIONS & DNS ***/
user_pref("network.http.max-connections", 1800);
user_pref("network.http.max-persistent-connections-per-server", 10);
user_pref("network.http.max-urgent-start-excessive-connections-per-host", 5);
user_pref("network.http.pacing.requests.enabled", false);
user_pref("network.dnsCacheExpiration", 3600);
user_pref("network.ssl_tokens_cache_capacity", 10240);

/** SPECULATIVE LOADING (Disable silent background network connections) ***/
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.dns.disablePrefetchFromHTTPS", true);
user_pref("browser.urlbar.speculativeConnect.enabled", false);
user_pref("browser.places.speculativeConnect.enabled", false);
user_pref("network.prefetch-next", false);
user_pref("network.predictor.enabled", false);

/****************************************************************************
 * SECTION 3: SMOOTHFOX (Responsive 60Hz Scrolling - Low CPU)               *
****************************************************************************/
// Uses the "Sharpen" profile without MSD physics to spare dual-core CPU cycles
user_pref("apz.overscroll.enabled", false); // Disabled on X11 to prevent visual stutter
user_pref("general.smoothScroll", true);
user_pref("mousewheel.min_line_scroll_amount", 10);
user_pref("general.smoothScroll.mouseWheel.durationMinMS", 80);
user_pref("general.smoothScroll.currentVelocityWeighting", "0.15");
user_pref("general.smoothScroll.stopDecelerationWeighting", "0.6");
user_pref("general.smoothScroll.msdPhysics.enabled", false); // Essential: avoids math spikes

/****************************************************************************
 * SECTION 4: SECUREFOX (Privacy, Telemetry, & Hardening)                   *
****************************************************************************/

/** TRACKING PROTECTION ***/
user_pref("browser.contentblocking.category", "strict");
user_pref("browser.download.start_downloads_in_tmp_dir", true);
user_pref("browser.helperApps.deleteTempFileOnExit", true);
user_pref("browser.uitour.enabled", false);
user_pref("privacy.globalprivacycontrol.enabled", true);

/** OCSP & CERTS ***/
user_pref("security.OCSP.enabled", 0);
user_pref("security.pki.crlite_mode", 2); // Enforce CRLite (faster & private)

/** SSL / TLS ***/
user_pref("security.ssl.treat_unsafe_negotiation_as_broken", true);
user_pref("browser.xul.error_pages.expert_bad_cert", true);
user_pref("security.tls.enable_0rtt_data", false);

/** DISK AVOIDANCE & SANITIZING ***/
user_pref("browser.privatebrowsing.forceMediaMemoryCache", true);
user_pref("browser.privatebrowsing.resetPBM.enabled", true);
user_pref("privacy.history.custom", true);

/** SEARCH & URL BAR PRIVACY ***/
user_pref("browser.urlbar.trimHttps", true);
user_pref("browser.urlbar.untrimOnUserInteraction.featureGate", true);
user_pref("browser.search.separatePrivateDefault.ui.enabled", true);
user_pref("browser.search.suggest.enabled", false);
user_pref("browser.urlbar.suggest.engines", false);
user_pref("browser.urlbar.quicksuggest.enabled", false);
user_pref("browser.urlbar.groupLabels.enabled", false);
user_pref("browser.formfill.enable", false);
user_pref("network.IDN_show_punycode", true);

/** PASSWORDS & CREDENTIALS ***/
user_pref("signon.formlessCapture.enabled", false);
user_pref("signon.privateBrowsingCapture.enabled", false);
user_pref("network.auth.subresource-http-auth-allow", 1);
user_pref("editor.truncate_user_pastes", false);

/** MIXED CONTENT & EXTENSIONS ***/
user_pref("security.mixed_content.block_display_content", true);
user_pref("pdfjs.enableScripting", false);
user_pref("extensions.enabledScopes", 5);

/** HEADERS / REFERERS & CONTAINERS ***/
user_pref("network.http.referer.XOriginTrimmingPolicy", 2);
user_pref("privacy.userContext.ui.enabled", true);

/** SAFE BROWSING (Disable remote checks, keep local protection) ***/
user_pref("browser.safebrowsing.downloads.remote.enabled", false);

/** MOZILLA CALL-HOME SERVICES ***/
user_pref("permissions.default.desktop-notification", 2);
user_pref("permissions.default.geo", 2);
user_pref("geo.provider.network.url", "https://beacondb.net/v1/geolocate");
user_pref("browser.search.update", false);
user_pref("permissions.manager.defaultsUrl", "");
user_pref("extensions.getAddons.cache.enabled", false);

/** TELEMETRY & DATA SUBMISSION (All Disabled) ***/
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
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
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
user_pref("browser.newtabpage.activity-stream.telemetry", false);
user_pref("datareporting.usage.uploadEnabled", false);

/** EXPERIMENTS & CRASH REPORTS ***/
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("app.normandy.enabled", false);
user_pref("app.normandy.api_url", "");
user_pref("breakpad.reportURL", "");
user_pref("browser.tabs.crashReporting.sendReport", false);

/****************************************************************************
 * SECTION 5: PESKYFOX (Annoyance Removal & UI Quality-of-Life)            *
****************************************************************************/

/** MOZILLA UI & RECOMMENDATIONS ***/
user_pref("browser.privatebrowsing.vpnpromourl", "");
user_pref("extensions.getAddons.showPane", false);
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);
user_pref("browser.preferences.moreFromMozilla", false);
user_pref("browser.aboutConfig.showWarning", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.profiles.enabled", true);

/** THEME ADJUSTMENTS ***/
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("browser.compactmode.show", true);
user_pref("layout.css.prefers-color-scheme.content-override", 2); // Follow OS theme

/** FULLSCREEN NOTICES ***/
user_pref("full-screen-api.transition-duration.enter", "0 0");
user_pref("full-screen-api.transition-duration.leave", "0 0");
user_pref("full-screen-api.warning.delay", -1);
user_pref("full-screen-api.warning.timeout", 0);

/** URL BAR & NEW TAB PAGE ***/
user_pref("browser.urlbar.unitConversion.enabled", true);
user_pref("browser.urlbar.trending.featureGate", false);
user_pref("browser.newtabpage.activity-stream.default.sites", "");
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);

/** POCKET & PDF ***/
user_pref("extensions.pocket.enabled", false);
user_pref("browser.download.open_pdf_attachments_inline", true);

/** TAB & BROWSER BEHAVIOR ***/
user_pref("browser.bookmarks.openInTabClosesMenu", false);
user_pref("browser.menu.showViewImageInfo", true);
user_pref("findbar.highlightAll", true);
user_pref("layout.word_select.eat_space_to_next_word", false);