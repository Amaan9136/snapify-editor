const LogsView = (() => {
  let source = null;
  let entries = [];
  let paused = false;
  let clipKeys = [];
  let queueProgressCb = null;
  const MAX_ENTRIES = 300;

  function init() {
    document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
    document.getElementById('btn-pause-logs').addEventListener('click', togglePause);
    connect();
  }

  function connect() {
    if (source) source.close();
    source = new EventSource('/api/logs/stream');
    source.onmessage = (e) => {
      if (paused) return;
      try {
        addEntry(JSON.parse(e.data));
      } catch (err) {}
    };
    source.onerror = () => {
      setStatus(false);
    };
    source.onopen = () => {
      setStatus(true);
    };
  }

  function onQueueProgress(cb) {
    queueProgressCb = cb;
    if (cb) clipKeys = [];
  }

  function seenClipKeys() {
    return clipKeys;
  }

  function handleProgress(entry) {
    if (!entry.clip_key) return;
    if (!clipKeys.includes(entry.clip_key)) clipKeys.push(entry.clip_key);
    if (entry.progress != null) {
      const row = document.getElementById('editor-render-progress-row');
      const fill = document.getElementById('editor-render-progress-fill');
      const label = document.getElementById('editor-render-progress-label');
      if (row && fill && label) {
        row.classList.add('is-active');
        fill.style.width = `${Math.round(entry.progress * 100)}%`;
        fill.classList.toggle('is-done', entry.progress >= 1);
        label.textContent = `${entry.clip_key} · ${Math.round(entry.progress * 100)}%`;
      }
      if (queueProgressCb) queueProgressCb(entry.clip_key, entry.progress);
    }
  }

  function setStatus(connected) {
    const dot = document.getElementById('logs-status-dot');
    if (dot) dot.dataset.ok = connected ? 'true' : 'false';
  }

  function addEntry(entry) {
    entries.push(entry);
    if (entries.length > MAX_ENTRIES) entries.shift();
    renderEntry(entry);
    handleProgress(entry);
  }

  function renderEntry(entry) {
    const list = document.getElementById('logs-list');
    const empty = list.querySelector('.empty-hint');
    if (empty) empty.remove();
    const row = document.createElement('div');
    row.className = 'log-row';
    row.dataset.level = entry.level;
    const time = new Date(entry.ts * 1000).toLocaleTimeString();
    row.innerHTML = `
      <span class="log-row-time">${time}</span>
      <span class="log-row-source">${escapeHtml(entry.source || 'app')}</span>
      <span class="log-row-message">${escapeHtml(entry.message)}</span>
    `;
    list.appendChild(row);
    if (!paused) list.scrollTop = list.scrollHeight;
    while (list.children.length > MAX_ENTRIES) list.removeChild(list.firstChild);
  }

  function clearLogs() {
    entries = [];
    document.getElementById('logs-list').innerHTML = `<p class="empty-hint">No logs yet.</p>`;
  }

  function togglePause() {
    paused = !paused;
    document.getElementById('btn-pause-logs').textContent = paused ? 'Resume' : 'Pause';
    document.getElementById('btn-pause-logs').classList.toggle('is-active', paused);
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  return { init, onQueueProgress, seenClipKeys };
})();