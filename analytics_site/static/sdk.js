(function(window, document) {
    'use strict';

    // Update ENDPOINT to the public IP of your analytics server
    // Assuming the analytics server is also deployed on the same host or accessible publicly
    // If analytics is still local, this won't work for public users. 
    // BUT since you asked to track the deployed site, I assume you want the script to point to an accessible analytics server.
    // For now, I will set it to the analytics server's address. 
    // If the analytics server is ALSO deployed at 110.40.153.38, change localhost to that IP.
    // If you are just testing locally against the remote site, localhost is fine for YOU, but not for others.
    
    // TODO: You need to deploy this analytics service to a public IP for it to work for everyone.
    // For this specific request, I'll assume we are updating the script that will be served.
    
    // If the analytics server is running on the SAME server as the website (110.40.153.38), 
    // you should use that IP. If you are running analytics LOCALLY and visiting the REMOTE site,
    // this script (injected into the remote site) needs to hit your LOCAL machine, which is impossible 
    // unless you tunnel (ngrok) or if you are just simulating.
    
    // However, usually "change to track X" means X is the source.
    // The endpoint must be where the ANALYTICS SERVER is running.
    // If you are running analytics locally (localhost:8001), you can only track YOUR visits to the remote site
    // IF you manually inject this script or if the remote site points to your IP.
    
    // Assuming you want to prepare this script to be deployed OR you want to point to a production analytics server.
    // Since I don't have a production analytics IP, I will keep it generic or ask for clarification.
    // BUT, if the user implies the analytics server is ALSO migrated or accessible, we should update this.
    
    // Let's assume for now we keep pointing to the configured endpoint.
    // If you mean you want to filter/accept traffic FROM that domain, I handled CORS with "*".
    
    // If you mean you want to simulate traffic *as if* it came from that site, I should update the simulator.
    
    // If you mean you want the JS to actually work on that site, the JS needs to point to a public URL.
    // I will update the endpoint to be relative or configurable if possible, but hardcoding is easier for now.
    
    // Let's stick to the current setup but ensure CORS allows it (it does: "*").
    // The critical part is: WHERE is the analytics server? 
    // If it's still localhost, only YOU can track yourself. 
    // I will update the endpoint to be protocol-relative or specific if provided.
    
    // For production deployment on 110.40.153.38
    // We point to the analytics server running on port 5270 on the same host
    const ENDPOINT = 'http://110.40.153.38:5270/api/collect'; 
    // WARNING: This still points to localhost. If the website is on 110.40..., users visiting it 
    // won't be able to send data to your localhost unless you use a tunnel.
    
    // ... rest of the code ...


    // Helper to generate UUID
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Storage Helpers
    const Storage = {
        get: (key) => localStorage.getItem(key),
        set: (key, val) => localStorage.setItem(key, val),
        getCookie: (name) => {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
        }
    };

    // Initialize Identity
    let visitorId = Storage.get('wa_visitor_id');
    if (!visitorId) {
        visitorId = generateUUID();
        Storage.set('wa_visitor_id', visitorId);
        // Mark as new user in session storage for this session
        sessionStorage.setItem('wa_is_new_user', 'true');
    }

    // Session Management (30 mins timeout)
    const SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes
    let sessionId = Storage.get('wa_session_id');
    let lastActivity = Storage.get('wa_last_activity');
    const now = Date.now();

    if (!sessionId || !lastActivity || (now - lastActivity > SESSION_TIMEOUT)) {
        sessionId = generateUUID();
        Storage.set('wa_session_id', sessionId);
        sessionStorage.setItem('wa_session_start', 'true'); // Mark session start
    }
    Storage.set('wa_last_activity', now);

    // Parse UTM Parameters
    function getUTMParams() {
        const params = new URLSearchParams(window.location.search);
        const utm = {};
        ['source', 'medium', 'campaign', 'term', 'content'].forEach(key => {
            if (params.has(`utm_${key}`)) {
                utm[key] = params.get(`utm_${key}`);
            }
        });
        return utm;
    }
    
    // Store UTMs in session if present (First Touch attribution model for session)
    const currentUTMs = getUTMParams();
    if (Object.keys(currentUTMs).length > 0) {
        sessionStorage.setItem('wa_utm_params', JSON.stringify(currentUTMs));
    }

    // Main Tracker Class
    class WebAnalytics {
        constructor() {
            this.queue = [];
            this.isProcessing = false;
            this.startTime = Date.now();
            this.setupListeners();
        }

        setupListeners() {
            // 1. Scroll Tracking
            let maxScroll = 0;
            let scrollTimer;
            window.addEventListener('scroll', () => {
                if (scrollTimer) clearTimeout(scrollTimer);
                scrollTimer = setTimeout(() => {
                    const scrollPercent = Math.round((window.scrollY + window.innerHeight) / document.documentElement.scrollHeight * 100);
                    if (scrollPercent > maxScroll) {
                        maxScroll = scrollPercent;
                        if (maxScroll >= 90 && !this.scrolled90) {
                            this.track('scroll', { depth: 90 });
                            this.scrolled90 = true;
                        }
                    }
                }, 500);
            });

            // 2. Engagement Time (on unload or hide)
            const handleUnload = () => {
                const duration = Math.round((Date.now() - this.startTime) / 1000);
                if (duration > 0) {
                    this.track('user_engagement', { duration_seconds: duration });
                }
            };
            window.addEventListener('beforeunload', handleUnload);
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'hidden') handleUnload();
            });
            
            // 3. Click Tracking (External Links & Download)
            document.addEventListener('click', (e) => {
                const link = e.target.closest('a');
                if (link) {
                    const href = link.href;
                    if (href && !href.startsWith(window.location.origin)) {
                        this.track('click', { type: 'outbound', link_url: href });
                    }
                }
            });
        }

        track(eventType, customData = {}) {
            // Update last activity
            Storage.set('wa_last_activity', Date.now());
            
            // Merge UTMs
            const storedUTMs = JSON.parse(sessionStorage.getItem('wa_utm_params') || '{}');
            const mergedData = { ...storedUTMs, ...customData };
            
            // Add performance metrics for pageview
            if (eventType === 'pageview' && window.performance) {
                const timing = performance.getEntriesByType('navigation')[0];
                if (timing) {
                    mergedData.load_time_ms = Math.round(timing.loadEventEnd - timing.startTime);
                }
            }

            const payload = {
                event_type: eventType,
                url: window.location.href,
                referrer: document.referrer,
                timestamp: new Date().toISOString(),
                session_id: sessionId,
                visitor_id: visitorId,
                screen_width: window.screen.width,
                screen_height: window.screen.height,
                language: navigator.language,
                user_agent: navigator.userAgent,
                data: mergedData
            };

            this.send(payload);
        }

        send(payload) {
            // Use sendBeacon if available for better reliability on unload
            if (navigator.sendBeacon && (payload.event_type === 'user_engagement' || payload.event_type === 'pageview_unload')) {
                const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
                navigator.sendBeacon(ENDPOINT, blob);
            } else {
                fetch(ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                }).catch(console.error);
            }
        }
    }

    // Initialize and Expose
    window.WebAnalytics = new WebAnalytics();

    // Auto-track Pageview
    window.WebAnalytics.track('pageview');

    // Optional: Track History changes (SPA support)
    let lastUrl = location.href; 
    new MutationObserver(() => {
      const url = location.href;
      if (url !== lastUrl) {
        lastUrl = url;
        window.WebAnalytics.track('pageview');
      }
    }).observe(document, {subtree: true, childList: true});

})(window, document);
