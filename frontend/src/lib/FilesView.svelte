<script>
  import { openVaultFile } from './api.js';

  let { files = [], siteId = '', courseId = 0 } = $props();

  let searchQuery = $state('');
  let openingStatus = $state({});

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function getFileIcon(name) {
    const ext = (name || '').split('.').pop().toLowerCase();
    switch (ext) {
      case 'pdf': return '📕';
      case 'ppt':
      case 'pptx': return '📊';
      case 'doc':
      case 'docx':
      case 'txt':
      case 'md': return '📄';
      case 'zip':
      case 'tar':
      case 'gz':
      case 'rar':
      case '7z': return '🗜️';
      case 'mp4':
      case 'mkv':
      case 'webm':
      case 'avi': return '🎬';
      case 'mp3':
      case 'wav': return '🎵';
      case 'py':
      case 'ipynb':
      case 'js':
      case 'ts':
      case 'html': return '💻';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return '🖼️';
      default: return '📎';
    }
  }

  let filteredFiles = $derived(
    files.filter((f) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      const name = (f.display_name || f.filename || '').toLowerCase();
      return name.includes(q);
    })
  );

  let downloadedCount = $derived(files.filter((f) => f.is_downloaded).length);
  let totalDownloadedBytes = $derived(
    files.reduce((acc, f) => acc + (f.is_downloaded ? (f.local_size || f.size || 0) : 0), 0)
  );

  async function handleOpenFile(fileId, displayName) {
    if (!fileId) return;
    openingStatus[fileId] = 'Opening...';
    try {
      await openVaultFile(siteId, courseId, fileId);
      openingStatus[fileId] = '✓ Opened!';
      setTimeout(() => {
        delete openingStatus[fileId];
      }, 2500);
    } catch (e) {
      console.error('Failed to open file via system viewer', e);
      openingStatus[fileId] = 'Browser open...';
      window.open(`/api/vault/files/${encodeURIComponent(siteId)}/${courseId}/${fileId}`, '_blank');
      setTimeout(() => {
        delete openingStatus[fileId];
      }, 2500);
    }
  }
</script>

<div class="files-view-container">
  <div class="files-header">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div>
        <h2 style="font-size: 20px; font-weight: 700; color: var(--canvas-navy); margin: 0 0 4px;">
          Course Files ({files.length})
        </h2>
        <div style="font-size: 13px; color: var(--canvas-text-muted);">
          <span>{downloadedCount} downloaded locally ({formatBytes(totalDownloadedBytes)})</span>
        </div>
      </div>

      <div style="width: 280px;">
        <input
          type="text"
          class="form-control"
          placeholder="Filter files by name..."
          bind:value={searchQuery}
          style="padding: 8px 12px; font-size: 13px;"
        />
      </div>
    </div>
  </div>

  {#if filteredFiles.length === 0}
    <div style="text-align: center; padding: 60px; color: var(--canvas-text-muted); background: #fff; border-radius: 8px; border: 1px solid var(--canvas-border);">
      {#if searchQuery}
        No files matching "{searchQuery}".
      {:else}
        No files archived in this course.
      {/if}
    </div>
  {:else}
    <div class="files-table-container">
      <table class="files-table">
        <thead>
          <tr>
            <th style="width: 44px;"></th>
            <th>Name</th>
            <th style="width: 120px;">Size</th>
            <th style="width: 150px;">Status</th>
            <th style="width: 240px; text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredFiles as f}
            <tr>
              <td style="font-size: 20px; text-align: center; vertical-align: middle;">
                {getFileIcon(f.display_name || f.filename)}
              </td>
              <td>
                <div style="font-weight: 600; color: var(--canvas-navy); word-break: break-all;">
                  {f.display_name || f.filename || `File #${f.id}`}
                </div>
                {#if f.updated_at}
                  <div style="font-size: 11px; color: var(--canvas-text-muted); margin-top: 2px;">
                    Updated: {new Date(f.updated_at).toLocaleDateString()}
                  </div>
                {/if}
              </td>
              <td style="font-size: 13px; color: var(--canvas-text-muted);">
                {formatBytes(f.local_size || f.size)}
              </td>
              <td>
                {#if f.is_downloaded}
                  <span class="badge-downloaded">✓ Local Backup</span>
                {:else}
                  <span class="badge-cloud">☁ Cloud Only</span>
                {/if}
              </td>
              <td style="text-align: right; white-space: nowrap;">
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  onclick={() => handleOpenFile(f.id, f.display_name)}
                  title="Open in system default application"
                >
                  {openingStatus[f.id] || '📂 Open File'}
                </button>
                <a
                  href="/api/vault/files/{encodeURIComponent(siteId)}/{courseId}/{f.id}"
                  target="_blank"
                  class="btn btn-secondary btn-sm"
                  style="margin-left: 6px; text-decoration: none;"
                  title="View / Download in browser"
                >
                  Browser
                </a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .files-view-container {
    background: #fff;
    border-radius: 8px;
    border: 1px solid var(--canvas-border);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .files-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--canvas-border);
    background: #FAFBFB;
  }

  .files-table-container {
    overflow-x: auto;
  }

  .files-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .files-table th {
    text-align: left;
    padding: 12px 16px;
    border-bottom: 1px solid var(--canvas-border);
    color: var(--canvas-text-muted);
    font-weight: 600;
    font-size: 12px;
    background: #F4F6F8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .files-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #EDF2F7;
    vertical-align: middle;
  }

  .files-table tr:hover td {
    background: #F8FAFC;
  }

  .badge-downloaded {
    background: #E6F4EA;
    color: #137333;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
  }

  .badge-cloud {
    background: #F1F3F4;
    color: #5F6368;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    display: inline-block;
  }
</style>
