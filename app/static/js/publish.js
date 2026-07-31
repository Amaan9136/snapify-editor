const PublishView = (() => {
  let activeClip = null;
  let publishMode = 'now';

  function init() {
    document.getElementById('btn-close-publish-modal').addEventListener('click', closeModal);
    document.getElementById('btn-cancel-publish').addEventListener('click', closeModal);
    document.getElementById('publish-modal-backdrop').addEventListener('click', (e) => {
      if (e.target.id === 'publish-modal-backdrop') closeModal();
    });

    document.getElementById('btn-generate-caption').addEventListener('click', generateCaption);
    document.getElementById('btn-confirm-publish').addEventListener('click', confirmPublish);

    document.querySelectorAll('.publish-mode-toggle .toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        publishMode = btn.dataset.mode;
        document.querySelectorAll('.publish-mode-toggle .toggle-btn').forEach(b => b.classList.toggle('is-active', b === btn));
        document.getElementById('schedule-datetime-row').classList.toggle('hidden', publishMode !== 'schedule');
      });
    });

    document.getElementById('btn-refresh-jobs').addEventListener('click', refreshJobs);
  }

  function openModal(clip) {
    activeClip = clip;
    document.getElementById('publish-modal-preview').src = clip.preview_url;
    document.getElementById('publish-title-field').value = clip.title || '';
    document.getElementById('publish-description-field').value = '';
    document.getElementById('publish-hashtags-field').value = '';
    document.getElementById('publish-privacy-field').value = 'private';
    publishMode = 'now';
    document.querySelectorAll('.publish-mode-toggle .toggle-btn').forEach(b => b.classList.toggle('is-active', b.dataset.mode === 'now'));
    document.getElementById('schedule-datetime-row').classList.add('hidden');

    const dt = new Date(Date.now() + 60 * 60 * 1000);
    document.getElementById('schedule-datetime-field').value = dt.toISOString().slice(0, 16);

    document.getElementById('publish-modal-backdrop').classList.remove('hidden');
  }

  function closeModal() {
    document.getElementById('publish-modal-backdrop').classList.add('hidden');
    document.getElementById('publish-modal-preview').pause();
    activeClip = null;
  }

  async function generateCaption() {
    if (!activeClip) return;
    const btn = document.getElementById('btn-generate-caption');
    btn.disabled = true;
    btn.textContent = '✨ Generating with Ollama…';
    try {
      const context = `Clip Details:
Title: ${document.getElementById('publish-title-field').value.trim() || 'None'}
Description: ${document.getElementById('publish-description-field').value.trim() || 'None'}
Hashtags: ${document.getElementById('publish-hashtags-field').value.trim() || 'None'}

Use the clip details and current inputs to generate an improved, engaging YouTube title, description, and hashtags.`;
      const result = await Api.generateCaption(activeClip._id, context, null);
      document.getElementById('publish-title-field').value = result.title;
      document.getElementById('publish-description-field').value = result.description;
      document.getElementById('publish-hashtags-field').value = result.hashtags.join(' ');
      showToast('Caption generated with Ollama.');
    } catch (e) {
      showToast(`Ollama generation failed: ${e.message}`, true);
    } finally {
      btn.disabled = false;
      btn.textContent = '✨ Generate title/description/hashtags with Ollama';
    }
  }

  async function confirmPublish() {
    if (!activeClip) return;
    const btn = document.getElementById('btn-confirm-publish');
    const title = document.getElementById('publish-title-field').value.trim();
    const description = document.getElementById('publish-description-field').value.trim();
    const hashtags = document.getElementById('publish-hashtags-field').value.trim().split(/\s+/).filter(Boolean);
    const privacyStatus = document.getElementById('publish-privacy-field').value;

    if (!title) {
      showToast('Title is required.', true);
      return;
    }

    btn.disabled = true;
    btn.textContent = publishMode === 'now' ? 'Publishing…' : 'Scheduling…';

    try {
      if (publishMode === 'now') {
        const result = await Api.uploadNow({
          clip_id: activeClip._id, title, description, hashtags, privacy_status: privacyStatus,
        });
        showToast(`Published! ${result.url}`);
      } else {
        const localDt = document.getElementById('schedule-datetime-field').value;
        if (!localDt) {
          showToast('Pick a date/time to schedule.', true);
          btn.disabled = false;
          btn.textContent = 'Publish';
          return;
        }
        const iso = new Date(localDt).toISOString();
        await Api.scheduleUpload({
          clip_id: activeClip._id, title, description, hashtags,
          privacy_status: privacyStatus, scheduled_for: iso, publish_at: iso,
        });
        showToast(`Upload scheduled for ${new Date(localDt).toLocaleString()}.`);
      }
      closeModal();
      ClipsView.refresh();
      switchView('publish');
    } catch (e) {
      showToast(`Publish failed: ${e.message}`, true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Publish';
    }
  }

  async function refreshJobs() {
    const list = document.getElementById('jobs-list');
    try {
      const data = await Api.listJobs();
      if (!data.jobs.length) {
        list.innerHTML = `<p class="empty-hint">No scheduled or past uploads yet.</p>`;
        return;
      }
      list.innerHTML = data.jobs.map(j => `
        <div class="job-row">
          <div>
            <strong>${escapeHtml(j.title || 'Untitled')}</strong>
            <div class="job-row-meta">
              ${j.scheduled_for ? 'Scheduled: ' + new Date(j.scheduled_for).toLocaleString() : ''}
              ${j.youtube_url ? ' · <a href="' + j.youtube_url + '" target="_blank" style="color:var(--accent-cyan)">View on YouTube</a>' : ''}
              ${j.error ? ' · Error: ' + escapeHtml(j.error) : ''}
            </div>
          </div>
          <span class="job-status-badge" data-status="${j.status}">${j.status}</span>
        </div>
      `).join('');
    } catch (e) {
      list.innerHTML = `<p class="empty-hint">Could not load jobs: ${e.message}</p>`;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  return { init, openModal, refreshJobs };
})();