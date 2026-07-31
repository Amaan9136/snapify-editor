function showToast(message, isError = false) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' is-error' : '');
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), isError ? 6000 : 3500);
}

function formatTimecode(seconds) {
  if (!isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(2);
  return `${String(m).padStart(2, '0')}:${s.padStart(5, '0')}`;
}

function parseTimecode(str) {
  if (!str) return 0;
  const parts = str.split(':');
  if (parts.length === 2) {
    return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
  }
  return parseFloat(str) || 0;
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
  return `${val.toFixed(1)} ${units[i]}`;
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

function switchView(viewName) {
  document.querySelectorAll('[data-view-panel]').forEach(panel => {
    panel.classList.toggle('hidden', panel.id !== `view-${viewName}`);
  });
  document.querySelectorAll('.topbar-tab').forEach(tab => {
    tab.classList.toggle('is-active', tab.dataset.view === viewName);
  });
  if (viewName === 'clips') ClipsView.refresh();
  if (viewName === 'publish') PublishView.refreshJobs();
  if (viewName === 'library') LibraryView.refresh();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.topbar-tab').forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });
  LibraryView.init();
  EditorView.init();
  ClipsView.init();
  PublishView.init();
  LibraryView.refresh();
});