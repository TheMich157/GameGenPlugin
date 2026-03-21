/**
 * GameGen Ultra-Premium Millennium Injectable - Version 5.0
 */

(function () {
    console.log("[GameGen] Ultra-Premium UI v5.0 initialized.");

    let uiInjected = false;
    let apiKeySet = false;
    let currentTab = 'generator';

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
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-20px) scale(0.9)';
                setTimeout(() => toast.remove(), 500);
            }, 6000);
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
    }

    function initUI() {
        if (document.getElementById('gamegen-plugin-container')) return;

        // 1. Launcher button
        const launcherBtn = document.createElement('button');
        launcherBtn.id = 'gamegen-launcher-btn';
        launcherBtn.innerHTML = '✨';
        launcherBtn.onclick = () => App.toggleUI();
        document.body.appendChild(launcherBtn);

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
                    <div class="gamegen-logo">✨</div>
                    <h1 class="gamegen-title">GAMEGEN <span style="font-size: 10px; color: var(--gg-text-dim); opacity: 0.5;">v3.3.0</span></h1>
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

                    <span class="section-label">Manual Generator</span>
                    <div class="gamegen-input-wrapper">
                        <input type="text" id="gg-app-id-input" class="gamegen-input" placeholder="Steam App ID (e.g. 730)">
                    </div>
                    <div style="display: flex; gap: 12px;">
                        <button class="gamegen-btn gamegen-btn-primary" id="gg-gen-btn">Generate</button>
                        <button class="gamegen-btn gamegen-btn-secondary" id="gg-req-btn">Request</button>
                    </div>
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
                    <span class="section-label">Authentication</span>
                    <p style="font-size: 12px; color: var(--gg-text-dim); margin-bottom: 20px;">Your API key is stored locally to authenticate requests with gamegen.lol</p>
                    <div class="gamegen-input-wrapper">
                        <input type="password" id="gg-key-input" class="gamegen-input" placeholder="Enter API Key">
                    </div>
                    <button class="gamegen-btn gamegen-btn-primary" id="gg-save-key">Update API Key</button>
                    
                    <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05);">
                        <span class="section-label">Maintenance</span>
                        <p style="font-size: 11px; color: var(--gg-text-dim); margin-bottom: 15px;">Version v3.3.0 · Pull latest changes from GitHub.</p>
                        <button class="gamegen-btn gamegen-btn-secondary" id="gg-update-plugin">Check for Updates</button>
                    </div>

                    <div style="margin-top: 24px; text-align: center;">
                        <a href="https://gamegen.lol" target="_blank" style="color: var(--gg-primary); font-size: 12px; text-decoration: none;">Get a key at gamegen.lol</a>
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

        document.getElementById('gg-req-btn').onclick = () => {
            const id = document.getElementById('gg-app-id-input').value.trim();
            if (id) App.request(id, document.getElementById('gg-req-btn'));
            else createToast("Enter an AppID", "error");
        };

        document.getElementById('gg-save-key').onclick = () => {
            const key = document.getElementById('gg-key-input').value.trim();
            if (key) {
                localStorage.setItem('gamegen_api_key', key);
                apiKeySet = true;
                safeCall('set_api_key', { key: key });
                createToast("API Key saved");
                App.switchTab('generator');
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
        const savedKey = localStorage.getItem('gamegen_api_key');
        if (savedKey) {
            apiKeySet = true;
            document.getElementById('gg-key-input').value = savedKey;
            safeCall('set_api_key', { key: savedKey });
            
            // Check for new games after login/init
            setTimeout(() => checkPostRestart(), 3000);
        } else {
            App.switchTab('settings');
            App.toggleUI(true);
        }

        uiInjected = true;
    }

    // -- Store Page Integration --
    function getStoreAppId() {
        const match = window.location.href.match(/https:\/\/store\.steampowered\.com\/app\/(\d+)/);
        return match ? match[1] : null;
    }

    let isInjecting = false;
    async function injectStoreUI() {
        if (isInjecting) return;
        
        const appId = getStoreAppId();
        if (!appId) {
            const launcher = document.getElementById('gamegen-launcher-btn');
            if (launcher) launcher.style.display = 'flex';
            return;
        }

        const launcher = document.getElementById('gamegen-launcher-btn');
        if (launcher) launcher.style.display = 'none';

        isInjecting = true;
        try {
            // Priority selectors for the sidebar area
            const selectors = [
                '.add_to_wishlist_area', 
                '.queue_actions_ctn',
                '#game_area_purchase',
                '.apphub_OtherSiteInfo'
            ];

            let target = null;
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && (el.offsetHeight > 0 || el.offsetWidth > 0)) {
                    target = el;
                    break;
                }
            }

            if (!target) return;

            // Ensure no duplicates
            document.querySelectorAll('#gg-store-inject').forEach(el => el.remove());

            const status = await safeCall('check_manifest_exists', { app_id: appId });
            const isInstalled = status?.exists;

            // Double check after async call
            if (document.getElementById('gg-store-inject')) return;

            const div = document.createElement('div');
            div.id = 'gg-store-inject';
            div.style.display = 'inline-block';
            div.style.verticalAlign = 'top';
            
            // If we're in the OtherSiteInfo area, we want to match the width/style of those buttons
            const isInOtherSiteInfo = target.classList.contains('apphub_OtherSiteInfo');
            
            if (isInstalled) {
                div.innerHTML = `
                    <a class="btnv6_red_hoverfade btn_medium" href="#" style="padding: 0 15px; height: 30px; line-height: 30px; display: inline-flex; align-items: center; gap: 6px; margin-right: 2px;">
                        <span>🗑️</span>
                        <span style="color: white; font-weight: 500; font-size: 12px;">Remove Game</span>
                    </a>
                `;
            } else {
                div.innerHTML = `
                    <a class="btnv6_blue_hoverfade btn_medium" href="#" style="padding: 0 15px; height: 30px; line-height: 30px; display: inline-flex; align-items: center; gap: 6px; margin-right: 2px;">
                        <span>✨</span>
                        <span style="color: white; font-weight: 500; font-size: 12px;">Add to GameGen</span>
                    </a>
                `;
            }

            div.onclick = async (e) => {
                e.preventDefault();
                const btn = div.querySelector('a');
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
            
            // Smart Insertion: Prepend to Community Hub area or purchase box for visibility
            if (isInOtherSiteInfo || target.id === 'game_area_purchase' || target.classList.contains('add_to_wishlist_area')) {
                target.prepend(div);
            } else {
                target.appendChild(div);
            }
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
