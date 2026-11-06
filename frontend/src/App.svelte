<script>
  import { onMount } from 'svelte';
  import { getSites, getRemoteCourses, getVaultCourses } from './lib/api.js';

  import SiteModal from './lib/SiteModal.svelte';
  import SyncModal from './lib/SyncModal.svelte';
  import CourseViewer from './lib/CourseViewer.svelte';

  // State
  let sites = $state([]);
  let activeSiteId = $state('');
  let courses = $state([]);
  let isLoadingCourses = $state(false);
  let courseFilter = $state('all'); // 'all' or 'synced'

  // Current route
  let selectedCourseId = $state(null);

  // Modals
  let isAddSiteOpen = $state(false);
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

  onMount(async () => {
    await loadSites();
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
      // First try to load remote courses which includes sync status
      courses = await getRemoteCourses(siteId);
    } catch {
      // If remote fails (offline mode), fallback to vault-only archived courses
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

  function handleSiteChange(newSiteId) {
    activeSiteId = newSiteId;
    selectedCourseId = null;
    loadCourses(newSiteId);
  }

  function triggerSync(courseId, courseName) {
    syncTarget = { id: courseId, name: courseName };
    isSyncOpen = true;
  }

  function openCourse(courseId) {
    selectedCourseId = courseId;
  }
</script>

<div class="app-container">
  <!-- Global Left Navigation Strip -->
  <aside class="global-nav">
    <div class="global-nav-logo" title="Canvas Track">
      CT
    </div>

    <div
      class="nav-item {!selectedCourseId ? 'active' : ''}"
      onclick={() => (selectedCourseId = null)}
      role="button"
      tabindex="0"
      onkeydown={(e) => e.key === 'Enter' && (selectedCourseId = null)}
      title="Courses Dashboard"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
      </svg>
      Courses
    </div>

    <div
      class="nav-item"
      onclick={() => (isAddSiteOpen = true)}
      role="button"
      tabindex="0"
      onkeydown={(e) => e.key === 'Enter' && (isAddSiteOpen = true)}
      title="Add Canvas Site"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="16"></line>
        <line x1="8" y1="12" x2="16" y2="12"></line>
      </svg>
      Add Site
    </div>
  </aside>

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
      />
    {:else}
      <!-- Top Bar -->
      <header class="top-bar">
        <div class="top-bar-left">
          <span class="top-bar-title">Dashboard</span>

          {#if sites.length > 0}
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
          {/if}
        </div>

        <div class="top-bar-right">
          {#if activeSite}
            <span style="font-size: 13px; color: var(--canvas-text-muted);">
              👤 <strong>{activeSite.user_name || 'User'}</strong>
            </span>
          {/if}
          <button class="btn btn-secondary btn-sm" onclick={() => (isAddSiteOpen = true)}>
            + Add Another Site
          </button>
        </div>
      </header>

      <!-- Content Body: Courses Grid -->
      <main class="content-body">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
          <div>
            <h1 style="font-size: 22px; font-weight: 700; color: var(--canvas-navy);">
              {activeSite ? `${activeSite.domain} Courses` : 'Your Courses'}
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
              <div class="course-card">
                <div class="course-card-header">
                  <h3>{course.name}</h3>
                  <div class="course-card-code">{course.course_code || `Course ID: ${course.id}`}</div>
                </div>

                <div class="course-card-body">
                  <div class="course-card-stats">
                    {#if course.is_synced}
                      <span class="stat-pill" style="color: #137333; background: #E6F4EA;">
                        ✓ Synced: {new Date(course.last_synced_at).toLocaleDateString()}
                      </span>
                      <span class="stat-pill">📄 {course.total_pages} Pages</span>
                      <span class="stat-pill">📦 {course.total_modules} Modules</span>
                    {:else}
                      <span class="stat-pill" style="color: #B06000; background: #FEF7E0;">
                        ☁️ Available on Canvas (Not Synced)
                      </span>
                    {/if}
                  </div>

                  <div class="course-card-footer">
                    {#if course.is_synced}
                      <button
                        class="btn btn-primary btn-sm"
                        onclick={() => openCourse(course.id)}
                      >
                        📖 Read Offline
                      </button>
                    {:else}
                      <button
                        class="btn btn-secondary btn-sm"
                        onclick={() => triggerSync(course.id, course.name)}
                      >
                        ⬇️ Sync to Vault
                      </button>
                    {/if}

                    {#if course.is_synced}
                      <button
                        class="btn btn-secondary btn-sm"
                        onclick={() => triggerSync(course.id, course.name)}
                        title="Re-sync updates"
                      >
                        ↻ Sync
                      </button>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </main>
    {/if}
  </div>
</div>

<!-- Add Site Modal -->
<SiteModal
  open={isAddSiteOpen}
  onClose={() => (isAddSiteOpen = false)}
  onSiteAdded={(site) => {
    sites = [...sites, site];
    activeSiteId = site.id;
    loadCourses(site.id);
  }}
/>

<!-- Sync Modal -->
<SyncModal
  open={isSyncOpen}
  siteId={activeSiteId}
  courseId={syncTarget.id}
  courseName={syncTarget.name}
  onClose={() => (isSyncOpen = false)}
  onSyncComplete={() => {
    loadCourses(activeSiteId);
  }}
/>
