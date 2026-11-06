<script>
  let { url = '', label = 'item' } = $props();

  let copied = $state(false);

  function handleOpen(e) {
    e.stopPropagation();
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }

  async function handleCopy(e) {
    e.stopPropagation();
    if (!url) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const ta = document.createElement('textarea');
        ta.value = url;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch (err) {
      console.error('Failed to copy link', err);
    }
  }
</script>

{#if url}
  <div class="canvas-link-actions" role="group">
    <button
      type="button"
      class="btn-icon-action"
      onclick={handleOpen}
      title="Open {label} in original Canvas page"
      aria-label="Open {label} in original Canvas page"
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
        <polyline points="15 3 21 3 21 9"></polyline>
        <line x1="10" y1="14" x2="21" y2="3"></line>
      </svg>
    </button>

    <button
      type="button"
      class="btn-icon-action {copied ? 'copied' : ''}"
      onclick={handleCopy}
      title={copied ? 'Link copied!' : `Copy link to original Canvas ${label}`}
      aria-label="Copy link to original Canvas {label}"
    >
      {#if copied}
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#137333" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      {:else}
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
      {/if}
    </button>
  </div>
{/if}

<style>
  .canvas-link-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .btn-icon-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    border-radius: 5px;
    border: 1px solid var(--canvas-border, #D0D7DE);
    background: #FFFFFF;
    color: var(--canvas-text-muted, #57606A);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-icon-action:hover {
    background: #F3F4F6;
    color: var(--canvas-navy, #1F2937);
    border-color: #BEC8D2;
  }

  .btn-icon-action.copied {
    background: #E6F4EA;
    border-color: #34A853;
    color: #137333;
  }
</style>
