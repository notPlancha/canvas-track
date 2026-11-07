<script>
  import { onMount } from 'svelte';
  import {
    getSites,
    getRemoteCourses,
    getVaultCourses,
    getSyncJobs,
    deleteVaultCourse,
    deleteSite,
    syncAllCourses,
  } from './lib/api.js';

  import SiteModal from './lib/SiteModal.svelte';
  import SyncModal from './lib/SyncModal.svelte';
  import CourseViewer from './lib/CourseViewer.svelte';
  import CanvasLinkButtons from './lib/CanvasLinkButtons.svelte';

  // State
  let sites = $state([]);
  let activeSiteId = $state('');
  let courses = $state([]);
  let isLoadingCourses = $state(false);
  let courseFilter = $state('all'); // 'all' or 'synced'

  // Sync tracking
  let syncJobs = $state({});
  let toasts = $state([]);
  let pollTimer = null;
  let isSyncingAll = $state(false);

  // Deletion modals
  let deleteModalCourse = $state(null);
  let isDeleting = $state(false);
  let deleteModalSite = $state(null);
  let isDeletingSite = $state(false);

  // Current route
  let selectedCourseId = $state(null);

  // Quick Course Switcher flyout
  let isCoursesFlyoutOpen = $state(false);
  let flyoutSearchQuery = $state('');

  // Modals
  let isAddSiteOpen = $state(false);
  let siteToEdit = $state(null);
  let isSyncOpen = $state(false);
  let syncTarget = $state({ id: 0, name: '' });

  const activeSite = $derived(
    sites.find((s) => s.id === activeSiteId) || null
  );

  const filteredCourses = $derived(
    courses.filter((c) => {
      if (courseFilter === 'synced') return c.is_synced;
      return true;
    })
  );

  const flyoutFilteredCourses = $derived(
    courses.filter((c) => {
      if (!flyoutSearchQuery.trim()) return true;
      const q = flyoutSearchQuery.toLowerCase();
      return (
        (c.name && c.name.toLowerCase().includes(q)) ||
        (c.course_code && c.course_code.toLowerCase().includes(q))
      );
    })
  );

  const runningJobs = $derived(
    Object.values(syncJobs).filter((j) => j.status === 'running')
  );

  onMount(async () => {
    await loadSites();
    await checkSyncJobs();
    return () => {
      if (pollTimer) clearTimeout(pollTimer);
    };
  });

  async function loadSites() {
    try {
      sites = await getSites();
      if (sites.length > 0 && !activeSiteId) {
        activeSiteId = sites[0].id;
        await loadCourses(activeSiteId);
      } else if (sites.length === 0) {
        isAddSiteOpen = true;
      }
    } catch (e) {
      console.error('Failed to load sites', e);
    }
  }

  async function loadCourses(siteId) {
    if (!siteId) return;
    isLoadingCourses = true;
    try {
      courses = await getRemoteCourses(siteId);
    } catch {
      try {
        const archived = await getVaultCourses(siteId);
        courses = archived.map((m) => ({
          id: m.course_id,
          name: m.course_name,
          course_code: m.course_code,
          default_view: m.default_view,
          is_synced: true,
          last_synced_at: m.last_synced_at,
          total_pages: m.total_pages,
          total_modules: m.total_modules,
          total_files: m.total_files,
        }));
      } catch {
        courses = [];
      }
    } finally {
      isLoadingCourses = false;
    }
  }

  async function checkSyncJobs() {
    try {
      const jobsList = await getSyncJobs();
      const newMap = {};
      for (const j of jobsList) {
        newMap[j.job_id] = j;

        const prev = syncJobs[j.job_id];
        if (prev && prev.status === 'running' && j.status === 'completed') {
          addToast(`✅ Sync completed: ${j.course_name || `Course ${j.course_id}`}`, 'success');
          loadCourses(activeSiteId);
        } else if (prev && prev.status === 'running' && j.status === 'error') {
          addToast(`❌ Sync failed for ${j.course_name || `Course ${j.course_id}`}: ${j.error}`, 'error');
        }
      }
      syncJobs = newMap;
    } catch (e) {
      console.error('Error polling sync jobs', e);
    }

    const anyRunning = Object.values(syncJobs).some((j) => j.status === 'running');
    const intervalMs = anyRunning ? 2000 : 30000;
    pollTimer = setTimeout(checkSyncJobs, intervalMs);
  }

  function addToast(message, type = 'info') {
    const id = Date.now() + Math.random();
    toasts = [...toasts, { id, message, type }];
    setTimeout(() => {
      toasts = toasts.filter((t) => t.id !== id);
    }, 6000);
  }

  function handleSiteChange(newSiteId) {
    activeSiteId = newSiteId;
    selectedCourseId = null;
    loadCourses(newSiteId);
    checkSyncJobs();
  }

  function triggerSync(courseId, courseName) {
    syncTarget = { id: courseId, name: courseName };
    isSyncOpen = true;
    // Kick off faster polling immediately
    setTimeout(checkSyncJobs, 500);
  }

  function openCourse(courseId) {
    selectedCourseId = courseId;
  }

  function confirmDeleteBackup(course) {
    deleteModalCourse = course;
  }

  async function executeDeleteBackup() {
    if (!deleteModalCourse) return;
    isDeleting = true;
    try {
      await deleteVaultCourse(activeSiteId, deleteModalCourse.id);
      addToast(`🗑️ Deleted local backup for "${deleteModalCourse.name}"`, 'info');
      if (selectedCourseId === deleteModalCourse.id) {
        selectedCourseId = null;
      }
      deleteModalCourse = null;
      await loadCourses(activeSiteId);
    } catch (e) {
      addToast(`Failed to delete backup: ${e.message}`, 'error');
    } finally {
      isDeleting = false;
    }
  }

  function openEditSite() {
    siteToEdit = activeSite;
    isAddSiteOpen = true;
  }

  function confirmDeleteSite() {
    deleteModalSite = activeSite;
  }

  async function executeDeleteSite() {
    if (!deleteModalSite) return;
    isDeletingSite = true;
    try {
      await deleteSite(deleteModalSite.id);
      addToast(`🗑️ Removed site "${deleteModalSite.domain}" (${deleteModalSite.id})`, 'info');
      deleteModalSite = null;
      activeSiteId = '';
      await loadSites();
    } catch (e) {
      addToast(`Failed to delete site: ${e.message}`, 'error');
    } finally {
      isDeletingSite = false;
    }
  }

  async function handleSyncAll() {
    if (isSyncingAll) return;
    isSyncingAll = true;
    try {
      const res = await syncAllCourses(true);
      addToast(`⚡ Initiated sync for ${res.count} courses across all sites!`, 'success');
      setTimeout(checkSyncJobs, 500);
    } catch (e) {
      addToast(`Failed to sync all courses: ${e.message}`, 'error');
    } finally {
      isSyncingAll = false;
    }
  }
  function handleKeydown(e) {
    if (e.key === 'Escape' && isCoursesFlyoutOpen) {
      isCoursesFlyoutOpen = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="app-container">
  <!-- Global Left Navigation Strip -->
  <aside class="global-nav">
    <div
      class="global-nav-logo"
      title="Canvas Track Dashboard"
      role="button"
      tabindex="0"
      onclick={() => {
        selectedCourseId = null;
        isCoursesFlyoutOpen = false;
      }}
      onkeydown={(e) => {
        if (e.key === 'Enter') {
          selectedCourseId = null;
          isCoursesFlyoutOpen = false;
        }
      }}
      style="cursor: pointer;"
    >
      CT
    </div>

    <!-- Quick Course Switcher Button -->
    <div
      class="nav-item {isCoursesFlyoutOpen ? 'active' : ''}"
      onclick={() => (isCoursesFlyoutOpen = !isCoursesFlyoutOpen)}
      role="button"
      tabindex="0"
      onkeydown={(e) => e.key === 'Enter' && (isCoursesFlyoutOpen = !isCoursesFlyoutOpen)}
      title="Quick Course Switcher"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
      </svg>
      Courses
    </div>

    <div class="nav-divider"></div>

    <!-- Site Switcher (Each Site with Nickname and Icon) -->
    {#each sites as s (s.id)}
      <div
        class="nav-item nav-site-item {activeSiteId === s.id && !isCoursesFlyoutOpen ? 'active' : ''}"
        onclick={() => {
          handleSiteChange(s.id);
          selectedCourseId = null;
          isCoursesFlyoutOpen = false;
        }}
        role="button"
        tabindex="0"
        onkeydown={(e) => {
          if (e.key === 'Enter') {
            handleSiteChange(s.id);
            selectedCourseId = null;
            isCoursesFlyoutOpen = false;
          }
        }}
        title={`Switch to ${s.domain} (${s.user_name || s.id})`}
      >
        <div class="nav-site-icon-wrapper">
          <img
            src={`/api/sites/${encodeURIComponent(s.id)}/icon`}
            alt=""
            class="nav-site-icon"
            onerror={(e) => {
              e.currentTarget.style.display = 'none';
            }}
          />
          <span class="nav-site-monogram">
            {s.id.slice(0, 3).toUpperCase()}
          </span>
        </div>
        <span class="nav-site-label">{s.id}</span>
      </div>
    {/each}

    <!-- Add Site Button -->
    <div
      class="nav-item"
      style="height: 48px; margin-top: 4px;"
      onclick={() => {
        siteToEdit = null;
        isAddSiteOpen = true;
        isCoursesFlyoutOpen = false;
      }}
      role="button"
      tabindex="0"
      onkeydown={(e) => {
        if (e.key === 'Enter') {
          siteToEdit = null;
          isAddSiteOpen = true;
          isCoursesFlyoutOpen = false;
        }
      }}
      title="Add Another Canvas Site"
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="16"></line>
        <line x1="8" y1="12" x2="16" y2="12"></line>
      </svg>
      <span style="font-size: 10px; margin-top: 2px;">+ Site</span>
    </div>
  </aside>

  <!-- Non-Sticky Quick Courses Flyout Drawer -->
  {#if isCoursesFlyoutOpen}
    <div
      class="flyout-backdrop"
      onclick={() => (isCoursesFlyoutOpen = false)}
      role="presentation"
    ></div>

    <div
      class="course-flyout-pane"
      role="dialog"
      aria-modal="true"
      aria-label="Courses Switcher"
    >
      <div class="flyout-header">
        <h3 class="flyout-title">
          <span>📚</span> Quick Courses
          {#if activeSite}
            <span style="font-size: 12px; font-weight: normal; color: var(--canvas-text-muted);">
              ({activeSite.id})
            </span>
          {/if}
        </h3>
        <button
          type="button"
          class="btn btn-secondary btn-sm"
          style="padding: 2px 8px; font-size: 12px;"
          onclick={() => (isCoursesFlyoutOpen = false)}
        >
          ✕
        </button>
      </div>

      <div class="flyout-search">
        <input
          class="form-input"
          type="text"
          bind:value={flyoutSearchQuery}
          placeholder="Filter courses..."
          style="padding: 6px 10px; font-size: 13px;"
        />
      </div>

      <div class="flyout-courses-list">
        {#if isLoadingCourses}
          <div style="padding: 24px; text-align: center; color: var(--canvas-text-muted); font-size: 13px;">
            Loading courses...
          </div>
        {:else if flyoutFilteredCourses.length === 0}
          <div style="padding: 24px; text-align: center; color: var(--canvas-text-muted); font-size: 13px;">
            No courses found.
          </div>
        {:else}
          {#each flyoutFilteredCourses as c (c.id)}
            <div
              class="flyout-course-item {selectedCourseId === c.id ? 'active' : ''}"
              onclick={() => {
                openCourse(c.id);
                isCoursesFlyoutOpen = false;
              }}
              role="button"
              tabindex="0"
              onkeydown={(e) => {
                if (e.key === 'Enter') {
                  openCourse(c.id);
                  isCoursesFlyoutOpen = false;
                }
              }}
            >
              <div class="flyout-course-name">{c.name}</div>
              <div class="flyout-course-meta">
                <span>{c.course_code || `ID: ${c.id}`}</span>
                {#if c.is_synced}
                  <span style="color: #137333; font-weight: 600;">✓ Synced</span>
                {:else}
                  <span style="color: #B06000;">☁️ Available</span>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div style="padding: 12px 16px; border-top: 1px solid var(--canvas-border); background: #F8FAFC;">
        <button
          type="button"
          class="btn btn-secondary btn-sm"
          style="width: 100%; justify-content: center;"
          onclick={() => {
            selectedCourseId = null;
            isCoursesFlyoutOpen = false;
          }}
        >
          📊 Go to Dashboard
        </button>
      </div>
    </div>
  {/if}

  <!-- Main View Area -->
  <div class="main-wrapper">
    {#if selectedCourseId}
      <CourseViewer
        siteId={activeSiteId}
        courseId={selectedCourseId}
        onBack={() => (selectedCourseId = null)}
        onTriggerSync={(cId) => {
          const c = courses.find((x) => x.id === cId);
          triggerSync(cId, c ? c.name : '');
        }}
        onDeleteCourse={(cId, cName) => {
          confirmDeleteBackup({ id: cId, name: cName });
        }}
      />
    {:else}
      <!-- Top Bar -->
      <header class="top-bar">
        <div class="top-bar-left">
          <span class="top-bar-title">Dashboard</span>

          {#if sites.length > 0}
            <div style="display: flex; align-items: center; gap: 8px;">
              <select
                class="form-input"
                style="width: auto; padding: 6px 12px; font-size: 13px;"
                value={activeSiteId}
                onchange={(e) => handleSiteChange(e.target.value)}
              >
                {#each sites as s}
                  <option value={s.id}>{s.domain} ({s.user_name || s.id})</option>
                {/each}
              </select>

              {#if activeSite}
                <button
                  type="button"
                  class="btn btn-secondary btn-sm"
                  style="padding: 5px 8px; font-size: 12px;"
                  onclick={openEditSite}
                  title="Edit site details, domain, or access token"
                >
                  ✏️
                </button>
                <button
                  type="button"
                  class="btn btn-secondary btn-sm"
                  style="padding: 5px 8px; font-size: 12px; color: #C53030;"
                  onclick={confirmDeleteSite}
                  title="Remove site registration"
                >
                  🗑️
                </button>
              {/if}
            </div>
          {/if}

          <!-- Background Sync Indicator in Header -->
          {#if runningJobs.length > 0}
            <button
              class="top-bar-sync-status"
              onclick={() => triggerSync(runningJobs[0].course_id, runningJobs[0].course_name)}
              title="Click to view live sync log"
            >
              <span class="sync-pulse-dot"></span>
              <span>Syncing {runningJobs.length} {runningJobs.length === 1 ? 'course' : 'courses'} in background...</span>
            </button>
          {/if}
        </div>

        <div class="top-bar-right" style="display: flex; align-items: center; gap: 10px;">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            style="background: #2B6CB0; border-color: #2B6CB0; font-weight: 600;"
            onclick={handleSyncAll}
            disabled={isSyncingAll}
            title="Sync all courses across all registered Canvas sites"
          >
            {#if isSyncingAll}
              ⏳ Enqueuing All...
            {:else}
              ⚡ Sync All Sites
            {/if}
          </button>

          {#if activeSite}
            <span style="font-size: 13px; color: var(--canvas-text-muted);">
              👤 <strong>{activeSite.user_name || 'User'}</strong>
            </span>
          {/if}
        </div>
      </header>

      <!-- Content Body: Courses Grid -->
      <main class="content-body">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
          <div>
            <h1 style="font-size: 22px; font-weight: 700; color: var(--canvas-navy);">
              {activeSite ? `${activeSite.domain} (${activeSite.platform === 'moodle' ? 'Moodle' : 'Canvas'}) Courses` : 'Your Courses'}
            </h1>
            <p style="font-size: 13px; color: var(--canvas-text-muted);">
              Select a course to read offline or trigger an incremental sync.
            </p>
          </div>

          <!-- Filter Pills -->
          <div style="display: flex; gap: 8px; background: #E0E4E8; padding: 4px; border-radius: 8px;">
            <button
              class="btn btn-sm {courseFilter === 'all' ? 'btn-primary' : ''}"
              onclick={() => (courseFilter = 'all')}
            >
              All Courses ({courses.length})
            </button>
            <button
              class="btn btn-sm {courseFilter === 'synced' ? 'btn-primary' : ''}"
              onclick={() => (courseFilter = 'synced')}
            >
              Synced Locally ({courses.filter((c) => c.is_synced).length})
            </button>
          </div>
        </div>

        {#if isLoadingCourses}
          <div style="padding: 80px; text-align: center; color: var(--canvas-text-muted);">
            Connecting to Canvas and checking offline vault...
          </div>
        {:else if filteredCourses.length === 0}
          <div style="padding: 80px; text-align: center; background: #fff; border-radius: 8px; border: 1px solid var(--canvas-border);">
            <h3>No courses found.</h3>
            <p style="color: var(--canvas-text-muted); margin: 8px 0 16px;">
              {#if courseFilter === 'synced'}
                You haven't synced any courses yet. Switch to "All Courses" and click "Sync to Vault".
              {:else}
                Make sure your Personal Access Token has permissions to access your courses.
              {/if}
            </p>
            {#if courseFilter === 'synced'}
              <button class="btn btn-secondary btn-sm" onclick={() => (courseFilter = 'all')}>
                Show All Courses
              </button>
            {/if}
          </div>
        {:else}
          <div class="card-grid">
            {#each filteredCourses as course}
              {@const jobKey = `${activeSiteId}:${course.id}`}
              {@const job = syncJobs[jobKey]}
              {@const isSyncing = job && job.status === 'running'}

              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
              <div
                class="course-card {course.is_synced ? 'clickable' : ''}"
                onclick={() => {
                  if (course.is_synced) openCourse(course.id);
                }}
                role={course.is_synced ? "button" : undefined}
                tabindex={course.is_synced ? 0 : undefined}
                onkeydown={(e) => {
                  if (course.is_synced && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    openCourse(course.id);
                  }
                }}
              >
                <div class="course-card-header">
                  <h3>{course.name}</h3>
                  <div class="course-card-code">{course.course_code || `Course ID: ${course.id}`}</div>
                </div>

                <div class="course-card-body">
                  {#if isSyncing}
                    <!-- Live Background Syncing Indicator on Course Card -->
                    <div class="card-syncing-banner" onclick={(e) => e.stopPropagation()}>
                      <div class="syncing-header">
                        <span class="sync-spinner"></span>
                        <span class="sync-stage-text">Syncing: <strong style="text-transform: capitalize;">{job.stage}</strong></span>
                        <span class="sync-pct-text">{job.percent}%</span>
                      </div>
                      <div class="sync-progress-bar-mini">
                        <div class="sync-progress-fill-mini" style="width: {job.percent}%;"></div>
                      </div>
                      <div class="sync-msg-mini" title={job.message}>{job.message}</div>
                      <div class="course-card-footer" style="padding-top: 8px;">
                        <button
                          class="btn btn-secondary btn-sm"
                          style="width: 100%; justify-content: center;"
                          onclick={(e) => {
                            e.stopPropagation();
                            triggerSync(course.id, course.name);
                          }}
                        >
                          👁️ View Live Progress
                        </button>
                      </div>
                    </div>
                  {:else}
                    <div class="course-card-stats">
                      {#if course.is_synced}
                        <span class="stat-pill" style="color: #137333; background: #E6F4EA;">
                          ✓ Synced: {new Date(course.last_synced_at).toLocaleDateString()}
                        </span>
                      {:else}
                        <span class="stat-pill" style="color: #B06000; background: #FEF7E0;">
                          ☁️ Available on Canvas (Not Synced)
                        </span>
                      {/if}
                    </div>

                    <div class="course-card-footer">
                      <div style="display: flex; gap: 8px; align-items: center;">
                        {#if !course.is_synced}
                          <button
                            class="btn btn-primary btn-sm"
                            onclick={(e) => {
                              e.stopPropagation();
                              triggerSync(course.id, course.name);
                            }}
                          >
                            ⬇️ Sync to Vault
                          </button>
                        {/if}

                        {#if activeSite}
                          <div onclick={(e) => e.stopPropagation()}>
                            <CanvasLinkButtons
                              url={activeSite.platform === 'moodle'
                                ? `https://${activeSite.domain}/course/view.php?id=${course.id}`
                                : `https://${activeSite.domain}/courses/${course.id}`}
                              label="course"
                            />
                          </div>
                        {/if}
                      </div>

                      {#if course.is_synced}
                        <div style="display: flex; gap: 6px; align-items: center;">
                          <button
                            class="btn btn-secondary btn-sm"
                            onclick={(e) => {
                              e.stopPropagation();
                              triggerSync(course.id, course.name);
                            }}
                            title="Re-sync updates"
                          >
                            ↻ Sync
                          </button>
                          <button
                            class="btn btn-secondary btn-sm btn-icon-danger"
                            onclick={(e) => {
                              e.stopPropagation();
                              confirmDeleteBackup(course);
                            }}
                            title="Delete local backup"
                          >
                            🗑️
                          </button>
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </main>
    {/if}
  </div>
</div>

<!-- Add/Edit Site Modal -->
<SiteModal
  open={isAddSiteOpen}
  siteToEdit={siteToEdit}
  onClose={() => {
    isAddSiteOpen = false;
    siteToEdit = null;
  }}
  onSiteAdded={(site) => {
    loadSites();
    activeSiteId = site.id;
    loadCourses(site.id);
    addToast(`Connected Canvas site: ${site.domain}!`, 'success');
  }}
  onSiteUpdated={(site) => {
    loadSites();
    activeSiteId = site.id;
    loadCourses(site.id);
    addToast(`Updated site: ${site.domain}!`, 'success');
  }}
/>

<!-- Sync Modal -->
<SyncModal
  open={isSyncOpen}
  siteId={activeSiteId}
  courseId={syncTarget.id}
  courseName={syncTarget.name}
  onClose={() => {
    isSyncOpen = false;
    checkSyncJobs();
  }}
  onSyncComplete={() => {
    loadCourses(activeSiteId);
    checkSyncJobs();
  }}
/>

<!-- Delete Course Backup Modal -->
{#if deleteModalCourse}
  <div
    class="modal-backdrop"
    onclick={() => (deleteModalCourse = null)}
    onkeydown={(e) => e.key === 'Escape' && (deleteModalCourse = null)}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document" style="max-width: 480px;">
      <div class="modal-header">
        <h2 style="color: #C53030;">Delete Local Backup?</h2>
        <button class="btn btn-secondary btn-sm" onclick={() => (deleteModalCourse = null)}>✕</button>
      </div>

      <div class="modal-body">
        <p style="font-size: 14px; color: var(--canvas-navy); margin-bottom: 12px;">
          Are you sure you want to permanently delete the offline vault backup for <strong>{deleteModalCourse.name}</strong>?
        </p>

        <div style="background: #FFF5F5; border: 1px solid #FEB2B2; border-radius: 6px; padding: 12px; font-size: 13px; color: #9B2C2C; margin-bottom: 16px;">
          ⚠️ <strong>What happens:</strong>
          <ul style="margin: 6px 0 0 18px; line-height: 1.5;">
            <li>All downloaded files, HTML pages, modules, and JSON data will be deleted from your disk.</li>
            <li>Your online Canvas account is <strong>completely unaffected</strong>.</li>
            <li>You can re-sync this course anytime from Canvas.</li>
          </ul>
        </div>
      </div>

      <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 10px;">
        <button type="button" class="btn btn-secondary" onclick={() => (deleteModalCourse = null)} disabled={isDeleting}>
          Cancel
        </button>
        <button type="button" class="btn btn-danger" onclick={executeDeleteBackup} disabled={isDeleting}>
          {isDeleting ? 'Deleting...' : 'Delete Backup'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Site Registration Modal -->
{#if deleteModalSite}
  <div
    class="modal-backdrop"
    onclick={() => (deleteModalSite = null)}
    onkeydown={(e) => e.key === 'Escape' && (deleteModalSite = null)}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="document" style="max-width: 480px;">
      <div class="modal-header">
        <h2 style="color: #C53030;">Remove Canvas Site?</h2>
        <button class="btn btn-secondary btn-sm" onclick={() => (deleteModalSite = null)}>✕</button>
      </div>

      <div class="modal-body">
        <p style="font-size: 14px; color: var(--canvas-navy); margin-bottom: 12px;">
          Are you sure you want to remove the registered site <strong>{deleteModalSite.domain}</strong> ({deleteModalSite.id})?
        </p>

        <div style="background: #FFF5F5; border: 1px solid #FEB2B2; border-radius: 6px; padding: 12px; font-size: 13px; color: #9B2C2C; margin-bottom: 16px;">
          ⚠️ <strong>What happens:</strong>
          <p style="margin: 6px 0 0 0; line-height: 1.5;">
            This removes the site's access token from your local configuration. Any downloaded courses on disk will remain safe. Your remote Canvas account is completely unaffected.
          </p>
        </div>
      </div>

      <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 10px;">
        <button type="button" class="btn btn-secondary" onclick={() => (deleteModalSite = null)} disabled={isDeletingSite}>
          Cancel
        </button>
        <button type="button" class="btn btn-danger" onclick={executeDeleteSite} disabled={isDeletingSite}>
          {isDeletingSite ? 'Removing...' : 'Remove Site'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Toast Notifications -->
<div class="toast-container">
  {#each toasts as t (t.id)}
    <div class="toast-item {t.type}">
      <span>{t.message}</span>
    </div>
  {/each}
</div>
