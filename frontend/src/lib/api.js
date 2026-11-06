// API client for Canvas Track FastAPI backend

const BASE_URL = '';

export async function fetchJson(endpoint, options = {}) {
  const resp = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!resp.ok) {
    let errorDetail = resp.statusText;
    try {
      const err = await resp.json();
      errorDetail = err.detail || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return resp.json();
}

export async function getSites() {
  return fetchJson('/api/sites');
}

export async function addSite(domain, token, siteId = null) {
  return fetchJson('/api/sites', {
    method: 'POST',
    body: JSON.stringify({ domain, token, site_id: siteId }),
  });
}

export async function updateSite(siteId, domain, token, newSiteId = null) {
  return fetchJson(`/api/sites/${encodeURIComponent(siteId)}`, {
    method: 'PUT',
    body: JSON.stringify({ domain, token, site_id: newSiteId }),
  });
}

export async function deduplicateSites() {
  return fetchJson('/api/sites/deduplicate', {
    method: 'POST',
  });
}

export async function deleteSite(siteId) {
  return fetchJson(`/api/sites/${encodeURIComponent(siteId)}`, {
    method: 'DELETE',
  });
}

export async function getRemoteCourses(siteId) {
  return fetchJson(`/api/sites/${encodeURIComponent(siteId)}/courses`);
}

export async function getVaultCourses(siteId) {
  return fetchJson(`/api/vault/sites/${encodeURIComponent(siteId)}/courses`);
}

export async function getVaultCourse(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}`);
}

export async function deleteVaultCourse(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}`, {
    method: 'DELETE',
  });
}

export async function getVaultFrontPage(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/front_page`);
}

export async function getVaultPages(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/pages`);
}

export async function getVaultPage(siteId, courseId, pageUrl) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/pages/${encodeURIComponent(pageUrl)}`);
}

export async function getVaultModules(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/modules`);
}

export async function getVaultAssignments(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/assignments`);
}

export async function getVaultSubmissions(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/submissions`);
}

export async function getVaultAnnouncements(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/announcements`);
}

export async function getVaultDiscussions(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/discussions`);
}

export async function getVaultDiscussionThread(siteId, courseId, topicId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/discussions/${topicId}`);
}

export async function getVaultFiles(siteId, courseId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/files`);
}

export async function openVaultFile(siteId, courseId, fileId) {
  return fetchJson(`/api/vault/files/${encodeURIComponent(siteId)}/${courseId}/${fileId}/open`, {
    method: 'POST',
  });
}

export async function getSyncJobs(siteId = null) {
  const url = siteId ? `/api/sync/jobs?site_id=${encodeURIComponent(siteId)}` : '/api/sync/jobs';
  return fetchJson(url);
}

export async function getCourseSyncStatus(siteId, courseId) {
  return fetchJson(`/api/sites/${encodeURIComponent(siteId)}/courses/${courseId}/sync/status`);
}

export async function triggerCourseSync(siteId, courseId, downloadFiles = true, courseName = '') {
  const params = new URLSearchParams({
    download_files: String(downloadFiles),
    course_name: courseName || '',
  });
  return fetchJson(`/api/sites/${encodeURIComponent(siteId)}/courses/${courseId}/sync?${params.toString()}`, {
    method: 'POST',
  });
}

export async function syncAllCourses(downloadFiles = true) {
  const params = new URLSearchParams({
    download_files: String(downloadFiles),
  });
  return fetchJson(`/api/sync/all?${params.toString()}`, {
    method: 'POST',
  });
}

export async function getPageComments(siteId, courseId, pageUrl) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/pages/${encodeURIComponent(pageUrl)}/comments`);
}

export async function addPageComment(siteId, courseId, pageUrl, text) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/pages/${encodeURIComponent(pageUrl)}/comments`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function deletePageComment(siteId, courseId, pageUrl, commentId) {
  return fetchJson(`/api/vault/courses/${encodeURIComponent(siteId)}/${courseId}/pages/${encodeURIComponent(pageUrl)}/comments/${encodeURIComponent(commentId)}`, {
    method: 'DELETE',
  });
}

export function subscribeSync(siteId, courseId, downloadFiles = true, courseName = '', onEvent = () => {}, onDone = () => {}, onError = () => {}) {
  const params = new URLSearchParams({
    download_files: String(downloadFiles),
    course_name: courseName || '',
  });
  const url = `${BASE_URL}/api/sites/${encodeURIComponent(siteId)}/courses/${courseId}/sync?${params.toString()}`;
  const es = new EventSource(url);

  es.onmessage = (event) => {
    if (event.data === '[DONE]') {
      es.close();
      onDone();
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.stage === 'error' || data.status === 'error') {
        es.close();
        onError(new Error(data.message || data.error || 'Sync failed.'));
        return;
      }
      onEvent(data);
      if (data.status === 'completed' || data.stage === 'done') {
        onDone();
      }
    } catch (e) {
      console.error('Error parsing SSE event', e);
    }
  };

  es.onerror = (err) => {
    es.close();
    onError(err);
  };

  return () => es.close();
}
