<script>
  import { subscribeSync } from './api.js';

  let { open = false, siteId = '', courseId = 0, courseName = '', onClose, onSyncComplete } = $props();

  let stage = $state('init');
  let message = $state('Initializing sync...');
  let current = $state(0);
  let total = $state(0);
  let logs = $state([]);
  let isDone = $state(false);
  let isError = $state(false);
  let downloadFiles = $state(true);
  let unsubscribe = null;

  $effect(() => {
    if (open && siteId && courseId) {
      startSync();
    }
    return () => {
      if (unsubscribe) {
        unsubscribe();
        unsubscribe = null;
      }
    };
  });

  function startSync() {
    isDone = false;
    isError = false;
    logs = [];
    stage = 'init';
    message = `Starting sync for ${courseName || courseId}...`;

    unsubscribe = subscribeSync(
      siteId,
      courseId,
      downloadFiles,
      (evt) => {
        stage = evt.stage || stage;
        message = evt.message || message;
        current = evt.current || current;
        total = evt.total || total;
        logs = [...logs, `[${evt.stage?.toUpperCase() || 'INFO'}] ${evt.message}`];
      },
      () => {
        isDone = true;
        logs = [...logs, '[DONE] Sync completed successfully!'];
        if (onSyncComplete) onSyncComplete();
      },
      (err) => {
        isError = true;
        logs = [...logs, `[ERROR] ${err.message || 'Sync failed.'}`];
      }
    );
  }

  function handleClose() {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
    onClose();
  }
</script>

{#if open}
  <div class="modal-backdrop" onclick={handleClose} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document" style="max-width: 650px;">
      <div class="modal-header">
        <h2>Syncing Course: {courseName || courseId}</h2>
        {#if isDone || isError}
          <button class="btn btn-secondary btn-sm" onclick={handleClose}>✕</button>
        {/if}
      </div>

      <div class="modal-body">
        <div style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: 600; margin-bottom: 6px;">
            <span>Stage: <span style="text-transform: capitalize; color: var(--canvas-primary);">{stage}</span></span>
            {#if total > 0}
              <span>{current} / {total}</span>
            {/if}
          </div>
          <div style="font-size: 13px; color: var(--canvas-text-muted); margin-bottom: 10px;">
            {message}
          </div>

          <!-- Progress Bar -->
          <div style="width: 100%; height: 8px; background: #E0E4E8; border-radius: 4px; overflow: hidden;">
            <div
              style="height: 100%; background: {isError ? '#D13838' : isDone ? '#0E8642' : 'var(--canvas-accent-blue)'}; width: {total > 0 ? Math.min(100, Math.round((current / total) * 100)) : (isDone ? 100 : 35)}%; transition: width 0.2s ease;"
            ></div>
          </div>
        </div>

        <div style="font-size: 12px; font-weight: 600; color: var(--canvas-navy); margin-top: 16px;">
          Live Sync Log:
        </div>
        <div class="sync-log-box">
          {#each logs as log}
            <div class="sync-log-line {log.includes('[ERROR]') ? 'error' : log.includes('[DONE]') ? 'success' : ''}">
              {log}
            </div>
          {/each}
        </div>
      </div>

      <div class="modal-footer">
        {#if !isDone && !isError}
          <button type="button" class="btn btn-secondary" onclick={handleClose}>
            Run in Background
          </button>
        {:else}
          <button type="button" class="btn btn-primary" onclick={handleClose}>
            Done
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}
