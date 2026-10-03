/* Sergeant Pace: the 60-second ad.
   A pure function of time: render(t) draws everything, so the page can be scrubbed, paused and re-taken.
   All timings are in seconds and live in the two tables below. */
(() => {
'use strict';

const DUR = 60;
// scene windows
const S = { A: [0, 4.7], B: [4.7, 8.9], C: [8.9, 14.0], D: [14.0, 21.7], E: [21.7, 29.7], F: [29.7, 41.7], G: [41.7, 49.7], H: [49.7, 56.9], I: [56.9, 60] };
// when each voiceover clip starts (clip lengths are in static/ad/vo.json)
const VO = { v1: 0.6, v2: 4.9, v3: 9.1, v4: 14.3, v5: 22.0, v6: 30.3, v7: 42.1, v8: 45.4, v9: 49.9, v10: 57.0 };

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x) => 1 - Math.pow(1 - clamp(x), 4);              // out-quart
const seg = (t, a, d) => clamp((t - a) / d);
const typed = (t, a, text, cps = 40) => text.slice(0, Math.floor(Math.max(0, t - a) * cps));
const mmss = (s) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, '0')}`;
const setText = (el, s) => { if (el.__s !== s) { el.textContent = s; el.__s = s; } };
const show = (el, on) => { const v = on ? 'block' : 'none'; if (el.style.display !== v) el.style.display = v; };
const tf = (el, x = 0, y = 0, s = 1, r = 0) => { el.style.transform = `translate(${x}px,${y}px) rotate(${r}deg) scale(${s})`; };
const el = (html) => { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstElementChild; };
const XMARK = '<svg viewBox="0 0 44 44"><path d="M9 10 36 35"/><path d="M35 9 10 36"/></svg>';
const INS = '<svg viewBox="0 0 48 48"><use href="#insignia"/></svg>';
const hdr = (title, sub, no) => `<div class="fh">${INS}<div><h2>${title}</h2><p>${sub}</p></div><div class="formno">${no}</div></div>`;

const SFX = [];
const sfx = (t, type, v = 1, f = 0) => SFX.push({ t, type, v, f });

/** draw an X into a .box: starts at ts */
function ink(box, t, ts, d = 0.34) {
  const [a, b] = box.querySelectorAll('path');
  a.style.strokeDashoffset = 80 * (1 - seg(t, ts, d * 0.6));
  b.style.strokeDashoffset = 80 * (1 - seg(t, ts + d * 0.4, d * 0.6));
}
/** slam a stamp in at ts */
function stamp(node, t, ts, rot) {
  const p = seg(t, ts, 0.2);
  if (t < ts) { node.style.opacity = 0; return; }
  node.style.opacity = 0.96;
  tf(node, 0, 0, 1 + (1 - ease(p)) * 1.4, rot - (1 - ease(p)) * 9);
}
/** deterministic shake that decays after a hit */
const shake = (t, ts, amp = 18) => (t < ts ? 0 : amp * Math.exp(-(t - ts) * 8) * Math.sin((t - ts) * 78));

const stage = $('#stage');
const scenes = [];
function scene(name, [a, b], html) {
  const node = el(`<div class="scene" id="s${name}">${html}</div>`);
  stage.append(node);
  const sc = { name, a, b, node, render: () => {} };
  scenes.push(sc);
  return sc;
}

/* ============================================================ A: the yes men */
(() => {
  const sc = scene('A', S.A, '');
  const CARDS = [
    [120, 110, -3, "Great job today, champ!", '#ffd6e0', 0.5], [1090, 170, 2.5, "You're doing amazing, sweetie!", '#cde8ff', 0.9],
    [190, 400, 1.5, "Rest day? Totally valid!", '#d6f5d6', 1.3], [1010, 470, -2, "Proud of you no matter what!", '#fff0b8', 1.7],
    [560, 650, -1, "Skip the run, you deserve it!", '#e6d9ff', 2.1],
  ];
  const cards = CARDS.map(([x, y, r, txt, col, t0]) => {
    const c = el(`<div class="yes" style="left:${x}px;top:${y}px"><i style="background:${col}"></i><div><b>${txt}</b><span>Your Coach, now</span></div></div>`);
    const st = el(`<div class="stamp red" style="left:150px;top:36px;font-size:84px">Rejected</div>`);
    c.append(st); sc.node.append(c);
    sfx(t0, 'pop', 0.9); sfx(t0 + 0.75, 'stamp', 0.9);
    return { c, st, x, y, r, t0 };
  });
  const words = ['TIRED', 'OF', 'THE', '<em>YES MEN</em>', 'SURROUNDING', 'YOU?'];
  const tick = el('<div class="abs ticker"></div>'); sc.node.append(tick);
  sc.render = (t) => {
    cards.forEach((k, i) => {
      const pop = ease(seg(t, k.t0, 0.25)), out = ease(seg(t, 3.55 + i * 0.07, 0.5));
      k.c.style.opacity = pop * (1 - out);
      tf(k.c, 0, -out * 1100 + (1 - pop) * 40, 0.6 + 0.4 * pop, k.r - out * 14);
      stamp(k.st, t, k.t0 + 0.75, -9);
    });
    const n = Math.floor(Math.max(0, t - 0.6) / 0.42) + (t >= 0.6 ? 1 : 0);
    tick.innerHTML = words.slice(0, Math.min(words.length, n)).join(' ');
    tick.style.opacity = t >= 0.6 ? 1 : 0;
  };
})();

/* ============================================================ B: yelled at */
(() => {
  const sc = scene('B', S.B, '');
  const bars = el('<div class="abs bars"></div>'); const N = 64; bars.innerHTML = '<i></i>'.repeat(N);
  const l1 = el('<div class="abs stencil center" style="top:90px;font-size:130px;color:var(--paper)"></div>');
  const l2 = el('<div class="abs stencil center" style="top:250px;font-size:420px;color:var(--amber)">Yelled at</div>');
  const l3 = el('<div class="abs stencil center" style="top:700px;font-size:180px;color:var(--paper)">to get motivated?</div>');
  sc.node.append(bars, l1, l2, l3);
  const bs = [...bars.children];
  sfx(4.9, 'whoosh', 0.8); sfx(5.6, 'boom', 1); sfx(6.7, 'boom', 1);
  sc.render = (t) => {
    setText(l1, typed(t, 4.9, 'NEED TO BE', 30));
    const p2 = ease(seg(t, 5.6, 0.16)), p3 = ease(seg(t, 6.7, 0.16));
    l2.style.opacity = t >= 5.6 ? 1 : 0; tf(l2, shake(t, 5.6, 22), shake(t, 5.6, 14) * 0.6, 1 + (1 - p2) * 1.6);
    l3.style.opacity = t >= 6.7 ? 1 : 0; tf(l3, shake(t, 6.7, 16), 0, 1 + (1 - p3) * 1.3);
    const env = 0.22 + 0.78 * Math.max(t > 5.6 ? Math.exp(-(t - 5.6) * 2.2) : 0, t > 6.7 ? Math.exp(-(t - 6.7) * 2.2) : 0, t > 7.6 ? 0.45 + 0.1 * Math.sin(t * 8) : 0);
    bs.forEach((b, i) => { b.style.height = `${(0.18 + 0.82 * Math.abs(Math.sin(i * 1.7 + t * 11) * Math.sin(i * 0.6 + t * 5.3))) * env * 100}%`; });
  };
})();

/* ============================================================ C: the reveal */
(() => {
  const sc = scene('C', S.C, '');
  const q = el('<div class="abs stencil center" style="top:210px;font-size:104px;color:var(--paper)"></div>');
  const a = el('<div class="abs stencil center" style="top:330px;font-size:330px;color:var(--paper)">Sergeant</div>');
  const b = el('<div class="abs stencil center" style="top:610px;font-size:330px;color:var(--amber)">Pace</div>');
  const tag = el('<div class="abs stencil center" style="top:915px;font-size:70px;color:var(--desk-dim);letter-spacing:0.08em"></div>');
  const t1 = el('<div class="tape" style="top:-20px"><i></i></div>'), t2 = el('<div class="tape" style="top:985px;transform:rotate(2deg)"><i></i></div>');
  sc.node.append(t1, t2, q, a, b, tag);
  sfx(9.2, 'whoosh', 0.6); sfx(11.8, 'whoosh', 0.9); sfx(11.9, 'boom', 1.2); sfx(12.35, 'boom', 1);
  sc.render = (t) => {
    setText(q, typed(t, 9.2, 'IF YES... HAVE YOU MET', 28));
    const pa = ease(seg(t, 11.9, 0.16)), pb = ease(seg(t, 12.35, 0.16));
    a.style.opacity = t >= 11.9 ? 1 : 0; tf(a, shake(t, 11.9, 20), 0, 1 + (1 - pa) * 1.5);
    b.style.opacity = t >= 12.35 ? 1 : 0; tf(b, shake(t, 12.35, 20), 0, 1 + (1 - pb) * 1.5);
    const k = ease(seg(t, 11.8, 0.5));
    tf(t1, (1 - k) * -2200, 0, 1, -3); tf(t2, (1 - k) * 2200, 0, 1, 2);
    setText(tag, typed(t, 12.95, 'COUCH TO MARATHON. NO EXCUSES.', 36));
    q.style.opacity = t > 12.0 ? Math.max(0.0, 1 - seg(t, 12.0, 0.4)) * 1 : 1;
  };
})();

/* ============================================================ D: enlist + orders */
(() => {
  const sc = scene('D', S.D, '');
  const choice = (label, sub) => `<div class="choice"><span class="box red">${XMARK}</span><div>${label}<small>${sub}</small></div></div>`;
  const intake = el(`<div class="abs paper" style="left:210px;top:110px;width:1500px;height:800px">${hdr('Enlistment record', 'Individual training file · recruit intake', 'SP-1')}
    <div style="padding:50px 50px 0"><div class="stencil" style="font-size:118px">Can you run right now?</div>
    <div style="display:flex;gap:30px;margin-top:26px">${choice('Cannot run', 'Not yet. Everyone starts somewhere.')}${choice('Can run a little', 'I can jog for a few minutes.')}</div></div></div>`);
  const blocks = [{ t: 'warmup', m: 5 }];
  for (let i = 0; i < 8; i++) { blocks.push({ t: 'run', m: 0.5 }); if (i < 7) blocks.push({ t: 'walk', m: 2 }); }
  blocks.push({ t: 'cooldown', m: 5 });
  const orders = el(`<div class="abs paper" style="left:210px;top:110px;width:1500px;height:800px">${hdr('Training order', 'Week 1, Day 1', 'SP-2')}
    <div style="padding:42px 50px 0"><div class="stencil" style="font-size:112px;white-space:nowrap">8 × (30 sec run + 2 min walk)</div>
    <div class="march" style="margin-top:34px">${blocks.map((b) => `<div class="seg ${b.t}" style="flex:${b.m}">${b.t === 'warmup' || b.t === 'cooldown' ? '5' : b.t === 'walk' ? '2.5' : ''}</div>`).join('')}</div>
    <div class="cap" style="margin:18px 0 0;font-size:26px">Run in blue. Walk hatched. 28 minutes, 4 of them running.</div>
    <div class="btn" style="margin-top:40px">Acknowledge, begin run</div></div></div>`);
  const cursor = el('<svg class="cursor" viewBox="0 0 24 24"><path d="M4 2v19l5-5 3 7 3-1.5-3-6.5h7z" fill="#fff" stroke="#161a11" stroke-width="1.4" stroke-linejoin="round"/></svg>');
  sc.node.append(intake, orders, cursor);
  const box = $('.choice .box', intake), segs = [...orders.querySelectorAll('.seg')], btn = $('.btn', orders);
  sfx(15.4, 'click', 1); sfx(16.35, 'whoosh', 0.8); sfx(20.5, 'click', 1);
  segs.forEach((s, i) => { if (i % 4 === 0) sfx(17.3 + i * 0.07, 'tick', 0.9); });
  sc.render = (t) => {
    const slide = ease(seg(t, 16.35, 0.55));
    tf(intake, -slide * 2300, 0, 1, -slide * 2); tf(orders, (1 - slide) * 2300, 0, 1, (1 - slide) * 2);
    ink(box, t, 15.5);
    const cp = ease(seg(t, 14.0, 1.3)), click = t > 15.4 && t < 15.55 ? 0.85 : 1;
    cursor.style.opacity = t < 16.6 ? 1 : 0; tf(cursor, 1500 + (560 - 1500) * cp, 940 + (530 - 940) * cp, click);
    segs.forEach((s, i) => { const p = ease(seg(t, 17.3 + i * 0.07, 0.22)); s.style.opacity = p; s.style.transform = `scaleY(${p})`; });
    const bp = ease(seg(t, 19.2, 0.4)), press = t > 20.5 ? 0.96 : 1;
    btn.style.opacity = bp; btn.style.filter = t > 20.5 && t < 20.7 ? 'brightness(1.4)' : '';
    tf(btn, 0, (1 - bp) * 40, press);
  };
})();

/* ============================================================ E: the run */
(() => {
  const sc = scene('E', S.E, '');
  const ph = el('<div class="abs phase center" style="top:50px"></div>'), ct = el('<div class="abs count center" style="top:190px"></div>');
  const blocks = [{ t: 'warmup', m: 5 }];
  for (let i = 0; i < 8; i++) { blocks.push({ t: 'run', m: 0.5 }); if (i < 7) blocks.push({ t: 'walk', m: 2 }); }
  blocks.push({ t: 'cooldown', m: 5 });
  const card = el(`<div class="abs paper" style="left:210px;top:740px;width:1500px;padding:26px 40px 38px;position:absolute">
    <div class="stencil" style="display:flex;justify-content:space-between;font-size:44px;margin-bottom:18px"><span>Week 1, Day 1</span><span style="color:var(--caption)">8 × (30 sec run + 2 min walk)</span></div>
    <div style="position:relative"><div class="march" style="height:120px">${blocks.map((b) => `<div class="seg ${b.t}" style="flex:${b.m}"></div>`).join('')}</div><div class="needle"></div></div></div>`);
  const flash = el('<div class="abs" style="inset:0;background:#fff;opacity:0;pointer-events:none"></div>');
  sc.node.append(ph, ct, card, flash);
  const needle = $('.needle', card);
  // the time-lapse: phase, start, end, counts from, to (seconds)
  const P = [['warmup', 21.7, 23.0, 298, 266, 'WARM UP', '#a9af95'], ['run', 23.0, 24.6, 30, 0, 'RUN', '#f0b400'], ['walk', 24.6, 26.2, 150, 0, 'WALK', '#e1e4d2'],
    ['run', 26.2, 27.5, 30, 0, 'RUN', '#f0b400'], ['walk', 27.5, 29.7, 150, 0, 'WALK', '#e1e4d2']];
  P.slice(1).forEach(([, s]) => sfx(s, 'beep', 1, s === 23.0 || s === 26.2 ? 1175 : 880));
  sfx(29.5, 'whoosh', 0.7);
  sc.render = (t) => {
    let cur = P[0];
    for (const p of P) if (t >= p[1]) cur = p;
    const [, s, e, from, to, label, color] = cur, k = seg(t, s, e - s);
    setText(ph, label); ph.style.color = color;
    setText(ct, mmss(from + (to - from) * k));
    needle.style.left = `calc(${ease(seg(t, 21.7, 7.4)) * 100 * 0.62}% - 4px)`;
    const since = t - s; flash.style.opacity = since >= 0 && since < 0.18 && cur !== P[0] ? 0.4 * (1 - since / 0.18) : 0;
    tf(ct, 0, 0, 1 + (since >= 0 && since < 0.2 && cur !== P[0] ? 0.05 * (1 - since / 0.2) : 0));
  };
})();

/* ============================================================ F: the agent decides */
(() => {
  const sc = scene('F', S.F, '');
  const clip = el('<div class="abs" style="left:80px;top:60px;width:1760px;height:960px;overflow:hidden"></div>');
  const modes = [['continue', 'Continue plan'], ['repeat', 'Repeat level'], ['step', 'Step back'], ['adv', 'Advance']];
  const FACTS = [['Run', 'Week 1, Day 1'], ['Ordered', '8 x (30 sec run + 2 min walk)'], ['Completed', '100% of the work'], ['Effort', '9 of 10']];
  const DIFF = [['Week 1, Day 2', '8 x (30 sec run + 2 min walk)', '6 x (30 sec run + 2 min 30 sec walk)'], ['Week 1, Day 3', '8 x (30 sec run + 2 min walk)', '6 x (30 sec run + 2 min 30 sec walk)'],
    ['Week 2, Day 1', '8 x (45 sec run + 1 min 30 sec walk)', '6 x (30 sec run + 2 min 30 sec walk)']];
  const REMARKS = 'Are you trying to retire early?! An effort of 9 out of 10 is not training. I have stepped you back to longer walks.';
  const REASON = 'Pushing too hard. Stepping back to longer walks so you can recover.';
  const sheet = el(`<div class="paper" style="width:1760px;position:absolute;left:0;top:0">
    ${hdr('Counseling session', '<span id="fsub">Run statement under review</span>', 'SP-4')}
    <div style="height:96px;overflow:hidden;position:relative"><div class="hazard" id="haz" style="height:96px"><span class="hz"></span><b>Safety rule tripped: effort 9 of 10, ceiling is 6</b><span class="hz"></span></div></div>
    <div class="counsel">
      <div class="block"><h3><i>1</i>Facts</h3>${FACTS.map(([k]) => `<div class="fact"><span class="cap">${k}</span><span class="typed"></span></div>`).join('')}</div>
      <div class="block"><h3><i>2</i>Assessment</h3><div class="chk" id="chk" style="opacity:0"><span class="box red">${XMARK}</span><div><b></b><span class="typed" style="font-size:28px"></span></div></div></div>
      <div class="block"><h3><i>3</i>Plan of action</h3><div class="modes" id="modes">${modes.map(([id, l]) => `<div class="mode" data-id="${id}"><span class="box red">${XMARK}</span>${l}</div>`).join('')}</div>
        <div class="typed" id="reason" style="font-size:26px;min-height:80px"></div><div class="stamp sm red" id="st" style="left:40px;top:320px;font-size:56px">Step back<small>Rule: effort ceiling 6 of 10</small></div></div></div>
    <div class="remarks"><h3>Counselor's remarks</h3><p id="rem"></p></div>
    <div class="diff"><h3 class="stencil" style="font-size:44px;margin:0 0 10px">Plan of record, changed</h3>${DIFF.map(([l, o, n]) => `<div class="drow"><span class="cap" style="font-size:24px">${l}</span><span class="typed old" style="font-size:26px">${o}<u></u></span><span class="typed new" style="font-size:26px"></span></div>`).join('')}</div></div>`);
  clip.append(sheet);
  const low = el('<div class="lower" style="top:830px">An AI agent that re-plans after every run</div>');
  sc.node.append(clip, low);
  const factEls = [...sheet.querySelectorAll('.fact .typed')], chk = $('#chk', sheet), haz = $('#haz', sheet), modeEls = [...sheet.querySelectorAll('.mode')];
  const st = $('#st', sheet), reason = $('#reason', sheet), rem = $('#rem', sheet), fsub = $('#fsub', sheet), news = [...sheet.querySelectorAll('.new')], olds = [...sheet.querySelectorAll('.old u')];
  // cues, pinned to the measured words of the voice line (it starts at 30.3)
  const C = { facts: [29.95, 30.15, 30.35, 30.6], red: 30.75, chk: 31.85, ink: 32.25, hazard: 32.95, modes: 33.9, step: 34.75, reason: 34.85,
    stamp: 35.2, scroll: 35.9, strike: 36.2, remarks: 36.9, low: 36.0, lowOut: 41.2 };
  sfx(29.7, 'whoosh', 0.7); sfx(C.red, 'click', 1); sfx(C.hazard, 'buzzer', 1); sfx(C.hazard + 0.35, 'stamp', 0.7); sfx(C.step, 'click', 1);
  sfx(C.stamp, 'stamp', 1.2); sfx(C.low, 'whoosh', 0.8); [0, 1, 2].forEach((i) => sfx(C.strike + 0.05 + i * 0.25, 'stamp', 0.6));
  C.facts.forEach((f) => sfx(f, 'tick', 0.8));
  sc.render = (t) => {
    const enter = ease(seg(t, 29.7, 0.5)); clip.style.opacity = enter; tf(clip, 0, (1 - enter) * 90);
    setText(fsub, t > C.scroll ? 'Decision filed' : 'Run statement under review');
    factEls.forEach((f, i) => { setText(f, typed(t, C.facts[i], FACTS[i][1], 70)); if (i === 3) f.style.color = t > C.red ? 'var(--red)' : ''; });
    const hp = ease(seg(t, C.hazard, 0.3)); tf(haz, 0, (1 - hp) * -96); haz.style.opacity = t >= C.hazard ? 1 : 0;
    chk.style.opacity = t >= C.chk ? 1 : 0;
    setText($('b', chk), typed(t, C.chk, 'EFFORT TOO HIGH', 36)); ink($('.box', chk), t, C.ink);
    setText($('.typed', chk), typed(t, C.ink + 0.3, 'Effort 9 of 10. Target 5 to 6, ceiling 6.', 60));
    modeEls.forEach((m, i) => { m.style.opacity = ease(seg(t, C.modes + i * 0.1, 0.25)); const on = m.dataset.id === 'step' && t > C.step; m.style.color = on ? 'var(--rule)' : ''; ink($('.box', m), t, on ? C.step : 999); });
    setText(reason, typed(t, C.reason, REASON, 46));
    stamp(st, t, C.stamp, -7);
    // scroll down to the remarks and the plan diff
    const sc2 = ease(seg(t, C.scroll, 0.55)); tf(sheet, 0, -sc2 * 410);
    setText(rem, typed(t, C.remarks, REMARKS, 42));
    DIFF.forEach((_, i) => { olds[i].style.width = `${ease(seg(t, C.strike + i * 0.25, 0.25)) * 100}%`; setText(news[i], typed(t, C.strike + 0.2 + i * 0.25, DIFF[i][2], 90)); });
    const lp = ease(seg(t, C.low, 0.4)) * (1 - ease(seg(t, C.lowOut, 0.4))); low.style.opacity = lp; tf(low, (1 - lp) * -900);
  };
})();

/* ============================================================ G: talk back */
(() => {
  const sc = scene('G', S.G, '');
  const BARS = 44, wave = (cls) => `<div class="wave ${cls}" style="height:96px">${'<i></i>'.repeat(BARS)}</div>`;
  const mic = '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>';
  const rec = el(`<div class="abs paper" style="left:110px;top:60px;width:1180px;height:500px">${hdr('Recruit statement', 'Knee check', 'SP-3')}
    <div style="padding:34px 48px"><div class="mic">${mic}<span>Talk back</span></div><div style="margin-top:16px">${wave('')}</div>
    <span class="cap" style="margin-top:6px">Transcript</span><div class="typed" style="font-size:44px"></div></div></div>`);
  const sgt = el(`<div class="abs paper" style="left:640px;top:590px;width:1180px;height:440px">${hdr("Counselor's remarks", 'Audience with the sergeant', 'SP-5')}
    <div style="padding:30px 48px">${wave('amber')}<div class="typed" style="font-size:46px;margin-top:8px;min-height:130px"></div></div>
    <div class="stamp sm red" style="right:60px;bottom:50px;font-size:52px">See a doctor<small>Rule: pain stops training</small></div></div>`);
  sc.node.append(rec, sgt);
  const micEl = $('.mic', rec), tr = $('.typed', rec), ws = [...rec.querySelectorAll('.wave i')], wa = [...sgt.querySelectorAll('.wave i')], reply = $('.typed', sgt), st = $('.stamp', sgt);
  sfx(41.9, 'click', 1); sfx(44.9, 'click', 0.8); sfx(45.0, 'whoosh', 0.7); sfx(48.5, 'stamp', 1.1);
  const level = (t, a, b) => (t < a || t > b ? 0.06 : 0.35 + 0.65 * Math.abs(Math.sin(t * 9.1) * Math.sin(t * 3.7)));
  sc.render = (t) => {
    const e1 = ease(seg(t, 41.7, 0.4)); rec.style.opacity = e1; tf(rec, 0, (1 - e1) * 80);
    const e2 = ease(seg(t, 45.0, 0.5)); sgt.style.opacity = e2; tf(sgt, (1 - e2) * 1300, 0, 1, (1 - e2) * 3);
    micEl.className = `mic ${t > 41.9 && t < 44.9 ? 'rec' : ''}`; setText($('span', micEl), t > 41.9 && t < 44.9 ? 'Tap to send' : 'Talk back');
    ws.forEach((b, i) => { b.style.height = `${(0.1 + 0.9 * Math.abs(Math.sin(i * 0.9 + t * 13))) * level(t, 42.1, 44.86) * 100}%`; });
    wa.forEach((b, i) => { b.style.height = `${(0.1 + 0.9 * Math.abs(Math.sin(i * 1.1 + t * 15))) * level(t, 45.4, 49.1) * 100}%`; });
    setText(tr, typed(t, 44.9, 'My knee hurts a little.', 38));
    setText(reply, typed(t, 45.5, 'Then see a doctor. Then get back here.', 24));
    stamp(st, t, 48.5, -6);
  };
})();

/* ============================================================ H: the ladder */
(() => {
  const sc = scene('H', S.H, '');
  const T = [['5K', 'First 5K', 50.3], ['10K', 'Ten kilometres', 51.55], ['21K', 'Half marathon', 52.75], ['42K', 'Marathon', 53.75]];
  const tiles = T.map(([big, small, ts], i) => {
    const n = el(`<div class="tile paper" style="left:${110 + i * 440}px;top:160px"><b>${big}</b><span>${small}</span><div class="stamp blue" style="left:26px;top:238px;font-size:58px">Qualified</div></div>`);
    sc.node.append(n); sfx(ts, 'stamp', 1); return { n, st: $('.stamp', n), ts, i };
  });
  const big = el('<div class="abs stencil center" style="top:610px;font-size:300px;color:var(--amber)">No excuses.</div>');
  sc.node.append(big); sfx(55.2, 'boom', 1.3);
  sc.render = (t) => {
    tiles.forEach((k) => { const p = ease(seg(t, 49.75 + k.i * 0.12, 0.4)); k.n.style.opacity = p; tf(k.n, 0, (1 - p) * 120, 1, k.i % 2 ? 1.2 : -1.2); stamp(k.st, t, k.ts, -8); });
    const p = ease(seg(t, 55.2, 0.16)); big.style.opacity = t >= 55.2 ? 1 : 0; tf(big, shake(t, 55.2, 22), 0, 1 + (1 - p) * 1.5);
  };
})();

/* ============================================================ I: close */
(() => {
  const sc = scene('I', S.I, '');
  const ins = el(`<div class="abs" style="left:810px;top:70px;width:300px;height:300px;color:var(--paper)">${INS.replace('<svg', '<svg style="width:100%;height:100%"')}</div>`);
  const name = el('<div class="abs stencil center" style="top:380px;font-size:300px;color:var(--paper)">Sergeant Pace</div>');
  const fall = el('<div class="abs stencil center" style="top:700px;font-size:110px;color:var(--amber);letter-spacing:0.05em"></div>');
  const small = el('<div class="abs center" style="top:900px;font:600 34px/1.2 var(--form);letter-spacing:0.12em;text-transform:uppercase;color:var(--desk-dim)">An AI running coach · Powered by Gemini</div>');
  const st = el('<div class="stamp blue" style="left:1230px;top:110px;font-size:96px">Enlisted<small>Sgt Pace</small></div>');
  sc.node.append(ins, name, fall, small, st);
  sfx(56.95, 'boom', 1.3); sfx(58.0, 'stamp', 1.2);
  sc.render = (t) => {
    const p = ease(seg(t, 56.9, 0.18)); tf(ins, 0, 0, 1 + (1 - p) * 1.4); tf(name, shake(t, 56.9, 16), 0, 1 + (1 - p) * 1.3);
    setText(fall, typed(t, 57.4, 'FALL IN, RECRUIT.', 14)); small.style.opacity = ease(seg(t, 58.4, 0.6)); stamp(st, t, 58.0, -9);
  };
})();

/* global flashes at the cuts */
const CUTS = [4.7, 8.9, 11.9, 14.0, 21.7, 29.7, 41.7, 49.7, 56.9];
const cutFlash = el('<div style="position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none"></div>'); stage.append(cutFlash);

function render(t) {
  scenes.forEach((s) => { const on = t >= s.a - 0.0001 && t < s.b; show(s.node, on); if (on) s.render(t); });
  let f = 0;
  CUTS.forEach((c) => { const d = t - c; if (d >= 0 && d < 0.1) f = Math.max(f, 0.3 * (1 - d / 0.1)); });
  cutFlash.style.opacity = f;
  $('#tc').textContent = `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;
  $('#bar-i').style.width = `${(t / DUR) * 100}%`;
}

/* ============================================================ audio */
const clips = {}, peaks = {};          // id -> AudioBuffer, and its loudest sample
let audioReady = null;
async function loadAudio(ctx) {
  if (audioReady) return audioReady;
  audioReady = Promise.all(Object.keys(VO).map(async (id) => {
    const buf = await fetch(`/static/ad/${id}.wav`).then((r) => r.arrayBuffer());
    clips[id] = await ctx.decodeAudioData(buf);
    const d = clips[id].getChannelData(0); let pk = 0; for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > pk) pk = a; } peaks[id] = pk || 1;
  }));
  return audioReady;
}
let noiseBuf = null;
const noise = (ctx) => noiseBuf && noiseBuf.sampleRate === ctx.sampleRate ? noiseBuf : (noiseBuf = (() => {
  const b = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate), d = b.getChannelData(0); let s = 1;
  for (let i = 0; i < d.length; i++) { s = (s * 16807) % 2147483647; d[i] = (s / 2147483647) * 2 - 1; } return b; })());

const SYN = {
  stamp(c, o, w, v) { tone(c, o, w, 'sine', 170, 42, 0.2, 0.95 * v); nz(c, o, w, 'lowpass', 1100, 0.09, 0.55 * v); nz(c, o, w, 'highpass', 3000, 0.02, 0.25 * v); },
  boom(c, o, w, v) { tone(c, o, w, 'sine', 95, 28, 0.7, 1.1 * v); nz(c, o, w, 'lowpass', 400, 0.5, 0.6 * v); tone(c, o, w, 'sine', 60, 30, 1.1, 0.5 * v); },
  pop(c, o, w, v) { tone(c, o, w, 'sine', 640, 1040, 0.08, 0.16 * v); },
  beep(c, o, w, v, f) { tone(c, o, w, 'sine', f || 880, f || 880, 0.22, 0.28 * v); },
  click(c, o, w, v) { tone(c, o, w, 'square', 1500, 900, 0.03, 0.16 * v); nz(c, o, w, 'highpass', 4000, 0.02, 0.2 * v); },
  tick(c, o, w, v) { nz(c, o, w, 'highpass', 5000, 0.012, 0.22 * v); },
  whoosh(c, o, w, v) { const n = c.createBufferSource(); n.buffer = noise(c); const f = c.createBiquadFilter(); f.type = 'bandpass'; f.Q.value = 0.9;
    f.frequency.setValueAtTime(250, w); f.frequency.exponentialRampToValueAtTime(3800, w + 0.4); const g = c.createGain(); g.gain.setValueAtTime(0.0001, w);
    g.gain.exponentialRampToValueAtTime(0.35 * v, w + 0.18); g.gain.exponentialRampToValueAtTime(0.0001, w + 0.45); n.connect(f).connect(g).connect(o); n.start(w); n.stop(w + 0.5); },
  buzzer(c, o, w, v) { [150, 157].forEach((fr) => { const os = c.createOscillator(); os.type = 'sawtooth'; os.frequency.value = fr; const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 1300;
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, w); g.gain.linearRampToValueAtTime(0.22 * v, w + 0.02); g.gain.setValueAtTime(0.22 * v, w + 0.42); g.gain.linearRampToValueAtTime(0.0001, w + 0.52);
    os.connect(f).connect(g).connect(o); os.start(w); os.stop(w + 0.55); }); },
  kick(c, o, w, v) { tone(c, o, w, 'sine', 125, 44, 0.24, 0.8 * v); },
  snare(c, o, w, v) { nz(c, o, w, 'bandpass', 1900, 0.13, 0.4 * v); tone(c, o, w, 'triangle', 200, 130, 0.08, 0.22 * v); },
  hat(c, o, w, v) { nz(c, o, w, 'highpass', 7500, 0.04, 0.1 * v); },
  bass(c, o, w, v, f) { const os = c.createOscillator(); os.type = 'sawtooth'; os.frequency.value = f; const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 260;
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, w); g.gain.linearRampToValueAtTime(0.2 * v, w + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, w + 0.42); os.connect(lp).connect(g).connect(o); os.start(w); os.stop(w + 0.45); },
};
function tone(c, o, w, type, f0, f1, dur, vol) { const os = c.createOscillator(); os.type = type; os.frequency.setValueAtTime(f0, w); os.frequency.exponentialRampToValueAtTime(Math.max(1, f1), w + dur);
  const g = c.createGain(); g.gain.setValueAtTime(vol, w); g.gain.exponentialRampToValueAtTime(0.0001, w + dur + 0.02); os.connect(g).connect(o); os.start(w); os.stop(w + dur + 0.05); }
function nz(c, o, w, type, f, dur, vol) { const n = c.createBufferSource(); n.buffer = noise(c); const fl = c.createBiquadFilter(); fl.type = type; fl.frequency.value = f; fl.Q.value = 0.7;
  const g = c.createGain(); g.gain.setValueAtTime(vol, w); g.gain.exponentialRampToValueAtTime(0.0001, w + dur); n.connect(fl).connect(g).connect(o); n.start(w); n.stop(w + dur + 0.02); }

/** the march: drone and ticking until the reveal, then kick-snare-bass, thinning out under the talk-back, building to the end */
function musicEvents() {
  const ev = [], beat = 60 / 118;
  for (let t = 0; t < 8.9; t += beat) ev.push([t, 'hat', 0.55]);
  for (let t = 8.4; t < 11.9; t += beat / 2) ev.push([t, 'snare', 0.25 + 0.5 * ((t - 8.4) / 3.5)]);   // build to the reveal
  for (let k = 0; ; k++) {
    const t = 11.9 + k * beat; if (t >= 56.9) break;
    const sec = t < 41.7 ? 1 : t < 49.7 ? 0.45 : 0.95, i = k % 4;
    if (i === 0 || i === 2) { ev.push([t, 'kick', sec]); ev.push([t, 'bass', sec, i === 0 ? 55 : 41.2]); }
    if ((i === 1 || i === 3) && sec > 0.5) ev.push([t, 'snare', sec * 0.9]);
    if (sec > 0.5) { ev.push([t, 'hat', sec]); ev.push([t + beat / 2, 'hat', sec * 0.8]); }
  }
  for (let t = 54.9; t < 56.9; t += beat / 4) ev.push([t, 'snare', 0.3 + 0.7 * ((t - 54.9) / 2)]);     // roll into the end card
  return ev;
}

function scheduleMix(ctx, out, from, when0) {
  const master = ctx.createGain(); master.gain.value = 0.6;
  const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -16; comp.ratio.value = 6;
  const lim = ctx.createWaveShaper(); lim.curve = Float32Array.from({ length: 2048 }, (_, i) => { const x = (i / 1023.5) - 1; return Math.tanh(1.3 * x) / Math.tanh(1.3) * 0.97; });
  master.connect(comp).connect(lim).connect(out);
  const music = ctx.createGain(), fx = ctx.createGain(), vo = ctx.createGain(); music.connect(master); fx.connect(master); vo.connect(master);
  fx.gain.value = 0.9; vo.gain.value = 1; music.gain.value = 0.55;
  const at = (tt) => when0 + (tt - from);
  // duck the music under the voice
  const windows = Object.entries(VO).map(([id, s]) => [s - 0.05, s + clips[id].duration + 0.2]);
  let mg = 0.55; music.gain.setValueAtTime(windows.some(([a, b]) => from >= a && from <= b) ? 0.2 : 0.55, when0);
  windows.forEach(([a, b]) => { if (b > from) { if (a >= from) { music.gain.setValueAtTime(0.55, at(a) - 0.001); music.gain.linearRampToValueAtTime(0.2, at(a) + 0.12); } music.gain.setValueAtTime(0.2, at(b) - 0.12); music.gain.linearRampToValueAtTime(0.55, at(b)); } });
  Object.entries(VO).forEach(([id, s]) => {
    const buf = clips[id], end = s + buf.duration; if (end <= from) return;
    const src = ctx.createBufferSource(); src.buffer = buf; const vg = ctx.createGain(); vg.gain.value = Math.min(3, 0.85 / peaks[id]); src.connect(vg).connect(vo);
    if (s >= from) src.start(at(s)); else src.start(when0, from - s);
  });
  SFX.forEach(({ t, type, v, f }) => { if (t >= from) SYN[type](ctx, fx, at(t), v, f); });
  musicEvents().forEach(([t, type, v, f]) => { if (t >= from) SYN[type](ctx, music, at(t), v, f); });
  // drone under the opening, then a low bed under the whole thing
  if (from < 56.9) { const d = ctx.createOscillator(); d.type = 'sawtooth'; d.frequency.value = 55; const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 160;
    const g = ctx.createGain(); g.gain.value = 0.05; d.connect(lp).connect(g).connect(music); d.start(when0); d.stop(at(56.9)); }
  return master;
}

/* ============================================================ player */
let ctx = null, t = 0, playing = false, startPerf = 0, from = 0, master = null;

let silent = false;
async function play(withSound = true) {
  if (t >= DUR) t = 0;
  silent = !withSound;
  from = t; startPerf = performance.now() + 80; playing = true;       // the picture never waits for the sound
  $('#b-play').textContent = 'Space: pause'; $('#start').style.display = 'none';
  if (silent) return;
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    // a blocked audio context must not freeze the picture: give it a moment, then play on regardless
    await Promise.race([ctx.resume(), new Promise((r) => setTimeout(r, 600))]); await loadAudio(ctx);
    from = t; startPerf = performance.now() + 80;                       // re-sync to the moment the sound is ready
    master = scheduleMix(ctx, ctx.destination, from, ctx.currentTime + 0.08);
  } catch (e) { window.adMessage && adMessage('Sound failed, playing the picture only: ' + e.message); }
}
function pause() {
  playing = false; $('#b-play').textContent = 'Space: play';
  if (master) { master.gain.setValueAtTime(0, ctx.currentTime); try { master.disconnect(); } catch (e) { /* already gone */ } master = null; }
}
function seek(to) { const was = playing; if (was) pause(); t = clamp(to, 0, DUR); render(t); if (was) play(!silent); }
function tick() {
  if (!playing) return;
  t = from + Math.max(0, performance.now() - startPerf) / 1000;
  if (t >= DUR) { t = DUR; pause(); }
  render(t);
}
// animation frames drive the picture; a timer backs them up in case the browser throttles frames
function loop() { tick(); requestAnimationFrame(loop); }
setInterval(tick, 40);

async function renderMix() {
  const rate = 44100, off = new OfflineAudioContext(2, rate * DUR, rate);
  await loadAudio(off); scheduleMix(off, off.destination, 0, 0);
  return off.startRendering();
}
async function exportAudio() {
  const rate = 44100, buf = await renderMix(), n = buf.length, ch = [buf.getChannelData(0), buf.getChannelData(1)];
  const out = new DataView(new ArrayBuffer(44 + n * 4)), w = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); out.setUint32(4, 36 + n * 4, true); w(8, 'WAVE'); w(12, 'fmt '); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 2, true);
  out.setUint32(24, rate, true); out.setUint32(28, rate * 4, true); out.setUint16(32, 4, true); out.setUint16(34, 16, true); w(36, 'data'); out.setUint32(40, n * 4, true);
  for (let i = 0; i < n; i++) for (let c = 0; c < 2; c++) out.setInt16(44 + (i * 2 + c) * 2, Math.max(-1, Math.min(1, ch[c][i])) * 0x7fff, true);
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([out], { type: 'audio/wav' })); a.download = 'sergeant-pace-ad-audio.wav'; a.click();
}

/* ============================================================ wiring */
function fit() { const s = Math.min(innerWidth / 1920, innerHeight / 1080); stage.style.transform = `translate(${(innerWidth - 1920 * s) / 2}px,${(innerHeight - 1080 * s) / 2}px) scale(${s})`; }
addEventListener('resize', fit); fit();
document.addEventListener('keydown', (e) => {
  if (e.key === ' ') { e.preventDefault(); playing ? pause() : play(!silent); }
  else if (e.key === 'ArrowRight') seek(t + (e.shiftKey ? 10 : 2)); else if (e.key === 'ArrowLeft') seek(t - (e.shiftKey ? 10 : 2));
  else if (e.key === 'r' || e.key === 'R') { pause(); t = 0; play(!silent); } else if (e.key === 'h' || e.key === 'H') document.body.classList.toggle('hidehud');
  else if (e.key === 'f' || e.key === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); }
  else if (e.key === 'e' || e.key === 'E') exportAudio();
});
$('#start').addEventListener('click', (e) => { if (e.target.id !== 'go-silent') play(); });
$('#go-silent').addEventListener('click', () => play(false));
$('#b-play').addEventListener('click', () => (playing ? pause() : play(!silent)));
$('#b-restart').addEventListener('click', () => { pause(); t = 0; play(!silent); });
$('#b-audio').addEventListener('click', exportAudio);

const q = new URLSearchParams(location.search);
document.fonts.ready.then(() => {
  if (q.has('t')) { t = Number(q.get('t')) || 0; $('#start').style.display = 'none'; if (q.has('clean')) document.body.classList.add('hidehud'); }
  render(t); loop();
});
window.__ad = { render, seek, play, pause, exportAudio, renderMix, get t() { return t; } };
})();
