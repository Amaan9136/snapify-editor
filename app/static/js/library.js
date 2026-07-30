const LibraryView = (() => {
  let videos = [];

  function init() {
    const fileInput = document.getElementById('file-upload-input');
    fileInput.addEventListener('change', (e) => handleUpload(e.target.files));

    const dropzone = document.getElementById('upload-dropzone');
    ['dragenter', 'dragover'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add('is-dragover');
      });
    });
    ['dragleave', 'drop'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove('is-dragover');
      });
    });
    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
    });

    const grid = document.getElementById('library-grid');
    grid.addEventListener('dragover', (e) => e.preventDefault());
    grid.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
    });
  }

  async function handleUpload(fileList) {
    if (!fileList || !fileList.length) return;
    showToast(`Uploading ${fileList.length} file(s) to local /videos folder…`);
    try {
      const result = await Api.uploadVideos(fileList);
      if (result.saved.length) {
        showToast(`Saved: ${result.saved.join(', ')}`);
      }
      if (result.skipped.length) {
        showToast(`Skipped ${result.skipped.length} unsupported file(s)`, true);
      }
      await refresh();
    } catch (e) {
      showToast(`Upload failed: ${e.message}`, true);
    }
  }

  async function refresh() {
    const grid = document.getElementById('library-grid');
    try {
      const data = await Api.listVideos();
      videos = data.videos;
      renderGrid();
      EditorView.populateSourceOptions(videos);
    } catch (e) {
      grid.innerHTML = `<p class="empty-hint">Could not load videos: ${e.message}</p>`;
    }
  }

  function renderGrid() {
    const grid = document.getElementById('library-grid');
    if (!videos.length) {
      grid.innerHTML = `<p class="empty-hint">No videos in the local /videos folder yet. Add some above.</p>`;
      return;
    }
    grid.innerHTML = videos.map(v => `
      <div class="video-card" data-filename="${escapeHtml(v.filename)}">
        <div class="video-card-thumb" style="background-image:url('${v.thumbnail_url || ''}')">
          <button class="video-card-delete" data-action="delete" title="Delete">&times;</button>
          ${v.duration ? `<span class="video-card-duration">${formatTimecode(v.duration)}</span>` : ''}
        </div>
        <div class="video-card-body">
          <p class="video-card-name">${escapeHtml(v.filename)}</p>
          <p class="video-card-meta">${v.width || '?'}×${v.height || '?'} · ${formatBytes(v.size_bytes)}</p>
        </div>
      </div>
    `).join('');

    grid.querySelectorAll('.video-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const filename = card.dataset.filename;
        if (e.target.dataset.action === 'delete') {
          e.stopPropagation();
          confirmDelete(filename);
          return;
        }
        openInEditor(filename);
      });
    });
  }

  async function confirmDelete(filename) {
    if (!confirm(`Delete "${filename}" from the local /videos folder? This cannot be undone.`)) return;
    try {
      await Api.deleteVideo(filename);
      showToast(`Deleted ${filename}`);
      await refresh();
    } catch (e) {
      showToast(`Delete failed: ${e.message}`, true);
    }
  }

  function openInEditor(filename) {
    switchView('editor');
    EditorView.loadSource(filename);
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  return { init, refresh, get videos() { return videos; } };
})();
