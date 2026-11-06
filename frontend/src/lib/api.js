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

export function subscribeSync(siteId, courseId, downloadFiles, onEvent, onDone, onError) {
  const url = `${BASE_URL}/api/sites/${encodeURIComponent(siteId)}/courses/${courseId}/sync?download_files=${downloadFiles}`;
  const es = new EventSource(url);

  es.onmessage = (event) => {
    if (event.data === '[DONE]') {
      es.close();
      onDone();
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.stage === 'error') {
        es.close();
        onError(new Error(data.message));
        return;
      }
      onEvent(data);
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
