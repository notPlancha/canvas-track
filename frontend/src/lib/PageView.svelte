<script>
  import { openVaultFile } from './api.js';
  import CanvasLinkButtons from './CanvasLinkButtons.svelte';

  let {
    page = null,
    isFrontPage = false,
    siteId = '',
    courseId = 0,
    onNavigatePage,
  } = $props();

  let showRawJson = $state(false);
  let statusToast = $state('');

  async function handleContentClick(e) {
    const target = e.target.closest('a');
    if (!target) return;

    const href = target.getAttribute('href');
    if (!href) return;

    // Check if it's an internal hash route like #/site/:siteId/course/:courseId/pages/:pageUrl
    if (href.startsWith('#/site/')) {
      e.preventDefault();
      const parts = href.split('/');
      // parts: ['#', 'site', siteId, 'course', courseId, 'pages', pageUrl]
      const pageIndex = parts.indexOf('pages');
      if (pageIndex !== -1 && parts[pageIndex + 1]) {
        const targetPageUrl = parts[pageIndex + 1];
        if (onNavigatePage) {
          onNavigatePage(targetPageUrl);
          return;
        }
      }
      window.location.hash = href;
      return;
    }

    // Check if it's an external link
    if (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('//')) {
      e.preventDefault();
      window.open(href, '_blank', 'noopener,noreferrer');
      return;
    }

    // Check if it's a local vault file URL: /api/vault/files/:siteId/:courseId/:fileId
    if (href.startsWith('/api/vault/files/')) {
      e.preventDefault();
      const parts = href.split('/').filter(Boolean);
      const fId = parts[parts.length - 1];
      const sId = parts[3] || siteId;
      const cId = parts[4] || courseId;

      statusToast = '📂 Opening file with default system application...';
      try {
        await openVaultFile(sId, cId, fId);
        statusToast = '✓ File opened in system viewer!';
        setTimeout(() => {
          statusToast = '';
        }, 3000);
      } catch (err) {
        console.error('System open failed, opening via browser fallback', err);
        statusToast = 'Opening via browser...';
        window.open(href, '_blank');
        setTimeout(() => {
          statusToast = '';
        }, 3000);
      }
    }
  }
</script>

{#if page}
  <div class="wiki-page-container">
    <div class="wiki-page-header">
      <div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <h1 class="wiki-page-title">{page.title || 'Untitled Page'}</h1>
          {#if isFrontPage || page.front_page}
            <span class="offline-badge" style="background: #E8F0FE; color: #1A73E8; font-size: 11px;">
              🏠 Front Page (Home)
            </span>
          {/if}
        </div>
        <div class="wiki-page-meta">
          {#if page.updated_at}
            <span>Last updated: {new Date(page.updated_at).toLocaleString()}</span>
          {/if}
          {#if page.url}
            <span style="margin-left: 12px; opacity: 0.7;">Slug: <code>{page.url}</code></span>
          {/if}
        </div>
      </div>

      <div style="display: flex; align-items: center; gap: 8px;">
        <CanvasLinkButtons url={page.html_url} label="page" />
        <button
          class="btn btn-secondary btn-sm"
          onclick={() => showRawJson = !showRawJson}
          title="View Canvas API JSON"
        >
          {showRawJson ? 'Hide Raw JSON' : '🔍 Inspect API JSON'}
        </button>
      </div>
    </div>

    {#if showRawJson}
      <div style="background: #1E272E; color: #E0E4E8; padding: 14px; border-radius: 6px; font-family: monospace; font-size: 12px; margin-bottom: 24px; max-height: 350px; overflow-y: auto;">
        <pre>{JSON.stringify(page, null, 2)}</pre>
      </div>
    {/if}

    {#if statusToast}
      <div style="background: #E8F0FE; color: #1967D2; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 500; margin-bottom: 16px; border: 1px solid #D2E3FC; display: flex; align-items: center; gap: 8px;">
        <span>ℹ️</span> {statusToast}
      </div>
    {/if}

    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="wiki-content"
      onclick={handleContentClick}
    >
      {#if page.body_rewritten || page.body}
        {@html page.body_rewritten || page.body}
      {:else}
        <div style="padding: 40px; text-align: center; color: var(--canvas-text-muted); background: #F8F9FA; border-radius: 8px;">
          <em>This page has no text or body content.</em>
        </div>
      {/if}
    </div>
  </div>
{:else}
  <div style="text-align: center; padding: 60px; color: var(--canvas-text-muted);">
    Loading page content...
  </div>
{/if}

<style>
  .wiki-page-container {
    background: #fff;
    padding: 32px;
    border-radius: 8px;
    border: 1px solid var(--canvas-border);
    box-shadow: var(--shadow-sm);
  }
</style>
