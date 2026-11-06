<script>
  let { modules = [], onNavigatePage, onNavigateAssignment, onNavigateDiscussion } = $props();

  let collapsed = $state({});

  function toggleModule(moduleId) {
    collapsed[moduleId] = !collapsed[moduleId];
  }

  function getItemIcon(type) {
    switch (type) {
      case 'Page': return '📄';
      case 'File': return '📎';
      case 'Assignment': return '📝';
      case 'Discussion': return '💬';
      case 'SubHeader': return '📌';
      case 'ExternalUrl': return '🔗';
      case 'Quiz': return '❓';
      default: return '🔹';
    }
  }

  function handleItemClick(item) {
    if (item.type === 'Page' && item.page_url) {
      if (onNavigatePage) onNavigatePage(item.page_url);
    } else if (item.type === 'Assignment' && item.content_id) {
      if (onNavigateAssignment) onNavigateAssignment(item.content_id);
    } else if (item.type === 'Discussion' && item.content_id) {
      if (onNavigateDiscussion) onNavigateDiscussion(item.content_id);
    } else if (item.html_url) {
      window.open(item.html_url, '_blank');
    }
  }
</script>

<div>
  {#if modules.length === 0}
    <div style="text-align: center; padding: 60px; color: var(--canvas-text-muted); background: #fff; border-radius: 8px; border: 1px solid var(--canvas-border);">
      No modules found in this course.
    </div>
  {:else}
    {#each modules as mod}
      <div class="module-block">
        <button
          type="button"
          class="module-header"
          onclick={() => toggleModule(mod.id)}
          style="width: 100%; text-align: left; background: none; border: none;"
        >
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 12px; color: var(--canvas-text-muted);">{collapsed[mod.id] ? '▶' : '▼'}</span>
            <span>{mod.name}</span>
          </div>
          <span style="font-size: 12px; font-weight: normal; color: var(--canvas-text-muted);">
            {(mod.items || []).length} items
          </span>
        </button>

        {#if !collapsed[mod.id]}
          <div>
            {#each (mod.items || []) as item}
              {#if item.type === 'SubHeader'}
                <div style="padding: 10px 20px; font-weight: 600; font-size: 13px; color: var(--canvas-text-muted); background: #FAFBFB; border-bottom: 1px solid #EDF2F7;">
                  {item.title}
                </div>
              {:else}
                <div
                  class="module-item"
                  onclick={() => handleItemClick(item)}
                  role="button"
                  tabindex="0"
                  onkeydown={(e) => e.key === 'Enter' && handleItemClick(item)}
                >
                  <span class="module-item-icon">{getItemIcon(item.type)}</span>
                  <div style="flex: 1;">
                    <div style="font-weight: 500; color: var(--canvas-navy);">{item.title}</div>
                    <div style="font-size: 11px; color: var(--canvas-text-muted);">{item.type}</div>
                  </div>
                  {#if item.type === 'Page'}
                    <span class="btn btn-secondary btn-sm" style="font-size: 11px; padding: 3px 8px;">View Page</span>
                  {/if}
                </div>
              {/if}
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>
