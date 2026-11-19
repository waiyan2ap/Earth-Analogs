/* Base planner: the "Base plan" tab on a Moon/Mars target's panel.
   Data rule: every number shown comes from a named source, is derived from one, or was typed by the user.
   - data/siting.json: site facts (null = no sourced value), NASA constants, and the design parameters (empty until
     the user types them, or the team writes agreed values with a source into the file).
   - data/siting/<site>.json: real elevation patch (+ NASA sunlight and Earth-visibility maps at the lunar south pole),
     made by pipeline/build_site_terrain.py.
   The planner places base zones on the terrain with the RULES below, routes roads along the gentlest slopes, sizes
   power, batteries and habitat, and explains each choice. Anything it cannot compute says which input is missing.
   Hooks in index.html: a 'plan' tab in showSite(), BP.html(t) for the tab body, BP.mount(t) after openPanel(). */
(function () {
'use strict';
const CSS = `
.pl-in{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.pl-in label,.pl-asm label{display:block;font-size:11px;color:var(--mute);margin-bottom:3px}
.pl-in input,.pl-asm input,.pl-fin{width:100%;box-sizing:border-box;padding:7px 8px;border-radius:4px;border:1px solid var(--line);background:rgba(0,0,0,.25);color:var(--text);font:inherit;font-size:13px}
.pl-asm input:placeholder-shown,.pl-fin:placeholder-shown{border-color:var(--gold)}
.pl-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}
.pl-seg{display:flex;gap:4px;flex-wrap:wrap}.pl-seg button{padding:6px 10px;border-radius:4px;border:1px solid var(--line);background:transparent;color:var(--text);font:inherit;font-size:12px;cursor:pointer}
.pl-seg button.on{border-color:var(--acc);background:var(--sel,rgba(124,199,238,.1));font-weight:600}
.pl-chk{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--text)}
.pl-asm{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px;margin-top:6px}
.pl-kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:12px 0}
.pl-kpi div{border:1px solid var(--line);border-radius:6px;padding:7px 8px;background:var(--card)}
.pl-kpi small{display:block;font-size:10.5px;color:var(--mute)}.pl-kpi b{font-size:16px}.pl-kpi span{display:block;font-size:10.5px;color:var(--mute)}
.pl-map{position:relative;border-radius:6px;overflow:hidden;border:1px solid var(--line);background:#000}
.pl-map canvas{display:block;width:100%;height:auto;cursor:crosshair}
.pl-read{font-size:12px;color:var(--mute);margin-top:6px;min-height:17px;font-variant-numeric:tabular-nums}
.pl-leg{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--mute);margin-top:4px}.pl-leg i{flex:1;height:8px;border-radius:4px}
.pl-sug{list-style:none;margin:0;padding:0}.pl-sug li{border-top:1px solid var(--line);padding:8px 0}.pl-sug li:first-child{border-top:0}
.pl-sug b{display:block;font-size:13px}.pl-sug div{font-size:12px;color:var(--mute);line-height:1.45}
.pl-tag{display:inline-block;font-size:10px;border:1px solid var(--line);border-radius:4px;padding:0 6px;margin-left:6px;color:var(--mute);font-weight:400}
.pl-tag.w{border-color:#ff8a65;color:#ff8a65}
.pl-ns{color:var(--gold);font-size:11px}
.pl-t{width:100%;border-collapse:collapse;font-size:12px}.pl-t td,.pl-t th{border-top:1px solid var(--line);padding:5px 4px;text-align:left;vertical-align:top}.pl-t th{color:var(--mute);font-weight:600}
.pl-t td small{display:block;color:var(--mute);font-size:11px}
.pl-d summary{cursor:pointer;color:var(--acc);font-size:12px;margin-top:10px}
.pl-need{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:var(--gold);margin-top:6px}.pl-need span{width:100%}
.pl-need button{font:inherit;font-size:12px;color:var(--gold);background:none;border:1px solid var(--gold);border-radius:4px;padding:3px 8px;cursor:pointer}.pl-need button:hover{background:rgba(227,176,75,.1)}
.pl-grp{border:1px solid var(--line);border-radius:6px;padding:8px 10px 10px;margin-top:8px}.pl-grp[hidden]{display:none}
.pl-gh{display:flex;justify-content:space-between;align-items:baseline;font-size:12px}.pl-gh span{font-size:11px;color:var(--gold)}.pl-gh span.ok{color:var(--ok,#7fcf9a)}
.pl-pres{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0 4px}
.pl-pres label{font-size:12px;color:var(--text);font-weight:600}
.pl-pres select{padding:5px 8px;border-radius:4px;border:1px solid var(--line);background:rgba(0,0,0,.35);color:var(--text);font:inherit;font-size:12px;cursor:pointer}
.pl-pres select:focus{border-color:var(--acc);outline:none}
.pl-pres-cite{font-size:11px;color:var(--mute);margin:2px 0 8px;line-height:1.4}
.pl-pres-cite a{color:var(--acc);text-decoration:none}
.pl-pres-cite a:hover{text-decoration:underline}
.pl-asm small{display:block;font-size:10.5px;color:var(--mute);margin-top:3px;line-height:1.35}
.pl-asm input:invalid{border-color:var(--bad,#ef8f7f)}
@media(max-width:520px){.pl-in{grid-template-columns:1fr 1fr}.pl-kpi{grid-template-columns:1fr 1fr}.pl-asm{grid-template-columns:1fr}}`;
document.head.insertAdjacentHTML('beforeend', `<style>${CSS}</style>`);

const E = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ok = x => typeof x === 'number' && isFinite(x);
const sig2 = x => { if (!ok(x)) return '–'; if (x === 0) return '0'; const p = Math.pow(10, Math.floor(Math.log10(Math.abs(x))) - 1); return (Math.round(x / p) * p).toLocaleString('en-US', { maximumFractionDigits: 2 }); };
const pctS = v => ok(v) ? Math.round(v * 100) + '%' : '–';
const km = m => !ok(m) ? '–' : m >= 1000 ? sig2(m / 1000) + ' km' : sig2(m) + ' m';
const INF = Infinity;
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } } };

const BP = { cfg: null, terr: {}, tid: null, site: null, T: null, c: null, roadCache: null,
  st: { prio: 'safety', preset: '', crew: '', days: '', pw: '', nuc: false, layer: 'relief', view: 'fit', a: {}, fv: {}, hab: {} } };
window.BP = BP;
const saveSt = () => store.set('bp-inputs-v2', { preset: BP.st.preset, crew: BP.st.crew, days: BP.st.days, pw: BP.st.pw, nuc: BP.st.nuc, prio: BP.st.prio, a: BP.st.a, fv: BP.st.fv });

/* ---------- loading ---------- */
async function loadCfg() {
  if (BP.cfg) return;
  const r = await fetch('data/siting.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error('data/siting.json returned HTTP ' + r.status);
  BP.cfg = await r.json();
  const saved = store.get('bp-inputs-v2') || {};  // v2: older presets filled design parameters their cited documents do not give, so inputs saved before that are dropped
  for (const [k, o] of Object.entries(BP.cfg.assumptions)) BP.st.a[k] = ok(o.v) ? o.v : null;  // file values (with source) first
  Object.assign(BP.st, { preset: saved.preset || '', crew: saved.crew ?? '', days: saved.days ?? '', pw: saved.pw ?? '', nuc: !!saved.nuc, prio: saved.prio || 'safety' });
  for (const [k, v] of Object.entries(saved.a || {})) if (k in BP.st.a && ok(v)) BP.st.a[k] = v;     // then this browser's typed values
  BP.st.fv = saved.fv || {};
}
function dec(b64, T) { const s = atob(b64), u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return new T(u.buffer); }
async function loadTerr(id, path) {
  if (id in BP.terr) return BP.terr[id];
  let T = null;
  try { const r = await fetch(path, { cache: 'no-cache' }); if (r.ok) T = prep(await r.json()); } catch (e) { T = null; }
  return (BP.terr[id] = T);
}
function pctLayer(d, key, N) { if (!d[key]) return null; const s = dec(d[key], Uint8Array), o = new Float32Array(N * N); for (let k = 0; k < N * N; k++) o[k] = s[k] === 255 ? NaN : s[k]; return o; }
function prep(d) {
  const N = d.N, c = d.cell_m, raw = dec(d.h, Int16Array), z = new Float32Array(N * N);
  let lo = INF, hi = -INF;
  for (let k = 0; k < N * N; k++) { const v = raw[k]; z[k] = v === -32768 ? NaN : v; if (v !== -32768) { if (v < lo) lo = v; if (v > hi) hi = v; } }
  const slope = new Float32Array(N * N), gx = new Float32Array(N * N), gy = new Float32Array(N * N);
  const Z = (i, j) => { i = Math.max(0, Math.min(N - 1, i)); j = Math.max(0, Math.min(N - 1, j)); return z[i * N + j]; };
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
    const k = i * N + j, dx = (Z(i, j + 1) - Z(i, j - 1)) / ((Math.min(N - 1, j + 1) - Math.max(0, j - 1)) * c), dy = (Z(i + 1, j) - Z(i - 1, j)) / ((Math.min(N - 1, i + 1) - Math.max(0, i - 1)) * c);
    gx[k] = dx; gy[k] = dy; slope[k] = Math.atan(Math.hypot(dx, dy)) * 180 / Math.PI;
  }
  return { ...d, N, c, z, sun: pctLayer(d, 'sun', N), earth: pctLayer(d, 'earth', N), slope, gx, gy, lo, hi };
}

/* ---------- roads: least-cost paths from the habitat over the terrain (Dijkstra, 8 neighbours) ----------
   Cost of a step = length × (1 + (grade ÷ slope limit)²); steps steeper than twice the limit cost 50× more.
   These weights are planner choices, not data. */
function roadTree(T, src, limit) {
  const N = T.N, n = N * N, dist = new Float64Array(n).fill(INF), prev = new Int32Array(n).fill(-1), heap = [];
  const push = (d, k) => { heap.push([d, k]); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
  const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
  const nb = [[-1, 0, 1], [1, 0, 1], [0, -1, 1], [0, 1, 1], [-1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [1, -1, Math.SQRT2], [1, 1, Math.SQRT2]];
  dist[src] = 0; push(0, src);
  while (heap.length) {
    const [d, k] = pop(); if (d > dist[k]) continue;
    const i = (k / N) | 0, j = k % N, zk = T.z[k];
    for (const [di, dj, f] of nb) {
      const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= N || jj >= N) continue;
      const q = ii * N + jj, zq = T.z[q]; if (!(zq === zq)) continue;
      const len = f * T.c, g = Math.atan(Math.abs(zq - zk) / len) * 180 / Math.PI;
      const w = len * (1 + (g / limit) ** 2) * (g > 2 * limit ? 50 : 1), nd = d + w;
      if (nd < dist[q]) { dist[q] = nd; prev[q] = k; push(nd, q); }
    }
  }
  return prev;
}
function roadPath(T, prev, to) {
  const path = []; let k = to, guard = T.N * T.N; while (k >= 0 && guard--) { path.push(k); k = prev[k]; } path.reverse();
  let len = 0, mx = 0; for (let s = 1; s < path.length; s++) { const a = path[s - 1], b = path[s], N = T.N, l = Math.hypot(((a / N) | 0) - ((b / N) | 0), (a % N) - (b % N)) * T.c; len += l; mx = Math.max(mx, Math.atan(Math.abs(T.z[b] - T.z[a]) / l) * 180 / Math.PI); }
  return { path, len, maxGrade: mx };
}

/* ---------- placement on terrain ---------- */
function place(T, site, a, nuclear, prio, hab0, iceFact) {
  const N = T.N, c = T.c, has = k => T.z[k] === T.z[k], ctr = (N - 1) / 2;
  const ij = k => [Math.floor(k / N), k % N], dist = (p, q) => { const [a1, b1] = ij(p), [a2, b2] = ij(q); return Math.hypot(a1 - a2, b1 - b2) * c; };
  const best = f => { let b = -1, bs = INF; for (let k = 0; k < N * N; k++) { if (!has(k)) continue; const s = f(k); if (s < bs) { bs = s; b = k; } } return b; };
  const L = a.slope_limit, half = N * c / 2, warn = [], need = [];
  const steep = (k, lim) => ok(lim) && T.slope[k] > lim;
  // Habitat: flattest ground near the centre (1° of slope counts the same as 1 km of distance), or where the user clicked.
  const hab = hab0 != null && has(hab0) ? hab0 : best(k => { const [i, j] = ij(k), d = Math.hypot(i - ctr, j - ctr) * c; return d > half * 0.7 ? INF : T.slope[k] + d / 1000; });
  const dh = k => dist(k, hab), away = k => dh(k) < 2 * c;  // keep zones off the habitat cell and its neighbours
  // Solar field: most sunlit buildable cell (sunlight map); else highest ground at a pole; else flattest ground near the habitat.
  let solar;
  if (T.sun) solar = best(k => away(k) || steep(k, L) || !(T.sun[k] >= 0) ? INF : -T.sun[k] + dh(k) / 1000 * 3);
  else if (site.polar) solar = best(k => away(k) || steep(k, L) ? INF : -T.z[k] / 20 + dh(k) / 1000 * 5);
  else solar = best(k => away(k) ? INF : T.slope[k] + dh(k) / 1000 * 2);
  const [hi_, hj] = ij(hab), [si, sj] = ij(solar);
  const batt = Math.round(hi_ + (si - hi_) * 0.35) * N + Math.round(hj + (sj - hj) * 0.35);
  // Landing pad: buildable cell at the chosen distance, kept away from the solar field.
  let pad = -1;
  if (ok(a.pad_dist)) {
    pad = best(k => steep(k, L) || dh(k) < a.pad_dist ? INF : (dist(k, solar) < a.pad_dist * 0.8 ? 5 : 0) + (dh(k) - a.pad_dist) / 200 + T.slope[k] / 2);
    if (pad < 0) { pad = best(k => steep(k, L) ? INF : -dh(k)); if (pad >= 0) warn.push(`No buildable ground ${km(a.pad_dist)} from the habitat inside this ${T.km} km patch. The pad is at the farthest buildable spot, ${km(dh(pad))} away.`); }
  } else need.push({ t: 'Landing pad distance', k: 'a:pad_dist' });
  // Antenna: best Earth visibility within 3 km (map), else highest point within 3 km.
  const ant = T.earth ? best(k => dh(k) > 3000 || !(T.earth[k] >= 0) || away(k) ? INF : -T.earth[k] - T.z[k] / 1e5) : best(k => dh(k) > 3000 || away(k) ? INF : -T.z[k]);
  // Ice: nearest never-lit cell on the sunlight map; or lowest ground if a sourced fact says ice is nearby.
  let ice = -1, iceSeen = iceFact;
  if (T.sun) { ice = best(k => T.sun[k] > 1 ? INF : dh(k)); iceSeen = ice >= 0; }
  else if (iceFact === true) ice = best(k => T.z[k]);
  let reactor = -1;
  if (nuclear) { if (ok(a.reactor_dist)) reactor = best(k => dh(k) < a.reactor_dist || dh(k) > a.reactor_dist * 2 || dist(k, solar) < 300 ? INF : T.z[k] / 10 + T.slope[k]); else need.push({ t: 'Reactor distance', k: 'a:reactor_dist' }); }
  const sci = prio === 'science' ? best(k => dh(k) > 5000 || k === solar || away(k) ? INF : -T.slope[k]) : -1;
  const Zs = { hab, solar, batt, pad, ant, ice, reactor, sci };
  // Roads along the gentlest slopes (needs the slope limit); otherwise straight lines.
  const roads = {};
  if (ok(L)) {
    const key = BP.tid + ':' + hab + ':' + L;
    if (!BP.roadCache || BP.roadCache.key !== key) BP.roadCache = { key, prev: roadTree(T, hab, L) };
    for (const k of ['solar', 'pad', 'ant', 'ice', 'reactor', 'sci']) if (Zs[k] >= 0) roads[k] = roadPath(T, BP.roadCache.prev, Zs[k]);
  } else need.push({ t: 'Max slope (also shapes the roads)', k: 'a:slope_limit' });
  const ring = []; for (let k = 0; k < N * N; k++) if (has(k) && dh(k) <= 2500) ring.push(T.slope[k]);
  ring.sort((x, y) => x - y);
  const stats = { medSlope: ring[Math.floor(ring.length / 2)], flatShare: ok(L) ? ring.filter(s => s <= L).length / ring.length : null, relief: T.hi - T.lo };
  return { Zs, roads, stats, warn, need, iceSeen, dh, ij };
}

/* ---------- the model: sizing + rules ---------- */
function model() {
  const cfg = BP.cfg, site = BP.site, T = BP.T, st = BP.st, a = st.a, K = cfg.constants, tid = BP.tid;
  const fvs = st.fv[tid] || {}, F = {};
  for (const [k, x] of Object.entries(site.facts)) { const u = fvs[k]; F[k] = { ...x, val: ok(x.v) ? x.v : typeof x.v === 'boolean' ? x.v : ok(u) ? u : null, user: !ok(x.v) && ok(u) }; }
  const need = [], num = s => s !== '' && ok(+s) && +s > 0 ? +s : null, crew = num(st.crew), days = num(st.days), pw = num(st.pw);
  const margin = ok(a.margin) ? a.margin : 1;
  const P = pw != null ? pw * margin : (crew && ok(a.kw_per_crew) ? crew * a.kw_per_crew * margin : null);
  if (P == null) need.push(crew ? { t: 'Power per crew member (or a power need)', k: 'a:kw_per_crew' } : { t: 'Power need, or crew + power per crew member', k: 'i:pw' });
  const night = F.night_hours ? F.night_hours.val : null, nuclear = st.nuc && ok(night) && ok(a.long_night_h) && night > a.long_night_h;
  const L = T ? place(T, site, a, nuclear, st.prio, st.hab[tid], F.ice_nearby ? F.ice_nearby.val : null) : null;
  if (L) need.push(...L.need);
  let sun = F.sun_fraction ? F.sun_fraction.val : null, sunFromMap = false, earthVis = F.earth_visible ? F.earth_visible.val : null, earthFromMap = false;
  if (L && T.sun && T.sun[L.Zs.solar] >= 0) { sun = Math.max(0.01, T.sun[L.Zs.solar] / 100); sunFromMap = true; }
  if (L && T.earth && L.Zs.ant >= 0 && T.earth[L.Zs.ant] >= 0) { earthVis = T.earth[L.Zs.ant] / 100; earthFromMap = true; }
  let I = null;
  if (BP.body === 'moon') I = K.moon_irradiance.v;
  else { const tau = F.transmission ? F.transmission.val : null; if (ok(tau)) I = 2 * K.mars_irradiance.v * Math.cos(BP.lat * Math.PI / 180) / Math.PI * tau; }
  const solarP = P == null ? null : nuclear ? P * 0.25 : P;
  const area = [solarP, sun, I, a.cell_eff, a.losses, a.rt_eff].every(ok) ? solarP * 1000 * (sun + (1 - sun) / a.rt_eff) / (sun * I * a.cell_eff * (1 - a.losses)) : null;
  const storageSolarOnly = [P, night, a.dod, a.rt_eff].every(ok) ? P * night / (a.dod * a.rt_eff) : null;
  const storage = nuclear ? ([P, a.buffer_h, a.dod, a.rt_eff].every(ok) ? P * a.buffer_h / (a.dod * a.rt_eff) : null) : storageSolarOnly;
  const vol = crew && ok(a.vol_per_crew) ? crew * a.vol_per_crew * (days > 180 ? 1.5 : 1) : null;
  const add = (cond, t, k) => { if (cond) need.push({ t, k }); };
  if (area == null) { add(!ok(sun), 'Sunlit share (site fact)', 'f:sun_fraction'); add(I == null && BP.body === 'mars', 'Sunlight reaching the ground (site fact)', 'f:transmission');
    add(!ok(a.cell_eff), 'Cell efficiency', 'a:cell_eff'); add(!ok(a.losses), 'Other losses', 'a:losses'); add(!ok(a.rt_eff), 'Battery round-trip efficiency', 'a:rt_eff'); }
  if (storage == null) { add(!ok(night), 'Longest dark spell (site fact)', 'f:night_hours'); add(!ok(a.dod), 'Depth of discharge', 'a:dod'); add(!ok(a.rt_eff), 'Battery round-trip efficiency', 'a:rt_eff'); add(nuclear && !ok(a.buffer_h), 'Emergency buffer', 'a:buffer_h'); }
  if (vol == null) { add(!crew, 'Crew', 'i:crew'); add(!ok(a.vol_per_crew), 'Volume per crew member', 'a:vol_per_crew'); }
  add(st.nuc && !ok(a.long_night_h), 'Night length that triggers nuclear', 'a:long_night_h');
  const c = { site, F, a, T, L, body: BP.body, crew, days, P, margin, sun, sunFromMap, earthVis, earthFromMap, night, I, nuclear, allowNuc: st.nuc, area, storage, storageSolarOnly, vol, prio: st.prio, iceNear: L ? L.iceSeen : (F.ice_nearby ? F.ice_nearby.val : null) };
  c.need = need.filter((x, i) => need.findIndex(y => y.k === x.k) === i);
  c.out = RULES.filter(r => r.when(c)).map(r => ({ id: r.id, ...r.say(c) }));
  if (L) L.warn.forEach(w => c.out.push({ id: 'T', title: 'Layout limit', why: w, warn: true }));
  return c;
}
const dOf = (c, key) => c.L && c.L.Zs[key] >= 0 ? km(c.L.dh(c.L.Zs[key])) : null;
const roadTxt = (c, key) => { const r = c.L && c.L.roads[key]; if (!r) return ''; return ` Road ${km(r.len)} along the gentlest slopes, steepest stretch ${Math.round(r.maxGrade)}°${r.maxGrade > c.a.slope_limit ? ', above your slope limit, so it needs grading or switchbacks' : ''}.`; };
const NS = 'No sourced value';
/* Parameter form: groups, plain-words hints, and fractions typed as percent (stored as 0-1 so saved values and siting.json keep working). */
const PGROUPS = [['Power', ['kw_per_crew', 'margin']], ['Solar panels', ['cell_eff', 'losses']], ['Batteries', ['dod', 'rt_eff', 'wh_per_kg']],
  ['Layout', ['pad_dist', 'slope_limit']], ['Habitat', ['vol_per_crew']], ['Nuclear', ['reactor_dist', 'long_night_h', 'buffer_h']]];
const PCT = new Set(['cell_eff', 'losses', 'dod', 'rt_eff']);
const HINT = { kw_per_crew: 'Average electrical power the base uses per person', margin: 'Multiplies the power need; 1 means no margin',
  cell_eff: 'Share of sunlight the panels turn into electricity', losses: 'Dust, wiring, heat and pointing losses together',
  dod: 'How much of each battery you allow yourself to use', rt_eff: 'Energy you get back for each unit you store',
  wh_per_kg: 'Only used for the battery mass hint', pad_dist: 'Keeps rocket blast away from the base',
  slope_limit: 'Steeper ground needs levelling; roads try to stay under it', vol_per_crew: 'Pressurised living volume per person',
  reactor_dist: 'Distance between the fission unit and the habitat', long_night_h: 'Nights longer than this suggest fission power',
  buffer_h: 'Battery reserve when fission is the main supply' };
const plabel = (k, o) => E(String(o.label).replace(/\s*\(0-1\)/, '')) + (PCT.has(k) ? ' (%)' : o.u ? ' (' + E(o.u) + ')' : '');
const pval = (k, v) => ok(v) ? (PCT.has(k) ? +(v * 100).toFixed(4) : v) : '';
function paramForm(A, a) {
  const seen = new Set(), groups = PGROUPS.map(([g, ks]) => [g, ks.filter(k => k in A)]);
  groups.forEach(([, ks]) => ks.forEach(k => seen.add(k)));
  const rest = Object.keys(A).filter(k => !seen.has(k)); if (rest.length) groups.push(['Other', rest]);
  return groups.filter(([, ks]) => ks.length).map(([g, ks]) => `<div class="pl-grp${g === 'Nuclear' ? ' pl-nucg' : ''}" ${g === 'Nuclear' && !BP.st.nuc ? 'hidden' : ''}>
    <div class="pl-gh"><b>${g}</b><span data-g="${ks.join(',')}"></span></div><div class="pl-asm">${ks.map(k => { const o = A[k]; return `<div><label for="pl-a-${k}">${plabel(k, o)}</label>
    <input id="pl-a-${k}" data-k="${k}" type="number" inputmode="decimal" step="any" min="0"${PCT.has(k) ? ' max="100"' : ''} placeholder="enter" value="${pval(k, a[k])}">
    <small>${E(HINT[k] || '')}${o.src ? ' · source: ' + E(o.src) : ''}</small></div>`; }).join('')}</div></div>`).join('');
}
function paramCounts() {
  document.querySelectorAll('#pl-dp .pl-gh span[data-g]').forEach(el => { const ks = el.dataset.g.split(','), n = ks.filter(k => ok(BP.st.a[k])).length;
    el.textContent = n === ks.length ? 'all filled' : `${n} of ${ks.length} filled`; el.className = n === ks.length ? 'ok' : ''; });
}
function jumpTo(k) {
  const [kind, key] = k.split(':'), id = kind === 'a' ? 'pl-a-' + key : kind === 'i' ? 'pl-' + key : null;
  let el = id ? document.getElementById(id) : document.querySelector(`.pl-fin[data-k="${key}"]`);
  if (kind === 'a') { const dp = document.getElementById('pl-dp'); if (dp) dp.open = true; }
  if (!el) return; el.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => el.focus({ preventScroll: true }), 250);
}

/* Rules: when(c) decides if a rule applies, say(c) writes the suggestion. Edit, add or remove rules here.
   Wording only; every number in a suggestion comes from the data files, the maps or the user's inputs. */
const RULES = [
  { id: 'R1', if: 'Always', then: 'Solar field on the most sunlit buildable ground near the habitat', because: 'More sunlight means a smaller array; at the poles high ground avoids long shadows',
    when: c => true, say: c => ({ title: `Solar field on the ${c.site.directions.sun}${dOf(c, 'solar') ? ', ' + dOf(c, 'solar') + ' from the habitat' : ''}`,
      why: `${c.area != null ? `About ${sig2(c.area)} m² of panels${c.nuclear ? ' as backup' : ''}. ` : 'Panel area needs more inputs (see the list above the map). '}${c.sunFromMap ? `That spot is sunlit ${pctS(c.sun)} of the time on NASA's sunlight map. ` : ok(c.sun) ? `Sunlit share used: ${pctS(c.sun)}. ` : ''}${c.site.polar ? 'At the pole the Sun stays low, so panels stand vertical and turn to follow it.' : ''}${roadTxt(c, 'solar')}` }) },
  { id: 'R2', if: 'Terrain file exists', then: 'Habitat on the flattest ground near the centre (or where you click)', because: 'Flat ground needs no levelling and is safer for vehicles',
    when: c => !!c.L, say: c => { const s = c.T.slope[c.L.Zs.hab], lim = c.a.slope_limit; return { title: `Habitat on ground with a ${Math.round(s)}° slope`,
      why: `Within 2.5 km the median slope is ${Math.round(c.L.stats.medSlope)}°${ok(lim) ? ` and ${pctS(c.L.stats.flatShare)} of the ground is under your ${lim}° limit` : ''}. Click the map to try another spot.`, warn: ok(lim) && s > lim }; } },
  { id: 'R4', if: 'Always', then: 'Cover the habitat with regolith (or bury it)', because: 'No thick atmosphere or magnetic field blocks space radiation; regolith is local shielding',
    when: c => true, say: c => ({ title: 'Shield the habitat with regolith', why: `${c.site.atmosphere === 'none' ? 'There is no atmosphere' : 'The atmosphere is thin'}, so it gives little radiation protection.${c.vol != null ? ` Habitat volume about ${sig2(c.vol)} m³ for ${c.crew} crew.` : ''}` }) },
  { id: 'R5', if: 'Pad distance entered', then: 'Landing pad on buildable ground at that distance, away from the solar field', because: 'Rocket exhaust blasts regolith outward at high speed',
    when: c => c.L ? c.L.Zs.pad >= 0 : ok(c.a.pad_dist), say: c => ({ title: `Landing pad ${dOf(c, 'pad') || km(c.a.pad_dist)} from the habitat`, why: `Away from the panels so blasted dust misses them. A berm between pad and base helps.${roadTxt(c, 'pad')}` }) },
  { id: 'R6', if: 'Always', then: 'Battery storage between solar field and habitat', because: 'Short cables, and storage stays close to the crew',
    when: c => true, say: c => ({ title: 'Battery storage between solar field and habitat', why: c.storage != null ? `About ${sig2(c.storage)} kWh usable to cover ${c.nuclear ? 'a ' + sig2(c.a.buffer_h) + ' h emergency buffer' : 'a ' + sig2(c.night) + ' h dark spell'}${ok(c.a.wh_per_kg) ? ` (mass hint about ${sig2(c.storage / c.a.wh_per_kg)} t)` : ''}.` : 'Battery size needs more inputs (see the list above the map).' }) },
  { id: 'R7', if: 'Night longer than your trigger and nuclear allowed', then: 'Fission power as main supply, solar as backup', because: 'Batteries for very long nights become huge',
    when: c => c.nuclear, say: c => ({ title: `Fission power unit${dOf(c, 'reactor') ? ' ' + dOf(c, 'reactor') + ' from the habitat' : ''}`, why: `${c.storageSolarOnly != null ? `The ${sig2(c.night)} h night would need about ${sig2(c.storageSolarOnly)} kWh of batteries with solar alone. ` : ''}${c.L && c.L.Zs.reactor >= 0 ? 'Placed in the lowest nearby ground so terrain helps shield the crew.' : 'Enter a reactor distance to place it.'}` }) },
  { id: 'R8', if: 'Night longer than your trigger and nuclear not allowed', then: 'Warn that storage is very large', because: 'Long nights dominate the design',
    when: c => ok(c.night) && ok(c.a.long_night_h) && c.night > c.a.long_night_h && !c.allowNuc, say: c => ({ title: 'Very large battery bank needed', why: `A ${sig2(c.night)} h night${c.storage != null ? ` needs about ${sig2(c.storage)} kWh` : ' dominates the design'}. Consider allowing nuclear power.`, warn: true }) },
  { id: 'R9', if: 'Never-lit ground on the sunlight map (or a sourced ice fact)', then: 'Ice prospecting toward the nearest permanently shadowed ground', because: 'Local water cuts what must be shipped from Earth',
    when: c => c.iceNear === true, say: c => ({ title: `Ice prospecting toward the ${c.site.directions.ice}${dOf(c, 'ice') ? ', ' + dOf(c, 'ice') + ' away' : ''}`, why: `${c.T && c.T.sun ? 'Nearest cell that NASA\'s sunlight map shows as never lit. Permanent shadow makes ice possible, not certain.' : 'Lowest ground in the patch.'}${roadTxt(c, 'ice')}` }) },
  { id: 'R10', if: 'No ice, or no sourced ice data', then: 'Plan water recycling and resupply', because: 'Without a confirmed local source, water must come with the crew',
    when: c => c.iceNear !== true, say: c => ({ title: 'Recycle water and plan resupply', why: c.iceNear === false ? 'The sunlight map shows no permanently shadowed ground in this patch.' : 'There is no sourced ice data for this site yet.' }) },
  { id: 'R11', if: 'Moon', then: 'Antenna where Earth is visible most of the time; plan a relay', because: 'Direct-to-Earth contact needs line of sight',
    when: c => c.body === 'moon', say: c => ({ title: `Antenna ${c.earthFromMap ? 'on the best Earth-view spot' : 'on the highest point'}${dOf(c, 'ant') ? ', ' + dOf(c, 'ant') + ' away' : ''}`, why: c.earthFromMap ? `Earth is visible ${pctS(c.earthVis)} of the time there on NASA's Earth-visibility map.${c.earthVis < 1 ? ' A relay satellite covers the rest.' : ''}${roadTxt(c, 'ant')}` : `Earth visibility has no sourced value here, so the antenna goes on the highest point within 3 km.${roadTxt(c, 'ant')}` }) },
  { id: 'R12', if: 'Mars', then: 'Antenna mast on high ground; relay through Mars orbiters', because: 'Mars-Earth links normally go through orbiters',
    when: c => c.body === 'mars', say: c => ({ title: 'Antenna mast on high ground, relay through Mars orbiters', why: `Direct links are possible but slow; orbiters carry most data.${roadTxt(c, 'ant')}` }) },
  { id: 'R13', if: 'Mars', then: 'Plan for dust: panel cleaning, extra capacity or nuclear', because: 'Mars dust storms cut sunlight',
    when: c => c.body === 'mars', say: c => ({ title: 'Plan for dust storms', why: c.nuclear ? 'Fission covers power during storms.' : 'Panels need cleaning and extra capacity. Consider allowing nuclear power.', warn: !c.nuclear }) },
  { id: 'R14', if: 'Priority is science', then: 'Science zone at the steepest nearby slopes', because: 'Steep slopes expose rock layers; short traverses mean more science time',
    when: c => c.prio === 'science', say: c => ({ title: `Science zone at the ${c.site.directions.science}${dOf(c, 'sci') ? ', ' + dOf(c, 'sci') + ' away' : ''}`, why: `Keep it away from the pad so samples are not contaminated by exhaust.${roadTxt(c, 'sci')}` }) },
  { id: 'R15', if: 'Mission longer than 180 days', then: 'Increase habitat volume by 50%', because: 'Long stays need more living and storage space',
    when: c => c.days > 180, say: c => ({ title: 'Larger habitat for a long stay', why: 'Volume per crew member is raised by 50% for stays over 180 days (a planner rule, not data).' }) }
];

/* ---------- rendering ---------- */
BP.html = t => `<div id="pl-root"><div class="sub" style="margin-top:12px">Loading base planner…</div></div>`;

BP.mount = async t => {
  const root = document.getElementById('pl-root'); if (!root) return;
  try { await loadCfg(); } catch (e) {
    root.innerHTML = `<div class="mp">The base planner could not read <b>docs/data/siting.json</b>. Open the site through a local server (README, section 1), not by double-clicking the file.</div><div class="note2">Details: ${E(e.message)}</div>`; return;
  }
  const site = BP.cfg.sites[t.id];
  if (!site) { BP.site = null; root.innerHTML = `<div class="mp">${E((BP.cfg.not_assessed || {})[t.id] || 'This site is not assessed yet.')}</div>`; return; }
  BP.tid = t.id; BP.site = site; BP.body = t.body; BP.lat = t.lat;
  BP.T = await loadTerr(t.id, site.terrain);
  if (!document.getElementById('pl-root')) return;
  const T = BP.T;
  if (T && (BP.st.layer === 'sun' || BP.st.layer === 'earth') && !T[BP.st.layer]) BP.st.layer = 'relief';
  const a = BP.st.a, A = BP.cfg.assumptions;
  const layers = [['relief', 'Relief'], ['slope', 'Slope'], ...(T && T.sun ? [['sun', 'Sunlight']] : []), ...(T && T.earth ? [['earth', 'Earth view']] : [])];
  const allPresets = BP.cfg.presets || {};
  const presets = Object.fromEntries(Object.entries(allPresets).filter(([, p]) => !p.body || p.body === BP.body));
  if (BP.st.preset && !presets[BP.st.preset]) BP.st.preset = '';
  const curPres = presets[BP.st.preset];
  const presOpts = Object.entries(presets).map(([k, p]) =>
    `<option value="${k}" ${BP.st.preset === k ? 'selected' : ''}>${E(p.name)} (${p.crew} crew · ${p.days} d · ${p.pw} kW)</option>`
  ).join('');
  const citeHtml = curPres ? `${E(curPres.desc)} · Source: <a class="lnk" href="${E(curPres.url)}" target="_blank" rel="noopener">${E(curPres.src)}</a>` : '';
  root.innerHTML = `
  <div class="pl-pres">
    <label for="pl-preset">Mission preset</label>
    <select id="pl-preset">
      <option value="">Custom (your own inputs)</option>
      ${presOpts}
    </select>
    ${curPres ? `<button class="lnk" id="pl-pres-reset" style="font-size:11px">Re-apply preset</button>` : ''}
  </div>
  <div class="pl-pres-cite" id="pl-pres-cite">${citeHtml}</div>
  <div class="pl-in">
    <div><label for="pl-crew">Crew</label><input id="pl-crew" type="number" min="1" max="50" placeholder="enter" value="${E(BP.st.crew)}"></div>
    <div><label for="pl-days">Days</label><input id="pl-days" type="number" min="1" max="3000" placeholder="enter" value="${E(BP.st.days)}"></div>
    <div><label for="pl-pw">Power need, kW</label><input id="pl-pw" type="number" min="0" step="0.5" placeholder="or use per crew" value="${E(BP.st.pw)}"></div>
  </div>
  <div class="pl-row"><div class="pl-seg" id="pl-prio">${[['safety', 'Safety'], ['science', 'Science'], ['cost', 'Low cost']].map(([k, l]) => `<button data-v="${k}" class="${BP.st.prio === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <label class="pl-chk"><input type="checkbox" id="pl-nuc" ${BP.st.nuc ? 'checked' : ''}> Allow nuclear power</label></div>
  <details class="pl-d" id="pl-dp" ${Object.values(a).some(v => v == null) ? 'open' : ''}><summary>Design parameters</summary>
  ${paramForm(A, a)}<div class="pl-row" style="justify-content:flex-end"><button class="lnk" id="pl-clear" style="font-size:12px">Clear my inputs</button></div></details>
  <div class="pl-kpi" id="pl-kpi"></div><div class="pl-need" id="pl-need"></div>
  ${T ? `<div class="pl-row" style="justify-content:space-between;margin-bottom:6px"><div class="pl-seg" id="pl-layer">${layers.map(([k, l]) => `<button data-v="${k}" class="${BP.st.layer === k ? 'on' : ''}">${l}</button>`).join('')}</div><span><button class="lnk" id="pl-view" style="font-size:12px;margin-right:10px">${BP.st.view === 'all' ? 'Zoom to base' : 'Show whole patch'}</button><button class="lnk" id="pl-reset" style="font-size:12px;margin-right:10px">Reset habitat spot</button><button class="lnk" id="pl-png" style="font-size:12px">Save image</button></span></div>
    <div class="pl-map"><canvas id="pl-cv" aria-label="Map of the base layout on real terrain"></canvas></div><div class="pl-leg" id="pl-leg"></div><div class="pl-read" id="pl-read">Move over the map to read elevation and slope. Click to move the habitat.</div>
    <div class="note2" style="margin-top:6px;display:flex;justify-content:space-between;flex-wrap:wrap"><span>${E(T.km)} × ${E(T.km)} km (${E(T.cell_m)} m/cell) · Elevation: <a class="lnk" href="${E(T.dem.url)}" target="_blank" rel="noopener">${E(T.dem.name)}</a>${T.sun_src ? ` · Sun: <a class="lnk" href="${E(T.sun_src.url)}" target="_blank" rel="noopener">${E(T.sun_src.name)}</a>` : ''}</span><span>Map up: ${E(T.up)}</span></div>`
    : `<div id="pl-svg"></div><div class="note2">Schematic only: no terrain file for this site yet. Make one with <b>python pipeline/build_site_terrain.py --site ${E(t.id)}</b>.</div>`}
  <div class="grp">Suggestions</div><ul class="pl-sug" id="pl-sug"></ul>
  <div class="grp">Site facts</div><div id="pl-facts"></div>
  <details class="pl-d"><summary>Rules used</summary><div id="pl-rules"></div></details>
  <details class="pl-d"><summary>Formulas</summary><div id="pl-form"></div></details>`;
  const on = (id, ev, fn) => { const el = document.getElementById(id); if (el) el.addEventListener(ev, fn); };
  const unpreset = () => {
    if (BP.st.preset) {
      BP.st.preset = '';
      const sel = document.getElementById('pl-preset'); if (sel) sel.value = '';
      const cEl = document.getElementById('pl-pres-cite'); if (cEl) cEl.innerHTML = '';
      const rBtn = document.getElementById('pl-pres-reset'); if (rBtn) rBtn.remove();
    }
  };
  const chg = () => { unpreset(); saveSt(); BP.update(); };
  function applyPreset(k) {
    const p = (BP.cfg.presets || {})[k];
    if (!p || (p.body && p.body !== BP.body)) { unpreset(); saveSt(); BP.update(); return; }
    BP.st.preset = k;
    BP.st.crew = String(p.crew);
    BP.st.days = String(p.days);
    BP.st.pw = String(p.pw);
    BP.st.nuc = !!p.nuc;
    BP.st.prio = p.prio || 'safety';
    for (const [ak, av] of Object.entries(p.a || {})) {
      if (ak in BP.st.a) BP.st.a[ak] = av;
    }
    if (p.site_facts && p.site_facts[BP.tid]) {
      BP.st.fv[BP.tid] = BP.st.fv[BP.tid] || {};
      for (const [fk, fv] of Object.entries(p.site_facts[BP.tid])) {
        BP.st.fv[BP.tid][fk] = fv;
      }
    }
    saveSt();
    BP.mount(t);
  }
  on('pl-preset', 'change', e => applyPreset(e.target.value));
  on('pl-pres-reset', 'click', () => { if (BP.st.preset) applyPreset(BP.st.preset); });
  on('pl-crew', 'input', e => { BP.st.crew = e.target.value; chg(); });
  on('pl-days', 'input', e => { BP.st.days = e.target.value; chg(); });
  on('pl-pw', 'input', e => { BP.st.pw = e.target.value; chg(); });
  on('pl-nuc', 'change', e => { BP.st.nuc = e.target.checked; root.querySelectorAll('.pl-nucg').forEach(g => g.hidden = !BP.st.nuc); chg(); });
  root.querySelectorAll('.pl-asm input').forEach(i => i.addEventListener('input', e => { const k = e.target.dataset.k, v = parseFloat(e.target.value);
    BP.st.a[k] = isFinite(v) && v > 0 && !(PCT.has(k) && v > 100) ? (PCT.has(k) ? v / 100 : v) : null; e.target.setCustomValidity(PCT.has(k) && v > 100 ? 'Enter a percentage from 0 to 100' : ''); chg(); }));
  on('pl-clear', 'click', () => { if (!confirm('Clear the crew, days, power and design parameters you typed in this browser?')) return;
    for (const [k, o] of Object.entries(BP.cfg.assumptions)) BP.st.a[k] = ok(o.v) ? o.v : null; Object.assign(BP.st, { preset: '', crew: '', days: '', pw: '', fv: {} }); saveSt(); BP.mount(t); });
  root.addEventListener('click', e => { const b = e.target.closest('[data-jump]'); if (b) jumpTo(b.dataset.jump); });
  root.querySelectorAll('#pl-prio button').forEach(b => b.addEventListener('click', () => { BP.st.prio = b.dataset.v; root.querySelectorAll('#pl-prio button').forEach(x => x.classList.toggle('on', x === b)); chg(); }));
  root.querySelectorAll('#pl-layer button').forEach(b => b.addEventListener('click', () => { BP.st.layer = b.dataset.v; root.querySelectorAll('#pl-layer button').forEach(x => x.classList.toggle('on', x === b)); BP.base = null; BP.update(true); }));
  on('pl-reset', 'click', () => { delete BP.st.hab[BP.tid]; BP.update(); });
  on('pl-view', 'click', e => { BP.st.view = BP.st.view === 'all' ? 'fit' : 'all'; e.target.textContent = BP.st.view === 'all' ? 'Zoom to base' : 'Show whole patch'; BP.update(true); });
  on('pl-png', 'click', savePng);
  root.addEventListener('input', e => { if (!e.target.classList.contains('pl-fin')) return; const k = e.target.dataset.k, pc = (BP.site.facts[k] || {}).u === '', v = parseFloat(e.target.value) / (pc ? 100 : 1); (BP.st.fv[BP.tid] = BP.st.fv[BP.tid] || {})[k] = isFinite(v) && v >= 0 && !(pc && v > 1) ? v : null; unpreset(); saveSt(); BP.update(true); });
  const cv = document.getElementById('pl-cv');
  if (cv) {
    const cell = e => { const r = cv.getBoundingClientRect(), N = BP.T.N, v = BP.view || { i0: 0, j0: 0, n: N }, j = Math.floor(v.j0 + (e.clientX - r.left) / r.width * v.n), i = Math.floor(v.i0 + (e.clientY - r.top) / r.height * v.n); return i >= 0 && j >= 0 && i < N && j < N ? i * N + j : -1; };
    cv.addEventListener('mousemove', e => { const k = cell(e), o = document.getElementById('pl-read'); if (k < 0 || !o) return; const T = BP.T;
      o.textContent = isFinite(T.z[k]) ? `Elevation ${Math.round(T.z[k]).toLocaleString('en-US')} m · slope ${Math.round(T.slope[k])}°${T.sun ? ' · sunlit ' + (isFinite(T.sun[k]) ? Math.round(T.sun[k]) + '%' : '–') : ''}${T.earth ? ' · Earth visible ' + (isFinite(T.earth[k]) ? Math.round(T.earth[k]) + '%' : '–') : ''}${BP.c && BP.c.L ? ' · ' + km(BP.c.L.dh(k)) + ' from habitat' : ''}` : 'No data here'; });
    cv.addEventListener('click', e => { const k = cell(e); if (k >= 0 && isFinite(BP.T.z[k])) { BP.st.hab[BP.tid] = k; BP.update(); } });
  }
  BP.base = null; BP.update();
};

BP.update = keepFacts => {
  if (!BP.site || !document.getElementById('pl-kpi')) return;
  const c = BP.c = model(), $ = id => document.getElementById(id);
  $('pl-kpi').innerHTML = [['Power need', c.P != null ? sig2(c.P) + ' kW' : '–', c.margin !== 1 ? `×${c.margin} margin` : 'no margin'], ['Solar array', c.area != null ? sig2(c.area) + ' m²' : '–', c.nuclear ? 'backup, 25% of load' : ok(c.sun) ? `sunlit ${pctS(c.sun)}${c.sunFromMap ? ' (map)' : ''}` : 'sunlit share needed'],
    ['Batteries', c.storage != null ? sig2(c.storage) + ' kWh' : '–', c.nuclear ? (ok(c.a.buffer_h) ? `${sig2(c.a.buffer_h)} h buffer` : 'buffer needed') : ok(c.night) ? `${sig2(c.night)} h of dark` : 'dark spell needed'], ['Habitat', c.vol != null ? sig2(c.vol) + ' m³' : '–', c.crew ? `${c.crew} crew${c.days ? ', ' + c.days + ' days' : ''}` : 'crew needed']]
    .map(([l, v, s]) => `<div><small>${l}</small><b>${v}</b><span>${s}</span></div>`).join('');
  $('pl-need').innerHTML = c.need.length ? `<span>To complete the plan, fill in (click to jump):</span>${c.need.map(x => `<button data-jump="${x.k}">${E(x.t)}</button>`).join('')}` : '';
  paramCounts();
  $('pl-sug').innerHTML = c.out.map(o => `<li><b>${E(o.title)}<span class="pl-tag${o.warn ? ' w' : ''}">${o.id}</span></b><div>${E(o.why)}</div></li>`).join('');
  if (!keepFacts) {
    const fval = (k, x) => {
      if (k === 'sun_fraction' && c.sunFromMap) return pctS(c.sun) + ' <small>NASA map, at the solar field</small>';
      if (k === 'earth_visible' && c.earthFromMap) return pctS(c.earthVis) + ' <small>NASA map, at the antenna</small>';
      if (k === 'ice_nearby' && c.T && c.T.sun) return c.iceNear ? 'Yes <small>never-lit ground on the NASA map</small>' : 'No <small>no never-lit ground in this patch</small>';
      if (typeof x.v === 'boolean') return x.v ? 'Yes' : 'No';
      if (ok(x.v)) return x.u === '' && x.v <= 1 ? pctS(x.v) : x.v + ' ' + E(x.u);
      if (k === 'ice_nearby' || k === 'earth_visible') return `<span class="pl-ns">${NS}</span>`;
      const u = (BP.st.fv[BP.tid] || {})[k];
      return `<span class="pl-ns">${NS}${ok(u) ? ', using yours' : ''}</span><input class="pl-fin" data-k="${k}" type="number" step="any" placeholder="your value${x.u ? ' (' + E(x.u) + ')' : x.u === '' ? ' (%)' : ''}" value="${ok(u) ? (x.u === '' ? +(u * 100).toFixed(4) : u) : ''}" style="margin-top:4px">`;
    };
    const tRows = c.L ? [['Median slope within 2.5 km of habitat', Math.round(c.L.stats.medSlope) + '°', 'From the elevation map'], ...(c.L.stats.flatShare != null ? [['Ground under ' + c.a.slope_limit + '° within 2.5 km', pctS(c.L.stats.flatShare), 'From the elevation map and your slope limit']] : []), ['Relief across the patch', sig2(c.L.stats.relief) + ' m', 'Highest minus lowest point on the elevation map']]
      .map(r => `<tr><td>${r[0]}<small>${r[2]}</small></td><td>${r[1]}</td></tr>`).join('') : '';
    const sunRow = `<tr><td>Sunlight on panel<small>${c.body === 'moon' ? 'NASA Moon Fact Sheet (1361 W/m²)' : 'NASA Mars Fact Sheet (586.2 W/m² × 2×cos(lat)/π × transmission)'}</small></td><td>${c.I != null ? sig2(c.I) + ' W/m²' : '–'}</td></tr>`;
    $('pl-facts').innerHTML = `<table class="pl-t">${tRows}${sunRow}${Object.entries(c.site.facts).map(([k, x]) => `<tr><td>${E(x.label)}<small>${E(x.src)}</small></td><td style="min-width:130px">${fval(k, x)}</td></tr>`).join('')}</table>`;
  }
  $('pl-rules').innerHTML = `<table class="pl-t"><tr><th>Rule</th><th>If</th><th>Then</th><th>Because</th></tr>${RULES.map(r => `<tr style="${c.out.some(o => o.id === r.id) ? '' : 'opacity:.45'}"><td>${r.id}</td><td>${E(r.if)}</td><td>${E(r.then)}</td><td>${E(r.because)}</td></tr>`).join('')}</table>`;
  const K = BP.cfg.constants;
  $('pl-form').innerHTML = `<table class="pl-t"><tr><td>Power</td><td>P = (typed kW, or crew × kW per crew member) × margin</td></tr><tr><td>Solar array</td><td>A = P × (f + (1−f)/e) ÷ (f × I × η × (1−L))</td></tr><tr><td>Batteries</td><td>E = P × T_dark ÷ (D × e)</td></tr><tr><td>Habitat</td><td>V = crew × volume per crew member (×1.5 over 180 days)</td></tr><tr><td>Mars sunlight</td><td>I = 2 × 586.2 × cos(lat) ÷ π × share reaching the ground</td></tr><tr><td>Roads</td><td>Cheapest path from the habitat; each step costs length × (1 + (grade ÷ slope limit)²), 50× more above twice the limit</td></tr></table>
    <div class="note2">${Object.values(K).map(k => `<a class="lnk" href="${E(k.url)}" target="_blank" rel="noopener">${E(k.src)}</a> ${k.v} ${E(k.u)}`).join(' · ')}.</div>`;
  if (c.L) drawTerrain(c); else drawSchematic(c);
};

/* ---------- 2D terrain map ---------- */
const ZONES = [['solar', 'Solar field', '#5ec8ff'], ['batt', 'Batteries', '#ffc857'], ['pad', 'Landing pad', '#ffffff'], ['ant', 'Antenna', '#ffffff'], ['ice', 'Ice prospect', '#9be7ff'], ['reactor', 'Fission unit', '#ff8a65'], ['sci', 'Science zone', '#6fd08c'], ['hab', 'Habitat', '#5ec8ff']];
function baseImage(T, layer, limit) {
  const N = T.N, cv = document.createElement('canvas'); cv.width = cv.height = N;
  const g = cv.getContext('2d'), im = g.createImageData(N, N), d = im.data, mars = BP.body === 'mars', lim = ok(limit) ? limit : 15;
  const az = 315 * Math.PI / 180, alt = 45 * Math.PI / 180, ex = Math.max(1, 3000 / Math.max(200, T.hi - T.lo));
  for (let k = 0; k < N * N; k++) {
    const o = k * 4; if (!(T.z[k] === T.z[k])) { d[o] = d[o + 1] = d[o + 2] = 20; d[o + 3] = 255; continue; }
    const sx = -T.gx[k] * ex, sy = T.gy[k] * ex, hs = Math.max(0, (Math.sin(alt) + Math.cos(alt) * (sx * Math.cos(az) + sy * Math.sin(az))) / Math.sqrt(1 + sx * sx + sy * sy));
    let r, gg, b;
    if (layer === 'slope') { const s = T.slope[k], u = Math.min(1, s / (lim * 2)); if (s <= lim) { r = 60 + 150 * u; gg = 170; b = 80; } else { r = 230; gg = 200 - 170 * (u - .5) * 2; b = 60; } }
    else if ((layer === 'sun' || layer === 'earth') && T[layer]) { const s = T[layer][k]; if (!(s >= 0)) { r = gg = b = 40; } else if (s <= 1) { r = 30; gg = 40; b = 120; } else { const u = s / 100; if (layer === 'sun') { r = 70 + 185 * u; gg = 60 + 170 * u; b = 70 - 30 * u; } else { r = 40 + 40 * u; gg = 60 + 160 * u; b = 90 + 160 * u; } } }
    else { const u = (T.z[k] - T.lo) / Math.max(1, T.hi - T.lo); if (mars) { r = 120 + 110 * u; gg = 70 + 80 * u; b = 50 + 50 * u; } else { r = gg = b = 90 + 130 * u; } }
    const m = layer === 'relief' ? 0.35 + 0.85 * hs : 0.55 + 0.5 * hs;
    d[o] = Math.min(255, r * m); d[o + 1] = Math.min(255, gg * m); d[o + 2] = Math.min(255, b * m); d[o + 3] = 255;
  }
  g.putImageData(im, 0, 0); return cv;
}
function drawTerrain(c) {
  const cv = document.getElementById('pl-cv'); if (!cv) return;
  const T = c.T, N = T.N, W = Math.max(240, Math.round(cv.parentElement.clientWidth || 600)), dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.width = W * dpr; cv.height = W * dpr; const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const key = BP.tid + BP.st.layer + c.a.slope_limit; if (!BP.base || BP.baseKey !== key) { BP.base = baseImage(T, BP.st.layer, c.a.slope_limit); BP.baseKey = key; }
  const Z = c.L.Zs, pts = Object.values(Z).filter(k => k >= 0).map(c.L.ij);
  let v = { i0: 0, j0: 0, n: N };
  if (BP.st.view !== 'all') { const is = pts.map(p => p[0]), js = pts.map(p => p[1]), span = Math.max(Math.max(...is) - Math.min(...is), Math.max(...js) - Math.min(...js));
    const n = Math.min(N, Math.max(2000 / T.c, span * 1.35 + 6)), cl = x => Math.max(0, Math.min(N - n, x));
    v = { i0: cl((Math.max(...is) + Math.min(...is)) / 2 + .5 - n / 2), j0: cl((Math.max(...js) + Math.min(...js)) / 2 + .5 - n / 2), n }; }
  BP.view = v;
  g.imageSmoothingEnabled = true; g.drawImage(BP.base, v.j0, v.i0, v.n, v.n, 0, 0, W, W);
  const s = W / v.n, P = k => { const [i, j] = c.L.ij(k); return [(j + .5 - v.j0) * s, (i + .5 - v.i0) * s]; };
  const [hx, hy] = P(Z.hab);
  if (ok(c.a.pad_dist)) { g.setLineDash([4, 4]); g.strokeStyle = 'rgba(255,255,255,.35)'; g.lineWidth = 1; g.beginPath(); g.arc(hx, hy, c.a.pad_dist / T.c * s, 0, 7); g.stroke(); }
  // roads: terrain-following when the slope limit is set, else dashed straight lines
  for (const k of ['solar', 'pad', 'ant', 'ice', 'reactor', 'sci']) {
    if (Z[k] < 0) continue; const r = c.L.roads[k];
    g.setLineDash(r ? [] : [6, 4]); g.lineWidth = r ? 2.2 : 1.4;
    g.strokeStyle = r && r.maxGrade > c.a.slope_limit ? 'rgba(255,138,101,.95)' : 'rgba(255,255,255,.85)';
    g.beginPath(); if (r) r.path.forEach((q, i) => { const [x, y] = P(q); i ? g.lineTo(x, y) : g.moveTo(x, y); }); else { const [x, y] = P(Z[k]); g.moveTo(hx, hy); g.lineTo(x, y); } g.stroke();
  }
  g.setLineDash([]);
  const sz = Math.max(7, W / 60), f1 = Math.max(11, W / 52), f2 = Math.max(10, W / 60), placed = [], todo = [];
  const label = (x, y, t, sub) => todo.push({ x, y, t, sub });
  const flushLabels = () => {
    const hit = r => placed.some(q => r.x < q.x + q.w && r.x + r.w > q.x && r.y < q.y + q.h && r.y + r.h > q.y) || r.x < 0 || r.x + r.w > W || r.y < 0 || r.y + r.h > W;
    todo.sort((p, q) => (q.t === 'Habitat') - (p.t === 'Habitat'));
    for (const L of todo) {
      g.font = `600 ${f1}px system-ui,sans-serif`; let w = g.measureText(L.t).width; g.font = `${f2}px system-ui,sans-serif`; if (L.sub) w = Math.max(w, g.measureText(L.sub).width);
      const h = f1 + (L.sub ? f2 + 3 : 0) + 4; let r = null;
      for (const m of [1, 2, 3.2]) { const off = sz * 1.7 * m, cand = [[L.x - w / 2, L.y + off], [L.x - w / 2, L.y - off - h], [L.x + off, L.y - h / 2], [L.x - off - w, L.y - h / 2], [L.x + off * .7, L.y + off * .7], [L.x - off * .7 - w, L.y + off * .7], [L.x + off * .7, L.y - off * .7 - h], [L.x - off * .7 - w, L.y - off * .7 - h]];
        for (const [cx, cy] of cand) { const q = { x: cx, y: cy, w, h }; if (!hit(q)) { r = q; break; } } if (r) break; }
      if (!r) r = { x: L.x - w / 2, y: L.y + sz * 1.7, w, h }; placed.push(r);
      const mx = r.x + w / 2; g.textAlign = 'center'; g.lineWidth = 3; g.strokeStyle = 'rgba(0,0,0,.8)';
      g.font = `600 ${f1}px system-ui,sans-serif`; g.fillStyle = '#fff'; g.strokeText(L.t, mx, r.y + f1); g.fillText(L.t, mx, r.y + f1);
      if (L.sub) { g.font = `${f2}px system-ui,sans-serif`; g.fillStyle = '#d6deef'; g.strokeText(L.sub, mx, r.y + f1 + f2 + 3); g.fillText(L.sub, mx, r.y + f1 + f2 + 3); }
    }
  };
  for (const [k, name, col] of ZONES) {
    if (Z[k] < 0) continue; const [x, y] = P(Z[k]); g.fillStyle = col; g.strokeStyle = '#000'; g.lineWidth = 1.5; g.beginPath();
    if (k === 'hab') { g.arc(x, y, sz * 1.2, 0, 7); g.fill(); g.stroke(); g.strokeStyle = '#fff'; g.beginPath(); g.arc(x, y, sz * 1.6, 0, 7); g.stroke(); }
    else if (k === 'solar') { g.rect(x - sz * 1.3, y - sz, sz * 2.6, sz * 2); g.fill(); g.stroke(); g.strokeStyle = '#0b3a55'; for (let q = 1; q < 4; q++) { g.beginPath(); g.moveTo(x - sz * 1.3, y - sz + q * sz / 2); g.lineTo(x + sz * 1.3, y - sz + q * sz / 2); g.stroke(); } }
    else if (k === 'pad') { g.arc(x, y, sz * 1.3, 0, 7); g.fillStyle = 'rgba(0,0,0,.45)'; g.fill(); g.strokeStyle = '#fff'; g.lineWidth = 2; g.stroke(); g.fillStyle = '#fff'; g.font = `700 ${sz * 1.4}px system-ui`; g.textAlign = 'center'; g.fillText('H', x, y + sz * .5); }
    else if (k === 'reactor') { g.moveTo(x, y - sz * 1.2); g.lineTo(x + sz * 1.2, y + sz); g.lineTo(x - sz * 1.2, y + sz); g.closePath(); g.fill(); g.stroke(); }
    else if (k === 'ice') { g.moveTo(x, y - sz * 1.2); g.lineTo(x + sz * 1.2, y); g.lineTo(x, y + sz * 1.2); g.lineTo(x - sz * 1.2, y); g.closePath(); g.fill(); g.stroke(); }
    else if (k === 'ant') { g.strokeStyle = '#fff'; g.lineWidth = 2; g.moveTo(x, y + sz); g.lineTo(x, y - sz); g.stroke(); g.beginPath(); g.arc(x, y - sz, 3, 0, 7); g.fill(); }
    else if (k === 'sci') { g.setLineDash([4, 3]); g.strokeStyle = col; g.lineWidth = 2; g.strokeRect(x - sz * 1.4, y - sz, sz * 2.8, sz * 2); g.setLineDash([]); }
    else { g.rect(x - sz * .7, y - sz * .7, sz * 1.4, sz * 1.4); g.fill(); g.stroke(); }
    const r = c.L.roads[k], dist = r ? `${km(r.len)} by road` : km(c.L.dh(Z[k]));
    const d = k === 'hab' ? (c.vol != null ? `${sig2(c.vol)} m³` : '') : k === 'solar' ? (c.area != null ? `${sig2(c.area)} m² · ` : '') + dist : k === 'batt' ? (c.storage != null ? `${sig2(c.storage)} kWh` : '') : dist;
    label(x, y, name, d); placed.push({ x: x - sz * 1.6, y: y - sz * 1.6, w: sz * 3.2, h: sz * 3.2 });
  }
  flushLabels();
  const kmBar = [0.5, 1, 2, 5, 10].reduce((b, x) => x * 1000 <= v.n * T.c / 3 ? x : b, 0.5), bw = kmBar * 1000 / T.c * s;
  g.fillStyle = '#fff'; g.strokeStyle = '#000'; g.lineWidth = 1; g.fillRect(12, W - 18, bw, 4); g.strokeRect(12, W - 18, bw, 4);
  g.font = '11px system-ui'; g.textAlign = 'left'; g.lineWidth = 3; g.strokeStyle = 'rgba(0,0,0,.8)'; g.strokeText(km(kmBar * 1000), 12, W - 24); g.fillText(km(kmBar * 1000), 12, W - 24);
  g.textAlign = 'right'; g.strokeText('↑ ' + T.up, W - 10, 18); g.fillText('↑ ' + T.up, W - 10, 18);
  const lg = document.getElementById('pl-leg'), lim = ok(c.a.slope_limit) ? c.a.slope_limit : 15;
  if (lg) lg.innerHTML = BP.st.layer === 'slope' ? `0° <i style="background:linear-gradient(90deg,#3caa50,#d2aa50 50%,#e6c83c 50%,#e61e3c)"></i> ${lim * 2}°+ · ${ok(c.a.slope_limit) ? 'your limit' : 'colour break (no limit entered)'} ${lim}° in the middle`
    : BP.st.layer === 'sun' ? `<span style="color:#7c8cff">never lit</span> <i style="background:linear-gradient(90deg,#1e2878,#46463c,#ffe628)"></i> sunlit 100% of the time`
    : BP.st.layer === 'earth' ? `<span style="color:#7c8cff">Earth never visible</span> <i style="background:linear-gradient(90deg,#1e2878,#283c5a,#50dcfa)"></i> visible 100% of the time`
    : `${sig2(T.lo)} m <i style="background:linear-gradient(90deg,${BP.body === 'mars' ? '#784632,#e6966e' : '#5a5a5a,#dcdcdc'})"></i> ${sig2(T.hi)} m · shaded relief`;
}

/* ---------- save the map + summary as a PNG (for slides) ---------- */
function savePng() {
  const cv = document.getElementById('pl-cv'), c = BP.c; if (!cv || !c) return;
  const W = cv.width, pad = Math.round(W / 40), lh = Math.round(W / 38), lines = [
    `${c.site.name} · base layout (screening estimate, not a base design)`,
    `Power ${c.P != null ? sig2(c.P) + ' kW' : '–'} · Solar ${c.area != null ? sig2(c.area) + ' m²' : '–'} · Batteries ${c.storage != null ? sig2(c.storage) + ' kWh' : '–'} · Habitat ${c.vol != null ? sig2(c.vol) + ' m³' : '–'}`,
    `Terrain: ${BP.T.dem.name}${BP.T.sun_src ? ' · Sunlight: ' + BP.T.sun_src.name : ''}${BP.T.earth_src ? ' · Earth view: ' + BP.T.earth_src.name : ''}`,
    'Earth Analogs Explorer · NASA Space Apps 2026'];
  const out = document.createElement('canvas'); out.width = W; out.height = W + pad * 2 + lh * lines.length;
  const g = out.getContext('2d'); g.fillStyle = '#05070d'; g.fillRect(0, 0, out.width, out.height); g.drawImage(cv, 0, 0);
  g.textAlign = 'left'; lines.forEach((t, i) => { g.font = `${i === 0 ? '600 ' : ''}${Math.round(lh * 0.62)}px system-ui,sans-serif`; g.fillStyle = i === 0 ? '#e9eef9' : '#93a1bf'; g.fillText(t, pad, W + pad + lh * (i + 0.8), W - pad * 2); });
  const a = document.createElement('a'); a.download = `base-plan-${BP.tid}.png`; a.href = out.toDataURL('image/png'); document.body.appendChild(a); a.click(); a.remove();
}

/* ---------- schematic fallback (no terrain file) ---------- */
function drawSchematic(c) {
  const el = document.getElementById('pl-svg'); if (!el) return;
  const W = 600, H = 400, cx = W / 2, cy = H / 2 - 6, a = c.a, ext = Math.max(a.pad_dist || 0, c.nuclear ? a.reactor_dist || 0 : 0, 600) * 1.1, R = H / 2 - 60;
  const P = (dx, dy) => { const d = Math.hypot(dx, dy); if (!d) return [cx, cy]; const r = R * Math.sqrt(Math.min(1, d / ext)); return [cx + dx / d * r * 1.5, cy + dy / d * r]; };
  const z = [['Habitat', 0, 0, c.vol != null ? `${sig2(c.vol)} m³` : '', '#5ec8ff', 16], ['Solar field', 380, -150, c.area != null ? `${sig2(c.area)} m²` : '', '#5ec8ff', 14], ['Batteries', 170, 40, c.storage != null ? `${sig2(c.storage)} kWh` : '', '#ffc857', 9], ['Antenna', 250, -420, '', '#ffffff', 7]];
  if (ok(a.pad_dist)) z.push(['Landing pad', -a.pad_dist, 0, `${km(a.pad_dist)} away`, '#ffffff', 14]);
  if (c.nuclear && ok(a.reactor_dist)) z.push(['Fission unit', -0.6 * a.reactor_dist, 0.8 * a.reactor_dist, `${km(a.reactor_dist)} away`, '#ff8a65', 10]);
  if (c.iceNear === true) z.push(['Ice prospect', -180, -480, c.site.directions.ice, '#9be7ff', 10]);
  if (c.prio === 'science') z.push(['Science zone', 200, 560, c.site.directions.science, '#6fd08c', 12]);
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;border-radius:6px;background:#1a1f2b" role="img" aria-label="Schematic base layout">
    ${z.slice(1).map(q => { const [x, y] = P(q[1], q[2]); return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#93a1bf" stroke-dasharray="4 4"/>`; }).join('')}
    ${z.map(q => { const [x, y] = P(q[1], q[2]), up = q[2] < -50, dy = up ? -(q[5] + 20) : q[5] + 14; return `<circle cx="${x}" cy="${y}" r="${q[5]}" fill="${q[4]}" opacity=".9"/><text x="${x}" y="${y + dy}" text-anchor="middle" font-size="12" font-weight="600" fill="#e9eef9">${E(q[0])}</text><text x="${x}" y="${y + dy + 13}" text-anchor="middle" font-size="11" fill="#93a1bf">${E(q[3])}</text>`; }).join('')}
    <text x="${W - 10}" y="${H - 10}" text-anchor="end" font-size="11" fill="#93a1bf">schematic, not to terrain or scale</text></svg>`;
}
window.addEventListener('resize', () => { if (BP.c && BP.c.L && document.getElementById('pl-cv')) drawTerrain(BP.c); });
})();
