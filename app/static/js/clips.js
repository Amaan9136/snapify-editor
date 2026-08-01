const ClipsView = (() => {
  let clips = [];

  function init() {
    document.getElementById('btn-refresh-clips').addEventListener('click', refresh);
  }

  async function refresh() {
    const grid = document.getElementById('clips-grid');
    try {
      const data = await Api.listClips();
      clips = data.clips;
      render();
    } catch (e) {
      grid.innerHTML = `<p class="empty-hint">Could not load clips: ${e.message}</p>`;
    }
  }

  function render() {
    const grid = document.getElementById('clips-grid');
    if (!clips.length) {
      grid.innerHTML = `<p class="empty-hint">No rendered clips yet. Go to the Editor tab and render your first reel.</p>`;
      return;
    }
    grid.innerHTML = clips.map(c => `
      <div class="clip-card" data-clip-id="${c._id}">
        <video src="${c.preview_url}" muted preload="metadata"></video>
        <button class="video-card-delete" data-action="delete" title="Delete">&times;</button>
        <div class="clip-card-body">
          <span class="clip-card-status" data-status="${c.status}">${statusLabel(c.status)}</span>
          <p class="clip-card-title">${escapeHtml(c.title || c.filename)}</p>
          <p class="clip-card-meta">${c.ratio} · ${c.width}×${c.height} · ${c.duration ? c.duration.toFixed(1) + 's' : ''}</p>
          <div class="clip-card-actions">
            <button class="btn btn-ghost btn-sm" data-action="cloudinary" ${c.status !== 'rendered' ? 'disabled' : ''}>
              ${c.status === 'rendered' ? 'Push to Cloudinary' : (c.cloudinary_url ? 'On Cloudinary ✓' : '')}
            </button>
            <button class="btn btn-primary btn-sm" data-action="publish">Publish to YouTube</button>
          </div>
        </div>
      </div>
    `).join('');

    grid.querySelectorAll('.clip-card').forEach(card => {
      const clipId = card.dataset.clipId;
      const clip = clips.find(c => c._id === clipId);
      card.querySelector('[data-action="cloudinary"]')?.addEventListener('click', () => pushToCloudinary(clipId, card));
      card.querySelector('[data-action="publish"]')?.addEventListener('click', () => PublishView.openModal(clip));
      card.querySelector('[data-action="delete"]')?.addEventListener('click', () => confirmDelete(clipId, clip));
    });
  }

  function statusLabel(status) {
    return {
      rendered: 'Rendered (local only)',
      uploaded_cloudinary: 'On Cloudinary',
      published_youtube: 'Published to YouTube',
    }[status] || status;
  }

  async function pushToCloudinary(clipId, cardEl) {
    const btn = cardEl.querySelector('[data-action="cloudinary"]');
    btn.disabled = true;
    btn.textContent = 'Uploading…';
    try {
      const result = await Api.uploadClipToCloudinary(clipId);
      showToast(`Uploaded to Cloudinary: ${result.cloudinary_public_id}`);
      await refresh();
    } catch (e) {
      showToast(`Cloudinary upload failed: ${e.message}`, true);
      btn.disabled = false;
      btn.textContent = 'Push to Cloudinary';
    }
  }

  async function confirmDelete(clipId, clip) {
    const label = clip?.title || clip?.filename || clipId;
    if (!confirm(`Delete "${label}"? This removes the rendered file locally and from Cloudinary if uploaded. This cannot be undone.`)) return;
    try {
      const result = await Api.deleteClip(clipId);
      showToast(result.cloudinary_warning || `Deleted ${label}`, !!result.cloudinary_warning);
      await refresh();
    } catch (e) {
      showToast(`Delete failed: ${e.message}`, true);
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  return { init, refresh };
})();
