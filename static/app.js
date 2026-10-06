/* Sergeant Pace: the recruit's individual training file.
   Flow: intake -> orders -> live run -> statement -> counseling session (the agent deciding, on paper). */
(() => {
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const stage = $('#stage');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

let fast = reduceMotion;          // true: show everything immediately
let playing = false;
const S = { current: null, step: 0, ans: { can: null }, report: {}, timer: null };

/* ---------- timing: sleeps and typing that can be skipped ---------- */
const waiters = new Set();
const sleep = (ms) => new Promise((res) => {
  if (fast) return res();
  const t = setTimeout(() => { waiters.delete(done); res(); }, ms);
  const done = () => { clearTimeout(t); res(); };
  waiters.add(done);
});
function skip() { if (!playing) return; fast = true; waiters.forEach((f) => f()); waiters.clear(); }
async function typeInto(node, text, cps = 70) {
  node.textContent = '';
  if (fast) { node.textContent = text; return; }
  const per = 1000 / cps;
  for (let i = 1; i <= text.length; i++) {
    if (fast) { node.textContent = text; return; }
    node.textContent = text.slice(0, i);
    await sleep(per);
  }
}
document.addEventListener('keydown', (e) => { if (playing && (e.key === ' ' || e.key === 'Escape')) { e.preventDefault(); skip(); } });

/* ---------- small builders ---------- */
const INSIGNIA = '<svg aria-hidden="true"><use href="#insignia"/></svg>';
const header = (title, sub, no) => `<div class="fh">${INSIGNIA}<div><h2>${esc(title)}</h2><p>${esc(sub)}</p></div><div class="formno" aria-label="Form ${esc(no)}">${esc(no)}</div></div>`;
const xmark = '<svg viewBox="0 0 44 44" aria-hidden="true"><path d="M9 10 36 35"/><path d="M35 9 10 36"/></svg>';
const box = (tone = 'blue', on = false) => `<span class="box ${tone}${on ? ' on static-on' : ''}">${xmark}</span>`;
const circleSvg = '<svg viewBox="0 0 104 52" preserveAspectRatio="none" aria-hidden="true"><path d="M10 24C6 8 40 3 70 7c30 5 31 33 2 38C42 51 8 47 10 24Z"/></svg>';

/* ---------- voice: the sergeant speaks, the recruit can talk back ---------- */
let voiceOn = true;
try { voiceOn = localStorage.getItem('sp-voice') !== 'off'; } catch (e) { /* no storage */ }
let currentAudio = null;
const MIC = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>';

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 5000);
}
function stopVoice() { if (currentAudio) { currentAudio.pause(); currentAudio = null; } }
function setVoiceButton() {
  const b = $('#voice-toggle'); b.textContent = voiceOn ? 'Voice on' : 'Voice off'; b.setAttribute('aria-pressed', String(voiceOn));
}
$('#voice-toggle').addEventListener('click', () => {
  voiceOn = !voiceOn; setVoiceButton(); if (!voiceOn) stopVoice();
  try { localStorage.setItem('sp-voice', voiceOn ? 'on' : 'off'); } catch (e) { /* no storage */ }
});
setVoiceButton();

/** Start fetching the spoken version of the remarks; resolves to a ready clip, or null if speech is unavailable. */
function fetchSpeech(text) {
  const h = { ready: false, promise: null };
  h.promise = fetch('/api/speak', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
    .then((r) => { if (!r.ok) throw new Error('no speech'); return r.blob(); })
    .then((blob) => new Promise((res) => {
      const audio = new Audio(URL.createObjectURL(blob));
      audio.addEventListener('loadedmetadata', () => res({ audio, duration: audio.duration || 0 }), { once: true });
      audio.addEventListener('error', () => res(null), { once: true });
    }))
    .catch(() => null)
    .then((clip) => { h.ready = true; return clip; });
  return h;
}
async function clipFor(spec) {
  const h = spec.speech; if (!h) return null;
  if (fast && !h.ready) return null;
  const clip = await Promise.race([h.promise, new Promise((r) => setTimeout(() => r(null), 9000))]);
  return clip && clip.duration > 0 ? clip : null;
}
function playClip(clip) { stopVoice(); currentAudio = clip.audio; clip.audio.play().catch(() => {}); }

async function toWav(buf) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ctx.decodeAudioData(buf); ctx.close();
  const rate = 16000, off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * rate)), rate);
  const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const out = new DataView(new ArrayBuffer(44 + pcm.length * 2)), w = (o, t) => [...t].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); out.setUint32(4, 36 + pcm.length * 2, true); w(8, 'WAVE'); w(12, 'fmt '); out.setUint32(16, 16, true); out.setUint16(20, 1, true);
  out.setUint16(22, 1, true); out.setUint32(24, rate, true); out.setUint32(28, rate * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
  w(36, 'data'); out.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
  return new Blob([out], { type: 'audio/wav' });
}
async function recordWav() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream), chunks = [];
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  rec.start();
  return { stop: () => new Promise((res, rej) => {
    rec.onstop = async () => { stream.getTracks().forEach((t) => t.stop()); try { res(await toWav(await new Blob(chunks).arrayBuffer())); } catch (e) { rej(e); } };
    rec.stop();
  }) };
}
/** Turn a button into tap-to-talk, tap-again-to-send. onText gets the transcript. */
function voiceInput(btn, onText) {
  const idle = btn.innerHTML; let session = null;
  btn.addEventListener('click', async () => {
    if (session) {
      const s = session; session = null; btn.classList.remove('rec'); btn.disabled = true; btn.textContent = 'Listening...';
      try {
        const wav = await s.stop();
        const r = await fetch('/api/transcribe', { method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: wav });
        const d = await r.json(); if (!r.ok) throw new Error(d.error || 'transcription failed');
        if (d.text) onText(d.text); else toast('Heard nothing. Say it again.');
      } catch (e) { toast('Voice failed: ' + e.message); }
      btn.disabled = false; btn.innerHTML = idle;
      return;
    }
    try { stopVoice(); session = await recordWav(); btn.classList.add('rec'); btn.textContent = 'Tap to send'; }
    catch (e) { toast('Microphone blocked. Allow it and try again.'); }
  });
}

function mount(html, cls = 'view') {
  clearInterval(S.timer); stopVoice();
  const n = document.createElement('div');
  n.className = cls; n.innerHTML = html;
  stage.replaceChildren(n);
  window.scrollTo(0, 0);
  return n;
}

function renderBar() {
  const c = S.current;
  $('#fileline').innerHTML = c ? `Recruit 0001 &nbsp;·&nbsp; <b>${esc(c.next.label)}</b>` : '';
  $('#open-file').hidden = !c;
}

/* ============================================================ INTAKE */
const STEPS = {
  can: { q: 'Can you run right now?', say: 'Listen up, recruit. Be honest. I find out either way.' },
  longest: { q: 'Longest recent run?', say: 'How far, and how fast. Do not lie to me.',
    fields: [['longest', 'Distance (km)', 'number', '3', { min: 1, max: 60, step: '0.1', required: true }], ['pace', 'Pace (min:sec per km)', 'text', '6:30', {}]] },
  body1: { q: 'Age and weight.', say: 'The boring part. It decides how hard I let you push.',
    fields: [['age', 'Age (years)', 'number', '', { min: 14, max: 100, required: true }], ['weight', 'Weight (kg)', 'number', '', { min: 30, max: 300, step: '0.1', required: true }]] },
  body2: { q: 'Height and body fat.', say: 'Estimate if you must. A guess beats a blank.',
    fields: [['height', 'Height (cm)', 'number', '', { min: 120, max: 230, required: true }], ['bf', 'Body fat (%)', 'number', '', { min: 3, max: 70, step: '0.1', required: true }]] },
};
const stepOrder = () => ['can', ...(S.ans.can === 'yes' ? ['longest'] : []), 'body1', 'body2'];

function recordRows() {
  const a = S.ans, v = (x, u = '') => (x ? `${esc(x)}${u}` : '');
  return [
    ['Running', a.can === 'yes' ? 'A little' : a.can === 'no' ? 'Cannot' : ''],
    ['Longest run', a.can === 'no' ? 'None' : v(a.longest, ' km')],
    ['Pace', v(a.pace, ' /km')], ['Age', v(a.age)], ['Weight', v(a.weight, ' kg')],
    ['Height', v(a.height, ' cm')], ['Body fat', v(a.bf, ' %')],
  ];
}

// Explicit consent for health data: nothing leaves the browser until this is ticked on the last step.
function consentHtml() {
  const free = !S.meta || S.meta.free_tier !== false;
  return `<label class="consent"><input type="checkbox" name="consent" ${S.ans.consent ? 'checked' : ''} required>
    <span>I agree that the numbers above, and anything I type or say to the sergeant, are processed as described in the <a href="/privacy" target="_blank" rel="noopener">privacy notice</a>, including being sent to Google's Gemini AI. ${free ? "Google's free tier lets people at Google read it. " : ''}I won't type my name or contact details.</span></label>`;
}

function viewIntake() {
  const order = stepOrder(), id = order[S.step], st = STEPS[id], last = S.step === order.length - 1;
  let controls;
  if (id === 'can') {
    controls = `<div class="choices">
      <button class="choice" data-can="no">${box('red')}<span><b>Cannot run</b><span class="d">Not yet. Everyone starts somewhere.</span></span></button>
      <button class="choice" data-can="yes">${box('red')}<span><b>Can run a little</b><span class="d">I can jog for a few minutes.</span></span></button></div>
      <p class="fine">Nothing leaves your browser until you report for duty. <a href="/privacy" target="_blank" rel="noopener">Privacy notice</a></p>`;
  } else {
    controls = `<form id="f" novalidate><div class="fields">${st.fields.map(([k, label, type, ph, at]) => `
      <label class="field"><span class="cap">${label}</span><input name="${k}" type="${type}" placeholder="${ph}" value="${esc(S.ans[k] || '')}" inputmode="${type === 'number' ? 'decimal' : 'text'}" ${Object.entries(at).map(([a, b]) => b === true ? a : `${a}="${b}"`).join(' ')} autocomplete="off"></label>`).join('')}</div>
      ${last ? consentHtml() : ''}
      <div class="actions">${S.step ? '<button type="button" class="btn plain" id="back">Back</button>' : ''}<button class="btn" type="submit">${last ? 'Report for duty' : 'Confirm'}</button></div></form>`;
  }
  const n = mount(`<section class="sheet">${header('Enlistment record', 'Individual training file · recruit intake', 'SP-1')}
    <div class="body"><h1 class="q">${st.q}</h1><p class="say">${st.say}</p>${controls}
    <div class="rec"><h4>Record so far</h4>${recordRows().map(([l, t]) => `<div><span class="cap">${l}</span><span class="typed">${t}</span></div>`).join('')}</div></div></section>`);

  n.querySelectorAll('[data-can]').forEach((b) => b.addEventListener('click', () => {
    S.ans.can = b.dataset.can;
    b.querySelector('.box').classList.add('on');
    setTimeout(() => { S.step++; viewIntake(); }, reduceMotion ? 0 : 420);
  }));
  const f = $('#f', n);
  if (f) {
    $('input', f).focus();
    f.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!f.reportValidity()) return;
      Object.assign(S.ans, Object.fromEntries(new FormData(f)));
      if (last) return submitIntake();
      S.step++; viewIntake();
    });
    const back = $('#back', f);
    if (back) back.addEventListener('click', () => { Object.assign(S.ans, Object.fromEntries(new FormData(f))); S.step--; viewIntake(); });
  }
}

function parsePace(s) {
  s = (s || '').trim();
  if (!s) return 0;
  if (s.includes(':')) { const [m, sec] = s.split(':').map(Number); return +(m + (sec || 0) / 60).toFixed(2); }
  return Number(s) || 0;
}

function submitIntake() {
  const a = S.ans, runs = a.can === 'yes';
  const longest = runs ? Number(a.longest) || 0 : 0, pace = runs ? parsePace(a.pace) : 0;
  const msg = `[Intake form submitted] Age: ${a.age}. Weight: ${a.weight} kg. Height: ${a.height} cm. Body fat: ${a.bf}%. ` +
    `Longest recent run: ${longest} km at ${pace} min/km (0 means they cannot run). ` +
    `Call save_profile with exactly these values (age=${a.age}, weight_kg=${a.weight}, height_cm=${a.height}, ` +
    `body_fat_pct=${a.bf}, longest_run_km=${longest}, pace_min_per_km=${pace}).`;
  ask('/api/chat', { message: msg }, 'intake');
}

/* ============================================================ WEIGH-IN */
function afterSession() { (S.current && S.current.weighin_due ? viewWeighin : viewOrders)(); }

function viewWeighin() {
  const b = S.current.body, last = b.log[b.log.length - 1];
  const v = mount(`<section class="sheet">${header('Weigh-in', 'Body record · every two weeks', 'SP-7')}
    <div class="body"><h1 class="q">Get on the scale.</h1><p class="say">Honest numbers. They set how hard I let you push.</p>
    <form id="wf" novalidate><div class="fields">
      <label class="field"><span class="cap">Weight (kg)</span><input name="weight_kg" type="number" step="0.1" min="30" max="300" value="${b.weight_kg}" required inputmode="decimal"></label>
      <label class="field"><span class="cap">Body fat (%)</span><input name="body_fat_pct" type="number" step="0.1" min="3" max="70" value="${b.body_fat_pct}" required inputmode="decimal"></label></div>
      <p class="cap" style="margin-top:14px">Last time, week ${last.week}: ${last.weight_kg} kg, ${last.body_fat_pct}% body fat. Cannot measure body fat? Leave the last number.</p>
      <div class="actions"><button class="btn" type="submit">File weigh-in</button><button type="button" class="link" id="not-today">Not today</button></div></form></div></section>`);
  const f = $('#wf', v); $('input', f).focus(); $('input', f).select();
  f.addEventListener('submit', (e) => {
    e.preventDefault(); if (!f.reportValidity()) return;
    ask('/api/weighin', { weight_kg: Number(f.weight_kg.value), body_fat_pct: Number(f.body_fat_pct.value) }, 'weighin');
  });
  $('#not-today', v).addEventListener('click', async () => {
    try { S.current = await (await fetch('/api/weighin/skip', { method: 'POST' })).json(); } catch (e) { /* carry on */ }
    renderBar(); viewOrders();
  });
}

/* ============================================================ ORDERS */
const fmtMin = (m) => (m < 1 ? `${Math.round(m * 60)}s` : Number.isInteger(m) ? String(m) : (Math.round(m * 10) / 10).toString());

function march(n, { needle = false } = {}) {
  const total = n.total_minutes;
  const segs = n.blocks.map((b) => {
    const wide = b.minutes / total >= 0.035;
    const text = b.label ? b.label : wide ? fmtMin(b.minutes) : '';
    return `<div class="seg ${b.type}" style="flex:${b.minutes}" title="${b.type}: ${fmtMin(b.minutes)} min">${text}</div>`;
  }).join('');
  const every = total > 45 ? 10 : total > 18 ? 5 : 1, ticks = [];
  for (let m = 0; m <= Math.floor(total); m += 1) {
    const major = m % 5 === 0, left = (m / total) * 100;
    if (m % every === 0 || major) ticks.push(`<i class="${major ? 'maj' : ''}" style="left:${left}%"></i>${major ? `<em style="left:${left}%">${m}</em>` : ''}`);
  }
  return `<div class="strip" style="position:relative"><div class="march" aria-label="Run timeline">${segs}</div>
    <div class="ruler" aria-hidden="true">${ticks.join('')}</div>${needle ? '<div class="needle" id="needle"></div>' : ''}</div>`;
}
const legend = '<div class="legend"><span><i class="run"></i>Run</span><span><i class="walk"></i>Walk</span><span><i class="warmup"></i>Warm-up, cool-down</span><span>Minutes</span></div>';

function viewOrders() {
  const c = S.current, n = c.next;
  const std = [['Easy pace', c.easy_pace], ['Pace ceiling', c.pace_limit], ['Effort target', '5 to 6 of 10']];
  if (n.kind !== 'distance') std.push(['Running time', `${fmtMin(n.run_minutes)} of ${fmtMin(n.total_minutes)} min`]);
  else std.push(['Distance', `${n.km} km`]);
  const road = (c.estimates || []).find((e) => !e.cleared);
  if (road && road.weeks) std.push([`Road to ${road.short}`, `about ${road.weeks} weeks`]);
  const v = mount(`<section class="sheet">${header('Training order', n.label, 'SP-2')}
    <div class="body"><h1 class="job">${esc(n.summary)}</h1>${march(n)}${legend}
      <div class="actions" style="margin:0 0 clamp(22px, 3vw, 36px)"><button class="btn" id="go">Acknowledge, begin run</button><button class="link" id="refuse">Refuse this order</button></div>
      <div class="cols"><div><span class="cap">Orders</span><ol class="orders">${n.steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol></div>
        <div class="stds"><span class="cap">Standards</span>${std.map(([l, t]) => `<div><span class="cap">${l}</span><span class="typed">${esc(t)}</span></div>`).join('')}</div></div>
      <div class="sim"><span class="cap">Demo, fake this run</span>
        <button data-sim="good">Went well</button><button data-sim="easy">Felt easy</button><button data-sim="hard">Too hard</button><button data-sim="hurt">Injured</button><button data-sim="skip">Skipped</button><button data-weighin>Weigh-in</button></div>
    </div></section>`);
  $('#go', v).addEventListener('click', viewRun);
  $('#refuse', v).addEventListener('click', () => ask('/api/skip', { notes: '' }, 'skip'));
  $('[data-weighin]', v).addEventListener('click', viewWeighin);
  v.querySelectorAll('[data-sim]').forEach((b) => b.addEventListener('click', () => ask('/api/sim', { scenario: b.dataset.sim }, b.dataset.sim === 'skip' ? 'skip' : 'run')));
}

/* ============================================================ LIVE RUN */
const NAMES = { warmup: 'Warm up', run: 'Run', walk: 'Walk', cooldown: 'Cool down' };
const CUES = { warmup: 'Brisk walk. Get warm.', run: 'Easy. You must be able to talk.', walk: 'Catch your breath. Keep moving.', cooldown: 'Easy walk. Then stretch.' };
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
function beep() {
  try { const c = new (window.AudioContext || window.webkitAudioContext)(), o = c.createOscillator();
    o.frequency.value = 880; o.connect(c.destination); o.start(); setTimeout(() => { o.stop(); c.close(); }, 200); } catch (e) { /* no audio */ }
}

function viewRun() {
  const c = S.current, n = c.next;
  const v = mount(`<section class="live"><h1 class="phase" id="ph"></h1><p class="count" id="ct" aria-live="off">0:00</p><p class="cue" id="cue"></p>
    <div class="drill"><div class="drill-h"><b>${esc(n.label)}</b><span>${esc(n.summary)}</span></div>${march(n, { needle: true })}</div>
    <div class="actions"><button class="btn" id="done">I'm done</button><button class="btn plain" id="abort">Back to orders</button></div></section>`);
  const start = Date.now(), total = n.total_minutes * 60;
  let last = -1;
  const tick = () => {
    const el = (Date.now() - start) / 1000;
    let acc = 0, idx = -1;
    for (let i = 0; i < n.blocks.length; i++) { const end = acc + n.blocks[i].minutes * 60; if (el < end) { idx = i; break; } acc = end; }
    const ph = $('#ph', v);
    if (idx === -1) {
      ph.className = 'phase done'; ph.textContent = 'Done'; $('#ct', v).textContent = '0:00'; $('#cue', v).textContent = 'Report to the sergeant.';
      if (last !== -2) beep(); last = -2; clearInterval(S.timer);
    } else {
      const b = n.blocks[idx], left = acc + b.minutes * 60 - el;
      ph.className = 'phase ' + b.type; ph.textContent = NAMES[b.type];
      $('#ct', v).textContent = mmss(left);
      $('#cue', v).textContent = b.type === 'run' && n.kind === 'distance' ? `Steady at ${c.easy_pace}.` : CUES[b.type];
      if (idx !== last && last !== -1) beep();
      last = idx;
    }
    $('#needle', v).style.left = `calc(${Math.min(100, (el / total) * 100)}% - 2px)`;
  };
  tick(); S.timer = setInterval(tick, 250);
  $('#done', v).addEventListener('click', viewStatementA);
  $('#abort', v).addEventListener('click', viewOrders);
}

/* ============================================================ STATEMENT */
function viewStatementA() {
  const c = S.current, n = c.next;
  S.report = { completed: 0, distance_km: 0, duration_min: 0, effort: 5, notes: '' };
  let inner = '';
  if (n.kind === 'intervals') {
    inner = `<h1 class="q">How many run intervals did you finish?</h1><p class="say">Out of ${n.reps}. Tap the last one you completed.</p>
      <div class="row" id="ticks">${Array.from({ length: n.reps }, (_, i) => `<button class="tick" data-k="${i + 1}"><span class="box blue">${xmark}</span><span class="n">${i + 1}</span></button>`).join('')}</div>
      <div class="actions"><button class="btn" id="next" disabled>Next</button><button class="link" id="none">None. I stopped early.</button></div>`;
  } else if (n.kind === 'continuous_time') {
    inner = `<h1 class="q">How many minutes without stopping?</h1><p class="say">Ordered: ${n.run_min}. Count only the running.</p>
      <div class="stepper"><button type="button" id="dec" aria-label="Fewer minutes">-</button><div class="typed" id="val">${n.run_min}</div><button type="button" id="inc" aria-label="More minutes">+</button></div>
      <div class="actions"><button class="btn" id="next">Next</button></div>`;
  } else {
    inner = `<h1 class="q">How far, and how long?</h1><p class="say">Ordered: ${n.km} km. Give me the real numbers.</p>
      <form id="f" novalidate><div class="fields"><label class="field"><span class="cap">Distance (km)</span><input name="km" type="number" step="0.01" min="0.1" value="${n.km}" required inputmode="decimal"></label>
        <label class="field"><span class="cap">Total time (minutes)</span><input name="min" type="number" step="0.1" min="1" required inputmode="decimal" placeholder="e.g. 32"></label></div>
      <div class="actions"><button class="btn" type="submit">Next</button></div></form>`;
  }
  const v = mount(`<section class="sheet">${header('Recruit statement', `${n.label} · ${n.summary}`, 'SP-3')}<div class="body">${inner}</div></section>`);

  if (n.kind === 'intervals') {
    const paint = (k) => { v.querySelectorAll('.tick .box').forEach((b, i) => b.classList.toggle('on', i < k)); };
    v.querySelectorAll('.tick').forEach((t) => t.addEventListener('click', () => {
      const k = +t.dataset.k; S.report.completed = k; paint(k); $('#next', v).disabled = false;
    }));
    $('#next', v).addEventListener('click', viewStatementB);
    $('#none', v).addEventListener('click', () => { S.report.completed = 0; viewStatementB(); });
  } else if (n.kind === 'continuous_time') {
    let val = n.run_min;
    const set = (x) => { val = Math.max(0, Math.min(n.run_min, x)); $('#val', v).textContent = val; };
    $('#dec', v).addEventListener('click', () => set(val - 1)); $('#inc', v).addEventListener('click', () => set(val + 1));
    $('#next', v).addEventListener('click', () => { S.report.completed = val; viewStatementB(); });
  } else {
    const f = $('#f', v); $('input[name=min]', f).focus();
    f.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!f.reportValidity()) return;
      S.report.distance_km = Number(f.km.value); S.report.duration_min = Number(f.min.value); viewStatementB();
    });
  }
}

const EFFORT = ['', 'Barely moving', 'Very easy', 'Easy', 'Easy', 'Target zone', 'Target zone', 'Getting hard', 'Hard', 'Very hard', 'All out'];
function viewStatementB() {
  const n = S.current.next;
  const v = mount(`<section class="sheet">${header('Recruit statement', `${n.label} · how it felt`, 'SP-3')}<div class="body">
    <h1 class="q">How hard did it feel?</h1><p class="say">Be honest. Easy running sits at 5 or 6.</p>
    <div class="scale" role="group" aria-label="Effort, 1 to 10">${Array.from({ length: 10 }, (_, i) => `<button data-e="${i + 1}" aria-label="${i + 1}, ${EFFORT[i + 1]}">${i + 1}<span class="circle red">${circleSvg}</span></button>`).join('')}</div>
    <div class="scale-words cap"><span>Barely moving</span><span>All out</span></div><p class="word" id="word"></p>
    <label style="display:block;margin-top:22px"><span class="cap">Remarks for the sergeant (pain, tiredness, excuses)</span><textarea class="ruled" id="notes" rows="2" placeholder="Optional"></textarea></label>
    <button type="button" class="link mic" id="speak-notes">${MIC}Speak your remarks</button>
    <div class="actions"><button class="btn" id="file">File report</button><button class="link" id="again">Back</button></div></div></section>`);
  const pick = (e) => {
    S.report.effort = e;
    v.querySelectorAll('.scale .circle').forEach((c, i) => c.classList.toggle('on', i + 1 === e));
    $('#word', v).textContent = EFFORT[e];
  };
  v.querySelectorAll('.scale button').forEach((b) => b.addEventListener('click', () => pick(+b.dataset.e)));
  pick(5);
  voiceInput($('#speak-notes', v), (text) => { const n = $('#notes', v); n.value = (n.value ? n.value + ' ' : '') + text; });
  $('#again', v).addEventListener('click', viewStatementA);
  $('#file', v).addEventListener('click', () => {
    S.report.notes = $('#notes', v).value.trim();
    ask('/api/run', S.report, 'run');
  });
}

/* ============================================================ COUNSELING SESSION */
const SHELL = {
  intake: ['Enlistment review', 'Recruit file opened', 'SP-1'],
  run: ['Counseling session', 'Run statement under review', 'SP-4'],
  skip: ['Counseling session', 'Order refused', 'SP-4'],
  chat: ['Audience with the sergeant', 'Recruit asked for a word', 'SP-5'],
  weighin: ['Weigh-in review', 'Body record under review', 'SP-7'],
};
const MODES = {
  plan: [['continue', 'Continue plan'], ['repeat', 'Repeat level'], ['step_back', 'Step back'], ['advance', 'Advance']],
  intake: [['run_walk', 'Run/walk start'], ['gentle', 'Gentle start'], ['ladder', 'Ladder start']],
  weighin: [['relaxed', 'Limits relaxed'], ['same', 'Barely moved'], ['tight', 'Limits tightened']],
};

function counselShell(kind, ctx) {
  const [t, sub, no] = SHELL[kind], chatOnly = kind === 'chat';
  const body = chatOnly ? '' : `<div class="hazard" id="hazard" hidden><span class="hz"></span><b id="hz-text"></b><span class="hz"></span></div>
    <div class="counsel">
      <div class="block"><h3><i>1</i>Facts</h3><div id="facts"><p class="waiting caret">Pulling the record</p></div></div>
      <div class="block"><h3><i>2</i>Assessment</h3><div id="checks"></div></div>
      <div class="block"><h3><i>3</i>Plan of action</h3><div class="modes" id="modes"></div><p class="typed reason" id="reason"></p><div class="stampbay" id="bay"></div></div></div>`;
  const said = chatOnly && ctx.said ? `<div class="fact"><span class="cap">Recruit stated</span><span class="typed">${esc(ctx.said)}</span></div>` : '';
  const v = mount(`<section class="sheet" id="sheet">${header(t, sub, no)}${body}
    <div class="remarks"><div>${said}<h3 style="margin-top:${said ? 18 : 0}px">Counselor's remarks</h3><p id="rem"><span class="waiting caret"> </span></p></div>
      <div class="sign"><b id="sig"></b><span class="cap">Counselor</span></div></div>
    <div class="diff" id="diff" hidden><h3>Plan of record, changed</h3><div id="drows"></div></div>
    <div class="counsel-foot" id="foot" hidden></div></section>`);
  if (!chatOnly) {
    const lines = kind === 'intake' ? ['Opening your file', 'Sizing you up', 'Setting your limits', 'Building your first orders']
      : ['Pulling the record', 'Reading your statement', 'Checking it against the limits', 'Deciding'];
    let i = 0; clearInterval(S.wait);
    S.wait = setInterval(() => { const w = $('#facts .waiting', v); if (!w) return clearInterval(S.wait); w.textContent = lines[++i % lines.length]; }, 2200);
    $('#facts .waiting', v).textContent = lines[0];
  }
  return v;
}

const PRAISE = new Set(['too_easy', 'getting_faster', 'near_limit']);        // good news: shown with a blue tick, never a scolding
const flagKey = (f) => f.split(':')[0].split(' (')[0];
function flagParts(f) {
  const key = f.split(':')[0].split(' (')[0], detail = f.includes(': ') ? f.slice(f.indexOf(': ') + 2) : '';
  const names = { incomplete: 'Incomplete', too_hard: 'Effort too high', too_fast: 'Pace too fast', overran: 'Overran the order',
    possible_injury: 'Possible injury', skipped: 'Refused orders', implausible_claim: 'Claim not believed', rapid_change: 'Check the scale',
    too_easy: 'Getting stronger', getting_faster: 'Faster than expected', near_limit: 'Near your ceiling' };
  return { title: names[key] || key.replace(/_/g, ' '), detail: detail ? detail.charAt(0).toUpperCase() + detail.slice(1) : '' };
}

function buildSpec(kind, data, ctx) {
  const trace = data.trace || [], st = data.state, find = (n) => trace.find((t) => t.tool === n);
  const spec = { facts: [], checks: [], modes: MODES.plan, chosen: 'continue', stamp: null, reason: '', remarks: data.reply, diff: [], next: st.next, nextLabel: 'Next orders' };

  if (kind === 'intake') {
    const sp = find('save_profile'), r = (sp && sp.result) || {}, a = (sp && sp.args) || {};
    spec.facts = [['Age', `${a.age} years`], ['Weight', `${a.weight_kg} kg`], ['Height', `${a.height_cm} cm`], ['Body fat', `${a.body_fat_pct} %`],
      ['BMI', r.bmi ? String(r.bmi) : '-'], ['Longest run', a.longest_run_km ? `${a.longest_run_km} km` : 'None, cannot run']];
    const lim = r.limits || {};
    spec.checks.push({ tone: lim.caution >= 0.66 ? 'bad' : 'ok', title: `${lim.label ? lim.label[0].toUpperCase() + lim.label.slice(1) : 'Standard'} limits`,
      detail: `Pace ceiling ${lim.pace_ceiling}. Effort ceiling ${lim.effort_ceiling} of 10.` });
    if (r.starts_with_run_walk) spec.checks.push({ tone: 'ok', title: r.gentle_start ? 'Gentle start' : 'Run/walk start', detail: r.gentle_start ? 'Extra-long walk breaks, on purpose.' : 'Intervals first. Nobody runs a kilometre on day one.' });
    (r.flags || []).forEach((f) => spec.checks.push({ tone: 'bad', ...flagParts(f) }));
    const road = (st.estimates || []).filter((e) => !e.cleared && e.weeks);
    if (road.length) spec.checks.push({ tone: 'ok', title: 'The road ahead', detail: road.map((e) => `${e.short} ${e.weeks}`).join(', ') + ' weeks on plan. The marathon is a rough guess. Setbacks stretch it.' });
    spec.modes = MODES.intake;
    spec.chosen = r.gentle_start ? 'gentle' : r.starts_with_run_walk ? 'run_walk' : 'ladder';
    spec.stamp = { tone: 'blue', text: 'Enlisted', small: 'Sgt Pace' };
    spec.reason = r.easy_pace ? `Easy pace ${r.easy_pace}. Never faster than ${r.pace_limit_do_not_beat}.` : '';
    spec.nextLabel = 'View first orders';
  } else if (kind === 'weighin') {
    const wi = find('log_weighin'), r = (wi && wi.result) || {}, L = r.logged || {}, sl = r.since_last || {}, ss = r.since_start || {};
    const sg = (x, u) => `${x > 0 ? '+' : ''}${x} ${u}`;
    spec.facts = [['Weight', `${L.weight_kg} kg`], ['Body fat', `${L.body_fat_pct} %`], ['BMI', String(r.bmi)],
      ['Since last', `${sg(sl.weight_kg, 'kg')}, ${sg(sl.body_fat_pct, '%')}`], ['Since start', `${sg(ss.weight_kg, 'kg')}, ${sg(ss.body_fat_pct, '%')}`]];
    const d = sl.weight_kg;
    spec.checks.push(d < 0 ? { tone: 'ok', title: `Down ${Math.abs(d)} kg`, detail: 'Since the last weigh-in. Keep running.' }
      : d > 0 ? { tone: 'ok', title: `Up ${d} kg`, detail: 'Weight is not the goal. Showing up is.' } : { tone: 'ok', title: 'Holding steady', detail: 'No change. The work continues.' });
    const lb = r.limits_before || {}, la = r.limits || {}, lc = r.limits_change;
    if (lc) spec.checks.push({ tone: lc === 'tightened' ? 'bad' : 'ok', title: lc === 'relaxed' ? 'Limits relaxed' : lc === 'tightened' ? 'Limits tightened' : 'Limits nudged',
      detail: `Pace ceiling ${lb.pace_ceiling} to ${la.pace_ceiling}. Effort ceiling ${lb.effort_ceiling} to ${la.effort_ceiling}.` });
    (r.flags || []).forEach((f) => spec.checks.push({ tone: 'bad', ...flagParts(f) }));
    if ((r.flags || []).length) spec.hazard = 'Check the scale. See a doctor if this is real.';
    spec.modes = MODES.weighin; spec.chosen = r.limits_change === 'relaxed' ? 'relaxed' : r.limits_change === 'tightened' ? 'tight' : 'same';
    spec.stamp = lc === 'tightened' ? { tone: 'red', text: 'Limits tightened', small: 'More body fat, more care' }
      : lc === 'relaxed' ? { tone: 'blue', text: 'Limits relaxed', small: 'Leaner, more room' } : { tone: 'blue', text: 'Recorded', small: 'Body file updated' };
    spec.reason = r.limits ? `Pace ceiling ${r.limits.pace_ceiling}. Effort ceiling ${r.limits.effort_ceiling} of 10. Next weigh-in in two weeks.` : '';
  } else if (kind === 'run' || kind === 'skip') {
    const h = st.history[st.history.length - 1] || {}, lr = find('log_run'), sr = find('skip_run');
    const note = (h.flags || []).find((f) => f.startsWith('recruit_note'));
    spec.facts = [['Run', h.label || '-'], ['Ordered', h.summary || '-']];
    if (h.skipped) spec.facts.push(['Status', 'Not run']); else spec.facts.push(['Completed', `${h.completion_pct}% of the work`], ['Effort', `${h.effort} of 10`]);
    if (h.pace) spec.facts.push(['Pace', h.pace]);
    if (note) spec.facts.push(['Recruit note', note.replace('recruit_note: ', '')]);
    const flags = (h.flags || []).filter((f) => !f.startsWith('recruit_note'));
    const ceiling = h.limits && h.limits.effort != null ? h.limits.effort : 7, key = (f) => f.split(':')[0].split(' (')[0];
    flags.forEach((f) => {
      const parts = flagParts(f);
      if (key(f) === 'too_hard') parts.detail = `Effort ${h.effort} of 10. Target 5 to 6, ceiling ${ceiling}.`;
      if (key(f) === 'too_easy') parts.detail = `Effort ${h.effort} of 10 on a full run. Below the target, so the work gets harder.`;
      spec.checks.push({ tone: PRAISE.has(key(f)) ? 'ok' : 'bad', ...parts });
    });
    const problems = flags.filter((f) => !PRAISE.has(key(f)));
    if (sr && sr.result && sr.result.skipped_in_a_row > 1) spec.checks.push({ tone: 'bad', title: `${sr.result.skipped_in_a_row} refusals in a row`, detail: 'Warning issued.' });
    const ms = lr && lr.result && lr.result.milestone_just_reached;
    if (ms) spec.checks.push({ tone: 'ok', title: 'Qualification earned', detail: ms });
    if (!spec.checks.length) spec.checks.push({ tone: 'ok', title: 'No deficiencies', detail: 'Work completed and effort inside the limit.' });

    const adj = find('adjust_plan');
    const RULES = { incomplete: 'Rule: finish 80% of the work', too_hard: `Rule: effort ceiling ${ceiling} of 10`, too_fast: 'Rule: stay under the pace ceiling',
      overran: 'Rule: stay within 115% of the order', possible_injury: 'Rule: pain stops training', skipped: 'Rule: orders get run' };
    const HAZARDS = { too_hard: `Safety rule tripped: effort ${h.effort} of 10, ceiling is ${ceiling}`, too_fast: 'Safety rule tripped: pace ceiling',
      possible_injury: 'Safety rule tripped: pain reported, stop training', overran: 'Safety rule tripped: over the ordered distance' };
    const PRIORITY = ['possible_injury', 'too_hard', 'too_fast', 'overran', 'incomplete', 'skipped'];  // the most serious rule leads
    const lead = PRIORITY.find((k) => flags.some((f) => key(f) === k));
    const cite = lead ? RULES[lead] : '';
    const hzKey = PRIORITY.find((k) => HAZARDS[k] && flags.some((f) => key(f) === k)); if (hzKey) spec.hazard = HAZARDS[hzKey];
    spec.reason = 'No change needed. The plan continues.';
    spec.stamp = problems.length ? { tone: 'red', text: 'Warning issued', small: cite || 'Plan continues' } : { tone: 'blue', text: 'Cleared', small: 'Plan continues' };
    if (h.skipped) { spec.reason = 'The same order stands until it is run.'; spec.stamp = { tone: 'red', text: 'Order stands', small: RULES.skipped }; }
    if (adj) {
      spec.chosen = adj.args.mode || 'continue'; spec.reason = adj.args.reason || '';
      const STAMPS = { continue: spec.stamp, repeat: { tone: 'red', text: 'Repeat level', small: cite }, step_back: { tone: 'red', text: 'Step back', small: cite }, advance: { tone: 'blue', text: 'Advanced', small: flags.some((f) => key(f) === 'too_easy') ? 'Rule: easy effort moves you up' : 'Clean runs earned it' } };
      spec.stamp = STAMPS[spec.chosen] || spec.stamp;
      if (adj.result && adj.result.applied === false && spec.chosen !== 'continue') {
        spec.stamp = { tone: 'red', text: 'Denied', small: 'Rule: no advance after a bad run' };
        spec.reason = adj.result.blocked || spec.reason;
      }
    }
    const b = new Map((data.before || []).map((u) => [u.id, u]));
    st.upcoming.forEach((u) => { const o = b.get(u.id); if (o && o.summary !== u.summary) spec.diff.push({ label: `Week ${u.week}, Day ${u.day}`, old: o.summary, neu: u.summary }); });
    const was = (data.before_estimates || []).find((e) => !e.cleared), now = (st.estimates || []).find((e) => e.name === (was && was.name));
    if (was && now && !now.cleared && was.weeks !== now.weeks) spec.diff.unshift({ label: `Road to ${now.short}`, old: `${was.weeks} weeks`, neu: `${now.weeks} weeks` });
  } else {
    spec.nextLabel = 'Back to orders';
  }
  return spec;
}

async function playCounsel(v, kind, spec) {
  const sheet = $('#sheet', v);
  playing = true; fast = reduceMotion; clearInterval(S.wait);
  const onClick = (e) => { if (!e.target.closest('button')) skip(); };
  sheet.addEventListener('click', onClick);
  const append = (host, html) => { const t = document.createElement('div'); t.innerHTML = html; const n = t.firstElementChild; host.append(n); return n; };

  if (kind !== 'chat') {
    // 1. facts, typed in
    const facts = $('#facts', v); facts.replaceChildren();
    for (const [k, val] of spec.facts) {
      const row = append(facts, `<div class="fact"><span class="cap">${esc(k)}</span><span class="typed caret"></span></div>`);
      const t = $('.typed', row); await typeInto(t, val, 80); t.classList.remove('caret'); await sleep(90);
    }
    await sleep(260);
    // 2. assessment: each deficiency inked against the rule that caught it
    const checks = $('#checks', v);
    for (const c of spec.checks) {
      const row = append(checks, `<div class="chk ${c.tone}"><span class="box ${c.tone === 'bad' ? 'red' : 'blue'}">${xmark}</span><div><b></b><span class="typed"></span></div></div>`);
      await typeInto($('b', row), c.title, 60);
      $('.box', row).classList.add('on'); await sleep(220);
      if (c.detail) await typeInto($('.typed', row), c.detail, 110);
      await sleep(160);
    }
    if (spec.hazard) {
      const hz = $('#hazard', v); $('#hz-text', v).textContent = spec.hazard; hz.hidden = false; hz.classList.add('in');
      sheet.classList.remove('shake'); void sheet.offsetWidth; if (!fast) sheet.classList.add('shake');
      await sleep(700);
    }
    await sleep(260);
    // 3. plan of action: the decision, then the stamp
    const modes = $('#modes', v);
    spec.modes.forEach(([id, label]) => append(modes, `<div class="mode" data-id="${id}"><span class="box ${spec.stamp && spec.stamp.tone === 'red' ? 'red' : 'blue'}">${xmark}</span>${esc(label)}</div>`));
    await sleep(380);
    const chosen = $(`.mode[data-id="${spec.chosen}"]`, modes);
    if (chosen) { chosen.classList.add('chosen'); $('.box', chosen).classList.add('on'); }
    await sleep(300);
    await typeInto($('#reason', v), spec.reason, 90);
    await sleep(240);
    if (spec.stamp) {
      const s = append($('#bay', v), `<div class="stamp ${spec.stamp.tone}">${esc(spec.stamp.text)}<small>${esc(spec.stamp.small)}</small></div>`);
      s.classList.add('hit');
      sheet.classList.remove('shake'); void sheet.offsetWidth; if (!fast) sheet.classList.add('shake');
      await sleep(520);
    }
  }
  // remarks, in the sergeant's voice, then the signature
  const rem = $('#rem', v); rem.replaceChildren(); const p = document.createElement('span'); rem.append(p);
  let cps = 140;
  const clip = await clipFor(spec);
  if (clip) { cps = Math.max(14, Math.min(45, spec.remarks.length / clip.duration)); playClip(clip); }
  await typeInto(p, spec.remarks, cps);
  await typeInto($('#sig', v), 'Sgt Pace', 12);
  await sleep(260);

  if (spec.diff.length) {
    const d = $('#diff', v); d.hidden = false;
    $('#drows', v).innerHTML = spec.diff.map((r) => `<div class="drow"><span class="cap">${esc(r.label)}</span><span class="typed old">${esc(r.old)}</span><span class="typed new">${esc(r.neu)}</span></div>`).join('');
    await sleep(500);
  }
  const foot = $('#foot', v); foot.hidden = false;
  const n = spec.next;
  foot.innerHTML = `<div class="next">${kind === 'chat' ? '' : `Next orders: <b>${esc(n.label)}</b>, ${esc(n.summary)}`}</div>
    <div class="foot-actions"><button class="btn plain mic" id="talk">${MIC}Talk back</button><button class="btn" id="proceed">${esc(spec.nextLabel)}</button></div>`;
  $('#proceed', v).addEventListener('click', afterSession); $('#proceed', v).focus({ preventScroll: true });
  voiceInput($('#talk', v), (text) => ask('/api/chat', { message: text }, 'chat', { said: text }));
  if (kind !== 'chat') $('.fh p', v).textContent = 'Decision filed';
  playing = false; sheet.removeEventListener('click', onClick); renderBar();
}

async function ask(path, body, kind, ctx = {}) {
  if (playing) return;
  if (kind === 'chat') ctx.said = body.message && !body.message.startsWith('[Intake') ? body.message : '';
  const v = counselShell(kind === 'intake' ? 'intake' : kind, ctx);
  try {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    S.current = data.state;
    const spec = buildSpec(kind, data, ctx);
    spec.speech = voiceOn ? fetchSpeech(data.reply) : null;  // fetched while the sheet fills in
    await playCounsel(v, kind === 'intake' ? 'intake' : kind, spec);
  } catch (e) {
    playing = false; clearInterval(S.wait);
    mount(`<section class="sheet">${header('Clerical error', 'The sergeant is off duty', 'SP-0')}<div class="fail"><h1 class="q">Report not filed.</h1>
      <p class="say" style="margin-inline:auto">${esc(e.message)}</p><button class="btn" id="ret">Return</button></div></section>`);
    $('#ret').addEventListener('click', () => (S.current ? viewOrders() : viewIntake()));
  }
}

/* ============================================================ TRAINING FILE (drawer) */
function openFile() {
  const c = S.current; if (!c) return;
  const weeks = {};
  c.upcoming.forEach((u) => (weeks[u.week] ||= {})[u.day] = u);
  const nextRung = c.ladder.find((r) => !c.milestones.includes(r.name));
  const hist = c.history.slice().reverse();
  const el = $('#file');
  el.innerHTML = `<div class="fh">${INSIGNIA}<div><h2>Training file</h2><p>Recruit 0001</p></div><button class="btn plain" id="close-file" style="padding:10px 16px;font-size:20px">Close</button></div>
    <section><h3>Qualifications</h3><div class="quals">${c.ladder.map((r) => {
      const st = c.milestones.includes(r.name) ? 'done' : nextRung && r.name === nextRung.name ? 'next' : '';
      const est = (c.estimates || []).find((e) => e.name === r.name), eta = est && !est.cleared && est.weeks ? `<span class="eta">${est.rough ? 'about ' : '~'}${est.weeks} wk</span>` : '';
      return `<div class="qual ${st}"><b>${esc(r.name.split(' ')[0])}</b><span>${st === 'done' ? 'Qualified' : st === 'next' ? 'Next' : 'Locked'}</span>${eta}</div>`; }).join('')}</div></section>
    <section><h3>Next two weeks</h3><table class="prog"><tr><th></th><th>Day 1</th><th>Day 2</th><th>Day 3</th></tr>${Object.entries(weeks).map(([w, d]) =>
      `<tr><td class="wk">W${w}</td>${[1, 2, 3].map((k) => `<td class="${d[k] && d[k].id === c.next.id ? 'now' : ''}">${d[k] ? esc(d[k].summary) : ''}</td>`).join('')}</tr>`).join('')}</table></section>
    <section><h3>Service record</h3>${hist.length ? hist.map((h) => `<div class="svc"><b>${esc(h.label)}</b><div class="typed">${h.skipped ? 'Skipped' : `${h.completion_pct}% done · effort ${h.effort}/10`}</div>
      ${(h.flags || []).filter((f) => !f.startsWith('recruit_note')).map((f) => `<div class="typed ${PRAISE.has(flagKey(f)) ? 'good' : 'bad'}">${esc(flagParts(f).title)}</div>`).join('')}</div>`).join('') : '<p class="typed">No runs on file.</p>'}</section>
    <section><h3>Body record</h3>${(c.body.log.slice().reverse().map((e) => `<div class="svc"><b>Week ${e.week}</b><div class="typed">${e.weight_kg} kg · ${e.body_fat_pct} % body fat</div></div>`)).join('')}</section>
    <section><h3>Request an audience</h3><form class="ask" id="ask"><input id="ask-in" placeholder="Ask the sergeant anything" autocomplete="off"><button class="btn plain mic" type="button" id="ask-mic" aria-label="Speak">${MIC}</button><button class="btn" type="submit">Send</button></form></section>
    <footer>${c.public ? '' : `<a class="link" href="/voices">Choose the sergeant's voice</a><br>`}<a class="link" href="/privacy" target="_blank" rel="noopener">Privacy notice</a><br><a class="link" href="/api/export" download>Download my data</a><br><button class="link" id="reset">Reset recruit</button></footer>`;
  el.hidden = false; $('#scrim').hidden = false;
  $('#close-file').focus();
  $('#close-file').addEventListener('click', closeFile);
  $('#ask').addEventListener('submit', (e) => { e.preventDefault(); const m = $('#ask-in').value.trim(); if (!m) return; closeFile(); ask('/api/chat', { message: m }, 'chat'); });
  voiceInput($('#ask-mic'), (text) => { closeFile(); ask('/api/chat', { message: text }, 'chat', { said: text }); });
  let armed = null;
  $('#reset').addEventListener('click', async (e) => {
    const b = e.currentTarget;
    if (!armed) { b.textContent = 'Tap again to wipe the file'; armed = setTimeout(() => { armed = null; b.textContent = 'Reset recruit'; }, 4000); return; }
    clearTimeout(armed);
    try { await fetch('/api/reset', { method: 'POST' }); } catch (err) { b.textContent = 'Reset failed'; return; }
    S.current = null; S.step = 0; S.ans = { can: null }; closeFile(); renderBar(); viewIntake();
  });
}
function closeFile() { $('#file').hidden = true; $('#scrim').hidden = true; }
$('#open-file').addEventListener('click', openFile);
$('#scrim').addEventListener('click', closeFile);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#file').hidden) closeFile(); });

/* ============================================================ BOOT */
fetch('/api/state').then((r) => r.json()).then((s) => {
  S.meta = s;
  if (s.onboarded) { S.current = s; renderBar(); afterSession(); } else viewIntake();
}).catch(() => viewIntake());
})();
