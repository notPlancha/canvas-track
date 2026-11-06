<script>
  import { subscribeSync } from './api.js';

  let { open = false, siteId = '', courseId = 0, courseName = '', onClose, onSyncComplete } = $props();

  let stage = $state('init');
  let message = $state('Initializing sync...');
  let current = $state(0);
  let total = $state(0);
  let percent = $state(0);
  let logs = $state([]);
  let isDone = $state(false);
  let isError = $state(false);
  let downloadFiles = $state(true);
  let unsubscribe = null;
  let logBoxRef = $state(null);

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
    percent = 0;
    message = `Connecting sync for ${courseName || courseId}...`;

    unsubscribe = subscribeSync(
      siteId,
      courseId,
      downloadFiles,
      courseName,
      (evt) => {
        stage = evt.stage || stage;
        message = evt.message || message;
        current = evt.current || current;
        total = evt.total || total;
        if (evt.percent !== undefined) {
          percent = evt.percent;
        }

        if (evt.logs && Array.isArray(evt.logs) && logs.length === 0) {
          logs = [...evt.logs];
        } else if (evt.message) {
          const logLine = `[${evt.stage?.toUpperCase() || 'INFO'}] ${evt.message}`;
          if (logs.length === 0 || logs[logs.length - 1] !== logLine) {
            logs = [...logs, logLine];
          }
        }

        if (evt.status === 'completed' || evt.stage === 'done') {
          isDone = true;
          percent = 100;
        } else if (evt.status === 'error' || evt.stage === 'error') {
          isError = true;
        }

        // Auto-scroll log box
        setTimeout(() => {
          if (logBoxRef) {
            logBoxRef.scrollTop = logBoxRef.scrollHeight;
          }
        }, 50);
      },
      () => {
        isDone = true;
        percent = 100;
        if (!logs.some((l) => l.includes('[DONE]'))) {
          logs = [...logs, '[DONE] Sync completed successfully!'];
        }
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
    if (isDone && onSyncComplete) {
      onSyncComplete();
    }
    onClose();
  }

  const computedPercent = $derived(
    percent > 0
      ? percent
      : total > 0
      ? Math.min(100, Math.round((current / total) * 100))
      : isDone
      ? 100
      : 20
  );
</script>

{#if open}
  <div class="modal-backdrop" onclick={handleClose} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document" style="max-width: 680px;">
      <div class="modal-header">
        <div>
          <h2>Syncing Course: {courseName || courseId}</h2>
          <span style="font-size: 13px; color: var(--canvas-text-muted);">
            Site: {siteId} &bull; Course ID: {courseId}
          </span>
        </div>
        <button class="btn btn-secondary btn-sm" onclick={handleClose} title="Close window">✕</button>
      </div>

      <div class="modal-body">
        <!-- Persistent status callout -->
        <div style="background: #EEF4FC; border-left: 4px solid var(--canvas-accent-blue); padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; color: var(--canvas-navy); line-height: 1.4;">
          💡 <strong>Background Sync Enabled:</strong> You can safely click <em>"Run in Background"</em> at any time. The sync will keep running uninterrupted, and live progress will be displayed directly on your course card.
        </div>

        <div style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: 600; margin-bottom: 6px;">
            <span>
              Stage: <span style="text-transform: capitalize; color: var(--canvas-primary);">{stage}</span>
            </span>
            <span>
              {#if total > 0}
                {current} / {total} ({computedPercent}%)
              {:else}
                {computedPercent}%
              {/if}
            </span>
          </div>

          <div style="font-size: 13px; color: var(--canvas-text-muted); margin-bottom: 10px; word-break: break-word;">
            {message}
          </div>

          <!-- Progress Bar -->
          <div style="width: 100%; height: 10px; background: #E0E4E8; border-radius: 5px; overflow: hidden; position: relative;">
            <div
              style="height: 100%; background: {isError ? '#D13838' : isDone ? '#0E8642' : 'var(--canvas-accent-blue)'}; width: {computedPercent}%; transition: width 0.3s ease;"
            ></div>
          </div>
        </div>

        <div style="font-size: 12px; font-weight: 600; color: var(--canvas-navy); margin-top: 16px; margin-bottom: 6px;">
          Live Sync Log ({logs.length} events):
        </div>
        <div class="sync-log-box" bind:this={logBoxRef} style="max-height: 240px; overflow-y: auto;">
          {#each logs as log}
            <div class="sync-log-line {log.includes('[ERROR]') ? 'error' : log.includes('[DONE]') ? 'success' : ''}">
              {log}
            </div>
          {/each}
          {#if logs.length === 0}
            <div style="color: var(--canvas-text-muted); font-style: italic;">Connecting to sync stream...</div>
          {/if}
        </div>
      </div>

      <div class="modal-footer" style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 12px; color: var(--canvas-text-muted);">
          {#if !isDone && !isError}
            🔄 Sync running in background...
          {:else if isDone}
            ✅ Completed successfully!
          {:else}
            ❌ Sync stopped with error.
          {/if}
        </span>

        <div>
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
  </div>
{/if}
