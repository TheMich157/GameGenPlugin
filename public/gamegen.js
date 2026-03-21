/**
 * GameGen Ultra-Premium Millennium Injectable - Version 5.0
 */

(function () {
    console.log("[GameGen] Ultra-Premium UI v5.0 initialized.");

    let uiInjected = false;
    let apiKeySet = false;
    let currentTab = 'generator';
    const VERSION = '3.4.3';
    
    let settings = {
        api_key: '',
        auto_restart_steam: false,
        beta_updates: false,
        debug_logging: true,
        notification_duration: 6
    };

    // -- Utilities --

    function createToast(message, type = 'success', actionLabel = null, actionCallback = null) {
        const container = document.querySelector('.gg-toast-container') || (function() {
            const c = document.createElement('div');
            c.className = 'gg-toast-container';
            document.body.appendChild(c);
            return c;
        })();

        const toast = document.createElement('div');
        toast.className = `gg-toast ${type} ${actionLabel ? 'has-action' : ''}`;
        
        let toastHTML = `
            <div class="gg-toast-message">
                <span>${type === 'success' ? '✨' : '⚠️'}</span>
                <span>${message}</span>
            </div>
        `;

        if (actionLabel && actionCallback) {
            toastHTML += `
                <div class="gg-toast-actions">
                    <button class="gg-btn-small" id="gg-toast-action-btn">${actionLabel}</button>
                    <button class="gg-btn-small secondary" id="gg-toast-close-btn">Dismiss</button>
                </div>
            `;
        }

        toast.innerHTML = toastHTML;
        container.appendChild(toast);

        if (actionLabel && actionCallback) {
            toast.querySelector('#gg-toast-action-btn').onclick = () => {
                actionCallback();
                toast.remove();
            };
            toast.querySelector('#gg-toast-close-btn').onclick = () => toast.remove();
        } else {
            const duration = (settings.notification_duration || 6) * 1000;
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-20px) scale(0.9)';
                setTimeout(() => toast.remove(), 500);
            }, duration);
        }
    }

    async function safeCall(method, args = {}) {
        if (!window.Millennium) {
            console.error("[GameGen] Millennium not found");
            return null;
        }
        try {
            const res = await Millennium.callServerMethod('gamegen', method, args);
            // Some versions return raw string, some return object
            const parsed = typeof res === 'string' ? JSON.parse(res) : res;
            console.log(`[GameGen] Call ${method} result:`, parsed);
            return parsed;
        } catch (err) {
            console.error(`[GameGen] Error calling ${method}:`, err);
            return { success: false, error: err.message };
        }
    }

    // -- App Logic --

    const App = {
        async generate(appId, sourceBtn = null) {
            if (!apiKeySet) {
                createToast("Configure API Key first!", "error");
                this.switchTab('settings');
                this.toggleUI(true);
                return;
            }

            const originalContent = sourceBtn ? sourceBtn.innerHTML : null;
            if (sourceBtn) {
                sourceBtn.disabled = true;
                sourceBtn.innerHTML = '<div class="gg-spinner"></div>';
            }

            const res = await safeCall('generate_manifest', { app_id: appId });
            
            if (res && res.success) {
                // Determine if we're on a store page to show the specific restart button
                const isStorePage = !!document.getElementById('gg-store-inject');
                
                let msg = res._already_existed ? "Manifest updated!" : "Manifest installed!";
                if (res._zip_installed) msg = "Game content extracted & manifest installed!";
                
                if (isStorePage && sourceBtn && sourceBtn.closest('#gg-store-inject')) {
                    // Replace the "Add" button with a "Restart" button
                    const container = sourceBtn.closest('#gg-store-inject');
                    container.innerHTML = `
                        <a class="gg-store-btn restart btnv6_yellow_hoverfade" href="#">
                            <span>🔄</span>
                            <span style="color: black; font-weight: 800;">RESTART STEAM</span>
                        </a>
                    `;
                    container.querySelector('a').onclick = (e) => {
                        e.preventDefault();
                        safeCall('restart_steam');
                    };
                    createToast(msg + " Please Restart Steam.", 'success');
                } else {
                    createToast(
                        msg, 
                        'success', 
                        'Restart Steam', 
                        () => safeCall('restart_steam')
                    );
                }
                this.refreshHistory();
                this.refreshStats();
            } else {
                createToast(res?.error || "Generation failed", "error");
                if (sourceBtn) {
                  sourceBtn.disabled = false;
                  sourceBtn.innerHTML = originalContent;
                }
            }
        },

        async removeManifest(appId) {
            const res = await safeCall('uninstall_manifest', { app_id: appId });
            if (res && res.success) {
                createToast("Manifest removed. Restart Steam to reflect changes.", 'success', 'Restart Now', () => safeCall('restart_steam'));
                this.refreshHistory();
            } else {
                createToast(res?.error || "Failed to remove manifest", "error");
            }
        },

        async request(appId, sourceBtn = null) {
            if (!apiKeySet) return createToast("Configure API Key first!", "error");
            
            if (sourceBtn) {
                sourceBtn.disabled = true;
                sourceBtn.innerHTML = '<div class="gg-spinner"></div>';
            }

            const res = await safeCall('request_game', { app_id: appId });
            
            if (res && (res.success || res.status === 'sent')) {
                createToast("Request submitted successfully!");
            } else {
                createToast(res?.error || "Request failed", "error");
            }

            if (res && res._should_restart) {
                createToast("Auto-restarting Steam in 2s...", "info");
            }

            if (sourceBtn) {
                sourceBtn.disabled = false;
                sourceBtn.innerHTML = 'Request Game';
            }
        },

        async refreshStats() {
            if (!apiKeySet) return;
            const res = await safeCall('get_stats');
            if (res) {
                const rem = document.getElementById('gg-stat-remaining');
                const tot = document.getElementById('gg-stat-limit');
                if (rem) rem.innerText = res.remaining !== undefined ? res.remaining : '-';
                if (tot) tot.innerText = res.limit || '∞';
            }
        },

        async refreshHistory() {
            console.log("[GameGen] Refreshing history...");
            const history = await safeCall('get_history');
            const list = document.getElementById('gg-history-list');
            if (!list) return;

            if (!history || (Array.isArray(history) && history.length === 0)) {
                list.innerHTML = '<div style="text-align: center; color: var(--gg-text-dim); padding: 40px 0;">No history yet</div>';
                return;
            }

            if (history.success === false) {
                list.innerHTML = `<div style="text-align: center; color: var(--gg-error); padding: 40px 0;">Error loading library: ${history.error}</div>`;
                return;
            }

            list.innerHTML = history.map(item => `
                <div class="gg-history-item" data-id="${item.app_id}">
                    <div class="gg-history-info">
                        <span class="gg-history-name">${item.name || 'Unknown Game'}</span>
                        <span class="gg-history-id">AppID: ${item.app_id}</span>
                    </div>
                    <div class="gg-history-controls">
                         <div class="gg-btn-icon gg-delete-btn" data-id="${item.app_id}" title="Remove Manifest">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                        </div>
                    </div>
                </div>
            `).join('');

            list.querySelectorAll('.gg-history-item').forEach(el => {
                el.onclick = (e) => {
                    if (e.target.closest('.gg-delete-btn')) {
                        e.stopPropagation();
                        const id = e.target.closest('.gg-delete-btn').dataset.id;
                        this.removeManifest(id);
                        return;
                    }
                    const appIdInput = document.getElementById('gg-app-id-input');
                    if (appIdInput) {
                        appIdInput.value = el.dataset.id;
                        this.switchTab('generator');
                    }
                };
            });
        },

        switchTab(tabId) {
            currentTab = tabId;
            document.querySelectorAll('.gamegen-tab').forEach(t => {
                t.classList.toggle('active', t.dataset.tab === tabId);
            });
            document.querySelectorAll('.gamegen-section').forEach(s => {
                s.classList.toggle('active', s.id === `gg-section-${tabId}`);
            });

            if (tabId === 'library') this.refreshHistory();
            if (tabId === 'generator') this.refreshStats();
        },

        toggleUI(forceOpen = null) {
            const container = document.getElementById('gamegen-plugin-container');
            const overlay = document.querySelector('.gamegen-overlay');
            if (!container) return;
            
            const isOpen = container.classList.contains('active');
            const shouldOpen = forceOpen !== null ? forceOpen : !isOpen;

            if (shouldOpen) {
                container.classList.add('active');
                overlay.classList.add('active');
                this.refreshStats();
                if (currentTab === 'library') this.refreshHistory();
            } else {
                container.classList.remove('active');
                overlay.classList.remove('active');
            }
        }
    };

    // -- UI Injection --


    async function checkPostRestart() {
        const res = await safeCall('get_newly_added');
        if (res && res.success && res.games && res.games.length > 0) {
            const count = res.games.length;
            const names = res.games.map(g => g.name || `App ${g.app_id}`).join(', ');
            createToast(`✨ ${count} New Game${count > 1 ? 's' : ''} Added: ${names}`, 'success');
        }
        
        // Also check for background update notifications
        const upd = await safeCall('get_update_notification');
        if (upd && upd.message) {
            createToast(upd.message, 'info', 'Restart Now', () => safeCall('restart_steam'));
        }
    }

    function initUI() {
        if (document.getElementById('gamegen-plugin-container')) return;

        // 1. Launcher and its menu
        const launcherCtn = document.createElement('div');
        launcherCtn.id = 'gg-launcher-ctn';
        launcherCtn.innerHTML = `
            <div id="gg-launcher-menu">
                <button class="gg-menu-item" id="gg-menu-settings">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                    <span>Settings</span>
                </button>
                <button class="gg-menu-item" id="gg-menu-update">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                    <span>Update Search</span>
                </button>
            </div>
            <button id="gamegen-launcher-btn" title="GameGen Manifest Generator">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
            </button>
        `;
        document.body.appendChild(launcherCtn);

        const launcherBtn = document.getElementById('gamegen-launcher-btn');
        launcherBtn.onclick = () => launcherCtn.classList.toggle('open');
        
        document.getElementById('gg-menu-settings').onclick = () => {
            App.switchTab('settings');
            App.toggleUI(true);
            launcherCtn.classList.remove('open');
        };
        
        document.getElementById('gg-menu-update').onclick = async () => {
            launcherCtn.classList.remove('open');
            createToast("Checking for updates...", "info");
            const res = await safeCall('update_plugin');
            if (res && res.success) {
                createToast(res.message || "Update process started.", "info");
            }
        };

        // 2. Overlay
        const overlay = document.createElement('div');
        overlay.className = 'gamegen-overlay';
        overlay.onclick = () => App.toggleUI(false);
        document.body.appendChild(overlay);

        // 3. Main Container
        const container = document.createElement('div');
        container.id = 'gamegen-plugin-container';
        container.innerHTML = `
            <div class="gamegen-header">
                <div class="gamegen-title-container">
                    <div class="gamegen-logo">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                    </div>
                    <h1 class="gamegen-title">GAMEGEN <span style="font-size: 10px; color: var(--gg-text-dim); opacity: 0.5;">v${VERSION}</span></h1>
                </div>
            </div>

            <div class="gamegen-tabs">
                <div class="gamegen-tab active" data-tab="generator">Generator</div>
                <div class="gamegen-tab" data-tab="library">Library</div>
                <div class="gamegen-tab" data-tab="settings">Settings</div>
            </div>

            <div class="gamegen-content">
                <!-- Generator -->
                <div id="gg-section-generator" class="gamegen-section active">
                    <div class="gg-stats-grid">
                        <div class="gg-stat-card">
                            <div class="gg-stat-label">REMAINING</div>
                            <div class="gg-stat-value" id="gg-stat-remaining">-</div>
                        </div>
                        <div class="gg-stat-card">
                            <div class="gg-stat-label">TOTAL LIMIT</div>
                            <div class="gg-stat-value" id="gg-stat-limit">-</div>
                        </div>
                    </div>

                    <span class="section-label">Generator</span>
                    <div class="gamegen-input-wrapper">
                        <input type="text" id="gg-app-id-input" class="gamegen-input" placeholder="Steam App ID (e.g. 730)">
                    </div>
                    <button class="gamegen-btn gamegen-btn-primary" id="gg-gen-btn">Install to Library</button>
                    
                    <p style="font-size: 11px; color: var(--gg-text-dim); margin-top: 20px; text-align: center;">Visit the Steam Store to add games directly.</p>
                </div>

                <!-- Library -->
                <div id="gg-section-library" class="gamegen-section">
                    <span class="section-label">Recent Generations</span>
                    <div id="gg-history-list" class="gg-history-list">
                        <!-- History items injected here -->
                    </div>
                    <button id="gg-clear-history" style="margin-top: 20px; background: none; border: none; color: var(--gg-text-dim); font-size: 11px; cursor: pointer; text-decoration: underline;">Clear History</button>
                </div>

                <!-- Settings -->
                <div id="gg-section-settings" class="gamegen-section">
                    <span class="section-label">General Settings</span>
                    
                    <div class="gg-settings-group">
                        <div class="gg-setting-item">
                            <div class="gg-setting-info">
                                <div class="gg-setting-title">Auto-Restart Steam</div>
                                <div class="gg-setting-desc">Instantly relaunch Steam after manifest generation.</div>
                            </div>
                            <label class="gg-switch">
                                <input type="checkbox" id="gg-set-autorestart">
                                <span class="gg-slider"></span>
                            </label>
                        </div>

                        <div class="gg-setting-item">
                            <div class="gg-setting-info">
                                <div class="gg-setting-title">Beta Releases</div>
                                <div class="gg-setting-desc">Check for pre-release versions on GitHub.</div>
                            </div>
                            <label class="gg-switch">
                                <input type="checkbox" id="gg-set-beta">
                                <span class="gg-slider"></span>
                            </label>
                        </div>

                        <div class="gg-setting-item">
                            <div class="gg-setting-info">
                                <div class="gg-setting-title">Detailed Debugging</div>
                                <div class="gg-setting-desc">Log extra information to debug.txt.</div>
                            </div>
                            <label class="gg-switch">
                                <input type="checkbox" id="gg-set-debug" checked>
                                <span class="gg-slider"></span>
                            </label>
                        </div>

                        <div class="gg-setting-item">
                            <div class="gg-setting-info">
                                <div class="gg-setting-title">Toast Duration</div>
                                <div class="gg-setting-desc">Seconds before notifications disappear.</div>
                            </div>
                            <input type="number" id="gg-set-duration" class="gamegen-input-small" value="6" min="1" max="60">
                        </div>
                    </div>

                    <span class="section-label" style="margin-top: 24px;">Authentication</span>
                    <div class="gamegen-input-wrapper">
                        <input type="password" id="gg-key-input" class="gamegen-input" placeholder="Enter API Key">
                        <div style="margin-top: 8px; text-align: right;">
                             <a href="https://gamegen.lol" target="_blank" style="color: var(--gg-primary); font-size: 11px; text-decoration: none;">Get key @ gamegen.lol</a>
                        </div>
                    </div>
                    
                    <button class="gamegen-btn gamegen-btn-primary" id="gg-save-settings">Save All Settings</button>
                    
                    <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05);">
                        <span class="section-label">Maintenance</span>
                        <p style="font-size: 11px; color: var(--gg-text-dim); margin-bottom: 15px;">Version v${VERSION} · Pull latest changes from GitHub.</p>
                        <button class="gamegen-btn gamegen-btn-secondary" id="gg-update-plugin">Check for Updates</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(container);

        // -- Event Binding --

        container.querySelectorAll('.gamegen-tab').forEach(tab => {
            tab.onclick = () => App.switchTab(tab.dataset.tab);
        });

        document.getElementById('gg-gen-btn').onclick = () => {
            const id = document.getElementById('gg-app-id-input').value.trim();
            if (id) App.generate(id, document.getElementById('gg-gen-btn'));
            else createToast("Enter an AppID", "error");
        };

        document.getElementById('gg-save-settings').onclick = async () => {
            const key = document.getElementById('gg-key-input').value.trim();
            const newSettings = {
                api_key: key,
                auto_restart_steam: document.getElementById('gg-set-autorestart').checked,
                beta_updates: document.getElementById('gg-set-beta').checked,
                debug_logging: document.getElementById('gg-set-debug').checked,
                notification_duration: parseInt(document.getElementById('gg-set-duration').value) || 6
            };
            
            settings = { ...settings, ...newSettings };
            
            if (key) {
                localStorage.setItem('gamegen_api_key', key);
                apiKeySet = true;
            }
            
            const res = await safeCall('update_settings', { settings: newSettings });
            if (res && res.success) {
                createToast("Settings saved successfully!");
                App.switchTab('generator');
            } else {
                createToast("Error saving settings", "error");
            }
        };

        document.getElementById('gg-clear-history').onclick = async () => {
            await safeCall('clear_history');
            App.refreshHistory();
            createToast("History cleared");
        };

        document.getElementById('gg-update-plugin').onclick = () => {
            createToast("Updating from GitHub... Steam will restart.", "info");
            safeCall('update_plugin');
        };

        // Load Initial State
        (async () => {
            const serverSettings = await safeCall('get_settings');
            if (serverSettings) {
                settings = serverSettings;
                document.getElementById('gg-key-input').value = settings.api_key || '';
                document.getElementById('gg-set-autorestart').checked = settings.auto_restart_steam;
                document.getElementById('gg-set-beta').checked = settings.beta_updates;
                document.getElementById('gg-set-debug').checked = settings.debug_logging;
                document.getElementById('gg-set-duration').value = settings.notification_duration;
                
                if (settings.api_key) {
                    apiKeySet = true;
                } else {
                    App.switchTab('settings');
                    App.toggleUI(true);
                }
            } else {
                // Fallback to localStorage for API key only
                const savedKey = localStorage.getItem('gamegen_api_key');
                if (savedKey) {
                    apiKeySet = true;
                    document.getElementById('gg-key-input').value = savedKey;
                    settings.api_key = savedKey;
                } else {
                    App.switchTab('settings');
                    App.toggleUI(true);
                }
            }
        })();
        
        // Initial check and periodic poll for background updates
        setTimeout(() => checkPostRestart(), 3000);
        setInterval(() => checkPostRestart(), 300000); // Poll every 5 mins

        uiInjected = true;
    }

    // -- Store Page Integration --
    function getStoreAppId() {
        const match = window.location.href.match(/https:\/\/store\.steampowered\.com\/app\/(\d+)/);
        return match ? match[1] : null;
    }

    let isInjecting = false;
    async function injectStoreUI() {
        const appId = getStoreAppId();
        if (!appId) {
            const launcher = document.getElementById('gamegen-launcher-btn');
            if (launcher) launcher.style.display = 'flex';
            return;
        }

        // On store pages, we can keep the launcher visible too
        const launcher = document.getElementById('gamegen-launcher-btn');
        if (launcher) launcher.style.display = 'flex';

        if (isInjecting) return;
        isInjecting = true;
        try {
            // Expanded selectors for more reliability
            const selectors = [
                '.apphub_OtherSiteInfo',
                '#game_area_purchase',
                '.queue_actions_ctn',
                '.add_to_wishlist_area',
                '.game_area_already_on_account'
            ];

            let target = null;
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetHeight > 0) {
                    target = el;
                    break;
                }
            }

            if (!target || document.getElementById('gg-store-inject')) return;

            const div = document.createElement('div');
            div.id = 'gg-store-inject';
            div.style.margin = '10px 0';
            
            // Initial render as "Loading..." or just "Add" to be immediate
            div.innerHTML = `
                <a class="gg-store-btn" href="#" style="opacity: 0.7;">
                    <span>✨</span>
                    <span>Loading GameGen...</span>
                </a>
            `;
            target.prepend(div);

            // Now do the slow check
            const status = await safeCall('check_manifest_exists', { app_id: appId });
            const isInstalled = status?.exists;
            const btn = div.querySelector('a');

            if (isInstalled) {
                btn.className = 'gg-store-btn remove';
                btn.innerHTML = '<span>🗑️</span><span>Remove Game</span>';
            } else {
                btn.className = 'gg-store-btn';
                btn.innerHTML = '<span>✨</span><span>Add to GameGen</span>';
            }
            btn.style.opacity = '1';

            div.onclick = async (e) => {
                e.preventDefault();
                if (btn.classList.contains('remove')) {
                    const res = await safeCall('uninstall_manifest', { app_id: appId });
                    if (res && res.success) {
                        createToast("Manifest removed! Restart Steam.", 'success', 'Restart Now', () => safeCall('restart_steam'));
                        injectStoreUI();
                    }
                } else if (btn.classList.contains('restart')) {
                    safeCall('restart_steam');
                } else {
                    App.generate(appId, btn);
                }
            };
        } finally {
            isInjecting = false;
        }
    }

    // -- Lifecycle --
    const observer = new MutationObserver(() => injectStoreUI());

    const initInterval = setInterval(() => {
        if (document.body) {
            initUI();
            injectStoreUI();
            observer.observe(document.body, { childList: true, subtree: true });
            clearInterval(initInterval);
        }
    }, 1000);

})();
