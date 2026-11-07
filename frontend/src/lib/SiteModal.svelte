<script>
  import { addSite, updateSite, getEnvConfig, getMoodleSsoUrl } from './api.js';

  let {
    open = false,
    siteToEdit = null,
    onClose = () => {},
    onSiteAdded = () => {},
    onSiteUpdated = () => {},
  } = $props();

  let platform = $state('canvas'); // 'canvas' or 'moodle'
  let domain = $state('');
  let token = $state('');
  let siteId = $state('');
  let showToken = $state(false);
  let isLoading = $state(false);
  let errorMessage = $state('');
  let isWaitingForSSO = $state(false);
  let ssoEventSource = null;

  let envConfig = $state({
    canvas_domain: '',
    canvas_token: '',
    canvas_site_id: '',
    moodle_url: '',
    moodle_token: '',
    moodle_course_id: '',
    has_env: false,
  });
  let loadedFromEnv = $state(false);

  $effect(() => {
    if (open) {
      errorMessage = '';
      showToken = false;
      loadedFromEnv = false;
      isWaitingForSSO = false;

      if (siteToEdit) {
        platform = siteToEdit.platform || 'canvas';
        domain = siteToEdit.domain || '';
        token = siteToEdit.token || '';
        siteId = siteToEdit.id || '';
      } else {
        domain = '';
        token = '';
        siteId = '';

        // Check for local .env defaults
        getEnvConfig().then((cfg) => {
          if (cfg) {
            envConfig = cfg;
            applyEnvDefaults();
          }
        }).catch(() => {
          // ignore if backend endpoint is unavailable
        });
      }
    } else {
      stopSSOListener();
    }
  });

  function applyEnvDefaults() {
    if (platform === 'moodle') {
      if (envConfig.moodle_url) {
        domain = envConfig.moodle_url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
        loadedFromEnv = true;
      }
      if (envConfig.moodle_token) {
        token = envConfig.moodle_token;
        loadedFromEnv = true;
      }
    } else {
      if (envConfig.canvas_domain) {
        domain = envConfig.canvas_domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
        loadedFromEnv = true;
      }
      if (envConfig.canvas_token) {
        token = envConfig.canvas_token;
        loadedFromEnv = true;
      }
      if (envConfig.canvas_site_id) {
        siteId = envConfig.canvas_site_id;
      }
    }
  }

  function handlePlatformChange(newPlatform) {
    platform = newPlatform;
    errorMessage = '';
    loadedFromEnv = false;
    token = '';
    domain = '';
    siteId = '';
    applyEnvDefaults();
  }

  function openCanvasSettings() {
    let cleanDomain = (domain.trim() || envConfig.canvas_domain || 'canvas.instructure.com')
      .replace(/^https?:\/\//, '')
      .replace(/\/.*$/, '');
    window.open(`https://${cleanDomain}/profile/settings#access_tokens`, '_blank');
  }

  async function openMoodleSSO() {
    let cleanDomain = (domain.trim() || envConfig.moodle_url || 'moodle.example.edu')
      .replace(/^https?:\/\//, '')
      .replace(/\/.*$/, '');
    if (!cleanDomain) {
      errorMessage = 'Please enter your Moodle institution domain first.';
      return;
    }
    errorMessage = '';
    isWaitingForSSO = true;

    try {
      const data = await getMoodleSsoUrl(cleanDomain);
      window.open(data.url, '_blank');
      startSSOListener();
    } catch (e) {
      isWaitingForSSO = false;
      errorMessage = e.message || 'Failed to generate SSO URL';
    }
  }

  function startSSOListener() {
    stopSSOListener();
    try {
      ssoEventSource = new EventSource('/api/auth/events');
      ssoEventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload && payload.type === 'auth_success' && payload.site) {
            stopSSOListener();
            isWaitingForSSO = false;
            onSiteAdded(payload.site);
            onClose();
          }
        } catch {
          // ignore malformed events
        }
      };
      ssoEventSource.onerror = () => {
        // SSE error, keep polling or let user paste
      };
    } catch (err) {
      console.debug('SSE not supported or connection failed', err);
    }
  }

  function stopSSOListener() {
    if (ssoEventSource) {
      ssoEventSource.close();
      ssoEventSource = null;
    }
  }

  async function pasteFromClipboard() {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          token = text.trim();
          errorMessage = '';
        }
      }
    } catch {
      errorMessage = 'Could not access clipboard. Please paste manually into the input box.';
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    errorMessage = '';
    isLoading = true;

    try {
      const cleanDomain = domain.trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '');
      if (siteToEdit) {
        const res = await updateSite(
          siteToEdit.id,
          cleanDomain,
          token.trim(),
          siteId.trim() || null,
          platform
        );
        isLoading = false;
        onSiteUpdated(res.site);
      } else {
        const res = await addSite(
          cleanDomain,
          token.trim(),
          siteId.trim() || null,
          platform
        );
        isLoading = false;
        onSiteAdded(res.site);
      }
      stopSSOListener();
      onClose();
    } catch (err) {
      isLoading = false;
      errorMessage = err.message || `Failed to authenticate with ${platform === 'moodle' ? 'Moodle' : 'Canvas'}`;
    }
  }
</script>

{#if open}
  <div class="modal-backdrop" onclick={onClose} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document">
      <div class="modal-header">
        <h2>
          {siteToEdit
            ? `Edit ${platform === 'moodle' ? 'Moodle' : 'Canvas'} Site`
            : 'Add LMS Site'}
        </h2>
        <button class="btn btn-secondary btn-sm" onclick={onClose}>✕</button>
      </div>

      {#if !siteToEdit}
        <!-- Platform Switcher Tabs -->
        <div class="platform-tabs">
          <button
            type="button"
            class="platform-tab {platform === 'canvas' ? 'active' : ''}"
            onclick={() => handlePlatformChange('canvas')}
          >
            🎓 Canvas LMS
          </button>
          <button
            type="button"
            class="platform-tab {platform === 'moodle' ? 'active' : ''}"
            onclick={() => handlePlatformChange('moodle')}
          >
            🟠 Moodle LMS
          </button>
        </div>
      {/if}

      <form onsubmit={handleSubmit}>
        <div class="modal-body">
          {#if errorMessage}
            <div class="alert-error">
              ⚠️ {errorMessage}
            </div>
          {/if}

          {#if loadedFromEnv && !siteToEdit}
            <div class="alert-info">
              <span>⚙️</span>
              <span>Pre-filled from your local <code>.env</code> file.</span>
            </div>
          {/if}

          {#if platform === 'moodle'}
            <!-- Moodle Platform Form -->
            <div class="form-group">
              <label class="form-label" for="site-domain">Moodle Domain or URL</label>
              <input
                id="site-domain"
                class="form-input"
                type="text"
                bind:value={domain}
                placeholder="e.g. moodle.example.edu or moodle.your-university.edu"
                required
              />
              <div class="form-hint">The domain your institution uses for Moodle LMS.</div>
            </div>

            <!-- Hands-Free SSO Login Button -->
            <div class="sso-box">
              <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">
                🔑 Hands-Free Single Sign-On (Microsoft / SAML)
              </div>
              <p style="font-size: 12px; color: #4A5568; margin-bottom: 10px; line-height: 1.4;">
                Log in with your standard university account. Your browser will prompt to hand the login directly to Canvas Track.
              </p>
              <button
                type="button"
                class="btn btn-primary"
                style="width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; font-weight: 600;"
                onclick={openMoodleSSO}
              >
                <span>↗</span>
                <span>Log in with University SSO</span>
              </button>

              {#if isWaitingForSSO}
                <div class="sso-waiting-status">
                  <span class="spinner-dot"></span>
                  <span>Waiting for login to complete in browser... (click "Open Canvas Track" when prompted)</span>
                </div>
              {/if}
            </div>

            <div style="text-align: center; margin: 12px 0; color: #718096; font-size: 12px; font-weight: 500;">
              ── OR PASTE TOKEN / LINK MANUALLY ──
            </div>

            <div class="form-group">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <label class="form-label" for="site-token" style="margin-bottom: 0;">Security Key or SSO Link</label>
                <button
                  type="button"
                  class="btn btn-secondary btn-xs"
                  onclick={pasteFromClipboard}
                  title="Paste from clipboard"
                >
                  📋 Paste from Clipboard
                </button>
              </div>
              <div style="position: relative; display: flex; align-items: center;">
                <input
                  id="site-token"
                  class="form-input"
                  type={showToken ? 'text' : 'password'}
                  bind:value={token}
                  placeholder="Paste moodlemobile://... link or token here"
                  style="padding-right: 42px; font-family: monospace; font-size: 12px;"
                />
                <button
                  type="button"
                  onclick={() => (showToken = !showToken)}
                  title={showToken ? 'Hide token' : 'Show token'}
                  aria-label={showToken ? 'Hide token' : 'Show token'}
                  class="token-toggle-btn"
                >
                  {#if showToken}🙈{:else}👁️{/if}
                </button>
              </div>
              <div class="form-hint">Accepts raw tokens, base64 strings, or moodlemobile:// links.</div>
            </div>

          {:else}
            <!-- Canvas Platform Form -->
            <div class="form-group">
              <label class="form-label" for="site-domain">Canvas Domain</label>
              <input
                id="site-domain"
                class="form-input"
                type="text"
                bind:value={domain}
                placeholder={envConfig.canvas_domain ? `e.g. ${envConfig.canvas_domain}` : "e.g. canvas.instructure.com"}
                required
              />
              <div class="form-hint">The domain your institution uses for Canvas LMS.</div>
            </div>

            <div class="token-guide-box">
              <strong>How to get your Personal Access Token in 3 clicks:</strong>
              <ol>
                <li>Click the button below to open your Canvas profile settings:</li>
                <div style="margin: 8px 0;">
                  <button type="button" class="btn btn-secondary btn-sm" onclick={openCanvasSettings}>
                    ↗ Open Canvas Token Settings
                  </button>
                </div>
                <li>Scroll down to <strong>Approved Integrations</strong> and click <strong>+ New Access Token</strong>.</li>
                <li>Give it a purpose (e.g. <code>CanvasTrack</code>), generate, and paste it below.</li>
              </ol>
            </div>

            <div class="form-group">
              <label class="form-label" for="site-token">Personal Access Token</label>
              <div style="position: relative; display: flex; align-items: center;">
                <input
                  id="site-token"
                  class="form-input"
                  type={showToken ? 'text' : 'password'}
                  bind:value={token}
                  placeholder="Paste token here..."
                  required
                  style="padding-right: 42px; font-family: monospace; font-size: 13px;"
                />
                <button
                  type="button"
                  onclick={() => (showToken = !showToken)}
                  title={showToken ? 'Hide token' : 'Show token'}
                  aria-label={showToken ? 'Hide token' : 'Show token'}
                  class="token-toggle-btn"
                >
                  {#if showToken}🙈{:else}👁️{/if}
                </button>
              </div>
              <div class="form-hint">Read-only API access. Your token never leaves your local machine.</div>
            </div>
          {/if}

          <div class="form-group">
            <label class="form-label" for="site-id">Site Nickname / ID (Optional)</label>
            <input
              id="site-id"
              class="form-input"
              type="text"
              bind:value={siteId}
              placeholder="e.g. lnu or university"
            />
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" onclick={onClose} disabled={isLoading}>Cancel</button>
          <button type="submit" class="btn btn-primary" disabled={isLoading}>
            {#if isLoading}
              Saving...
            {:else if siteToEdit}
              Save Changes
            {:else}
              Connect & Verify
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .platform-tabs {
    display: flex;
    border-bottom: 1px solid #E2E8F0;
    margin-bottom: 16px;
    padding: 0 20px;
    gap: 8px;
    background: #F8FAFC;
  }
  .platform-tab {
    padding: 10px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    color: #64748B;
    transition: all 0.15s ease;
  }
  .platform-tab:hover {
    color: #1E293B;
  }
  .platform-tab.active {
    color: #2563EB;
    border-bottom-color: #2563EB;
  }
  .alert-error {
    background: #FCE8E6;
    color: #C5221F;
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 13px;
  }
  .alert-info {
    background: #E8F0FE;
    color: #1A73E8;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 14px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    border: 1px solid #D2E3FC;
  }
  .sso-box {
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 14px;
  }
  .sso-waiting-status {
    margin-top: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #166534;
    background: #DCFCE7;
    padding: 8px 12px;
    border-radius: 6px;
  }
  .spinner-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #16A34A;
    display: inline-block;
    animation: pulse-dot 1.2s infinite ease-in-out;
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 0.3; transform: scale(0.8); }
    50% { opacity: 1; transform: scale(1.2); }
  }
  .token-toggle-btn {
    position: absolute;
    right: 10px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    font-size: 15px;
    color: #718096;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .btn-xs {
    padding: 2px 8px;
    font-size: 11px;
    border-radius: 4px;
  }
</style>
