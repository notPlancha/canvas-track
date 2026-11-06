<script>
  import { getVaultDiscussionThread } from './api.js';

  let { siteId = '', courseId = 0, discussions = [] } = $props();

  let selectedTopic = $state(null);
  let threadData = $state(null);
  let isLoadingThread = $state(false);

  async function openTopic(topic) {
    selectedTopic = topic;
    isLoadingThread = true;
    threadData = null;
    try {
      threadData = await getVaultDiscussionThread(siteId, courseId, topic.id);
    } catch {
      threadData = null;
    } finally {
      isLoadingThread = false;
    }
  }
</script>

<div>
  {#if selectedTopic}
    <div style="margin-bottom: 16px;">
      <button class="btn btn-secondary btn-sm" onclick={() => (selectedTopic = null)}>
        ← Back to All Discussions
      </button>
    </div>

    <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; padding: 28px; box-shadow: var(--shadow-sm); margin-bottom: 24px;">
      <h1 style="font-size: 22px; font-weight: 700; color: var(--canvas-navy); margin-bottom: 8px;">
        {selectedTopic.title}
      </h1>
      <div style="font-size: 13px; color: var(--canvas-text-muted); margin-bottom: 20px;">
        Posted by: <strong>{selectedTopic.user_name || 'Instructor'}</strong>
        {#if selectedTopic.posted_at}
          • {new Date(selectedTopic.posted_at).toLocaleString()}
        {/if}
      </div>

      <div class="wiki-content" style="border-bottom: 1px solid var(--canvas-border); padding-bottom: 20px; margin-bottom: 24px;">
        {#if selectedTopic.message_rewritten || selectedTopic.message}
          {@html selectedTopic.message_rewritten || selectedTopic.message}
        {:else}
          <em>No topic prompt text.</em>
        {/if}
      </div>

      <!-- Replies Thread -->
      <h3 style="font-size: 16px; font-weight: 600; color: var(--canvas-navy); margin-bottom: 16px;">
        Replies & Discussion
      </h3>

      {#if isLoadingThread}
        <div style="padding: 20px; text-align: center; color: var(--canvas-text-muted);">
          Loading discussion replies...
        </div>
      {:else if threadData && threadData.view && threadData.view.length > 0}
        <div style="display: flex; flex-direction: column; gap: 16px;">
          {#each threadData.view as entry}
            <div style="border: 1px solid var(--canvas-border); border-radius: 6px; padding: 16px; background: #FAFBFB;">
              <div style="font-size: 13px; font-weight: 600; color: var(--canvas-navy); margin-bottom: 6px;">
                {entry.user_name || 'Participant'}
                {#if entry.created_at}
                  <span style="font-size: 11px; font-weight: normal; color: var(--canvas-text-muted); margin-left: 8px;">
                    {new Date(entry.created_at).toLocaleString()}
                  </span>
                {/if}
              </div>
              <div class="wiki-content" style="font-size: 14px;">
                {@html entry.message || ''}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div style="padding: 20px; text-align: center; color: var(--canvas-text-muted); background: #FAFBFB; border-radius: 6px;">
          No replies in this discussion yet.
        </div>
      {/if}
    </div>
  {:else}
    <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm);">
      <div style="padding: 16px 20px; border-bottom: 1px solid var(--canvas-border); font-size: 16px; font-weight: 600;">
        Discussion Topics ({discussions.length})
      </div>

      {#if discussions.length === 0}
        <div style="padding: 40px; text-align: center; color: var(--canvas-text-muted);">
          No discussions found in this course.
        </div>
      {:else}
        {#each discussions as disc}
          <div
            class="module-item"
            onclick={() => openTopic(disc)}
            role="button"
            tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && openTopic(disc)}
            style="padding: 16px 20px;"
          >
            <span style="font-size: 18px; margin-right: 8px;">💬</span>
            <div style="flex: 1;">
              <div style="font-size: 15px; font-weight: 600; color: var(--canvas-navy);">
                {disc.title}
              </div>
              <div style="font-size: 12px; color: var(--canvas-text-muted); margin-top: 3px;">
                Posted by: {disc.user_name || 'Instructor'}
                {#if disc.posted_at}
                  • {new Date(disc.posted_at).toLocaleDateString()}
                {/if}
              </div>
            </div>
            <button class="btn btn-secondary btn-sm">Read Thread →</button>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>
