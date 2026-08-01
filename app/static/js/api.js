const Api = (() => {
  async function _request(url, options = {}) {
    const res = await fetch(url, options);
    let data;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    if (!res.ok) {
      const message = (data && data.error) ? data.error : `Request failed (${res.status})`;
      const err = new Error(message);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  return {
    listVideos: () => _request('/api/videos'),
    uploadVideos: (fileList) => {
      const form = new FormData();
      for (const f of fileList) form.append('files', f);
      return _request('/api/videos/upload', { method: 'POST', body: form });
    },
    deleteVideo: (filename) => _request(`/api/videos/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
    probeVideo: (filename) => _request('/api/editor/probe', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    }),
    splitVideo: (filename, splitPoints) => _request('/api/editor/split', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, split_points: splitPoints }),
    }),
    renderVideo: (params) => _request('/api/editor/render', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
    renderBatch: (clips) => _request('/api/editor/render-batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clips }),
    }),
    uploadClipToCloudinary: (clipId) => _request('/api/editor/upload-cloudinary', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_id: clipId }),
    }),
    listClips: () => _request('/api/editor/clips'),
    deleteClip: (clipId) => _request(`/api/editor/clips/${encodeURIComponent(clipId)}`, { method: 'DELETE' }),
    generateCaption: (clipId, context, notes) => _request('/api/ollama/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_id: clipId, context, notes }),
    }),
    ollamaStatus: () => _request('/api/ollama/status'),
    youtubeStatus: () => _request('/youtube/status'),
    uploadNow: (payload) => _request('/youtube/upload-now', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
    scheduleUpload: (payload) => _request('/youtube/schedule', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
    listJobs: () => _request('/youtube/jobs'),
  };
})();
