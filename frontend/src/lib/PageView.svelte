<script>
  import { openVaultFile, getPageComments, addPageComment, deletePageComment } from './api.js';
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
  let comments = $state([]);
  let newCommentText = $state('');
  let isAddingComment = $state(false);

  $effect(() => {
    if (page && page.url && siteId && courseId) {
      loadComments(siteId, courseId, page.url);
    } else {
      comments = [];
    }
  });

  async function loadComments(sId, cId, pUrl) {
    try {
      comments = await getPageComments(sId, cId, pUrl);
    } catch (e) {
      console.error('Failed to load comments', e);
      comments = [];
    }
  }

  async function handleAddComment(e) {
    e.preventDefault();
    const text = newCommentText.trim();
    if (!text || !page?.url) return;
    isAddingComment = true;
    try {
      const res = await addPageComment(siteId, courseId, page.url, text);
      if (res.success && res.comment) {
        comments = [...comments, res.comment];
      }
      newCommentText = '';
    } catch (e) {
      console.error('Failed to add comment', e);
    } finally {
      isAddingComment = false;
    }
  }

  async function handleDeleteComment(commentId) {
    if (!page?.url) return;
    try {
      await deletePageComment(siteId, courseId, page.url, commentId);
      comments = comments.filter((c) => c.id !== commentId);
    } catch (e) {
      console.error('Failed to delete comment', e);
    }
  }

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

    <!-- Page Notes & Comments Section -->
    <div class="page-comments-section" style="margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--canvas-border);">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <h3 style="font-size: 16px; font-weight: 600; color: var(--canvas-navy); display: flex; align-items: center; gap: 8px; margin: 0;">
          <span>📝</span> Local Page Notes & Comments
          {#if comments.length > 0}
            <span style="font-size: 12px; background: #E2E8F0; color: #4A5568; padding: 2px 8px; border-radius: 12px; font-weight: 500;">
              {comments.length}
            </span>
          {/if}
        </h3>
        <span style="font-size: 12px; color: var(--canvas-text-muted);">
          Saved locally in vault
        </span>
      </div>

      <!-- Existing Comments List -->
      {#if comments.length > 0}
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px;">
          {#each comments as c (c.id)}
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px; position: relative;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; color: var(--canvas-text-muted); font-weight: 500;">
                  📅 {new Date(c.created_at).toLocaleString()}
                </span>
                <button
                  type="button"
                  class="btn btn-secondary btn-sm"
                  style="padding: 2px 6px; font-size: 11px; color: #E53E3E; border-color: #FEB2B2;"
                  onclick={() => handleDeleteComment(c.id)}
                  title="Delete note"
                >
                  🗑️ Delete
                </button>
              </div>
              <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #2D3748; white-space: pre-wrap;">{c.text}</p>
            </div>
          {/each}
        </div>
      {:else}
        <div style="padding: 16px; text-align: center; color: var(--canvas-text-muted); background: #F8FAFC; border: 1px dashed #E2E8F0; border-radius: 8px; margin-bottom: 20px; font-size: 13px;">
          No notes on this page yet. Add personal reminders, summaries, or questions below.
        </div>
      {/if}

      <!-- Add New Comment Box -->
      <form onsubmit={handleAddComment} style="display: flex; flex-direction: column; gap: 8px;">
        <textarea
          class="form-input"
          bind:value={newCommentText}
          placeholder="Type a personal note or comment for this page..."
          rows="3"
          style="width: 100%; resize: vertical; font-family: inherit; font-size: 13px; line-height: 1.5;"
        ></textarea>
        <div style="display: flex; justify-content: flex-end;">
          <button
            type="submit"
            class="btn btn-primary btn-sm"
            disabled={isAddingComment || !newCommentText.trim()}
          >
            {isAddingComment ? 'Saving...' : '+ Add Note'}
          </button>
        </div>
      </form>
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
