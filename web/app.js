/*
 * Cardia dashboard, adapted for the local Python virtual ECG device.
 * Polls /api/ecg every 250 ms and renders physical ECG samples in their
 * original WFDB unit. Cardia attribution: Nisa Maaşoğlu, MIT License.
 */

(() => {
  'use strict';

  const pollMs = 250;
  const restingMin = 60;
  const restingMax = 100;
  const el = {
    sound: document.getElementById('sound-btn'),
    status: document.getElementById('status'),
    alert: document.getElementById('alert'),
    alertTitle: document.getElementById('alert-title'),
    heart: document.getElementById('heart'),
    bpm: document.getElementById('bpm'),
    source: document.getElementById('beat-source'),
    ibi: document.getElementById('m-ibi'),
    amp: document.getElementById('m-amp'),
    quality: document.getElementById('m-quality'),
    beats: document.getElementById('m-beats'),
    wave: document.getElementById('wave'),
    waveNote: document.getElementById('wave-note'),
    audio: document.getElementById('beat-audio')
  };
  const ctx = el.wave.getContext('2d');
  let lastBeats = null;
  let soundOn = false;

  function setStatus(kind, text) {
    el.status.className = `status status--${kind}`;
    el.status.textContent = text;
  }

  function resizeWave() {
    const dpr = window.devicePixelRatio || 1;
    el.wave.width = Math.max(1, Math.round(el.wave.getBoundingClientRect().width * dpr));
    el.wave.height = Math.round(220 * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawWave(samples) {
    const w = el.wave.clientWidth;
    const h = 220;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(120, 160, 220, 0.12)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      const y = (h / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    if (!samples || samples.length < 2) return;

    let min = Math.min(...samples);
    let max = Math.max(...samples);
    if (max - min < 0.1) {
      const mid = (max + min) / 2;
      min = mid - 0.05;
      max = mid + 0.05;
    }
    const pad = (max - min) * 0.12;
    min -= pad;
    max += pad;
    const x = i => (i / (samples.length - 1)) * w;
    const y = v => h - ((v - min) / (max - min)) * h;
    ctx.beginPath();
    ctx.moveTo(x(0), y(samples[0]));
    for (let i = 1; i < samples.length; i++) ctx.lineTo(x(i), y(samples[i]));
    ctx.strokeStyle = '#2de08a';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.shadowColor = 'rgba(45, 224, 138, 0.55)';
    ctx.shadowBlur = 10;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.arc(x(samples.length - 1), y(samples[samples.length - 1]), 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#2de08a';
    ctx.fill();
  }

  function drawBackgroundGrid() {
    const c = document.getElementById('grid');
    const g = c.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    c.width = window.innerWidth * dpr;
    c.height = window.innerHeight * dpr;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, window.innerWidth, window.innerHeight);
    g.strokeStyle = 'rgba(30, 60, 110, 0.35)';
    g.lineWidth = 1;
    for (let px = 0; px <= window.innerWidth; px += 37) {
      g.beginPath(); g.moveTo(px, 0); g.lineTo(px, window.innerHeight); g.stroke();
    }
    for (let py = 0; py <= window.innerHeight; py += 37) {
      g.beginPath(); g.moveTo(0, py); g.lineTo(window.innerWidth, py); g.stroke();
    }
  }

  function pulseHeart() {
    el.heart.classList.add('beat');
    setTimeout(() => el.heart.classList.remove('beat'), 130);
    if (soundOn) {
      el.audio.currentTime = 0;
      el.audio.play().catch(() => {});
    }
  }

  function render(data) {
    const known = data.quality === 1 && Number.isFinite(data.bpm) && data.bpm > 0;
    el.bpm.textContent = known ? Math.round(data.bpm) : '--';
    el.bpm.className = 'bpm';
    if (!known) el.bpm.classList.add('unknown');
    else if (data.bpm < restingMin || data.bpm > restingMax) el.bpm.classList.add('out-of-range');

    const progress = Number.isFinite(data.elapsed) ? `${data.elapsed.toFixed(1)} s replayed` : 'waiting for ECG';
    el.source.textContent = `${data.source} · ${progress}`;
    el.ibi.textContent = Number.isFinite(data.ibi) ? `${Math.round(data.ibi * 1000)} ms` : '--';
    el.amp.textContent = Number.isFinite(data.amplitude) ? `${data.amplitude.toFixed(2)} ${data.unit}` : '--';
    el.quality.textContent = data.completed ? 'replay complete' : data.active ? 'replaying' : 'waiting';
    el.quality.className = `metric-value ${data.quality === 1 ? 'good' : ''}`;
    el.beats.textContent = data.beats;
    const seconds = Array.isArray(data.wave) && data.fs > 0 ? data.wave.length / data.fs : 0;
    el.waveNote.textContent = `${data.unit} · ${data.fs} Hz · ${seconds.toFixed(1)} s window`;
    drawWave(data.wave);

    if (lastBeats !== null && data.beats > lastBeats) pulseHeart();
    lastBeats = data.beats;
    setStatus(data.completed ? 'offline' : data.active ? 'live' : 'offline',
      data.completed ? 'Completed' : data.active ? 'Live' : 'Waiting');

    const outOfRange = known && (data.bpm < restingMin || data.bpm > restingMax);
    el.alert.hidden = !outOfRange;
    if (outOfRange) {
      el.alertTitle.textContent = data.bpm > restingMax
        ? `Heart rate above the resting range (${Math.round(data.bpm)} BPM)`
        : `Heart rate below the resting range (${Math.round(data.bpm)} BPM)`;
    }
  }

  async function tick() {
    try {
      const response = await fetch('/api/ecg', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    } catch (error) {
      setStatus('offline', 'Offline');
      el.source.textContent = 'Python virtual device unavailable';
      el.bpm.textContent = '--';
      el.bpm.className = 'bpm unknown';
    } finally {
      setTimeout(tick, pollMs);
    }
  }

  el.sound.addEventListener('click', () => {
    soundOn = !soundOn;
    el.sound.setAttribute('aria-pressed', String(soundOn));
    el.sound.textContent = `Sound: ${soundOn ? 'on' : 'off'}`;
    if (soundOn) el.audio.play().then(() => el.audio.pause()).catch(() => {});
  });
  window.addEventListener('resize', () => { resizeWave(); drawBackgroundGrid(); });
  resizeWave();
  drawBackgroundGrid();
  tick();
})();
