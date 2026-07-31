const EditorView = (() => {
  let state = null;

  function freshState() {
    return { filename: null, meta: null, trimStart: 0, trimEnd: 0, splitPoints: [], ratio: '9:16', customRatio: { w: 21, h: 9 }, panStart: { x: 0.5, y: 0.5 }, panEnd: null, settingPanTarget: 'start', speed: 1.0, brightness: 0.0, contrast: 1.0, saturation: 1.0, mute: false, volume: 1.0, title: '', queue: [], };
  }

  function init() {
    state = freshState();

    document.getElementById('source-select').addEventListener('change', (e) => {
      if (e.target.value) loadSource(e.target.value);
    });

    document.getElementById('ratio-picker').addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-ratio]');
      if (!btn) return;
      setRatio(btn.dataset.ratio);
    });
    document.getElementById('custom-ratio-w').addEventListener('input', debounce(onCustomRatioChange, 250));
    document.getElementById('custom-ratio-h').addEventListener('input', debounce(onCustomRatioChange, 250));

    document.getElementById('btn-play-pause').addEventListener('click', togglePlayback);

    setupTimelineDrag();
    document.getElementById('trim-start-field').addEventListener('change', onTrimFieldChange);
    document.getElementById('trim-end-field').addEventListener('change', onTrimFieldChange);
    document.getElementById('btn-add-split').addEventListener('click', addSplitAtPlayhead);
    document.getElementById('btn-run-split').addEventListener('click', runSplit);

    document.getElementById('btn-set-pan-start').addEventListener('click', () => { state.settingPanTarget = 'start'; showToast('Drag the crop box to set the pan START position.'); });
    document.getElementById('btn-set-pan-end').addEventListener('click', () => {
      if (!state.panEnd) state.panEnd = { ...state.panStart };
      state.settingPanTarget = 'end';
      showToast('Drag the crop box to set the pan END position.');
    });
    document.getElementById('btn-clear-pan').addEventListener('click', () => {
      state.panEnd = null;
      state.settingPanTarget = 'start';
      updateViewfinder();
      showToast('Pan cleared - crop is now static.');
    });

    bindSlider('speed-slider', 'speed-value', (v) => { state.speed = v; return `${v.toFixed(2)}x`; }, applyPlaybackRate);
    bindSlider('brightness-slider', 'brightness-value', (v) => { state.brightness = v; return v.toFixed(2); }, applyCssFilterPreview);
    bindSlider('contrast-slider', 'contrast-value', (v) => { state.contrast = v; return v.toFixed(2); }, applyCssFilterPreview);
    bindSlider('saturation-slider', 'saturation-value', (v) => { state.saturation = v; return v.toFixed(2); }, applyCssFilterPreview);
    bindSlider('volume-slider', 'volume-value', (v) => { state.volume = v; return v.toFixed(2); }, applyVolumePreview);
    document.getElementById('mute-checkbox').addEventListener('change', (e) => {
      state.mute = e.target.checked;
      document.getElementById('volume-row').style.opacity = state.mute ? 0.4 : 1;
      applyVolumePreview();
    });

    document.getElementById('clip-title-field').addEventListener('input', (e) => { state.title = e.target.value; });

    document.getElementById('btn-add-to-queue').addEventListener('click', addCurrentToQueue);
    document.getElementById('btn-render-queue').addEventListener('click', renderQueue);

    const video = document.getElementById('preview-video');
    video.addEventListener('timeupdate', onVideoTimeUpdate);
    video.addEventListener('loadedmetadata', onVideoLoadedMetadata);
    video.addEventListener('play', () => togglePlayIcon(true));
    video.addEventListener('pause', () => togglePlayIcon(false));
  }

  function populateSourceOptions(videos) {
    const select = document.getElementById('source-select');
    const currentValue = select.value;
    select.innerHTML = '<option value="">Choose a video…</option>' + videos.map(v =>
      `<option value="${v.filename}">${v.filename}</option>`
    ).join('');
    if (videos.some(v => v.filename === currentValue)) select.value = currentValue;
  }

  async function loadSource(filename) {
    try {
      const meta = await Api.probeVideo(filename);
      state = freshState();
      state.filename = filename;
      state.meta = meta;
      state.trimStart = 0;
      state.trimEnd = meta.duration;

      document.getElementById('source-select').value = filename;
      document.getElementById('preview-empty-state').classList.add('is-hidden');

      const video = document.getElementById('preview-video');
      video.src = `/api/videos/proxy/${encodeURIComponent(filename)}`;
      video.load();

      document.getElementById('clip-title-field').value = filenameToTitle(filename);
      state.title = filenameToTitle(filename);

      resetSlidersUI();
      renderSplitMarkers();
      updateTrimFieldsUI();
      document.getElementById('btn-run-split').disabled = true;

    } catch (e) {
      showToast(`Could not load "${filename}": ${e.message}`, true);
    }
  }

  function filenameToTitle(filename) {
    return filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
  }

  function resetSlidersUI() {
    document.getElementById('speed-slider').value = 1;
    document.getElementById('speed-value').textContent = '1.0x';
    document.getElementById('brightness-slider').value = 0;
    document.getElementById('brightness-value').textContent = '0.00';
    document.getElementById('contrast-slider').value = 1;
    document.getElementById('contrast-value').textContent = '1.00';
    document.getElementById('saturation-slider').value = 1;
    document.getElementById('saturation-value').textContent = '1.00';
    document.getElementById('volume-slider').value = 1;
    document.getElementById('volume-value').textContent = '1.00';
    document.getElementById('mute-checkbox').checked = false;
    applyCssFilterPreview();
    applyPlaybackRate();
    applyVolumePreview();
  }

  function bindSlider(sliderId, labelId, updateFn, sideEffectFn) {
    const slider = document.getElementById(sliderId);
    slider.addEventListener('input', () => {
      const v = parseFloat(slider.value);
      document.getElementById(labelId).textContent = updateFn(v);
      if (sideEffectFn) sideEffectFn();
    });
  }

  function onVideoLoadedMetadata() {
    updateViewfinder();
    updateTimecodeDisplay();
  }

  function onVideoTimeUpdate() {
    const video = document.getElementById('preview-video');
    const track = document.getElementById('timeline-track');
    const playhead = document.getElementById('timeline-playhead');
    if (state.meta && state.meta.duration > 0) {
      const pct = (video.currentTime / state.meta.duration) * 100;
      playhead.style.left = `${pct}%`;
    }
    updateTimecodeDisplay();
    updateViewfinderPan();
    if (!video.paused && video.currentTime >= state.trimEnd) {
      video.currentTime = state.trimStart;
    }
  }

  function updateTimecodeDisplay() {
    const video = document.getElementById('preview-video');
    const dur = state.meta ? state.meta.duration : 0;
    document.getElementById('timecode-display').textContent =
      `${formatTimecode(video.currentTime || 0)} / ${formatTimecode(dur)}`;
  }

  function togglePlayback() {
    const video = document.getElementById('preview-video');
    if (video.paused) {
      if (video.currentTime < state.trimStart || video.currentTime >= state.trimEnd) {
        video.currentTime = state.trimStart;
      }
      video.play();
    } else {
      video.pause();
    }
  }

  function togglePlayIcon(isPlaying) {
    document.getElementById('icon-play').hidden = isPlaying;
    document.getElementById('icon-pause').classList.toggle('hidden', !isPlaying);
  }

  function applyPlaybackRate() {
    document.getElementById('preview-video').playbackRate = state.speed;
  }

  function applyCssFilterPreview() {
    const video = document.getElementById('preview-video');
    const b = 1 + state.brightness;
    video.style.filter = `brightness(${b}) contrast(${state.contrast}) saturate(${state.saturation})`;
  }

  function applyVolumePreview() {
    const video = document.getElementById('preview-video');
    video.muted = state.mute;
    video.volume = Math.min(1, Math.max(0, state.volume > 1 ? 1 : state.volume));
  }

  function setRatio(ratio) {
    state.ratio = ratio;
    document.querySelectorAll('#ratio-picker button').forEach(b => b.classList.toggle('is-active', b.dataset.ratio === ratio));
    document.getElementById('custom-ratio-row').classList.toggle('hidden', ratio !== 'custom');
    document.getElementById('preview-frame').dataset.ratio = ratio === 'custom'
      ? `${state.customRatio.w}:${state.customRatio.h}` : ratio;
    if (ratio === 'custom') {
      document.getElementById('preview-frame').style.aspectRatio = `${state.customRatio.w} / ${state.customRatio.h}`;
    } else {
      document.getElementById('preview-frame').style.aspectRatio = '';
    }
    updateViewfinder();
  }

  function onCustomRatioChange() {
    const w = parseFloat(document.getElementById('custom-ratio-w').value) || 1;
    const h = parseFloat(document.getElementById('custom-ratio-h').value) || 1;
    state.customRatio = { w, h };
    if (state.ratio === 'custom') {
      document.getElementById('preview-frame').style.aspectRatio = `${w} / ${h}`;
      updateViewfinder();
    }
  }

  function getTargetRatioValue() {
    if (state.ratio === 'custom') return state.customRatio.w / state.customRatio.h;
    const [w, h] = state.ratio.split(':').map(Number);
    return w / h;
  }

  function computeCropRect(cx, cy) {
    const { width: srcW, height: srcH } = state.meta;
    const targetRatio = getTargetRatioValue();
    const srcRatio = srcW / srcH;

    let cropW, cropH;
    if (srcRatio > targetRatio) {
      cropH = srcH;
      cropW = Math.round(cropH * targetRatio);
    } else {
      cropW = srcW;
      cropH = Math.round(cropW / targetRatio);
    }
    cropW -= cropW % 2;
    cropH -= cropH % 2;

    const maxX = Math.max(srcW - cropW, 0);
    const maxY = Math.max(srcH - cropH, 0);
    const x = Math.round(Math.max(0, Math.min(1, cx)) * maxX);
    const y = Math.round(Math.max(0, Math.min(1, cy)) * maxY);

    return { cropW, cropH, x, y, srcW, srcH };
  }

  function updateViewfinderPan() {
    if (!state.meta) return;
    const video = document.getElementById('preview-video');
    let progress = 0;
    const trimDur = state.trimEnd - state.trimStart;
    if (state.panEnd && trimDur > 0) {
      progress = Math.min(1, Math.max(0, (video.currentTime - state.trimStart) / trimDur));
    }
    const cx = state.panEnd ? state.panStart.x + (state.panEnd.x - state.panStart.x) * progress : state.panStart.x;
    const cy = state.panEnd ? state.panStart.y + (state.panEnd.y - state.panStart.y) * progress : state.panStart.y;
    renderCropToDom(cx, cy);
  }

  function updateViewfinder() {
    if (!state.meta) return;
    updateViewfinderPan();
  }

  function renderCropToDom(cx, cy) {
    const frame = document.getElementById('preview-frame');
    const video = document.getElementById('preview-video');
    const cropBox = document.getElementById('viewfinder-crop');
    const { cropW, cropH, x, y, srcW, srcH } = computeCropRect(cx, cy);

    const frameRect = frame.getBoundingClientRect();
    const frameW = frameRect.width || 1;
    const frameH = frameRect.height || 1;

    const scale = frameW / cropW;
    const scaledVideoW = srcW * scale;
    const scaledVideoH = srcH * scale;
    const offsetX = -x * scale;
    const offsetY = -y * scale;

    video.style.width = `${scaledVideoW}px`;
    video.style.height = `${scaledVideoH}px`;
    video.style.left = `${offsetX}px`;
    video.style.top = `${offsetY}px`;

    cropBox.style.left = '0px';
    cropBox.style.top = '0px';
    cropBox.style.width = `${frameW}px`;
    cropBox.style.height = `${frameH}px`;
  }

  function setupCropDrag() {
    const cropBox = document.getElementById('viewfinder-crop');
    const frame = document.getElementById('preview-frame');
    let dragging = false;

    cropBox.addEventListener('pointerdown', (e) => {
      if (!state.meta) return;
      dragging = true;
      cropBox.setPointerCapture(e.pointerId);
      handleDragMove(e);
    });
    cropBox.addEventListener('pointermove', (e) => { if (dragging) handleDragMove(e); });
    cropBox.addEventListener('pointerup', () => { dragging = false; });
    cropBox.addEventListener('pointercancel', () => { dragging = false; });

    function handleDragMove(e) {
      const rect = frame.getBoundingClientRect();
      const cx = (e.clientX - rect.left) / rect.width;
      const cy = (e.clientY - rect.top) / rect.height;
      const clamped = { x: Math.min(1, Math.max(0, cx)), y: Math.min(1, Math.max(0, cy)) };

      if (state.settingPanTarget === 'end' && state.panEnd) {
        state.panEnd = clamped;
      } else {
        state.panStart = clamped;
      }
      updateViewfinderPan();
    }
  }

  function setupTimelineDrag() {
    setupCropDrag();
    const track = document.getElementById('timeline-track');
    const startHandle = document.getElementById('handle-start');
    const endHandle = document.getElementById('handle-end');
    let dragTarget = null;

    function pctToTime(clientX) {
      const rect = track.getBoundingClientRect();
      const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      return pct * (state.meta ? state.meta.duration : 0);
    }

    startHandle.addEventListener('pointerdown', (e) => { dragTarget = 'start'; startHandle.setPointerCapture(e.pointerId); });
    endHandle.addEventListener('pointerdown', (e) => { dragTarget = 'end'; endHandle.setPointerCapture(e.pointerId); });

    window.addEventListener('pointermove', (e) => {
      if (!dragTarget || !state.meta) return;
      const t = pctToTime(e.clientX);
      if (dragTarget === 'start') {
        state.trimStart = Math.min(t, state.trimEnd - 0.05);
      } else {
        state.trimEnd = Math.max(t, state.trimStart + 0.05);
      }
      updateTrimFieldsUI();
      renderTimelineUI();
    });
    window.addEventListener('pointerup', () => { dragTarget = null; });

    track.addEventListener('click', (e) => {
      if (e.target === startHandle || e.target === endHandle) return;
      if (!state.meta) return;
      const t = pctToTime(e.clientX);
      document.getElementById('preview-video').currentTime = Math.min(Math.max(t, state.trimStart), state.trimEnd);
    });
  }

  function updateTrimFieldsUI() {
    document.getElementById('trim-start-field').value = formatTimecode(state.trimStart);
    document.getElementById('trim-end-field').value = formatTimecode(state.trimEnd);
    renderTimelineUI();
  }

  function onTrimFieldChange() {
    if (!state.meta) return;
    let start = parseTimecode(document.getElementById('trim-start-field').value);
    let end = parseTimecode(document.getElementById('trim-end-field').value);
    start = Math.max(0, Math.min(start, state.meta.duration));
    end = Math.max(0, Math.min(end, state.meta.duration));
    if (end <= start) end = Math.min(state.meta.duration, start + 0.5);
    state.trimStart = start;
    state.trimEnd = end;
    updateTrimFieldsUI();
  }

  function renderTimelineUI() {
    if (!state.meta || !state.meta.duration) return;
    const dur = state.meta.duration;
    const startPct = (state.trimStart / dur) * 100;
    const endPct = (state.trimEnd / dur) * 100;
    document.getElementById('handle-start').style.left = `${startPct}%`;
    document.getElementById('handle-end').style.left = `${endPct}%`;
    const sel = document.getElementById('timeline-selection');
    sel.style.left = `${startPct}%`;
    sel.style.width = `${endPct - startPct}%`;
  }

  function addSplitAtPlayhead() {
    if (!state.meta) return;
    const video = document.getElementById('preview-video');
    const t = video.currentTime;
    if (t <= 0.1 || t >= state.meta.duration - 0.1) {
      showToast('Move the playhead into the middle of the clip first.', true);
      return;
    }
    if (state.splitPoints.some(p => Math.abs(p - t) < 0.2)) return;
    state.splitPoints.push(t);
    state.splitPoints.sort((a, b) => a - b);
    renderSplitMarkers();
    document.getElementById('btn-run-split').disabled = state.splitPoints.length === 0;
  }

  function removeSplitPoint(index) {
    state.splitPoints.splice(index, 1);
    renderSplitMarkers();
    document.getElementById('btn-run-split').disabled = state.splitPoints.length === 0;
  }

  function renderSplitMarkers() {
    const dur = state.meta ? state.meta.duration : 0;
    const layer = document.getElementById('split-markers-layer');
    const list = document.getElementById('split-markers-list');

    layer.innerHTML = state.splitPoints.map(p => {
      const pct = dur ? (p / dur) * 100 : 0;
      return `<div class="split-marker" style="left:${pct}%"></div>`;
    }).join('');

    list.innerHTML = state.splitPoints.map((p, i) =>
      `<span class="split-marker-chip">${formatTimecode(p)} <button data-index="${i}">&times;</button></span>`
    ).join('');
    list.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => removeSplitPoint(parseInt(btn.dataset.index, 10)));
    });
  }

  async function runSplit() {
    if (!state.filename || !state.splitPoints.length) return;
    const btn = document.getElementById('btn-run-split');
    btn.disabled = true;
    btn.textContent = 'Splitting…';
    try {
      const result = await Api.splitVideo(state.filename, state.splitPoints);
      showToast(`Split into ${result.segments.length} segments. Reload the Library to see them, or find them under outputs/splits.`);
    } catch (e) {
      showToast(`Split failed: ${e.message}`, true);
    } finally {
      btn.textContent = 'Split at markers';
      btn.disabled = state.splitPoints.length === 0;
    }
  }

  function buildRenderParams() {
    return {
      filename: state.filename,
      start: state.trimStart,
      end: state.trimEnd,
      ratio: state.ratio,
      custom_ratio: state.ratio === 'custom' ? state.customRatio : null,
      pan_start: state.panStart,
      pan_end: state.panEnd,
      speed: state.speed,
      brightness: state.brightness,
      contrast: state.contrast,
      saturation: state.saturation,
      mute: state.mute,
      volume: state.volume,
      title: state.title || filenameToTitle(state.filename || 'clip'),
    };
  }

  function addCurrentToQueue() {
    if (!state.filename || !state.meta) {
      showToast('Load a video first.', true);
      return;
    }
    state.queue.push(buildRenderParams());
    renderQueueUI();
  }

  function removeFromQueue(index) {
    state.queue.splice(index, 1);
    renderQueueUI();
  }

  function renderQueueUI() {
    const list = document.getElementById('render-queue-list');
    list.innerHTML = state.queue.map((c, i) => `
      <div class="render-queue-item">
        <span>${escapeHtml(c.title)} · ${c.ratio} · ${formatTimecode(c.start)}–${formatTimecode(c.end)}</span>
        <button data-index="${i}">&times;</button>
      </div>
    `).join('');
    list.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => removeFromQueue(parseInt(btn.dataset.index, 10)));
    });
    document.getElementById('queue-count').textContent = state.queue.length;
    document.getElementById('btn-render-queue').disabled = state.queue.length === 0;
  }

  async function renderQueue() {
    if (!state.queue.length) return;
    const btn = document.getElementById('btn-render-queue');
    btn.disabled = true;
    btn.textContent = 'Rendering…';
    try {
      const result = await Api.renderBatch(state.queue);
      const succeeded = result.results.filter(r => !r.error).length;
      const failed = result.results.filter(r => r.error);
      showToast(`Rendered ${succeeded}/${result.results.length} clip(s).${failed.length ? ' Some failed - check console.' : ''}`);
      if (failed.length) console.error('Render failures:', failed);
      state.queue = [];
      renderQueueUI();
      switchView('clips');
    } catch (e) {
      showToast(`Batch render failed: ${e.message}`, true);
    } finally {
      btn.textContent = 'Render queue (0)';
      document.getElementById('queue-count').textContent = 0;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.addEventListener('resize', debounce(() => { if (state && state.meta) updateViewfinder(); }, 150));

  return { init, loadSource, populateSourceOptions };
})();