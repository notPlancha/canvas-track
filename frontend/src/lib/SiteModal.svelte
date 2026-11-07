<script>
  import { addSite, updateSite, getEnvConfig } from './api.js';

  let {
    open = false,
    siteToEdit = null,
    onClose = () => {},
    onSiteAdded = () => {},
    onSiteUpdated = () => {},
  } = $props();

  let domain = $state('');
  let token = $state('');
  let siteId = $state('');
  let showToken = $state(false);
  let isLoading = $state(false);
  let errorMessage = $state('');
  let envConfig = $state({ canvas_domain: '', canvas_token: '', canvas_site_id: '', has_env: false });
  let loadedFromEnv = $state(false);

  $effect(() => {
    if (open) {
      errorMessage = '';
      showToken = false;
      loadedFromEnv = false;
      if (siteToEdit) {
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
            let usedEnv = false;
            if (!domain && cfg.canvas_domain) {
              domain = cfg.canvas_domain;
              usedEnv = true;
            }
            if (!token && cfg.canvas_token) {
              token = cfg.canvas_token;
              usedEnv = true;
            }
            if (!siteId && cfg.canvas_site_id) {
              siteId = cfg.canvas_site_id;
            }
            if (usedEnv) {
              loadedFromEnv = true;
            }
          }
        }).catch(() => {
          // ignore if backend endpoint is unavailable
        });
      }
    }
  });

  function openCanvasSettings() {
    let cleanDomain = (domain.trim() || envConfig.canvas_domain || 'canvas.instructure.com').replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    window.open(`https://${cleanDomain}/profile/settings#access_tokens`, '_blank');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    errorMessage = '';
    isLoading = true;

    try {
      const cleanDomain = domain.trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '');
      if (siteToEdit) {
        const res = await updateSite(siteToEdit.id, cleanDomain, token.trim(), siteId.trim() || null);
        isLoading = false;
        onSiteUpdated(res.site);
      } else {
        const res = await addSite(cleanDomain, token.trim(), siteId.trim() || null);
        isLoading = false;
        onSiteAdded(res.site);
      }
      onClose();
    } catch (err) {
      isLoading = false;
      errorMessage = err.message || 'Failed to authenticate with Canvas';
    }
  }
</script>

{#if open}
  <div class="modal-backdrop" onclick={onClose} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document">
      <div class="modal-header">
        <h2>{siteToEdit ? 'Edit Canvas Site' : 'Add Canvas Site'}</h2>
        <button class="btn btn-secondary btn-sm" onclick={onClose}>✕</button>
      </div>

      <form onsubmit={handleSubmit}>
        <div class="modal-body">
          {#if errorMessage}
            <div style="background: #FCE8E6; color: #C5221F; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px;">
              ⚠️ {errorMessage}
            </div>
          {/if}

          {#if loadedFromEnv && !siteToEdit}
            <div style="background: #E8F0FE; color: #1A73E8; padding: 8px 12px; border-radius: 6px; margin-bottom: 14px; font-size: 12px; display: flex; align-items: center; gap: 6px; border: 1px solid #D2E3FC;">
              <span>⚙️</span>
              <span>Pre-filled from your local <code>.env</code> file.</span>
            </div>
          {/if}

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
                style="position: absolute; right: 10px; background: none; border: none; cursor: pointer; padding: 4px; font-size: 15px; color: #718096; display: flex; align-items: center; justify-content: center;"
              >
                {#if showToken}
                  🙈
                {:else}
                  👁️
                {/if}
              </button>
            </div>
            <div class="form-hint">Read-only API access. Your token never leaves your local machine.</div>
          </div>

          <div class="form-group">
            <label class="form-label" for="site-id">Site Nickname / ID (Optional)</label>
            <input
              id="site-id"
              class="form-input"
              type="text"
              bind:value={siteId}
              placeholder="e.g. ltu or university"
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
