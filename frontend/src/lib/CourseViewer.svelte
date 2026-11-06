<script>
  import { onMount } from 'svelte';
  import {
    getVaultCourse,
    getVaultFrontPage,
    getVaultPages,
    getVaultPage,
    getVaultModules,
    getVaultAssignments,
    getVaultSubmissions,
    getVaultAnnouncements,
    getVaultDiscussions,
    getVaultFiles,
    openVaultFile,
  } from './api.js';

  import PageView from './PageView.svelte';
  import PagesListView from './PagesListView.svelte';
  import ModulesView from './ModulesView.svelte';
  import AssignmentsView from './AssignmentsView.svelte';
  import DiscussionsView from './DiscussionsView.svelte';
  import AnnouncementsView from './AnnouncementsView.svelte';
  import FilesView from './FilesView.svelte';
  import CanvasLinkButtons from './CanvasLinkButtons.svelte';

  let { siteId = '', courseId = 0, onBack, onTriggerSync, onDeleteCourse } = $props();

  let activeTab = $state('home'); // home, pages, modules, assignments, discussions, announcements, files, syllabus
  let courseData = $state(null);
  let frontPage = $state(null);
  let pages = $state([]);
  let currentPage = $state(null); // when viewing a specific page in pages tab or home
  let modules = $state([]);
  let assignments = $state([]);
  let submissions = $state([]);
  let announcements = $state([]);
  let discussions = $state([]);
  let files = $state([]);
  let isLoading = $state(true);

  onMount(async () => {
    await loadCourse();
  });

  async function loadCourse() {
    isLoading = true;
    try {
      courseData = await getVaultCourse(siteId, courseId);
      
      // Load front page
      try {
        frontPage = await getVaultFrontPage(siteId, courseId);
      } catch {
        frontPage = null;
      }

      // Load pages
      try {
        pages = await getVaultPages(siteId, courseId);
      } catch {
        pages = [];
      }

      // Load modules
      try {
        modules = await getVaultModules(siteId, courseId);
      } catch {
        modules = [];
      }

      // Load assignments & submissions
      try {
        assignments = await getVaultAssignments(siteId, courseId);
        submissions = await getVaultSubmissions(siteId, courseId);
      } catch {
        assignments = [];
        submissions = [];
      }

      // Load announcements
      try {
        announcements = await getVaultAnnouncements(siteId, courseId);
      } catch {
        announcements = [];
      }

      // Load discussions
      try {
        discussions = await getVaultDiscussions(siteId, courseId);
      } catch {
        discussions = [];
      }

      // Load files
      try {
        files = await getVaultFiles(siteId, courseId);
      } catch {
        files = [];
      }

    } catch (e) {
      console.error('Failed to load vault course', e);
    } finally {
      isLoading = false;
    }
  }

  async function handleHtmlFileClick(e) {
    const target = e.target.closest('a');
    if (!target) return;
    const href = target.getAttribute('href');
    if (!href) return;
    if (href.startsWith('/api/vault/files/')) {
      e.preventDefault();
      const parts = href.split('/').filter(Boolean);
      const fId = parts[parts.length - 1];
      try {
        await openVaultFile(siteId, courseId, fId);
      } catch (err) {
        window.open(href, '_blank');
      }
    }
  }

  async function selectPage(pageUrl) {
    activeTab = 'pages';
    try {
      currentPage = await getVaultPage(siteId, courseId, pageUrl);
    } catch {
      currentPage = null;
    }
  }
</script>

{#if isLoading}
  <div style="padding: 80px; text-align: center; color: var(--canvas-text-muted);">
    Loading offline course archive...
  </div>
{:else if !courseData}
  <div style="padding: 60px; text-align: center;">
    <h2>Course Archive Not Found Locally</h2>
    <p style="color: var(--canvas-text-muted); margin: 12px 0 20px;">
      This course has not been synced to your local vault yet.
    </p>
    <button class="btn btn-primary" onclick={() => onTriggerSync(courseId)}>
      Sync Course Now
    </button>
  </div>
{:else}
  <!-- Course Header Bar -->
  <div class="top-bar">
    <div class="top-bar-left">
      <button class="btn btn-secondary btn-sm" onclick={onBack}>
        ← Back
      </button>
      <div>
        <span class="top-bar-title">{courseData.meta.course_name}</span>
        {#if courseData.meta.course_code}
          <span style="font-size: 13px; color: var(--canvas-text-muted); margin-left: 8px;">
            ({courseData.meta.course_code})
          </span>
        {/if}
      </div>
    </div>

    <div class="top-bar-right">
      <span class="offline-badge">
        ✓ Local Offline Vault
      </span>
      {#if courseData.canvas_url}
        <CanvasLinkButtons url={courseData.canvas_url} label="course" />
      {/if}
      <button class="btn btn-secondary btn-sm" onclick={() => onTriggerSync(courseId)}>
        ↻ Re-sync Course
      </button>
      {#if onDeleteCourse}
        <button
          class="btn btn-danger-outline btn-sm"
          onclick={() => onDeleteCourse(courseId, courseData.meta.course_name)}
          title="Delete this local offline backup"
        >
          🗑️ Delete Backup
        </button>
      {/if}
    </div>
  </div>

  <div class="course-layout">
    <!-- Course Tabs Sidebar -->
    <div class="course-sidebar">
      <button
        type="button"
        class="course-nav-item {activeTab === 'home' ? 'active' : ''}"
        onclick={() => { activeTab = 'home'; currentPage = null; }}
      >
        <span>🏠</span> Home
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'pages' ? 'active' : ''}"
        onclick={() => { activeTab = 'pages'; }}
      >
        <span>📄</span> Pages ({pages.length})
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'modules' ? 'active' : ''}"
        onclick={() => { activeTab = 'modules'; }}
      >
        <span>📦</span> Modules ({modules.length})
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'assignments' ? 'active' : ''}"
        onclick={() => { activeTab = 'assignments'; }}
      >
        <span>📝</span> Assignments ({assignments.length})
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'discussions' ? 'active' : ''}"
        onclick={() => { activeTab = 'discussions'; }}
      >
        <span>💬</span> Discussions ({discussions.length})
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'announcements' ? 'active' : ''}"
        onclick={() => { activeTab = 'announcements'; }}
      >
        <span>📢</span> Announcements ({announcements.length})
      </button>

      <button
        type="button"
        class="course-nav-item {activeTab === 'files' ? 'active' : ''}"
        onclick={() => { activeTab = 'files'; }}
      >
        <span>📁</span> Files ({files.length})
      </button>

      {#if courseData.syllabus_rewritten}
        <button
          type="button"
          class="course-nav-item {activeTab === 'syllabus' ? 'active' : ''}"
          onclick={() => { activeTab = 'syllabus'; }}
        >
          <span>📋</span> Syllabus
        </button>
      {/if}
    </div>

    <!-- Course Tab Content -->
    <div class="course-main">
      {#if activeTab === 'home'}
        <!-- Home View: Prioritize Wiki Front Page if default_view is wiki or frontPage exists -->
        {#if frontPage && frontPage.url}
          <PageView
            page={frontPage}
            isFrontPage={true}
            {siteId}
            {courseId}
            onNavigatePage={selectPage}
          />
        {:else if courseData.meta.default_view === 'modules' && modules.length > 0}
          <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 20px;">Course Modules</h2>
          <ModulesView
            {modules}
            {siteId}
            {courseId}
            onNavigatePage={selectPage}
            onNavigateAssignment={() => { activeTab = 'assignments'; }}
            onNavigateDiscussion={() => { activeTab = 'discussions'; }}
          />
        {:else if courseData.syllabus_rewritten}
          <div class="wiki-page-container">
            <h1 class="wiki-page-title" style="margin-bottom: 20px;">Syllabus</h1>
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="wiki-content" onclick={handleHtmlFileClick}>
              {@html courseData.syllabus_rewritten}
            </div>
          </div>
        {:else}
          <div class="wiki-page-container" style="text-align: center; padding: 60px;">
            <h2>Welcome to {courseData.meta.course_name}</h2>
            <p style="color: var(--canvas-text-muted); margin-top: 8px;">
              Select a tab from the left navigation to explore pages, modules, or assignments.
            </p>
          </div>
        {/if}

      {:else if activeTab === 'pages'}
        {#if currentPage}
          <div style="margin-bottom: 16px;">
            <button class="btn btn-secondary btn-sm" onclick={() => (currentPage = null)}>
              ← Back to All Pages List
            </button>
          </div>
          <PageView
            page={currentPage}
            isFrontPage={currentPage.front_page || (frontPage && currentPage.url === frontPage.url)}
            {siteId}
            {courseId}
            onNavigatePage={selectPage}
          />
        {:else}
          <PagesListView
            {pages}
            onSelectPage={selectPage}
          />
        {/if}

      {:else if activeTab === 'modules'}
        <ModulesView
          {modules}
          {siteId}
          {courseId}
          onNavigatePage={selectPage}
          onNavigateAssignment={() => { activeTab = 'assignments'; }}
          onNavigateDiscussion={() => { activeTab = 'discussions'; }}
        />

      {:else if activeTab === 'assignments'}
        <AssignmentsView
          {assignments}
          {submissions}
        />

      {:else if activeTab === 'discussions'}
        <DiscussionsView
          {siteId}
          {courseId}
          {discussions}
        />

      {:else if activeTab === 'announcements'}
        <AnnouncementsView
          {announcements}
        />

      {:else if activeTab === 'files'}
        <FilesView
          {files}
          {siteId}
          {courseId}
        />

      {:else if activeTab === 'syllabus'}
        <div class="wiki-page-container" style="background: #fff; padding: 32px; border-radius: 8px; border: 1px solid var(--canvas-border);">
          <h1 class="wiki-page-title" style="margin-bottom: 20px;">Course Syllabus</h1>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="wiki-content" onclick={handleHtmlFileClick}>
            {@html courseData.syllabus_rewritten}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
