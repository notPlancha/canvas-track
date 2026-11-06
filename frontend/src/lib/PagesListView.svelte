<script>
  let { pages = [], onSelectPage } = $props();

  let searchQuery = $state('');

  const filteredPages = $derived(
    pages.filter((p) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      return (
        (p.title || '').toLowerCase().includes(q) ||
        (p.url || '').toLowerCase().includes(q)
      );
    })
  );
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div>
      <h2 style="font-size: 20px; font-weight: 700; color: var(--canvas-navy);">Course Pages</h2>
      <div style="font-size: 13px; color: var(--canvas-text-muted);">
        {pages.length} total wiki pages archived locally
      </div>
    </div>

    <input
      type="text"
      class="form-input"
      style="max-width: 280px;"
      placeholder="Filter pages..."
      bind:value={searchQuery}
    />
  </div>

  <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm);">
    {#if filteredPages.length === 0}
      <div style="padding: 40px; text-align: center; color: var(--canvas-text-muted);">
        No matching pages found.
      </div>
    {:else}
      {#each filteredPages as page}
        <div
          class="module-item"
          onclick={() => onSelectPage(page.url)}
          role="button"
          tabindex="0"
          onkeydown={(e) => e.key === 'Enter' && onSelectPage(page.url)}
          style="padding: 16px 20px;"
        >
          <span style="font-size: 18px; margin-right: 8px;">📄</span>
          <div style="flex: 1;">
            <div style="font-size: 15px; font-weight: 600; color: var(--canvas-accent-blue); display: flex; align-items: center; gap: 8px;">
              <span>{page.title || 'Untitled Page'}</span>
              {#if page.front_page}
                <span class="offline-badge" style="background: #E8F0FE; color: #1A73E8; font-size: 10px; padding: 2px 8px;">
                  Front Page
                </span>
              {/if}
            </div>
            <div style="font-size: 12px; color: var(--canvas-text-muted); margin-top: 2px;">
              Slug: <code>{page.url}</code>
              {#if page.updated_at}
                • Updated: {new Date(page.updated_at).toLocaleDateString()}
              {/if}
            </div>
          </div>
          <button class="btn btn-secondary btn-sm">Read Page →</button>
        </div>
      {/each}
    {/if}
  </div>
</div>
