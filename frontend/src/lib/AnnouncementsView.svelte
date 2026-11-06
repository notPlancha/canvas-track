<script>
  let { announcements = [] } = $props();
</script>

<div>
  <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm);">
    <div style="padding: 16px 20px; border-bottom: 1px solid var(--canvas-border); font-size: 16px; font-weight: 600;">
      Announcements ({announcements.length})
    </div>

    {#if announcements.length === 0}
      <div style="padding: 40px; text-align: center; color: var(--canvas-text-muted);">
        No announcements posted for this course.
      </div>
    {:else}
      <div style="padding: 20px; display: flex; flex-direction: column; gap: 20px;">
        {#each announcements as ann}
          <div style="border: 1px solid var(--canvas-border); border-radius: 8px; padding: 20px; background: #FAFBFB;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
              <h3 style="font-size: 17px; font-weight: 700; color: var(--canvas-navy);">
                {ann.title}
              </h3>
              {#if ann.posted_at}
                <span style="font-size: 12px; color: var(--canvas-text-muted); background: #E0E4E8; padding: 2px 8px; border-radius: 10px;">
                  {new Date(ann.posted_at).toLocaleDateString()}
                </span>
              {/if}
            </div>

            <div style="font-size: 12px; color: var(--canvas-text-muted); margin-bottom: 14px;">
              By: <strong>{ann.author?.display_name || 'Instructor'}</strong>
            </div>

            <div class="wiki-content" style="font-size: 14px;">
              {#if ann.message_rewritten || ann.message}
                {@html ann.message_rewritten || ann.message}
              {:else}
                <em>No message content.</em>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
