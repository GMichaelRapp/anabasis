'use strict';
/* ================================================================
   Anabasis — app logic
   ================================================================ */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = (p = '') => p + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const nowISO = () => new Date().toISOString();
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const STORE_KEY = 'commonplace.project.v1';
const THEME_KEY = 'commonplace.theme';
const FIRST_VISIT = (() => { try { return localStorage.getItem('commonplace.prefs') === null && localStorage.getItem(STORE_KEY) === null; } catch (e) { return false; } })();
const FORMAT = 2;
const APP_VERSION = '1.0.1';
/* File-format migrations. Each step takes a project at version n and returns it at n + 1.
   Add a step here whenever the shape of the saved file changes, and bump FORMAT. */
const MIGRATIONS = {
  1: p => p, // v1 → v2: nothing moved; v2 files also record the app version that saved them
};
function migrateProject(p) {
  if (!p || typeof p !== 'object') return p;
  let v = +p.format || 1;
  while (v < FORMAT && MIGRATIONS[v]) { p = MIGRATIONS[v](p) || p; v++; }
  p.format = Math.max(v, +p.format || 1);
  return p;
}
const asStr = v => (typeof v === 'string' ? v : v == null ? '' : String(v));

/* ---------------- citation styles ---------------- */
const STYLES = {
  'chicago-notes-bibliography': { label: 'Chicago 18th · notes & bibliography', bib: 'Bibliography' },
  'chicago-shortened-notes-bibliography': { label: 'Chicago 18th · shortened notes & bibliography', bib: 'Bibliography' },
  'chicago-author-date': { label: 'Chicago 18th · author-date', bib: 'References' },
  'apa': { label: 'APA 7th', bib: 'References', ds: true },
  'modern-language-association': { label: 'MLA 9th', bib: 'Works Cited', ds: true },
  'osint': { label: 'OSINT Style Guide v1.5', bib: '', custom: true, note: true },
};
const DEFAULT_STYLE = 'chicago-notes-bibliography';
const cslXml = k => document.getElementById('csl-' + k).textContent;
const LOCALE = document.getElementById('csl-locale').textContent;
for (const k in STYLES) if (!STYLES[k].custom) STYLES[k].note = /class="note"/.test(cslXml(k).slice(0, 2000));

const LOCATOR_LABELS = ['page', 'timestamp', 'chapter', 'section', 'paragraph', 'line', 'figure', 'table', 'volume', 'part', 'note', 'column', 'folio', 'verse', 'book'];

/* ---------------- project state ---------------- */
let P = null;            // the project
let curDocId = null;
let srcVersion = 0;      // bumps when sources change → engines rebuilt
let dirtyFile = false;   // changes since last file save/open
let fileHandle = null;
let lastFileSave = null;
let panelState = null;   // {kind:'note'|'source', id}
let noteTagFilter = null;
let homeOn = false;      // project home dashboard showing

function blankProject() {
  return { app: 'Anabasis', format: FORMAT, id: uid('p'), title: 'Untitled project', created: nowISO(), modified: nowISO(), parts: [], piles: [], docs: [], notes: [], sources: [], entities: [], stats: { days: {}, base: {} }, indexTerms: [], indexOpts: { names: false }, plan: { items: [], hoist: '' }, goal: { kind: '', target: 0, deadline: '', started: '' }, assets: {} };
}
function newDoc(title = 'Untitled document', html = '<p><br></p>') {
  return { id: uid('d'), title, html, style: DEFAULT_STYLE, created: nowISO(), modified: nowISO(), partId: '', order: 0, target: 0,
    meta: { author: '', subtitle: '', date: '', showTitleBlock: false }, snapshots: [], comments: [], role: 'body', status: '', deadline: '',
    layout: { font: 'book', size: '12', spacing: '2', indent: true, paper: 'letter', bib: 'cited', pageNums: true, pdfNotes: 'foot' } };
}
function newNote() {
  const order = P && P.notes && P.notes.length ? Math.max(...P.notes.map(n => +n.order || 0)) + 1 : 0;
  return { id: uid('n'), title: '', body: '', date: '', kind: 'idea', tags: [], sourceId: '', locator: '', label: 'page', color: '', pinned: false, pile: '', order, x: null, y: null, created: nowISO(), modified: nowISO() };
}
function normalize(p) {
  p = migrateProject(p);
  if (p && Array.isArray(p.docs)) p.docs = p.docs.filter(x => x && typeof x === 'object').map(x => Object.assign(x, { html: scrubHTML(asStr(x.html)), title: asStr(x.title), snapshots: Array.isArray(x.snapshots) ? x.snapshots.filter(v => v && typeof v === 'object').map(v => Object.assign(v, { html: scrubHTML(asStr(v.html)), name: asStr(v.name) })) : [] }));
  if (p && Array.isArray(p.notes)) p.notes = p.notes.filter(x => x && typeof x === 'object');
  if (p && Array.isArray(p.sources)) p.sources = p.sources.filter(x => x && typeof x === 'object' && x.id).map(x => Object.assign(x, { csl: x.csl && typeof x.csl === 'object' ? x.csl : {} }));
  if (p) p.title = asStr(p.title) || 'Untitled project';
  const d = blankProject();
  const out = Object.assign(d, p || {});
  out.docs = Array.isArray(out.docs) ? out.docs : [];
  out.notes = Array.isArray(out.notes) ? out.notes : [];
  out.sources = Array.isArray(out.sources) ? out.sources : [];
  out.docs = out.docs.map(x => { const b = newDoc(); return Object.assign(b, x, { meta: Object.assign(b.meta, x.meta || {}), layout: Object.assign(b.layout, x.layout || {}) }); })
    .map(x => (STYLES[x.style] ? x : Object.assign(x, { style: DEFAULT_STYLE })));
  out.notes = out.notes.map(x => Object.assign(newNote(), x, { tags: Array.isArray(x.tags) ? x.tags : [] }));
  out.piles = Array.isArray(out.piles) ? out.piles.filter(x => x && x.id).map(x => ({ id: x.id, name: x.name || 'Pile' })) : [];
  const pileIds = new Set(out.piles.map(x => x.id));
  [...out.notes].sort((a, b) => (a.created || '').localeCompare(b.created || '')).forEach((n, i) => { if (typeof n.order !== 'number' || !isFinite(n.order)) n.order = i; if (!pileIds.has(n.pile)) n.pile = ''; n.pinned = !!n.pinned; n.color = n.color || ''; });
  out.parts = Array.isArray(out.parts) ? out.parts.filter(x => x && x.id).map(x => ({ id: x.id, name: x.name || 'Untitled part', collapsed: !!x.collapsed })) : [];
  const partIds = new Set(out.parts.map(x => x.id));
  out.docs.forEach((x, i) => { if (!partIds.has(x.partId)) x.partId = ''; if (typeof x.order !== 'number') x.order = i; x.target = +x.target || 0;
    x.snapshots = Array.isArray(x.snapshots) ? x.snapshots : []; { let k = 0; x.snapshots.forEach(v => { v.kind = v.kind || (/^Before /.test(v.name || '') ? 'safety' : 'draft'); v.note = v.note || ''; }); [...x.snapshots].reverse().forEach(v => { if (v.kind === 'draft') { if (!v.n) v.n = k + 1; k = Math.max(k, v.n); } }); } x.comments = Array.isArray(x.comments) ? x.comments : []; x.role = x.role || 'body'; x.status = x.status || ''; x.deadline = x.deadline || ''; });
  out.entities = Array.isArray(out.entities) ? out.entities.filter(e => e && e.name).map(e => ({ id: e.id || uid('e'), name: e.name, kind: e.kind || 'person', variants: Array.isArray(e.variants) ? e.variants : [], note: e.note || '' })) : [];
  out.indexTerms = Array.isArray(out.indexTerms) ? out.indexTerms.filter(t => t && t.term).map(t => ({ id: t.id || uid('x'), term: t.term, sub: t.sub || '', match: Array.isArray(t.match) ? t.match : [], see: t.see || '', seeAlso: t.seeAlso || '' })) : [];
  out.indexOpts = Object.assign({ names: false }, out.indexOpts || {});
  // images: keep only assets some document (or a saved version) still uses
  const used = new Set(); [...out.docs.map(d => d.html), ...out.docs.flatMap(d => (d.snapshots || []).map(v => v.html))].forEach(h => (String(h || '').match(/data-asset="([^"]+)"/g) || []).forEach(m => used.add(m.slice(12, -1))));
  out.assets = out.assets && typeof out.assets === 'object' ? Object.fromEntries(Object.entries(out.assets).filter(([k, a]) => used.has(k) && a && typeof a.data === 'string' && a.data.startsWith('data:image/'))) : {};
  ['acronyms', 'acroIgnore', 'places', 'relations'].forEach(k => { out[k] = Array.isArray(out[k]) ? out[k] : []; }); out.relLayout = out.relLayout && typeof out.relLayout === 'object' ? out.relLayout : {};
  const g = out.goal && typeof out.goal === 'object' ? out.goal : {};
  out.goal = { kind: String(g.kind || ''), target: Math.max(0, +g.target || 0), deadline: /^\d{4}-\d\d-\d\d$/.test(g.deadline || '') ? g.deadline : '', started: g.started || '' };
  const pl = out.plan && typeof out.plan === 'object' ? out.plan : {};
  out.plan = { hoist: pl.hoist || '', items: Array.isArray(pl.items) ? pl.items.filter(i => i && i.id).map((i, k) => ({ id: i.id, parent: i.parent || '', order: typeof i.order === 'number' ? i.order : k, title: i.title || '', type: i.type in { section: 1, claim: 1, evidence: 1, counter: 1, question: 1, idea: 1 } ? i.type : 'section', synopsis: i.synopsis || '', status: i.status || '', target: +i.target || 0, notes: Array.isArray(i.notes) ? i.notes : [], sources: Array.isArray(i.sources) ? i.sources : [], docId: i.docId || '', collapsed: !!i.collapsed })) : [] };
  out.stats = out.stats && typeof out.stats === 'object' ? out.stats : {}; out.stats.days = out.stats.days || {}; out.stats.base = out.stats.base || {};
  out.sources = out.sources.filter(s => s && s.id).map(s => Object.assign({ id: s.id, csl: s.csl || {}, created: s.created || nowISO(), modified: s.modified || nowISO() }, s.osint && typeof s.osint === 'object' ? { osint: s.osint } : {}, typeof s.annotation === 'string' && s.annotation ? { annotation: s.annotation } : {}, typeof s.transcript === 'string' && s.transcript ? { transcript: s.transcript } : {}, s.pdfName ? { pdfName: s.pdfName } : {}, s.pdfOffset ? { pdfOffset: +s.pdfOffset || 0 } : {}));
  return out;
}
function sampleProject() {
  const p = blankProject();
  p.title = 'My research';
  const s1 = { id: uid('s'), created: nowISO(), modified: nowISO(), csl: { type: 'book', title: 'The Guns of August', author: [{ family: 'Tuchman', given: 'Barbara W.' }], publisher: 'Macmillan', 'publisher-place': 'New York', issued: { 'date-parts': [[1962]] } } };
  const s2 = { id: uid('s'), created: nowISO(), modified: nowISO(), csl: { type: 'article-journal', title: 'Why States Act through Proxies', author: [{ family: 'Mumford', given: 'Andrew' }], 'container-title': 'Survival', volume: '55', issue: '2', page: '40–61', issued: { 'date-parts': [[2013]] }, DOI: '10.1080/00396338.2013.784469' } };
  p.sources.push(s1, s2);
  const n1 = Object.assign(newNote(), { title: 'Plans outrun politics', kind: 'paraphrase', tags: ['war plans', 'WWI'], sourceId: s1.id, locator: '17–18', body: 'Tuchman argues the Schlieffen Plan had acquired a momentum of its own. Mobilization timetables left statesmen almost no room to negotiate once the machinery started.' });
  const n2 = Object.assign(newNote(), { title: 'Proxy war — deniability', kind: 'idea', tags: ['proxy war'], sourceId: s2.id, locator: '42', body: 'Possible thread: proxies let a state **buy deniability** cheaply. Compare cases across regions and decades.' });
  const n3 = Object.assign(newNote(), { title: 'Germany declares war on Russia', kind: 'summary', date: '1914-08-01', tags: ['WWI'], sourceId: s1.id, locator: '73', body: 'A dated note. Notes with a date line up on the board’s Timeline view, and Insert → Timeline turns them into a figure.' });
  p.notes.push(n1, n2, n3);
  const c = (id, loc) => citeHTML([{ id, locator: loc, label: 'page' }]);
  const d = newDoc('Welcome — try me', '');
  d.html = `<h1>Welcome to Anabasis</h1>
<p>Anabasis keeps your documents, notes and sources together in one project. <b>Your work stays on this computer.</b> There’s no account and no server: the browser keeps a working copy as you type, and <b>Save</b> writes the whole project to one .json file wherever you choose. Anabasis goes online only when you look up a source by DOI, ISBN or web address, or back up to GitHub.</p>
<h2>Citations</h2>
<p>This sample document shows how citations work. Click a highlighted marker to edit it, or use <b>“ Cite</b> in the toolbar to add one. The first citation of Tuchman prints in full, and the second becomes a short note.${c(s1.id, '3')}</p>
<p>Proxy strategies let a state act while keeping its distance from the outcome.${c(s2.id, '41–42')} Notes and the bibliography below rebuild as you write.${fnHTML('This is a text footnote, a discursive aside rather than a citation. It is numbered with the citation notes.')}</p>
<p>Plans built for speed can crowd out diplomacy.${c(s1.id, '17–18')}</p>
<p>Change the style in the menu next to the title (try <i>Chicago author-date</i>, <i>APA</i>, <i>MLA</i>, or the <i>OSINT Style Guide</i>) and every citation reformats.</p>
<h2>Figures</h2>
<p>Choose the figure button in the toolbar, then <i>Chart from data</i>, and pick this table from the Data menu. Maps, timelines and relationship maps live in the same menu.</p>
<figure class="tbl"><table><thead><tr><th>Week</th><th>Words drafted</th><th>Words cut</th></tr></thead><tbody><tr><td>1</td><td>2,400</td><td>300</td></tr><tr><td>2</td><td>3,100</td><td>900</td></tr><tr><td>3</td><td>1,800</td><td>1,600</td></tr><tr><td>4</td><td>3,600</td><td>700</td></tr></tbody></table><figcaption>An example writing log (invented numbers)</figcaption></figure>
<h2>Checks</h2>
<p>The Outline tab reads over your shoulder. This paragraph trips two checks on purpose: the NATO summit was a turning point, and the delegation flew in from Kiev. Open the Outline tab to see them, with one-click fixes.</p>
<p>When you’re done exploring, delete this document and the sample notes and sources, or start a clean project with <b>New</b>. Help (the <b>?</b> button) has the full guide and can replay the tour.</p>`;
  p.docs.push(d);
  p.acroIgnore = ['DOI', 'ISBN', 'APA', 'MLA', 'OSINT'];
  return p;
}

/* ---------------- persistence ----------------
   The project file (JSON) is the real copy. The browser keeps a working copy in IndexedDB
   (falls back to localStorage) so nothing is lost on a crash; reminders nudge you to save the file. */
function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }
const idb = (() => {
  let dbp = null;
  const open = () => dbp || (dbp = new Promise((res, rej) => {
    try { const r = indexedDB.open('commonplace', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }
    catch (e) { rej(e); }
  }));
  return {
    async get(k) { const db = await open(); return new Promise((res, rej) => { const q = db.transaction('kv').objectStore('kv').get(k); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); }); },
    async set(k, v) { const db = await open(); return new Promise((res, rej) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = () => res(true); t.onerror = () => rej(t.error); }); },
  };
})();
const PREFS_KEY = 'commonplace.prefs';
let PREFS = { remindMins: 15, sessionGoal: 0, typewriter: true, dimOthers: true, uncitedMin: 40, spellcheck: true };
try { Object.assign(PREFS, JSON.parse(lsGet(PREFS_KEY) || '{}')); } catch (e) {}
const savePrefs = () => lsSet(PREFS_KEY, JSON.stringify(PREFS));
let autosaveOk = true, dirtySince = null, snoozeUntil = 0, lastFileName = '';
function sessionRecord() {
  return JSON.stringify({ project: P, curDocId, dirtyFile, dirtySince, lastFileSave: lastFileSave ? lastFileSave.toISOString() : null, lastFileName, stamp: Date.now() });
}
async function persistLocal() {
  if (!P) return;
  syncEditor();
  let rec = sessionRecord();
  if (LOCK) rec = await sealText(rec, { stamp: Date.now() });
  try { await idb.set(STORE_KEY, rec); autosaveOk = true; lsSet(STORE_KEY, 'idb'); }
  catch (e) { autosaveOk = lsSet(STORE_KEY, rec); }
  updateSaveState();
  if (PREFS.fileAutosave && dirtyFile) fileAutosave();
}
const autosave = debounce(persistLocal, 700);
async function loadLocal() {
  let a = null, b = null;
  try { const v = await idb.get(STORE_KEY); if (v) a = JSON.parse(v); } catch (e) {}
  try { const v = lsGet(STORE_KEY); if (v && v !== 'idb') b = JSON.parse(v); } catch (e) {}
  if (a && b) return (b.stamp || 0) > (a.stamp || 0) ? b : a;
  return a || b;
}
function markDirty() { if (typeof requestPersist === 'function') requestPersist(); if (!dirtyFile || !dirtySince) { dirtyFile = true; dirtySince = dirtySince || Date.now(); } P.modified = nowISO(); updateSaveState(); autosave(); }
function updateSaveState() {
  const el = $('#saveState');
  if (dirtyFile) { el.textContent = autosaveOk ? 'Unsaved changes · kept in browser' : 'Unsaved changes'; el.classList.add('dirty'); }
  else { el.textContent = lastFileSave ? 'Saved ' + lastFileSave.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''; el.classList.remove('dirty'); }
  checkReminder();
}
const fmtMins = m => m < 60 ? Math.round(m) + ' min' : (m / 60).toFixed(m < 600 ? 1 : 0).replace(/\.0$/, '') + ' h';
function checkReminder() {
  const bar = $('#remindBar'); if (!bar) return;
  const mins = dirtySince ? (Date.now() - dirtySince) / 60000 : 0;
  const show = PREFS.remindMins > 0 && dirtyFile && dirtySince && mins >= PREFS.remindMins && Date.now() >= snoozeUntil;
  bar.classList.toggle('hidden', !show);
  if (!show) return;
  bar.classList.toggle('urgent', mins >= PREFS.remindMins * 3);
  $('#remindText').textContent = `Unsaved changes for ${fmtMins(mins)}. ` + (lastFileName ? `Last saved to ${lastFileName}${lastFileSave ? ' at ' + lastFileSave.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}.` : 'This project hasn’t been saved to a file yet.');
}
setInterval(checkReminder, 30000);
const fileSafe = s => (String(s || 'untitled').replace(/[\\/:*?"<>|]+/g, '').replace(/\s+/g, ' ').trim().slice(0, 80) || 'untitled');
function download(name, text, type) {
  const blob = text instanceof Blob ? text : new Blob([text], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
}
function projectJSON() { syncEditor(); return JSON.stringify(Object.assign({}, P, { app: 'Anabasis', format: FORMAT, appVersion: APP_VERSION, saved: nowISO() }), null, 2); }
async function saveProject(saveAs = false) {
  let text; try { text = await projectFileText(); } catch (e) { toast(e.message); return; }
  const types = [{ description: 'Anabasis project', accept: { 'application/json': ['.json'] } }];
  if (!fileHandle && pendingHandle && !saveAs) { try { if (!pendingHandle.requestPermission || (await pendingHandle.requestPermission({ mode: 'readwrite' })) === 'granted') fileHandle = pendingHandle; } catch (e) {} }
  if (window.showSaveFilePicker && (saveAs || !fileHandle)) {
    try { fileHandle = await window.showSaveFilePicker({ suggestedName: fileSafe(P.title) + '.json', types }); }
    catch (e) { if (e.name === 'AbortError') return; fileHandle = null; }
  }
  if (fileHandle) {
    try { const w = await fileHandle.createWritable(); await w.write(text); await w.close(); await verifyWritten(fileHandle, text); pendingHandle = null; autoFailed = false; afterSave(fileHandle.name, 'Saved to ' + fileHandle.name + (LOCK ? ' (locked)' : '') + (PREFS.fileAutosave ? '. Autosave is on.' : '')); return; }
    catch (e) { console.warn(e); if (e.verify) toast(e.message); fileHandle = null; }
  }
  const name = fileSafe(P.title) + '.json';
  download(name, text, 'application/json');
  afterSave(name, 'Project downloaded as ' + name);
}
function afterSave(name, msg) { setTimeout(() => ghAfterSave(false), 50); rememberRecent(fileHandle, name); dirtyFile = false; dirtySince = null; snoozeUntil = 0; lastFileSave = new Date(); lastFileName = name; persistLocal(); updateSaveState(); toast(msg); }
async function openProject() {
  if (dirtyFile && !(await ask('Open another project?', 'Your current project has changes that aren’t saved to a file. They stay in this browser’s autosave only until the new project replaces them.', 'Open anyway'))) return;
  if (window.showOpenFilePicker) {
    try {
      const [h] = await window.showOpenFilePicker({ types: [{ description: 'Anabasis project', accept: { 'application/json': ['.json'] } }] });
      const f = await h.getFile(); loadProjectText(await f.text(), h, f.name); return;
    } catch (e) { if (e.name === 'AbortError') return; }
  }
  $('#fileOpen').click();
}
async function verifyWritten(h, text) { // read the file back; a mismatch means the disk copy can't be trusted
  try { const back = await (await h.getFile()).text(); if (back === text) return; } catch (e) { return; } // browsers that can't read back: trust the write
  const err = new Error('The saved file didn’t match what Anabasis wrote, so a copy was downloaded instead. Keep that copy.'); err.verify = true; throw err;
}
function repairJSON(text) { // fix the damage that's common in files that were cut off, hand-edited or synced badly
  let t = String(text).replace(/^\uFEFF/, '').trim();
  const tries = [t, t.replace(/,(\s*[}\]])/g, '$1'), t.slice(0, t.lastIndexOf('}') + 1), t.slice(0, t.lastIndexOf('}') + 1).replace(/,(\s*[}\]])/g, '$1')];
  for (const c of tries) { try { return JSON.parse(c); } catch (e) {} }
  return null;
}
async function loadProjectText(text, handle = null, name = '') {
  let data, newLock = null, repaired = false;
  try { data = JSON.parse(text); } catch (e) {
    data = repairJSON(text);
    if (data) { repaired = true; handle = null; }
    else {
      const local = await loadLocal().catch(() => null), pos = /position (\d+)/.exec(e.message), at = pos && +pos[1] < text.length - 1 ? ` near character ${(+pos[1]).toLocaleString()} of ${text.length.toLocaleString()}` : text.length ? ` (${text.length.toLocaleString()} characters, ${/end of JSON|Unterminated|unexpected end/i.test(e.message) ? 'cut off before the end' : 'garbled'})` : ' (the file is empty)';
      const lp = local && local.project, lpWhen = lp && lp.modified ? new Date(lp.modified).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
      if (lp && await ask('This file is damaged', `“${name || 'The file'}” can’t be read${at}. This browser still has a copy of “${lp.title}” from ${lpWhen}. Open that instead? You can also restore from a checkpoint or a GitHub backup.`, 'Open the browser copy')) { data = lp; handle = null; name = ''; }
      else { if (!lp) await ask('This file is damaged', `“${name || 'The file'}” can’t be read${at}. If you have checkpoints or GitHub backups, restore from one of those; otherwise try an earlier copy of the file from your sync service’s version history.`, 'OK'); return; }
    }
  }
  if (data && +data.format > FORMAT && !isLocked(data)) {
    if (!(await ask('Made with a newer Anabasis', `This file was saved by Anabasis ${data.appVersion || ''} (file format ${data.format}). This copy is ${APP_VERSION} and may not understand everything in it. Open it anyway? Saving will ask for a new file name, so the original stays as it is.`, 'Open a copy'))) return;
    handle = null;
  }
  if (isLocked(data)) {
    const r = await unlockLoop(data, `Unlock “${(name || 'project').replace(/\.json$/i, '')}”`, 'This project file is locked with a password.', false);
    if (!r) return;
    try { data = JSON.parse(r.text); newLock = r.lock; } catch (e) { toast('That file couldn’t be read.'); return; }
  }
  if (!data || (!Array.isArray(data.docs) && !Array.isArray(data.notes) && !Array.isArray(data.sources))) { toast('That doesn’t look like an Anabasis project.'); return; }
  let useLocal = false;
  const local = await loadLocal();
  if (local && local.project && data.id && local.project.id === data.id && local.dirtyFile && (local.project.modified || '') > (data.modified || '')) {
    const when = new Date(local.project.modified).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    useLocal = await ask('This browser has newer work', `You have unsaved edits to “${local.project.title}” from ${when} in this browser, newer than the file you opened. Keep working from the newer browser copy? (Choose Cancel to use the file as saved.)`, 'Use newer copy');
  }
  let np; try { np = normalize(useLocal ? local.project : data); } catch (e) { console.error(e); toast('That project couldn’t be opened: ' + e.message); return; }
  P = np;
  LOCK = newLock; document.body.classList.toggle('locked', !!LOCK); pendingHandle = null; autoFailed = false;
  fileHandle = handle; lastFileName = name || (handle && handle.name) || ''; lastFileSave = null;
  dirtyFile = useLocal; dirtySince = useLocal ? (local.dirtySince || Date.now()) : null;
  srcVersion++;
  if (!P.docs.length) P.docs.push(newDoc());
  closePanel();
  openDoc((useLocal && P.docs.some(d => d.id === local.curDocId)) ? local.curDocId : P.docs[0].id, true);
  renderAll();
  persistLocal();
  updateSaveState();
  toast((useLocal ? 'Continuing from the newer browser copy of “' : 'Opened “') + P.title + '”');
  if (repaired) setTimeout(() => toast('The file was slightly damaged and has been repaired. Check your work, then use Save project as… to write a clean copy.'), 1600);
  rememberRecent(handle, lastFileName);
  if (PREFS.startHome !== false) openHome();
  updateAutoState();
  return true;
}
async function newProject() {
  if (dirtyFile && !(await ask('Start a new project?', 'Changes not saved to a file will be lost.', 'Start new'))) return;
  P = blankProject(); P.docs.push(newDoc()); LOCK = null; document.body.classList.remove('locked');
  fileHandle = null; pendingHandle = null; dirtyFile = false; dirtySince = null; lastFileSave = null; lastFileName = ''; srcVersion++;
  closePanel(); openDoc(P.docs[0].id, true); renderAll(); persistLocal(); updateSaveState();
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && P) persistLocal(); });

/* ---------------- citeproc engines ---------------- */
const engines = {}, previewEngines = {};
function itemFor(id) {
  const s = P.sources.find(x => x.id === id);
  if (!s) return { id, type: 'document', title: '[missing source]' };
  return Object.assign({}, s.csl, { id });
}
function makeEngine(style) {
  return new CSL.Engine({ retrieveLocale: () => LOCALE, retrieveItem: itemFor }, cslXml(style), 'en-US');
}
function getEngine(style, cache = engines) {
  const k = style + '|' + srcVersion;
  if (cache[style] && cache[style].k === k) return cache[style].e;
  const e = makeEngine(style); cache[style] = { k, e }; return e;
}
function cleanCiteItem(it) {
  const o = { id: it.id };
  if (it.locator) { o.locator = String(it.locator); o.label = it.label || 'page'; }
  if (it.prefix) o.prefix = it.prefix.endsWith(' ') ? it.prefix : it.prefix + ' ';
  if (it.suffix) o.suffix = /^[,;\s]/.test(it.suffix) ? it.suffix : ', ' + it.suffix;
  if (it['suppress-author']) o['suppress-author'] = true;
  return o;
}
function previewCluster(style, items) {
  if (STYLES[style].custom) return osintCluster(items, new Set());
  try { return getEngine(style, previewEngines).makeCitationCluster(items.map(cleanCiteItem)); } catch (e) { console.warn(e); return ''; }
}
function previewBib(style, id) {
  if (STYLES[style].custom) return '';
  try { const e = getEngine(style, previewEngines); e.updateItems([id]); const b = e.makeBibliography(); return b ? b[1].join('') : ''; } catch (e) { console.warn(e); return ''; }
}

/* ---------------- markers ---------------- */
function citeHTML(items) {
  return `<span class="cite" contenteditable="false" data-items="${esc(JSON.stringify(items))}">[cite]</span>`;
}
function fnHTML(text) {
  return `<span class="fn" contenteditable="false" data-text="${esc(text)}">*</span>`;
}
function markerItems(m) { try { return JSON.parse(m.dataset.items || '[]'); } catch (e) { return []; } }
function inlineMd(s) { return sanitize(marked.parseInline(String(s || ''))); }

/* Compute numbering, formatted citations, notes and bibliography for a set of markers. */
function computeRefs(doc, markers) {
  if (STYLES[doc.style].custom) return computeOsint(doc, markers);
  const style = doc.style, isNote = STYLES[style].note, eng = getEngine(style);
  let n = 0; const citations = [], byId = new Map(), notes = [], disp = [];
  markers.forEach((m, i) => {
    if (m.classList.contains('fn')) { n++; disp.push({ m, type: 'fn', n }); notes.push({ n, html: inlineMd(m.dataset.text) }); return; }
    const items = markerItems(m).filter(it => P.sources.some(s => s.id === it.id));
    if (!items.length) {
      const d = { m, type: 'missing', n: isNote ? ++n : 0 }; disp.push(d);
      if (isNote) notes.push({ n: d.n, html: '<span class="refs-missing">[source deleted. Click the marker to fix it.]</span>' });
      return;
    }
    const ni = isNote ? ++n : 0, cid = 'c' + i;
    citations.push({ citationID: cid, citationItems: items.map(cleanCiteItem), properties: { noteIndex: ni } });
    const d = { m, type: 'cite', n: ni, cid, html: '' }; disp.push(d); byId.set(cid, d);
    if (isNote) notes.push({ n: ni, cid });
  });
  try { eng.rebuildProcessorState(citations, 'html').forEach(([cid, , html]) => { const d = byId.get(cid); if (d) d.html = html; }); }
  catch (e) { console.error('citeproc', e); }
  notes.forEach(x => { if (x.cid) x.html = byId.get(x.cid).html; });
  let bib = null;
  if (doc.layout.bib !== 'none') {
    try {
      eng.updateUncitedItems(doc.layout.bib === 'all' ? P.sources.map(s => s.id) : []);
      const b = eng.makeBibliography();
      if (b && b[1].length) bib = { entries: b[1], hanging: !!b[0].hangingindent };
    } catch (e) { console.error('bibliography', e); }
  }
  return { isNote, disp, notes: notes.sort((a, b) => a.n - b.n), bib, heading: STYLES[style].bib };
}
function applyMarkers(out) {
  out.disp.forEach(d => {
    const m = d.m;
    if (d.type === 'fn' || (out.isNote && d.type !== 'fn')) {
      m.classList.add('sup'); m.textContent = String(d.n);
      const note = out.notes.find(x => x.n === d.n);
      m.title = note ? htmlToText(note.html) : '';
    } else {
      m.classList.remove('sup');
      if (d.type === 'missing') { m.textContent = '[missing source]'; m.title = 'This source was deleted. Click to fix.'; }
      else {
        const prev = m.previousSibling, glue = prev && prev.nodeType === 3 && /[^\s(\[“"‘'\u00a0]$/.test(prev.data);
        m.innerHTML = (glue ? ' ' : '') + (d.html || '[?]'); m.title = 'Click to edit citation';
      }
    }
  });
}
function refsHTML(out, forExport = false) {
  let h = '';
  if (out.notes.length) {
    h += `<section class="end-sec notes"><h2 class="end-h">Notes</h2>` + out.notes.map(x => `<p class="note"><span class="nn">${x.n}.</span> ${x.html}</p>`).join('') + `</section>`;
  }
  if (out.bib) {
    h += `<section class="end-sec bib"><h2 class="end-h">${esc(out.heading)}</h2><div class="csl-bib${out.bib.hanging ? ' hanging' : ''}">${out.bib.entries.join('')}</div></section>`;
  }
  if (!forExport && h) h = `<span class="gen-label">Generated from your citations and updated as you write</span>` + h;
  return h;
}
const htmlToText = h => { const d = document.createElement('div'); d.innerHTML = h; return d.textContent; };

/* ---------------- editor ---------------- */
const editor = $('#editor');
let lastSig = '';
let savedRange = null;
function curDoc() { return P.docs.find(d => d.id === curDocId); }
function syncEditor() {
  const d = P && curDoc(); if (!d) return;
  const h = stripCp(editor.innerHTML);
  if (h !== d.html) { d.html = h; d.modified = nowISO(); }
}
function renderRefs(force = false) {
  const doc = curDoc(); if (!doc) return;
  const markers = $$('.cite,.fn', editor);
  const sig = [doc.style, srcVersion, doc.layout.bib, markers.map(m => (m.classList.contains('fn') ? 'f' + m.dataset.text : 'c' + m.dataset.items)).join('§')].join('|');
  if (!force && sig === lastSig) return;
  lastSig = sig;
  const out = computeRefs(doc, markers);
  applyMarkers(out);
  $('#refs').innerHTML = refsHTML(out);
}
function applyLayout(el, doc) {
  const L = doc.layout;
  el.classList.toggle('f-times', L.font === 'times');
  el.classList.toggle('f-sans', L.font === 'sans');
  el.classList.toggle('indent', !!L.indent);
  el.classList.toggle('bib-ds', !!STYLES[doc.style].ds && L.spacing === '2');
  el.style.setProperty('--doc-size', L.size + 'pt');
  el.style.setProperty('--doc-lh', L.spacing);
}
function titleBlockHTML(doc) {
  const m = doc.meta; if (!m.showTitleBlock) return '';
  return `<p class="tb-title">${esc(doc.title)}</p>` + [m.subtitle, m.author, m.date].filter(Boolean).map(x => `<p>${esc(x)}</p>`).join('');
}
function openDoc(id, skipSync = false) {
  if (!skipSync) syncEditor();
  const d = P.docs.find(x => x.id === id) || P.docs[0];
  if (!d) return;
  if (boardOn) closeBoard();
  if (planOn) closePlan();
  if (homeOn) closeHome();
  if (draftsOn) closeDrafts();
  if (relOn) closeRel();
  curDocId = d.id;
  editor.innerHTML = d.html || '<p><br></p>'; tidyTopLevel(); prepFigureDom(editor); hydrateImages(); renumberFigures();
  $('#docTitle').value = d.title;
  $('#docStyle').value = d.style;
  $('#titleBlock').innerHTML = titleBlockHTML(d);
  applyLayout($('#page'), d);
  editor.spellcheck = PREFS.spellcheck !== false;
  lastSig = ''; renderRefs(true); updateWordCount();
  renderDocList(); renderOutline(); updateTargets();
  if (!$('#findBar').classList.contains('hidden')) runFind();
  $('#scroller').scrollTop = 0;
  document.body.classList.remove('side-open');
  renderMargin(); requestAnimationFrame(() => renderMargin()); updateDraftBtn(); updateScript(); renderAcronyms(); runEstimative(); renderCorroboration(); renderHouse(); renderA11y();
}
function updateWordCount() {
  const clone = editor.cloneNode(true);
  $$('.cite,.fn,.flag', clone).forEach(m => m.remove());
  const words = (clone.innerText || '').trim().split(/\s+/).filter(Boolean).length;
  const cites = $$('.cite', editor).length;
  $('#wordCount').textContent = `${words.toLocaleString()} words · ${cites} citation${cites === 1 ? '' : 's'}`;
}
// Edits made by the app itself (inserting a note, a citation, a figure) don't fire 'input', so refresh the Outline checks here too.
const refreshChecks = debounce(() => { if (typeof homeOn !== 'undefined' && (homeOn || boardOn || planOn)) return; renderAcronyms(); runEstimative(); renderCorroboration(); renderHouse(); renderA11y(); }, 1000);
const onEdit = debounce(() => { syncEditor(); renderRefs(); updateWordCount(); trackWords(); renderDocList(); markDirty(); refreshChecks(); }, 350);
editor.addEventListener('input', () => { onEdit(); });
document.addEventListener('selectionchange', () => {
  const sel = getSelection();
  if (sel.rangeCount && editor.contains(sel.anchorNode)) { savedRange = sel.getRangeAt(0).cloneRange(); updateToolbarState(); }
});
function restoreSelection() {
  editor.focus();
  const sel = getSelection();
  if (savedRange && editor.contains(savedRange.startContainer)) { sel.removeAllRanges(); sel.addRange(savedRange); }
  else { const r = document.createRange(); r.selectNodeContents(editor); r.collapse(false); sel.removeAllRanges(); sel.addRange(r); }
}
/* Keep the caret inside a paragraph: Chrome can park it between blocks, where inserts get lost. */
function tidyTopLevel() {
  [...editor.childNodes].forEach(n => { if (n.nodeType === 3 && !n.data.trim()) n.remove(); });
  if (!editor.firstChild) editor.innerHTML = '<p><br></p>';
}
function snapRange(r) {
  let ref = null, after = true;
  if (r.startContainer === editor) { const prev = editor.childNodes[r.startOffset - 1], next = editor.childNodes[r.startOffset]; ref = prev && prev.nodeType === 1 ? prev : next; after = ref === prev; }
  else if (r.startContainer.nodeType === 3 && r.startContainer.parentNode === editor) { const t = r.startContainer; ref = t.previousElementSibling || t.nextElementSibling; after = ref === t.previousElementSibling; }
  if (!ref || ref.nodeType !== 1) return r;
  const n = document.createRange(); n.selectNodeContents(ref); n.collapse(!after); return n;
}
function rescueStrayInline() {
  [...editor.childNodes].forEach(n => {
    if (n.nodeType === 1 && n.matches('.cite,.fn,.flag')) {
      const prev = n.previousElementSibling;
      if (prev && /^(P|H[1-6]|BLOCKQUOTE)$/.test(prev.nodeName)) { const nx = n.nextSibling; prev.append(n); if (nx && nx.nodeType === 3 && nx.parentNode === editor && nx.data.trim() === '') { prev.append('\u00a0'); nx.remove(); } else if (nx && nx.nodeType === 3 && nx.parentNode === editor) prev.append(nx); }
      else { const pp = document.createElement('p'); n.replaceWith(pp); pp.append(n); }
      const r = document.createRange(); r.setStartAfter(n); r.collapse(true); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); savedRange = r.cloneRange();
    }
  });
  tidyTopLevel();
}
function insertHTMLAtCursor(html) {
  restoreSelection();
  const sel = getSelection(); if (sel.rangeCount && !sel.isCollapsed) sel.collapseToEnd();
  if (sel.rangeCount) { const r = snapRange(sel.getRangeAt(0)); sel.removeAllRanges(); sel.addRange(r); }
  const before = $$('.cite,.fn', editor).length;
  const range = sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
  document.execCommand('insertHTML', false, html);
  // Chrome can silently refuse insertHTML right beside a non-editable marker; fall back to a plain DOM insert
  if ($$('.cite,.fn', editor).length === before && /class="(cite|fn)"/.test(html) && range) {
    const frag = range.createContextualFragment(html), last = frag.lastChild;
    range.insertNode(frag);
    const r = document.createRange(); r.setStartAfter(last); r.collapse(true); sel.removeAllRanges(); sel.addRange(r); savedRange = r.cloneRange();
  }
  // Chrome sometimes drops contenteditable=false from inserted markers; restore it
  $$('.cite,.fn,.flag', editor).forEach(m => { m.setAttribute('contenteditable', 'false'); m.removeAttribute('style'); });
  rescueStrayInline();
  syncEditor(); renderRefs(true); updateWordCount(); markDirty();
}
/* Block content (notes, compiled drafts) goes after the paragraph holding the caret, never inside it. */
function insertBlocksAtCursor(html) {
  restoreSelection();
  const sel = getSelection();
  let blk = sel.rangeCount ? snapRange(sel.getRangeAt(0)).startContainer : null;
  while (blk && blk.parentNode !== editor) blk = blk.parentNode;
  const tpl = document.createElement('template'); tpl.innerHTML = html;
  const nodes = [...tpl.content.childNodes];
  if (!nodes.length) return;
  if (!blk) editor.append(...nodes);
  else if (!blk.textContent.trim() && !blk.querySelector('.cite,.fn')) blk.replaceWith(...nodes);
  else blk.after(...nodes);
  const last = nodes[nodes.length - 1];
  const r = document.createRange(); r.selectNodeContents(last.nodeType === 1 ? last : editor); r.collapse(false);
  sel.removeAllRanges(); sel.addRange(r); savedRange = r.cloneRange();
  last.nodeType === 1 && last.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  syncEditor(); renderRefs(true); updateWordCount(); markDirty(); refreshChecks();
}
function exec(cmd, val = null) { restoreSelection(); document.execCommand(cmd, false, val); onEdit(); updateToolbarState(); }
try { document.execCommand('defaultParagraphSeparator', false, 'p'); } catch (e) {}
$('#toolbar').addEventListener('mousedown', e => { if (e.target.closest('button')) e.preventDefault(); });
$$('#toolbar [data-cmd]').forEach(b => b.addEventListener('click', () => exec(b.dataset.cmd)));
$('#blockSel').addEventListener('change', e => { exec('formatBlock', '<' + e.target.value + '>'); });
function updateToolbarState() {
  ['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList'].forEach(c => {
    const b = $(`#toolbar [data-cmd="${c}"]`); try { b.classList.toggle('on', document.queryCommandState(c)); } catch (e) {}
  });
  const sel = getSelection(); if (!sel.rangeCount) return;
  let n = sel.anchorNode; while (n && n !== editor && !(n.nodeType === 1 && /^(P|H1|H2|H3|BLOCKQUOTE)$/.test(n.nodeName))) n = n.parentNode;
  if (n && n !== editor) $('#blockSel').value = n.nodeName.toLowerCase();
}
$('#btnLink').addEventListener('click', async () => {
  const r = savedRange;
  const url = await ask('Insert link', 'Web address:', 'Insert', 'https://');
  if (!url) return;
  savedRange = r;
  exec('createLink', /^(https?:|mailto:|#)/i.test(url) ? url : 'https://' + url);
});

/* Everything that arrives from a file is scrubbed before it reaches the page: scripts, event handlers,
   javascript: links, frames, forms and plug-ins are removed; Anabasis's own markup is kept. */
const SCRUB_CFG = { ADD_ATTR: ['contenteditable', 'target'], FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select', 'option', 'iframe', 'frame', 'frameset', 'object', 'embed', 'base', 'link', 'meta', 'svg', 'math', 'template', 'noscript', 'audio', 'video', 'source', 'track', 'portal'], FORBID_ATTR: ['srcset', 'formaction', 'action', 'xlink:href', 'ping'] };
function scrubHTML(html) {
  if (!html) return '';
  if (window.DOMPurify && DOMPurify.isSupported) {
    if (!scrubHTML.hooked) { // images live in the project as data; a remote address would let a shared file ping a server when opened
      DOMPurify.addHook('uponSanitizeAttribute', (node, d) => { if (node.nodeName === 'IMG' && d.attrName === 'src' && !/^data:image\/(png|jpeg|gif|webp)/i.test(d.attrValue)) d.keepAttr = false; });
      scrubHTML.hooked = true;
    }
    return DOMPurify.sanitize(html, SCRUB_CFG);
  }
  return sanitize(html);
}
/* paste: keep basic structure only */
const ALLOWED = { P: 1, H1: 1, H2: 1, H3: 1, BLOCKQUOTE: 1, UL: 1, OL: 1, LI: 1, STRONG: 1, B: 1, EM: 1, I: 1, U: 1, S: 1, A: 1, BR: 1, SUP: 1, SUB: 1, SPAN: 1, CODE: 1, PRE: 1, DIV: 1, FIGURE: 1, FIGCAPTION: 1, IMG: 1, TABLE: 1, THEAD: 1, TBODY: 1, TFOOT: 1, TR: 1, TH: 1, TD: 1 };
function sanitize(html) {
  const doc = new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html');
  const walk = node => {
    [...node.childNodes].forEach(ch => {
      if (ch.nodeType === 8) { ch.remove(); return; }
      if (ch.nodeType !== 1) return;
      const tag = ch.nodeName;
      if (/^(SCRIPT|STYLE|META|LINK|TITLE|HEAD|IFRAME|OBJECT|EMBED|SVG|MATH)$/.test(tag)) { ch.remove(); return; }
      if (/^H[4-6]$/.test(tag)) { const h = doc.createElement('h3'); h.append(...ch.childNodes); ch.replaceWith(h); walk(h); return; }
      if (!ALLOWED[tag]) { walk(ch); ch.replaceWith(...ch.childNodes); return; }
      const isMarker = tag === 'SPAN' && (ch.classList.contains('cite') || ch.classList.contains('fn'));
      // Google Docs / Word: bold & italic arrive as inline styles on spans
      if (tag === 'SPAN' && !isMarker) {
        const st = ch.getAttribute('style') || '';
        let wrap = null;
        if (/font-weight:\s*(bold|[6-9]00)/.test(st)) wrap = 'strong';
        if (/font-style:\s*italic/.test(st)) wrap = wrap ? 'strong-em' : 'em';
        walk(ch);
        if (wrap) {
          let el = doc.createElement(wrap === 'em' ? 'em' : 'strong'), inner = el;
          if (wrap === 'strong-em') { inner = doc.createElement('em'); el.append(inner); }
          inner.append(...ch.childNodes); ch.replaceWith(el);
        } else ch.replaceWith(...ch.childNodes);
        return;
      }
      [...ch.attributes].forEach(a => {
        const keep = (tag === 'A' && a.name === 'href' && /^(https?:|mailto:|#)/i.test(a.value)) ||
          (isMarker && (a.name === 'class' || a.name === 'data-items' || a.name === 'data-text')) ||
          (tag === 'IMG' && (a.name === 'data-asset' || a.name === 'alt' || (a.name === 'src' && /^data:image\/(png|jpeg|gif|webp)/i.test(a.value)))) ||
          (tag === 'FIGURE' && ((a.name === 'class' && /^(fig|tbl|tbl av)$/.test(a.value)) || a.name === 'data-size')) ||
          ((tag === 'TD' || tag === 'TH') && (a.name === 'colspan' || a.name === 'rowspan'));
        if (!keep) ch.removeAttribute(a.name);
      });
      if (isMarker) { ch.setAttribute('contenteditable', 'false'); return; }
      if (tag === 'IMG' && !ch.getAttribute('data-asset') && !ch.getAttribute('src')) { ch.remove(); return; }
      if (tag === 'DIV') { const p = doc.createElement('p'); p.append(...ch.childNodes); ch.replaceWith(p); walk(p); return; }
      walk(ch);
    });
  };
  walk(doc.body);
  return doc.body.innerHTML;
}
editor.addEventListener('paste', e => {
  const cd = e.clipboardData; if (!cd) return;
  const html = cd.getData('text/html');
  e.preventDefault();
  if (html) document.execCommand('insertHTML', false, sanitize(html));
  else {
    const t = cd.getData('text/plain');
    const paras = t.split(/\r?\n\s*\r?\n/);
    if (paras.length > 1) document.execCommand('insertHTML', false, paras.map(p => '<p>' + esc(p).replace(/\r?\n/g, '<br>') + '</p>').join(''));
    else document.execCommand('insertText', false, t);
  }
  $$('.cite,.fn', editor).forEach(m => m.setAttribute('contenteditable', 'false'));
  wrapBareTables(editor);
  adoptInlineImages(editor).then(() => { hydrateImages(); renumberFigures(); onEdit(); });
  onEdit();
});
function stripCapLabel(html, words) { // “<strong>Figure 3.</strong> Caption” → “Caption”
  return html.replace(new RegExp('^\\s*(<(strong|b|em|i)>\\s*)?(' + words + ')\\s*\\d+[.:]\\s*(<\\/(strong|b|em|i)>)?\\s*', 'i'), '').trim() || '<br>';
}
function wrapBareTables(root) {
  $$('table', root).filter(t => !t.closest('figure')).forEach(t => {
    const f = document.createElement('figure'); f.className = 'tbl'; const c = document.createElement('figcaption'); c.innerHTML = '<br>';
    const host = t.parentElement && t.parentElement !== root && t.parentElement.nodeName === 'P' ? t.parentElement : t;
    host.replaceWith(f); f.append(c, t);
  });
}

/* clicking a marker */
let popEl = null;
function closePop() { if (popEl) { popEl.remove(); popEl = null; } }
editor.addEventListener('click', e => {
  const m = e.target.closest('.cite,.fn'); closePop();
  if (!m) return;
  e.preventDefault();
  if (m.classList.contains('fn')) { openFootnote(m); return; }
  const r = m.getBoundingClientRect();
  popEl = document.createElement('div'); popEl.className = 'pop';
  const out = refsForMarker(m);
  popEl.innerHTML = `<div class="ptext">${out || '<span class="muted">[missing source]</span>'}</div><div class="pbtns"><button class="primary" data-a="edit">Edit citation</button><button data-a="src">Open source</button><button class="danger" data-a="del">Remove</button></div>`;
  document.body.appendChild(popEl);
  const pw = popEl.offsetWidth;
  popEl.style.left = Math.max(8, Math.min(innerWidth - pw - 8, r.left - 20)) + 'px';
  popEl.style.top = (r.bottom + 6 + popEl.offsetHeight > innerHeight ? r.top - popEl.offsetHeight - 6 : r.bottom + 6) + 'px';
  popEl.addEventListener('click', ev => {
    const a = ev.target.closest('button')?.dataset.a; if (!a) return;
    closePop();
    if (a === 'edit') openCite(m);
    if (a === 'del') { m.remove(); onEdit(); renderRefs(true); }
    if (a === 'src') { const it = markerItems(m)[0]; if (it && P.sources.some(s => s.id === it.id)) openSource(it.id); else toast('That source no longer exists.'); }
  });
});
document.addEventListener('mousedown', e => { if (popEl && !popEl.contains(e.target) && !e.target.closest('.cite')) closePop(); });
function refsForMarker(m) {
  const doc = curDoc();
  if (STYLES[doc.style].note) { const n = parseInt(m.textContent, 10); const it = $$('#refs .notes p.note')[n - 1]; return it ? it.innerHTML.replace(/^<span class="nn">\d+\.<\/span>\s*/, '') : ''; }
  return m.innerHTML;
}

/* ---------------- citation dialog ---------------- */
let citeTarget = null, cluster = [];
function sourceLabel(s) {
  const c = s.csl, names = c.author || c.editor || c['container-author'] || [];
  const who = names.length ? (names[0].family || names[0].literal || names[0].given || '') + (names.length > 2 ? ' et al.' : names.length === 2 ? ' & ' + (names[1].family || names[1].literal || '') : '') : '';
  const yr = yearOf(c.issued);
  return { who, yr, title: c.title || '(untitled)' };
}
function yearOf(d) { if (!d) return ''; if (d['date-parts']?.[0]?.[0]) return String(d['date-parts'][0][0]); if (d.literal) return d.literal; if (d.raw) return d.raw; return ''; }
function openCite(marker = null) {
  if (!curDoc()) return;
  citeTarget = marker;
  cluster = marker ? markerItems(marker).filter(it => P.sources.some(s => s.id === it.id)) : [];
  $('#citeDlgTitle').textContent = marker ? 'Edit citation' : 'Insert citation';
  $('#citeOk').textContent = marker ? 'Update' : 'Insert';
  $('#citeRemove').classList.toggle('hidden', !marker);
  $('#citeSearch').value = ''; $('#citeLookup').value = '';
  renderCitePick(); renderCluster();
  $('#citeDlg').showModal();
  setTimeout(() => $('#citeSearch').focus(), 30);
}
function renderCitePick() {
  const q = $('#citeSearch').value.toLowerCase().trim();
  const list = sortedSources().filter(s => !q || JSON.stringify(s.csl).toLowerCase().includes(q));
  $('#citePick').innerHTML = list.length ? list.map(s => {
    const l = sourceLabel(s), on = cluster.some(c => c.id === s.id);
    return `<li data-id="${s.id}" class="${on ? 'on' : ''}">${on ? '✓ ' : ''}<b>${esc(l.who || '—')}</b>${l.yr ? ' (' + esc(l.yr) + ')' : ''}: ${esc(l.title)}</li>`;
  }).join('') : `<li class="muted" style="cursor:default">${P.sources.length ? 'No matches.' : 'No sources yet. Add one by DOI/ISBN at right, or from the Sources tab.'}</li>`;
}
$('#citeSearch').addEventListener('input', renderCitePick);
$('#citeSearch').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); const li = $('#citePick li[data-id]'); if (li) li.click(); } });
$('#citePick').addEventListener('click', e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  const id = li.dataset.id, i = cluster.findIndex(c => c.id === id);
  if (i >= 0) cluster.splice(i, 1); else cluster.push({ id, locator: '', label: 'page', prefix: '', suffix: '' });
  renderCitePick(); renderCluster();
  const loc = $$('#citeCluster .loc'); if (i < 0 && loc.length) loc[loc.length - 1].focus();
});
function renderCluster() {
  const box = $('#citeCluster');
  if (!cluster.length) { box.innerHTML = '<div class="muted small">Nothing selected yet.</div>'; updateCitePreview(); return; }
  box.innerHTML = cluster.map((c, i) => {
    const s = P.sources.find(x => x.id === c.id), l = sourceLabel(s);
    return `<div class="cluster-row" data-i="${i}"><div class="hd"><span>${esc(l.who)}${l.yr ? ' (' + esc(l.yr) + ')' : ''}: ${esc(l.title)}</span>
      ${i ? '<button class="ghost icon" data-a="up" title="Move up">↑</button>' : ''}<button class="ghost icon" data-a="rm" title="Remove from citation">✕</button></div>
      <div class="fields"><select data-k="label">${LOCATOR_LABELS.map(x => `<option ${x === c.label ? 'selected' : ''}>${x}</option>`).join('')}</select>
      <input class="loc" data-k="locator" placeholder="e.g. 45–47" value="${esc(c.locator)}">
      <input data-k="prefix" placeholder="Prefix (see also)" value="${esc(c.prefix)}">
      <input data-k="suffix" placeholder="Suffix (emphasis mine)" value="${esc(c.suffix)}"></div>
      <label class="chk"><input type="checkbox" data-k="suppress-author" ${c['suppress-author'] ? 'checked' : ''}> Omit author (already named in your sentence, e.g. “Tuchman argues (1962, 45)”)</label></div>`;
  }).join('');
  updateCitePreview();
}
$('#citeCluster').addEventListener('input', e => {
  const row = e.target.closest('.cluster-row'), k = e.target.dataset.k; if (!row || !k) return;
  const c = cluster[+row.dataset.i];
  c[k] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
  updateCitePreview();
});
$('#citeCluster').addEventListener('click', e => {
  const a = e.target.closest('button')?.dataset.a; if (!a) return;
  const i = +e.target.closest('.cluster-row').dataset.i;
  if (a === 'rm') cluster.splice(i, 1);
  if (a === 'up') [cluster[i - 1], cluster[i]] = [cluster[i], cluster[i - 1]];
  renderCitePick(); renderCluster();
});
const updateCitePreview = debounce(() => {
  const doc = curDoc();
  if (!cluster.length) { $('#citePreview').innerHTML = '<span class="muted">Choose a source above.</span>'; return; }
  const h = previewCluster(doc.style, cluster);
  $('#citePreview').innerHTML = (STYLES[doc.style].note ? '<span class="muted small">First note looks like:</span><br>' : '') + (h || '<span class="muted">—</span>');
}, 120);
$('#citeLookupBtn').addEventListener('click', async () => {
  const q = $('#citeLookup').value.trim(); if (!q) return;
  const b = $('#citeLookupBtn'); b.disabled = true; b.textContent = '…';
  try { const c = await lookupId(q); takePartial(c); const s = addSource(c); cluster.push({ id: s.id, locator: '', label: 'page', prefix: '', suffix: '' }); $('#citeLookup').value = ''; renderCitePick(); renderCluster(); toast('Added: ' + (s.csl.title || 'source')); }
  catch (e) { toast(e.message || 'Lookup failed'); }
  b.disabled = false; b.textContent = 'Add';
});
$('#citeLookup').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#citeLookupBtn').click(); } });
$('#citeCancel').addEventListener('click', () => $('#citeDlg').close());
$('#citeRemove').addEventListener('click', () => { if (citeTarget) { citeTarget.remove(); onEdit(); renderRefs(true); } $('#citeDlg').close(); });
$('#citeOk').addEventListener('click', () => {
  if (!cluster.length) { toast('Pick at least one source.'); return; }
  const items = cluster.map(c => { const o = { id: c.id }; ['locator', 'label', 'prefix', 'suffix'].forEach(k => { if (c[k]) o[k] = c[k]; }); if (c['suppress-author']) o['suppress-author'] = true; if (!o.locator) delete o.label; return o; });
  $('#citeDlg').close();
  if (citeTarget) { citeTarget.dataset.items = JSON.stringify(items); syncEditor(); renderRefs(true); markDirty(); }
  else insertHTMLAtCursor(citeHTML(items));
});
$('#btnCite').addEventListener('click', () => openCite());

/* ---------------- footnotes ---------------- */
let fnTarget = null;
function openFootnote(m = null) {
  fnTarget = m;
  $('#fnText').value = m ? m.dataset.text : '';
  $('#fnRemove').classList.toggle('hidden', !m);
  $('#fnDlg').showModal(); setTimeout(() => $('#fnText').focus(), 30);
}
$('#btnFootnote').addEventListener('click', () => openFootnote());
$('#fnCancel').addEventListener('click', () => $('#fnDlg').close());
$('#fnRemove').addEventListener('click', () => { if (fnTarget) { fnTarget.remove(); onEdit(); renderRefs(true); } $('#fnDlg').close(); });
$('#fnOk').addEventListener('click', () => {
  const t = $('#fnText').value.trim(); $('#fnDlg').close();
  if (!t) return;
  if (fnTarget) { fnTarget.dataset.text = t; syncEditor(); renderRefs(true); markDirty(); }
  else insertHTMLAtCursor(fnHTML(t));
});

/* ---------------- document list / doc bar ---------------- */
for (const k in STYLES) $('#docStyle').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(STYLES[k].label)}</option>`);
$('#docStyle').addEventListener('change', e => { const d = curDoc(); d.style = e.target.value; applyLayout($('#page'), d); renderRefs(true); markDirty(); });
$('#docTitle').addEventListener('input', e => { const d = curDoc(); d.title = e.target.value; d.modified = nowISO(); $('#titleBlock').innerHTML = titleBlockHTML(d); renderDocList(); markDirty(); });
$('#projTitle').addEventListener('input', e => { P.title = e.target.value; markDirty(); });
function relTime(iso) {
  const d = new Date(iso), s = (Date.now() - d) / 1000;
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago'; if (s < 86400) return Math.floor(s / 3600) + ' h ago';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
}
/* ---------- binder: documents grouped into parts, in manual order ---------- */
const docWords = d => { const t = htmlToText((d.id === curDocId ? editor.innerHTML : d.html).replace(/<span class="(cite|fn|flag)[^"]*"[^>]*>.*?<\/span>/g, ' ')); return t.trim().split(/\s+/).filter(Boolean).length; };
function docsInPart(pid) { return P.docs.filter(d => (d.partId || '') === pid).sort((a, b) => a.order - b.order); }
function binderOrder() { return ['', ...P.parts.map(x => x.id)].flatMap(docsInPart); }
function renumber(pid) { docsInPart(pid).forEach((d, i) => d.order = i); }
function docLi(d, inPart) {
  const w = docWords(d), tgt = d.target ? ` · ${Math.min(100, Math.round(w / d.target * 100))}% of ${d.target.toLocaleString()}` : '';
  return `<li data-id="${d.id}" draggable="true" class="doc ${inPart ? 'in-part' : ''} ${d.id === curDocId ? 'on' : ''}"><span class="act"><button data-a="up" title="Move up">↑</button><button data-a="down" title="Move down">↓</button><button data-a="move" title="Move to a part">⇥</button><button data-a="dup" title="Duplicate">⧉</button><button data-a="del" title="Delete" class="danger">✕</button></span>
    <div class="t">${d.role && d.role !== 'body' ? `<span class="role-tag">${d.role === 'front' ? 'front' : 'back'}</span>` : ''}${esc(d.title || 'Untitled')}</div><div class="meta">${d.status ? `<span class="st st-${d.status}">${esc(d.status)}</span>` : ''}${dueLabel(d)}<span>${w.toLocaleString()} words${tgt}</span><span>${relTime(d.modified)}</span></div></li>`;
}
function renderDocList() {
  const q = $('#qDocs').value.toLowerCase().trim();
  const match = d => !q || (d.title + ' ' + htmlToText(d.html)).toLowerCase().includes(q);
  let h = docsInPart('').filter(match).map(d => docLi(d, false)).join('');
  P.parts.forEach((pt, i) => {
    const docs = docsInPart(pt.id), shown = docs.filter(match);
    if (q && !shown.length) return;
    const w = docs.reduce((n, d) => n + docWords(d), 0);
    h += `<li class="part ${pt.collapsed && !q ? 'collapsed' : ''}" data-part="${pt.id}"><span class="act"><button data-pa="up" ${i ? '' : 'disabled'} title="Move part up">↑</button><button data-pa="down" ${i < P.parts.length - 1 ? '' : 'disabled'} title="Move part down">↓</button><button data-pa="ren" title="Rename">✎</button><button data-pa="del" class="danger" title="Remove part (keeps its documents)">✕</button></span>
      <div class="t"><span class="caret">▾</span>${esc(pt.name)}</div><div class="meta"><span>${docs.length} doc${docs.length === 1 ? '' : 's'} · ${w.toLocaleString()} words</span></div></li>`;
    if (!pt.collapsed || q) h += shown.map(d => docLi(d, true)).join('') || `<li class="part-empty" data-part-drop="${pt.id}">Drag documents here</li>`;
  });
  $('#docList').innerHTML = h || '<div class="empty">No documents match.</div>';
  $('#cntDocs').textContent = P.docs.length;
}
function moveDoc(id, partId, beforeId = null) {
  const d = P.docs.find(x => x.id === id); if (!d) return;
  const from = d.partId || '';
  const list = docsInPart(partId).filter(x => x.id !== id);
  let i = beforeId ? list.findIndex(x => x.id === beforeId) : list.length; if (i < 0) i = list.length;
  list.splice(i, 0, d); d.partId = partId; list.forEach((x, k) => x.order = k);
  if (from !== partId) renumber(from);
  renderDocList(); markDirty();
}
$('#qDocs').addEventListener('input', renderDocList);
$('#docList').addEventListener('click', async e => {
  const part = e.target.closest('li.part');
  if (part) {
    const pa = e.target.closest('button')?.dataset.pa, pt = P.parts.find(x => x.id === part.dataset.part), i = P.parts.indexOf(pt);
    if (!pa) { pt.collapsed = !pt.collapsed; renderDocList(); markDirty(); return; }
    if (pa === 'ren') { const n = await ask('Rename part', 'Part name:', 'Rename', pt.name); if (n) { pt.name = n; renderDocList(); markDirty(); } }
    if (pa === 'up' && i > 0) { [P.parts[i - 1], P.parts[i]] = [P.parts[i], P.parts[i - 1]]; renderDocList(); markDirty(); }
    if (pa === 'down' && i < P.parts.length - 1) { [P.parts[i + 1], P.parts[i]] = [P.parts[i], P.parts[i + 1]]; renderDocList(); markDirty(); }
    if (pa === 'del') {
      if (!(await ask('Remove part?', `“${pt.name}” will be removed. Its documents move to the top of the list. Nothing is deleted.`, 'Remove part'))) return;
      const base = docsInPart('').length; docsInPart(pt.id).forEach((d, k) => { d.partId = ''; d.order = base + k; });
      P.parts.splice(i, 1); renderDocList(); markDirty();
    }
    return;
  }
  const li = e.target.closest('li[data-id]'); if (!li) return;
  const a = e.target.closest('button')?.dataset.a, id = li.dataset.id, d = P.docs.find(x => x.id === id);
  if (a === 'up' || a === 'down') {
    const list = docsInPart(d.partId || ''), i = list.indexOf(d), j = a === 'up' ? i - 1 : i + 1;
    if (j >= 0 && j < list.length) { [list[i], list[j]] = [list[j], list[i]]; list.forEach((x, k) => x.order = k); renderDocList(); markDirty(); }
    return;
  }
  if (a === 'move') {
    const cur = P.parts.find(x => x.id === d.partId);
    const n = await ask('Move to part', `Type a part name (an existing one or a new one). Leave it blank to move “${d.title}” out of any part. Parts: ${P.parts.map(x => x.name).join(', ') || 'none yet'}.`, 'Move', cur ? cur.name : '');
    if (n === null) return;
    let pt = n ? P.parts.find(x => x.name.toLowerCase() === n.toLowerCase()) : null;
    if (n && !pt) { pt = { id: uid('pt'), name: n, collapsed: false }; P.parts.push(pt); }
    moveDoc(id, pt ? pt.id : ''); return;
  }
  if (a === 'dup') { syncEditor(); const c = JSON.parse(JSON.stringify(d)); c.id = uid('d'); c.title = d.title + ' (copy)'; c.created = c.modified = nowISO(); c.order = d.order + 0.5; P.docs.push(c); renumber(c.partId || ''); openDoc(c.id); markDirty(); return; }
  if (a === 'del') {
    if (!(await ask('Delete document?', `“${d.title || 'Untitled'}” will be removed from the project. Your notes and sources are not affected.`, 'Delete'))) return;
    P.docs = P.docs.filter(x => x.id !== id); renumber(d.partId || '');
    if (!P.docs.length) P.docs.push(newDoc());
    if (curDocId === id) openDoc(binderOrder()[0].id, true); else renderDocList();
    markDirty(); return;
  }
  if (id !== curDocId) openDoc(id);
});
/* drag and drop inside the binder */
let dragId = null;
$('#docList').addEventListener('dragstart', e => { const li = e.target.closest('li.doc'); if (!li) return; dragId = li.dataset.id; e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', dragId); } catch (x) {} li.classList.add('dragging'); });
$('#docList').addEventListener('dragend', () => { dragId = null; $$('#docList .drop-before,#docList .drop-into,#docList .dragging').forEach(x => x.classList.remove('drop-before', 'drop-into', 'dragging')); });
$('#docList').addEventListener('dragover', e => {
  if (!dragId) return; e.preventDefault();
  $$('#docList .drop-before,#docList .drop-into').forEach(x => x.classList.remove('drop-before', 'drop-into'));
  const t = e.target.closest('li.doc,li.part,li.part-empty'); if (!t) return;
  t.classList.add(t.classList.contains('doc') ? 'drop-before' : 'drop-into');
});
$('#docList').addEventListener('drop', e => {
  if (!dragId) return; e.preventDefault();
  const t = e.target.closest('li.doc,li.part,li.part-empty');
  if (!t) moveDoc(dragId, '');
  else if (t.classList.contains('doc')) { const tg = P.docs.find(x => x.id === t.dataset.id); if (tg && tg.id !== dragId) moveDoc(dragId, tg.partId || '', tg.id); }
  else { const pid = t.dataset.part || t.dataset.partDrop; const pt = P.parts.find(x => x.id === pid); if (pt) { pt.collapsed = false; moveDoc(dragId, pid); } }
});
function addDoc(d) {
  syncEditor();
  const cur = curDoc();
  if (cur) { d.style = d.style === DEFAULT_STYLE ? cur.style : d.style; d.layout = Object.assign({}, cur.layout); d.meta.author = d.meta.author || cur.meta.author; d.partId = cur.partId || ''; d.order = cur.order + 0.5; }
  else d.order = 1e6;
  P.docs.push(d); renumber(d.partId || ''); openDoc(d.id); markDirty();
}
$('#btnNewDoc').addEventListener('click', () => { addDoc(newDoc()); $('#docTitle').select(); });
$('#btnNewPart').addEventListener('click', async () => {
  const n = await ask('New part', 'Name the part (e.g. “Part I: The March Inland” or “Research”). Drag documents into it, or use ⇥ on a document.', 'Create', '');
  if (!n) return;
  P.parts.push({ id: uid('pt'), name: n, collapsed: false }); renderDocList(); markDirty();
});

/* page setup */
$('#btnPageSetup').addEventListener('click', () => {
  const d = curDoc(), m = d.meta, L = d.layout;
  $('#suTitleBlock').checked = m.showTitleBlock; $('#suAuthor').value = m.author; $('#suDate').value = m.date; $('#suSubtitle').value = m.subtitle;
  $('#suFont').value = L.font; $('#suSize').value = L.size; $('#suSpacing').value = L.spacing; $('#suPaper').value = L.paper; $('#suBib').value = L.bib;
  $('#suIndent').checked = !!L.indent; $('#suPageNums').checked = !!L.pageNums; $('#suTarget').value = d.target || ''; $('#suRole').value = d.role || 'body'; $('#suPdfNotes').value = L.pdfNotes || 'foot'; $('#suIndex').checked = !!L.index; $('#suMargin').value = L.marginalia || 'word'; $('#suScript').checked = !!(L.script && L.script.on); $('#suWpm').value = (L.script && L.script.wpm) || 150;
  $('#setupDlg').showModal();
});
$('#suCancel').addEventListener('click', () => $('#setupDlg').close());
$('#suOk').addEventListener('click', () => {
  const d = curDoc();
  Object.assign(d.meta, { showTitleBlock: $('#suTitleBlock').checked, author: $('#suAuthor').value.trim(), date: $('#suDate').value.trim(), subtitle: $('#suSubtitle').value.trim() });
  Object.assign(d.layout, { font: $('#suFont').value, size: $('#suSize').value, spacing: $('#suSpacing').value, paper: $('#suPaper').value, bib: $('#suBib').value, indent: $('#suIndent').checked, pageNums: $('#suPageNums').checked });
  d.target = Math.max(0, parseInt($('#suTarget').value, 10) || 0); d.role = $('#suRole').value; d.layout.pdfNotes = $('#suPdfNotes').value; d.layout.index = $('#suIndex').checked; d.layout.marginalia = $('#suMargin').value; d.layout.script = { on: $('#suScript').checked, wpm: Math.max(60, Math.min(260, parseInt($('#suWpm').value, 10) || 150)) }; setTimeout(updateScript, 0);
  $('#setupDlg').close(); updateTargets(); renderDocList();
  $('#titleBlock').innerHTML = titleBlockHTML(d); applyLayout($('#page'), d); renderRefs(true); markDirty();
});

/* ---------------- sources ---------------- */
const TYPES = [
  ['book', 'Book'], ['chapter', 'Chapter in edited book'], ['article-journal', 'Journal article'], ['article-magazine', 'Magazine article'],
  ['article-newspaper', 'Newspaper article'], ['webpage', 'Web page'], ['post-weblog', 'Blog / Substack post'], ['report', 'Report / white paper'],
  ['thesis', 'Thesis / dissertation'], ['interview', 'Interview'], ['speech', 'Speech / lecture'], ['motion_picture', 'Film / video'],
  ['broadcast', 'Podcast / broadcast episode'], ['dataset', 'Dataset'], ['map', 'Map'], ['entry-encyclopedia', 'Encyclopedia entry'],
  ['manuscript', 'Manuscript / archival item'], ['document', 'Government / other document'], ['legislation', 'Legislation / treaty'],
  ['personal_communication', 'Personal communication'], ['post', 'Social media post'], ['software', 'AI model output / software'],
];
const ROLES = [['author', 'Author'], ['editor', 'Editor'], ['translator', 'Translator'], ['container-author', 'Book author'], ['collection-editor', 'Series editor'], ['director', 'Director / host'], ['interviewer', 'Interviewer'], ['recipient', 'Recipient'], ['contributor', 'Contributor']];
const ALL = '*';
const FIELDS = [
  { k: 'title', l: 'Title', t: ALL, wide: 1 },
  { k: 'title-short', l: 'Short title (for shortened notes)', t: ALL },
  { k: 'container-title', l: { 'chapter': 'Book title', 'article-journal': 'Journal', 'article-magazine': 'Magazine', 'article-newspaper': 'Newspaper', 'webpage': 'Website name', 'post-weblog': 'Blog / newsletter name', 'broadcast': 'Program / podcast', 'entry-encyclopedia': 'Encyclopedia', 'motion_picture': 'Platform / series', 'post': 'Platform (X, Telegram…)', 'software': 'Platform (Claude.ai…)', '_': 'Container (journal, site, collection)' },
    t: ['post', 'software', 'chapter', 'article-journal', 'article-magazine', 'article-newspaper', 'webpage', 'post-weblog', 'broadcast', 'entry-encyclopedia', 'motion_picture', 'document', 'dataset', 'speech', 'interview'], wide: 1 },
  { k: 'issued', l: 'Date published', t: ALL, date: 1 },
  { k: 'edition', l: 'Edition', t: ['book', 'chapter', 'entry-encyclopedia', 'report'] },
  { k: 'volume', l: 'Volume', t: ['book', 'chapter', 'article-journal', 'article-magazine', 'entry-encyclopedia', 'legislation'] },
  { k: 'issue', l: 'Issue / no.', t: ['article-journal', 'article-magazine'] },
  { k: 'page', l: 'Pages', t: ['chapter', 'article-journal', 'article-magazine', 'article-newspaper', 'entry-encyclopedia', 'legislation'] },
  { k: 'section', l: 'Section', t: ['article-newspaper', 'legislation'] },
  { k: 'number', l: { 'report': 'Report number', 'broadcast': 'Episode number', 'legislation': 'Bill / public law no.', '_': 'Number' }, t: ['report', 'broadcast', 'legislation', 'document', 'dataset'] },
  { k: 'genre', l: { 'thesis': 'Type (PhD diss., MA thesis)', 'report': 'Type (white paper, research report)', 'interview': 'Type (interview by author)', 'speech': 'Type (lecture, keynote)', '_': 'Genre / description' }, t: ['thesis', 'report', 'interview', 'speech', 'document', 'manuscript', 'personal_communication', 'map', 'post-weblog'] },
  { k: 'collection-title', l: 'Series', t: ['book', 'chapter', 'report', 'broadcast'] },
  { k: 'collection-number', l: 'Number in series', t: ['book', 'chapter', 'report'] },
  { k: 'publisher', l: { 'thesis': 'University', 'report': 'Institution / publisher', 'broadcast': 'Network / producer', 'motion_picture': 'Studio / distributor', 'webpage': 'Publisher / owner (if different)', 'speech': 'Host organization', '_': 'Publisher' },
    t: ['book', 'chapter', 'report', 'thesis', 'broadcast', 'motion_picture', 'dataset', 'map', 'entry-encyclopedia', 'document', 'webpage', 'speech', 'manuscript', 'software', 'post'] },
  { k: 'publisher-place', l: { 'speech': 'Location', 'interview': 'Location', '_': 'Place of publication' }, t: ['book', 'chapter', 'report', 'thesis', 'map', 'document', 'speech', 'interview', 'manuscript'] },
  { k: 'medium', l: 'Medium / format (video, MP3, PDF)', t: ['motion_picture', 'broadcast', 'interview', 'speech', 'dataset', 'map', 'document'] },
  { k: 'original-date', l: 'Original publication date (reprints)', t: ['book', 'chapter'], date: 1 },
  { k: 'archive', l: 'Archive / repository', t: ['manuscript', 'document', 'map', 'interview', 'motion_picture'] },
  { k: 'archive_location', l: 'Collection, box, folder', t: ['manuscript', 'document', 'map', 'interview'] },
  { k: 'archive-place', l: 'Archive location', t: ['manuscript', 'document'] },
  { k: 'URL', l: 'URL', t: ALL, wide: 1 },
  { k: 'DOI', l: 'DOI', t: ['article-journal', 'chapter', 'book', 'report', 'dataset', 'article-magazine'] },
  { k: 'ISBN', l: 'ISBN', t: ['book', 'chapter', 'report'] },
  { k: 'accessed', l: 'Date accessed', t: ALL, date: 1 },
  { k: 'note', l: 'Extra (printed by some styles)', t: ALL, wide: 1 },
];
const fieldLabel = (f, type) => typeof f.l === 'string' ? f.l : (f.l[type] || f.l._ || f.k);
const fieldOn = (f, type) => f.t === ALL || f.t.includes(type);

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
function parseDate(str) {
  str = String(str || '').trim(); if (!str) return null;
  let m; const mi = s => MONTHS.indexOf(s.slice(0, 3).toLowerCase()) + 1;
  if ((m = str.match(/^(\d{3,4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?$/))) return { 'date-parts': [[+m[1], ...(m[2] ? [+m[2]] : []), ...(m[3] ? [+m[3]] : [])]] };
  if ((m = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/))) return { 'date-parts': [[+m[3], +m[1], +m[2]]] };
  if ((m = str.match(/^([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})$/)) && mi(m[1])) return { 'date-parts': [[+m[3], mi(m[1]), +m[2]]] };
  if ((m = str.match(/^(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s+(\d{4})$/)) && mi(m[2])) return { 'date-parts': [[+m[3], mi(m[2]), +m[1]]] };
  if ((m = str.match(/^([A-Za-z]{3,})\.?,?\s+(\d{4})$/)) && mi(m[1])) return { 'date-parts': [[+m[2], mi(m[1])]] };
  return { literal: str };
}
function fmtDate(d) {
  if (!d) return ''; if (d.literal) return d.literal; if (d.raw) return d.raw;
  const p = d['date-parts']?.[0]; if (!p || !p.length) return '';
  return p.map((v, i) => i ? String(v).padStart(2, '0') : String(v)).join('-');
}
const todayParts = () => { const t = new Date(); return { 'date-parts': [[t.getFullYear(), t.getMonth() + 1, t.getDate()]] }; };

function sortedSources() {
  return [...P.sources].sort((a, b) => {
    const la = sourceLabel(a), lb = sourceLabel(b);
    return (la.who || la.title).localeCompare(lb.who || lb.title) || la.yr.localeCompare(lb.yr);
  });
}
function renderSourceList() {
  const q = $('#qSources').value.toLowerCase().trim();
  const list = sortedSources().filter(s => !q || JSON.stringify(s.csl).toLowerCase().includes(q));
  const typeName = Object.fromEntries(TYPES);
  $('#sourceList').innerHTML = list.length ? list.map(s => {
    const l = sourceLabel(s), uses = citeCount(s.id), nn = P.notes.filter(n => n.sourceId === s.id).length;
    return `<li data-id="${s.id}" class="${panelState?.kind === 'source' && panelState.id === s.id ? 'on' : ''}"><span class="act"><button data-a="cite" title="Cite at cursor">“ Cite</button></span>
      <div class="t">${esc(l.who || '—')}${l.yr ? ' · ' + esc(l.yr) : ''}</div><div class="s">${esc(l.title)}</div>
      <div class="meta"><span>${esc(typeName[s.csl.type] || s.csl.type || '')}</span>${uses ? `<span>cited ${uses}×</span>` : ''}${nn ? `<span>${nn} note${nn > 1 ? 's' : ''}</span>` : ''}</div></li>`;
  }).join('') : `<div class="empty">${P.sources.length ? 'No sources match.' : 'No sources yet.<br>Add one with <b>+ New</b>, quick-add a DOI or ISBN, or import a Zotero CSL-JSON export.'}</div>`;
  $('#cntSources').textContent = P.sources.length;
}
function citeCount(id) {
  let n = 0; const needle = '&quot;id&quot;:&quot;' + id + '&quot;';
  P.docs.forEach(d => { const h = d.id === curDocId ? editor.innerHTML : d.html; n += h.split(needle).length - 1; });
  return n;
}
$('#qSources').addEventListener('input', renderSourceList);
$('#sourceList').addEventListener('click', e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  if (e.target.closest('button')?.dataset.a === 'cite') { insertHTMLAtCursor(citeHTML([{ id: li.dataset.id }])); toast('Citation inserted. Click it to add a page number.'); return; }
  openSource(li.dataset.id);
});
function addSource(csl) {
  const s = { id: uid('s'), csl: csl || { type: 'book', title: '' }, created: nowISO(), modified: nowISO() };
  P.sources.push(s); srcVersion++; renderSourceList(); markDirty(); return s;
}
$('#btnNewSource').addEventListener('click', () => { const s = addSource({ type: 'book', title: '' }); openSource(s.id, true); });
async function quickAdd() {
  const q = $('#quickId').value.trim(); if (!q) return;
  const b = $('#btnQuickId'); b.disabled = true; b.textContent = '…';
  try { const c = await lookupId(q), partial = takePartial(c); const s = addSource(c); $('#quickId').value = ''; openSource(s.id); toast(partial ? 'Couldn’t fetch details for that page (offline, or the site blocks lookups). The URL is saved; fill in the rest.' : 'Added. Check the details.'); }
  catch (e) { toast(e.message || 'Lookup failed'); }
  b.disabled = false; b.textContent = 'Add';
}
$('#btnQuickId').addEventListener('click', quickAdd);
$('#quickId').addEventListener('keydown', e => { if (e.key === 'Enter') quickAdd(); });

/* identifier lookups (need network; work from a local file or GitHub Pages) */
const KEEP = new Set(['type', 'title', 'title-short', 'container-title', 'collection-title', 'collection-number', 'author', 'editor', 'translator', 'container-author', 'collection-editor', 'director', 'contributor', 'issued', 'accessed', 'original-date', 'volume', 'issue', 'page', 'publisher', 'publisher-place', 'DOI', 'URL', 'ISBN', 'ISSN', 'edition', 'number', 'genre', 'medium', 'section', 'note', 'archive', 'archive_location', 'archive-place', 'language', 'abstract']);
const NAME_KEYS = ['author', 'editor', 'translator', 'container-author', 'collection-editor', 'director', 'interviewer', 'recipient', 'contributor'];
function cleanCsl(j) {
  const o = {};
  for (const k in j) {
    if (!KEEP.has(k)) continue;
    let v = j[k];
    if (Array.isArray(v) && !NAME_KEYS.includes(k)) v = v[0];
    if (NAME_KEYS.includes(k)) v = (v || []).map(n => n.literal || n.name ? { literal: n.literal || n.name } : { family: n.family || '', given: n.given || '' }).filter(n => n.literal || n.family);
    if (typeof v === 'string') v = v.replace(/<\/?(jats:)?(p|title|sec|abstract)[^>]*>/g, '').trim();
    if (v === '' || v == null) continue;
    o[k] = v;
  }
  if (o.DOI && o.URL && /doi\.org/i.test(o.URL)) delete o.URL;
  if (o.type === 'journal-article') o.type = 'article-journal';
  if (!o.type) o.type = 'article-journal';
  if (o.ISSN) delete o.ISSN;
  delete o.abstract;
  return o;
}
function splitName(full) {
  full = String(full || '').trim(); if (!full) return null;
  if (full.includes(',')) { const [f, g] = full.split(',', 2); return { family: f.trim(), given: g.trim() }; }
  const parts = full.split(/\s+/);
  if (parts.length === 1) return { literal: full };
  let fam = parts.pop(); if (/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(fam) && parts.length > 1) fam = parts.pop() + ' ' + fam;
  return { family: fam, given: parts.join(' ') };
}
async function lookupId(q) {
  q = q.trim();
  const doi = q.match(/10\.\d{4,9}\/[^\s"<>]+/);
  if (doi) {
    let r;
    try { r = await fetch('https://doi.org/' + doi[0].replace(/[.,;)]+$/, ''), { headers: { Accept: 'application/vnd.citationstyles.csl+json' } }); }
    catch (e) { throw new Error('Couldn’t reach doi.org. Check your connection, or enter the source by hand.'); }
    if (!r.ok) throw new Error('DOI not found (' + r.status + ').');
    return cleanCsl(await r.json());
  }
  const isbn = q.replace(/[^0-9Xx]/g, '');
  if ((isbn.length === 10 || isbn.length === 13) && !/^https?:/i.test(q)) {
    let j;
    try { const r = await fetch(`https://openlibrary.org/api/books?bibkeys=ISBN:${isbn}&format=json&jscmd=data`); j = await r.json(); }
    catch (e) { throw new Error('Couldn’t reach Open Library. Check your connection, or enter the source by hand.'); }
    const b = j['ISBN:' + isbn];
    if (!b) { try { return await citoid(isbn); } catch (e) { throw new Error('No record found for that ISBN. Enter it by hand.'); } }
    const yr = String(b.publish_date || '').match(/\d{4}/);
    const o = { type: 'book', title: b.subtitle ? b.title + ': ' + b.subtitle : b.title, author: (b.authors || []).map(a => splitName(a.name)).filter(Boolean), ISBN: isbn };
    if (b.publishers?.[0]?.name) o.publisher = b.publishers[0].name;
    if (b.publish_places?.[0]?.name) o['publisher-place'] = b.publish_places[0].name;
    if (yr) o.issued = { 'date-parts': [[+yr[0]]] };
    return o;
  }
  if (/^https?:\/\//i.test(q)) {
    let host = ''; try { host = new URL(q).hostname.replace(/^www\./, ''); } catch (e) {}
    const bare = { type: 'webpage', title: '', 'container-title': host, URL: q, accessed: todayParts() };
    try { const c = await citoid(q); return Object.assign(bare, c, { URL: c.URL || q, accessed: todayParts() }); }
    catch (e) { return Object.assign(bare, { __partial: true }); }
  }
  throw new Error('Enter a DOI (10.xxxx/…), a 10- or 13-digit ISBN, or a URL.');
}

function takePartial(o) { const p = !!o.__partial; delete o.__partial; return p; }
/* Wikipedia's citation service (Citoid): metadata for URLs, DOIs, ISBNs, PMIDs. Needs a connection. */
const ZOTERO_TO_CSL = {
  journalArticle: 'article-journal', magazineArticle: 'article-magazine', newspaperArticle: 'article-newspaper', webpage: 'webpage', blogPost: 'post-weblog',
  forumPost: 'post', book: 'book', bookSection: 'chapter', report: 'report', thesis: 'thesis', videoRecording: 'motion_picture', film: 'motion_picture',
  podcast: 'broadcast', radioBroadcast: 'broadcast', tvBroadcast: 'broadcast', audioRecording: 'broadcast', encyclopediaArticle: 'entry-encyclopedia',
  dictionaryEntry: 'entry-encyclopedia', document: 'document', conferencePaper: 'report', presentation: 'speech', dataset: 'dataset', map: 'map',
  statute: 'legislation', bill: 'legislation', letter: 'personal_communication', email: 'personal_communication', manuscript: 'manuscript', interview: 'interview',
  preprint: 'article-journal', computerProgram: 'software',
};
function citoidToCsl(it) {
  if (!it || typeof it !== 'object') throw new Error('No citation data');
  const o = { type: ZOTERO_TO_CSL[it.itemType] || 'webpage' };
  const str = v => Array.isArray(v) ? String(v[0] || '') : String(v || '');
  const set = (k, v) => { v = str(v).trim(); if (v) o[k] = v; };
  set('title', it.title); set('title-short', it.shortTitle);
  set('container-title', it.publicationTitle || it.websiteTitle || it.blogTitle || it.bookTitle || it.forumTitle || it.proceedingsTitle || it.encyclopediaTitle || it.dictionaryTitle || it.programTitle || it.seriesTitle && it.itemType === 'podcast' && it.seriesTitle);
  set('publisher', it.publisher || it.institution || it.university || it.label || it.network || it.studio || it.distributor);
  set('publisher-place', it.place); set('volume', it.volume); set('issue', it.issue); set('page', it.pages); set('edition', it.edition);
  set('collection-title', it.series); set('number', it.reportNumber || it.episodeNumber || it.number || it.billNumber || it.publicLawNumber);
  set('genre', it.thesisType || it.reportType || it.websiteType || it.postType || it.presentationType || it.letterType); set('section', it.section);
  set('URL', it.url); set('DOI', it.DOI); set('ISBN', str(it.ISBN).split(/\s+/)[0]);
  const dt = str(it.date).trim();
  if (dt) { const iso = dt.match(/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/); o.issued = iso ? { 'date-parts': [[+iso[1], ...(iso[2] && +iso[2] ? [+iso[2]] : []), ...(iso[3] && +iso[3] ? [+iso[3]] : [])]] } : parseDate(dt); }
  const people = { author: [], editor: [], translator: [], contributor: [], director: [], interviewer: [] };
  const roleOf = t => ({ author: 'author', editor: 'editor', seriesEditor: 'editor', translator: 'translator', director: 'director', interviewer: 'interviewer', podcaster: 'author', presenter: 'author', programmer: 'author', reporter: 'author', contributor: 'contributor', bookAuthor: 'container-author' })[t] || 'author';
  const addP = (role, first, last) => {
    first = String(first || '').trim(); last = String(last || '').trim(); if (!first && !last) return;
    (people[role] = people[role] || []).push(last && first ? { family: last, given: first } : { literal: last || first });
  };
  ['author', 'editor', 'translator', 'contributor', 'director', 'interviewer'].forEach(k => (Array.isArray(it[k]) ? it[k] : []).forEach(a => Array.isArray(a) ? addP(k, a[0], a[1]) : a && addP(k, a.firstName, a.lastName || a.name)));
  (Array.isArray(it.creators) ? it.creators : []).forEach(c => addP(roleOf(c.creatorType), c.firstName, c.lastName || c.name));
  for (const k in people) if (people[k].length) o[k] = people[k];
  if (o.DOI && o.URL && /doi\.org/i.test(o.URL)) delete o.URL;
  if (!o.title) throw new Error('No title found');
  return o;
}
async function citoid(q) {
  const url = 'https://en.wikipedia.org/api/rest_v1/data/citation/mediawiki/' + encodeURIComponent(q);
  let r = null;
  try { r = await fetch(url, { headers: { 'Api-User-Agent': 'Anabasis/1.0 (open-source writing and research tool)' } }); }
  catch (e) { try { r = await fetch(url); } catch (e2) { r = null; } }
  if (!r || !r.ok) throw new Error('Citation service unavailable');
  const j = await r.json();
  return citoidToCsl(Array.isArray(j) ? j[0] : j);
}

/* source editor panel */
function openSource(id, focusTitle = false) {
  const s = P.sources.find(x => x.id === id); if (!s) return;
  panelState = { kind: 'source', id };
  $('#panel').classList.remove('hidden');
  $('#panelTitle').textContent = 'Source';
  renderSourcePanel(s);
  $('#panelFoot').innerHTML = `<button class="primary" data-a="cite">“ Cite at cursor</button><button data-a="note">+ Note on this</button><button data-a="transcript" title="Paste an interview or video transcript and turn lines into timestamped quote notes">Transcript…</button><button data-a="pdf" title="Read this source’s PDF beside your draft">${s.pdfName ? 'Read PDF' : 'Attach PDF'}</button><span class="spacer"></span><button class="danger" data-a="del">Delete</button>`;
  renderSourceList();
  if (focusTitle) setTimeout(() => $('#panelBody [data-f="title"]')?.focus(), 30);
}
function renderSourcePanel(s) {
  const osOpen = $('#osintBox') ? $('#osintBox').open : null;
  setTimeout(() => { if (osOpen !== null && $('#osintBox')) $('#osintBox').open = osOpen; });
  const c = s.csl, type = c.type || 'book';
  const people = [];
  NAME_KEYS.forEach(role => (c[role] || []).forEach(n => people.push({ role, ...n })));
  if (!people.length) people.push({ role: 'author', family: '', given: '' });
  const fieldsHTML = FIELDS.filter(f => fieldOn(f, type)).map(f => {
    const v = f.date ? fmtDate(c[f.k]) : (c[f.k] ?? '');
    const ph = f.date ? 'YYYY-MM-DD, 2020, or May 2020' : f.k === 'title' ? 'As it should print, e.g. The Guns of August' : '';
    return `<div style="${f.wide ? 'grid-column:1/-1' : ''}"><label>${esc(fieldLabel(f, type))}</label><input data-f="${f.k}" value="${esc(v)}" placeholder="${esc(ph)}">${f.k === 'accessed' ? '' : ''}</div>`;
  }).join('');
  $('#panelBody').innerHTML = `
    <div class="lookup"><input id="srcLookup" placeholder="Fill from DOI or ISBN"><button id="srcLookupBtn">Fetch</button></div>
    <label>Type</label><select data-f="type">${TYPES.map(([k, l]) => `<option value="${k}" ${k === type ? 'selected' : ''}>${l}</option>`).join('')}</select>
    <label>People <span class="muted">(order matters)</span></label>
    <div class="people" id="people">${people.map(personRow).join('')}</div>
    <button class="ghost small" id="addPerson">+ Add person</button>
    <div class="grid2">${fieldsHTML}</div>
    ${fieldOn({ t: ['webpage', 'post-weblog', 'article-newspaper', 'article-magazine'] }, type) ? '<button class="ghost small" id="accToday" style="margin-top:4px">Set accessed date to today</button>' : ''}
    <div class="preview-box" id="srcPreview"></div>
    <label>Annotation <span class="muted">(for an annotated bibliography)</span></label><textarea id="srcAnnot" rows="3" placeholder="What this source is, what it argues, and how you use it.">${esc(s.annotation || '')}</textarea>
    ${osintSectionHTML(s)}
    <details><summary>Advanced: raw CSL-JSON (any CSL variable)</summary><textarea class="raw" id="rawCsl">${esc(JSON.stringify(c, null, 2))}</textarea><button id="applyRaw" style="margin-top:6px">Apply JSON</button></details>
    <div class="tip">Enter titles exactly as they should print. For an organization as author (RAND Corporation, U.S. Army), tick “Org”.</div>`;
  updateSourcePreview(s);
  updateOsintPreview(s);
}
function personRow(p) {
  const org = p.literal !== undefined;
  return `<div class="prow ${org ? 'org' : ''}"><select data-p="role">${ROLES.map(([k, l]) => `<option value="${k}" ${k === p.role ? 'selected' : ''}>${l}</option>`).join('')}</select>
    ${org ? `<input data-p="literal" placeholder="Organization name" value="${esc(p.literal)}">` : `<input data-p="family" placeholder="Last name" value="${esc(p.family || '')}"><input data-p="given" placeholder="First / middle" value="${esc(p.given || '')}">`}
    <span style="display:flex;gap:2px"><button class="ghost icon small" data-p="org" title="${org ? 'Switch to a person' : 'Switch to an organization'}">${org ? 'Person' : 'Org'}</button><button class="ghost icon small" data-p="rm" title="Remove">✕</button></span></div>`;
}
function readPeople() {
  const out = {};
  $$('#people .prow').forEach(r => {
    const role = $('[data-p=role]', r).value, lit = $('[data-p=literal]', r);
    let n = null;
    if (lit) { if (lit.value.trim()) n = { literal: lit.value.trim() }; }
    else { const f = $('[data-p=family]', r).value.trim(), g = $('[data-p=given]', r).value.trim(); if (f || g) n = f ? { family: f, given: g } : { literal: g }; }
    if (n) (out[role] = out[role] || []).push(n);
  });
  return out;
}
function readSourceForm(s) {
  const c = Object.assign({}, s.csl);
  const type = $('#panelBody [data-f=type]').value; c.type = type;
  NAME_KEYS.forEach(k => delete c[k]); Object.assign(c, readPeople());
  FIELDS.forEach(f => {
    const el = $(`#panelBody input[data-f="${f.k}"]`);
    if (!el) { if (!fieldOn(f, type)) delete c[f.k]; return; }
    const v = el.value.trim();
    if (!v) delete c[f.k]; else c[f.k] = f.date ? parseDate(v) : v;
  });
  return c;
}
const commitSource = debounce(s => {
  s.csl = readSourceForm(s); if ($('#osintBox')) s.osint = readOsintForm(); s.modified = nowISO(); srcVersion++;
  const raw = $('#rawCsl'); if (raw && document.activeElement !== raw) raw.value = JSON.stringify(s.csl, null, 2);
  updateSourcePreview(s); updateOsintPreview(s); renderSourceList(); renderRefs(true); markDirty();
}, 300);
function updateSourcePreview(s) {
  const doc = curDoc(), style = doc ? doc.style : DEFAULT_STYLE, isNote = STYLES[style].note;
  const bib = previewBib(style, s.id), cite = previewCluster(style, [{ id: s.id }]);
  $('#srcPreview').innerHTML = `<h5>${esc(STYLES[style].label)}</h5>` +
    (cite ? `<p><span class="muted small">${isNote ? 'Note' : 'In text'}:</span> ${cite}</p>` : '') +
    (bib ? `<p><span class="muted small">${esc(STYLES[style].bib)}:</span></p>${bib}` : '');
}
$('#panelBody').addEventListener('input', e => {
  if (panelState?.kind === 'source') {
    if (e.target.id === 'rawCsl' || e.target.id === 'srcLookup') return;
    const s = P.sources.find(x => x.id === panelState.id); if (!s) return;
    if (e.target.id === 'srcAnnot') { s.annotation = e.target.value; s.modified = nowISO(); markDirty(); return; }
    if (e.target.dataset.f === 'type') { s.csl = readSourceForm(s); renderSourcePanel(s); }
    if (e.target.dataset.o === 'type') { s.osint = readOsintForm(); renderSourcePanel(s); }
    commitSource(s);
  } else if (panelState?.kind === 'note') commitNote();
});
$('#panelBody').addEventListener('change', e => { if (panelState?.kind === 'note' && e.target.tagName === 'SELECT') commitNote(); });
$('#panelBody').addEventListener('click', async e => {
  if (panelState?.kind === 'note') return noteBodyClick(e);
  if (panelState?.kind !== 'source') return;
  const s = P.sources.find(x => x.id === panelState.id); if (!s) return;
  const t = e.target.closest('button'); if (!t) return;
  if (t.id === 'addPerson') { $('#people').insertAdjacentHTML('beforeend', personRow({ role: 'author', family: '', given: '' })); $('#people .prow:last-child input').focus(); return; }
  if (t.dataset.p === 'rm') { t.closest('.prow').remove(); commitSource(s); return; }
  if (t.dataset.p === 'org') {
    const r = t.closest('.prow'), role = $('[data-p=role]', r).value, lit = $('[data-p=literal]', r);
    let p;
    if (lit) { const sp = splitName(lit.value) || { family: '', given: '' }; p = sp.literal !== undefined ? { role, family: sp.literal, given: '' } : { role, family: sp.family, given: sp.given }; }
    else p = { role, literal: [$('[data-p=given]', r).value.trim(), $('[data-p=family]', r).value.trim()].filter(Boolean).join(' ') };
    r.outerHTML = personRow(p);
    commitSource(s); return;
  }
  if (t.id === 'accToday') { $('#panelBody input[data-f="accessed"]').value = fmtDate(todayParts()); commitSource(s); return; }
  if (t.id === 'applyRaw') {
    try { const j = JSON.parse($('#rawCsl').value); if (typeof j !== 'object' || Array.isArray(j)) throw 0; delete j.id; s.csl = j; s.modified = nowISO(); srcVersion++; renderSourcePanel(s); renderSourceList(); renderRefs(true); markDirty(); toast('Applied'); }
    catch (err) { toast('That JSON didn’t parse. It needs to be a single object.'); }
    return;
  }
  if (t.id === 'srcLookupBtn') {
    const q = $('#srcLookup').value.trim(); if (!q) return;
    t.disabled = true; t.textContent = '…';
    try { const j = await lookupId(q), partial = takePartial(j); if (partial) throw new Error('Couldn’t fetch details for that page. Fill them in by hand.'); s.csl = Object.assign({}, s.csl, j); srcVersion++; renderSourcePanel(s); renderSourceList(); renderRefs(true); markDirty(); toast('Filled from lookup. Check the details.'); }
    catch (err) { toast(err.message); }
    t.disabled = false; t.textContent = 'Fetch';
  }
});
$('#panelBody').addEventListener('keydown', e => { if (e.target.id === 'srcLookup' && e.key === 'Enter') $('#srcLookupBtn').click(); });
$('#panelFoot').addEventListener('click', async e => {
  const a = e.target.closest('button')?.dataset.a; if (!a || !panelState) return;
  if (panelState.kind === 'source') {
    const s = P.sources.find(x => x.id === panelState.id); if (!s) return;
    if (a === 'transcript') { openTranscript(s.id); return; }
    if (a === 'pdf') { readSourcePdf(s.id); return; }
    if (a === 'cite') { insertHTMLAtCursor(citeHTML([{ id: s.id }])); toast('Citation inserted. Click it to add a page number.'); }
    if (a === 'note') { const n = newNote(); n.sourceId = s.id; n.kind = 'quote'; P.notes.unshift(n); renderNoteList(); openNote(n.id); switchTab('notes'); markDirty(); }
    if (a === 'del') {
      const uses = citeCount(s.id), nn = P.notes.filter(n => n.sourceId === s.id).length;
      if (!(await ask('Delete source?', uses || nn ? `It is cited ${uses} time(s) and linked to ${nn} note(s). Those citations will show as missing.` : 'This can’t be undone after you save.', 'Delete'))) return;
      P.sources = P.sources.filter(x => x.id !== s.id); srcVersion++; closePanel(); renderSourceList(); renderNoteList(); renderRefs(true); markDirty();
    }
  } else if (panelState.kind === 'note') noteFootClick(a);
});
function closePanel() { panelState = null; $('#panel').classList.add('hidden'); renderSourceList(); renderNoteList(); }
$('#btnPanelClose').addEventListener('click', closePanel);

/* CSL-JSON import/export */
$('#btnImportCsl').addEventListener('click', () => $('#fileCsl').click());
$('#fileCsl').addEventListener('change', async e => {
  const f = e.target.files[0]; e.target.value = ''; if (!f) return;
  try {
    const raw = (await f.text()).replace(/^\uFEFF/, '');
    if (/\.(bib|ris|txt)$/i.test(f.name) || /^\s*@\w+\s*[{(]/.test(raw) || /^TY  - /m.test(raw)) { importBibRis(raw, f.name); return; }
    let j = JSON.parse(raw);
    if (j && !Array.isArray(j) && (j.app === 'OSINT Citation Generator' || (Array.isArray(j.sources) && j.sources.some(x => x && x.fields)))) { importOsintList(j); return; }
    if (!Array.isArray(j)) j = j.items || [j];
    let n = 0; j.forEach(it => { if (it && typeof it === 'object') { P.sources.push({ id: uid('s'), csl: cleanCslImport(it), created: nowISO(), modified: nowISO() }); n++; } });
    srcVersion++; renderSourceList(); markDirty(); toast(`Imported ${n} source${n === 1 ? '' : 's'}`); switchTab('sources');
  } catch (err) { toast('Couldn’t read that file as CSL-JSON.'); }
});
function cleanCslImport(it) { const o = JSON.parse(JSON.stringify(it)); delete o.id; delete o['citation-key']; return o; }

/* ---------------- OSINT Style Guide (v1.5) ----------------
   Footnotes are built by the OSINT Citation Generator's own formatter (OSINT.build / OSINT.shortForms),
   so they match https://gmichaelrapp.github.io/OSINT_Cites/ exactly. Each source keeps its OSINT-only
   details (description, qualifiers, rating, archive copy…) in s.osint; everything else comes from the
   shared source record. */
const OT = OSINT_DATA.TYPES;
const CSL_TO_OSINT = {
  book: 'book', chapter: 'chapter', 'entry-encyclopedia': 'chapter', 'article-journal': 'journal', 'article-magazine': 'news', 'article-newspaper': 'news',
  webpage: 'web', 'post-weblog': 'web', post: 'social', report: 'report', thesis: 'report', document: 'report', legislation: 'report',
  interview: 'video', speech: 'video', motion_picture: 'video', broadcast: 'video', dataset: 'live', map: 'imagery',
  manuscript: 'archival', personal_communication: 'archival', software: 'ai',
};
const OSINT_TO_CSL = { book: 'book', journal: 'article-journal', news: 'article-newspaper', chapter: 'chapter', web: 'webpage', report: 'report', social: 'post', video: 'motion_picture', archival: 'manuscript', live: 'dataset', imagery: 'map', ai: 'software' };
const DESC_BY_CSL = {
  'article-magazine': 'Magazine Article', 'post-weblog': 'Blog Post', thesis: 'Dissertation', legislation: 'Public Law / Statute', broadcast: 'Podcast',
  interview: 'Recorded Interview', speech: 'Lecture (Recorded)', 'entry-encyclopedia': 'Encyclopedia Article', document: 'Government Report',
};
const DESC_BY_TYPE = { book: 'Trade Book', journal: 'Journal Article', news: 'News Article', chapter: 'Book Section', web: 'Web Page', report: 'Research Report', social: 'Social Media Post', video: 'Video', archival: 'Archival Material', live: 'Data Dashboard', imagery: 'Commercial Satellite Imagery', ai: 'AI Model Output' };
const OSINT_KEYS = ['type', 'titleStyle', 'lead', 'descType', 'descDetails', 'quals', 'access', 'accessNote', 'rating', 'location', 'publisher', 'dateKind', 'langMode', 'origLang', 'transTitle', 'transBy', 'archiveUrl', 'archiveDate', 'note', 'shortName'];
const personName = n => n.literal || [n.given, n.family].filter(Boolean).join(' ');
function cslDateText(d, yearOnly = false) {
  if (!d) return ''; if (d.literal) return d.literal;
  const p = d['date-parts']?.[0]; if (!p || !p.length) return d.raw || '';
  if (yearOnly) return String(p[0]);
  return p.map((v, i) => i ? String(v).padStart(2, '0') : String(v)).join('-');
}
function osintTypeOf(s) { return (s.osint && s.osint.type) || CSL_TO_OSINT[s.csl.type] || 'web'; }
function osintAutoDetails(c, type) {
  if (type === 'journal' || type === 'news') return [c.volume && 'Vol. ' + c.volume, c.issue && 'No. ' + c.issue].filter(Boolean).join(', ');
  if (type === 'report' && c.number) return 'Report No. ' + c.number;
  if (type === 'video' && c.number) return 'Ep. ' + c.number;
  return '';
}
/* Build the generator's field state for one source (+ the locator of one citation). */
function osintState(s, cite = {}) {
  const c = s.csl || {}, o = s.osint || {};
  const type = osintTypeOf(s), def = OT[type] || OT.web;
  const yearOnly = type === 'book' || type === 'journal' || type === 'chapter';
  let locator = '';
  if (cite.locator) locator = (!cite.label || cite.label === 'page') ? String(cite.locator) : cite.label === 'timestamp' ? 'at ' + cite.locator : cite.label + ' ' + cite.locator;
  else if ((type === 'journal' || type === 'chapter') && c.page) locator = c.page;
  const lead = /^(see|cited in|quoted in)$/i.test((cite.prefix || '').trim()) ? (cite.prefix.trim()[0].toUpperCase() + cite.prefix.trim().slice(1).toLowerCase()) : (o.lead || '');
  return {
    type, titleStyle: o.titleStyle || def.style, lead,
    authors: (c.author || []).map(personName).join('\n'),
    editors: (c.editor || []).map(personName).join('\n'),
    translators: (c.translator || []).map(personName).join('\n'),
    contributors: (c.contributor || []).map(personName).join('\n'),
    title: c.title || '', shortTitle: c['title-short'] || '', shortName: o.shortName || '',
    langMode: o.langMode || 'en', origLang: o.origLang || '', transTitle: o.transTitle || '', transBy: o.transBy || '',
    location: o.location || c['container-title'] || '',
    descType: o.descType || DESC_BY_CSL[c.type] || DESC_BY_TYPE[type] || '',
    descDetails: o.descDetails || osintAutoDetails(c, type),
    quals: o.quals || [], access: o.access || [], accessNote: o.accessNote || '', rating: o.rating || '',
    publisher: o.publisher || ((type === 'journal' || type === 'news') ? '' : (c.publisher || '')),
    date: cslDateText(c.issued, yearOnly), dateKind: o.dateKind || '',
    accessed: (def.live || o.dateKind) ? cslDateText(c.accessed) : '',
    url: c.DOI ? c.DOI : (c.URL || ''),
    archiveUrl: o.archiveUrl || '', archiveDate: o.archiveDate || '',
    note: [o.note, cite.suffix].filter(Boolean).join(' '),
    locator,
    volatile: !!def.volatile, live: !!def.live, dayDate: !!def.dayDate, ai: !!def.ai,
  };
}
/* One footnote for a citation cluster; `seen` tracks sources already given in full. */
function osintCluster(items, seen) {
  const segs = items.map(it => {
    const s = P.sources.find(x => x.id === it.id); if (!s) return [{ s: '[missing source]', i: false }];
    const st = osintState(s, it);
    let seg;
    if (seen.has(s.id)) {
      seg = OSINT.shortForms(st).short.map(x => ({ s: x.s, i: x.i }));
      if (st.lead) seg.unshift({ s: st.lead + ' ', i: false });
      if (it.suffix) { const l = seg[seg.length - 1]; l.s = l.s.replace(/\.$/, '') + '. ' + it.suffix.replace(/[.\s]*$/, '.'); }
    } else seg = OSINT.build(st).seg;
    seen.add(s.id);
    return seg;
  });
  return OSINT.toHTML(OSINT.joinSources(segs));
}
function computeOsint(doc, markers) {
  let n = 0; const notes = [], disp = [], seen = new Set();
  markers.forEach(m => {
    n++;
    if (m.classList.contains('fn')) { disp.push({ m, type: 'fn', n }); notes.push({ n, html: inlineMd(m.dataset.text) }); return; }
    const items = markerItems(m).filter(it => P.sources.some(s => s.id === it.id));
    if (!items.length) { disp.push({ m, type: 'missing', n }); notes.push({ n, html: '<span class="refs-missing">[source deleted. Click the marker to fix it.]</span>' }); return; }
    const html = osintCluster(items, seen);
    disp.push({ m, type: 'cite', n, html }); notes.push({ n, html });
  });
  return { isNote: true, disp, notes, bib: null, heading: '' };
}

/* --- source panel section --- */
let osintDatalistReady = false;
function ensureOsintDatalist() {
  if (osintDatalistReady) return; osintDatalistReady = true;
  const dl = document.createElement('datalist'); dl.id = 'osintLib';
  dl.innerHTML = OSINT_DATA.LIB.map(c => c.g.map(g => g.i.map(x => `<option value="${esc(x)}">${esc(c.c + ' · ' + g.n)}</option>`).join('')).join('')).join('');
  document.body.appendChild(dl);
}
const REL_L = 'ABCDEF', REL_N = { A: 'Highly reliable', B: 'Usually reliable', C: 'Fairly reliable', D: 'Not usually reliable', E: 'Unreliable', F: 'Reliability unknown' };
const CRED_N = { 1: 'Confirmed', 2: 'Probably true', 3: 'Possibly true', 4: 'Doubtful', 5: 'Improbable', 6: 'Truth unknown' };
function osintSectionHTML(s) {
  ensureOsintDatalist();
  const o = s.osint || {}, c = s.csl, autoType = CSL_TO_OSINT[c.type] || 'web', type = o.type || autoType, def = OT[type];
  const v = k => esc(o[k] || ''), sel = (k, val) => (o[k] || '') === val ? 'selected' : '';
  const open = curDoc() && STYLES[curDoc().style].custom;
  const quals = o.quals || [], access = o.access || [];
  const qHTML = OSINT_DATA.QUALIFIERS.map(([g, list]) => `<div class="small muted" style="margin-top:6px">${esc(g)}</div><div class="radio-row">` +
    list.map(q => `<label><input type="checkbox" data-oq="${esc(q)}" ${quals.includes(q) ? 'checked' : ''}> ${esc(q)}</label>`).join('') + '</div>').join('');
  const aHTML = OSINT_DATA.ACCESS.map(([k, l]) => `<label><input type="checkbox" data-oa="${esc(k)}" ${access.includes(k) ? 'checked' : ''}> ${esc(l)}</label>`).join('');
  const r = o.rating || '';
  return `<details id="osintBox" ${open ? 'open' : ''}><summary><b>OSINT Style Guide details</b> <span class="muted">(used when a document is set to OSINT style)</span></summary>
    <div class="preview-box" id="osintPreview" style="margin-top:10px"></div>
    <div class="grid2">
      <div><label>OSINT source type</label><select data-o="type"><option value="">Auto: ${esc(OT[autoType].label)}</option>${Object.keys(OT).map(k => `<option value="${k}" ${sel('type', k)}>${esc(OT[k].label)}</option>`).join('')}</select></div>
      <div><label>Title set in</label><select data-o="titleStyle"><option value="">Auto: ${def.style}</option><option value="quotes" ${sel('titleStyle', 'quotes')}>Quotation marks</option><option value="italics" ${sel('titleStyle', 'italics')}>Italics</option><option value="plain" ${sel('titleStyle', 'plain')}>Plain (description, no title)</option></select></div>
      <div style="grid-column:1/-1"><label>Description: kind of source <span class="muted">(${OSINT_DATA.LIB.reduce((n, c) => n + c.g.reduce((m, g) => m + g.i.length, 0), 0)}-term library; type to search)</span></label><input data-o="descType" list="osintLib" value="${v('descType')}" placeholder="${esc(DESC_BY_CSL[c.type] || DESC_BY_TYPE[type])} (default). Suggested: ${esc(def.picks.slice(0, 4).join(', '))}"></div>
      <div style="grid-column:1/-1"><label>Details <span class="muted">(volume and issue, report no., episode, coordinates; separate with ;)</span></label><input data-o="descDetails" value="${v('descDetails')}" placeholder="${esc(osintAutoDetails(c, type) || def.ph.descDetails || '')}"></div>
      <div><label>Reliability of source</label><select data-o="relA"><option value="">— no rating —</option>${[...REL_L].map(L => `<option value="${L}" ${r[0] === L ? 'selected' : ''}>${L}: ${REL_N[L]}</option>`).join('')}</select></div>
      <div><label>Credibility of information</label><select data-o="rel1"><option value="">—</option>${[1, 2, 3, 4, 5, 6].map(N => `<option value="${N}" ${r[1] === String(N) ? 'selected' : ''}>${N}: ${CRED_N[N]}</option>`).join('')}</select></div>
      <div><label>Opens with</label><select data-o="lead"><option value="">—</option>${['See', 'Cited in', 'Quoted in'].map(x => `<option ${sel('lead', x)}>${x}</option>`).join('')}</select></div>
      <div><label>Date is</label><select data-o="dateKind"><option value="">Publication date</option><option value="updated" ${sel('dateKind', 'updated')}>Last updated (live source)</option><option value="captured" ${sel('dateKind', 'captured')}>Captured (imagery)</option></select></div>
      <div><label>${esc(def.loc || 'Location')} <span class="muted">(italic slot)</span></label><input data-o="location" value="${v('location')}" placeholder="${esc(c['container-title'] || def.ph.location || '')}"></div>
      <div><label>${esc(def.pub || 'Publisher')}</label><input data-o="publisher" value="${v('publisher')}" placeholder="${esc((type === 'journal' || type === 'news') ? 'Usually blank' : (c.publisher || def.ph.publisher || ''))}"></div>
    </div>
    <label>Access</label><div class="radio-row">${aHTML}</div>
    <input data-o="accessNote" value="${v('accessNote')}" placeholder="Other access note" class="${access.includes('other') ? '' : 'hidden'}">
    <details style="margin-top:8px"><summary>Qualifiers about this copy${quals.length ? ` (${quals.length} set)` : ''}</summary>${qHTML}</details>
    <details style="margin-top:8px" ${o.langMode && o.langMode !== 'en' ? 'open' : ''}><summary>Language of the source</summary>
      <div class="grid2"><div><label>Source is</label><select data-o="langMode"><option value="en">In English</option><option value="foreign" ${sel('langMode', 'foreign')}>In another language</option><option value="published" ${sel('langMode', 'published')}>A published English translation</option></select></div>
      <div><label>Original language</label><input data-o="origLang" value="${v('origLang')}" placeholder="Chinese, Russian…"></div>
      <div><label>Title in English</label><input data-o="transTitle" value="${v('transTitle')}"></div>
      <div><label>You read it through</label><select data-o="transBy"><option value="">—</option><option value="own" ${sel('transBy', 'own')}>Your own translation</option><option value="machine" ${sel('transBy', 'machine')}>Machine translation</option></select></div></div>
    </details>
    <div class="grid2">
      <div><label>Archive copy URL</label><input data-o="archiveUrl" value="${v('archiveUrl')}" placeholder="https://archive.ph/…"></div>
      <div><label>Captured on</label><input data-o="archiveDate" value="${v('archiveDate')}" placeholder="14 February 2026"></div>
    </div>
    ${c.URL ? `<div class="small" style="margin-top:4px">Make a copy: <a href="https://web.archive.org/save/${esc(c.URL)}" target="_blank" rel="noopener">Wayback Machine</a> · <a href="https://archive.ph/?url=${encodeURIComponent(c.URL)}" target="_blank" rel="noopener">archive.today</a></div>` : ''}
    <label>Commentary after the citation</label><input data-o="note" value="${v('note')}" placeholder="e.g. Location established by matching the skyline to…">
    <label>Short-form name <span class="muted">(defaults to surnames)</span></label><input data-o="shortName" value="${v('shortName')}">
    <div class="tip">Authors, title, date, URL/DOI and the short title come from the fields above. In a citation, “See”, “Cited in” or “Quoted in” typed as the prefix becomes the opening word.</div>
  </details>`;
}
function readOsintForm() {
  const o = {}, box = $('#osintBox');
  $$('[data-o]', box).forEach(el => { const val = el.value.trim(); if (val && !['relA', 'rel1'].includes(el.dataset.o)) o[el.dataset.o] = val; });
  const A = $('[data-o=relA]', box).value, N = $('[data-o=rel1]', box).value;
  if (A && N) o.rating = A + N;
  if (o.langMode === 'en') delete o.langMode;
  const q = $$('[data-oq]', box).filter(x => x.checked).map(x => x.dataset.oq); if (q.length) o.quals = q;
  const a = $$('[data-oa]', box).filter(x => x.checked).map(x => x.dataset.oa); if (a.length) o.access = a;
  $('[data-o=accessNote]', box).classList.toggle('hidden', !a.includes('other'));
  return o;
}
function updateOsintPreview(s) {
  const box = $('#osintPreview'); if (!box) return;
  const st = osintState(s, {}), r = OSINT.build(st);
  const sh = OSINT.toHTML(OSINT.shortForms(Object.assign({}, st, { locator: '' })).short);
  const checks = r.checks.filter(c => c.level !== 'note' || /description|bracket/i.test(c.msg));
  const defaulted = !(s.osint && s.osint.descType);
  box.innerHTML = `<h5>OSINT footnote</h5><p>${OSINT.toHTML(r.seg) || '<span class="muted">—</span>'}</p><p><span class="muted small">Short form:</span> ${sh}</p>` +
    (defaulted ? `<p class="small" style="font-family:var(--ui);color:#b26b00">Description “${esc(st.descType)}” is a default. Pick the most specific kind of source below.</p>` : '') +
    (checks.length ? `<div class="small" style="font-family:var(--ui)">${checks.map(c => `<div style="margin-top:3px"><b style="color:${c.level === 'fix' ? 'var(--danger)' : '#b26b00'}">${c.level === 'fix' ? 'Fix' : c.level === 'check' ? 'Check' : 'Note'}:</b> ${esc(c.msg)}</div>`).join('')}</div>` : '');
}

/* --- OSINT Citation Generator list files (format 2) --- */
function nameFromOsint(n) {
  n = String(n || '').trim(); if (!n) return null;
  if (/^@/.test(n) || /\d/.test(n) || n.split(/\s+/).length === 1 || n.split(/\s+/).length > 4 ||
    /\b(Staff|Department|Ministry|Institute|University|Corporation|Council|Bureau|Office|Agency|Labs?|PBC|Inc|LLC|Ltd|News|Organization|Commission|Government|House|Press|Group|Project|Center|Centre|Foundation|Command|Navy|Army|Force)\b/i.test(n)) return { literal: n };
  return splitName(n);
}
function importOsintList(j) {
  const linesOf = v => String(v || '').split(/[\n;]+/).map(x => x.trim()).filter(Boolean);
  let n = 0;
  (j.sources || []).forEach(x => {
    const f = x && (x.fields || x.st); if (!f || typeof f !== 'object') return;
    const type = OT[f.type] ? f.type : 'web';
    const csl = { type: OSINT_TO_CSL[type], title: f.title || '' };
    [['authors', 'author'], ['editors', 'editor'], ['translators', 'translator'], ['contributors', 'contributor']].forEach(([a, b]) => {
      const ns = linesOf(f[a]).map(nameFromOsint).filter(Boolean); if (ns.length) csl[b] = ns;
    });
    if (f.location && type !== 'book' && type !== 'report') csl['container-title'] = f.location;
    if (f.publisher) csl.publisher = f.publisher;
    if (f.shortTitle) csl['title-short'] = f.shortTitle;
    if (f.date) csl.issued = parseDate(OSINT.normDate(f.date).text);
    if (f.accessed) csl.accessed = parseDate(OSINT.normDate(f.accessed).text);
    if (f.url) { const u = OSINT.normUrl(f.url).url; const d = u.match(/^https:\/\/doi\.org\/(.+)$/); if (d) csl.DOI = d[1]; else csl.URL = u; }
    if (f.locator && (type === 'journal' || type === 'chapter') && /^[\d\s,–—-]+$/.test(f.locator)) csl.page = f.locator.replace(/\s*-\s*/g, '–');
    const o = { type };
    OSINT_KEYS.forEach(k => { if (k === 'type') return; const val = f[k]; if (Array.isArray(val) ? val.length : (typeof val === 'string' && val.trim())) o[k] = Array.isArray(val) ? val.filter(v => typeof v === 'string') : val.trim(); });
    if (o.titleStyle === OT[type].style) delete o.titleStyle;
    if (o.langMode === 'en') delete o.langMode;
    P.sources.push({ id: uid('s'), csl, osint: o, created: nowISO(), modified: nowISO() }); n++;
  });
  srcVersion++; renderSourceList(); markDirty(); switchTab('sources');
  toast(`Imported ${n} source${n === 1 ? '' : 's'} from the OSINT list${j.name ? ' “' + j.name + '”' : ''}`);
}
function exportOsintList() {
  const items = sortedSources().map(s => {
    const st = osintState(s, {});
    ['volatile', 'live', 'dayDate', 'ai'].forEach(k => delete st[k]);
    Object.keys(st).forEach(k => { if (st[k] === '' || (Array.isArray(st[k]) && !st[k].length)) delete st[k]; });
    return { id: s.id, st };
  });
  return OSINT.listFile(P.title, items);
}

/* ---------------- notes ---------------- */
const KINDS = [['quote', 'Quote'], ['paraphrase', 'Paraphrase'], ['summary', 'Summary'], ['idea', 'Idea']];
function allTags() { const s = new Set(); P.notes.forEach(n => n.tags.forEach(t => s.add(t))); return [...s].sort((a, b) => a.localeCompare(b)); }
function renderNoteList() {
  const q = $('#qNotes').value.toLowerCase().trim();
  const tags = allTags();
  if (noteTagFilter && !tags.includes(noteTagFilter)) noteTagFilter = null;
  $('#tagChips').innerHTML = tags.map(t => `<span class="chip ${t === noteTagFilter ? 'on' : ''}" data-t="${esc(t)}">#${esc(t)}</span>`).join('');
  const list = [...P.notes].sort((a, b) => (b.pinned - a.pinned) || b.modified.localeCompare(a.modified))
    .filter(n => (!noteTagFilter || n.tags.includes(noteTagFilter)) && (!q || (n.title + ' ' + n.body + ' ' + n.tags.join(' ')).toLowerCase().includes(q)));
  $('#noteList').innerHTML = list.length ? list.map(n => {
    const s = n.sourceId && P.sources.find(x => x.id === n.sourceId), l = s ? sourceLabel(s) : null;
    return `<li data-id="${n.id}" draggable="true" class="note-li ${n.color ? 'c-' + n.color : ''} ${panelState?.kind === 'note' && panelState.id === n.id ? 'on' : ''}"><span class="act"><button data-a="ins" title="Insert into document at cursor">Insert</button></span>
      <div class="t">${n.pinned ? '<span class="pin-dot" title="Pinned">●</span>' : ''}<span class="kind">${esc(n.kind)}</span> ${esc(n.title || firstLine(n.body) || 'Untitled note')}</div>
      <div class="s">${esc(n.body.replace(/[#*_>`]/g, '').slice(0, 160))}</div>
      <div class="meta">${n.tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}${l ? `<span>↳ ${esc(l.who || l.title)}${n.locator ? ', ' + esc(n.locator) : ''}</span>` : ''}</div></li>`;
  }).join('') : `<div class="empty">${P.notes.length ? 'No notes match.' : 'No notes yet.<br>Notes can be quotes, paraphrases or ideas, linked to a source and page, then inserted or compiled into a draft.'}</div>`;
  $('#cntNotes').textContent = P.notes.length;
}
const firstLine = s => String(s || '').split('\n').find(x => x.trim())?.replace(/^#+\s*/, '').slice(0, 80) || '';
$('#qNotes').addEventListener('input', renderNoteList);
$('#tagChips').addEventListener('click', e => { const c = e.target.closest('.chip'); if (!c) return; noteTagFilter = noteTagFilter === c.dataset.t ? null : c.dataset.t; renderNoteList(); });
$('#noteList').addEventListener('click', e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  if (e.target.closest('button')?.dataset.a === 'ins') { insertNote(P.notes.find(n => n.id === li.dataset.id)); return; }
  openNote(li.dataset.id);
});
$('#btnNewNote').addEventListener('click', () => { const n = newNote(); if (noteTagFilter) n.tags = [noteTagFilter]; P.notes.unshift(n); renderNoteList(); openNote(n.id, true); markDirty(); });
let notePreview = false;
function openNote(id, focus = false) {
  const n = P.notes.find(x => x.id === id); if (!n) return;
  panelState = { kind: 'note', id }; notePreview = false;
  $('#panel').classList.remove('hidden'); $('#panelTitle').textContent = 'Note';
  const opts = sortedSources().map(s => { const l = sourceLabel(s); return `<option value="${s.id}" ${s.id === n.sourceId ? 'selected' : ''}>${esc((l.who ? l.who + ', ' : '') + l.title).slice(0, 70)}</option>`; }).join('');
  $('#panelBody').innerHTML = `
    <label>Title</label><input data-n="title" value="${esc(n.title)}" placeholder="Short handle for this note">
    <div class="grid2"><div><label>Kind</label><select data-n="kind">${KINDS.map(([k, l]) => `<option value="${k}" ${k === n.kind ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
    <div><label>Tags <span class="muted">(comma-separated)</span></label><input data-n="tags" value="${esc(n.tags.join(', '))}" placeholder="chapter 3, proxies"></div></div>
    <label style="display:flex;justify-content:space-between;align-items:end">Note <span><button class="ghost small" data-a="mdtoggle" style="padding:1px 6px">Preview</button></span></label>
    <textarea class="note-body" data-n="body" placeholder="Markdown: **bold**, *italic*, - lists, > quotes">${esc(n.body)}</textarea>
    <div class="md-preview hidden" id="mdPreview"></div>
    <label>Source</label><select data-n="sourceId"><option value="">— none —</option>${opts}</select>
    <label>Event date <span class="muted">(puts the card on the timeline: 1914-08-04, Aug 1914, c. 1680)</span></label><input data-n="date" value="${esc(n.date || '')}" placeholder="When it happened, not when it was published">
    <div class="grid2" style="grid-template-columns:110px 1fr"><div><label>Locator</label><select data-n="label">${LOCATOR_LABELS.map(x => `<option ${x === n.label ? 'selected' : ''}>${x}</option>`).join('')}</select></div>
    <div><label>&nbsp;</label><input data-n="locator" value="${esc(n.locator)}" placeholder="e.g. 112–13"></div></div>
    <div class="grid2" style="grid-template-columns:1fr auto">
      <div><label>Pile <span class="muted">(board)</span></label><select data-n="pile"><option value="">Unsorted</option>${P.piles.map(p => `<option value="${p.id}" ${p.id === n.pile ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
      <div><label>Card</label><div class="swatches">${CARD_COLORS.map(c => `<button class="sw ${c ? 'c-' + c : 'none'} ${c === (n.color || '') ? 'on' : ''}" data-a="color" data-c="${c}" title="${c || 'No color'}"></button>`).join('')}<button class="ghost small pin-btn ${n.pinned ? 'on' : ''}" data-a="pin" title="Pin to the top">${n.pinned ? 'Pinned' : 'Pin'}</button></div></div>
    </div>
    <div class="note-links" id="noteLinks">${noteLinksHTML(n)}</div>
    <div class="muted small" style="margin-top:12px">Created ${new Date(n.created).toLocaleString()} · edited ${relTime(n.modified)} · Link notes with [[Note title]]</div>`;
  $('#panelFoot').innerHTML = `<button class="primary" data-a="ins">Insert at cursor</button><button data-a="split" title="Split this card in two at the cursor in the note text">Split</button><button data-a="dupn">Duplicate</button><span class="spacer"></span><button class="danger" data-a="deln">Delete</button>`;
  renderNoteList();
  if (focus) setTimeout(() => $('#panelBody [data-n=title]').focus(), 30);
}
const commitNote = debounce(() => {
  if (panelState?.kind !== 'note') return;
  const n = P.notes.find(x => x.id === panelState.id); if (!n) return;
  const g = k => $(`#panelBody [data-n="${k}"]`).value;
  n.title = g('title').trim(); n.kind = g('kind'); n.body = g('body'); n.sourceId = g('sourceId'); n.label = g('label'); n.locator = g('locator').trim();
  n.tags = g('tags').split(',').map(t => t.trim().replace(/^#/, '')).filter(Boolean).filter((t, i, a) => a.indexOf(t) === i);
  n.pile = g('pile'); n.date = g('date').trim();
  n.modified = nowISO();
  if (notePreview) $('#mdPreview').innerHTML = mdNote(n.body);
  $('#noteLinks').innerHTML = noteLinksHTML(n);
  renderNoteList(); renderBoardSoon(); markDirty();
}, 250);
function noteBodyClick(e) {
  const wl = e.target.closest('a[href^="#note:"]'); if (wl) { e.preventDefault(); followNoteLink(decodeURIComponent(wl.getAttribute('href').slice(6))); return; }
  const btn = e.target.closest('button'), a = btn?.dataset.a;
  const n = P.notes.find(x => x.id === panelState.id);
  if (a === 'color' && n) { n.color = btn.dataset.c; n.modified = nowISO(); $$('#panelBody .sw').forEach(x => x.classList.toggle('on', x === btn)); renderNoteList(); renderBoard(); markDirty(); return; }
  if (a === 'pin' && n) { n.pinned = !n.pinned; btn.classList.toggle('on', n.pinned); btn.textContent = n.pinned ? 'Pinned' : 'Pin'; renderNoteList(); renderBoard(); markDirty(); return; }
  if (a === 'mdtoggle') {
    notePreview = !notePreview;
    const ta = $('#panelBody [data-n=body]'), pv = $('#mdPreview');
    pv.innerHTML = mdNote(ta.value);
    ta.classList.toggle('hidden', notePreview); pv.classList.toggle('hidden', !notePreview);
    e.target.textContent = notePreview ? 'Edit' : 'Preview';
  }
}
async function noteFootClick(a) {
  const n = P.notes.find(x => x.id === panelState.id); if (!n) return;
  if (a === 'ins') insertNote(n);
  if (a === 'split') splitNote(n);
  if (a === 'dupn') { const c = Object.assign({}, n, { id: uid('n'), title: n.title + ' (copy)', tags: [...n.tags], created: nowISO(), modified: nowISO() }); P.notes.unshift(c); openNote(c.id); markDirty(); }
  if (a === 'deln') { if (!(await ask('Delete note?', `“${n.title || firstLine(n.body) || 'Untitled note'}” will be removed.`, 'Delete'))) return; P.notes = P.notes.filter(x => x.id !== n.id); closePanel(); renderBoard(); markDirty(); }
}
/* turn a note into document HTML */
function noteToHTML(n, { withCite = true, heading = '' } = {}) {
  const hasSrc = withCite && n.sourceId && P.sources.some(s => s.id === n.sourceId);
  const cite = hasSrc ? citeHTML([Object.assign({ id: n.sourceId }, n.locator ? { locator: n.locator, label: n.label || 'page' } : {})]) : '';
  let h = heading ? `<h2>${esc(heading)}</h2>` : '';
  const body = stripWikiLinks(n.body).trim();
  if (n.kind === 'quote' && body) {
    const words = body.split(/\s+/).length;
    let plain = body.replace(/^\s*>\s?/gm, '').trim();
    if (/^[“"]/.test(plain) && /[”"]$/.test(plain) && plain.length > 1) plain = plain.slice(1, -1).trim(); // drop quote marks only when they wrap the whole passage
    if (words >= 100 || plain.includes('\n\n')) {
      const inner = sanitize(marked.parse(plain));
      h += `<blockquote data-qn="${n.id}">${inner.replace(/<\/p>\s*$/, cite + '</p>')}</blockquote>`;
    } else { // a run-in quotation: quotation marks inside it become single quotes
      const inner = plain.replace(/\s*\n\s*/g, ' ').replace(/"([^"]*)"/g, '‘$1’').replace(/“/g, '‘').replace(/”/g, '’');
      h += `<p>“<span class="qlink" data-qn="${n.id}">${sanitize(marked.parseInline(inner))}</span>”${cite}</p>`;
    }
  } else if (body) {
    const inner = sanitize(marked.parse(body));
    h += cite ? inner.replace(/<\/(p|li|blockquote)>\s*$/, m => cite + m) : inner;
    if (cite && !/<\/(p|li|blockquote)>\s*$/.test(inner)) h += `<p>${cite}</p>`;
  }
  return h;
}
function insertNote(n) {
  if (!n) return;
  insertBlocksAtCursor(noteToHTML(n));
  toast('Note inserted into “' + (curDoc().title || 'document') + '”');
}

/* markdown import (e.g., from Notecards) */
$('#btnImportMd').addEventListener('click', () => openMdImport());
$('#fileMd').addEventListener('change', e => { const f = [...e.target.files]; e.target.value = ''; if (f.length) importMarkdownFiles(f); });

/* compile */
let cmOrder = [];
$('#btnCompile').addEventListener('click', () => {
  if (!P.notes.length) { toast('No notes to compile yet.'); return; }
  $('#cmTag').innerHTML = '<option value="">All tags</option>' + allTags().map(t => `<option ${t === noteTagFilter ? 'selected' : ''}>${esc(t)}</option>`).join('');
  $('#cmSource').innerHTML = '<option value="">All sources</option><option value="__none">No source</option>' + sortedSources().map(s => { const l = sourceLabel(s); return `<option value="${s.id}">${esc((l.who ? l.who + ', ' : '') + l.title).slice(0, 60)}</option>`; }).join('');
  cmOrder = [...P.notes].sort(boardSort).map(n => ({ id: n.id, on: true }));
  renderCompile(); $('#compileDlg').showModal();
});
function cmVisible() {
  const tag = $('#cmTag').value, src = $('#cmSource').value;
  return cmOrder.filter(o => { const n = P.notes.find(x => x.id === o.id); return n && (!tag || n.tags.includes(tag)) && (!src || (src === '__none' ? !n.sourceId : n.sourceId === src)); });
}
function renderCompile() {
  const vis = cmVisible();
  $('#cmList').innerHTML = vis.length ? vis.map((o, i) => {
    const n = P.notes.find(x => x.id === o.id);
    return `<li data-id="${o.id}"><input type="checkbox" ${o.on ? 'checked' : ''}><span><span class="kind">${esc(n.kind)}</span> ${esc(n.title || firstLine(n.body) || 'Untitled')} <span class="muted small">${n.tags.map(t => '#' + esc(t)).join(' ')}</span></span>
      <button class="ghost" data-a="up" ${i ? '' : 'disabled'} title="Move up">↑</button><button class="ghost" data-a="down" ${i < vis.length - 1 ? '' : 'disabled'} title="Move down">↓</button></li>`;
  }).join('') : '<li class="muted">No notes match these filters.</li>';
  $('#cmCount').textContent = vis.filter(o => o.on).length + ' selected';
}
['cmTag', 'cmSource'].forEach(id => $('#' + id).addEventListener('change', renderCompile));
$('#cmList').addEventListener('click', e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  const o = cmOrder.find(x => x.id === li.dataset.id);
  if (e.target.type === 'checkbox') { o.on = e.target.checked; $('#cmCount').textContent = cmVisible().filter(x => x.on).length + ' selected'; return; }
  const a = e.target.closest('button')?.dataset.a; if (!a) return;
  const vis = cmVisible(), vi = vis.indexOf(o), other = vis[a === 'up' ? vi - 1 : vi + 1]; if (!other) return;
  const i1 = cmOrder.indexOf(o), i2 = cmOrder.indexOf(other); [cmOrder[i1], cmOrder[i2]] = [cmOrder[i2], cmOrder[i1]];
  renderCompile();
});
$('#cmCancel').addEventListener('click', () => $('#compileDlg').close());
$('#cmOk').addEventListener('click', () => {
  const chosen = cmVisible().filter(o => o.on).map(o => P.notes.find(n => n.id === o.id));
  if (!chosen.length) { toast('Select at least one note.'); return; }
  const group = $('#cmGroup').value, titles = $('#cmTitles').checked, withCite = $('#cmCite').checked;
  let html = '';
  const one = (n, lvl) => noteToHTML(n, { withCite, heading: '' }).replace(/^/, titles && (n.title || '').trim() ? `<h${lvl}>${esc(n.title)}</h${lvl}>` : '');
  if (group === 'order') html = chosen.map(n => one(n, 2)).join('');
  else {
    const groups = new Map();
    chosen.forEach(n => {
      const keys = group === 'tag' ? (n.tags.length ? n.tags.slice(0, 1) : ['Untagged']) : [n.sourceId ? (sourceLabel(P.sources.find(s => s.id === n.sourceId) || { csl: {} }).title) : 'No source'];
      keys.forEach(k => { if (!groups.has(k)) groups.set(k, []); groups.get(k).push(n); });
    });
    groups.forEach((ns, k) => { html += `<h2>${esc(group === 'tag' && k !== 'Untagged' ? k.charAt(0).toUpperCase() + k.slice(1) : k)}</h2>` + ns.map(n => one(n, 3)).join(''); });
  }
  $('#compileDlg').close();
  const dest = $('input[name=cmDest]:checked').value;
  if (dest === 'cursor' && curDoc()) { insertBlocksAtCursor(html); toast(`Inserted ${chosen.length} notes`); return; }
  const d = newDoc('Draft from notes — ' + new Date().toLocaleDateString(), html || '<p><br></p>');
  addDoc(d); switchTab('docs'); toast(`Compiled ${chosen.length} notes into a new draft`);
});

/* ---------------- export ---------------- */
function docClassAndStyle(doc) {
  const tmp = document.createElement('div'); tmp.className = 'docbody'; applyLayout(tmp, doc);
  return { cls: tmp.className, style: tmp.getAttribute('style') || '' };
}
/* mode: 'html' | 'md' */
function buildExport(doc, mode = 'html') {
  if (doc.id === curDocId) syncEditor();
  const tmp = document.createElement('div'); tmp.innerHTML = stripCp(doc.html);
  $$('.flag', tmp).forEach(f => { const m = document.createElement('mark'); m.textContent = `[${(FLAG_KINDS[f.dataset.kind] || FLAG_KINDS.tk).label}${f.dataset.note ? ': ' + f.dataset.note : ''}]`; f.replaceWith(m); });
  $$('.qlink', tmp).forEach(q => q.replaceWith(...q.childNodes));
  $$('[data-qn]', tmp).forEach(q => q.removeAttribute('data-qn'));
  const figs = prepExportFigures(tmp); fillAbbreviations(tmp);
  const mgWant = doc.layout.marginalia || 'word';
  const mg = mgWant === 'page' && mode !== 'substack' ? collectMarginalia(tmp, mode) : [];
  if (mode !== 'docx' || mgWant !== 'word') $$('.cmt', tmp).forEach(c => c.replaceWith(...c.childNodes));
  let index = '';
  if (doc.layout.index && mode !== 'md') index = buildIndex(tmp, mode); else $$('.ixm', tmp).forEach(m => m.remove());
  const markers = $$('.cite,.fn', tmp);
  const out = computeRefs(doc, markers); applyMarkers(out);
  const noteOf = n => (out.notes.find(x => x.n === n) || {}).html || '';
  markers.forEach(m => {
    let r;
    if (m.classList.contains('sup')) {
      const n = +m.textContent;
      if (mode === 'md') r = document.createTextNode(`@@FN${n}@@`);
      else if (mode === 'paged') { r = document.createElement('span'); r.className = 'fn-note'; r.innerHTML = noteOf(n); }
      else if (mode === 'epub') { r = document.createElement('sup'); r.innerHTML = `<a class="noteref" data-n="${n}" id="r${n}">${n}</a>`; }
      else { r = document.createElement('sup'); r.className = 'fnref'; r.textContent = n; }
    } else { r = document.createElement('span'); r.innerHTML = m.innerHTML; }
    m.replaceWith(r);
  });
  $$('p', tmp).forEach(p => { if (!p.textContent.trim() && !p.querySelector('img,a.ix-a')) p.remove(); });
  lastSig = ''; renderRefs(true); // restore the open document's citation state
  return { body: tmp.innerHTML, out, title: titleBlockHTML(doc), index, figs, mg, marginalia: marginaliaHTML(mg, mode) };
}
function exportStandaloneHTML(doc) {
  const x = buildExport(doc, 'html'), cs = docClassAndStyle(doc);
  const css = $('#docCss').textContent + `\nbody{margin:0;background:#fff;color:#111}.docbody{max-width:6.5in;margin:1in auto;padding:0 .3in}@page{size:${doc.layout.paper === 'A4' ? 'A4' : 'letter'};margin:1in}`;
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(doc.title)}</title><style>${css}</style></head><body><article class="${cs.cls}" style="${cs.style}">${x.title ? `<header class="title-block">${x.title}</header>` : ''}${x.body}${refsHTML(x.out, true)}${x.index || ''}${x.marginalia || ''}</article></body></html>`;
}
function exportPDF(doc = curDoc()) {
  if (!doc) return;
  if (doc.layout.pdfNotes !== 'end') { exportPagedPDF(doc); return; }
  const x = buildExport(doc, 'html'), cs = docClassAndStyle(doc);
  $('#printRoot').innerHTML = `<article class="${cs.cls}" style="${cs.style}">${x.title ? `<header class="title-block">${x.title}</header>` : ''}${x.body}${refsHTML(x.out, true)}${(x.index || '').replace(/<span class="ix-refs">[\s\S]*?<\/span>/g, '')}${x.marginalia || ''}</article>`;
  $('#pageRule').textContent = `@page{size:${doc.layout.paper === 'A4' ? 'A4' : 'letter'};margin:1in;${doc.layout.pageNums ? '@bottom-center{content:counter(page);font:10pt Georgia,serif}' : ''}}`;
  const prevTitle = document.title; document.title = fileSafe(doc.title);
  const done = () => { document.title = prevTitle; $('#printRoot').innerHTML = ''; window.removeEventListener('afterprint', done); };
  window.addEventListener('afterprint', done);
  try { window.print(); } catch (e) { toast('Printing isn’t available here. Open the file directly in your browser.'); done(); }
}
function exportMarkdown(doc) {
  const x = buildExport(doc, 'md');
  const td = addTableRules(new TurndownService({ headingStyle: 'atx', emDelimiter: '*', bulletListMarker: '-' }));
  let md = `# ${doc.title}\n\n` + [doc.meta.subtitle, doc.meta.author, doc.meta.date].filter(Boolean).map(s => `*${s}*`).join('  \n') + '\n\n';
  md += td.turndown(x.body).replace(/@@FN(\d+)@@/g, '[^$1]');
  if (x.out.notes.length) md += '\n\n' + x.out.notes.map(n => `[^${n.n}]: ${td.turndown(n.html).replace(/\n+/g, ' ')}`).join('\n');
  if (x.out.bib) md += `\n\n## ${x.out.heading}\n\n` + x.out.bib.entries.map(e => td.turndown(e).trim()).join('\n\n');
  if (x.mg && x.mg.length) md += '\n\n## Marginalia\n\n' + x.mg.map(m => `${m.n}. **${m.sec || 'Opening'}** — “${m.passage}”  \n   ${m.text.replace(/\n/g, '  \n   ')}`).join('\n\n');
  return md.replace(/\n{3,}/g, '\n\n') + '\n';
}
async function copyFormatted(doc) {
  const x = buildExport(doc, 'html');
  const html = `${x.title}${x.body}${refsHTML(x.out, true)}`;
  const text = htmlToText(html);
  try {
    if (window.ClipboardItem) await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([text], { type: 'text/plain' }) })]);
    else await navigator.clipboard.writeText(text);
    toast('Copied. Paste into Substack, Google Docs or Word.');
  } catch (e) { toast('The browser blocked clipboard access.'); }
}
function notesMarkdown() {
  return `# ${P.title}: notes\n\n` + [...P.notes].sort((a, b) => a.created.localeCompare(b.created)).map(n => {
    const s = n.sourceId && P.sources.find(x => x.id === n.sourceId);
    const cite = s ? htmlToText(previewCluster(curDoc()?.style || DEFAULT_STYLE, [Object.assign({ id: s.id }, n.locator ? { locator: n.locator, label: n.label } : {})])) : '';
    return `## ${n.title || firstLine(n.body) || 'Untitled'}\n\n*${n.kind}*${n.tags.length ? ' · ' + n.tags.map(t => '#' + t.replace(/\s+/g, '-')).join(' ') : ''}\n\n${n.body.trim()}\n${cite ? `\n> Source: ${cite}\n` : ''}`;
  }).join('\n---\n\n');
}
$('#btnExport').addEventListener('click', e => { e.stopPropagation(); $('#exportMenu').classList.toggle('open'); });
document.addEventListener('click', e => { if (!e.target.closest('.menu')) $('#exportMenu').classList.remove('open'); });
$('#exportMenu').addEventListener('click', e => {
  const x = e.target.closest('button')?.dataset.x; if (!x) return;
  $('#exportMenu').classList.remove('open');
  const doc = curDoc();
  if (x === 'pdf') exportPDF();
  if (x === 'docx') exportDocx(doc);
  if (x === 'ms') openManuscript();
  if (x === 'html') download(fileSafe(doc.title) + '.html', exportStandaloneHTML(doc), 'text/html');
  if (x === 'md') download(fileSafe(doc.title) + '.md', exportMarkdown(doc), 'text/markdown');
  if (x === 'copy') copyFormatted(doc);
  if (x === 'substack') openSubstack();
  if (x === 'promo') openPromo();
  if (x === 'checkpoints') openCheckpoints();
  if (x === 'html' || x === 'epub' || x === 'docx') a11yNudge();
  if (x === 'lock') openLockSettings();
  if (x === 'github') openGitHub();
  if (x === 'saveas') saveProject(true);
  if (x === 'notesmd') download(fileSafe(P.title) + ' - notes.md', notesMarkdown(), 'text/markdown');
  if (x === 'epub') exportEpub(doc);
  if (x === 'annot') annotatedBibliography();
  if (x === 'osintlist') download(fileSafe(P.title) + ' - OSINT sources.json', exportOsintList(), 'application/json');
  if (x === 'csl') download(fileSafe(P.title) + ' - sources.json', JSON.stringify(P.sources.map(s => Object.assign({ id: s.id }, s.csl)), null, 2), 'application/json');
});

/* ---------------- dialogs, toast, misc ---------------- */
function ask(title, msg, okLabel = 'OK', inputValue = null) {
  return new Promise(res => {
    const d = $('#askDlg'), inp = $('#askInput');
    $('#askTitle').textContent = title; $('#askMsg').textContent = msg; $('#askOk').textContent = okLabel;
    $('#askOk').classList.toggle('danger', /delete|discard/i.test(okLabel));
    inp.classList.toggle('hidden', inputValue === null); if (inputValue !== null) inp.value = inputValue;
    const fin = v => { d.close(); $('#askOk').onclick = $('#askCancel').onclick = inp.onkeydown = d.oncancel = null; res(v); };
    $('#askOk').onclick = () => fin(inputValue !== null ? inp.value.trim() : true);
    $('#askCancel').onclick = () => fin(inputValue !== null ? null : false);
    d.oncancel = () => fin(inputValue !== null ? null : false);
    inp.onkeydown = e => { if (e.key === 'Enter') $('#askOk').click(); };
    d.showModal(); setTimeout(() => (inputValue !== null ? inp : $('#askOk')).focus(), 30);
  });
}
let toastT;
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2800); }
function switchTab(name) {
  $$('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  $$('.pane').forEach(p => p.classList.toggle('on', p.dataset.pane === name));
}
$$('.tabs button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
$('#btnSide').addEventListener('click', () => document.body.classList.toggle('side-open'));
$('#btnSave').addEventListener('click', () => saveProject(false));
$('#btnOpen').addEventListener('click', openProject);
$('#btnNewProj').addEventListener('click', () => openNewProject());
$('#fileOpen').addEventListener('change', async e => { const f = e.target.files[0]; e.target.value = ''; if (f) loadProjectText(await f.text(), null, f.name); });
$('#btnHelp').addEventListener('click', () => $('#helpDlg').showModal());
$('#helpClose').addEventListener('click', () => $('#helpDlg').close());
function setTheme(t) { document.documentElement.dataset.theme = t; lsSet(THEME_KEY, t); }
$('#btnTheme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
document.addEventListener('keydown', e => {
  const mod = e.metaKey || e.ctrlKey;
  if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(e.shiftKey); }
  if (mod && e.key.toLowerCase() === 'p') { e.preventDefault(); exportPDF(); }
  const k = e.key.toLowerCase(), dlgOpen = !!document.querySelector('dialog[open]');
  if (mod && !e.shiftKey && !e.altKey && k === 'k') { e.preventDefault(); if (!dlgOpen) openPalette(); }
  if (mod && !e.shiftKey && !e.altKey && k === 'f') { e.preventDefault(); if (!dlgOpen) openFind(); }
  if (mod && e.shiftKey && k === 'f') { e.preventDefault(); if (!dlgOpen) toggleFocus(); }
  if (mod && e.shiftKey && k === 'e') { e.preventDefault(); if (!dlgOpen) captureNote(); }
  if (mod && e.shiftKey && k === 'k') { e.preventDefault(); if (!dlgOpen) openFlag(); }
  if (mod && e.altKey && e.code === 'KeyC') { e.preventDefault(); if (!dlgOpen) openCite(); } // e.code: Option changes e.key on a Mac
  if (mod && e.altKey && e.code === 'KeyA') { e.preventDefault(); if (!dlgOpen) addComment(); }
  if (mod && e.altKey && e.code === 'KeyX') { e.preventDefault(); if (!dlgOpen) openIndexMark(); }
  if (mod && e.altKey && e.code === 'KeyD') { e.preventDefault(); if (!dlgOpen) openSaveDraft(); }
  if (e.key === 'Escape') { closePop(); if (!dlgOpen && !$('#findBar').classList.contains('hidden')) closeFind(); else if (!dlgOpen && document.body.classList.contains('focus')) toggleFocus(false); }
});
window.addEventListener('beforeunload', e => { if (dirtyFile) { syncEditor(); lsSet(STORE_KEY, sessionRecord()); e.preventDefault(); e.returnValue = ''; } });

function renderAll() { $('#projTitle').value = P.title; renderDocList(); renderNoteList(); renderSourceList(); }

/* ================================================================
   Drafting & research tools
   ================================================================ */
const stripCp = h => h.replace(/\sdata-cp-[a-z-]+="[^"]*"/g, '').replace(/<img\b[^>]*>/g, t => /data-asset=/.test(t) ? t.replace(/\ssrc="[^"]*"/, '') : t);

/* ---------- flags: TK / citation needed / check ---------- */
const FLAG_KINDS = { tk: { label: 'TK', long: 'TK: missing fact or detail' }, cite: { label: 'cite?', long: 'Citation needed' }, check: { label: 'check', long: 'Check this' } };
function flagHTML(kind, note) {
  return `<span class="flag flag-${kind}" contenteditable="false" data-kind="${kind}" data-note="${esc(note || '')}">${FLAG_KINDS[kind].label}</span>`;
}
let flagTarget = null;
function openFlag(m = null, kind = 'tk') {
  flagTarget = m;
  const k = m ? m.dataset.kind : kind;
  $$('#flagDlg input[name=flagKind]').forEach(r => r.checked = r.value === k);
  $('#flagNote').value = m ? m.dataset.note : '';
  $('#flagRemove').classList.toggle('hidden', !m);
  $('#flagCiteNow').classList.toggle('hidden', !(m && k === 'cite'));
  $('#flagDlgTitle').textContent = m ? 'Flag' : 'Leave a flag';
  $('#flagDlg').showModal(); setTimeout(() => $('#flagNote').focus(), 30);
}
$('#flagCancel').addEventListener('click', () => $('#flagDlg').close());
$('#flagNote').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#flagOk').click(); } });
$('#flagOk').addEventListener('click', () => {
  const kind = $('#flagDlg input[name=flagKind]:checked').value, note = $('#flagNote').value.trim();
  $('#flagDlg').close();
  if (flagTarget) { flagTarget.dataset.kind = kind; flagTarget.dataset.note = note; flagTarget.className = 'flag flag-' + kind; flagTarget.textContent = FLAG_KINDS[kind].label; onEdit(); }
  else insertHTMLAtCursor(flagHTML(kind, note) + '&nbsp;');
  renderOutlineSoon();
});
$('#flagRemove').addEventListener('click', () => { if (flagTarget) { flagTarget.remove(); onEdit(); renderOutlineSoon(); } $('#flagDlg').close(); });
$('#flagCiteNow').addEventListener('click', () => {
  const m = flagTarget; $('#flagDlg').close(); if (!m) return;
  const r = document.createRange(); r.setStartBefore(m); r.collapse(true); savedRange = r;
  m.remove(); onEdit(); openCite();
});
$('#btnFlag').addEventListener('click', () => openFlag());
editor.addEventListener('click', e => { const f = e.target.closest('.flag'); if (f) { e.preventDefault(); openFlag(f); } });

/* ---------- outline & drafting checklist ---------- */
function blockSnippet(el, n = 70) { const t = (el.textContent || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n) + '…' : t; }
function wordsIn(el) { const c = el.cloneNode(true); $$('.cite,.fn,.flag', c).forEach(m => m.remove()); return (c.textContent || '').trim().split(/\s+/).filter(Boolean).length; }
function uncitedBlocks() {
  return $$(':scope > p, :scope > blockquote, :scope > ul > li, :scope > ol > li', editor)
    .filter(el => !el.querySelector('.cite') && wordsIn(el) >= (PREFS.uncitedMin || 40));
}
function literalTKs() {
  const out = [], w = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const n = w.currentNode; if (n.parentElement.closest('.cite,.fn,.flag')) continue; if (/\bTK\b/.test(n.data)) out.push(n.parentElement.closest('#editor > *') || n.parentElement); }
  return out;
}
let outlineEls = [];
function renderOutline() {
  if (!P) return;
  outlineEls = [];
  const kids = [...editor.children], heads = [];
  let cur = { el: null, words: 0 };
  const pre = { el: null, words: 0 };
  kids.forEach(k => {
    if (/^H[123]$/.test(k.nodeName)) { cur = { el: k, level: +k.nodeName[1], words: 0 }; heads.push(cur); }
    else (cur.el ? cur : pre).words += wordsIn(k);
  });
  renderStructure();
  const flags = $$('.flag', editor), tks = literalTKs();
  const fl = flags.map(f => { outlineEls.push(f); return `<li data-i="${outlineEls.length - 1}"><b class="fk fk-${f.dataset.kind}">${FLAG_KINDS[f.dataset.kind]?.label || 'TK'}</b><span>${esc(f.dataset.note || blockSnippet(f.closest('#editor > *') || f, 50))}</span></li>`; })
    .concat(tks.map(el => { outlineEls.push(el); return `<li data-i="${outlineEls.length - 1}"><b class="fk fk-tk">TK</b><span>${esc(blockSnippet(el, 50))}</span></li>`; })).join('');
  $('#flagList').innerHTML = fl || '<li class="muted small none">Nothing to resolve. Use the flag button or type TK to leave yourself a marker.</li>';
  $('#flagCount').textContent = (flags.length + tks.length) || '';
  const unc = uncitedBlocks();
  $$('[data-cp-uncited]', editor).forEach(x => x.removeAttribute('data-cp-uncited'));
  if ($('#showUncited').checked) unc.forEach(x => x.setAttribute('data-cp-uncited', ''));
  $('#uncitedList').innerHTML = unc.length ? unc.map(el => { outlineEls.push(el); return `<li data-i="${outlineEls.length - 1}"><span>${esc(blockSnippet(el, 60))}</span><em>${wordsIn(el)}</em></li>`; }).join('')
    : `<li class="muted small none">Every paragraph of ${PREFS.uncitedMin || 40}+ words has a citation.</li>`;
  $('#uncitedCount').textContent = unc.length || '';
  const issues = renderIntegrity();
  const n = flags.length + tks.length + issues; $('#tabOutlineBadge').textContent = n ? n : '';
}
const renderOutlineSoon = debounce(renderOutline, 500);
$$('#outlinePane ul').forEach(ul => ul.addEventListener('click', e => {
  const li = e.target.closest('li[data-i]'); if (!li) return;
  const el = outlineEls[+li.dataset.i]; if (!el || !editor.contains(el)) return;
  el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  el.setAttribute('data-cp-flash', ''); setTimeout(() => el.removeAttribute('data-cp-flash'), 1400);
  const r = document.createRange(); r.selectNodeContents(el.matches('.flag') ? el.parentNode : el); r.collapse(el.matches('.flag'));
  if (el.matches('.flag')) { r.setStartAfter(el); r.collapse(true); }
  const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); savedRange = r.cloneRange();
  document.body.classList.remove('side-open');
}));
$('#showUncited').addEventListener('change', renderOutline);
editor.addEventListener('input', renderOutlineSoon);

/* ---------- find & replace ---------- */
let findHits = [], findIdx = -1;
const hasHL = !!(window.CSS && CSS.highlights && window.Highlight);
function textNodesIn(root) {
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentElement.closest('.cite,.fn,.flag') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  const a = []; while (w.nextNode()) a.push(w.currentNode); return a;
}
function runFind(keep = false) {
  const q = $('#findQ').value, cs = $('#findCase').checked;
  findHits = [];
  if (q) {
    const needle = cs ? q : q.toLowerCase();
    textNodesIn(editor).forEach(tn => {
      const t = cs ? tn.data : tn.data.toLowerCase(); let i = 0;
      while ((i = t.indexOf(needle, i)) !== -1) { const r = document.createRange(); r.setStart(tn, i); r.setEnd(tn, i + q.length); findHits.push(r); i += q.length; }
    });
  }
  if (!keep) findIdx = findHits.length ? 0 : -1;
  if (findIdx >= findHits.length) findIdx = findHits.length - 1;
  paintFind();
}
function paintFind(scroll = true) {
  const q = $('#findQ').value;
  $('#findCount').textContent = q ? (findHits.length ? `${findIdx + 1} of ${findHits.length}` : 'No matches') : '';
  if (hasHL) {
    CSS.highlights.set('cp-find', new Highlight(...findHits));
    if (findIdx >= 0) CSS.highlights.set('cp-cur', new Highlight(findHits[findIdx])); else CSS.highlights.delete('cp-cur');
  }
  if (findIdx >= 0 && scroll) {
    const r = findHits[findIdx], rect = r.getBoundingClientRect(), sc = $('#scroller'), sr = sc.getBoundingClientRect();
    if (rect.top < sr.top + 40 || rect.bottom > sr.bottom - 40) sc.scrollTop += rect.top - sr.top - sr.height / 2;
    if (!hasHL) { const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r.cloneRange()); }
  }
}
function openFind(prefill) {
  $('#findBar').classList.remove('hidden');
  const sel = getSelection();
  const s = prefill ?? (sel.rangeCount && editor.contains(sel.anchorNode) && !sel.isCollapsed ? sel.toString() : '');
  if (s && s.length < 120) $('#findQ').value = s;
  $('#findQ').focus(); $('#findQ').select(); runFind();
}
function closeFind() { $('#findBar').classList.add('hidden'); if (hasHL) { CSS.highlights.delete('cp-find'); CSS.highlights.delete('cp-cur'); } findHits = []; }
function stepFind(d) { if (!findHits.length) return; findIdx = (findIdx + d + findHits.length) % findHits.length; paintFind(); }
function replaceRange(r, text) {
  const sel = getSelection(); editor.focus(); sel.removeAllRanges(); sel.addRange(r);
  document.execCommand('insertText', false, text); // keeps undo working
}
$('#findQ').addEventListener('input', () => runFind());
$('#findCase').addEventListener('change', () => runFind());
$('#findQ').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); stepFind(e.shiftKey ? -1 : 1); } if (e.key === 'Escape') closeFind(); });
$('#replQ').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#replOne').click(); } if (e.key === 'Escape') closeFind(); });
$('#findNext').addEventListener('click', () => stepFind(1));
$('#findPrev').addEventListener('click', () => stepFind(-1));
$('#findClose').addEventListener('click', closeFind);
$('#replOne').addEventListener('click', () => {
  if (findIdx < 0 || !findHits[findIdx]) return;
  replaceRange(findHits[findIdx], $('#replQ').value);
  runFind(true); $('#replQ').focus(); onEdit();
});
$('#replAll').addEventListener('click', () => {
  const n = findHits.length; if (!n) return;
  for (let i = n - 1; i >= 0; i--) replaceRange(findHits[i], $('#replQ').value);
  runFind(); onEdit(); toast(`Replaced ${n} match${n === 1 ? '' : 'es'}. Undo (Ctrl/Cmd+Z) reverses them.`);
});
$('#btnFind').addEventListener('click', () => openFind());

/* ---------- search everything (Ctrl/Cmd+K) ---------- */
const COMMANDS = [
  ['New document', () => $('#btnNewDoc').click()], ['New part', () => $('#btnNewPart').click()],
  ['Capture note (from selection, or a blank note)', () => captureNote()], ['New source', () => { switchTab('sources'); $('#btnNewSource').click(); }],
  ['Insert citation', () => openCite()], ['Leave a flag (TK / citation needed / check)', () => openFlag()], ['Insert footnote', () => openFootnote()],
  ['Find & replace', () => openFind()], ['Focus mode', () => toggleFocus()], ['Compile manuscript…', () => openManuscript()],
  ['Compile notes into a draft…', () => $('#btnCompile').click()], ['Export Word (.docx)', () => exportDocx(curDoc())], ['Export PDF', () => exportPDF()],
  ['Save project', () => saveProject(false)], ['Page setup', () => $('#btnPageSetup').click()], ['Settings', () => openSettings()],
  ['Notes board (cards, piles, canvas)', () => openBoard()], ['Web clipper (bookmarklet)', () => openClipper()], ['Add source from a URL, DOI or ISBN', () => { switchTab('sources'); document.body.classList.add('side-open'); $('#quickId').focus(); }],
  ['Import a Word document (.docx)', () => $('#fileDocx').click()], ['Versions: save or compare', () => openVersions()], ['Export ePub (e-book)', () => exportEpub(curDoc())],
  ['Names & spellings', () => openNames()], ['Source audit', () => openAudit('all')], ['Writing record & chapter status', () => openRecord()], ['Revision lens', () => toggleLens()],
  ['Add a comment on the selection', () => addComment()], ['Templates: front & back matter', () => openTemplates()], ['Chronology from dated notes', () => chronologyDoc()],
  ['Annotated bibliography', () => annotatedBibliography()], ['Interview transcript → quote notes', () => openTranscript()], ['Timeline of dated notes', () => { PREFS.boardGroup = 'timeline'; savePrefs(); openBoard(); }],
  ['Read a PDF beside the draft', () => $('#btnReader').click()], ['Mark an index entry', () => openIndexMark()], ['Index terms & preview', () => openIndexManager()], ['Start fresh (blank project or erase everything)', () => openFresh()],
  ['Project home: progress, pace, loose ends', () => openHome()], ['Chart from data (insert a figure)', () => { saveSelectionNow(); specTarget = null; openChart(); }], ['Map (insert a figure)', () => { saveSelectionNow(); specTarget = null; openMap(); }], ['Timeline figure from dated notes', () => { saveSelectionNow(); specTarget = null; openTimelineFig(); }], ['Relationship map: who’s connected to whom', () => { saveSelectionNow(); openRel(); }], ['Acronyms & abbreviations…', () => openAcronyms()], ['Insert list of abbreviations here', () => insertBlocksAtCursor(abbrPlaceholder())], ['Estimative language check on / off', () => { estOn = !(estOn ?? estDefaultOn()); runEstimative(); switchTab('outline'); }], ['Teleprompter (script mode)', () => openPrompter()], ['Back up to GitHub…', () => openGitHub()], ['Save a draft of this document', () => openSaveDraft()], ['Drafts: compare versions side by side', () => openDrafts()], ['Insert figure (image)', () => $('#btnFigure').click()], ['Insert table', () => $('#btnTable').click()], ['Insert list of figures & tables here', () => { insertBlocksAtCursor(lofPlaceholder()); }], ['Margin note at the cursor', () => addComment()], ['Show / hide margin notes', () => $('#btnMargin').click()], ['Substack: copy or download this document for a post', () => openSubstack()], ['Lock project with a password', () => openLockSettings()], ['Import Markdown notes (Notecards, Obsidian)', () => openMdImport()], ['New project… (book, article, series, white paper, brief, script)', () => openNewProject()],
  ['Find and replace in all documents', () => openFindAll()], ['House style rules', () => openHouse()], ['Project checkpoints: save, compare, restore', () => openCheckpoints()], ['Promo kit: social thread, subtitle, quote card', () => openPromo()], ['Quote card from the selection', () => openPromo('card')], ['Corroboration check', () => { PREFS.corrOn = true; savePrefs(); switchTab('outline'); renderCorroboration(); }], ['Accessibility check', () => { switchTab('outline'); renderA11y(); $('#a11yList').scrollIntoView({ block: 'center' }); }],
  ['Take the tour', () => startTour()], ['Plan: outline your piece before drafting', () => openPlan()], ['Freewrite sprint', () => openFreewrite()], ['Reverse outline (every paragraph)', () => { switchTab('outline'); document.body.classList.add('side-open'); $('#olParas').checked = true; renderOutline(); }],
  ['Show outline & checklist', () => { switchTab('outline'); document.body.classList.add('side-open'); }], ['Help', () => $('#helpDlg').showModal()], ['Switch light / dark theme', () => $('#btnTheme').click()],
];
let palItems = [], palIdx = 0;
function snippetAround(text, q, n = 60) {
  const i = text.toLowerCase().indexOf(q.toLowerCase()); if (i < 0) return esc(text.slice(0, n * 2));
  const a = Math.max(0, i - n), b = Math.min(text.length, i + q.length + n);
  return (a ? '…' : '') + esc(text.slice(a, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length, b)) + (b < text.length ? '…' : '');
}
function renderPalette() {
  const q = $('#palQ').value.trim(), ql = q.toLowerCase();
  palItems = [];
  const cmd = COMMANDS.filter(([l]) => !ql || l.toLowerCase().includes(ql)).slice(0, ql ? 6 : 8);
  cmd.forEach(([l, fn]) => palItems.push({ kind: 'Command', html: esc(l), run: fn }));
  if (ql) {
    syncEditor();
    binderOrder().forEach(d => {
      const t = htmlToText(d.html).replace(/\s+/g, ' ');
      const inTitle = d.title.toLowerCase().includes(ql), inText = t.toLowerCase().includes(ql);
      if (inTitle || inText) palItems.push({ kind: 'Document', html: `<b>${esc(d.title || 'Untitled')}</b>${inText ? `<div class="sn">${snippetAround(t, q)}</div>` : ''}`, run: () => { openDoc(d.id); if (inText) setTimeout(() => openFind(q), 60); } });
    });
    P.notes.forEach(n => {
      const t = (n.title + ' ' + n.body + ' ' + n.tags.join(' ')).replace(/\s+/g, ' ');
      if (t.toLowerCase().includes(ql)) palItems.push({ kind: 'Note', html: `<b>${esc(n.title || firstLine(n.body) || 'Untitled note')}</b><div class="sn">${snippetAround(n.body.replace(/\s+/g, ' ') || t, q)}</div>`, run: () => { switchTab('notes'); openNote(n.id); } });
    });
    P.sources.forEach(s => {
      const t = JSON.stringify(s.csl) + ' ' + JSON.stringify(s.osint || {});
      if (t.toLowerCase().includes(ql)) { const l = sourceLabel(s); palItems.push({ kind: 'Source', html: `<b>${esc(l.who || '—')}${l.yr ? ' (' + esc(l.yr) + ')' : ''}</b>: ${esc(l.title)}`, run: () => { switchTab('sources'); openSource(s.id); } }); }
    });
  }
  palItems = palItems.slice(0, 60); palIdx = 0;
  $('#palList').innerHTML = palItems.length ? palItems.map((it, i) => `<li data-i="${i}" class="${i === 0 ? 'on' : ''}"><span class="pk">${it.kind}</span><div>${it.html}</div></li>`).join('') : '<li class="muted">Nothing found.</li>';
}
function openPalette() { $('#palQ').value = ''; renderPalette(); $('#palDlg').showModal(); setTimeout(() => $('#palQ').focus(), 20); }
function runPal(i) { const it = palItems[i]; if (!it) return; $('#palDlg').close(); setTimeout(() => it.run(), 10); }
$('#palQ').addEventListener('input', renderPalette);
$('#palQ').addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault(); palIdx = Math.max(0, Math.min(palItems.length - 1, palIdx + (e.key === 'ArrowDown' ? 1 : -1)));
    $$('#palList li').forEach((li, i) => li.classList.toggle('on', i === palIdx)); $$('#palList li')[palIdx]?.scrollIntoView({ block: 'nearest' });
  }
  if (e.key === 'Enter') { e.preventDefault(); runPal(palIdx); }
});
$('#palList').addEventListener('click', e => { const li = e.target.closest('li[data-i]'); if (li) runPal(+li.dataset.i); });
$('#btnSearch').addEventListener('click', openPalette);

/* ---------- capture: selection → note ---------- */
function captureNote() {
  const sel = getSelection(), doc = curDoc();
  const inEditor = sel.rangeCount && editor.contains(sel.anchorNode) && !sel.isCollapsed;
  const n = newNote();
  if (inEditor) {
    const frag = sel.getRangeAt(0).cloneContents(), box = document.createElement('div'); box.appendChild(frag);
    const cite = box.querySelector('.cite') || sel.getRangeAt(0).startContainer.parentElement?.closest('#editor > *')?.querySelector('.cite');
    $$('.cite,.fn,.flag', box).forEach(m => m.remove());
    const td = new TurndownService({ headingStyle: 'atx', emDelimiter: '*', bulletListMarker: '-' });
    n.body = td.turndown(box.innerHTML).trim();
    n.title = n.body.replace(/[#*_>`\[\]]/g, '').split(/\s+/).slice(0, 7).join(' ') + (n.body.split(/\s+/).length > 7 ? '…' : '');
    if (cite) { const it = markerItems(cite)[0]; if (it && P.sources.some(s => s.id === it.id)) { n.sourceId = it.id; n.locator = it.locator || ''; n.label = it.label || 'page'; } }
    n.kind = n.sourceId ? 'quote' : 'idea';
    toast('Captured to a new note. Edit it in the panel.');
  } else if (panelState?.kind === 'source') { n.sourceId = panelState.id; n.kind = 'quote'; }
  P.notes.unshift(n); renderNoteList(); openNote(n.id, !inEditor); markDirty();
}
$('#btnCapture').addEventListener('click', captureNote);
$('#toolbar').addEventListener('mousedown', e => { if (e.target.closest('#btnCapture')) e.preventDefault(); });

/* ---------- focus mode, word targets, session count ---------- */
const sessionBase = {};
function docWordsLive() { return wordsIn(editor); }
function sessionWords() {
  let n = 0;
  for (const id in sessionBase) { const d = P.docs.find(x => x.id === id); if (d) n += Math.max(0, docWords(d) - sessionBase[id]); }
  return n;
}
function updateTargets() {
  const d = curDoc(); if (!d) return;
  if (!(d.id in sessionBase)) sessionBase[d.id] = docWords(d);
  const w = docWordsLive(), sw = sessionWords();
  const bar = $('#tgtBar');
  if (d.target) { bar.classList.remove('hidden'); $('#tgtFill').style.width = Math.min(100, w / d.target * 100) + '%'; bar.title = `${w.toLocaleString()} of ${d.target.toLocaleString()} words`; }
  else bar.classList.add('hidden');
  $('#focusStat').textContent = `${w.toLocaleString()}${d.target ? ' / ' + d.target.toLocaleString() : ''} words · ${sw.toLocaleString()} this session${PREFS.sessionGoal ? ' / ' + PREFS.sessionGoal.toLocaleString() : ''}`;
  $('#focusStat').classList.toggle('done', !!PREFS.sessionGoal && sw >= PREFS.sessionGoal);
}
editor.addEventListener('input', debounce(updateTargets, 400));
function toggleFocus(on) {
  const b = document.body, want = on ?? !b.classList.contains('focus');
  b.classList.toggle('focus', want);
  b.classList.toggle('dim', want && PREFS.dimOthers);
  if (want) { try { document.documentElement.requestFullscreen?.().catch(() => {}); } catch (e) {} updateTargets(); setTimeout(() => restoreSelection(), 50); }
  else { try { if (document.fullscreenElement) document.exitFullscreen(); } catch (e) {} $$('[data-cp-current]', editor).forEach(x => x.removeAttribute('data-cp-current')); }
}
$('#btnFocus').addEventListener('click', () => toggleFocus(true));
$('#focusExit').addEventListener('click', () => toggleFocus(false));
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && document.body.classList.contains('focus')) { /* stay in focus mode; Esc on our side exits */ } });
function focusTrack() {
  if (!document.body.classList.contains('focus')) return;
  const sel = getSelection(); if (!sel.rangeCount || !editor.contains(sel.anchorNode)) return;
  let blk = sel.anchorNode; while (blk && blk.parentNode !== editor) blk = blk.parentNode;
  $$('[data-cp-current]', editor).forEach(x => { if (x !== blk) x.removeAttribute('data-cp-current'); });
  if (blk && blk.nodeType === 1) blk.setAttribute('data-cp-current', '');
  if (PREFS.typewriter) {
    const r = sel.getRangeAt(0).cloneRange(); let rect = r.getBoundingClientRect();
    if (!rect.height && blk && blk.nodeType === 1) rect = blk.getBoundingClientRect();
    const sc = $('#scroller'), sr = sc.getBoundingClientRect();
    const target = sr.top + sr.height * 0.42;
    if (rect.height && Math.abs(rect.top - target) > 24) sc.scrollTop += rect.top - target;
  }
}
document.addEventListener('selectionchange', debounce(focusTrack, 30));

/* ---------- settings ---------- */
function openSettings() {
  $('#stRemind').value = String(PREFS.remindMins); $('#stGoal').value = PREFS.sessionGoal || '';
  $('#stDaily').value = PREFS.dailyGoal || ''; $('#stType').checked = !!PREFS.typewriter; $('#stDim').checked = !!PREFS.dimOthers; $('#stUncited').value = PREFS.uncitedMin; $('#stHome').checked = PREFS.startHome !== false; $('#stAuto').checked = !!PREFS.fileAutosave; $('#stAuto').disabled = !canFileAutosave(); $('#stAutoNote').textContent = canFileAutosave() ? 'Writes to the .json file a few seconds after you stop typing, once you’ve saved it there.' : 'This browser can’t write to files directly (Chrome and Edge can). You’ll get save reminders instead.'; $('#stSpell').checked = !!PREFS.spellcheck;
  $('#settingsDlg').showModal(); renderStorageStatus();
}
$('#btnSettings').addEventListener('click', openSettings);
$('#stCancel').addEventListener('click', () => $('#settingsDlg').close());
$('#stOk').addEventListener('click', () => {
  PREFS.remindMins = +$('#stRemind').value; PREFS.sessionGoal = Math.max(0, parseInt($('#stGoal').value, 10) || 0);
  PREFS.dailyGoal = Math.max(0, parseInt($('#stDaily').value, 10) || 0); PREFS.startHome = $('#stHome').checked; const wasAuto = !!PREFS.fileAutosave; PREFS.fileAutosave = $('#stAuto').checked && canFileAutosave(); if (PREFS.fileAutosave && !wasAuto) { if (fileHandle) fileAutosave(); else restoreAutosaveHandle(); } PREFS.typewriter = $('#stType').checked; PREFS.dimOthers = $('#stDim').checked; PREFS.uncitedMin = Math.max(5, parseInt($('#stUncited').value, 10) || 40); PREFS.spellcheck = $('#stSpell').checked;
  savePrefs(); $('#settingsDlg').close();
  editor.spellcheck = PREFS.spellcheck; snoozeUntil = 0; checkReminder(); renderOutline(); updateTargets();
});
$('#remindSave').addEventListener('click', () => saveProject(false));
$('#remindLater').addEventListener('click', () => { snoozeUntil = Date.now() + Math.max(5, PREFS.remindMins) * 60000; checkReminder(); });

/* ---------- manuscript compile ---------- */
function openManuscript(partId = '__all') {
  syncEditor();
  $('#msScope').innerHTML = '<option value="__all">Whole project, in binder order</option>' + P.parts.map(p => `<option value="${p.id}">Part: ${esc(p.name)}</option>`).join('');
  $('#msScope').value = P.parts.some(p => p.id === partId) ? partId : '__all';
  $('#msStyle').innerHTML = Object.keys(STYLES).map(k => `<option value="${k}">${esc(STYLES[k].label)}</option>`).join('');
  $('#msStyle').value = curDoc()?.style || DEFAULT_STYLE;
  if (!$('#msTitle').value) $('#msTitle').value = P.title;
  renderMsList(); $('#msDlg').showModal();
}
let msOff = new Set();
function msDocs() { const sc = $('#msScope').value; return sc === '__all' ? binderOrder() : docsInPart(sc); }
function renderMsList() {
  const docs = msDocs();
  $('#msList').innerHTML = docs.map(d => { const pt = P.parts.find(x => x.id === d.partId); return `<li data-id="${d.id}"><input type="checkbox" ${msOff.has(d.id) ? '' : 'checked'}><span>${pt ? `<span class="muted small">${esc(pt.name)} › </span>` : ''}${esc(d.title || 'Untitled')}</span><span class="muted small">${docWords(d).toLocaleString()}</span></li>`; }).join('') || '<li class="muted">No documents.</li>';
  const on = docs.filter(d => !msOff.has(d.id));
  $('#msCount').textContent = `${on.length} document${on.length === 1 ? '' : 's'} · ${on.reduce((n, d) => n + docWords(d), 0).toLocaleString()} words`;
}
$('#msScope').addEventListener('change', renderMsList);
$('#msList').addEventListener('change', e => { const li = e.target.closest('li[data-id]'); if (!li) return; e.target.checked ? msOff.delete(li.dataset.id) : msOff.add(li.dataset.id); renderMsList(); });
$('#msCancel').addEventListener('click', () => $('#msDlg').close());
function buildManuscript() {
  syncEditor();
  const sel = msDocs().filter(d => !msOff.has(d.id)); if (!sel.length) return null;
  const rank = d => d.role === 'front' ? 0 : d.role === 'back' ? 2 : 1;
  const docs = sel.map((d, i) => [d, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(x => x[0]);
  const partTitles = $('#msPartTitles').checked, docTitles = $('#msDocTitles').checked, breaks = $('#msBreaks').checked;
  const numberCh = $('#msNumber').checked, wantToc = $('#msToc').checked;
  let html = '', lastPart = null, chNo = 0, tocDone = !wantToc, k = 0;
  const toc = [];
  const tocSlot = '<!--TOC-->';
  docs.forEach((d, i) => {
    if (!tocDone && !(d.role === 'front' && /dedication|epigraph/i.test(d.template || d.title))) { html += tocSlot; tocDone = true; }
    const pt = d.role === 'body' || !d.role ? P.parts.find(x => x.id === d.partId) : null;
    if (partTitles && pt && pt.id !== lastPart) { const id = 'h' + (++k); html += `<h1 id="${id}" class="part-title${html.replace(tocSlot, '') ? ' ch-break' : ''}">${esc(pt.name)}</h1>`; toc.push({ id, t: pt.name, part: true }); }
    lastPart = pt ? pt.id : lastPart;
    const label = (numberCh && (d.role || 'body') === 'body' ? `Chapter ${++chNo}: ` : '') + (d.title || 'Untitled');
    if (docTitles) { const id = 'h' + (++k); html += `<h1 id="${id}" class="chapter-title${breaks && html.replace(tocSlot, '') && !/part-title[^>]*>[^<]*<\/h1>$/.test(html) ? ' ch-break' : ''}">${esc(label)}</h1>`; toc.push({ id, t: label }); }
    else if (breaks && html.replace(tocSlot, '')) html += '<div class="ch-break"></div>';
    html += stripCp(d.html);
  });
  if (!tocDone) html += tocSlot;
  if ($('#msLof').checked && !html.includes('class="lof"')) html = html.replace(tocSlot, tocSlot + '<nav class="lof"></nav>');
  if ($('#msAbbr').checked && !html.includes('class="abbr"')) html = html.replace(tocSlot, tocSlot + '<nav class="abbr"></nav>');
  html = html.replace(tocSlot, wantToc && toc.length ? `<nav class="toc${html.indexOf(tocSlot) > 0 ? ' ch-break' : ''}"><h1 class="toc-title">Contents</h1><ol>${toc.map(t => `<li class="${t.part ? 'toc-part' : ''}"><a href="#${t.id}">${esc(t.t)}</a></li>`).join('')}</ol></nav>` : '');
  const first = docs[0];
  return {
    id: '__ms', title: $('#msTitle').value.trim() || P.title, html, style: $('#msStyle').value,
    meta: Object.assign({}, first.meta, { showTitleBlock: true }), layout: Object.assign({}, first.layout, { index: $('#msIndex').checked }), target: 0,
  };
}
$('#msOk').addEventListener('click', async () => {
  const ms = buildManuscript(); if (!ms) { toast('Select at least one document.'); return; }
  const fmt = $('#msFormat').value; $('#msDlg').close();
  if (fmt === 'docx') await exportDocx(ms);
  if (fmt === 'pdf') exportPDF(ms);
  if (fmt === 'md') download(fileSafe(ms.title) + '.md', exportMarkdown(ms), 'text/markdown');
  if (fmt === 'html') download(fileSafe(ms.title) + '.html', exportStandaloneHTML(ms), 'text/html');
  if (fmt === 'epub') await exportEpub(ms);
  if (fmt === 'doc') { const d = newDoc(ms.title, ms.html); d.style = ms.style; addDoc(d); toast('Manuscript compiled into a new document.'); }
});
$('#btnManuscript').addEventListener('click', () => openManuscript());

/* ---------- Word (.docx) export with real footnotes ---------- */
async function exportDocx(doc) {
  if (!doc) return;
  const D = docx, x = buildExport(doc, 'docx'), L = doc.layout;
  const font = { book: 'Palatino Linotype', times: 'Times New Roman', sans: 'Arial' }[L.font] || 'Times New Roman';
  const size = Math.round(parseFloat(L.size) * 2), line = Math.round(parseFloat(L.spacing) * 240);
  const isNote = x.out.isNote;
  const cmtIds = {}, cmtList = [];
  ((L.marginalia || 'word') === 'word' ? (x.body.match(/data-cmt="([^"]+)"/g) || []) : []).forEach(m => { const id = m.slice(10, -1); if (id in cmtIds) return; const c = findComment(id); if (!c) return; cmtIds[id] = cmtList.length; cmtList.push({ id: cmtList.length, author: c.author || doc.meta.author || 'Author', initials: (c.author || doc.meta.author || 'A').split(/\s+/).map(w => w[0]).join('').slice(0, 3), date: new Date(c.date || Date.now()), children: [new D.Paragraph({ children: [new D.TextRun(c.text)] })] }); });
  const ctxBody = { font, size, line, footnotes: {}, comments: cmtIds }, ctxNote = { font, size: Math.max(16, size - 4), line: 240, footnotes: {} };
  const notes = {};
  x.out.notes.forEach(n => { notes[n.n] = n.html; ctxBody.footnotes[n.n] = true; });
  const footnotes = {};
  for (const n in notes) footnotes[n] = { children: htmlToDocx(notes[n], ctxNote, { inlineOnly: true, spacingAfter: 120 }) };
  const children = [];
  if (x.title) {
    const tb = document.createElement('div'); tb.innerHTML = x.title;
    $$('p', tb).forEach((p, i) => children.push(new D.Paragraph({ alignment: D.AlignmentType.CENTER, spacing: { after: i ? 0 : 120, line: 276 }, children: [new D.TextRun({ text: p.textContent, bold: i === 0, size: i === 0 ? size + 8 : size, font })] })));
    children.push(new D.Paragraph({ spacing: { after: 240 }, children: [] }));
  }
  children.push(...htmlToDocx(x.body, ctxBody, { indent: !!L.indent }));
  if (x.out.bib) {
    children.push(new D.Paragraph({ heading: D.HeadingLevel.HEADING_2, alignment: D.AlignmentType.CENTER, pageBreakBefore: true, children: [new D.TextRun({ text: x.out.heading, font, bold: true, color: '000000', size })] }));
    const ds = !!STYLES[doc.style].ds && L.spacing === '2';
    x.out.bib.entries.forEach(h => {
      const p = htmlToDocx(h.replace(/<\/?div[^>]*>/g, ''), { font, size, line: ds ? 480 : 240, footnotes: {} }, { inlineOnly: true, spacingAfter: ds ? 0 : 240, hanging: x.out.bib.hanging });
      children.push(...p);
    });
  }
  if (x.mg && x.mg.length) {
    const mgEnd = [];
    mgEnd.push(new D.Paragraph({ heading: D.HeadingLevel.HEADING_2, alignment: D.AlignmentType.CENTER, pageBreakBefore: true, children: [new D.TextRun({ text: 'Marginalia', font, bold: true, color: '000000', size })] }));
    x.mg.forEach(m => {
      mgEnd.push(new D.Paragraph({ keepNext: true, spacing: { before: 200, after: 40, line: 260 }, children: [new D.TextRun({ text: m.n + '.  ', bold: true, font, size: size - 2 }), new D.TextRun({ text: 'p. ', font, size: size - 2, color: '555555' }), new D.PageReference(m.id.replace(/-/g, '_')), new D.TextRun({ text: ' · ' + (m.sec || 'Opening'), font, size: size - 2, color: '555555' })] }));
      if (m.passage) mgEnd.push(new D.Paragraph({ keepNext: true, spacing: { after: 40, line: 260 }, indent: { left: 360 }, children: [new D.TextRun({ text: '“' + m.passage + '”', italics: true, font, size: size - 2, color: '444444' })] }));
      mgEnd.push(new D.Paragraph({ spacing: { after: 120, line: 276 }, indent: { left: 360 }, children: m.text.split('\n').flatMap((t, i) => i ? [new D.TextRun({ break: 1 }), new D.TextRun({ text: t, font, size: size - 2 })] : [new D.TextRun({ text: t, font, size: size - 2 })]) }));
    });
    x.mgDocx = mgEnd;
  }
  if (x.index) {
    children.push(new D.Paragraph({ heading: D.HeadingLevel.HEADING_2, alignment: D.AlignmentType.CENTER, pageBreakBefore: true, children: [new D.TextRun({ text: 'Index', font, bold: true, color: '000000', size })] }));
    children.push(new D.Paragraph({ children: [new D.SimpleField('INDEX \\e "	" \\h "A" \\c "2"', 'Word will build the index here. If it doesn’t appear, right-click this line and choose Update Field.')] }));
  }
  if (x.mgDocx) children.push(...x.mgDocx);
  const page = L.paper === 'A4' ? { width: 11906, height: 16838 } : { width: 12240, height: 15840 };
  const footers = L.pageNums ? { default: new D.Footer({ children: [new D.Paragraph({ alignment: D.AlignmentType.CENTER, children: [new D.TextRun({ children: [D.PageNumber.CURRENT], font, size: 20 })] })] }) } : undefined;
  const hstyle = (sz, it) => ({ run: { font, size: sz, bold: true, italics: !!it, color: '000000' }, paragraph: { spacing: { before: 360, after: 160, line: 276 }, keepNext: true } });
  const bullets = ['•', '◦', '▪'];
  const wdoc = new D.Document({
    creator: doc.meta.author || 'Anabasis', title: doc.title, ...(x.index || (x.mg && x.mg.length) ? { features: { updateFields: true } } : {}),
    styles: {
      default: { document: { run: { font, size } }, heading1: hstyle(size + 8), heading2: hstyle(size + 4), heading3: hstyle(size + 2, true) },
    },
    numbering: { config: [
      { reference: 'ul', levels: [0, 1, 2].map(l => ({ level: l, format: D.LevelFormat.BULLET, text: bullets[l], alignment: D.AlignmentType.LEFT, style: { paragraph: { indent: { left: 720 * (l + 1), hanging: 360 } } } })) },
      { reference: 'ol', levels: [0, 1, 2].map(l => ({ level: l, format: [D.LevelFormat.DECIMAL, D.LevelFormat.LOWER_LETTER, D.LevelFormat.LOWER_ROMAN][l], text: `%${l + 1}.`, alignment: D.AlignmentType.LEFT, style: { paragraph: { indent: { left: 720 * (l + 1), hanging: 360 } } } })) },
    ] },
    footnotes,
    ...(cmtList.length ? { comments: { children: cmtList } } : {}),
    sections: [{ properties: { page: { size: page, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, footers, children }],
  });
  try {
    const blob = await D.Packer.toBlob(wdoc);
    download(fileSafe(doc.title) + '.docx', blob, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    const fl = (doc.html.match(/class="flag/g) || []).length;
    if (cmtList.length) toast(`Word file saved with ${cmtList.length} comment${cmtList.length > 1 ? 's' : ''} in the margin${fl ? ` and ${fl} unresolved flag${fl > 1 ? 's' : ''}` : ''}.`); else
    toast(fl ? `Word file saved. Note: ${fl} unresolved flag${fl > 1 ? 's' : ''} printed as [TK].` : (isNote ? 'Word file saved with real footnotes.' : 'Word file saved.'));
  } catch (e) { console.error(e); toast('Couldn’t build the Word file: ' + e.message); }
}
/* Convert sanitized document HTML into docx Paragraphs. */
function htmlToDocx(html, ctx, opt = {}) {
  const D = docx, root = document.createElement('div'); root.innerHTML = html;
  const out = []; let olInst = (htmlToDocx.ol = (htmlToDocx.ol || 0)); let prevHeading = true;
  const align = el => ({ center: D.AlignmentType.CENTER, right: D.AlignmentType.RIGHT, justify: D.AlignmentType.JUSTIFIED })[(el.style && el.style.textAlign) || el.getAttribute?.('align') || ''];
  const runs = (node, f = {}, sz = ctx.size) => {
    const r = [];
    node.childNodes.forEach(ch => {
      if (ch.nodeType === 3) {
        const t = ch.data.replace(/\s+/g, ' '); if (!t) return;
        r.push(new D.TextRun({ text: t, bold: f.b, italics: f.i, underline: f.u ? {} : undefined, strike: f.s, superScript: f.sup, subScript: f.sub, font: ctx.font, size: sz, color: f.link ? '1F4E9A' : undefined, highlight: f.mark ? 'yellow' : undefined }));
        return;
      }
      if (ch.nodeType === 1 && ch.nodeName === 'A' && ch.classList.contains('mg-a')) { r.push(new D.Bookmark({ id: ch.id.replace(/-/g, '_'), children: [new D.TextRun({ text: '' })] })); return; }
      if (ch.nodeType !== 1) return;
      const tag = ch.nodeName;
      if (tag === 'BR') { r.push(new D.TextRun({ break: 1 })); return; }
      if (tag === 'SPAN' && ch.classList.contains('cmt') && ctx.comments && ch.dataset.cmt in ctx.comments) { const id = ctx.comments[ch.dataset.cmt]; r.push(new D.CommentRangeStart(id), ...runs(ch, f, sz), new D.CommentRangeEnd(id), new D.TextRun({ children: [new D.CommentReference(id)] })); return; }
      if (tag === 'A' && ch.classList.contains('ix-a')) { r.push(new D.SimpleField('XE "' + (ch.dataset.ix || '').replace(/"/g, '') + '"', '')); return; }
      if (tag === 'SUP' && ch.classList.contains('fnref')) { const n = +ch.textContent; r.push(ctx.footnotes[n] ? new D.FootnoteReferenceRun(n) : new D.TextRun({ text: ch.textContent, superScript: true, font: ctx.font, size: sz })); return; }
      if (tag === 'A' && /^https?:|^mailto:/i.test(ch.getAttribute('href') || '')) { r.push(new D.ExternalHyperlink({ link: ch.getAttribute('href'), children: runs(ch, Object.assign({}, f, { u: true, link: true }), sz) })); return; }
      if (/^(UL|OL|P|DIV|BLOCKQUOTE|H[1-6])$/.test(tag) && opt.inlineOnly) { r.push(...runs(ch, f, sz)); return; }
      const g = Object.assign({}, f);
      if (tag === 'B' || tag === 'STRONG') g.b = true; if (tag === 'I' || tag === 'EM' || tag === 'CITE') g.i = true; if (tag === 'U') g.u = true;
      if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL') g.s = true; if (tag === 'SUP') g.sup = true; if (tag === 'SUB') g.sub = true; if (tag === 'MARK') g.mark = true;
      r.push(...runs(ch, g, sz));
    });
    return r;
  };
  const trimRuns = (el) => { // drop leading/trailing whitespace-only text
    const c = el.cloneNode(true);
    const first = c.firstChild, last = c.lastChild;
    if (first && first.nodeType === 3) first.data = first.data.replace(/^\s+/, '');
    if (last && last.nodeType === 3) last.data = last.data.replace(/\s+$/, '');
    return c;
  };
  if (opt.inlineOnly) {
    out.push(new D.Paragraph({ children: runs(trimRuns(root)), spacing: { line: ctx.line, after: opt.spacingAfter ?? 0 }, indent: opt.hanging ? { left: 720, hanging: 720 } : undefined }));
    return out;
  }
  const para = (el, extra = {}) => new D.Paragraph(Object.assign({ children: runs(trimRuns(el)), alignment: align(el), spacing: { line: ctx.line, after: ctx.line >= 480 ? 0 : 160 } }, extra));
  const list = (el, level) => {
    const ordered = el.nodeName === 'OL'; if (ordered) olInst = ++htmlToDocx.ol;
    [...el.children].filter(li => li.nodeName === 'LI').forEach(li => {
      const inline = li.cloneNode(true); $$(':scope > ul, :scope > ol', inline).forEach(x => x.remove());
      out.push(new D.Paragraph({ children: runs(trimRuns(inline)), numbering: ordered ? { reference: 'ol', level, instance: olInst } : { reference: 'ul', level }, spacing: { line: Math.min(ctx.line, 360), after: 80 } }));
      $$(':scope > ul, :scope > ol', li).forEach(sub => list(sub, Math.min(2, level + 1)));
    });
  };
  const block = el => {
    if (el.nodeType === 3) { if (el.data.trim()) { const p = document.createElement('p'); p.textContent = el.data; block(p); } return; }
    if (el.nodeType !== 1) return;
    const tag = el.nodeName;
    if (/^H[1-6]$/.test(tag)) {
      const lvl = Math.min(3, +tag[1]);
      const brk = el.classList.contains('ch-break');
      out.push(new D.Paragraph({ heading: [D.HeadingLevel.HEADING_1, D.HeadingLevel.HEADING_2, D.HeadingLevel.HEADING_3][lvl - 1], pageBreakBefore: brk, alignment: el.classList.contains('part-title') ? D.AlignmentType.CENTER : align(el), children: runs(trimRuns(el)) }));
      prevHeading = true; return;
    }
    if (tag === 'DIV' && el.classList.contains('ch-break') && !el.textContent.trim()) { out.push(new D.Paragraph({ pageBreakBefore: true, children: [] })); prevHeading = true; return; }
    if (tag === 'UL' || tag === 'OL') { list(el, 0); prevHeading = false; return; }
    if (tag === 'FIGURE') { out.push(...figureToDocx(el, ctx, runs, trimRuns)); prevHeading = true; return; }
    if (tag === 'TABLE') { out.push(tableToDocx(el, ctx, runs, trimRuns)); prevHeading = true; return; }
    if (tag === 'NAV') { if (el.classList.contains('lof') || el.classList.contains('toc')) out.push(new D.Paragraph({ pageBreakBefore: true, children: [] })); [...el.childNodes].forEach(block); return; }
    if (tag === 'BLOCKQUOTE') {
      const hasBlocks = [...el.children].some(c => /^(P|DIV|UL|OL)$/.test(c.nodeName));
      const items = hasBlocks ? [...el.childNodes].filter(c => c.nodeType === 1 || c.data.trim()) : [el];
      items.forEach(c => { const p = c.nodeType === 1 ? c : Object.assign(document.createElement('p'), { textContent: c.data }); out.push(para(p, { indent: { left: 720 }, spacing: { line: 240, after: 200 } })); });
      prevHeading = true; return;
    }
    if (/^(SECTION|ARTICLE|HEADER|DIV)$/.test(tag) && [...el.children].some(c => /^(P|H[1-6]|UL|OL|BLOCKQUOTE|DIV|SECTION)$/.test(c.nodeName))) { [...el.childNodes].forEach(block); return; }
    if (tag === 'HR') { out.push(new D.Paragraph({ alignment: D.AlignmentType.CENTER, children: [new D.TextRun({ text: '* * *', font: ctx.font, size: ctx.size })] })); prevHeading = true; return; }
    if (!el.textContent.trim() && !el.querySelector('sup')) return;
    out.push(para(el, opt.indent && !prevHeading && !(el.style && el.style.textAlign) ? { indent: { firstLine: 720 } } : {}));
    prevHeading = false;
  };
  [...root.childNodes].forEach(block);
  return out;
}

/* ================================================================
   Notecards: board, piles, canvas, bulk actions, links
   ================================================================ */
const CARD_COLORS = ['', 'yellow', 'green', 'blue', 'pink', 'purple', 'gray'];
const boardSort = (a, b) => (b.pinned - a.pinned) || ((a.order ?? 0) - (b.order ?? 0)) || (a.created || '').localeCompare(b.created || '');
const noteTitle = n => n.title || firstLine(n.body) || 'Untitled note';
const WIKI = /\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]/g;
const stripWikiLinks = t => String(t || '').replace(WIKI, (m, a, b) => b || a);
function mdNote(text) {
  const t = String(text || '').replace(WIKI, (m, a, b) => `[${(b || a).replace(/[\[\]]/g, '')}](#note:${encodeURIComponent(a.trim())})`);
  return sanitize(marked.parse(t));
}
function findNoteByTitle(t) { t = t.trim().toLowerCase(); return P.notes.find(n => noteTitle(n).toLowerCase() === t); }
async function followNoteLink(t) {
  const n = findNoteByTitle(t);
  if (n) { openNote(n.id); return; }
  if (await ask('Create linked note?', `No note is titled “${t}” yet. Create one?`, 'Create')) {
    const nn = newNote(); nn.title = t; P.notes.unshift(nn); renderNoteList(); renderBoard(); openNote(nn.id); markDirty();
  }
}
function noteLinksHTML(n) {
  const out = [...new Set([...String(n.body).matchAll(WIKI)].map(m => m[1].trim()))];
  const me = noteTitle(n).toLowerCase();
  const back = P.notes.filter(x => x.id !== n.id && [...String(x.body).matchAll(WIKI)].some(m => m[1].trim().toLowerCase() === me));
  if (!out.length && !back.length) return '';
  const chip = (t, ok) => `<a href="#note:${encodeURIComponent(t)}" class="nlink ${ok ? '' : 'missing'}">${esc(t)}</a>`;
  return (out.length ? `<div><span class="muted small">Links to</span> ${out.map(t => chip(t, !!findNoteByTitle(t))).join(' ')}</div>` : '') +
    (back.length ? `<div><span class="muted small">Linked from</span> ${back.map(x => chip(noteTitle(x), true)).join(' ')}</div>` : '');
}
function splitNote(n) {
  const ta = $('#panelBody [data-n=body]');
  if (!ta || ta.classList.contains('hidden')) { toast('Switch to Edit, put the cursor where the split should go, then click Split.'); return; }
  const at = ta.selectionStart, a = ta.value.slice(0, at).trim(), b = ta.value.slice(at).trim();
  if (!a || !b) { toast('Put the cursor inside the note text, where the second card should start.'); return; }
  n.body = a; n.modified = nowISO();
  const m = Object.assign(newNote(), { title: (n.title || firstLine(a)) + ' (2)', body: b, kind: n.kind, tags: [...n.tags], sourceId: n.sourceId, locator: n.locator, label: n.label, color: n.color, pile: n.pile, order: n.order + 0.5 });
  P.notes.unshift(m); renderNoteList(); renderBoard(); openNote(m.id); markDirty(); toast('Split into two cards.');
}

/* ---------- drag notes from the sidebar into the draft ---------- */
$('#noteList').addEventListener('dragstart', e => {
  const li = e.target.closest('li[data-id]'); if (!li) return;
  e.dataTransfer.setData('application/x-commonplace-note', li.dataset.id); e.dataTransfer.setData('text/plain', noteTitle(P.notes.find(n => n.id === li.dataset.id) || {}));
  e.dataTransfer.effectAllowed = 'copyLink';
});
editor.addEventListener('dragover', e => { if ([...e.dataTransfer.types].includes('application/x-commonplace-note')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } });
editor.addEventListener('drop', e => {
  const id = e.dataTransfer.getData('application/x-commonplace-note'); if (!id) return;
  e.preventDefault();
  let r = null;
  if (document.caretRangeFromPoint) r = document.caretRangeFromPoint(e.clientX, e.clientY);
  else if (document.caretPositionFromPoint) { const cp = document.caretPositionFromPoint(e.clientX, e.clientY); if (cp) { r = document.createRange(); r.setStart(cp.offsetNode, cp.offset); } }
  if (r && editor.contains(r.startContainer)) savedRange = r;
  insertNote(P.notes.find(n => n.id === id));
});

/* ---------- board ---------- */
let boardSel = new Set(), boardOn = false;
const BG = () => PREFS.boardGroup || 'pile';
function openBoard() {
  syncEditor(); if (planOn) closePlan(); if (homeOn) closeHome(); if (draftsOn) closeDrafts(); if (relOn) closeRel(); boardOn = true; document.body.classList.add('board-on'); $('#board').classList.remove('hidden');
  $('#bdGroup').value = BG(); renderBoard(); document.body.classList.remove('side-open');
}
function closeBoard() { boardOn = false; boardSel.clear(); document.body.classList.remove('board-on'); $('#board').classList.add('hidden'); }
function boardNotes() {
  const q = $('#bdQ').value.trim().toLowerCase();
  return P.notes.filter(n => !q || (n.title + ' ' + n.body + ' ' + n.tags.join(' ')).toLowerCase().includes(q));
}
function boardColumns() {
  const g = BG(), notes = boardNotes(), cols = [];
  const col = (key, name, list, extra = {}) => cols.push(Object.assign({ key, name, notes: list.sort(boardSort) }, extra));
  if (g === 'pile') {
    col('', 'Unsorted', notes.filter(n => !n.pile));
    P.piles.forEach(p => col(p.id, p.name, notes.filter(n => n.pile === p.id), { pile: p }));
  } else if (g === 'tag') {
    allTags().forEach(t => col(t, '#' + t, notes.filter(n => n.tags.includes(t))));
    col('', 'Untagged', notes.filter(n => !n.tags.length));
  } else if (g === 'source') {
    sortedSources().forEach(s => { const list = notes.filter(n => n.sourceId === s.id); if (list.length) { const l = sourceLabel(s); col(s.id, (l.who ? l.who + ', ' : '') + l.title, list); } });
    col('', 'No source', notes.filter(n => !n.sourceId || !P.sources.some(s => s.id === n.sourceId)));
  } else if (g === 'kind') KINDS.forEach(([k, l]) => col(k, l, notes.filter(n => n.kind === k)));
  return cols;
}
function cardHTML(n) {
  const s = n.sourceId && P.sources.find(x => x.id === n.sourceId), l = s ? sourceLabel(s) : null;
  const body = mdNote(n.body.length > 900 ? n.body.slice(0, 900) + '…' : n.body);
  return `<div class="card ${n.color ? 'c-' + n.color : ''} ${n.pinned ? 'pinned' : ''} ${boardSel.has(n.id) ? 'sel' : ''} ${panelState?.kind === 'note' && panelState.id === n.id ? 'open' : ''}" data-id="${n.id}">
    <div class="card-top"><span class="kind">${esc(n.kind)}</span>${n.pinned ? '<span class="pin" title="Pinned">●</span>' : ''}<span class="grip" title="Drag">⠿</span></div>
    ${n.title ? `<div class="card-title">${esc(n.title)}</div>` : ''}
    <div class="card-body">${body || '<span class="muted">Empty card</span>'}</div>
    <div class="card-meta">${n.tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}${l ? `<span>↳ ${esc(l.who || l.title)}${n.locator ? ', ' + esc(n.locator) : ''}</span>` : ''}</div></div>`;
}
function renderBoard() {
  if (!boardOn) return;
  const g = BG(), area = $('#bdArea');
  $('#bdNewPile').classList.toggle('hidden', g !== 'pile');
  $('#bdTidy').classList.toggle('hidden', g !== 'canvas');
  area.className = 'bd-area ' + (g === 'canvas' ? 'canvas' : 'cols');
  $('#bdTlFig').classList.toggle('hidden', g !== 'timeline');
  if (g === 'timeline') { renderTimeline(area); renderSelBar(); $('#bdNewPile').classList.add('hidden'); return; }
  if (g === 'canvas') {
    const notes = boardNotes().sort(boardSort);
    let i = 0; notes.forEach(n => { if (n.x == null || n.y == null) { const slot = freeSlot(i++); n.x = slot.x; n.y = slot.y; } });
    const w = Math.max(1400, ...notes.map(n => n.x + 300)), h = Math.max(900, ...notes.map(n => n.y + 320));
    area.innerHTML = `<div class="canvas-in" style="width:${w}px;height:${h}px">${notes.map(n => cardHTML(n).replace('class="card', `style="left:${n.x}px;top:${n.y}px" class="card`)).join('')}</div>`;
  } else {
    area.innerHTML = boardColumns().map((c, i, all) => `<div class="bd-col" data-key="${esc(c.key)}">
      <div class="bd-col-h"><b title="${esc(c.name)}">${esc(c.name)}</b><span class="muted small">${c.notes.length}</span>
      ${c.pile ? `<span class="col-act"><button class="ghost" data-pa="left" ${i > 1 ? '' : 'disabled'} title="Move left">‹</button><button class="ghost" data-pa="right" ${i < all.length - 1 ? '' : 'disabled'} title="Move right">›</button><button class="ghost" data-pa="ren" title="Rename">✎</button><button class="ghost danger" data-pa="del" title="Remove pile (cards go to Unsorted)">✕</button></span>` : ''}
      <button class="ghost add-card" data-pa="add" title="New card here">+</button></div>
      <div class="bd-cards">${c.notes.map(cardHTML).join('') || '<div class="bd-empty">Drop cards here</div>'}</div></div>`).join('') ||
      `<div class="empty">No cards${$('#bdQ').value ? ' match' : ' yet'}.</div>`;
  }
  renderSelBar();
}
const renderBoardSoon = debounce(renderBoard, 200);
function freeSlot(i) { const per = Math.max(3, Math.floor(($('#bdArea').clientWidth - 40) / 250)); return { x: 20 + (i % per) * 250, y: 20 + Math.floor(i / per) * 260 }; }
function renderSelBar() {
  const n = boardSel.size; $('#bdSel').classList.toggle('hidden', !n);
  $('#bdSelN').textContent = `${n} selected`;
}
$('#btnBoard').addEventListener('click', openBoard);
$('#bdBack').addEventListener('click', () => { closeBoard(); openDoc(curDocId); });
$('#bdGroup').addEventListener('change', e => { PREFS.boardGroup = e.target.value; savePrefs(); renderBoard(); });
$('#bdQ').addEventListener('input', renderBoardSoon);
$('#bdNewCard').addEventListener('click', () => newCardIn(BG() === 'pile' ? '' : null));
$('#bdNewPile').addEventListener('click', async () => {
  const name = await ask('New pile', 'Name the pile (e.g. “Chapter 3”, “Counterarguments”, “Maybe”).', 'Create', ''); if (!name) return;
  P.piles.push({ id: uid('pl'), name }); renderBoard(); markDirty();
});
$('#bdTidy').addEventListener('click', () => { boardNotes().sort(boardSort).forEach((n, i) => { const s = freeSlot(i); n.x = s.x; n.y = s.y; }); renderBoard(); markDirty(); });
function newCardIn(key) {
  const n = newNote(), g = BG();
  if (key != null && key !== '') { if (g === 'pile') n.pile = key; if (g === 'tag') n.tags = [key]; if (g === 'source') { n.sourceId = key; n.kind = 'quote'; } if (g === 'kind') n.kind = key; }
  if (g === 'canvas') { const a = $('#bdArea'); n.x = a.scrollLeft + 40; n.y = a.scrollTop + 40; }
  P.notes.unshift(n); renderNoteList(); renderBoard(); openNote(n.id, true); markDirty();
}
$('#bdArea').addEventListener('click', async e => {
  const h = e.target.closest('.bd-col-h button'); if (!h) return;
  const key = h.closest('.bd-col').dataset.key, pa = h.dataset.pa;
  if (pa === 'add') { newCardIn(key); return; }
  const p = P.piles.find(x => x.id === key), i = P.piles.indexOf(p); if (!p) return;
  if (pa === 'ren') { const v = await ask('Rename pile', 'Pile name:', 'Rename', p.name); if (v) { p.name = v; renderBoard(); markDirty(); } }
  if (pa === 'left' && i > 0) { [P.piles[i - 1], P.piles[i]] = [P.piles[i], P.piles[i - 1]]; renderBoard(); markDirty(); }
  if (pa === 'right' && i < P.piles.length - 1) { [P.piles[i + 1], P.piles[i]] = [P.piles[i], P.piles[i + 1]]; renderBoard(); markDirty(); }
  if (pa === 'del') { if (!(await ask('Remove pile?', `Cards in “${p.name}” move to Unsorted. No cards are deleted.`, 'Remove pile'))) return; P.notes.forEach(n => { if (n.pile === p.id) n.pile = ''; }); P.piles.splice(i, 1); renderBoard(); markDirty(); }
});

/* pointer-based dragging: works with mouse, pen and touch */
let bd = null;
$('#bdArea').addEventListener('pointerdown', e => {
  const card = e.target.closest('.card'); if (!card || e.button > 0 || e.target.closest('a,button,input,textarea')) return;
  const area = $('#bdArea');
  if (area.classList.contains('timeline')) { bd = { id: card.dataset.id, card, sx: e.clientX, sy: e.clientY, started: false, pid: e.pointerId, noDrag: true, multi: e.shiftKey || e.metaKey || e.ctrlKey }; return; }
  bd = { id: card.dataset.id, card, sx: e.clientX, sy: e.clientY, started: false, from: card.closest('.bd-col')?.dataset.key, pid: e.pointerId,
    canvas: area.classList.contains('canvas'), x0: parseFloat(card.style.left) || 0, y0: parseFloat(card.style.top) || 0, multi: e.shiftKey || e.metaKey || e.ctrlKey };
});
document.addEventListener('pointermove', e => {
  if (!bd || e.pointerId !== bd.pid) return;
  const dx = e.clientX - bd.sx, dy = e.clientY - bd.sy;
  if (!bd.started) {
    if (bd.noDrag || Math.hypot(dx, dy) < 6) return;
    bd.started = true; document.body.classList.add('bd-dragging');
    try { bd.card.setPointerCapture(bd.pid); } catch (x) {}
    if (!bd.canvas) {
      const r = bd.card.getBoundingClientRect();
      bd.ghost = bd.card.cloneNode(true); bd.ghost.classList.add('ghost-card'); bd.ghost.style.width = r.width + 'px';
      bd.ox = e.clientX - r.left; bd.oy = e.clientY - r.top; document.body.appendChild(bd.ghost);
      bd.card.classList.add('placeholder');
    } else bd.card.classList.add('lifting');
  }
  e.preventDefault();
  if (bd.canvas) {
    bd.card.style.left = Math.max(0, bd.x0 + dx) + 'px'; bd.card.style.top = Math.max(0, bd.y0 + dy) + 'px';
  } else {
    bd.ghost.style.left = (e.clientX - bd.ox) + 'px'; bd.ghost.style.top = (e.clientY - bd.oy) + 'px';
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const col = (el && el.closest('.bd-col')) || (el && el.closest('#bdArea') ? $$('#bdArea .bd-col').find(c => { const r = c.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right; }) : null);
    $$('.bd-col.drop').forEach(c => c !== col && c.classList.remove('drop'));
    $$('.drop-line').forEach(x => x.remove());
    if (col) {
      col.classList.add('drop');
      const cards = $$('.card', col).filter(c => c !== bd.card);
      const before = cards.find(c => { const r = c.getBoundingClientRect(); return e.clientY < r.top + r.height / 2; });
      bd.to = col.dataset.key; bd.before = before ? before.dataset.id : null;
      const line = document.createElement('div'); line.className = 'drop-line';
      const list = $('.bd-cards', col); before ? list.insertBefore(line, before) : list.appendChild(line);
    } else bd.to = undefined;
  }
  // auto-scroll near the edges
  const a = $('#bdArea'), ar = a.getBoundingClientRect(), edge = 50;
  if (e.clientX > ar.right - edge) a.scrollLeft += 14; else if (e.clientX < ar.left + edge) a.scrollLeft -= 14;
  if (e.clientY > ar.bottom - edge) a.scrollTop += 14; else if (e.clientY < ar.top + edge) a.scrollTop -= 14;
  const col = document.elementFromPoint(e.clientX, e.clientY)?.closest('.bd-cards');
  if (col) { const cr = col.getBoundingClientRect(); if (e.clientY > cr.bottom - edge) col.scrollTop += 12; else if (e.clientY < cr.top + edge) col.scrollTop -= 12; }
}, { passive: false });
document.addEventListener('pointerup', e => {
  if (!bd || e.pointerId !== bd.pid) return;
  const d = bd; bd = null; document.body.classList.remove('bd-dragging');
  $$('.bd-col.drop').forEach(c => c.classList.remove('drop')); $$('.drop-line').forEach(x => x.remove());
  if (d.ghost) d.ghost.remove();
  const n = P.notes.find(x => x.id === d.id); if (!n) return;
  if (!d.started) { // a click
    if (d.multi) { boardSel.has(n.id) ? boardSel.delete(n.id) : boardSel.add(n.id); d.card.classList.toggle('sel'); renderSelBar(); }
    else { boardSel.clear(); renderSelBar(); $$('#bdArea .card.sel').forEach(c => c.classList.remove('sel')); openNote(n.id); $$('#bdArea .card.open').forEach(c => c.classList.remove('open')); d.card.classList.add('open'); }
    return;
  }
  if (d.canvas) { n.x = Math.round(parseFloat(d.card.style.left)); n.y = Math.round(parseFloat(d.card.style.top)); n.modified = nowISO(); d.card.classList.remove('lifting'); markDirty(); return; }
  if (d.to === undefined) { renderBoard(); return; }
  const ids = boardSel.has(n.id) && boardSel.size > 1 ? [...boardSel] : [n.id];
  ids.forEach(id => dropNote(P.notes.find(x => x.id === id), d.from, d.to, d.before));
  renderBoard(); renderNoteList(); markDirty();
});
document.addEventListener('pointercancel', () => { if (bd) { bd.ghost && bd.ghost.remove(); bd = null; document.body.classList.remove('bd-dragging'); renderBoard(); } });
function dropNote(n, from, to, beforeId) {
  if (!n) return;
  const g = BG();
  if (g === 'pile') n.pile = to;
  if (g === 'tag' && from !== to) { n.tags = n.tags.filter(t => t !== from); if (to && !n.tags.includes(to)) n.tags.push(to); }
  if (g === 'source') n.sourceId = to;
  if (g === 'kind' && to) n.kind = to;
  const col = boardColumns().find(c => c.key === to); const list = col ? col.notes.filter(x => x.id !== n.id && x.pinned === n.pinned) : [];
  let i = beforeId ? list.findIndex(x => x.id === beforeId) : list.length; if (i < 0) i = list.length;
  const prev = list[i - 1], next = list[i];
  n.order = prev && next ? (prev.order + next.order) / 2 : prev ? prev.order + 1 : next ? next.order - 1 : n.order;
  n.modified = nowISO();
}

/* bulk actions on selected cards */
$('#bdSel').addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  const sel = P.notes.filter(n => boardSel.has(n.id)).sort(boardSort), act = b.dataset.b;
  if (act === 'clear') { boardSel.clear(); renderBoard(); return; }
  if (act === 'color') { sel.forEach(n => { n.color = b.dataset.c; n.modified = nowISO(); }); }
  if (act === 'pin') { const on = !sel.every(n => n.pinned); sel.forEach(n => n.pinned = on); }
  if (act === 'tag') {
    const v = await ask('Tag selected cards', 'Tags to add, separated by commas. Put a minus sign in front to remove one (e.g. -draft).', 'Apply', ''); if (!v) return;
    v.split(',').map(t => t.trim().replace(/^#/, '')).filter(Boolean).forEach(t => sel.forEach(n => { if (t.startsWith('-')) n.tags = n.tags.filter(x => x !== t.slice(1).trim()); else if (!n.tags.includes(t)) n.tags.push(t); }));
  }
  if (act === 'pile') {
    const v = await ask('Move to pile', `Pile name (an existing one or a new one). Leave blank for Unsorted. Piles: ${P.piles.map(p => p.name).join(', ') || 'none yet'}.`, 'Move', ''); if (v === null) return;
    let p = v ? P.piles.find(x => x.name.toLowerCase() === v.toLowerCase()) : null;
    if (v && !p) { p = { id: uid('pl'), name: v }; P.piles.push(p); }
    sel.forEach(n => n.pile = p ? p.id : '');
  }
  if (act === 'merge') {
    if (sel.length < 2) { toast('Select two or more cards to merge.'); return; }
    const srcs = new Set(sel.map(n => n.sourceId || ''));
    if (!(await ask('Merge cards?', `${sel.length} cards become one, in board order. ${srcs.size > 1 ? 'They cite different sources, so the merged card keeps the first card’s source. Check the citations afterward.' : ''}`, 'Merge'))) return;
    const [first, ...rest] = sel;
    first.body = sel.map(n => (sel.length > 1 && n.title && n !== first ? `**${n.title}**\n\n` : '') + n.body.trim()).join('\n\n');
    first.tags = [...new Set(sel.flatMap(n => n.tags))]; first.modified = nowISO();
    P.notes = P.notes.filter(n => !rest.includes(n)); boardSel = new Set([first.id]); openNote(first.id);
  }
  if (act === 'draft') {
    const html = sel.map(n => (n.title ? `<h2>${esc(n.title)}</h2>` : '') + noteToHTML(n)).join('');
    const d = newDoc('Draft from cards · ' + new Date().toLocaleDateString(), html || '<p><br></p>'); closeBoard(); addDoc(d); switchTab('docs');
    toast(`Drafted ${sel.length} cards into a new document.`); return;
  }
  if (act === 'del') {
    if (!(await ask('Delete cards?', `Delete ${sel.length} card${sel.length > 1 ? 's' : ''}? This can’t be undone after you save.`, 'Delete'))) return;
    P.notes = P.notes.filter(n => !boardSel.has(n.id)); boardSel.clear(); if (panelState?.kind === 'note' && !P.notes.some(n => n.id === panelState.id)) closePanel();
  }
  renderBoard(); renderNoteList(); markDirty();
});
$('#bdSel').insertAdjacentHTML('afterbegin', `<span id="bdSelN"></span><span class="swatches">${CARD_COLORS.map(c => `<button class="sw ${c ? 'c-' + c : 'none'}" data-b="color" data-c="${c}" title="${c || 'No color'}"></button>`).join('')}</span>`);
document.addEventListener('keydown', e => {
  if (!boardOn || document.querySelector('dialog[open]') || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'a') { e.preventDefault(); boardNotes().forEach(n => boardSel.add(n.id)); renderBoard(); }
  if (e.key === 'Escape' && boardSel.size) { boardSel.clear(); renderBoard(); }
});
$('#panelBody').addEventListener('click', e => { const a = e.target.closest('#noteLinks a[href^="#note:"]'); if (a) { e.preventDefault(); followNoteLink(decodeURIComponent(a.getAttribute('href').slice(6))); } });

/* ================================================================
   Web clipper, tab hand-off, storage protection
   ================================================================ */
const TAB_ID = uid('t');
const bc = 'BroadcastChannel' in window ? new BroadcastChannel('commonplace-app') : null;
let appReady = false, otherTabWarned = false;
if (bc) bc.onmessage = e => {
  const m = e.data || {};
  if (m.type === 'ping' && appReady) { bc.postMessage({ type: 'pong', to: m.from, from: TAB_ID }); if (!m.clipOnly) showTabWarning(); }
  if (m.type === 'clip' && m.to === TAB_ID && appReady) { handleClip(m.clip); bc.postMessage({ type: 'clip-ok', to: m.from }); try { window.focus(); } catch (x) {} }
};
function findOtherTab(clipOnly, ms = 350) {
  return new Promise(res => {
    if (!bc) return res(null);
    const t = setTimeout(() => { bc.removeEventListener('message', on); res(null); }, ms);
    const on = e => { const m = e.data || {}; if (m.type === 'pong' && m.to === TAB_ID) { clearTimeout(t); bc.removeEventListener('message', on); res(m.from); } };
    bc.addEventListener('message', on);
    bc.postMessage({ type: 'ping', from: TAB_ID, clipOnly });
  });
}
function showTabWarning() {
  if (otherTabWarned) return; otherTabWarned = true;
  $('#tabBar').classList.remove('hidden');
}
$('#tabBarClose').addEventListener('click', () => $('#tabBar').classList.add('hidden'));
function readClipFromHash() {
  const h = location.hash; if (!h.startsWith('#clip=')) return null;
  try { return JSON.parse(decodeURIComponent(h.slice(6))); } catch (e) { return null; }
  finally { try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
}
window.addEventListener('hashchange', () => { const c = readClipFromHash(); if (c && appReady) handleClip(c); });
const normUrlKey = u => String(u || '').replace(/^https?:\/\/(www\.)?/i, '').replace(/[#?].*$/, '').replace(/\/+$/, '').toLowerCase();
function clipToCsl(c) {
  const t = c.type || '';
  const type = c.journal ? 'article-journal' : /NewsArticle|ReportageNewsArticle/.test(t) ? 'article-newspaper' : /BlogPosting/.test(t) ? 'post-weblog' : /Report/.test(t) ? 'report' : /ScholarlyArticle/.test(t) ? 'article-journal' : /^Book$/.test(t) ? 'book' : 'webpage';
  const o = { type, URL: c.url, accessed: todayParts() };
  let title = String(c.title || '').trim();
  if (c.titleFromDoc && c.site) title = title.replace(new RegExp('\\s*[|\\-–—:·]\\s*' + c.site.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*$', 'i'), '');
  if (title) o.title = title;
  const site = c.journal || c.site; if (site) o['container-title'] = site;
  const names = (c.authors || []).map(a => String(a).trim()).filter(a => a && !/^https?:/.test(a) && a.length < 80);
  if (names.length) o.author = [...new Set(names)].slice(0, 12).map(nameFromOsint).filter(Boolean);
  if (c.date) { const iso = String(c.date).match(/^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?/); o.issued = iso ? { 'date-parts': [[+iso[1], +iso[2], ...(iso[3] ? [+iso[3]] : [])]] } : parseDate(c.date); }
  ['volume', 'issue', 'publisher'].forEach(k => { if (c[k]) o[k] = c[k]; });
  if (c.firstpage) o.page = c.firstpage + (c.lastpage ? '–' + c.lastpage : '');
  if (c.doi) o.DOI = String(c.doi).replace(/^https?:\/\/(dx\.)?doi\.org\//i, '');
  return o;
}
async function handleClip(c) {
  if (!c || !c.url) return;
  closeBoard();
  let s = P.sources.find(x => x.csl.URL && normUrlKey(x.csl.URL) === normUrlKey(c.url));
  const isNew = !s;
  if (!s) s = addSource(clipToCsl(c));
  let n = null;
  if (c.sel) {
    n = newNote(); n.kind = 'quote'; n.body = String(c.sel).trim(); n.sourceId = s.id;
    n.title = n.body.split(/\s+/).slice(0, 7).join(' ') + (n.body.split(/\s+/).length > 7 ? '…' : '');
    P.notes.unshift(n); renderNoteList();
  }
  markDirty();
  if (n) { switchTab('notes'); openNote(n.id); } else { switchTab('sources'); openSource(s.id); }
  document.body.classList.add('side-open');
  toast(`${n ? 'Quote clipped' : 'Page clipped'} from ${s.csl['container-title'] || new URL(c.url).hostname}${isNew ? '' : ' (source already in your library)'}.`);
  if (isNew && navigator.onLine !== false) {
    // fill gaps from DOI / Citoid without overwriting what the page told us
    try {
      const extra = c.doi ? await lookupId(c.doi) : (!s.csl.author || !s.csl.issued) ? await citoid(c.url) : null;
      if (extra) { takePartial(extra); const merged = Object.assign({}, extra, s.csl); if (c.doi) Object.assign(merged, extra, { URL: s.csl.URL }); s.csl = merged; srcVersion++; renderSourceList(); if (panelState?.kind === 'source' && panelState.id === s.id) renderSourcePanel(s); markDirty(); }
    } catch (e) { /* offline or blocked; the clipped data stands */ }
  }
}
/* the bookmarklet itself: runs on the page being clipped */
function clipperSource() {
  return `(function(){var A=${JSON.stringify(location.href.replace(/#.*$/, ''))};function M(n){return Array.prototype.slice.call(document.querySelectorAll('meta[name="'+n+'"],meta[property="'+n+'"]')).map(function(m){return m.content}).filter(Boolean)}var j={};try{var S=document.querySelectorAll('script[type="application/ld+json"]');for(var i=0;i<S.length;i++){var d=JSON.parse(S[i].textContent);d=[].concat(d['@graph']||d);for(var k=0;k<d.length;k++){var t=[].concat(d[k]['@type']).join(' ');if(/Article|Posting|Report|Book|WebPage/.test(t)&&!j['@type']){j=d[k]}}}}catch(e){}function N(v){return[].concat(v||[]).map(function(x){return typeof x=='string'?x:x&&x.name}).filter(Boolean)}var au=M('citation_author');if(!au.length)au=N(j.author);if(!au.length)au=M('author').concat(M('parsely-author'),M('sailthru.author'),M('dc.creator'),M('DC.creator'));var cn=document.querySelector('link[rel=canonical]');var tt=M('citation_title')[0]||M('og:title')[0]||j.headline||'';var c={v:1,url:(cn&&cn.href)||location.href,title:tt||document.title,titleFromDoc:!tt,site:M('og:site_name')[0]||(j.publisher&&j.publisher.name)||location.hostname.replace(/^www\\./,''),journal:M('citation_journal_title')[0]||'',authors:au,date:M('citation_publication_date')[0]||M('citation_date')[0]||M('article:published_time')[0]||j.datePublished||M('date')[0]||M('dc.date')[0]||M('DC.date.issued')[0]||'',volume:M('citation_volume')[0]||'',issue:M('citation_issue')[0]||'',firstpage:M('citation_firstpage')[0]||'',lastpage:M('citation_lastpage')[0]||'',doi:M('citation_doi')[0]||M('dc.identifier')[0]&&/^10\\./.test(M('dc.identifier')[0])&&M('dc.identifier')[0]||'',publisher:M('citation_publisher')[0]||'',type:[].concat(j['@type']||'').join(' '),sel:String(window.getSelection()).trim().slice(0,12000)};window.open(A+'#clip='+encodeURIComponent(JSON.stringify(c)),'commonplace')})()`;
}
function openClipper() {
  const href = 'javascript:' + encodeURIComponent(clipperSource());
  $('#clipLink').setAttribute('href', href);
  const local = location.protocol === 'file:';
  $('#clipLocal').classList.toggle('hidden', !local);
  $('#clipHere').textContent = location.href.replace(/#.*$/, '');
  $('#clipDlg').showModal();
}
$('#clipLink').addEventListener('click', e => { e.preventDefault(); toast('Drag this button to your bookmarks bar. Clicking it here does nothing.'); });
$('#clipCopy').addEventListener('click', async () => { try { await navigator.clipboard.writeText('javascript:' + clipperSource()); toast('Bookmarklet code copied.'); } catch (e) { toast('Copy blocked. Drag the button to your bookmarks bar instead.'); } });
$('#clipClose').addEventListener('click', () => $('#clipDlg').close());
$('#btnClipper').addEventListener('click', openClipper);

/* storage protection */
async function storageStatus() {
  const s = navigator.storage; if (!s || !s.persisted) return { supported: false };
  let persisted = false, usage = 0, quota = 0;
  try { persisted = await s.persisted(); } catch (e) {}
  try { const est = await s.estimate(); usage = est.usage || 0; quota = est.quota || 0; } catch (e) {}
  return { supported: true, persisted, usage, quota };
}
let persistAsked = false;
async function requestPersist() {
  if (persistAsked || !navigator.storage?.persist) return false; persistAsked = true;
  try { return await navigator.storage.persist(); } catch (e) { return false; }
}
const fmtBytes = b => b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' KB';
async function renderStorageStatus() {
  const st = await storageStatus(), el = $('#stStorage');
  if (!st.supported) { el.innerHTML = 'This browser doesn’t report storage status. Keep saving your project file.'; return; }
  el.innerHTML = (st.persisted ? '<b class="ok">Protected.</b> The browser won’t clear Anabasis’s copy to free space.' : '<b class="warn">Not protected yet.</b> The browser may clear its copy when space runs low, and Safari clears it after 7 days of browsing without a visit. <button id="stProtect" class="small">Protect</button>') +
    (st.quota ? ` <span class="muted">Using ${fmtBytes(st.usage)} of ${fmtBytes(st.quota)} available.</span>` : '');
  $('#stProtect')?.addEventListener('click', async () => { persistAsked = false; const ok = await requestPersist(); renderStorageStatus(); toast(ok ? 'Storage protected.' : 'The browser declined for now. It usually agrees once you bookmark or install the page, or use it regularly.'); });
}

/* ================================================================
   Nonfiction toolkit
   ================================================================ */
const escRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const todayKey = (d = new Date()) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
const wc = t => String(t || '').trim().split(/\s+/).filter(Boolean).length;

/* ---------- book-style PDF (Paged.js): footnotes at the foot of each page ---------- */
function pagedCSS(doc) {
  const L = doc.layout, size = parseFloat(L.size) || 12;
  return `@page{size:${L.paper === 'A4' ? 'A4' : 'letter'};margin:1in;${L.pageNums ? '@bottom-center{content:counter(page);font:10pt Georgia,serif}' : ''}@top-center{content:string(runhead);font:italic 9pt Georgia,serif;color:#555}@footnote{border-top:.5pt solid #999;padding-top:6pt;margin-top:8pt}}
@page:first{@top-center{content:none}}
html,body{margin:0;background:#fff;color:#000}
.docbody{max-width:none;padding:0}
.docbody .fn-note{float:footnote;font-size:${Math.max(8, size - 2)}pt;line-height:1.3;text-indent:0;font-style:normal;font-weight:normal;text-align:left;margin:0 0 3pt}
.docbody .fn-note::footnote-marker{font-size:inherit}
.docbody ::footnote-call{font-size:70%;vertical-align:super;line-height:0}
.docbody .rh{string-set:runhead content(text);height:0;overflow:hidden;margin:0}
.docbody h1.chapter-title,.docbody h1.part-title{string-set:runhead content(text)}
.docbody .ch-break,.docbody .end-sec,.docbody nav.toc{break-before:page}
.docbody nav.toc ol{list-style:none;padding:0}
.docbody nav.toc li{display:flex;gap:6pt;margin:0 0 4pt}
.docbody nav.toc li a{color:inherit;text-decoration:none;flex:1}
.docbody nav.toc li a::after{content:target-counter(attr(href url), page);float:right}
.docbody nav.toc .toc-part{font-weight:bold;margin-top:8pt}
.docbody mark{background:#fde68a}
.docbody figure{break-inside:avoid}
.docbody nav.lof{break-before:page}
.docbody nav.lof ol{list-style:none;padding:0}
.docbody nav.lof li{margin:0 0 4pt}
.docbody nav.lof li a{color:inherit;text-decoration:none}
.docbody nav.lof li a::after{content:target-counter(attr(href url), page);float:right}
.docbody .mg-ref::after{content:target-counter(attr(href url), page)}
.docbody .mg-ref{color:inherit;text-decoration:none}`;
}
function exportPagedPDF(doc) {
  const x = buildExport(doc, 'paged'), cs = docClassAndStyle(doc);
  const lib = document.getElementById('lib-paged').textContent;
  const bib = refsHTML(Object.assign({}, x.out, { notes: [] }), true);
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(fileSafe(doc.title))}</title><style>${$('#docCss').textContent}\n${pagedCSS(doc)}</style>
<script>${IX_PAGES_JS}window.PagedConfig={auto:true,after:function(){try{cpIndexPages()}catch(e){}parent.postMessage({cpPaged:1},'*')}};<\/script><script>${lib}<\/script></head>
<body><article class="${cs.cls}" style="${cs.style}"><p class="rh">${esc(doc.title)}</p>${x.title ? `<header class="title-block">${x.title}</header>` : ''}${x.body}${bib}${x.index || ''}${x.marginalia || ''}</article></body></html>`;
  $$('iframe.paged-print').forEach(f => f.remove());
  const f = document.createElement('iframe'); f.className = 'paged-print';
  f.style.cssText = 'position:fixed;left:-10000px;top:0;width:8.5in;height:11in;border:0';
  toast('Laying out pages with footnotes…');
  const done = e => {
    if (!e.data || !e.data.cpPaged || e.source !== f.contentWindow) return;
    window.removeEventListener('message', done);
    try { f.contentWindow.focus(); f.contentWindow.print(); } catch (err) { toast('Printing isn’t available here. Open Anabasis directly in your browser.'); }
    setTimeout(() => f.remove(), 120000);
  };
  window.addEventListener('message', done);
  f.srcdoc = html; document.body.appendChild(f);
  return html;
}
function pagedHTMLFor(doc) { // used by tests and for saving a print-ready page
  const x = buildExport(doc, 'paged'), cs = docClassAndStyle(doc);
  return { x, cs, css: pagedCSS(doc) };
}

/* ---------- Word import (mammoth.js) ---------- */
async function importDocx(file) {
  toast('Reading “' + file.name + '”…');
  let r;
  try { r = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() }); }
  catch (e) { toast('Couldn’t read that Word file: ' + e.message); return; }
  const tmp = document.createElement('div'); tmp.innerHTML = r.value;
  const notes = {};
  $$('li[id^="footnote-"],li[id^="endnote-"]', tmp).forEach(li => {
    $$('a[href^="#footnote-ref-"],a[href^="#endnote-ref-"]', li).forEach(a => a.remove());
    notes[li.id] = li.textContent.replace(/\s+/g, ' ').trim();
  });
  let fnCount = 0;
  $$('a[href^="#footnote-"],a[href^="#endnote-"]', tmp).forEach(a => {
    const key = a.getAttribute('href').slice(1); if (!(key in notes)) return;
    const holder = a.closest('sup') || a;
    const t = document.createElement('template'); t.innerHTML = fnHTML(notes[key]); holder.replaceWith(t.content); fnCount++;
  });
  $$('ol', tmp).forEach(ol => { if (ol.querySelector('li[id^="footnote-"],li[id^="endnote-"]') || (!ol.textContent.trim())) ol.remove(); });
  $$('img', tmp).forEach(img => { const p = img.closest('p'); if (p && !p.textContent.trim() && p.parentNode === tmp) p.replaceWith(img); });
  const clean = document.createElement('div'); clean.innerHTML = sanitize(tmp.innerHTML);
  wrapBareTables(clean);
  // a paragraph like “Figure 3. Caption” or “Table 2: Caption” next to a figure/table becomes its caption
  $$('table', clean).forEach(t => { const f = t.closest('figure'), prev = f && f.previousElementSibling; if (prev && prev.nodeName === 'P' && /^\s*Table\s+\d+[.:]/i.test(prev.textContent)) { f.querySelector('figcaption').innerHTML = stripCapLabel(prev.innerHTML, 'Table'); prev.remove(); } });
  const tables = $$('table', clean).length;
  const imgs = await adoptInlineImages(clean);
  $$('figure.fig', clean).forEach(f => { const nx = f.nextElementSibling; if (nx && nx.nodeName === 'P' && /^\s*(Figure|Fig\.|Map|Chart)\s*\d+[.:]/i.test(nx.textContent)) { f.querySelector('figcaption').innerHTML = stripCapLabel(nx.innerHTML, 'Figure|Fig\\.|Map|Chart'); nx.remove(); } });
  const h1 = tmp.querySelector('h1');
  const title = (h1 && h1.textContent.trim()) || file.name.replace(/\.docx$/i, '');
  const d = newDoc(title, stripCp(clean.innerHTML) || '<p><br></p>');
  addDoc(d); switchTab('docs');
  const bits = [fnCount && `${fnCount} footnote${fnCount > 1 ? 's' : ''}`, imgs && `${imgs} image${imgs > 1 ? 's' : ''}`, tables && `${tables} table${tables > 1 ? 's' : ''}`].filter(Boolean);
  toast(`Imported “${title}”${bits.length ? ' with ' + bits.join(', ').replace(/, ([^,]*)$/, ' and $1') : ''}.`);
}
$('#btnImportDocx').addEventListener('click', () => $('#fileDocx').click());
$('#fileDocx').addEventListener('change', e => { const f = e.target.files[0]; e.target.value = ''; if (f) importDocx(f); });

/* ================================================================
   Drafts: saved when you choose, compared side by side
   A draft is a frozen copy of one document (doc.snapshots, kind 'draft', numbered).
   Safety copies (kind 'safety') are made automatically only before Anabasis replaces
   text for you, and are kept apart from your drafts.
   ================================================================ */
let draftsOn = false, dfLeft = '', dfRight = 'current', dfRows = [], dfTook = false, dfPos = -1;
function docPlain(html) {
  const t = document.createElement('div'); t.innerHTML = html;
  $$('.cite,.fn,.flag', t).forEach(m => m.remove());
  return [...t.children].map(c => c.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n\n');
}
const isDraft = v => v.kind !== 'safety';
const nextDraftNo = d => Math.max(0, ...d.snapshots.filter(isDraft).map(v => +v.n || 0)) + 1;
function snapshot(doc, name, kind = 'safety', note = '') {
  if (doc.id === curDocId) syncEditor();
  const n = kind === 'draft' ? nextDraftNo(doc) : 0;
  const v = { id: uid('v'), n, kind, name: name || (kind === 'draft' ? 'Draft ' + n : 'Safety copy'), note, date: nowISO(), html: doc.html, words: wc(docPlain(doc.html)) };
  doc.snapshots.unshift(v); markDirty(); updateDraftBtn(); return v;
}
const dfWhen = iso => new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', year: new Date(iso).getFullYear() === new Date().getFullYear() ? undefined : 'numeric', hour: 'numeric', minute: '2-digit' });
function updateDraftBtn() {
  const d = curDoc(), b = $('#btnVersions'); if (!d || !b) return;
  const n = d.snapshots.filter(isDraft).length;
  b.innerHTML = `Drafts${n ? ` <span class="df-count">${n}</span>` : ''}`;
  b.title = n ? `${n} saved draft${n === 1 ? '' : 's'}. Save, compare side by side, restore (⌘/Ctrl+Alt+D saves one)` : 'Save a draft of this document to compare against later (⌘/Ctrl+Alt+D)';
}

/* ---------- saving and editing a draft ---------- */
let sdEditing = null;
function openSaveDraft(v = null) {
  const d = curDoc(); if (!d) return;
  sdEditing = v;
  $('#sdTitle').textContent = v ? 'Edit draft' : 'Save a draft';
  $('#sdName').value = v ? v.name : ''; $('#sdName').placeholder = v ? '' : 'Draft ' + nextDraftNo(d);
  $('#sdNote').value = v ? v.note || '' : '';
  $('#sdOk').textContent = v ? 'Save changes' : 'Save draft';
  if (!v) { syncEditor(); const last = d.snapshots.find(isDraft); $('#sdInfo').textContent = last ? `${wc(docPlain(d.html)).toLocaleString()} words now. Last draft: “${last.name}”, ${dfWhen(last.date)}${last.html === d.html ? ' (no changes since)' : ''}.` : `${wc(docPlain(d.html)).toLocaleString()} words now. This will be Draft 1.`; }
  else $('#sdInfo').textContent = `${v.words.toLocaleString()} words, saved ${dfWhen(v.date)}.`;
  $('#sdDlg').showModal(); setTimeout(() => $('#sdName').focus(), 30);
}
$('#sdCancel').addEventListener('click', () => $('#sdDlg').close());
$('#sdOk').addEventListener('click', () => {
  const d = curDoc(), name = $('#sdName').value.trim(), note = $('#sdNote').value.trim();
  if (sdEditing) { sdEditing.name = name || sdEditing.name; sdEditing.note = note; markDirty(); $('#sdDlg').close(); if (draftsOn) renderDrafts(); return; }
  const v = snapshot(d, name, 'draft', note);
  $('#sdDlg').close();
  toast(`Saved “${v.name}”. Open Drafts to compare it with later work.`);
  if (draftsOn) { dfLeft = 'v:' + v.id; dfRight = 'current'; renderDrafts(); }
});
$('#sdDlg').addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.id === 'sdName') { e.preventDefault(); $('#sdOk').click(); } });

/* ---------- the workspace ---------- */
function openDrafts(left) {
  const d = curDoc(); if (!d) return;
  syncEditor(); if (boardOn) closeBoard(); if (planOn) closePlan(); if (homeOn) closeHome(); if (relOn) closeRel();
  draftsOn = true; dfTook = false; document.body.classList.add('drafts-on'); $('#drafts').classList.remove('hidden'); document.body.classList.remove('side-open');
  const ds = d.snapshots.filter(isDraft);
  if (left) dfLeft = left; else if (!dfLeft || !dfSource(dfLeft)) dfLeft = ds[0] ? 'v:' + ds[0].id : (d.snapshots[0] ? 'v:' + d.snapshots[0].id : '');
  if (!dfSource(dfRight)) dfRight = 'current';
  renderDrafts();
}
function closeDrafts() { draftsOn = false; document.body.classList.remove('drafts-on'); $('#drafts').classList.add('hidden'); }
$('#btnVersions').addEventListener('click', () => openDrafts());
$('#dfBack').addEventListener('click', () => { closeDrafts(); openDoc(curDocId); });
$('#dfSave').addEventListener('click', () => openSaveDraft());
function dfSource(key) {
  const d = curDoc(); if (!d || !key) return null;
  if (key === 'current') { if (d.id === curDocId) syncEditor(); return { key, name: 'Current text', short: 'Current', html: d.html, date: d.modified, words: wc(docPlain(d.html)) }; }
  if (key.startsWith('v:')) { const v = d.snapshots.find(x => x.id === key.slice(2)); return v ? { key, name: v.name, short: v.kind === 'draft' && v.n ? 'Draft ' + v.n : v.name, html: v.html, date: v.date, words: v.words, v } : null; }
  if (key.startsWith('cp:')) { const [, cid, did] = key.split(':'), snap = CP_CACHE[cid], o = snap && snap.docs.find(x => x.id === did), meta = cpList().find(x => x.id === cid); return o ? { key, name: `Checkpoint: ${meta ? meta.name : ''}`, short: meta ? meta.name : 'Checkpoint', html: o.html, date: meta ? meta.date : o.modified, words: wc(docPlain(o.html)), other: true } : null; }
  if (key.startsWith('doc:')) { const o = P.docs.find(x => x.id === key.slice(4)); return o ? { key, name: o.title || 'Untitled', short: o.title || 'Untitled', html: o.html, date: o.modified, words: wc(docPlain(o.html)), other: true } : null; }
  return null;
}
function dfOptions(sel) {
  const d = curDoc(), drafts = d.snapshots.filter(isDraft), safety = d.snapshots.filter(v => !isDraft(v)), others = P.docs.filter(o => o.id !== d.id);
  const o = (k, l) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(l)}</option>`;
  return o('current', 'Current text') +
    (drafts.length ? `<optgroup label="Drafts">${drafts.map(v => o('v:' + v.id, (v.n && v.name !== 'Draft ' + v.n ? `Draft ${v.n}: ` : '') + v.name + ' · ' + dfWhen(v.date))).join('')}</optgroup>` : '') +
    (safety.length ? `<optgroup label="Safety copies">${safety.map(v => o('v:' + v.id, v.name + ' · ' + dfWhen(v.date))).join('')}</optgroup>` : '') +
    (sel && sel.startsWith('cp:') && dfSource(sel) ? `<optgroup label="Checkpoint">${o(sel, dfSource(sel).name)}</optgroup>` : '') +
    (others.length ? `<optgroup label="Other documents">${others.map(x => o('doc:' + x.id, x.title || 'Untitled')).join('')}</optgroup>` : '');
}
function renderDrafts() {
  const d = curDoc(); if (!d) return;
  $('#dfHead').textContent = `Drafts of “${d.title || 'Untitled'}”`;
  const drafts = d.snapshots.filter(isDraft), safety = d.snapshots.filter(v => !isDraft(v));
  const item = v => {
    const on = dfLeft === 'v:' + v.id || dfRight === 'v:' + v.id;
    const label = v.kind === 'draft' && v.n ? `Draft ${v.n}` : '';
    return `<li class="df-item ${on ? 'on' : ''}" data-v="${v.id}">
      <div class="df-it-head">${label ? `<span class="df-num">${label}</span>` : ''}<b>${esc(v.name !== label ? v.name : '')}</b></div>
      <div class="df-meta">${dfWhen(v.date)} · ${v.words.toLocaleString()} words</div>
      ${v.note ? `<p class="df-note">${esc(v.note)}</p>` : ''}
      <div class="df-acts"><button data-a="cmp" class="small">Compare with current</button><button data-a="restore" class="small">Restore</button><button data-a="copy" class="small" title="Keep this draft as its own document, e.g. an alternate version">Copy to new doc</button><button data-a="edit" class="small ghost">Edit</button><button data-a="del" class="small ghost danger" title="Delete this draft">Delete</button></div>
    </li>`;
  };
  $('#dfRail').innerHTML = `
    <div class="df-cur ${dfLeft === 'current' || dfRight === 'current' ? 'on' : ''}"><b>Current text</b><div class="df-meta">${wc(docPlain(d.html)).toLocaleString()} words · edited ${relTime(d.modified)}</div></div>
    ${drafts.length ? `<ol class="df-list">${drafts.map(item).join('')}</ol>` : `<div class="df-empty"><p>No drafts yet.</p><p>Save one before a big revision, when you send it out, or whenever you want a fixed point to come back to. Drafts are only made when you choose.</p><button class="primary" data-a="save">Save Draft 1</button></div>`}
    ${safety.length ? `<details class="df-safety"><summary>Safety copies <span class="count">${safety.length}</span></summary><p class="small muted">Made automatically just before Anabasis replaced text for you (restoring a draft, or bringing back paragraphs).</p><ol class="df-list">${safety.map(item).join('')}</ol></details>` : ''}`;
  $('#dfL').innerHTML = dfOptions(dfLeft); $('#dfR').innerHTML = dfOptions(dfRight);
  if (!dfLeft) $('#dfL').insertAdjacentHTML('afterbegin', '<option value="" selected>Choose a draft…</option>');
  dfCompute();
}
$('#dfL').addEventListener('change', e => { dfLeft = e.target.value; dfTook = false; renderDrafts(); });
$('#dfR').addEventListener('change', e => { dfRight = e.target.value; dfTook = false; renderDrafts(); });
$('#dfSwap').addEventListener('click', () => { [dfLeft, dfRight] = [dfRight, dfLeft]; renderDrafts(); });
$('#dfAll').addEventListener('change', () => dfRender());
$('#dfRail').addEventListener('click', async e => {
  const d = curDoc();
  if (e.target.closest('[data-a=save]')) { openSaveDraft(); return; }
  if (e.target.closest('.df-cur')) { dfRight = 'current'; renderDrafts(); return; }
  const li = e.target.closest('.df-item'); if (!li) return;
  const v = d.snapshots.find(x => x.id === li.dataset.v); if (!v) return;
  const a = e.target.closest('button')?.dataset.a;
  if (!a || a === 'cmp') { dfLeft = 'v:' + v.id; if (a === 'cmp' || dfRight === dfLeft) dfRight = 'current'; dfTook = false; renderDrafts(); return; }
  if (a === 'edit') { openSaveDraft(v); return; }
  if (a === 'del') { if (await ask('Delete this draft?', `“${v.name}” (${dfWhen(v.date)}) will be removed. Your current text isn’t affected.`, 'Delete draft')) { d.snapshots = d.snapshots.filter(x => x !== v); if (dfLeft === 'v:' + v.id) dfLeft = ''; if (dfRight === 'v:' + v.id) dfRight = 'current'; markDirty(); updateDraftBtn(); openDrafts(); } return; }
  if (a === 'copy') {
    const nd = newDoc(`${d.title || 'Untitled'} (${v.kind === 'draft' && v.n ? 'Draft ' + v.n : v.name})`, v.html);
    ['style', 'part', 'role'].forEach(k => { if (d[k] !== undefined) nd[k] = d[k]; });
    nd.layout = JSON.parse(JSON.stringify(d.layout)); nd.meta = Object.assign({}, d.meta);
    nd.comments = d.comments.filter(c => v.html.includes(c.id)).map(c => Object.assign({}, c));
    closeDrafts(); addDoc(nd); toast(`Copied “${v.name}” into a new document, next to the original.`); return;
  }
  if (a === 'restore') {
    if (!(await ask('Restore this draft?', `The document goes back to “${v.name}”. Your current text is kept as a safety copy first, so you can switch back.`, 'Restore draft'))) return;
    snapshot(d, `Before restoring “${v.name}”`, 'safety');
    d.html = v.html; editor.innerHTML = v.html; tidyTopLevel(); prepFigureDom(editor); hydrateImages(); renumberFigures(); lastSig = ''; renderRefs(true); updateWordCount(); renderOutline(); markDirty(); syncEditor();
    toast(`Restored “${v.name}”. The text you replaced is under Safety copies.`); renderDrafts();
  }
});

/* ---------- the comparison ---------- */
const dfWords = s => new Set((s.toLowerCase().match(/[\p{L}\p{N}’']+/gu) || []));
function dfSim(a, b) { const A = a.ws || (a.ws = dfWords(a.text)), B = b.ws || (b.ws = dfWords(b.text)); if (!A.size && !B.size) return 1; let i = 0; A.forEach(w => { if (B.has(w)) i++; }); return i / (A.size + B.size - i); }
function dfBlocks(html) {
  const t = document.createElement('div'); t.innerHTML = html || '';
  const out = [];
  [...t.children].forEach((el, idx) => {
    const c = el.cloneNode(true);
    $$('.cite', c).forEach(m => m.replaceWith('⟦cite⟧')); $$('.fn', c).forEach(m => m.replaceWith('⟦note⟧'));
    $$('.flag', c).forEach(m => m.replaceWith('⟦' + ((FLAG_KINDS[m.dataset.kind] || FLAG_KINDS.tk).label) + '⟧'));
    $$('.cmt-pt,.ix-a,a.mg-a', c).forEach(m => m.remove());
    let text = c.textContent.replace(/\s+/g, ' ').trim();
    if (el.matches('figure.fig')) { const img = el.querySelector('img'); text = `⟦image ${img ? img.dataset.asset : ''}⟧ ${text}`; }
    else if (el.matches('figure.tbl')) text = '⟦table⟧ ' + text;
    if (!text) return;
    out.push({ idx, tag: el.nodeName, html: el.outerHTML, text });
  });
  return out;
}
function dfAlign(A, B) {
  const rows = []; let ia = 0, ib = 0, R = [], D = [];
  const flush = () => {
    let j = 0;
    R.forEach(r => {
      let best = -1, bs = 0.34;
      for (let k = j; k < Math.min(D.length, j + 15); k++) { const s = dfSim(r, D[k]); if (s > bs) { bs = s; best = k; } }
      if (best < 0) { rows.push({ t: 'del', a: r }); return; }
      for (; j < best; j++) rows.push({ t: 'add', b: D[j] });
      rows.push({ t: 'chg', a: r, b: D[best] }); j = best + 1;
    });
    for (; j < D.length; j++) rows.push({ t: 'add', b: D[j] });
    R = []; D = [];
  };
  Diff.diffArrays(A.map(x => x.text), B.map(x => x.text)).forEach(p => {
    const n = p.count ?? p.value.length;
    if (p.removed) { for (let k = 0; k < n; k++) R.push(A[ia++]); return; }
    if (p.added) { for (let k = 0; k < n; k++) D.push(B[ib++]); return; }
    flush(); for (let k = 0; k < n; k++) rows.push({ t: 'same', a: A[ia++], b: B[ib++] });
  });
  flush();
  const adds = rows.filter(r => r.t === 'add');
  rows.filter(r => r.t === 'del').forEach(dl => { const m = adds.find(a => a.t === 'add' && dfSim(dl.a, a.b) >= 0.85); if (m) { dl.t = 'movefrom'; m.t = 'moveto'; dl.pair = m; m.pair = dl; } });
  return rows;
}
const dfWc = s => (s.replace(/⟦[^⟧]*⟧/g, ' ').match(/[\p{L}\p{N}’'-]+/gu) || []).length;
function dfCompute() {
  const L = dfSource(dfLeft), R = dfSource(dfRight);
  $('#dfLH').textContent = L ? L.name : ''; $('#dfRH').textContent = R ? R.name : '';
  if (!L || !R) { dfRows = []; $('#dfSum').innerHTML = ''; $('#dfGrid').innerHTML = `<div class="df-pickfirst">${curDoc().snapshots.length ? 'Choose a draft on the left to compare.' : 'Save a draft now. Later, compare it side by side with how the document has changed.'}</div>`; dfNav(); return; }
  if (L.key === R.key) { dfRows = []; $('#dfSum').innerHTML = ''; $('#dfGrid').innerHTML = '<div class="df-pickfirst">Both sides show the same text. Pick something different on one side.</div>'; dfNav(); return; }
  dfRows = dfAlign(dfBlocks(L.html), dfBlocks(R.html));
  let add = 0, del = 0; const n = { chg: 0, add: 0, del: 0, move: 0 };
  dfRows.forEach(r => {
    if (r.t === 'chg') { n.chg++; r.parts = Diff.diffWords(r.a.text, r.b.text); r.parts.forEach(p => { if (p.added) add += dfWc(p.value); else if (p.removed) del += dfWc(p.value); }); }
    if (r.t === 'add') { n.add++; add += dfWc(r.b.text); }
    if (r.t === 'del') { n.del++; del += dfWc(r.a.text); }
    if (r.t === 'movefrom') n.move++;
  });
  const net = R.words - L.words;
  const bits = [n.chg && `${n.chg} rewritten`, n.add && `${n.add} new`, n.del && `${n.del} cut`, n.move && `${n.move} moved`].filter(Boolean);
  $('#dfSum').innerHTML = bits.length && !add && !del
    ? `<span>No words changed.</span><span class="df-s-paras">Paragraphs: ${bits.join(', ')}</span>`
    : bits.length
    ? `<span class="df-s-add">+${add.toLocaleString()}</span> <span class="df-s-del">−${del.toLocaleString()}</span> words <span class="muted">(${net >= 0 ? '+' : '−'}${Math.abs(net).toLocaleString()} net: ${L.words.toLocaleString()} → ${R.words.toLocaleString()})</span><span class="df-s-paras">Paragraphs: ${bits.join(', ')}</span>`
    : '<span>No differences in the text.</span>';
  dfRender();
}
function dfCanTake() { return dfRight === 'current' && !String(dfLeft).startsWith('doc:'); }
function dfClean(html) {
  const t = document.createElement('div'); t.innerHTML = html;
  $$('[contenteditable]', t).forEach(x => x.removeAttribute('contenteditable'));
  $$('.cmt', t).forEach(c => c.replaceWith(...c.childNodes)); $$('.ix-a,a.mg-a', t).forEach(x => x.remove());
  return t.innerHTML;
}
const dfTok = s => esc(s).replace(/⟦image [^⟧]*⟧/g, '<span class="df-tok">image</span>').replace(/⟦([^⟧]+)⟧/g, '<span class="df-tok">$1</span>');
function dfDiffSide(parts, side) {
  return parts.map(p => { if (p.added) return side === 'r' ? `<ins>${dfTok(p.value)}</ins>` : ''; if (p.removed) return side === 'l' ? `<del>${dfTok(p.value)}</del>` : ''; return dfTok(p.value); }).join('');
}
const dfTagCls = b => 'df-' + b.tag.toLowerCase();
function dfRowHTML(r, k) {
  const take = dfCanTake(), L = esc(dfSource(dfLeft)?.short || ''), Rn = esc(dfSource(dfRight)?.short || '');
  const btn = (label, title) => take ? `<button class="df-take small" data-take="${k}" title="${title}">${label}</button>` : '';
  const gap = (msg, jump) => `<div class="df-gap">${msg}${jump !== undefined ? ` <button class="ghost small df-jump" data-jump="${jump}">Show</button>` : ''}</div>`;
  const wrapText = (b, inner) => `<div class="df-b ${dfTagCls(b)}">${inner}</div>`;
  switch (r.t) {
    case 'same': return `<div class="df-row same" data-k="${k}"><div class="df-c l" data-side="${L}">${dfClean(r.a.html)}</div><div class="df-c r" data-side="${Rn}">${dfClean(r.b.html)}</div></div>`;
    case 'chg': return `<div class="df-row chg" data-k="${k}"><div class="df-c l" data-side="${L}"><span class="df-tag">Rewritten</span>${wrapText(r.a, dfDiffSide(r.parts, 'l'))}${btn('Use this version', 'Replace the paragraph in your current text with this one')}</div><div class="df-c r" data-side="${Rn}">${wrapText(r.b, dfDiffSide(r.parts, 'r'))}</div></div>`;
    case 'del': return `<div class="df-row del" data-k="${k}"><div class="df-c l" data-side="${L}"><span class="df-tag">Cut</span>${dfClean(r.a.html)}${btn('Put it back', 'Add this paragraph back to your current text, in this position')}</div><div class="df-c r" data-side="${Rn}">${gap('Not in this version.')}</div></div>`;
    case 'add': return `<div class="df-row add" data-k="${k}"><div class="df-c l" data-side="${L}">${gap('Not in this version.')}</div><div class="df-c r" data-side="${Rn}"><span class="df-tag">New</span>${dfClean(r.b.html)}${take ? `<button class="df-take small" data-take="${k}" title="Remove this paragraph from your current text">Remove it</button>` : ''}</div></div>`;
    case 'movefrom': return `<div class="df-row move" data-k="${k}"><div class="df-c l" data-side="${L}"><span class="df-tag">Moved</span>${dfClean(r.a.html)}</div><div class="df-c r" data-side="${Rn}">${gap('Moved further down.', dfRows.indexOf(r.pair))}</div></div>`;
    case 'moveto': return `<div class="df-row move" data-k="${k}"><div class="df-c l" data-side="${L}">${gap('Moved here from further up.', dfRows.indexOf(r.pair))}</div><div class="df-c r" data-side="${Rn}"><span class="df-tag">Moved</span>${dfClean(r.b.html)}</div></div>`;
  }
  return '';
}
function dfRender() {
  const all = $('#dfAll').checked; let html = '', i = 0;
  while (i < dfRows.length) {
    if (dfRows[i].t === 'same' && !all) {
      let j = i; while (j < dfRows.length && dfRows[j].t === 'same') j++;
      const head = i > 0 ? 1 : 0, tail = j < dfRows.length ? 1 : 0, hidden = j - i - head - tail;
      if (hidden > 1) {
        for (let k = i; k < i + head; k++) html += dfRowHTML(dfRows[k], k);
        html += `<button class="df-fold" data-a="${i + head}" data-b="${j - tail}">${hidden} unchanged paragraph${hidden === 1 ? '' : 's'}</button>`;
        for (let k = j - tail; k < j; k++) html += dfRowHTML(dfRows[k], k);
        i = j; continue;
      }
    }
    html += dfRowHTML(dfRows[i], i); i++;
  }
  $('#dfGrid').innerHTML = html || (dfRows.length ? '' : $('#dfGrid').innerHTML);
  hydrateImages($('#dfGrid'));
  dfPos = -1; dfNav();
}
function dfChanges() { return $$('#dfGrid .df-row:not(.same)'); }
function dfNav() { const c = dfChanges(); $('#dfPos').textContent = c.length ? (dfPos >= 0 ? `${dfPos + 1} of ${c.length}` : `${c.length} change${c.length === 1 ? '' : 's'}`) : ''; $('#dfPrev').disabled = $('#dfNext').disabled = !c.length; }
function dfGo(step) {
  const c = dfChanges(); if (!c.length) return;
  dfPos = dfPos < 0 ? (step > 0 ? 0 : c.length - 1) : (dfPos + step + c.length) % c.length;
  const el = c[dfPos]; el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  c.forEach(x => x.classList.remove('df-here')); el.classList.add('df-here'); dfNav();
}
$('#dfNext').addEventListener('click', () => dfGo(1));
$('#dfPrev').addEventListener('click', () => dfGo(-1));
document.addEventListener('keydown', e => {
  if (!draftsOn || e.target.closest('input,textarea,select,[contenteditable="true"]') || $$('dialog[open]').length || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === 'j' || e.key === 'ArrowDown' && e.shiftKey) { e.preventDefault(); dfGo(1); }
  if (e.key === 'k' || e.key === 'ArrowUp' && e.shiftKey) { e.preventDefault(); dfGo(-1); }
});
$('#dfGrid').addEventListener('click', e => {
  const f = e.target.closest('.df-fold');
  if (f) { const a = +f.dataset.a, b = +f.dataset.b; let h = ''; for (let k = a; k < b; k++) h += dfRowHTML(dfRows[k], k); f.insertAdjacentHTML('afterend', h); const nx = f.nextElementSibling; f.remove(); hydrateImages($('#dfGrid')); if (nx) nx.scrollIntoView({ block: 'nearest' }); dfNav(); return; }
  const j = e.target.closest('[data-jump]');
  if (j) { const el = $(`#dfGrid .df-row[data-k="${j.dataset.jump}"]`); if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); el.classList.add('df-here'); setTimeout(() => el.classList.remove('df-here'), 1600); } return; }
  const t = e.target.closest('[data-take]'); if (t) dfTake(+t.dataset.take);
});
function dfTake(k) {
  const r = dfRows[k], d = curDoc(), L = dfSource(dfLeft); if (!r || !dfCanTake()) return;
  if (d.id !== curDocId) return;
  syncEditor();
  if (!dfTook) { snapshot(d, `Before bringing back text from “${L.name}”`, 'safety'); dfTook = true; }
  const kids = [...editor.children];
  const frag = h => { const t = document.createElement('template'); t.innerHTML = h; return t.content; };
  let msg = '';
  if (r.t === 'chg') { kids[r.b.idx].replaceWith(frag(r.a.html)); msg = 'Paragraph replaced with the version from ' + L.short + '.'; }
  else if (r.t === 'del') {
    let prev = null; for (let q = k - 1; q >= 0; q--) if (dfRows[q].b) { prev = kids[dfRows[q].b.idx]; break; }
    const f = frag(r.a.html); if (prev) prev.after(f); else editor.prepend(f); msg = 'Paragraph put back.';
  } else if (r.t === 'add') { kids[r.b.idx].remove(); msg = 'Paragraph removed from your current text.'; }
  else return;
  tidyTopLevel(); prepFigureDom(editor); hydrateImages(); renumberFigures();
  $$('.cite,.fn,.flag', editor).forEach(m => m.setAttribute('contenteditable', 'false'));
  lastSig = ''; renderRefs(true); updateWordCount(); syncEditor(); markDirty();
  const y = $('#dfGrid').scrollTop; dfCompute(); $('#dfGrid').scrollTop = y;
  const doc = curDoc(); $('.df-cur .df-meta') && ($('.df-cur .df-meta').textContent = `${wc(docPlain(doc.html)).toLocaleString()} words · edited just now`);
  toast(msg + ' A safety copy from before your first change is in the list.');
}
$('#dfDl').addEventListener('click', () => {
  const L = dfSource(dfLeft), R = dfSource(dfRight), d = curDoc(); if (!L || !R || !dfRows.length) { toast('Pick two versions to compare first.'); return; }
  const body = dfRows.map((r, k) => dfRowHTML(r, k)).join('').replace(/<button[^>]*>[\s\S]*?<\/button>/g, '');
  const holder = document.createElement('div'); holder.innerHTML = body; hydrateImages(holder);
  $$('img[data-asset]', holder).forEach(img => { const a = P.assets[img.dataset.asset]; if (a) img.src = a.data; });
  const css = `body{font:15px/1.55 Georgia,serif;color:#16202c;margin:0;background:#fff}header{padding:24px 32px 12px;border-bottom:1px solid #ccd}h1{font:700 20px/1.3 system-ui,sans-serif;margin:0 0 6px}.sum{font:13px/1.5 system-ui,sans-serif;color:#4a5763}.cols{display:grid;grid-template-columns:1fr 1fr;gap:0 28px;padding:10px 32px;font:700 13px system-ui,sans-serif;position:sticky;top:0;background:#fff;border-bottom:1px solid #ccd}.df-row{display:grid;grid-template-columns:1fr 1fr;gap:0 28px;padding:6px 32px;border-left:4px solid transparent;break-inside:avoid}.df-row.same{color:#555}.df-row.chg{border-left-color:#b5841f}.df-row.add{border-left-color:#2e7d4f}.df-row.del{border-left-color:#a3271b}.df-row.move{border-left-color:#24456e}.df-c p,.df-c h1,.df-c h2,.df-c h3,.df-c blockquote{margin:.3em 0}.df-tag{font:700 11px system-ui,sans-serif;color:#4a5763;display:block}.df-gap{font:italic 13px system-ui,sans-serif;color:#7a8590;padding:.4em 0}ins{background:#d5ead7;text-decoration:none}del{background:#f5d6d1}.df-tok{font:11px system-ui,sans-serif;border:1px solid #bbb;border-radius:3px;padding:0 3px}img{max-width:100%}figure{margin:.5em 0}table{border-collapse:collapse}td,th{border:1px solid #999;padding:2px 5px}`;
  const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${esc(d.title)}: ${esc(L.name)} compared with ${esc(R.name)}</title><style>${css}</style></head><body><header><h1>${esc(d.title)}</h1><div class="sum">${$('#dfSum').innerHTML}</div></header><div class="cols"><div>${esc(L.name)} (${dfWhen(L.date)})</div><div>${esc(R.name)} (${dfWhen(R.date || nowISO())})</div></div>${holder.innerHTML}</body></html>`;
  download(fileSafe(`${d.title} - ${L.short} vs ${R.short}`) + '.html', html, 'text/html');
});

/* ---------- ePub 3 export ---------- */
const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
function zipStore(files) { // stored (uncompressed) zip; mimetype must come first for ePub
  const enc = new TextEncoder(), parts = [], central = []; let off = 0;
  files.forEach(f => {
    const name = enc.encode(f.name), data = typeof f.data === 'string' ? enc.encode(f.data) : f.data, crc = crc32(data);
    const h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true); h.setUint32(14, crc, true);
    h.setUint32(18, data.length, true); h.setUint32(22, data.length, true); h.setUint16(26, name.length, true);
    parts.push(new Uint8Array(h.buffer), name, data);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint32(16, crc, true);
    c.setUint32(20, data.length, true); c.setUint32(24, data.length, true); c.setUint16(28, name.length, true); c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), name);
    off += 30 + name.length + data.length;
  });
  const csize = central.reduce((n, p) => n + p.length, 0), e = new DataView(new ArrayBuffer(22));
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, csize, true); e.setUint32(16, off, true);
  return new Blob([...parts, ...central, new Uint8Array(e.buffer)], { type: 'application/epub+zip' });
}
function toXhtml(html) {
  const d = new DOMParser().parseFromString('<!DOCTYPE html><html><body>' + html + '</body></html>', 'text/html');
  $$('script,style', d).forEach(x => x.remove());
  return [...d.body.childNodes].map(n => n.nodeType === 1 ? new XMLSerializer().serializeToString(n) : esc(n.textContent)).join('').replace(/ xmlns="http:\/\/www\.w3\.org\/1999\/xhtml"/g, '');
}
const xpage = (title, body, cls = '') => `<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en"><head><meta charset="UTF-8"/><title>${esc(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body class="${cls}">${body}</body></html>`;
async function exportEpub(doc) {
  if (!doc) return;
  const x = buildExport(doc, 'epub');
  // split into chapters at top-level h1s that start chapters/parts (or keep one file)
  const box = document.createElement('div'); box.innerHTML = x.body;
  const chunks = []; let cur = null;
  [...box.childNodes].forEach(n => {
    if (n.nodeType === 1 && n.matches('nav.toc')) return;
    const isHead = n.nodeType === 1 && n.matches('h1.chapter-title,h1.part-title,nav.toc,div.ch-break');
    if (!cur || (isHead && cur.html.trim())) { cur = { title: '', html: '' }; chunks.push(cur); }
    if (n.nodeType === 1 && n.matches('div.ch-break')) return;
    if (!cur.title && n.nodeType === 1 && /^H[12]$/.test(n.nodeName)) cur.title = n.textContent.trim();
    cur.html += n.nodeType === 1 ? n.outerHTML : esc(n.textContent);
  });
  if (!chunks.length) chunks.push({ title: doc.title, html: '<p></p>' });
  const imgs = epubImages(chunks.map(c => c.html)); chunks.forEach((c, i) => { c.html = imgs.chunks[i]; });
  const files = chunks.map((c, i) => ({ id: 'c' + (i + 1), file: `c${i + 1}.xhtml`, title: c.title || (i === 0 ? doc.title : 'Section ' + (i + 1)), html: c.html }));
  const refFile = {};
  files.forEach(f => (f.html.match(/data-n="(\d+)"/g) || []).forEach(m => refFile[m.slice(8, -1)] = f.file));
  files.forEach(f => {
    f.html = f.html.replace(/<a class="noteref" data-n="(\d+)" id="r\d+">/g, (m, n) => `<a class="noteref" epub:type="noteref" href="notes.xhtml#n${n}" id="r${n}">`);
    f.html = f.html.replace(/<nav class="toc[^"]*">[\s\S]*?<\/nav>/, '');
  });
  const notesPage = x.out.notes.length ? `<section epub:type="endnotes"><h1>Notes</h1>${x.out.notes.map(n => `<aside epub:type="footnote" id="n${n.n}"><p><a href="${refFile[n.n] || files[0].file}#r${n.n}">${n.n}.</a> ${n.html}</p></aside>`).join('')}</section>` : '';
  const ixFile = {}; files.forEach(f => (f.html.match(/id="ix\d+"/g) || []).forEach(m => ixFile[m.slice(4, -1)] = f.file));
  const ixPage = x.index ? x.index.replace(/href="#(ix\d+)"/g, (m, id) => `href="${ixFile[id] || files[0].file}#${id}"`).replace(/<section class="end-sec index">/, '<section epub:type="index">').replace(/<h2 class="end-h">/, '<h1>').replace(/<\/h2>/, '</h1>') : '';
  const bibPage = x.out.bib ? `<section epub:type="bibliography"><h1>${esc(x.out.heading)}</h1><div class="csl-bib${x.out.bib.hanging ? ' hanging' : ''}">${x.out.bib.entries.join('')}</div></section>` : '';
  const m = doc.meta, uuid = 'urn:uuid:' + ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  const titlePage = `<section epub:type="titlepage" class="titlepage"><h1>${esc(doc.title)}</h1>${m.subtitle ? `<p class="sub">${esc(m.subtitle)}</p>` : ''}${m.author ? `<p class="author">${esc(m.author)}</p>` : ''}</section>`;
  const all = [{ id: 'title', file: 'title.xhtml', title: doc.title, html: titlePage }, ...files];
  if (notesPage) all.push({ id: 'notes', file: 'notes.xhtml', title: 'Notes', html: notesPage, raw: true });
  if (bibPage) all.push({ id: 'bib', file: 'bib.xhtml', title: x.out.heading, html: bibPage, raw: true });
  if (ixPage) all.push({ id: 'index', file: 'index.xhtml', title: 'Index', html: ixPage, raw: true });
  if (x.marginalia) all.push({ id: 'marginalia', file: 'marginalia.xhtml', title: 'Marginalia', html: x.marginalia.replace(/<h2 class="end-h">/, '<h1>').replace(/<\/h2>/, '</h1>'), raw: true });
  const css = `body{font-family:Georgia,serif;line-height:1.5;margin:0 5%}h1,h2,h3{line-height:1.25;page-break-after:avoid}h1.part-title{text-align:center;margin-top:30%}p{margin:0 0 .6em;text-indent:0}blockquote{margin:0 0 .8em 1.5em}sup{font-size:.7em;line-height:0}a.noteref{text-decoration:none}aside{margin:0 0 .6em}.csl-entry{margin:0 0 .5em}.hanging .csl-entry{padding-left:1.5em;text-indent:-1.5em}.titlepage{text-align:center;margin-top:30%}.titlepage .author{margin-top:2em}mark{background:#fde68a}`;
  const opf = `<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">${uuid}</dc:identifier><dc:title>${esc(doc.title)}</dc:title>${m.author ? `<dc:creator>${esc(m.author)}</dc:creator>` : ''}<dc:language>en</dc:language><meta property="dcterms:modified">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</meta></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/><item id="css" href="style.css" media-type="text/css"/>${all.map(f => `<item id="${f.id}" href="${f.file}" media-type="application/xhtml+xml"/>`).join('')}${imgs.files.map(f => `<item id="${f.id}" href="${f.name}" media-type="${f.mime}"/>`).join('')}</manifest>
<spine toc="ncx">${all.map(f => `<itemref idref="${f.id}"/>`).join('')}</spine></package>`;
  const nav = xpage('Contents', `<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>${all.map(f => `<li><a href="${f.file}">${esc(f.title)}</a></li>`).join('')}</ol></nav>`);
  const ncx = `<?xml version="1.0" encoding="UTF-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="${uuid}"/></head><docTitle><text>${esc(doc.title)}</text></docTitle><navMap>${all.map((f, i) => `<navPoint id="p${i + 1}" playOrder="${i + 1}"><navLabel><text>${esc(f.title)}</text></navLabel><content src="${f.file}"/></navPoint>`).join('')}</navMap></ncx>`;
  const zfiles = [
    { name: 'mimetype', data: 'application/epub+zip' },
    { name: 'META-INF/container.xml', data: '<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>' },
    { name: 'OEBPS/content.opf', data: opf }, { name: 'OEBPS/nav.xhtml', data: nav }, { name: 'OEBPS/toc.ncx', data: ncx }, { name: 'OEBPS/style.css', data: css },
    ...all.map(f => ({ name: 'OEBPS/' + f.file, data: xpage(f.title, toXhtml(f.html)) })),
    ...imgs.files.map(f => ({ name: 'OEBPS/' + f.name, data: f.bytes })),
  ];
  download(fileSafe(doc.title) + '.epub', zipStore(zfiles), 'application/epub+zip');
  toast('ePub saved. It opens in Apple Books, Kobo, Calibre and most e-readers' + (x.out.notes.length ? ', with tappable notes.' : '.'));
}

/* ---------- BibTeX & RIS import ---------- */
const RIS_TYPES = { JOUR: 'article-journal', JFULL: 'article-journal', EJOUR: 'article-journal', BOOK: 'book', EBOOK: 'book', CHAP: 'chapter', ECHAP: 'chapter', NEWS: 'article-newspaper', MGZN: 'article-magazine', ELEC: 'webpage', WEB: 'webpage', BLOG: 'post-weblog', RPRT: 'report', GOVDOC: 'report', THES: 'thesis', CONF: 'report', CPAPER: 'report', VIDEO: 'motion_picture', MPCT: 'motion_picture', SOUND: 'broadcast', INTV: 'interview', DATA: 'dataset', MAP: 'map', MANSCPT: 'manuscript', UNPB: 'manuscript', STAT: 'legislation', BILL: 'legislation', PCOMM: 'personal_communication', ENCYC: 'entry-encyclopedia', DICT: 'entry-encyclopedia', GEN: 'document' };
function risDate(v) { const m = String(v || '').match(/^(\d{4})(?:\/(\d{1,2})?(?:\/(\d{1,2})?)?)?/); if (!m) return parseDate(v); return { 'date-parts': [[+m[1], ...(m[2] ? [+m[2]] : []), ...(m[2] && m[3] ? [+m[3]] : [])]] }; }
function parseRIS(text) {
  const out = []; let cur = null;
  text.split(/\r?\n/).forEach(line => {
    const m = line.match(/^([A-Z][A-Z0-9])  -\s?(.*)$/); if (!m) return;
    const [, tag, val] = m, v = val.trim();
    if (tag === 'TY') { cur = { type: RIS_TYPES[v] || 'document', _au: [], _ed: [] }; return; }
    if (!cur) return;
    if (tag === 'ER') { out.push(cur); cur = null; return; }
    const set = (k, x) => { if (x && !cur[k]) cur[k] = x; };
    if (/^(AU|A1)$/.test(tag)) cur._au.push(v); else if (/^(A2|ED|A3)$/.test(tag)) cur._ed.push(v);
    else if (/^(TI|T1|CT)$/.test(tag)) set('title', v); else if (/^(JO|JF|JA|T2|BT|SE)$/.test(tag)) set('container-title', v);
    else if (/^(PY|Y1|DA)$/.test(tag)) { if (!cur.issued || tag === 'DA') cur.issued = risDate(v); }
    else if (tag === 'VL') set('volume', v); else if (tag === 'IS') set('issue', v); else if (tag === 'SP') cur._sp = v; else if (tag === 'EP') cur._ep = v;
    else if (tag === 'PB') set('publisher', v); else if (tag === 'CY') set('publisher-place', v); else if (tag === 'UR') set('URL', v);
    else if (tag === 'DO') set('DOI', v.replace(/^https?:\/\/(dx\.)?doi\.org\//, '')); else if (tag === 'SN' && /^[\dXx-]{10,17}$/.test(v)) set('ISBN', v);
    else if (tag === 'ET') set('edition', v); else if (tag === 'Y2') cur.accessed = risDate(v); else if (tag === 'M3') set('genre', v);
  });
  return out.map(c => { const o = Object.assign({}, c); delete o._au; delete o._ed; delete o._sp; delete o._ep;
    if (c._au.length) o.author = c._au.map(splitName).filter(Boolean); if (c._ed.length) o.editor = c._ed.map(splitName).filter(Boolean);
    if (c._sp) o.page = c._sp + (c._ep && c._ep !== c._sp ? '–' + c._ep : ''); return o; });
}
const TEX = { "\\'": { a: 'á', e: 'é', i: 'í', o: 'ó', u: 'ú', c: 'ć', n: 'ń', s: 'ś', z: 'ź', E: 'É', A: 'Á' }, '\\`': { a: 'à', e: 'è', i: 'ì', o: 'ò', u: 'ù' }, '\\"': { a: 'ä', o: 'ö', u: 'ü', e: 'ë', i: 'ï', A: 'Ä', O: 'Ö', U: 'Ü' }, '\\^': { a: 'â', e: 'ê', i: 'î', o: 'ô', u: 'û' }, '\\~': { n: 'ñ', a: 'ã', o: 'õ', N: 'Ñ' }, '\\c': { c: 'ç', C: 'Ç' }, '\\v': { s: 'š', c: 'č', z: 'ž', r: 'ř', e: 'ě', S: 'Š', C: 'Č', Z: 'Ž' } };
function texClean(s) {
  s = String(s || '');
  s = s.replace(/\{?\\([`'"^~cv])\s*\{?\\?([A-Za-z])\}?\}?/g, (m, a, l) => (TEX['\\' + a] && TEX['\\' + a][l]) || l);
  s = s.replace(/\\ss\b/g, 'ß').replace(/\\o\b/g, 'ø').replace(/\\&/g, '&').replace(/\\%/g, '%').replace(/\\_/g, '_').replace(/\\textendash\b|--/g, '–').replace(/\\textemdash\b|---/g, '—');
  s = s.replace(/\\(emph|textit|textbf|textsc)\{([^}]*)\}/g, '$2').replace(/[{}]/g, '').replace(/~/g, ' ');
  return s.replace(/\s+/g, ' ').trim();
}
const BIB_TYPES = { article: 'article-journal', book: 'book', inbook: 'chapter', incollection: 'chapter', inproceedings: 'report', conference: 'report', techreport: 'report', report: 'report', phdthesis: 'thesis', mastersthesis: 'thesis', thesis: 'thesis', online: 'webpage', electronic: 'webpage', www: 'webpage', unpublished: 'manuscript', manual: 'document', misc: 'document', booklet: 'book', proceedings: 'book', dataset: 'dataset', video: 'motion_picture', movie: 'motion_picture', newsarticle: 'article-newspaper' };
function parseBibTeX(text) {
  const out = []; let i = 0;
  while ((i = text.indexOf('@', i)) !== -1) {
    const m = text.slice(i).match(/^@(\w+)\s*[{(]/); if (!m) { i++; continue; }
    const kind = m[1].toLowerCase(); i += m[0].length;
    if (/^(comment|preamble|string)$/.test(kind)) { let depth = 1; while (i < text.length && depth) { if (text[i] === '{') depth++; else if (text[i] === '}') depth--; i++; } continue; }
    const comma = text.indexOf(',', i); if (comma < 0) break; i = comma + 1;
    const f = {};
    while (i < text.length) {
      const km = text.slice(i).match(/^\s*([\w-]+)\s*=\s*/); if (!km) { const end = text.slice(i).match(/^\s*[})]/); if (end) i += end[0].length; break; }
      const key = km[1].toLowerCase(); i += km[0].length;
      let val = '';
      if (text[i] === '{') { let depth = 0, st = i; do { if (text[i] === '{') depth++; else if (text[i] === '}') depth--; i++; } while (i < text.length && depth); val = text.slice(st + 1, i - 1); }
      else if (text[i] === '"') { const st = ++i; while (i < text.length && !(text[i] === '"' && text[i - 1] !== '\\')) i++; val = text.slice(st, i); i++; }
      else { const vm = text.slice(i).match(/^[^,})\s]+/); val = vm ? vm[0] : ''; i += val.length; }
      f[key] = val;
      const sep = text.slice(i).match(/^\s*,?/); i += sep[0].length;
    }
    const names = v => String(v || '').split(/\s+and\s+/i).map(n => n.trim()).filter(Boolean).map(n => /^\{.*\}$/.test(n) ? { literal: texClean(n) } : splitName(texClean(n))).filter(Boolean);
    let type = BIB_TYPES[kind] || 'document'; if (kind === 'misc' && f.url && !f.publisher) type = 'webpage';
    const o = { type };
    const set = (k, v) => { v = texClean(v); if (v) o[k] = v; };
    set('title', f.title); set('container-title', f.journal || f.journaltitle || f.booktitle || f.howpublished && !/^\\url/.test(f.howpublished) && f.howpublished);
    set('publisher', f.publisher || f.institution || f.school || f.organization); set('publisher-place', f.address || f.location);
    set('volume', f.volume); set('issue', f.number || f.issue); set('edition', f.edition); set('collection-title', f.series); set('genre', f.type);
    if (f.pages) o.page = texClean(f.pages).replace(/\s*-+\s*/g, '–');
    if (f.doi) o.DOI = texClean(f.doi).replace(/^https?:\/\/(dx\.)?doi\.org\//, '');
    if (f.url) o.URL = f.url.trim(); if (f.isbn) o.ISBN = texClean(f.isbn);
    const date = texClean(f.date || ''); const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
    if (date) o.issued = parseDate(date); else if (f.year) { const mo = months[String(f.month || '').toLowerCase().slice(0, 3)] || parseInt(f.month, 10); o.issued = { 'date-parts': [[parseInt(texClean(f.year), 10), ...(mo ? [mo] : [])]] }; }
    if (f.urldate) o.accessed = parseDate(texClean(f.urldate));
    if (f.author) o.author = names(f.author); if (f.editor) o.editor = names(f.editor); if (f.translator) o.translator = names(f.translator);
    if (o.title || o.author) out.push(o);
  }
  return out;
}
function importBibRis(text, name) {
  const items = /^\s*TY  - /m.test(text) ? parseRIS(text) : parseBibTeX(text);
  if (!items.length) { toast('No references found in that file.'); return; }
  items.forEach(o => P.sources.push({ id: uid('s'), csl: o, created: nowISO(), modified: nowISO() }));
  srcVersion++; renderSourceList(); markDirty(); switchTab('sources');
  toast(`Imported ${items.length} reference${items.length > 1 ? 's' : ''} from ${name}. Check titles and names; database exports vary.`);
}

/* ---------- quote integrity ---------- */
const normQ = s => String(s || '').replace(/[“”„"‘’']/g, "'").replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim().toLowerCase();
const plainMd = s => stripWikiLinks(s).replace(/^\s*>\s?/gm, '').replace(/[*_`#]/g, '').replace(/^[“"]|[”"]$/g, '');
function quoteStatus(el) {
  const n = P.notes.find(x => x.id === el.dataset.qn);
  if (!n) return { state: 'orphan' };
  const orig = normQ(plainMd(n.body));
  const c = el.cloneNode(true); $$('.cite,.fn,.flag', c).forEach(m => m.remove());
  const cur = normQ(c.textContent).replace(/^"|"$/g, '');
  if (!cur) return { state: 'changed', n, cur, orig };
  if (orig.includes(cur)) return { state: 'ok', n };
  const pat = cur.split(/(\s*(?:\.\s?\.\s?\.|…)\s*|\[[^\]]*\])/).map((part, i) => i % 2 ? (part.trim().startsWith('[') ? '.{0,80}?' : '.*?') : escRe(part)).join('');
  try { if (new RegExp(pat).test(orig)) return { state: 'edited', n }; } catch (e) {}
  return { state: 'changed', n, cur, orig };
}
function quoteDiffHTML(n, el) {
  const c = el.cloneNode(true); $$('.cite,.fn,.flag', c).forEach(m => m.remove());
  return Diff.diffWords(plainMd(n.body).replace(/\s+/g, ' ').trim(), c.textContent.replace(/\s+/g, ' ').trim()).map(p => p.added ? `<ins>${esc(p.value)}</ins>` : p.removed ? `<del>${esc(p.value)}</del>` : esc(p.value)).join('');
}
function unlinkedQuotes() {
  const out = [];
  $$(':scope > p, :scope > li, :scope > ul > li, :scope > ol > li', editor).forEach(p => {
    const c = p.cloneNode(true); $$('.qlink,.cite,.fn,.flag', c).forEach(m => m.remove());
    (c.textContent.match(/“[^”]{60,}”/g) || []).forEach(q => { if (wc(q) >= 12) out.push({ el: p, q }); });
  });
  return out;
}

/* ---------- names & spellings ---------- */
function nameIssues() {
  const issues = [];
  if (!P.entities.length) return issues;
  const nodes = textNodesIn(editor);
  P.entities.forEach(e => e.variants.forEach(v => {
    v = v.trim(); if (!v || v === e.name) return;
    const re = new RegExp('(^|[^\\p{L}\\p{N}])(' + escRe(v) + ')(?![\\p{L}\\p{N}])', 'gu'), ranges = [];
    nodes.forEach(tn => { let m; re.lastIndex = 0; while ((m = re.exec(tn.data))) { const st = m.index + m[1].length; const r = document.createRange(); r.setStart(tn, st); r.setEnd(tn, st + m[2].length); ranges.push(r); } });
    if (ranges.length) issues.push({ e, v, ranges });
  }));
  return issues;
}
function lev(a, b, max = 3) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) { const cur = [i]; let best = i; for (let j = 1; j <= b.length; j++) { cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); best = Math.min(best, cur[j]); } if (best > max) return max + 1; prev = cur; }
  return prev[b.length];
}
function spellingSuggestions() {
  syncEditor();
  const counts = new Map();
  const text = P.docs.map(d => htmlToText(d.html)).join(' ') + ' ' + P.notes.map(n => n.title + ' ' + n.body).join(' ');
  (text.match(/\b[A-Z][\p{Ll}'’-]{4,}\b/gu) || []).forEach(w => counts.set(w, (counts.get(w) || 0) + 1));
  const known = new Set(P.entities.flatMap(e => [e.name, ...e.variants]));
  const words = [...counts.keys()].filter(w => !known.has(w));
  const out = [], seen = new Set();
  for (let i = 0; i < words.length; i++) for (let j = i + 1; j < words.length; j++) {
    const a = words[i], b = words[j]; if (a[0] !== b[0]) continue;
    const base = x => x.replace(/(['’]s|s|es)$/, '');
    if (base(a) === base(b) || a.startsWith(b) || b.startsWith(a)) continue;
    const d = lev(a.toLowerCase(), b.toLowerCase(), 2);
    if (d <= (Math.min(a.length, b.length) >= 8 ? 2 : 1)) {
      const [keep, alt] = counts.get(a) >= counts.get(b) ? [a, b] : [b, a];
      const k = keep + '|' + alt; if (seen.has(k)) continue; seen.add(k);
      out.push({ keep, alt, nk: counts.get(keep), na: counts.get(alt) });
    }
  }
  return out.sort((x, y) => (y.nk + y.na) - (x.nk + x.na)).slice(0, 25);
}
function openNames() { renderNames(); $('#namesDlg').showModal(); }
function renderNames() {
  const kinds = ['person', 'organization', 'place', 'term'];
  $('#namesList').innerHTML = P.entities.length ? P.entities.map(e => `<div class="ent" data-e="${e.id}">
      <input data-k="name" value="${esc(e.name)}" placeholder="Preferred spelling"><select data-k="kind">${kinds.map(k => `<option ${k === e.kind ? 'selected' : ''}>${k}</option>`).join('')}</select>
      <input data-k="variants" value="${esc(e.variants.join(', '))}" placeholder="Spellings to flag (comma-separated)"><input data-k="note" value="${esc(e.note)}" placeholder="Role, title, or note"><button class="ghost danger" data-k="del" title="Remove">✕</button></div>`).join('')
    : '<div class="muted small" style="padding:8px 0">No names yet. Add the people, organizations and places you write about, with any spellings you want flagged (Kiev → Kyiv, Prigozin → Prigozhin).</div>';
  const sug = spellingSuggestions();
  $('#namesSug').innerHTML = sug.length ? sug.map(s => `<li><span><b>${esc(s.keep)}</b> (${s.nk}) and <b>${esc(s.alt)}</b> (${s.na})</span><button data-keep="${esc(s.keep)}" data-alt="${esc(s.alt)}">Use “${esc(s.keep)}”</button><button class="ghost" data-keep="${esc(s.alt)}" data-alt="${esc(s.keep)}">Use “${esc(s.alt)}”</button></li>`).join('') : '<li class="muted small">No near-duplicate spellings spotted in your documents and notes.</li>';
}
$('#namesList').addEventListener('input', e => {
  const row = e.target.closest('.ent'); if (!row) return; const en = P.entities.find(x => x.id === row.dataset.e); const k = e.target.dataset.k;
  if (k === 'variants') en.variants = e.target.value.split(',').map(x => x.trim()).filter(Boolean); else en[k] = e.target.value;
  markDirty(); renderOutlineSoon();
});
$('#namesList').addEventListener('click', e => { const b = e.target.closest('[data-k=del]'); if (!b) return; P.entities = P.entities.filter(x => x.id !== b.closest('.ent').dataset.e); renderNames(); markDirty(); renderOutline(); });
$('#namesAdd').addEventListener('click', () => { P.entities.push({ id: uid('e'), name: '', kind: 'person', variants: [], note: '' }); renderNames(); $$('#namesList .ent:last-child input')[0]?.focus(); });
$('#namesSug').addEventListener('click', e => {
  const b = e.target.closest('button[data-keep]'); if (!b) return;
  let en = P.entities.find(x => x.name === b.dataset.keep);
  if (!en) { en = { id: uid('e'), name: b.dataset.keep, kind: 'person', variants: [], note: '' }; P.entities.push(en); }
  if (!en.variants.includes(b.dataset.alt)) en.variants.push(b.dataset.alt);
  renderNames(); markDirty(); renderOutline(); toast(`Added. “${b.dataset.alt}” will be flagged in favor of “${b.dataset.keep}”.`);
});
$('#namesClose').addEventListener('click', () => { P.entities = P.entities.filter(x => x.name.trim()); $('#namesDlg').close(); renderOutline(); });

/* ---------- margin comments (export as Word comments) ---------- */
function findComment(id) { for (const d of P.docs) { const c = (d.comments || []).find(x => x.id === id); if (c) return c; } return null; }
$('#btnComment').addEventListener('click', addComment);
$('#toolbar').addEventListener('mousedown', e => { if (e.target.closest('#btnComment')) e.preventDefault(); });
/* ---------- integrity panel (Outline tab): quotes, names, comments ---------- */
let intEls = [];
function renderIntegrity() {
  intEls = [];
  const push = el => { intEls.push(el); return intEls.length - 1; };
  // quotes
  $$('[data-cp-qbad]', editor).forEach(x => x.removeAttribute('data-cp-qbad'));
  const qs = $$('.qlink[data-qn], blockquote[data-qn]', editor).map(el => ({ el, st: quoteStatus(el) }));
  const bad = qs.filter(q => q.st.state === 'changed' || q.st.state === 'orphan');
  bad.forEach(q => q.el.setAttribute('data-cp-qbad', ''));
  const unl = unlinkedQuotes();
  $('#quoteSum').innerHTML = qs.length || unl.length ? `${qs.length - bad.length} of ${qs.length} linked quote${qs.length === 1 ? '' : 's'} match their notes${unl.length ? ` · ${unl.length} quotation${unl.length > 1 ? 's' : ''} not linked to a note` : ''}` : '';
  $('#quoteList').innerHTML = bad.map(q => `<li data-j="${push(q.el)}" class="qbad"><b class="fk fk-cite">${q.st.state === 'orphan' ? 'no note' : 'changed'}</b><span>${esc(blockSnippet(q.el, 50))}</span>${q.st.n ? `<button class="ghost small" data-qa="diff" data-qn="${q.st.n.id}">Compare</button>` : ''}</li>`).join('') +
    unl.slice(0, 8).map(u => `<li data-j="${push(u.el)}"><b class="fk fk-check">unlinked</b><span>${esc(u.q.slice(0, 60))}…</span></li>`).join('') ||
    `<li class="muted small none">${qs.length ? 'All linked quotes match their source notes.' : 'Quotes you insert from notes are checked against the original here.'}</li>`;
  // names
  const ni = nameIssues();
  if (window.CSS && CSS.highlights && window.Highlight) { const all = ni.flatMap(x => x.ranges); if (all.length) CSS.highlights.set('cp-name', new Highlight(...all)); else CSS.highlights.delete('cp-name'); }
  $('#nameList').innerHTML = ni.map(x => `<li data-j="${push(x.ranges[0].startContainer.parentElement)}"><b class="fk fk-tk">${x.ranges.length}×</b><span>${esc(x.v)} → ${esc(x.e.name)}</span><button class="ghost small" data-fix="${esc(x.v)}" data-to="${esc(x.e.name)}">Fix all</button></li>`).join('')
    || `<li class="muted small none">${P.entities.length ? 'No flagged spellings in this document.' : 'Add names and spellings to check.'}</li>`;
  // comments
  const cm = $$('.cmt', editor).map(el => ({ el, c: findComment(el.dataset.cmt) })).filter(x => x.c);
  $('#cmtList').innerHTML = cm.map(x => `<li data-j="${push(x.el)}"><span><b>${esc(x.c.text.slice(0, 60) || '(empty)')}</b> <em class="muted">“${esc(x.el.textContent.slice(0, 30))}”</em></span><button class="ghost small" data-resolve="${x.c.id}">Resolve</button></li>`).join('')
    || '<li class="muted small none">Click ✎ in the toolbar (⌘/Ctrl+Alt+A) to write a note in the margin, anchored to the cursor or a selection.</li>';
  $('#cmtCount').textContent = cm.length || '';
  $('#qCount').textContent = bad.length || ''; $('#nCount').textContent = ni.length || '';
  const ixm = $$('.ixm', editor).length; $('#ixSum').textContent = `${ixm} marked here · ${P.indexTerms.length} term${P.indexTerms.length === 1 ? '' : 's'} indexed everywhere${P.indexOpts.names && P.entities.length ? ' · names list on' : ''}`;
  return bad.length + ni.length;
}
['#quoteList', '#nameList', '#cmtList'].forEach(sel => $(sel).addEventListener('click', async e => {
  const fix = e.target.closest('[data-fix]'), res = e.target.closest('[data-resolve]'), qa = e.target.closest('[data-qa]');
  if (fix) {
    const iss = nameIssues().find(x => x.v === fix.dataset.fix); if (!iss) return;
    for (let i = iss.ranges.length - 1; i >= 0; i--) replaceRange(iss.ranges[i], fix.dataset.to);
    onEdit(); renderOutline(); toast(`Replaced ${iss.ranges.length} × ${fix.dataset.fix}.`); return;
  }
  if (res) { removeComment(res.dataset.resolve); return; }
  if (qa) {
    const li = qa.closest('li'), el = intEls[+li.dataset.j], n = P.notes.find(x => x.id === qa.dataset.qn);
    const ex = li.nextElementSibling; if (ex && ex.classList.contains('qdiff')) { ex.remove(); return; }
    li.insertAdjacentHTML('afterend', `<li class="qdiff none"><div class="diffbox small">${quoteDiffHTML(n, el)}</div><div class="pbtns"><button class="small" data-qfix="restore" data-qn="${n.id}">Restore original</button><button class="small ghost" data-qfix="note" data-qn="${n.id}">Update note to match</button></div></li>`);
    return;
  }
  const qf = e.target.closest('[data-qfix]');
  if (qf) {
    const li = qf.closest('li').previousElementSibling, el = intEls[+li.dataset.j], n = P.notes.find(x => x.id === qf.dataset.qn);
    if (qf.dataset.qfix === 'restore') { if (el.matches('blockquote')) { const t = document.createElement('template'); t.innerHTML = noteToHTML(n); el.replaceWith(t.content); } else el.innerHTML = sanitize(marked.parseInline(plainMd(n.body).replace(/\s*\n\s*/g, ' '))); toast('Quote restored to match your note.'); }
    else { const c = el.cloneNode(true); $$('.cite,.fn,.flag', c).forEach(m => m.remove()); n.body = c.textContent.trim(); n.modified = nowISO(); toast('Note updated to match the draft. Make sure that’s what the source says.'); }
    onEdit(); setTimeout(renderOutline, 400); return;
  }
  const li = e.target.closest('li[data-j]'); if (!li) return;
  const el = intEls[+li.dataset.j]; if (!el || !editor.contains(el)) return;
  el.scrollIntoView({ block: 'center', behavior: 'smooth' }); const blk = el.closest('#editor > *') || el;
  blk.setAttribute('data-cp-flash', ''); setTimeout(() => blk.removeAttribute('data-cp-flash'), 1400);
}));
$('#btnNames').addEventListener('click', openNames);

/* ---------- source audit ---------- */
function auditData(scope) {
  syncEditor();
  const docs = scope === 'doc' ? [curDoc()] : binderOrder();
  const rows = new Map(P.sources.map(s => [s.id, { s, cites: 0, quoted: 0, notes: P.notes.filter(n => n.sourceId === s.id).length, docs: new Set() }]));
  const per = [];
  docs.forEach(d => {
    const t = document.createElement('div'); t.innerHTML = d.html;
    const counts = {};
    $$('.cite', t).forEach(m => markerItems(m).forEach(it => { const r = rows.get(it.id); if (!r) return; r.cites++; r.docs.add(d.id); counts[it.id] = (counts[it.id] || 0) + 1; }));
    $$('.qlink[data-qn], blockquote[data-qn]', t).forEach(q => { const n = P.notes.find(x => x.id === q.dataset.qn); const r = n && rows.get(n.sourceId); if (r) { const c = q.cloneNode(true); $$('.cite,.fn', c).forEach(m => m.remove()); r.quoted += wc(c.textContent); } });
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    if (total >= 5 && top && top[1] / total > 0.4) { const l = sourceLabel(rows.get(top[0]).s); per.push(`“${d.title}” relies on ${l.who || l.title} for ${Math.round(top[1] / total * 100)}% of its ${total} citations.`); }
  });
  const list = [...rows.values()];
  const missing = list.filter(r => r.cites && (!r.s.csl.title || !(r.s.csl.author || r.s.csl.editor) || !r.s.csl.issued)).map(r => r.s);
  return { list, per, unused: list.filter(r => !r.cites), missing, docs };
}
function openAudit(scope = 'all') {
  $('#auScope').value = scope; renderAudit(); $('#auditDlg').showModal();
}
function renderAudit() {
  const a = auditData($('#auScope').value), used = a.list.filter(r => r.cites).sort((x, y) => y.cites - x.cites);
  const total = used.reduce((n, r) => n + r.cites, 0) || 1;
  $('#auBody').innerHTML = `
    ${a.per.length ? `<div class="tip warnbox">${a.per.map(esc).join('<br>')}</div>` : ''}
    <table class="audit"><thead><tr><th>Source</th><th>Citations</th><th>Share</th><th>Quoted words</th><th>Notes</th></tr></thead><tbody>
    ${used.map(r => { const l = sourceLabel(r.s); return `<tr><td><b>${esc(l.who || '—')}</b>${l.yr ? ' (' + esc(l.yr) + ')' : ''}: ${esc(l.title)}</td><td>${r.cites}</td><td><span class="bar"><i style="width:${Math.round(r.cites / total * 100)}%"></i></span> ${Math.round(r.cites / total * 100)}%</td><td class="${r.quoted >= 300 ? 'hot' : ''}">${r.quoted ? r.quoted.toLocaleString() : '—'}</td><td>${r.notes || '—'}</td></tr>`; }).join('') || '<tr><td colspan="5" class="muted">No citations in this scope yet.</td></tr>'}
    </tbody></table>
    <p class="small muted">Quoted words count text you inserted from quote notes, so typed or pasted quotations aren’t included. Publishers set their own thresholds for quoting without permission, so check yours. Totals of 300+ words from one work are highlighted.</p>
    ${a.missing.length ? `<h4>Cited sources missing basic details</h4><ul class="small">${a.missing.map(s => `<li><a href="#" data-src="${s.id}">${esc(sourceLabel(s).title)}</a>: ${[!s.csl.title && 'title', !(s.csl.author || s.csl.editor) && 'author', !s.csl.issued && 'date'].filter(Boolean).join(', ')}</li>`).join('')}</ul>` : ''}
    ${a.unused.length ? `<h4>In your library but not cited ${$('#auScope').value === 'doc' ? 'in this document' : 'anywhere'} (${a.unused.length})</h4><ul class="small cols2">${a.unused.map(r => `<li><a href="#" data-src="${r.s.id}">${esc((sourceLabel(r.s).who ? sourceLabel(r.s).who + ', ' : '') + sourceLabel(r.s).title)}</a>${r.notes ? ` <span class="muted">· ${r.notes} note${r.notes > 1 ? 's' : ''}</span>` : ''}</li>`).join('')}</ul>` : ''}`;
}
$('#auScope').addEventListener('change', renderAudit);
$('#auBody').addEventListener('click', e => { const a = e.target.closest('[data-src]'); if (!a) return; e.preventDefault(); $('#auditDlg').close(); switchTab('sources'); openSource(a.dataset.src); });
$('#auClose').addEventListener('click', () => $('#auditDlg').close());
$('#btnAudit').addEventListener('click', () => openAudit('all'));

/* ---------- timeline (board mode) ---------- */
function dateKey(s) {
  s = String(s || '').trim(); if (!s) return null;
  const bce = /\b(BCE?|B\.C\.)\b/i.test(s);
  const d = parseDate(s.replace(/^(c\.|ca\.|circa|about)\s*/i, '').replace(/\s*[–—-]\s*\d{3,4}.*$/, '').replace(/\s*\b(BCE?|CE|AD|B\.C\.|A\.D\.)\b\.?/gi, ''));
  let p = d && d['date-parts'] ? d['date-parts'][0] : null;
  if (!p) { const y = s.match(/\d{3,4}/); if (!y) return null; p = [+y[0]]; }
  const y = bce ? -p[0] : p[0];
  return y * 10000 + (p[1] || 0) * 100 + (p[2] || 0);
}
function renderTimeline(area) {
  const notes = boardNotes(), dated = notes.map(n => ({ n, k: dateKey(n.date) })).filter(x => x.k !== null).sort((a, b) => a.k - b.k), undated = notes.filter(n => dateKey(n.date) === null);
  let lastY = null;
  const gaps = dated.slice(1).map((x, i) => keyYear(x.k) - keyYear(dated[i].k)).filter(g => g > 0).sort((a, b) => a - b);
  const med = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0;
  let prevK = null;
  const gapText = g => g >= 1.5 ? `${Math.round(g)} years` : g >= 2 / 12 ? `${Math.round(g * 12)} months` : `${Math.max(1, Math.round(g * 52))} weeks`;
  const rows = dated.map(({ n, k }) => {
    const y = Math.trunc(k / 10000), head = y !== lastY ? `<div class="tl-year">${y < 0 ? -y + ' BCE' : y}</div>` : ''; lastY = y;
    const g = prevK === null ? 0 : keyYear(k) - keyYear(prevK); prevK = k;
    const gap = dated.length > 3 && g > Math.max(med * 3, 1 / 12) ? `<div class="tl-gap">${gapText(g)} with nothing on the record</div>` : '';
    return gap + head + `<div class="tl-row"><div class="tl-date">${esc(n.date)}</div><div class="tl-dot"></div>${cardHTML(n)}</div>`;
  }).join('');
  area.className = 'bd-area timeline';
  area.innerHTML = `<div class="tl-main">${rows || '<div class="empty">No dated cards yet. Give a note an <b>event date</b> (when it happened) and it appears here in order.</div>'}</div>
    <div class="tl-side"><div class="bd-col-h"><b>Undated</b><span class="muted small">${undated.length}</span></div><div class="bd-cards">${undated.sort(boardSort).map(cardHTML).join('') || '<div class="bd-empty">Every card has a date</div>'}</div></div>`;
}
function chronologyDoc() {
  const dated = P.notes.map(n => ({ n, k: dateKey(n.date) })).filter(x => x.k !== null).sort((a, b) => a.k - b.k);
  if (!dated.length) { toast('No dated notes yet. Add an event date to notes first.'); return; }
  const html = '<h1>Chronology</h1>' + dated.map(({ n }) => `<p><b>${esc(n.date)}.</b> ${esc(n.title || firstLine(n.body))}${n.title && n.body && n.kind !== 'quote' ? ': ' + esc(plainMd(n.body).replace(/\s+/g, ' ').slice(0, 220)) : ''}</p>`).join('');
  const d = newDoc('Chronology', html); d.role = 'back'; d.template = 'chronology'; closeBoard(); addDoc(d); switchTab('docs'); toast('Chronology created from your dated notes. Edit freely.');
}

/* ---------- revision lens ---------- */
let lensOn = false, lensOff = new Set();
const HEDGES = ['arguably', 'somewhat', 'perhaps', 'fairly', 'quite', 'rather', 'very', 'really', 'basically', 'essentially', 'actually', 'virtually', 'relatively', 'seemingly', 'apparently', 'it seems', 'in order to', 'it is important to note', 'it should be noted', 'needless to say', 'a number of', 'the fact that', 'kind of', 'sort of'];
const STOP = new Set('about above after again against their there these those would could should which while where when what with within without because before being between other under until through during every never always often still since first second third people years however although though among'.split(' '));
const IRREG = 'built|made|done|seen|known|given|taken|held|found|left|told|thought|brought|kept|sent|shown|written|chosen|caught|fought|led|lost|met|paid|put|read|said|set|shot|sold|spent|struck|taught|won|hit|cut|hurt|let|shut|spread|drawn|driven|eaten|fallen|forgotten|hidden|ridden|risen|shaken|spoken|stolen|sworn|thrown|woken|worn|broken|frozen|begun|sung|sunk|swum|beaten|bitten|born|borne|bound|bred|dealt|dug|fed|fled|flung|forbidden|forgiven|ground|hung|laid|lent|lit|meant|overseen|overrun|overtaken|sought|slain|sped|split|sprung|stuck|stung|struck|strewn|swept|torn|undertaken|upheld|withdrawn|wound|wrung';
const PASSIVE = new RegExp(`\\b(am|is|are|was|were|be|been|being)\\s+(?:\\w+ly\\s+)?(\\w+ed|${IRREG})\\b`, 'gi');
function syllables(w) { w = w.toLowerCase().replace(/[^a-z]/g, ''); if (w.length <= 3) return 1; w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, ''); const m = w.match(/[aeiouy]{1,2}/g); return m ? m.length : 1; }
function blockMap(el) {
  const map = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentElement.closest('.cite,.fn,.flag') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  let text = ''; while (w.nextNode()) { map.push({ node: w.currentNode, start: text.length }); text += w.currentNode.data; }
  const at = i => { let k = map.length - 1; while (k > 0 && map[k].start > i) k--; return { node: map[k].node, off: Math.min(i - map[k].start, map[k].node.data.length) }; };
  const range = (a, b) => { if (!map.length) return null; const s = at(a), e = at(b); const r = document.createRange(); r.setStart(s.node, s.off); r.setEnd(e.node, e.off); return r; };
  return { text, range };
}
function runLens() {
  const hl = window.CSS && CSS.highlights && window.Highlight;
  const R = { long: [], passive: [], hedge: [], repeat: [] };
  let words = 0, sents = 0, syl = 0;
  $$(':scope > p, :scope > li, :scope > ul > li, :scope > ol > li, :scope > blockquote > p, :scope > blockquote', editor).forEach(el => {
    if (el.matches('blockquote') && el.querySelector('p')) return;
    const { text, range } = blockMap(el); if (!text.trim()) return;
    const sre = /[^.!?]+(?:[.!?]+["”’)\]]*|$)/g; let m;
    while ((m = sre.exec(text))) { const s = m[0]; const n = wc(s); if (!n) continue; sents++; words += n; syl += (s.match(/[A-Za-z]+/g) || []).reduce((a, w) => a + syllables(w), 0); if (n > 35) { const lead = s.length - s.trimStart().length; const r = range(m.index + lead, m.index + s.trimEnd().length); r && R.long.push(r); } }
    PASSIVE.lastIndex = 0; while ((m = PASSIVE.exec(text))) { const r = range(m.index, m.index + m[0].length); r && R.passive.push(r); }
    const hre = new RegExp('\\b(' + HEDGES.map(escRe).join('|') + ')\\b', 'gi'); while ((m = hre.exec(text))) { const r = range(m.index, m.index + m[0].length); r && R.hedge.push(r); }
    const wre = /[A-Za-z’']{5,}/g, last = {}; let idx = 0;
    while ((m = wre.exec(text))) { const w = m[0].toLowerCase().replace(/[’']s$/, ''); idx++; if (STOP.has(w)) continue; if (last[w] !== undefined && idx - last[w] <= 40) { const r = range(m.index, m.index + m[0].length); r && R.repeat.push(r); } last[w] = idx; }
  });
  const grade = words && sents ? Math.max(0, 0.39 * (words / sents) + 11.8 * (syl / words) - 15.59) : 0;
  if (hl) Object.keys(R).forEach(k => { if (R[k].length && !lensOff.has(k)) CSS.highlights.set('cp-' + k, new Highlight(...R[k])); else CSS.highlights.delete('cp-' + k); });
  const chip = (k, label) => `<button class="lchip l-${k} ${lensOff.has(k) ? 'off' : ''}" data-l="${k}">${label} <b>${R[k].length}</b></button>`;
  $('#lensBar').innerHTML = chip('long', 'Long sentences') + chip('passive', 'Passive voice') + chip('hedge', 'Hedges & filler') + chip('repeat', 'Repeated words') +
    `<span class="muted small">Grade level ${grade ? grade.toFixed(1) : '—'} · ${sents ? Math.round(words / sents) : 0} words per sentence</span>${hl ? '' : '<span class="muted small">(Highlighting needs a newer browser. Counts still work.)</span>'}<button class="ghost small" id="lensClose">✕</button>`;
}
const runLensSoon = debounce(() => { if (lensOn) runLens(); }, 700);
function toggleLens(on) {
  lensOn = on ?? !lensOn; $('#lensBar').classList.toggle('hidden', !lensOn); $('#btnLens').classList.toggle('on', lensOn);
  if (lensOn) runLens(); else if (window.CSS && CSS.highlights) ['long', 'passive', 'hedge', 'repeat'].forEach(k => CSS.highlights.delete('cp-' + k));
}
$('#btnLens').addEventListener('click', () => toggleLens());
$('#lensBar').addEventListener('click', e => { if (e.target.closest('#lensClose')) { toggleLens(false); return; } const c = e.target.closest('[data-l]'); if (!c) return; lensOff.has(c.dataset.l) ? lensOff.delete(c.dataset.l) : lensOff.add(c.dataset.l); runLens(); });
editor.addEventListener('input', runLensSoon);

/* ---------- book furniture: templates & annotated bibliography ---------- */
const TEMPLATES = [
  ['dedication', 'Dedication', 'front', '<p style="text-align: center;"><i>For …</i></p>'],
  ['epigraph', 'Epigraph', 'front', '<blockquote><p>Quotation.</p><p style="text-align: right;">— Author, <i>Work</i></p></blockquote>'],
  ['abbreviations', 'List of Abbreviations', 'front', '<nav class="abbr" contenteditable="false"><p>List of abbreviations — filled in when you export.</p></nav>'],
  ['lof', 'List of Figures and Tables', 'front', '<nav class="lof" contenteditable="false"><p>List of figures and tables — filled in when you export.</p></nav>'],
  ['preface', 'Preface', 'front', '<p>Why you wrote this book, and how it came to be.</p>'],
  ['introduction', 'Introduction', 'body', '<p>The question, the stakes, and the road map.</p>'],
  ['chapter', 'Chapter', 'body', '<p><br></p>'],
  ['conclusion', 'Conclusion', 'body', '<p>What it all adds up to.</p>'],
  ['acknowledgments', 'Acknowledgments', 'back', '<p>Thank the people, institutions and archives that made the book possible.</p>'],
  ['sources-note', 'A Note on Sources', 'back', '<p>Describe the sources you relied on, how you weighed them, and any limits, such as gaps, translation, or access.</p>'],
  ['glossary', 'Glossary', 'back', '<p><b>Term</b> — Definition.</p>'],
  ['about', 'About the Author', 'back', '<p>Name is …</p>'],
];
function openTemplates() {
  $('#tplList').innerHTML = TEMPLATES.map(([k, t, r]) => `<button class="tpl" data-t="${k}"><b>${t}</b><span>${r === 'front' ? 'Front matter' : r === 'back' ? 'Back matter' : 'Chapter'}</span></button>`).join('') +
    `<button class="tpl" data-t="__chron"><b>Chronology</b><span>Built from your dated notes</span></button><button class="tpl" data-t="__annot"><b>Annotated bibliography</b><span>Sources with your annotations</span></button>`;
  $('#tplDlg').showModal();
}
$('#tplList').addEventListener('click', e => {
  const b = e.target.closest('[data-t]'); if (!b) return; $('#tplDlg').close();
  if (b.dataset.t === '__chron') { chronologyDoc(); return; }
  if (b.dataset.t === '__annot') { annotatedBibliography(); return; }
  const [k, t, role, html] = TEMPLATES.find(x => x[0] === b.dataset.t);
  const d = newDoc(t, html); d.role = role; d.template = k; addDoc(d); d.role = role; renderDocList(); toast(`${t} added as ${role === 'body' ? 'a chapter' : role + ' matter'}. Manuscript compile puts it in the right place.`);
});
$('#tplClose').addEventListener('click', () => $('#tplDlg').close());
$('#btnTemplates').addEventListener('click', openTemplates);
async function annotatedBibliography() {
  syncEditor();
  const cited = new Set(); P.docs.forEach(d => { for (const m of d.html.matchAll(/&quot;id&quot;:&quot;([^&]+)&quot;/g)) cited.add(m[1]); });
  const scopeCited = cited.size && await ask('Annotated bibliography', `Include only the ${cited.size} sources cited in your documents? Choose Cancel to include your whole library (${P.sources.length}).`, 'Cited only');
  const ids = P.sources.filter(s => !scopeCited || cited.has(s.id)).map(s => s.id);
  if (!ids.length) { toast('No sources to include.'); return; }
  const style = curDoc()?.style || DEFAULT_STYLE;
  let entries = [];
  if (STYLES[style].custom) entries = sortedSources().filter(s => ids.includes(s.id)).map(s => ({ id: s.id, html: osintCluster([{ id: s.id }], new Set()) }));
  else { const e = makeEngine(style); e.updateItems(ids); const b = e.makeBibliography(); entries = b[0].entry_ids.map((x, i) => ({ id: x[0], html: b[1][i].replace(/^\s*<div class="csl-entry">|<\/div>\s*$/g, '') })); }
  const html = '<h1>Annotated Bibliography</h1>' + entries.map(en => {
    const s = P.sources.find(x => x.id === en.id);
    const sum = s.annotation || P.notes.filter(n => n.sourceId === s.id && n.kind === 'summary').map(n => plainMd(n.body)).join(' ');
    return `<p class="ab-entry">${en.html}</p>${sum ? `<p class="ab-note">${esc(sum)}</p>` : `<p class="ab-note"><mark>[Add an annotation in this source’s panel, or write one here.]</mark></p>`}`;
  }).join('');
  const d = newDoc('Annotated Bibliography', html); d.role = 'back'; d.template = 'annotated'; d.style = style; addDoc(d); d.role = 'back'; renderDocList();
  toast(`Annotated bibliography created with ${entries.length} entries.`);
}

/* ---------- writing record: daily words, streak, chapter status ---------- */
function trackWords() {
  const d = curDoc(); if (!d || !P.stats) return;
  const now = wordsIn(editor), base = P.stats.base[d.id];
  P.stats.base[d.id] = now;
  if (base === undefined) return;
  const delta = now - base; if (!delta || delta > 250) return; // big jumps are pastes/imports, not writing
  const k = todayKey(), day = P.stats.days[k] || (P.stats.days[k] = { a: 0, n: 0 });
  if (delta > 0) day.a += delta; day.n += delta;
}
function streak() {
  const goal = PREFS.dailyGoal || 1; let n = 0; const d = new Date();
  if (((P.stats.days[todayKey(d)] || {}).a || 0) < goal) d.setDate(d.getDate() - 1);
  while (((P.stats.days[todayKey(d)] || {}).a || 0) >= goal) { n++; d.setDate(d.getDate() - 1); }
  return n;
}
function dueLabel(d) {
  if (!d.deadline || d.status === 'final') return '';
  const days = Math.round((new Date(d.deadline + 'T12:00') - new Date()) / 864e5);
  return `<span class="due ${days < 0 ? 'late' : days <= 3 ? 'soon' : ''}">${days < 0 ? Math.abs(days) + 'd overdue' : days === 0 ? 'due today' : 'due in ' + days + 'd'}</span>`;
}
function openRecord() {
  syncEditor(); const days = [], dd = new Date(); dd.setDate(dd.getDate() - 29);
  for (let i = 0; i < 30; i++) { const k = todayKey(dd); days.push({ k, a: (P.stats.days[k] || {}).a || 0, d: new Date(dd) }); dd.setDate(dd.getDate() + 1); }
  const max = Math.max(PREFS.dailyGoal || 0, ...days.map(x => x.a), 10), W = 600, H = 120, bw = W / 30;
  const svg = `<svg viewBox="0 0 ${W} ${H + 18}" class="rec-chart" role="img" aria-label="Words added per day, last 30 days">${days.map((x, i) => { const h = Math.round(x.a / max * H); return `<rect x="${i * bw + 2}" y="${H - h}" width="${bw - 4}" height="${Math.max(h, x.a ? 2 : 0)}" rx="2"><title>${x.d.toLocaleDateString([], { month: 'short', day: 'numeric' })}: ${x.a} words</title></rect>`; }).join('')}${PREFS.dailyGoal ? `<line x1="0" x2="${W}" y1="${H - PREFS.dailyGoal / max * H}" y2="${H - PREFS.dailyGoal / max * H}" class="goal"/>` : ''}<line x1="0" x2="${W}" y1="${H}" y2="${H}" class="axis"/><text x="0" y="${H + 14}">${days[0].d.toLocaleDateString([], { month: 'short', day: 'numeric' })}</text><text x="${W}" y="${H + 14}" text-anchor="end">Today</text></svg>`;
  const today = days[29].a, week = days.slice(23).reduce((n, x) => n + x.a, 0), total = P.docs.reduce((n, d) => n + docWords(d), 0);
  $('#recStats').innerHTML = `<div><b>${today.toLocaleString()}</b><span>today${PREFS.dailyGoal ? ' / ' + PREFS.dailyGoal.toLocaleString() : ''}</span></div><div><b>${streak()}</b><span>day streak</span></div><div><b>${week.toLocaleString()}</b><span>last 7 days</span></div><div><b>${total.toLocaleString()}</b><span>words in project</span></div>`;
  $('#recChart').innerHTML = svg;
  const ST = ['', 'idea', 'drafting', 'revising', 'final'];
  $('#recDocs').innerHTML = binderOrder().map(d => { const w = docWords(d); return `<tr data-d="${d.id}"><td>${d.role && d.role !== 'body' ? `<span class="role-tag">${d.role}</span>` : ''}${esc(d.title || 'Untitled')}</td>
    <td><select data-r="status">${ST.map(s => `<option value="${s}" ${s === d.status ? 'selected' : ''}>${s || '—'}</option>`).join('')}</select></td>
    <td><input type="date" data-r="deadline" value="${esc(d.deadline || '')}"></td><td>${w.toLocaleString()}${d.target ? ` / ${d.target.toLocaleString()}<span class="bar"><i style="width:${Math.min(100, w / d.target * 100)}%"></i></span>` : ''}</td><td>${dueLabel(d)}</td></tr>`; }).join('');
  $('#recDlg').showModal();
}
$('#recDocs').addEventListener('change', e => { const tr = e.target.closest('tr'); const d = P.docs.find(x => x.id === tr.dataset.d); d[e.target.dataset.r] = e.target.value; markDirty(); renderDocList(); tr.lastElementChild.innerHTML = dueLabel(d); });
$('#recClose').addEventListener('click', () => $('#recDlg').close());
$('#btnRecord').addEventListener('click', openRecord);

/* ---------- interviews & transcripts ---------- */
let trLines = [], trSel = new Set(), trAnchor = null, trSource = null;
function parseTranscript(text) {
  const out = []; let ts = '', sp = '';
  const TS = '(\\d{1,2}:\\d{2}(?::\\d{2})?(?:[.,]\\d+)?)';
  String(text || '').split(/\r?\n/).forEach(raw => {
    const line = raw.trim(); if (!line || /^WEBVTT|^\d+$|-->/.test(line) && !/:\s/.test(line)) { const vt = line.match(new RegExp('^' + TS + '\\s*-->')); if (vt) ts = vt[1].replace(/[.,]\d+$/, ''); return; }
    let m;
    if ((m = line.match(new RegExp('^[\\[(]?' + TS + '[\\])]?\\s*[-–—|]?\\s*(?:([^:]{1,40}):\\s*)?(.*)$')))) { ts = m[1].replace(/[.,]\d+$/, ''); if (m[2]) sp = m[2].trim(); if (m[3]) out.push({ ts, sp, text: m[3] }); return; }
    if ((m = line.match(new RegExp('^([^:\\d][^:]{0,40}?)\\s+[\\[(]?' + TS + '[\\])]?\\s*:?\\s*(.*)$')))) { sp = m[1].trim(); ts = m[2].replace(/[.,]\d+$/, ''); if (m[3]) out.push({ ts, sp, text: m[3] }); return; }
    if ((m = line.match(/^([A-Z][\w .'’-]{0,40}):\s+(.+)$/))) { sp = m[1].trim(); out.push({ ts, sp, text: m[2] }); return; }
    out.push({ ts, sp, text: line });
  });
  return out;
}
function openTranscript(sourceId) {
  trSource = sourceId || (panelState?.kind === 'source' ? panelState.id : null);
  $('#trSource').innerHTML = '<option value="">— choose a source —</option>' + sortedSources().map(s => { const l = sourceLabel(s); return `<option value="${s.id}" ${s.id === trSource ? 'selected' : ''}>${esc((l.who ? l.who + ', ' : '') + l.title).slice(0, 70)}</option>`; }).join('');
  loadTranscript(); $('#trDlg').showModal();
}
function loadTranscript() {
  trSource = $('#trSource').value || null; const s = P.sources.find(x => x.id === trSource);
  $('#trText').value = s ? s.transcript || '' : ''; trSel.clear(); renderTrLines();
}
function renderTrLines() {
  trLines = parseTranscript($('#trText').value);
  const used = new Set(P.notes.filter(n => n.sourceId === trSource && n.label === 'timestamp').map(n => n.locator));
  $('#trLines').innerHTML = trLines.length ? trLines.map((l, i) => `<li data-i="${i}" class="${trSel.has(i) ? 'on' : ''}"><span class="ts">${esc(l.ts || '—')}${used.has(l.ts) && l.ts ? ' ✓' : ''}</span>${l.sp ? `<b>${esc(l.sp)}:</b> ` : ''}${esc(l.text)}</li>`).join('') : '<li class="muted">Paste a transcript above. Lines with timestamps like [00:12:34], 12:34, or “Speaker 0:05” are recognized, as are Otter, Zoom and WebVTT exports.</li>';
  $('#trCount').textContent = trSel.size ? `${trSel.size} line${trSel.size > 1 ? 's' : ''} selected` : '';
  if ($('#trFind') && $('#trFind').value) $('#trFind').dispatchEvent(new Event('input'));
}
$('#trSource').addEventListener('change', loadTranscript);
$('#trText').addEventListener('input', debounce(() => { const s = P.sources.find(x => x.id === trSource); if (s) { s.transcript = $('#trText').value; markDirty(); } renderTrLines(); }, 300));
$('#trLines').addEventListener('click', e => {
  const li = e.target.closest('li[data-i]'); if (!li) return; const i = +li.dataset.i;
  if (e.shiftKey && trAnchor !== null) { const [a, b] = [Math.min(trAnchor, i), Math.max(trAnchor, i)]; for (let k = a; k <= b; k++) trSel.add(k); }
  else { trSel.has(i) ? trSel.delete(i) : trSel.add(i); trAnchor = i; }
  renderTrLines();
});
$('#trNewSrc').addEventListener('click', async () => {
  const who = await ask('New interview', 'Who was interviewed? (e.g. “Jane Doe”). Add the date and other details in the source panel afterward.', 'Create', ''); if (!who) return;
  const s = addSource({ type: 'interview', title: 'Interview with ' + who, author: [splitName(who)].filter(Boolean), issued: todayParts(), genre: 'interview by author' });
  openTranscript(s.id);
});
function trMake(kind) {
  if (!trSource) { toast('Choose the source this transcript belongs to.'); return; }
  const lines = [...trSel].sort((a, b) => a - b).map(i => trLines[i]); if (!lines.length) { toast('Click lines to select them (Shift-click for a range).'); return; }
  const n = newNote(); n.kind = kind; n.sourceId = trSource;
  n.body = lines.map(l => l.text).join(' ');
  const ts = lines.find(l => l.ts)?.ts; if (ts) { n.locator = ts; n.label = 'timestamp'; }
  const sp = lines.find(l => l.sp)?.sp;
  n.title = (sp ? sp + ': ' : '') + n.body.split(/\s+/).slice(0, 6).join(' ') + '…';
  P.notes.unshift(n); trSel.clear(); renderTrLines(); renderNoteList(); renderBoard(); markDirty();
  toast(`${kind === 'quote' ? 'Quote' : 'Paraphrase'} note made${ts ? ' at ' + ts : ''}.`);
}
$('#trQuote').addEventListener('click', () => trMake('quote'));
$('#trPara').addEventListener('click', () => trMake('paraphrase'));
$('#trClose').addEventListener('click', () => $('#trDlg').close());

/* ================================================================
   PDF reader · Index · Start fresh
   ================================================================ */
/* raw IndexedDB helpers for stored PDFs and resets */
function idbReq(mode, fn) {
  return new Promise((res, rej) => {
    const r = indexedDB.open('commonplace', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('kv');
    r.onerror = () => rej(r.error);
    r.onsuccess = () => { const db = r.result, t = db.transaction('kv', mode), st = t.objectStore('kv'); let out; const q = fn(st); if (q) q.onsuccess = () => { out = q.result; }; t.oncomplete = () => { db.close(); res(out); }; t.onerror = () => { db.close(); rej(t.error); }; };
  });
}
const pdfStore = {
  get: id => idbReq('readonly', st => st.get('pdf:' + id)),
  set: (id, val) => idbReq('readwrite', st => st.put(val, 'pdf:' + id)),
  del: id => idbReq('readwrite', st => st.delete('pdf:' + id)),
  keys: () => idbReq('readonly', st => st.getAllKeys()),
};

/* ---------- PDF.js, loaded on first use from the embedded copy ---------- */
let pdfjs = null;
async function loadPdfjs() {
  if (pdfjs) return pdfjs;
  const src = document.getElementById('lib-pdfjs').textContent, wsrc = document.getElementById('lib-pdfworker').textContent;
  pdfjs = await import(URL.createObjectURL(new Blob([src], { type: 'text/javascript' })));
  // a classic (not module) worker: browsers refuse module workers from blob URLs when the page is a local file
  pdfjs.GlobalWorkerOptions.workerPort = new Worker(URL.createObjectURL(new Blob([wsrc], { type: 'text/javascript' })));
  return pdfjs;
}
const R = { doc: null, name: '', sourceId: '', scale: 1, pages: [], labels: null, texts: {}, obs: null, renderGen: 0, buf: null };
function readerOpen() { return !$('#reader').classList.contains('hidden'); }
function showReader(on = true) {
  $('#reader').classList.toggle('hidden', !on); document.body.classList.toggle('reader-on', on);
  if (on) { const w = PREFS.readerWidth || Math.round(window.innerWidth * 0.42); $('#reader').style.width = Math.max(320, Math.min(w, window.innerWidth * 0.7)) + 'px'; fillReaderSources(); }
}
function fillReaderSources() {
  $('#rdSource').innerHTML = '<option value="">Link this PDF to a source…</option><option value="__new">+ New source from this PDF</option>' +
    sortedSources().map(s => { const l = sourceLabel(s); return `<option value="${s.id}" ${s.id === R.sourceId ? 'selected' : ''}>${esc((l.who ? l.who + ', ' : '') + l.title).slice(0, 60)}</option>`; }).join('');
}
async function openPdfFile(file, sourceId = '') {
  const buf = await file.arrayBuffer();
  await openPdfData(buf, file.name, sourceId);
}
async function openPdfData(buf, name, sourceId = '') {
  showReader(true);
  $('#rdPages').innerHTML = '<div class="rd-empty">Opening…</div>';
  let lib;
  try { lib = await loadPdfjs(); } catch (e) { console.error(e); $('#rdPages').innerHTML = '<div class="rd-empty">This browser couldn’t start the PDF reader.</div>'; return; }
  if (R.doc) { try { R.doc.destroy(); } catch (e) {} }
  R.buf = buf.slice(0); // pdf.js takes ownership of the buffer it's given
  let doc;
  try { doc = await lib.getDocument({ data: new Uint8Array(buf), isEvalSupported: false, enableXfa: false }).promise; }
  catch (e) { $('#rdPages').innerHTML = `<div class="rd-empty">Couldn’t open that PDF${e && e.name === 'PasswordException' ? ' (it’s password-protected)' : ''}.</div>`; return; }
  Object.assign(R, { doc, name, sourceId: sourceId || '', pages: [], texts: {}, labels: null });
  try { R.labels = await doc.getPageLabels(); } catch (e) { R.labels = null; }
  const s = P.sources.find(x => x.id === R.sourceId);
  $('#rdOffset').value = s && s.pdfOffset ? s.pdfOffset : '';
  $('#rdName').textContent = name; $('#rdName').title = name;
  fillReaderSources();
  const first = await doc.getPage(1), vp1 = first.getViewport({ scale: 1 });
  const avail = $('#rdPages').clientWidth - 28;
  R.scale = PREFS.readerZoom || Math.max(0.5, Math.min(2.2, avail / vp1.width));
  R.base = { w: vp1.width, h: vp1.height };
  layoutPages();
  if (R.sourceId) { pdfStore.set(R.sourceId, { name, buf: R.buf }).catch(() => {}); }
  else suggestSourceFromPdf();
}
function layoutPages() {
  const box = $('#rdPages'); box.innerHTML = ''; R.pages = []; R.renderGen++;
  if (R.obs) R.obs.disconnect();
  R.obs = new IntersectionObserver(ents => ents.forEach(en => { if (en.isIntersecting) renderPage(+en.target.dataset.n); }), { root: box, rootMargin: '800px 0px' });
  for (let i = 1; i <= R.doc.numPages; i++) {
    const d = document.createElement('div'); d.className = 'rd-page'; d.dataset.n = i;
    d.style.width = Math.floor(R.base.w * R.scale) + 'px'; d.style.height = Math.floor(R.base.h * R.scale) + 'px';
    d.innerHTML = `<span class="rd-pnum">${esc(pageLabel(i))}</span>`;
    box.appendChild(d); R.pages.push({ div: d, done: false }); R.obs.observe(d);
  }
  $('#rdOf').textContent = '/ ' + R.doc.numPages;
  $('#rdZoom').textContent = Math.round(R.scale * 100) + '%';
}
async function renderPage(n) {
  const rec = R.pages[n - 1]; if (!rec || rec.done) return; rec.done = true;
  const gen = R.renderGen, page = await R.doc.getPage(n); if (gen !== R.renderGen) return;
  const vp = page.getViewport({ scale: R.scale }), d = rec.div, dpr = window.devicePixelRatio || 1;
  d.style.width = Math.floor(vp.width) + 'px'; d.style.height = Math.floor(vp.height) + 'px';
  d.style.setProperty('--scale-factor', R.scale); d.style.setProperty('--total-scale-factor', R.scale);
  const c = document.createElement('canvas'); c.width = Math.floor(vp.width * dpr); c.height = Math.floor(vp.height * dpr);
  c.style.width = Math.floor(vp.width) + 'px'; c.style.height = Math.floor(vp.height) + 'px';
  const tl = document.createElement('div'); tl.className = 'textLayer';
  d.prepend(c); d.appendChild(tl);
  try { await page.render({ canvasContext: c.getContext('2d'), viewport: vp, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise; } catch (e) { if (e && e.name !== 'RenderingCancelledException') console.warn(e); }
  if (gen !== R.renderGen) return;
  try { await new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: tl, viewport: vp }).render(); } catch (e) { console.warn(e); }
  if (R.findQ) markFind(d, R.findQ);
}
function pageLabel(n) { return R.labels && R.labels[n - 1] ? R.labels[n - 1] : String(n); }
function printedPage(n) {
  const off = parseInt($('#rdOffset').value, 10);
  if (!isNaN(off) && off !== 0) return String(n - off);
  if (R.labels && R.labels[n - 1]) return R.labels[n - 1];
  return String(n);
}
function currentPage() {
  const box = $('#rdPages'), top = box.scrollTop + 40;
  let cur = 1; for (const p of R.pages) { if (p.div.offsetTop <= top) cur = +p.div.dataset.n; else break; }
  return cur;
}
function goPage(n) { n = Math.max(1, Math.min(R.doc?.numPages || 1, n)); const p = R.pages[n - 1]; if (p) $('#rdPages').scrollTop = p.div.offsetTop - 8; $('#rdPage').value = n; }
$('#rdPages').addEventListener('scroll', debounce(() => { if (R.doc) $('#rdPage').value = currentPage(); }, 80));
$('#rdPage').addEventListener('keydown', e => { if (e.key === 'Enter') goPage(parseInt(e.target.value, 10) || 1); });
$('#rdPrev').addEventListener('click', () => R.doc && goPage(currentPage() - 1));
$('#rdNext').addEventListener('click', () => R.doc && goPage(currentPage() + 1));
function setZoom(z) {
  if (!R.doc) return; const cur = currentPage();
  R.scale = Math.max(0.4, Math.min(3, z)); PREFS.readerZoom = R.scale; savePrefs(); layoutPages(); goPage(cur);
}
$('#rdZoomIn').addEventListener('click', () => setZoom(R.scale * 1.15));
$('#rdZoomOut').addEventListener('click', () => setZoom(R.scale / 1.15));
$('#rdFit').addEventListener('click', () => { PREFS.readerZoom = 0; if (R.doc) setZoom(($('#rdPages').clientWidth - 28) / R.base.w); PREFS.readerZoom = 0; savePrefs(); });
$('#rdClose').addEventListener('click', () => { showReader(false); $('#rdSelBar').classList.add('hidden'); });
$('#rdOpen').addEventListener('click', () => $('#filePdf').click());
$('#filePdf').addEventListener('change', e => { const f = e.target.files[0]; e.target.value = ''; if (f) openPdfFile(f, R.pendingSource || ''); R.pendingSource = ''; });
$('#rdOffset').addEventListener('change', () => { const s = P.sources.find(x => x.id === R.sourceId); if (s) { s.pdfOffset = parseInt($('#rdOffset').value, 10) || 0; markDirty(); } updateSelBar(); });
$('#rdSource').addEventListener('change', async e => {
  const v = e.target.value;
  if (v === '__new') { const s = await sourceFromPdf(); if (s) { R.sourceId = s.id; fillReaderSources(); } else e.target.value = ''; }
  else R.sourceId = v;
  if (R.sourceId && R.buf) { const s = P.sources.find(x => x.id === R.sourceId); s.pdfName = R.name; markDirty(); pdfStore.set(R.sourceId, { name: R.name, buf: R.buf }).then(() => toast('PDF linked to the source and kept in this browser for next time.')).catch(() => toast('Linked. (This browser couldn’t store the PDF itself, so you’ll reopen the file next time.)')); }
});
/* resize handle */
$('#rdResize').addEventListener('pointerdown', e => {
  e.preventDefault(); const startX = e.clientX, startW = $('#reader').offsetWidth;
  const mv = ev => { const w = Math.max(320, Math.min(window.innerWidth * 0.7, startW + (startX - ev.clientX))); $('#reader').style.width = w + 'px'; };
  const up = () => { document.removeEventListener('pointermove', mv); document.removeEventListener('pointerup', up); PREFS.readerWidth = $('#reader').offsetWidth; savePrefs(); if (R.doc && !PREFS.readerZoom) $('#rdFit').click(); };
  document.addEventListener('pointermove', mv); document.addEventListener('pointerup', up);
});
/* text of a page (cached) */
async function pageText(n) {
  if (R.texts[n] != null) return R.texts[n];
  const page = await R.doc.getPage(n), tc = await page.getTextContent();
  return (R.texts[n] = tc.items.map(i => i.str + (i.hasEOL ? '\n' : '')).join(''));
}
/* source from PDF metadata (+ DOI on the first pages) */
async function pdfMeta() {
  let info = {}; try { info = (await R.doc.getMetadata()).info || {}; } catch (e) {}
  let text = ''; for (let i = 1; i <= Math.min(2, R.doc.numPages); i++) text += await pageText(i) + '\n';
  const doi = (text.match(/\b(10\.\d{4,9}\/[^\s"<>]+[^\s"<>.,;)\]])/) || [])[1];
  return { info, doi };
}
async function sourceFromPdf() {
  if (!R.doc) return null;
  const { info, doi } = await pdfMeta();
  let csl = null;
  if (doi) { try { csl = await lookupId(doi); takePartial(csl); } catch (e) { csl = null; } }
  if (!csl) {
    csl = { type: R.doc.numPages > 120 ? 'book' : 'report', title: (info.Title || '').trim() || R.name.replace(/\.pdf$/i, '').replace(/[_-]+/g, ' ') };
    const au = String(info.Author || '').split(/\s*(?:;|\band\b|&)\s*/).map(a => a.trim()).filter(Boolean);
    if (au.length) csl.author = au.map(nameFromOsint).filter(Boolean);
    const y = String(info.CreationDate || '').match(/D:(\d{4})/); if (y) csl.issued = { 'date-parts': [[+y[1]]] };
    if (doi) csl.DOI = doi;
  }
  const s = addSource(csl); s.pdfName = R.name; markDirty();
  toast(doi && csl.title ? 'Source created from the PDF’s DOI. Check the details.' : 'Source created from the PDF’s properties. Check the title, author and date.');
  return s;
}
async function suggestSourceFromPdf() {
  // if a source with this DOI already exists, link it automatically
  try {
    const { doi } = await pdfMeta();
    if (doi) { const s = P.sources.find(x => (x.csl.DOI || '').toLowerCase() === doi.toLowerCase()); if (s) { R.sourceId = s.id; fillReaderSources(); pdfStore.set(s.id, { name: R.name, buf: R.buf }).catch(() => {}); toast('Matched this PDF to “' + (s.csl.title || 'source') + '” by its DOI.'); return; } }
  } catch (e) {}
  $('#rdSource').classList.add('nudge'); setTimeout(() => $('#rdSource').classList.remove('nudge'), 2500);
}
/* selection → note */
function readerSelection() {
  const sel = getSelection(); if (!sel.rangeCount || sel.isCollapsed) return null;
  const node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
  const pg = node && node.closest('#rdPages .rd-page'); if (!pg) return null;
  const endNode = sel.focusNode && (sel.focusNode.nodeType === 1 ? sel.focusNode : sel.focusNode.parentElement);
  const pg2 = endNode && endNode.closest('#rdPages .rd-page');
  const text = sel.toString().replace(/(\w)-\s*\n\s*(\w)/g, '$1$2').replace(/\s*\n\s*/g, ' ').replace(/\s{2,}/g, ' ').trim();
  if (!text) return null;
  const a = +pg.dataset.n, b = pg2 ? +pg2.dataset.n : a;
  const pa = printedPage(Math.min(a, b)), pb = printedPage(Math.max(a, b));
  return { text, page: pa === pb ? pa : pa + '–' + pb };
}
function updateSelBar() {
  const s = readerOpen() && readerSelection();
  $('#rdSelBar').classList.toggle('hidden', !s);
  if (s) $('#rdSelPage').textContent = `p. ${s.page} · ${wc(s.text)} words`;
}
document.addEventListener('selectionchange', debounce(updateSelBar, 120));
$('#rdSelBar').addEventListener('mousedown', e => e.preventDefault());
$('#rdSelBar').addEventListener('click', async e => {
  const k = e.target.closest('button')?.dataset.k; if (!k) return;
  const s = readerSelection(); if (!s) return;
  if (!R.sourceId) { const src = await sourceFromPdf(); if (!src) return; R.sourceId = src.id; fillReaderSources(); pdfStore.set(src.id, { name: R.name, buf: R.buf }).catch(() => {}); }
  const n = newNote(); n.kind = k; n.sourceId = R.sourceId; n.locator = s.page; n.label = 'page';
  n.body = s.text; n.title = s.text.split(/\s+/).slice(0, 7).join(' ') + (wc(s.text) > 7 ? '…' : '');
  P.notes.unshift(n); renderNoteList(); renderBoard(); markDirty();
  getSelection().removeAllRanges(); updateSelBar();
  if (k === 'paraphrase') { openNote(n.id, true); toast('Paraphrase started from the passage. Rewrite it in your own words.'); }
  else toast(`Quote note saved (p. ${s.page}).`);
});
/* find in PDF */
function markFind(div, q) {
  $$('.textLayer span', div).forEach(sp => sp.classList.toggle('rd-hit', !!q && sp.textContent.toLowerCase().includes(q)));
}
$('#rdFind').addEventListener('keydown', async e => {
  if (e.key !== 'Enter' || !R.doc) return;
  const q = e.target.value.trim().toLowerCase(); R.findQ = q;
  R.pages.forEach(p => p.done && markFind(p.div, q));
  if (!q) { $('#rdFindN').textContent = ''; return; }
  const start = currentPage(), N = R.doc.numPages;
  $('#rdFindN').textContent = '…';
  for (let k = 1; k <= N; k++) {
    const n = ((start - 1 + k) % N) + 1;
    const t = (await pageText(n)).toLowerCase().replace(/\s+/g, ' ');
    if (t.includes(q)) { goPage(n); $('#rdFindN').textContent = 'p. ' + pageLabel(n); return; }
  }
  $('#rdFindN').textContent = 'not found';
});
/* entry points */
async function readSourcePdf(id) {
  const rec = await pdfStore.get(id).catch(() => null);
  if (rec && rec.buf) { openPdfData(rec.buf, rec.name || 'document.pdf', id); return; }
  R.pendingSource = id; showReader(true); $('#filePdf').click();
}
$('#btnReader').addEventListener('click', () => { if (R.doc) showReader(true); else { showReader(true); $('#filePdf').click(); } });
document.addEventListener('dragover', e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) e.preventDefault(); });
document.addEventListener('drop', e => {
  const f = [...(e.dataTransfer?.files || [])].find(f => /\.pdf$/i.test(f.name) || f.type === 'application/pdf');
  if (f) { e.preventDefault(); openPdfFile(f); return; }
  const d = [...(e.dataTransfer?.files || [])].find(f => /\.docx$/i.test(f.name)); if (d) { e.preventDefault(); importDocx(d); }
});

/* ================================================================
   Index
   ================================================================ */
let ixTarget = null;
function ixMarkerHTML(term) { return `<span class="ixm" contenteditable="false" data-ix="${esc(term)}"></span>`; }
function openIndexMark(m = null) {
  ixTarget = m;
  const sel = getSelection(), selText = !m && sel.rangeCount && editor.contains(sel.anchorNode) ? sel.toString().trim().replace(/\s+/g, ' ') : '';
  const [main, sub] = m ? m.dataset.ix.split(':') : [selText.slice(0, 80), ''];
  $('#ixMain').value = main || ''; $('#ixSub').value = sub || ''; $('#ixAll').checked = false;
  $('#ixAllRow').classList.toggle('hidden', !!m); $('#ixRemove').classList.toggle('hidden', !m);
  $('#ixDlg').showModal(); setTimeout(() => $('#ixMain').focus(), 30);
}
$('#ixCancel').addEventListener('click', () => $('#ixDlg').close());
$('#ixRemove').addEventListener('click', () => { if (ixTarget) { ixTarget.remove(); onEdit(); renderOutlineSoon(); } $('#ixDlg').close(); });
$('#ixOk').addEventListener('click', () => {
  const main = $('#ixMain').value.trim().replace(/:/g, ' '), sub = $('#ixSub').value.trim().replace(/:/g, ' ');
  if (!main) { toast('Type the index entry.'); return; }
  const term = sub ? main + ':' + sub : main;
  $('#ixDlg').close();
  if (ixTarget) { ixTarget.dataset.ix = term; onEdit(); renderOutlineSoon(); return; }
  if ($('#ixAll').checked) {
    if (!P.indexTerms.some(t => t.term.toLowerCase() === main.toLowerCase() && (t.sub || '').toLowerCase() === sub.toLowerCase())) P.indexTerms.push({ id: uid('x'), term: main, sub, match: [], see: '', seeAlso: '' });
    markDirty(); renderOutlineSoon(); toast(`“${main}” added to index terms. Every occurrence will be indexed.`); return;
  }
  restoreSelection();
  const s = getSelection(); if (s.rangeCount) { const r = snapRange(s.getRangeAt(0)); r.collapse(false); const t = document.createElement('template'); t.innerHTML = ixMarkerHTML(term); const node = t.content.firstChild; r.insertNode(node); const after = document.createRange(); after.setStartAfter(node); after.collapse(true); s.removeAllRanges(); s.addRange(after); savedRange = after.cloneRange(); }
  onEdit(); renderOutlineSoon(); toast('Index entry marked.');
});
$('#ixMain').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#ixOk').click(); } });
$('#ixSub').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#ixOk').click(); } });
editor.addEventListener('click', e => { const m = e.target.closest('.ixm'); if (m) { e.preventDefault(); openIndexMark(m); } });
$('#btnIndexMark').addEventListener('click', () => openIndexMark());
$('#toolbar').addEventListener('mousedown', e => { if (e.target.closest('#btnIndexMark')) e.preventDefault(); });

const ixSortKey = s => s.toLowerCase().replace(/^(the|a|an)\s+/, '').replace(/^[^\p{L}\p{N}]+/u, '');
function personIndexName(e) {
  if (e.kind !== 'person') return e.name;
  const parts = e.name.trim().split(/\s+/); if (parts.length < 2) return e.name;
  return parts[parts.length - 1] + ', ' + parts.slice(0, -1).join(' ');
}
/* Insert index anchors into an export DOM and return the index HTML for the given mode. */
function buildIndex(tmp, mode) {
  const entries = new Map(); let k = 0;
  const entry = main => { const key = main.toLowerCase(); let e = entries.get(key); if (!e) { e = { main, ids: [], subs: new Map(), see: '', seeAlso: '' }; entries.set(key, e); } return e; };
  const add = (main, sub, id) => { main = main.trim(); if (!main) return; const e = entry(main); if (sub) { const sk = sub.toLowerCase(); if (!e.subs.has(sk)) e.subs.set(sk, { sub, ids: [] }); e.subs.get(sk).ids.push(id); } else e.ids.push(id); };
  $$('.ixm', tmp).forEach(m => { const [main, sub] = (m.dataset.ix || '').split(':'); const id = 'ix' + (++k); const a = document.createElement('a'); a.className = 'ix-a'; a.id = id; a.dataset.ix = m.dataset.ix; m.replaceWith(a); add(main, sub || '', id); });
  const terms = P.indexTerms.map(t => ({ main: t.term, sub: t.sub || '', pats: [t.term, ...(t.match || [])].filter(Boolean), see: t.see, seeAlso: t.seeAlso }));
  if (P.indexOpts.names) P.entities.filter(e => e.name.trim()).forEach(e => terms.push({ main: personIndexName(e), sub: '', pats: [e.name], see: '', seeAlso: '' }));
  terms.forEach(t => { if (t.see || t.seeAlso) { const e = entry(t.main); if (t.see) e.see = t.see; if (t.seeAlso) e.seeAlso = t.seeAlso; } });
  const nodes = [], w = document.createTreeWalker(tmp, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentElement.closest('h1,h2,h3,nav.toc,.title-block,sup,mark,a') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  while (w.nextNode()) nodes.push(w.currentNode);
  terms.forEach(t => t.pats.forEach(pat => {
    const re = new RegExp('(^|[^\\p{L}\\p{N}])(' + escRe(pat) + ')(?![\\p{L}\\p{N}])', /\p{Lu}/u.test(pat) ? 'gu' : 'giu');
    const fresh = [];
    for (const tn of nodes.slice()) { // snapshot: pieces split off below are scanned only by later terms
      const hits = []; let m; re.lastIndex = 0;
      while ((m = re.exec(tn.data))) hits.push(m.index + m[1].length);
      hits.reverse().forEach(pos => { const rest = tn.splitText(pos); const id = 'ix' + (++k); const a = document.createElement('a'); a.className = 'ix-a'; a.id = id; a.dataset.ix = t.sub ? t.main + ':' + t.sub : t.main; rest.parentNode.insertBefore(a, rest); add(t.main, t.sub, id); fresh.push(rest); });
    }
    nodes.push(...fresh);
  }));
  if (!entries.size) return '';
  const refs = ids => {
    if (!ids.length) return '';
    if (mode === 'paged') return `<span class="ix-refs">${ids.map(id => `<a class="ixref" href="#${id}"></a>`).join('')}</span>`;
    return `<span class="ix-refs">${ids.map((id, i) => `<a class="ixref" href="#${id}">${i + 1}</a>`).join(', ')}</span>`;
  };
  const sorted = [...entries.values()].filter(e => e.ids.length || e.subs.size || e.see).sort((a, b) => ixSortKey(a.main).localeCompare(ixSortKey(b.main)));
  let letter = '', html = '';
  sorted.forEach(e => {
    const L = (ixSortKey(e.main)[0] || '#').toUpperCase();
    if (L !== letter) { letter = L; html += `<p class="ix-letter">${esc(/\p{L}/u.test(L) ? L : '#')}</p>`; }
    html += `<p class="ix-e">${esc(e.main)}${e.ids.length ? ', ' + refs(e.ids) : ''}${e.see ? `. <i>See</i> ${esc(e.see)}` : ''}${e.seeAlso ? `. <i>See also</i> ${esc(e.seeAlso)}` : ''}</p>`;
    [...e.subs.values()].sort((a, b) => ixSortKey(a.sub).localeCompare(ixSortKey(b.sub))).forEach(s => { html += `<p class="ix-sub">${esc(s.sub)}, ${refs(s.ids)}</p>`; });
  });
  return `<section class="end-sec index"><h2 class="end-h">Index</h2><div class="ix-body">${html}</div></section>`;
}
/* script run inside the book-style PDF after layout: real page numbers, de-duplicated, ranges joined */
const IX_PAGES_JS = `function cpIndexPages(){document.querySelectorAll('.ix-refs').forEach(function(sp){var ps=[];sp.querySelectorAll('a.ixref').forEach(function(a){var t=document.getElementById(a.getAttribute('href').slice(1));var pg=t&&t.closest('.pagedjs_page');if(pg)ps.push(+pg.getAttribute('data-page-number'));});var u=ps.filter(function(v,i,a){return v&&a.indexOf(v)===i}).sort(function(a,b){return a-b});var out=[];for(var i=0;i<u.length;i++){var j=i;while(j+1<u.length&&u[j+1]===u[j]+1)j++;out.push(j>i+1?u[i]+'\\u2013'+u[j]:(j===i+1?u[i]+', '+u[j]:String(u[i])));i=j;}sp.textContent=out.join(', ');});}`;
function indexStats() {
  syncEditor();
  let marks = 0; P.docs.forEach(d => { marks += (d.html.match(/class="ixm"/g) || []).length; });
  return { marks, terms: P.indexTerms.length, names: P.indexOpts.names ? P.entities.length : 0 };
}
function openIndexManager() { renderIndexManager(); $('#ixManDlg').showModal(); }
function renderIndexManager() {
  $('#ixNames').checked = !!P.indexOpts.names;
  $('#ixTerms').innerHTML = P.indexTerms.length ? P.indexTerms.map(t => `<div class="ixrow" data-x="${t.id}"><input data-k="term" value="${esc(t.term)}" placeholder="Entry"><input data-k="sub" value="${esc(t.sub || '')}" placeholder="Subentry (optional)"><input data-k="match" value="${esc((t.match || []).join(', '))}" placeholder="Also match (comma-separated)"><input data-k="seeAlso" value="${esc(t.seeAlso || '')}" placeholder="See also"><button class="ghost danger" data-k="del">✕</button></div>`).join('')
    : '<div class="small muted">No index terms yet. Terms listed here are found and indexed everywhere they appear, which suits names, places, organizations and key concepts.</div>';
  const st = indexStats();
  $('#ixStat').textContent = `${st.marks} marked entr${st.marks === 1 ? 'y' : 'ies'} in the text · ${st.terms} term${st.terms === 1 ? '' : 's'} indexed everywhere${P.indexOpts.names ? ` · ${P.entities.length} names from Names & spellings` : ''}`;
}
$('#ixTerms').addEventListener('input', e => {
  const row = e.target.closest('.ixrow'); if (!row) return; const t = P.indexTerms.find(x => x.id === row.dataset.x), k = e.target.dataset.k;
  if (k === 'match') t.match = e.target.value.split(',').map(x => x.trim()).filter(Boolean); else t[k] = e.target.value;
  markDirty();
});
$('#ixTerms').addEventListener('click', e => { const b = e.target.closest('[data-k=del]'); if (!b) return; P.indexTerms = P.indexTerms.filter(x => x.id !== b.closest('.ixrow').dataset.x); renderIndexManager(); markDirty(); });
$('#ixAddTerm').addEventListener('click', () => { P.indexTerms.push({ id: uid('x'), term: '', sub: '', match: [], see: '', seeAlso: '' }); renderIndexManager(); $$('#ixTerms .ixrow:last-child input')[0]?.focus(); });
$('#ixNames').addEventListener('change', e => { P.indexOpts.names = e.target.checked; markDirty(); renderIndexManager(); });
$('#ixPreview').addEventListener('click', () => {
  syncEditor(); const tmp = document.createElement('div'); tmp.innerHTML = binderOrder().map(d => stripCp(d.html)).join('');
  const h = buildIndex(tmp, 'html');
  $('#ixPrev').innerHTML = h ? h.replace(/<a class="ixref"[^>]*>(\d+)<\/a>/g, '$1').replace(/<span class="ix-refs">([^<]*)<\/span>/g, (m, s) => `<span class="muted">${s.split(', ').length}×</span>`) : '<p class="muted">Nothing to index yet.</p>';
  $('#ixPrev').classList.remove('hidden');
});
$('#ixManClose').addEventListener('click', () => { P.indexTerms = P.indexTerms.filter(t => t.term.trim()); $('#ixManDlg').close(); renderOutlineSoon(); });
$('#btnIndexMgr').addEventListener('click', openIndexManager);

/* ================================================================
   Start fresh
   ================================================================ */
function openFresh() { $('#frBackup').checked = true; $$('#freshDlg input[name=frMode]')[0].checked = true; $('#freshDlg').showModal(); }
$('#frCancel').addEventListener('click', () => $('#freshDlg').close());
$('#frOk').addEventListener('click', async () => {
  const mode = $('#freshDlg input[name=frMode]:checked').value;
  if ($('#frBackup').checked) download(fileSafe(P.title) + ' (backup ' + todayKey() + ').json', await projectFileText(), 'application/json');
  $('#freshDlg').close();
  if (mode === 'all') {
    try { const keys = Object.keys(localStorage).filter(k => k.startsWith('commonplace.')); keys.forEach(k => localStorage.removeItem(k)); } catch (e) {}
    try { await new Promise(res => { const r = indexedDB.deleteDatabase('commonplace'); r.onsuccess = r.onerror = r.onblocked = () => res(); }); } catch (e) {}
    lsSet('commonplace.fresh', '1');
    dirtyFile = false; window.onbeforeunload = null;
    setTimeout(() => location.reload(), 600);
    return;
  }
  try { (await pdfStore.keys() || []).filter(k => String(k).startsWith('pdf:')).forEach(k => pdfStore.del(String(k).slice(4))); } catch (e) {}
  P = blankProject(); P.docs.push(newDoc()); LOCK = null; document.body.classList.remove('locked'); pendingHandle = null;
  fileHandle = null; dirtyFile = false; dirtySince = null; lastFileSave = null; lastFileName = ''; srcVersion++;
  if (R.doc) { try { R.doc.destroy(); } catch (e) {} R.doc = null; } showReader(false); closeBoard();
  closePanel(); openDoc(P.docs[0].id, true); renderAll(); persistLocal(); updateSaveState();
  toast('Fresh start: a blank project. Your settings are kept.');
});
$('#btnFresh').addEventListener('click', () => { $('#settingsDlg').close(); openFresh(); });

/* ================================================================
   Planning: planner (outliner · cards · check), build drafts, freewrite,
   and the Outline tab as a structure editor
   ================================================================ */
const PT = {
  section: { label: 'Section', icon: '§', status: ['', 'todo', 'drafting', 'done'] },
  claim: { label: 'Claim', icon: 'C', status: ['', 'todo', 'drafting', 'done'] },
  evidence: { label: 'Evidence', icon: 'E', status: ['', 'todo', 'found', 'done'] },
  counter: { label: 'Counterpoint', icon: '↺', status: ['', 'todo', 'answered'] },
  question: { label: 'Research question', icon: '?', status: ['open', 'answered'] },
  idea: { label: 'Idea', icon: '✦', status: ['', 'keep', 'cut'] },
};
const PLI = () => P.plan.items;
const plKids = pid => PLI().filter(i => (i.parent || '') === (pid || '')).sort((a, b) => a.order - b.order);
const plItem = id => PLI().find(i => i.id === id);
function plOutdent(it) {
  const p = plItem(it.parent); if (!p) return;
  it.parent = p.parent; const ps = plKids(p.parent).filter(x => x !== it); ps.splice(ps.indexOf(p) + 1, 0, it); ps.forEach((x, k) => x.order = k); plRenumber(p.id);
}
function plRenumber(pid) { plKids(pid).forEach((x, k) => x.order = k); }
function plDescendants(id) { const out = []; plKids(id).forEach(k => { out.push(k); out.push(...plDescendants(k.id)); }); return out; }
function plNewItem(parent = '', afterId = null, props = {}) {
  const p = plItem(parent);
  const type = props.type || (p && p.type === 'claim' ? 'evidence' : p && p.type === 'counter' ? 'claim' : p && p.type === 'question' ? 'idea' : 'section');
  const it = Object.assign({ id: uid('pl'), parent: parent || '', order: 0, title: '', type, synopsis: '', status: type === 'question' ? 'open' : '', target: 0, notes: [], sources: [], docId: '', collapsed: false }, props);
  const sib = plKids(parent);
  const idx = afterId ? sib.findIndex(x => x.id === afterId) + 1 : sib.length;
  sib.splice(idx, 0, it); PLI().push(it); sib.forEach((x, k) => x.order = k);
  return it;
}
let plSel = null, planOn = false;
function openPlan() {
  syncEditor(); if (boardOn) closeBoard(); if (homeOn) closeHome(); if (draftsOn) closeDrafts(); if (relOn) closeRel();
  planOn = true; document.body.classList.add('plan-on'); $('#plan').classList.remove('hidden');
  $('#plView').value = PREFS.planView || 'outline'; renderPlan(); document.body.classList.remove('side-open');
}
function closePlan() { planOn = false; document.body.classList.remove('plan-on'); $('#plan').classList.add('hidden'); }
$('#btnPlan').addEventListener('click', openPlan);
$('#plBack').addEventListener('click', () => { closePlan(); openDoc(curDocId); });
$('#plView').addEventListener('change', e => { PREFS.planView = e.target.value; savePrefs(); renderPlan(); });

/* coverage: how much of a plan item is drafted */
function docSectionWords(doc, title) {
  const t = document.createElement('div'); t.innerHTML = doc.id === curDocId ? editor.innerHTML : doc.html;
  const want = title.trim().toLowerCase(); let on = false, lvl = 0, n = 0;
  [...t.children].forEach(el => {
    const h = /^H([1-3])$/.exec(el.nodeName);
    if (h) { if (on && +h[1] <= lvl) on = false; if (el.textContent.trim().toLowerCase() === want) { on = true; lvl = +h[1]; return; } }
    if (on) { $$('.cite,.fn,.flag', el).forEach(m => m.remove()); n += wc(el.textContent); }
  });
  return n;
}
function plDocOf(it) { let x = it; while (x) { if (x.docId && P.docs.some(d => d.id === x.docId)) return P.docs.find(d => d.id === x.docId); x = plItem(x.parent); } return null; }
function plCoverage(it) {
  const d = plDocOf(it); if (!d) return null;
  const words = d.id === it.docId ? docWords(d) : docSectionWords(d, it.title);
  return { words, target: it.target || 0, doc: d };
}
function plBadges(it) {
  const cov = plCoverage(it), st = it.status;
  return `${st ? `<span class="st st-${st}">${esc(st)}</span>` : ''}${it.notes.length ? `<span class="pl-link" title="Linked notes">▤ ${it.notes.length}</span>` : ''}${it.sources.length ? `<span class="pl-link" title="Linked sources">❝ ${it.sources.length}</span>` : ''}${cov ? `<span class="pl-cov" title="Drafted words${cov.target ? ' / target' : ''}">${cov.words.toLocaleString()}${cov.target ? ' / ' + cov.target.toLocaleString() : ' words'}${cov.target ? `<span class="bar"><i style="width:${Math.min(100, cov.words / cov.target * 100)}%"></i></span>` : ''}</span>` : it.target ? `<span class="pl-cov muted">target ${it.target.toLocaleString()}</span>` : ''}`;
}
function plRoot() { return P.plan.hoist && plItem(P.plan.hoist) ? P.plan.hoist : ''; }
function renderPlan() {
  if (!planOn) return;
  const view = PREFS.planView || 'outline', root = plRoot();
  // breadcrumb
  const crumbs = []; let x = plItem(root); while (x) { crumbs.unshift(x); x = plItem(x.parent); }
  $('#plCrumbs').innerHTML = `<a href="#" data-h="">Plan</a>` + crumbs.map(c => ` › <a href="#" data-h="${c.id}">${esc(c.title || 'Untitled')}</a>`).join('');
  const area = $('#plArea');
  if (view === 'cards') { area.className = 'pl-area cards'; area.innerHTML = renderPlanCards(root); return; }
  if (view === 'check') { area.className = 'pl-area check'; area.innerHTML = renderPlanCheck(); return; }
  area.className = 'pl-area outline';
  const rows = [];
  (function walk(pid, d) { plKids(pid).forEach(it => { rows.push({ it, d }); if (!it.collapsed) walk(it.id, d + 1); }); })(root, 0);
  area.innerHTML = rows.length ? rows.map(({ it, d }) => {
    const has = plKids(it.id).length, T = PT[it.type] || PT.section;
    return `<div class="pl-row ty-${it.type} ${plSel === it.id ? 'sel' : ''}" data-id="${it.id}" style="--d:${d}">
      <button class="pl-caret ghost" tabindex="-1" title="${has ? (it.collapsed ? 'Expand' : 'Collapse') : ''}">${has ? (it.collapsed ? '▸' : '▾') : '·'}</button>
      <span class="pl-type" title="${T.label}">${T.icon}</span>
      <input class="pl-title" value="${esc(it.title)}" placeholder="${T.label}…">
      <span class="pl-meta">${plBadges(it)}</span><span class="pl-grip" title="Drag to move">⠿</span>
    </div>${it.synopsis ? `<div class="pl-syn" style="--d:${d}">${esc(it.synopsis.length > 220 ? it.synopsis.slice(0, 220) + '…' : it.synopsis)}</div>` : ''}`;
  }).join('') + '<div class="pl-end" data-end="1"></div>'
    : `<div class="empty pl-empty"><b>Plan before you draft.</b><br>Click <b>+ Item</b> or pick a template. In the outline, Enter adds a line, Tab indents, Shift+Tab outdents, Alt+↑/↓ moves an item, and ⌘/Ctrl+. folds it.<br>Mark items as claims, evidence, counterpoints or research questions, and <b>Check</b> finds the gaps in your argument.</div>`;
}
function renderPlanCards(root) {
  const items = plKids(root);
  return items.length ? `<div class="pl-cards">${items.map(it => { const T = PT[it.type] || PT.section, n = plKids(it.id).length; return `<div class="pl-card ty-${it.type} ${plSel === it.id ? 'sel' : ''}" data-id="${it.id}" draggable="true">
    <div class="pl-card-top"><span class="pl-type">${T.icon}</span><b>${esc(it.title || 'Untitled')}</b></div>
    <div class="pl-card-syn">${esc(it.synopsis || '')}${it.synopsis ? '' : '<span class="muted">No synopsis yet.</span>'}</div>
    <div class="pl-card-meta">${plBadges(it)}${n ? `<a href="#" class="pl-open" data-h="${it.id}">${n} inside ›</a>` : ''}</div></div>`; }).join('')}</div>`
    : '<div class="empty">Nothing at this level yet.</div>';
}
function plIssues() {
  const out = [];
  const linked = it => it.notes.length || it.sources.length;
  PLI().forEach(it => {
    const k = plKids(it.id);
    if (it.type === 'claim' && !k.some(c => c.type === 'evidence') && !linked(it)) out.push({ it, sev: 2, msg: 'Claim has no evidence under it and no linked notes or sources.' });
    if (it.type === 'evidence' && !linked(it)) out.push({ it, sev: 2, msg: 'Evidence isn’t linked to a note or source yet.' });
    if (it.type === 'counter' && it.status !== 'answered' && !k.length) out.push({ it, sev: 2, msg: 'Counterpoint has no response.' });
    if (it.type === 'question' && it.status !== 'answered') out.push({ it, sev: 1, msg: `Open research question${linked(it) ? ` (${it.notes.length} note${it.notes.length === 1 ? '' : 's'} so far)` : ''}.` });
    if ((it.type === 'section' || it.type === 'claim') && !it.synopsis && !k.length) out.push({ it, sev: 0, msg: 'No synopsis or sub-points yet.' });
    const cov = plCoverage(it); if (cov && cov.target && cov.words < cov.target * 0.5 && it.status !== 'done') out.push({ it, sev: 0, msg: `Drafted ${cov.words.toLocaleString()} of ${cov.target.toLocaleString()} words.` });
  });
  return out.sort((a, b) => b.sev - a.sev);
}
function renderPlanCheck() {
  const iss = plIssues(), claims = PLI().filter(i => i.type === 'claim').length, ev = PLI().filter(i => i.type === 'evidence').length, ctr = PLI().filter(i => i.type === 'counter').length, q = PLI().filter(i => i.type === 'question');
  const head = `<div class="pl-stats"><div><b>${claims}</b><span>claims</span></div><div><b>${ev}</b><span>evidence</span></div><div><b>${ctr}</b><span>counterpoints</span></div><div><b>${q.filter(x => x.status !== 'answered').length}/${q.length}</b><span>questions open</span></div></div>`;
  return head + (iss.length ? `<ul class="pl-issues">${iss.map(x => `<li data-id="${x.it.id}" class="sev${x.sev}"><span class="pl-type ty-${x.it.type}">${(PT[x.it.type] || PT.section).icon}</span><b>${esc(x.it.title || 'Untitled')}</b><span>${esc(x.msg)}</span></li>`).join('')}</ul>`
    : '<div class="empty">No gaps found. Every claim has support, every counterpoint has an answer, and no questions are open.</div>');
}
const renderPlanSoon = debounce(renderPlan, 250);
function plFocus(id, caretEnd = true) {
  // synchronous on purpose: a deferred focus drops the first keystrokes of a fast typist
  const inp = $(`#plArea .pl-row[data-id="${id}"] .pl-title`); if (inp) { inp.focus(); if (caretEnd) inp.setSelectionRange(inp.value.length, inp.value.length); }
}
function plSelect(id) {
  plSel = id; $$('#plArea .sel').forEach(r => r.classList.toggle('sel', r.dataset.id === id));
  $$('#plArea [data-id="' + id + '"]').forEach(r => r.classList.add('sel'));
  openPlanItem(id);
}
$('#plCrumbs').addEventListener('click', e => { const a = e.target.closest('[data-h]'); if (!a) return; e.preventDefault(); P.plan.hoist = a.dataset.h; renderPlan(); markDirty(); });
$('#plArea').addEventListener('focusin', e => { const row = e.target.closest('.pl-row'); if (row && plSel !== row.dataset.id) plSelect(row.dataset.id); });
$('#plArea').addEventListener('input', e => {
  if (!e.target.classList.contains('pl-title')) return;
  const it = plItem(e.target.closest('.pl-row').dataset.id); it.title = e.target.value; markDirty();
  if (panelState?.kind === 'plan' && panelState.id === it.id) { const t = $('#panelBody [data-p=title]'); if (t && document.activeElement !== t) t.value = it.title; }
});
$('#plArea').addEventListener('click', e => {
  const open = e.target.closest('.pl-open'); if (open) { e.preventDefault(); P.plan.hoist = open.dataset.h; renderPlan(); return; }
  const car = e.target.closest('.pl-caret'); if (car) { const it = plItem(car.closest('.pl-row').dataset.id); if (plKids(it.id).length) { it.collapsed = !it.collapsed; renderPlan(); markDirty(); } return; }
  const iss = e.target.closest('.pl-issues li'); if (iss) { const it = plItem(iss.dataset.id); let p = plItem(it.parent); while (p) { p.collapsed = false; p = plItem(p.parent); } P.plan.hoist = ''; PREFS.planView = 'outline'; $('#plView').value = 'outline'; renderPlan(); plSelect(it.id); plFocus(it.id); return; }
  const card = e.target.closest('.pl-card'); if (card) { plSelect(card.dataset.id); return; }
  const row = e.target.closest('.pl-row'); if (row && !e.target.closest('input')) plSelect(row.dataset.id);
});
$('#plArea').addEventListener('dblclick', e => { const card = e.target.closest('.pl-card'); if (card && plKids(card.dataset.id).length) { P.plan.hoist = card.dataset.id; renderPlan(); } });
$('#plArea').addEventListener('keydown', e => {
  if (!e.target.classList.contains('pl-title')) return;
  const row = e.target.closest('.pl-row'), it = plItem(row.dataset.id), sib = plKids(it.parent), i = sib.indexOf(it);
  const mod = e.metaKey || e.ctrlKey;
  if (e.key === 'Enter' && !mod) {
    e.preventDefault();
    if (!it.title.trim() && it.parent && it.parent !== plRoot()) { plOutdent(it); renderPlan(); markDirty(); plFocus(it.id); return; } // Enter on an empty line steps out a level
    let n;
    if (plKids(it.id).length && !it.collapsed) { n = plNewItem(it.id); n.order = -1; plRenumber(it.id); }
    else n = plNewItem(it.parent, it.id, ['evidence', 'idea', 'claim', 'question'].includes(it.type) ? { type: it.type } : {});
    renderPlan(); markDirty(); plSelect(n.id); plFocus(n.id); return;
  }
  if (e.key === 'Tab') {
    e.preventDefault();
    if (!e.shiftKey) { const prev = sib[i - 1]; if (!prev) return; it.parent = prev.id; prev.collapsed = false; it.order = 1e6; plRenumber(prev.id); plRenumber(sib[0].parent); }
    else { if (!it.parent || it.parent === plRoot()) return; plOutdent(it); }
    renderPlan(); markDirty(); plFocus(it.id); return;
  }
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault(); const j = e.key === 'ArrowUp' ? i - 1 : i + 1; if (j < 0 || j >= sib.length) return;
    [sib[i], sib[j]] = [sib[j], sib[i]]; sib.forEach((x, k) => x.order = k); renderPlan(); markDirty(); plFocus(it.id); return;
  }
  if (mod && e.key === '.') { e.preventDefault(); if (plKids(it.id).length) { it.collapsed = !it.collapsed; renderPlan(); markDirty(); plFocus(it.id); } return; }
  if (e.key === 'Backspace' && !e.target.value && !plKids(it.id).length) {
    e.preventDefault(); const rows = $$('#plArea .pl-row'), ri = rows.indexOf(row), prevId = rows[ri - 1]?.dataset.id;
    PLI().splice(PLI().indexOf(it), 1); plRenumber(it.parent); if (panelState?.kind === 'plan' && panelState.id === it.id) closePanel(); renderPlan(); markDirty(); if (prevId) { plSelect(prevId); plFocus(prevId); } return;
  }
  if (!e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    const rows = $$('#plArea .pl-row'), ri = rows.indexOf(row), nx = rows[ri + (e.key === 'ArrowUp' ? -1 : 1)];
    if (nx) { e.preventDefault(); $('.pl-title', nx).focus(); }
  }
});
$('#plAdd').addEventListener('click', () => {
  const sel = plItem(plSel), root = plRoot();
  const n = sel && (sel.parent === root || plDescendants(root).includes(sel)) ? plNewItem(sel.parent, sel.id) : plNewItem(root);
  if ((PREFS.planView || 'outline') !== 'outline') { PREFS.planView = 'outline'; $('#plView').value = 'outline'; }
  renderPlan(); markDirty(); plSelect(n.id); plFocus(n.id);
});
/* drag rows (pointer): drop before a row, or onto its right side to nest inside */
let pd = null;
$('#plArea').addEventListener('pointerdown', e => {
  const g = e.target.closest('.pl-grip'); if (!g) return;
  e.preventDefault(); const row = g.closest('.pl-row');
  pd = { id: row.dataset.id, row, started: false, sy: e.clientY };
});
document.addEventListener('pointermove', e => {
  if (!pd) return;
  if (!pd.started) { if (Math.abs(e.clientY - pd.sy) < 4) return; pd.started = true; pd.row.classList.add('dragging'); document.body.classList.add('bd-dragging'); }
  $$('.pl-drop').forEach(x => x.remove());
  const el = document.elementFromPoint(e.clientX, e.clientY), row = el && el.closest('#plArea .pl-row, #plArea .pl-end');
  if (!row || row === pd.row) { pd.to = null; return; }
  const r = row.getBoundingClientRect(), d = +getComputedStyle(row).getPropertyValue('--d') || 0;
  const inside = row.classList.contains('pl-row') && e.clientX > r.left + 90 + d * 22 && e.clientY > r.top + r.height / 2;
  pd.to = { id: row.dataset.id || null, inside };
  const line = document.createElement('div'); line.className = 'pl-drop'; line.style.marginLeft = (inside ? (d + 1) * 22 + 30 : d * 22 + 30) + 'px';
  if (inside) row.after(line); else row.before(line);
});
document.addEventListener('pointerup', () => {
  if (!pd) return; const d = pd; pd = null; document.body.classList.remove('bd-dragging'); $$('.pl-drop').forEach(x => x.remove()); d.row.classList.remove('dragging');
  if (!d.started || !d.to) return;
  const it = plItem(d.id), oldParent = it.parent;
  if (!d.to.id) { it.parent = plRoot(); it.order = 1e6; }
  else {
    const tgt = plItem(d.to.id);
    if (tgt.id === it.id || plDescendants(it.id).includes(tgt)) return;
    if (d.to.inside) { it.parent = tgt.id; it.order = -1; tgt.collapsed = false; }
    else { it.parent = tgt.parent; it.order = tgt.order - 0.5; }
  }
  plRenumber(it.parent); plRenumber(oldParent); renderPlan(); markDirty(); plSelect(it.id);
});
/* cards: native drag to reorder */
let cardDrag = null;
$('#plArea').addEventListener('dragstart', e => { const c = e.target.closest('.pl-card'); if (!c) return; cardDrag = c.dataset.id; e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', cardDrag); } catch (x) {} });
$('#plArea').addEventListener('dragover', e => {
  if (cardDrag && e.target.closest('.pl-card')) e.preventDefault();
  if ([...e.dataTransfer.types].includes('application/x-commonplace-note') && e.target.closest('.pl-row,.pl-card')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }
});
$('#plArea').addEventListener('drop', e => {
  const nid = e.dataTransfer.getData('application/x-commonplace-note');
  const tgtEl = e.target.closest('.pl-row,.pl-card'); if (!tgtEl) return;
  e.preventDefault();
  if (nid) { const it = plItem(tgtEl.dataset.id); if (!it.notes.includes(nid)) it.notes.push(nid); renderPlan(); markDirty(); if (panelState?.kind === 'plan' && panelState.id === it.id) openPlanItem(it.id); toast('Note linked to “' + (it.title || 'item') + '”.'); return; }
  if (!cardDrag) return; const it = plItem(cardDrag), tgt = plItem(tgtEl.dataset.id); cardDrag = null;
  if (!tgt || tgt === it || tgt.parent !== it.parent) return;
  it.order = tgt.order - 0.5; plRenumber(it.parent); renderPlan(); markDirty();
});

/* item panel */
function openPlanItem(id) {
  const it = plItem(id); if (!it) return;
  panelState = { kind: 'plan', id }; $('#panel').classList.remove('hidden'); $('#panelTitle').textContent = (PT[it.type] || PT.section).label;
  const T = PT[it.type] || PT.section;
  const noteChips = it.notes.map(nid => { const n = P.notes.find(x => x.id === nid); return n ? `<span class="chipx"><a href="#" data-on="${n.id}">${esc(noteTitle(n).slice(0, 50))}</a><button class="ghost" data-un="${n.id}" title="Unlink">×</button></span>` : ''; }).join('');
  const srcChips = it.sources.map(sid => { const s = P.sources.find(x => x.id === sid); if (!s) return ''; const l = sourceLabel(s); return `<span class="chipx"><a href="#" data-os="${s.id}">${esc(((l.who ? l.who + ', ' : '') + l.title).slice(0, 50))}</a><button class="ghost" data-us="${s.id}" title="Unlink">×</button></span>`; }).join('');
  const cov = plCoverage(it);
  $('#panelBody').innerHTML = `
    <label>Title</label><input data-p="title" value="${esc(it.title)}">
    <div class="grid2"><div><label>Kind</label><select data-p="type">${Object.entries(PT).map(([k, v]) => `<option value="${k}" ${k === it.type ? 'selected' : ''}>${v.label}</option>`).join('')}</select></div>
    <div><label>Status</label><select data-p="status">${T.status.map(s => `<option value="${s}" ${s === it.status ? 'selected' : ''}>${s || '—'}</option>`).join('')}</select></div></div>
    <label>Synopsis <span class="muted">(what this part must do, in a sentence or two)</span></label><textarea data-p="synopsis" rows="4">${esc(it.synopsis)}</textarea>
    <div class="grid2"><div><label>Word target</label><input data-p="target" inputmode="numeric" value="${it.target || ''}" placeholder="e.g. 4000"></div>
    <div><label>Drafted in</label><select data-p="docId"><option value="">—</option>${binderOrder().map(d => `<option value="${d.id}" ${d.id === it.docId ? 'selected' : ''}>${esc(d.title || 'Untitled')}</option>`).join('')}</select></div></div>
    ${cov ? `<div class="small muted" style="margin-top:6px">Drafted: ${cov.words.toLocaleString()} words in “${esc(cov.doc.title)}”${cov.target ? ` of ${cov.target.toLocaleString()}` : ''}</div>` : ''}
    <label>Linked notes <span class="muted">(or drag notes from the Notes list onto the item)</span></label><div class="chips-x">${noteChips || '<span class="muted small">None yet.</span>'}</div>
    <select data-add="note"><option value="">+ Link a note…</option>${P.notes.filter(n => !it.notes.includes(n.id)).map(n => `<option value="${n.id}">${esc(noteTitle(n).slice(0, 70))}</option>`).join('')}</select>
    <label>Linked sources</label><div class="chips-x">${srcChips || '<span class="muted small">None yet.</span>'}</div>
    <select data-add="source"><option value="">+ Link a source…</option>${sortedSources().filter(s => !it.sources.includes(s.id)).map(s => { const l = sourceLabel(s); return `<option value="${s.id}">${esc(((l.who ? l.who + ', ' : '') + l.title).slice(0, 70))}</option>`; }).join('')}</select>`;
  $('#panelFoot').innerHTML = `${it.docId ? '<button data-pa="opendoc" class="primary">Open draft</button>' : '<button data-pa="build" class="primary">Build draft</button>'}<button data-pa="fw" title="Timed freewrite on this item">Freewrite</button>${plKids(it.id).length ? '<button data-pa="hoist" title="Show only this branch">Focus branch</button>' : ''}<span class="spacer"></span><button class="danger" data-pa="del">Delete</button>`;
}
$('#panelBody').addEventListener('input', e => {
  if (panelState?.kind !== 'plan') return; const it = plItem(panelState.id); if (!it) return; const k = e.target.dataset.p; if (!k) return;
  if (k === 'target') it.target = Math.max(0, parseInt(e.target.value, 10) || 0); else it[k] = e.target.value;
  markDirty();
  if (k === 'title') { const inp = $(`#plArea .pl-row[data-id="${it.id}"] .pl-title`); if (inp) inp.value = it.title; }
  if (k === 'synopsis' || k === 'target') renderPlanSoon();
});
$('#panelBody').addEventListener('change', e => {
  if (panelState?.kind !== 'plan') return; const it = plItem(panelState.id); if (!it) return;
  const k = e.target.dataset.p, add = e.target.dataset.add;
  if (k === 'type') { it.type = e.target.value; if (!PT[it.type].status.includes(it.status)) it.status = PT[it.type].status[0]; openPlanItem(it.id); renderPlan(); markDirty(); }
  if (k === 'status' || k === 'docId') { it[k] = e.target.value; renderPlan(); markDirty(); if (k === 'docId') openPlanItem(it.id); }
  if (add && e.target.value) { (add === 'note' ? it.notes : it.sources).push(e.target.value); openPlanItem(it.id); renderPlan(); markDirty(); }
});
$('#panelBody').addEventListener('click', e => {
  if (panelState?.kind !== 'plan') return; const it = plItem(panelState.id); if (!it) return;
  const t = e.target.closest('[data-un],[data-us],[data-on],[data-os]'); if (!t) return; e.preventDefault();
  if (t.dataset.un) { it.notes = it.notes.filter(x => x !== t.dataset.un); openPlanItem(it.id); renderPlan(); markDirty(); }
  if (t.dataset.us) { it.sources = it.sources.filter(x => x !== t.dataset.us); openPlanItem(it.id); renderPlan(); markDirty(); }
  if (t.dataset.on) openNote(t.dataset.on);
  if (t.dataset.os) openSource(t.dataset.os);
});
$('#panelFoot').addEventListener('click', async e => {
  if (panelState?.kind !== 'plan') return; const a = e.target.closest('button')?.dataset.pa; if (!a) return; const it = plItem(panelState.id); if (!it) return;
  if (a === 'opendoc') { closePlan(); openDoc(it.docId); }
  if (a === 'build') openBuild(it.id);
  if (a === 'fw') openFreewrite(it.id);
  if (a === 'hoist') { P.plan.hoist = it.id; renderPlan(); markDirty(); }
  if (a === 'del') {
    const n = plDescendants(it.id).length;
    if (!(await ask('Delete from plan?', `“${it.title || 'Untitled'}”${n ? ` and the ${n} item${n > 1 ? 's' : ''} under it` : ''} will be removed from the plan. Drafts and notes aren’t affected.`, 'Delete'))) return;
    const gone = new Set([it.id, ...plDescendants(it.id).map(x => x.id)]); P.plan.items = PLI().filter(x => !gone.has(x.id)); if (gone.has(P.plan.hoist)) P.plan.hoist = '';
    closePanel(); plSel = null; renderPlan(); markDirty();
  }
});

/* templates for nonfiction forms */
const PLAN_TEMPLATES = {
  'Argument essay': ['section:Introduction — hook and stakes', ['claim:Thesis', []], 'claim:Point 1', ['evidence:Evidence', 'evidence:Evidence'], 'claim:Point 2', ['evidence:Evidence'], 'claim:Point 3', ['evidence:Evidence'], 'counter:Strongest objection', ['claim:Response'], 'section:Conclusion — so what?'],
  'Policy brief / white paper': ['section:Bottom line up front', 'section:The problem', ['evidence:Scale and trend', 'evidence:Who is affected'], 'section:Background', 'section:Options', ['claim:Option A', ['evidence:Pros and cons'], 'claim:Option B', ['evidence:Pros and cons'], 'claim:Option C', ['evidence:Pros and cons']], 'claim:Recommendation', 'section:Implementation', 'counter:Risks and objections', 'question:What would change this assessment?'],
  'Intelligence brief': ['claim:Key judgments', ['claim:Judgment 1 (confidence: moderate)', 'claim:Judgment 2 (confidence: low)'], 'section:Background', 'section:Analysis', ['evidence:Reporting', 'evidence:Imagery / OSINT'], 'counter:Alternative explanations', 'section:Indicators to watch', 'section:Outlook', 'question:Intelligence gaps'],
  'Op-ed': ['section:Hook (news peg)', 'claim:Argument in one sentence', 'claim:Reason 1', ['evidence:Proof'], 'claim:Reason 2', ['evidence:Proof'], 'counter:“Critics will say…”', ['claim:Answer'], 'section:What should happen now'],
  'Narrative / literary journalism': ['section:Opening scene', 'section:Nut graf — why this matters', 'section:Backstory', 'section:Rising complications', ['section:Scene', 'section:Scene'], 'section:Turn', 'section:Resolution and kicker', 'question:Who else needs to be interviewed?'],
  'Explainer / video script': ['section:Hook (first 30 seconds)', 'section:The promise — what viewers will learn', 'section:Context', 'claim:Main point 1', ['evidence:Example / footage'], 'claim:Main point 2', ['evidence:Example / footage'], 'claim:Main point 3', ['evidence:Example / footage'], 'section:Payoff', 'section:Call to action'],
  'Article series (Substack)': ['section:Series arc — what readers get by the end', ['question:What do readers already believe about this?', 'idea:Running thread across all parts'], 'section:Part 1', ['section:Hook', 'claim:Argument', 'evidence:Key evidence', 'section:Cliffhanger into Part 2'], 'section:Part 2', ['section:Hook', 'claim:Argument', 'evidence:Key evidence', 'section:Cliffhanger into Part 3'], 'section:Part 3', ['section:Hook', 'claim:Argument', 'evidence:Key evidence', 'section:Cliffhanger into Part 4'], 'section:Part 4', ['section:Hook', 'claim:Argument', 'evidence:Key evidence', 'section:Payoff']],
  'Nonfiction book': ['section:Introduction', 'section:Part I', ['section:Chapter 1', 'section:Chapter 2', 'section:Chapter 3'], 'section:Part II', ['section:Chapter 4', 'section:Chapter 5', 'section:Chapter 6'], 'section:Conclusion'],
  'Book proposal': ['section:Overview — the book in two pages', 'section:Audience', 'section:Comparable titles', 'section:About the author', 'section:Marketing and platform', 'section:Chapter-by-chapter outline', 'section:Sample chapter'],
};
function plApplyTemplate(name, parent) {
  const walk = (list, pid) => { let last = null; list.forEach(x => { if (Array.isArray(x)) { if (last) walk(x, last.id); return; } const [type, title] = x.split(/:(.+)/); last = plNewItem(pid, last ? last.id : (plKids(pid).slice(-1)[0] || {}).id || null, { type, title }); }); };
  walk(PLAN_TEMPLATES[name], parent);
}
$('#plTemplates').addEventListener('click', () => {
  $('#ptList').innerHTML = Object.keys(PLAN_TEMPLATES).map(k => `<button class="tpl" data-pt="${esc(k)}"><b>${esc(k)}</b><span>${PLAN_TEMPLATES[k].filter(x => !Array.isArray(x)).slice(0, 4).map(x => x.split(':')[1]).join(' · ')}…</span></button>`).join('');
  $('#ptDlg').showModal();
});
$('#ptList').addEventListener('click', e => {
  const b = e.target.closest('[data-pt]'); if (!b) return; $('#ptDlg').close();
  const sel = plItem(plSel), parent = $('#ptInside').checked && sel ? sel.id : plRoot();
  plApplyTemplate(b.dataset.pt, parent); if (sel && parent === sel.id) sel.collapsed = false;
  PREFS.planView = 'outline'; $('#plView').value = 'outline'; renderPlan(); markDirty(); toast(`“${b.dataset.pt}” added to your plan. Rename, cut and rearrange freely.`);
});
$('#ptClose').addEventListener('click', () => $('#ptDlg').close());

/* build drafts from the plan */
let buildFrom = null;
function openBuild(id = null) {
  buildFrom = id; const it = plItem(id);
  $('#bdScope').innerHTML = (it ? `<option value="item">Just “${esc(it.title || 'Untitled')}”</option>` : '') + `<option value="all">The whole plan (each top-level item becomes a document)</option>`;
  $('#bdPart').innerHTML = '<option value="">No part</option><option value="__new">New part…</option>' + P.parts.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  $('#buildDlg').showModal();
}
$('#plBuild').addEventListener('click', () => openBuild(null));
$('#bdCancel').addEventListener('click', () => $('#buildDlg').close());
$('#bdOk').addEventListener('click', async () => {
  const scope = $('#bdScope').value, syn = $('#bdSyn').checked, withNotes = $('#bdNotes').checked;
  let partId = $('#bdPart').value;
  if (partId === '__new') { const n = await ask('New part', 'Name the part for these drafts:', 'Create', 'Draft'); if (!n) return; const pt = { id: uid('pt'), name: n, collapsed: false }; P.parts.push(pt); partId = pt.id; }
  $('#buildDlg').close();
  const tops = scope === 'item' && buildFrom ? [plItem(buildFrom)] : plKids('');
  const itemHTML = (it, level) => {
    const hl = Math.min(level + 1, 3); // the document title stands for level 0, so children start at Heading 2
    let h = level ? `<h${hl}>${esc(it.title || 'Untitled')}</h${hl}>` : '';
    if (syn) h += it.synopsis ? `<p><i>${esc(it.synopsis)}</i> ${flagHTML('tk', 'draft: ' + (it.title || 'this section'))}</p>` : (plKids(it.id).length ? '' : `<p>${flagHTML('tk', 'draft: ' + (it.title || 'this section'))}</p>`);
    if (withNotes) it.notes.forEach(nid => { const n = P.notes.find(x => x.id === nid); if (n) h += noteToHTML(n); });
    if (it.type === 'question' && it.status !== 'answered') h += `<p>${flagHTML('check', 'open question: ' + (it.title || ''))}</p>`;
    plKids(it.id).forEach(k => { h += itemHTML(k, level + 1); });
    return h;
  };
  let made = 0, skipped = 0, firstDoc = null;
  tops.forEach(it => {
    if (it.docId && P.docs.some(d => d.id === it.docId)) { skipped++; return; }
    const d = newDoc(it.title || 'Untitled', itemHTML(it, 0) || '<p><br></p>');
    const cur = curDoc(); if (cur) { d.style = cur.style; d.layout = Object.assign({}, cur.layout); d.meta.author = cur.meta.author; }
    d.partId = partId; d.order = 1e6 + made; if (it.target) d.target = it.target; d.status = 'drafting';
    P.docs.push(d); renumber(partId); it.docId = d.id; if (!it.status) it.status = 'drafting'; made++; firstDoc = firstDoc || d;
  });
  renderDocList(); renderPlan(); markDirty();
  toast(made ? `Built ${made} draft${made > 1 ? 's' : ''} from your plan${skipped ? ` (${skipped} already had one)` : ''}. Placeholders are TK flags, listed under Outline → To resolve.` : 'Those items already have drafts. Unlink one in its panel to rebuild.');
  if (made === 1 && firstDoc) { closePlan(); openDoc(firstDoc.id); }
});

/* ---------- freewrite sprints ---------- */
let fw = null;
function openFreewrite(planId = null) {
  const it = plItem(planId);
  fw = { planId, start: 0, secs: 0, timer: null, done: false };
  $('#fwPrompt').value = it ? (it.title + (it.synopsis ? ' — ' + it.synopsis : '')) : '';
  $('#fwText').value = ''; $('#fwText').disabled = true; $('#fwStat').textContent = 'Ready';
  $('#fwSetup').classList.remove('hidden'); $('#fwDone').classList.add('hidden');
  $('#fwMins').value = String(PREFS.fwMins || 10); $('#fwStrict').checked = !!PREFS.fwStrict;
  $('#fw').classList.remove('hidden'); setTimeout(() => $('#fwGo').focus(), 30);
}
function fwTick() {
  const left = Math.max(0, fw.secs - Math.floor((Date.now() - fw.start) / 1000)), words = wc($('#fwText').value);
  $('#fwStat').textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')} · ${words} words`;
  $('#fwBar').style.width = (100 - left / fw.secs * 100) + '%';
  if (!left && !fw.done) { fw.done = true; clearInterval(fw.timer); $('#fwStat').textContent = `Time! ${words} words. Finish your sentence, then save.`; $('#fwDone').classList.remove('hidden'); }
}
$('#fwGo').addEventListener('click', () => {
  PREFS.fwMins = +$('#fwMins').value; PREFS.fwStrict = $('#fwStrict').checked; savePrefs();
  fw.secs = PREFS.fwMins * 60; fw.start = Date.now(); fw.done = false;
  $('#fwSetup').classList.add('hidden'); $('#fwText').disabled = false; $('#fwText').focus();
  clearInterval(fw.timer); fw.timer = setInterval(fwTick, 500); fwTick();
});
$('#fwText').addEventListener('keydown', e => { if (fw && PREFS.fwStrict && !fw.done && (e.key === 'Backspace' || e.key === 'Delete' || ((e.metaKey || e.ctrlKey) && /^[xz]$/i.test(e.key)))) { e.preventDefault(); $('#fwText').classList.add('nope'); setTimeout(() => $('#fwText').classList.remove('nope'), 200); } });
$('#fwText').addEventListener('cut', e => { if (fw && PREFS.fwStrict && !fw.done) e.preventDefault(); });
$('#fwText').addEventListener('input', () => { if (fw && fw.start) fwTick(); });
$('#fwStop').addEventListener('click', () => { if (!fw) return; clearInterval(fw.timer); fw.done = true; $('#fwDone').classList.remove('hidden'); $('#fwStat').textContent = `${wc($('#fwText').value)} words`; });
$('#fwSave').addEventListener('click', () => {
  const text = $('#fwText').value.trim(); if (!text) { $('#fw').classList.add('hidden'); return; }
  const n = newNote(); n.kind = 'idea'; n.tags = ['freewrite']; n.body = ($('#fwPrompt').value ? '*Prompt: ' + $('#fwPrompt').value.trim() + '*\n\n' : '') + text;
  n.title = 'Freewrite · ' + new Date().toLocaleDateString([], { month: 'short', day: 'numeric' }) + (fw.planId && plItem(fw.planId) ? ' · ' + plItem(fw.planId).title : '');
  P.notes.unshift(n); if (fw.planId && plItem(fw.planId)) plItem(fw.planId).notes.push(n.id);
  renderNoteList(); renderPlan(); markDirty(); $('#fw').classList.add('hidden'); clearInterval(fw.timer);
  toast(`Freewrite saved as a note (${wc(text)} words)${fw.planId ? ' and linked to the plan item' : ''}.`);
});
$('#fwDiscard').addEventListener('click', async () => { if (wc($('#fwText').value) > 20 && !(await ask('Discard freewrite?', 'This text won’t be saved.', 'Discard'))) return; clearInterval(fw?.timer); $('#fw').classList.add('hidden'); });
$('#plFreewrite').addEventListener('click', () => openFreewrite(plSel));

/* ---------- Outline tab: structure editor + reverse outline ---------- */
let olBlocks = [], olUndo = null;
const firstSentence = t => { t = t.replace(/\s+/g, ' ').trim(); const m = t.match(/^.{20,}?[.!?](?=\s|$)/); return (m ? m[0] : t).slice(0, 110) + ((m ? m[0] : t).length > 110 ? '…' : ''); };
function sectionNodes(el) {
  const h = /^H([1-3])$/.exec(el.nodeName); if (!h) return [el];
  const out = [el]; let n = el.nextElementSibling;
  while (n && !(/^H[1-3]$/.test(n.nodeName) && +n.nodeName[1] <= +h[1])) { out.push(n); n = n.nextElementSibling; }
  return out;
}
function renderStructure() {
  const paras = $('#olParas').checked; olBlocks = [];
  const rows = []; let cur = null;
  [...editor.children].forEach(el => {
    const h = /^H([1-3])$/.exec(el.nodeName);
    if (h) { cur = { el, kind: 'h', level: +h[1], words: 0 }; rows.push(cur); return; }
    const w = wordsIn(el); if (cur) cur.words += w;
    if (paras && el.textContent.trim()) rows.push({ el, kind: 'p', words: w, under: cur ? cur.level : 0 });
  });
  const html = rows.map(r => {
    const i = outlineEls.push(r.el) - 1, b = olBlocks.push(r.el) - 1;
    if (r.kind === 'h') return `<li class="lvl${r.level} ol-h" data-i="${i}" data-b="${b}"><span class="ol-grip" title="Drag to move this section">⠿</span><span>${esc(blockSnippet(r.el, 60) || '(empty heading)')}</span><span class="ol-act"><button class="ghost" data-sa="up" title="Promote (bigger heading)">←</button><button class="ghost" data-sa="down" title="Demote (smaller heading)">→</button></span><em>${r.words.toLocaleString()}</em></li>`;
    return `<li class="ol-p lvl${Math.min(3, r.under + 1)}" data-i="${i}" data-b="${b}"><span class="ol-grip" title="Drag to move this paragraph">⠿</span><span>${esc(firstSentence(r.el.textContent))}</span><em>${r.words}</em></li>`;
  }).join('');
  $('#outlineList').innerHTML = html ? html + '<li class="ol-end none" data-end="1"></li>' : '<li class="muted small none">Add headings (Heading 1–3) and they’ll appear here. Drag them to reorder whole sections. Tick <i>paragraphs</i> for a reverse outline of every paragraph.</li>';
  $('#olUndo').classList.toggle('hidden', !olUndo);
}
function olApply(fn) {
  olUndo = editor.innerHTML; fn(); tidyTopLevel(); syncEditor(); lastSig = ''; renderRefs(true); updateWordCount(); markDirty(); renderOutline();
}
$('#outlineList').addEventListener('click', e => {
  const b = e.target.closest('[data-sa]'); if (!b) return; e.stopPropagation();
  const el = olBlocks[+b.closest('li').dataset.b]; if (!el) return;
  const lvl = +el.nodeName[1], nl = b.dataset.sa === 'up' ? Math.max(1, lvl - 1) : Math.min(3, lvl + 1); if (nl === lvl) return;
  olApply(() => { const h = document.createElement('h' + nl); h.append(...el.childNodes); [...el.attributes].forEach(a => h.setAttribute(a.name, a.value)); el.replaceWith(h); });
}, true);
let od = null;
$('#outlineList').addEventListener('pointerdown', e => { const g = e.target.closest('.ol-grip'); if (!g) return; e.preventDefault(); e.stopPropagation(); const li = g.closest('li'); od = { li, el: olBlocks[+li.dataset.b], started: false, sy: e.clientY }; });
document.addEventListener('pointermove', e => {
  if (!od) return;
  if (!od.started) { if (Math.abs(e.clientY - od.sy) < 4) return; od.started = true; od.li.classList.add('dragging'); document.body.classList.add('bd-dragging'); }
  $$('.ol-drop').forEach(x => x.remove());
  const t = document.elementFromPoint(e.clientX, e.clientY)?.closest('#outlineList li[data-b], #outlineList li.ol-end');
  od.to = t && t !== od.li ? t : null;
  if (od.to) { const line = document.createElement('li'); line.className = 'ol-drop'; od.to.before(line); }
});
document.addEventListener('pointerup', () => {
  if (!od) return; const d = od; od = null; document.body.classList.remove('bd-dragging'); $$('.ol-drop').forEach(x => x.remove()); d.li.classList.remove('dragging');
  if (!d.started || !d.to || !d.el) return;
  const nodes = sectionNodes(d.el);
  if (d.to.classList.contains('ol-end')) { olApply(() => editor.append(...nodes)); return; }
  const tgt = olBlocks[+d.to.dataset.b]; if (!tgt || nodes.includes(tgt)) return;
  olApply(() => tgt.before(...nodes));
  toast(d.el.nodeName[0] === 'H' ? 'Section moved. Notes renumbered.' : 'Paragraph moved.');
});
$('#olParas').addEventListener('change', renderOutline);
$('#olUndo').addEventListener('click', () => { if (!olUndo) return; editor.innerHTML = olUndo; olUndo = null; tidyTopLevel(); syncEditor(); lastSig = ''; renderRefs(true); updateWordCount(); markDirty(); renderOutline(); toast('Move undone.'); });

/* ================================================================
   Project home: launch pad for one project at a time
   ================================================================ */
const PKINDS = {
  book: { label: 'Book', blurb: 'Chapters in parts; a long-haul pace.', tpl: 'Nonfiction book', style: 'chicago-notes-bibliography', target: 80000, days: 365 },
  article: { label: 'Article or essay', blurb: 'One argued piece with notes.', tpl: 'Argument essay', style: 'chicago-notes-bibliography', target: 3000, days: 21 },
  series: { label: 'Substack series', blurb: 'Several parts, each with a hook and a cliffhanger.', tpl: 'Article series (Substack)', style: 'osint', target: 12000, days: 45 },
  whitepaper: { label: 'White paper or policy brief', blurb: 'Problem, options, recommendation.', tpl: 'Policy brief / white paper', style: 'osint', target: 6000, days: 30 },
  brief: { label: 'Intelligence brief', blurb: 'Key judgments, analysis, indicators.', tpl: 'Intelligence brief', style: 'osint', target: 2000, days: 7 },
  script: { label: 'Video script', blurb: 'Hook, promise, points, payoff.', tpl: 'Explainer / video script', style: 'osint', target: 2500, days: 7 },
  narrative: { label: 'Literary journalism', blurb: 'Scenes, nut graf, turn, kicker.', tpl: 'Narrative / literary journalism', style: 'chicago-notes-bibliography', target: 8000, days: 60 },
  blank: { label: 'Blank', blurb: 'No template; set it up yourself.', tpl: '', style: DEFAULT_STYLE, target: 0, days: 0 },
};
const DAY = 864e5;
const dayStart = (d = new Date()) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const fmtDay = d => d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
const nf = n => Math.round(n).toLocaleString();

/* ---------- recent files (handles kept in IndexedDB where the browser allows) ---------- */
async function recentList() { try { const v = await idb.get('recent'); return Array.isArray(v) ? v : []; } catch (e) { return []; } }
async function rememberRecent(handle, name) {
  if (!P || !name) return;
  try {
    const list = (await recentList()).filter(r => r.pid !== P.id && r.name !== name);
    const rec = { pid: P.id, title: LOCK ? '🔒 Locked project' : (P.title || 'Untitled project'), name, kind: (P.goal || {}).kind || '', opened: nowISO() };
    list.unshift(handle ? Object.assign({ handle }, rec) : rec);
    try { await idb.set('recent', list.slice(0, 8)); } catch (e) { await idb.set('recent', list.slice(0, 8).map(({ handle, ...r }) => r)); }
  } catch (e) {}
}
async function openRecent(i) {
  const r = (await recentList())[i]; if (!r) return;
  if (r.pid === P.id) { toast('That’s the project you have open.'); return; }
  if (dirtyFile && !(await ask('Open another project?', `“${P.title}” has changes that aren’t saved to a file. Save first, or they’ll be replaced.`, 'Open anyway'))) return;
  if (r.handle && r.handle.getFile) {
    try {
      let perm = r.handle.queryPermission ? await r.handle.queryPermission({ mode: 'readwrite' }) : 'granted';
      if (perm !== 'granted' && r.handle.requestPermission) perm = await r.handle.requestPermission({ mode: 'readwrite' });
      if (perm === 'granted') { const f = await r.handle.getFile(); dirtyFile = false; await loadProjectText(await f.text(), r.handle, f.name); return; }
    } catch (e) { console.warn(e); }
  }
  toast(`Choose “${r.name}” to reopen it.`);
  dirtyFile = false; openProject();
}

/* ---------- metrics ---------- */
function blockIndexOf(root, el) { let x = el; while (x && x.parentElement !== root) x = x.parentElement; return x ? [...root.children].indexOf(x) : -1; }
function looseEnds() {
  syncEditor();
  const flags = [], uncited = [], docs = binderOrder();
  docs.forEach(d => {
    const t = document.createElement('div'); t.innerHTML = d.html;
    $$('.flag', t).forEach(f => flags.push({ d, kind: f.dataset.kind || 'tk', note: f.dataset.note || '', at: blockIndexOf(t, f), snip: blockSnippet(f.closest('p,li,blockquote,h1,h2,h3') || f, 60) }));
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const n = w.currentNode; if (n.parentElement.closest('.cite,.fn,.flag')) continue; if (/\bTK\b/.test(n.data)) flags.push({ d, kind: 'tk', note: '', at: blockIndexOf(t, n.parentElement), snip: blockSnippet(n.parentElement.closest('p,li,blockquote,h1,h2,h3') || n.parentElement, 60) }); }
    if ((d.role || 'body') === 'body') $$(':scope > p, :scope > blockquote, :scope > ul > li, :scope > ol > li', t).forEach(el => { if (!el.querySelector('.cite') && wordsIn(el) >= (PREFS.uncitedMin || 40)) uncited.push({ d, at: blockIndexOf(t, el), snip: blockSnippet(el, 60) }); });
  });
  const iss = PLI().length ? plIssues() : [];
  const questions = iss.filter(x => x.it.type === 'question'), gaps = iss.filter(x => x.sev >= 2);
  let missing = [];
  try { missing = auditData('all').missing; } catch (e) {}
  const noteSrc = new Set(P.notes.map(n => n.sourceId).filter(Boolean));
  const pdfs = P.sources.filter(s => s.pdfName && !noteSrc.has(s.id));
  return { flags, uncited, questions, gaps, missing, pdfs };
}
function inboxNotes() {
  const linked = new Set(PLI().flatMap(i => i.notes || []));
  return P.notes.filter(n => !linked.has(n.id) && !n.pile).sort((a, b) => (b.created || '').localeCompare(a.created || ''));
}
function paceData() {
  const docs = binderOrder(), body = docs.filter(d => (d.role || 'body') === 'body');
  const words = body.reduce((n, d) => n + docWords(d), 0);
  const g = P.goal || {};
  const target = g.target || body.reduce((n, d) => n + (d.target || 0), 0);
  const days = []; const dd = dayStart(); dd.setDate(dd.getDate() - 13);
  for (let i = 0; i < 14; i++) { days.push({ d: new Date(dd), a: (P.stats.days[todayKey(dd)] || {}).a || 0 }); dd.setDate(dd.getDate() + 1); }
  const last7 = days.slice(7).reduce((n, x) => n + x.a, 0), avg7 = last7 / 7;
  const today = days[13].a;
  let daysLeft = null, need = null, finish = null, state = '';
  if (g.deadline) daysLeft = Math.round((new Date(g.deadline + 'T00:00') - dayStart()) / DAY);
  const left = Math.max(0, target - words);
  if (target && left && daysLeft !== null) need = daysLeft > 0 ? Math.ceil(left / daysLeft) : left;
  if (target && left && avg7 > 0) finish = new Date(dayStart().getTime() + Math.ceil(left / avg7) * DAY);
  if (target && !left) state = 'done';
  else if (daysLeft !== null && daysLeft < 0) state = 'late';
  else if (need !== null) state = avg7 >= need ? 'ok' : 'behind';
  return { words, target, left, days, last7, avg7, today, daysLeft, need, finish, state, docs, body };
}
function lastDoc() {
  const d = P.docs.find(x => x.id === curDocId);
  return d || [...P.docs].sort((a, b) => (b.modified || '').localeCompare(a.modified || ''))[0];
}
function nextStep(pc, le, inbox) {
  const planned = plKids('').filter(i => i.type === 'section' || i.type === 'claim'), undrafted = planned.filter(i => !plDocOf(i));
  const overdue = pc.docs.filter(d => d.deadline && d.status !== 'final' && new Date(d.deadline + 'T23:59') < new Date());
  const tks = le.flags.length;
  if (!PLI().length && pc.words < 300) return { text: 'Sketch the structure before drafting: start the plan from a template or a blank outline.', btn: 'Open the plan', act: () => openPlan() };
  if (overdue.length) return { text: `“${overdue[0].title || 'Untitled'}” is past its deadline.`, btn: 'Open it', act: () => openDoc(overdue[0].id) };
  if (undrafted.length && planned.length && undrafted.length === planned.length) return { text: `Your plan has ${planned.length} top-level part${planned.length === 1 ? '' : 's'} and none is drafted yet. Turn them into documents with headings and placeholders.`, btn: 'Build drafts…', act: () => { openPlan(); $('#plBuild').click(); } };
  if (pc.daysLeft !== null && pc.daysLeft <= 7 && pc.daysLeft >= 0 && tks) return { text: `${tks} flag${tks === 1 ? '' : 's'} still open, ${pc.daysLeft ? pc.daysLeft + ' day' + (pc.daysLeft === 1 ? '' : 's') : 'and the deadline is today'}${pc.daysLeft ? ' to the deadline' : ''}. Clear them while you still have time.`, btn: 'Show flags', act: () => { const g = $('#hmFlags'); if (g) { g.open = true; g.scrollIntoView({ block: 'center', behavior: 'smooth' }); } } };
  if (pc.state === 'behind' && pc.need) { const d = lastDoc(); return { text: `To make the deadline, write about ${nf(pc.need)} words a day. You’re averaging ${nf(pc.avg7)}.${pc.today ? ` ${nf(pc.today)} so far today.` : ''}`, btn: 'Start writing', act: () => openDoc(d.id) }; }
  if (le.questions.length && pc.words < (pc.target || 4000) * 0.3) { const q = le.questions[0].it; return { text: `Open research question: “${q.title || 'Untitled'}”.`, btn: 'Go to it', act: () => { openPlan(); plSelect(q.id); } }; }
  if (inbox.length >= 10) return { text: `${inbox.length} notes haven’t been linked to the plan or sorted into a pile.`, btn: 'Sort on the board', act: () => openBoard() };
  if (undrafted.length) return { text: `“${undrafted[0].title || 'Untitled'}” is planned but not drafted.`, btn: 'Build drafts…', act: () => { openPlan(); $('#plBuild').click(); } };
  const d = pc.docs.filter(x => x.status === 'drafting' || x.status === 'revising').sort((a, b) => (b.modified || '').localeCompare(a.modified || ''))[0] || lastDoc();
  return { text: `Keep going on “${d.title || 'Untitled'}”${d.status ? ' (' + d.status + ')' : ''}.`, btn: 'Open it', act: () => openDoc(d.id) };
}

/* ---------- render ---------- */
let hmNext = null, hmJump = [];
function openHome() {
  if (!P) return;
  syncEditor(); if (boardOn) closeBoard(); if (planOn) closePlan(); if (draftsOn) closeDrafts(); if (relOn) closeRel();
  homeOn = true; document.body.classList.add('home-on'); $('#home').classList.remove('hidden');
  document.body.classList.remove('side-open'); renderHome();
}
function closeHome() { homeOn = false; document.body.classList.remove('home-on'); $('#home').classList.add('hidden'); }
function jumpTo(docId, at) {
  openDoc(docId);
  const el = editor.children[at]; if (!el) return;
  el.scrollIntoView({ block: 'center' }); el.classList.remove('hm-flash'); void el.offsetWidth; el.classList.add('hm-flash');
  setTimeout(() => el.classList.remove('hm-flash'), 2000);
  try { const r = document.createRange(); r.selectNodeContents(el); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus({ preventScroll: true }); } catch (e) {}
}
function groupHTML(id, title, items, row, open = false) {
  if (!items.length) return '';
  return `<details class="hm-group" ${id ? `id="${id}"` : ''} ${open ? 'open' : ''}><summary>${title}<span class="count">${items.length}</span></summary><ul class="hm-list">${items.slice(0, 40).map(row).join('')}${items.length > 40 ? `<li class="m">…and ${items.length - 40} more</li>` : ''}</ul></details>`;
}
async function renderHome() {
  if (!homeOn) return;
  const pc = paceData(), le = looseEnds(), inbox = inboxNotes(), g = P.goal, K = PKINDS[g.kind];
  hmNext = nextStep(pc, le, inbox); hmJump = [];
  const J = (fn) => { hmJump.push(fn); return hmJump.length - 1; };
  const d = lastDoc();
  const pct = pc.target ? Math.min(100, pc.words / pc.target * 100) : 0;
  const max = Math.max(10, ...pc.days.map(x => x.a)), bw = 100 / 14;
  const spark = `<svg class="hm-spark" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Words added per day, last 14 days">${pc.days.map((x, i) => { const h = x.a ? Math.max(2, x.a / max * 38) : 1.5; return `<rect class="${x.a ? '' : 'z'}" x="${i * bw + .6}" y="${40 - h}" width="${bw - 1.2}" height="${h}" rx=".8"><title>${fmtDay(x.d)}: ${nf(x.a)} words</title></rect>`; }).join('')}</svg>`;
  const paceMsg = {
    done: '<div class="hm-pace ok">Target reached. Time to revise.</div>',
    late: `<div class="hm-pace late">The deadline passed ${Math.abs(pc.daysLeft)} day${Math.abs(pc.daysLeft) === 1 ? '' : 's'} ago, with ${nf(pc.left)} words to go.</div>`,
    ok: `<div class="hm-pace ok">On pace: you need ${nf(pc.need)} a day and you’re averaging ${nf(pc.avg7)}.</div>`,
    behind: `<div class="hm-pace behind">Behind: you need ${nf(pc.need)} a day and you’re averaging ${nf(pc.avg7)}.${pc.finish ? ` At this rate you’ll finish ${fmtDay(pc.finish)}.` : ''}</div>`,
  }[pc.state] || (pc.target ? (pc.finish ? `<div class="hm-pace">At your 7-day pace you’ll reach the target ${fmtDay(pc.finish)}. Set a deadline to see the pace you need.</div>` : '<div class="hm-pace">Set a deadline to see the daily pace you need.</div>') : '<div class="hm-pace">Set a word target and a deadline to track your pace.</div>');
  const ST = { idea: 'idea', drafting: 'drafting', revising: 'revising', final: 'final' };
  const plannedUndrafted = plKids('').filter(i => (i.type === 'section' || i.type === 'claim') && !plDocOf(i));
  const recent = [...P.docs.map(x => ({ t: 'd', x })), ...P.notes.map(x => ({ t: 'n', x }))].sort((a, b) => (b.x.modified || '').localeCompare(a.x.modified || '')).slice(0, 6);
  const files = await recentList();
  const flagLabel = k => (FLAG_KINDS[k] || FLAG_KINDS.tk).label;

  const leTotal = le.flags.length + le.questions.length + le.gaps.length + le.uncited.length + le.missing.length + le.pdfs.length;
  const looseHTML = leTotal ? [
    groupHTML('hmFlags', 'Flags in drafts (TK, cite?, check)', le.flags, f => `<li data-j="${J(() => jumpTo(f.d.id, f.at))}"><span class="flag flag-${f.kind}">${flagLabel(f.kind)}</span><span class="t">${esc(f.note || f.snip || '(empty paragraph)')}</span><span class="m">${esc(f.d.title || 'Untitled')}</span></li>`, le.flags.length <= 8),
    groupHTML('', 'Open research questions', le.questions, x => `<li data-j="${J(() => { openPlan(); plSelect(x.it.id); })}"><span class="pl-type ty-question">?</span><span class="t">${esc(x.it.title || 'Untitled')}</span></li>`),
    groupHTML('', 'Gaps in the argument', le.gaps, x => `<li data-j="${J(() => { PREFS.planView = 'check'; savePrefs(); openPlan(); })}"><span class="pl-type ty-${x.it.type}">${(PT[x.it.type] || PT.section).icon}</span><span class="t">${esc(x.it.title || 'Untitled')}</span><span class="m">${esc(x.msg.replace(/\.$/, ''))}</span></li>`),
    groupHTML('', `Uncited paragraphs (${PREFS.uncitedMin || 40}+ words)`, le.uncited, u => `<li data-j="${J(() => jumpTo(u.d.id, u.at))}"><span class="t">${esc(u.snip)}</span><span class="m">${esc(u.d.title || 'Untitled')}</span></li>`),
    groupHTML('', 'Cited sources missing details', le.missing, s => { const l = sourceLabel(s); return `<li data-j="${J(() => openSource(s.id))}"><span class="t">${esc(l.title || 'Untitled source')}</span><span class="m">${esc([!s.csl.title && 'title', !(s.csl.author || s.csl.editor) && 'author', !s.csl.issued && 'date'].filter(Boolean).join(', ') + ' missing')}</span></li>`; }),
    groupHTML('', 'PDFs with no notes yet', le.pdfs, s => `<li data-j="${J(() => openSource(s.id))}"><span class="t">${esc(sourceLabel(s).title || s.pdfName)}</span><span class="m">${esc(s.pdfName)}</span></li>`),
  ].join('') : '<div class="hm-empty">Nothing outstanding: no flags, open questions, gaps or uncited paragraphs.</div>';

  $('#hmArea').innerHTML = `<div class="hm-grid">
  <div class="hm-card hm-wide">
    <div class="hm-resume">
      <div class="who"><span class="small muted">${esc(K ? K.label : 'Project')} · pick up where you left off</span><b>${esc(d ? d.title || 'Untitled document' : 'No documents yet')}</b><span class="small muted">${d ? `${nf(docWords(d))} words${d.modified ? ' · edited ' + relTime(d.modified) : ''}${d.status ? ' · ' + d.status : ''}` : ''}</span></div>
      <button class="primary" id="hmResume">Resume writing →</button>
    </div>
    <div class="hm-next"><span><b>Next:</b> ${esc(hmNext.text)}</span><button id="hmNextBtn">${esc(hmNext.btn)}</button></div>
    <div class="hm-quick"><button data-q="plan">▤ Plan</button><button data-q="board">Board</button><button data-q="fw">Freewrite</button><button data-q="reader">PDF reader</button><button data-q="record">Writing record</button><button data-q="ms">Compile manuscript</button></div>
  </div>

  <div class="hm-card">
    <h5>Goal &amp; pace</h5>
    <div class="hm-big"><b>${nf(pc.words)}</b><span class="muted">${pc.target ? `of ${nf(pc.target)} words · ${Math.floor(pct)}%` : 'words drafted'}</span></div>
    <div class="hm-bar"><i style="width:${pct}%"></i></div>
    <div class="hm-stats">
      <div><b>${pc.daysLeft === null ? '—' : pc.daysLeft < 0 ? Math.abs(pc.daysLeft) + 'd late' : pc.daysLeft}</b><span>${pc.daysLeft === null ? 'no deadline' : pc.daysLeft < 0 ? 'past ' + fmtDay(new Date(g.deadline + 'T12:00')) : 'days left · ' + fmtDay(new Date(g.deadline + 'T12:00'))}</span></div>
      <div><b>${pc.need === null ? '—' : nf(pc.need)}</b><span>words a day needed</span></div>
      <div><b>${nf(pc.today)}</b><span>today${PREFS.dailyGoal ? ' / ' + nf(PREFS.dailyGoal) : ''}</span></div>
      <div><b>${nf(pc.avg7)}</b><span>a day, last 7 days · ${streak()}-day streak</span></div>
    </div>
    ${paceMsg}${spark}
    <div class="hm-goal">
      <div><label>Kind</label><select id="hmKind"><option value="">—</option>${Object.entries(PKINDS).filter(([k]) => k !== 'blank').map(([k, v]) => `<option value="${k}" ${k === g.kind ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></div>
      <div><label>Word target</label><input id="hmTarget" inputmode="numeric" value="${g.target || ''}" placeholder="${pc.target && !g.target ? nf(pc.target) + ' (docs)' : 'none'}"></div>
      <div><label>Deadline</label><input type="date" id="hmDeadline" value="${esc(g.deadline || '')}"></div>
    </div>
  </div>

  <div class="hm-card">
    <h5>Documents <span class="count">${pc.docs.length}</span><button class="ghost small" id="hmNewDoc">+ Doc</button></h5>
    <ul class="hm-list">${pc.docs.map(x => { const w = docWords(x); return `<li data-j="${J(() => openDoc(x.id))}"><span class="t">${x.role && x.role !== 'body' ? `<span class="role-tag">${esc(x.role)}</span> ` : ''}${esc(x.title || 'Untitled')}</span>${x.status ? `<span class="st st-${x.status === 'final' ? 'done' : 'todo'}">${esc(ST[x.status] || x.status)}</span>` : ''}${x.target ? `<span class="mini" title="${nf(w)} of ${nf(x.target)}"><i style="width:${Math.min(100, w / x.target * 100)}%"></i></span>` : ''}<span class="m">${nf(w)}</span>${dueLabel(x)}</li>`; }).join('')}</ul>
    ${plannedUndrafted.length ? `<div class="hm-next" style="margin-top:10px"><span>${plannedUndrafted.length} planned part${plannedUndrafted.length === 1 ? '' : 's'} not drafted yet.</span><button id="hmBuild">Build drafts…</button></div>` : ''}
  </div>

  <div class="hm-card">
    <h5>Loose ends <span class="count">${leTotal}</span></h5>
    ${looseHTML}
  </div>

  <div class="hm-card">
    <h5>Notes inbox <span class="count">${inbox.length}</span><button class="ghost small" id="hmBoard">Sort on the board</button></h5>
    ${inbox.length ? `<ul class="hm-list">${inbox.slice(0, 8).map(n => `<li data-j="${J(() => openNote(n.id))}"><span class="t">${esc(noteTitle(n) || 'Untitled note')}</span><span class="m">${n.kind ? esc(n.kind) + ' · ' : ''}${relTime(n.created)}</span></li>`).join('')}${inbox.length > 8 ? `<li class="m" data-j="${J(() => openBoard())}">…${inbox.length - 8} more on the board</li>` : ''}</ul>` : '<div class="hm-empty">Every note is linked to the plan or sorted into a pile.</div>'}
    <p class="small muted" style="margin:10px 0 0">Notes leave the inbox when you link them to a plan item or drop them in a board pile.</p>
  </div>

  <div class="hm-card">
    <h5>Recently touched</h5>
    <ul class="hm-list">${recent.map(r => `<li data-j="${J(() => r.t === 'd' ? openDoc(r.x.id) : openNote(r.x.id))}"><span class="m">${r.t === 'd' ? 'Doc' : 'Note'}</span><span class="t">${esc(r.t === 'd' ? r.x.title || 'Untitled' : noteTitle(r.x) || 'Untitled note')}</span><span class="m">${relTime(r.x.modified || r.x.created)}</span></li>`).join('')}</ul>
  </div>

  <div class="hm-card">
    <h5>Project file</h5>
    <div class="hm-file">${lastFileName ? `<b>${esc(lastFileName)}</b>` : '<b>Not saved to a file yet</b>'}<br><span class="${dirtyFile ? 'dirty' : 'muted'}">${dirtyFile ? 'Unsaved changes, kept in this browser until you save' : lastFileSave ? 'Saved ' + relTime(lastFileSave.toISOString()) : 'No changes since opening'}</span></div>
    <div class="row" style="gap:6px;flex-wrap:wrap"><button class="primary" id="hmSave">Save</button><button id="hmOpen2">Open…</button><button id="hmNew2">New project…</button></div>
    ${files.filter(f => f.pid !== P.id).length ? `<label>Recent files</label><ul class="hm-list">${files.map((f, i) => f.pid === P.id ? '' : `<li data-recent="${i}" title="${f.handle ? 'Reopen' : 'Choose this file to reopen it'}"><span class="t">${esc(f.title)}</span><span class="m">${esc(f.name)} · ${relTime(f.opened)}</span></li>`).join('')}</ul>` : ''}
    <p class="small muted" style="margin:10px 0 0">One project at a time. Saving keeps it in its .json file, and opening another replaces this one in the browser.</p>
  </div>
</div>`;
}
const renderHomeSoon = debounce(renderHome, 300);
$('#hmArea').addEventListener('click', e => {
  const r = e.target.closest('[data-recent]'); if (r) { openRecent(+r.dataset.recent); return; }
  const j = e.target.closest('[data-j]'); if (j) { const fn = hmJump[+j.dataset.j]; if (fn) fn(); return; }
  const q = e.target.closest('[data-q]');
  if (q) { ({ plan: () => openPlan(), board: () => openBoard(), fw: () => openFreewrite(), reader: () => $('#btnReader').click(), record: () => openRecord(), ms: () => openManuscript() })[q.dataset.q](); return; }
  const id = e.target.id;
  if (id === 'hmResume') { const d = lastDoc(); if (d) openDoc(d.id); else addDoc(newDoc()); }
  else if (id === 'hmNextBtn' && hmNext) hmNext.act();
  else if (id === 'hmBuild') { openPlan(); $('#plBuild').click(); }
  else if (id === 'hmNewDoc') addDoc(newDoc());
  else if (id === 'hmBoard') openBoard();
  else if (id === 'hmSave') saveProject(false).then(renderHome);
  else if (id === 'hmOpen2') openProject();
  else if (id === 'hmNew2') openNewProject();
});
$('#hmArea').addEventListener('change', e => {
  const g = P.goal;
  if (e.target.id === 'hmKind') g.kind = e.target.value;
  else if (e.target.id === 'hmTarget') g.target = Math.max(0, parseInt(String(e.target.value).replace(/[^\d]/g, ''), 10) || 0);
  else if (e.target.id === 'hmDeadline') g.deadline = e.target.value || '';
  else return;
  markDirty(); renderHome();
});
$('#btnHome').addEventListener('click', () => { if (homeOn) { closeHome(); openDoc(curDocId); } else openHome(); });
$('#hmBack').addEventListener('click', () => { closeHome(); openDoc(curDocId); });
$('#hmOpen').addEventListener('click', () => openProject());
$('#hmNew').addEventListener('click', () => openNewProject());

/* ---------- new project ---------- */
let npKind = 'article';
function npApplyKind(k) {
  npKind = k; const K = PKINDS[k];
  $$('#npKinds .np-kind').forEach(b => b.classList.toggle('on', b.dataset.k === k));
  $('#npStyle').value = K.style; $('#npTarget').value = K.target ? K.target.toLocaleString() : '';
  if (K.days) { const d = new Date(Date.now() + K.days * DAY); $('#npDeadline').value = todayKey(d); } else $('#npDeadline').value = '';
  $('#npPlan').checked = !!K.tpl; $('#npPlan').disabled = !K.tpl;
  $('#npPlanLbl').textContent = K.tpl ? `Start the plan from the “${K.tpl}” template` : 'No template for a blank project';
}
async function openNewProject() {
  $('#npKinds').innerHTML = Object.entries(PKINDS).map(([k, v]) => `<button type="button" class="np-kind" data-k="${k}"><b>${esc(v.label)}</b><span>${esc(v.blurb)}</span></button>`).join('');
  $('#npStyle').innerHTML = Object.keys(STYLES).map(k => `<option value="${k}">${esc(STYLES[k].label)}</option>`).join('');
  $('#npTitle').value = ''; npApplyKind(npKind);
  $('#npWarn').innerHTML = dirtyFile ? `<b>“${esc(P.title)}” has unsaved changes.</b> Save it first. The new project replaces it in this browser. <button id="npSaveFirst" class="small">Save “${esc(P.title)}” now</button>` : `“${esc(P.title)}” stays in ${lastFileName ? esc(lastFileName) : 'this browser only, so save it first if you want to keep it'}. The new project replaces it here.`;
  $('#npDlg').showModal(); setTimeout(() => $('#npTitle').focus(), 30);
}
$('#npKinds').addEventListener('click', e => { const b = e.target.closest('.np-kind'); if (b) npApplyKind(b.dataset.k); });
$('#npWarn').addEventListener('click', async e => { if (e.target.id === 'npSaveFirst') { await saveProject(false); if (!dirtyFile) $('#npWarn').textContent = `Saved to ${lastFileName}. The new project replaces it in this browser.`; } });
$('#npCancel').addEventListener('click', () => $('#npDlg').close());
$('#npOk').addEventListener('click', async () => {
  if (dirtyFile && !(await ask('Replace the current project?', `“${P.title}” has changes that aren’t saved to a file. Starting a new project replaces them in this browser.`, 'Start new anyway'))) return;
  const K = PKINDS[npKind], title = $('#npTitle').value.trim() || 'Untitled project';
  syncEditor();
  P = blankProject(); P.title = title; LOCK = null; document.body.classList.remove('locked'); pendingHandle = null;
  P.goal = { kind: npKind === 'blank' ? '' : npKind, target: Math.max(0, parseInt($('#npTarget').value.replace(/[^\d]/g, ''), 10) || 0), deadline: $('#npDeadline').value || '', started: todayKey() };
  const d = newDoc(npKind === 'book' || npKind === 'series' ? 'Notes toward a draft' : title); d.style = $('#npStyle').value; P.docs.push(d);
  if ($('#npPlan').checked && K.tpl && PLAN_TEMPLATES[K.tpl]) plApplyTemplate(K.tpl, '');
  fileHandle = null; dirtyFile = true; dirtySince = Date.now(); lastFileSave = null; lastFileName = ''; srcVersion++; curDocId = d.id;
  if (typeof R !== 'undefined' && R.doc) { try { R.doc.destroy(); } catch (e) {} R.doc = null; showReader(false); }
  $('#npDlg').close(); closePanel();
  openDoc(d.id, true); renderAll(); persistLocal(); updateSaveState(); openHome();
  toast(`New ${K.label.toLowerCase()} project: “${title}”. Save it to a file when you’re ready.`);
});

/* ================================================================
   Figures, tables & images
   Images live in P.assets (data URLs, downscaled on the way in) so they travel
   inside the project file. Documents refer to them by id; the editor shows them
   through object URLs, and exports inline the data.
   ================================================================ */
const assetCache = {};
function b64ToBytes(b64) { const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
function bytesToB64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
function dataURLParts(d) {
  const m = /^data:([^;,]+)(;base64)?,([\s\S]*)$/.exec(d || ''); if (!m) return null;
  return { mime: m[1], bytes: m[2] ? b64ToBytes(m[3]) : new TextEncoder().encode(decodeURIComponent(m[3])) };
}
function assetURL(id) {
  const a = P.assets[id]; if (!a) return '';
  const c = assetCache[id]; if (c && c.d === a.data) return c.u;
  let u = a.data;
  try { const p = dataURLParts(a.data); u = URL.createObjectURL(new Blob([p.bytes], { type: p.mime })); } catch (e) {}
  if (c && c.u.startsWith('blob:')) URL.revokeObjectURL(c.u);
  assetCache[id] = { d: a.data, u }; return u;
}
function hydrateImages(root = editor) {
  $$('img[data-asset]', root).forEach(img => { const u = assetURL(img.dataset.asset); if (u && img.getAttribute('src') !== u) img.setAttribute('src', u); if (!u) img.setAttribute('alt', '[missing image]'); });
}
function addAsset(data, name = '', w = 0, h = 0) {
  const id = uid('i'), mime = (/^data:([^;,]+)/.exec(data) || [])[1] || 'image/png';
  P.assets[id] = { name, type: mime, data, w, h, created: nowISO() }; return id;
}
const loadImage = src => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('That image couldn’t be read. Try a PNG or JPEG.')); i.src = src; });
const fileToDataURL = f => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = () => rej(r.error); r.readAsDataURL(f); });
async function normalizeImage(raw, type = '', size = 0) {
  const img = await loadImage(raw);
  let w = img.naturalWidth || 800, h = img.naturalHeight || 600;
  const scale = Math.min(1, 1800 / Math.max(w, h));
  if (/^image\/(png|jpeg|gif)$/.test(type) && scale === 1 && size && size < 700e3) return { data: raw, w, h };
  w = Math.max(1, Math.round(w * scale)); h = Math.max(1, Math.round(h * scale));
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
  g.drawImage(img, 0, 0, w, h);
  const png = /png|svg|gif|webp/.test(type) ? c.toDataURL('image/png') : '';
  if (png && png.length < 1.4e6) return { data: png, w, h };
  g.globalCompositeOperation = 'destination-over'; g.fillStyle = '#fff'; g.fillRect(0, 0, w, h);
  return { data: c.toDataURL('image/jpeg', 0.86), w, h };
}
async function imageFileToAsset(file) {
  if (!/^image\//.test(file.type)) throw new Error(`“${file.name}” isn’t an image.`);
  const r = await normalizeImage(await fileToDataURL(file), file.type, file.size);
  return addAsset(r.data, file.name.replace(/\.[^.]+$/, ''), r.w, r.h);
}
async function dataURLToAsset(src, name = '') { // pasted or imported data: images
  const mime = (/^data:([^;,]+)/.exec(src) || [])[1] || '';
  try { const r = await normalizeImage(src, mime, src.length * 0.75); return addAsset(r.data, name, r.w, r.h); } catch (e) { return ''; }
}
const figHTML = (id, cap = '') => `<figure class="fig" data-size="full" contenteditable="false"><img data-asset="${id}" alt=""><figcaption contenteditable="true">${cap ? esc(cap) : '<br>'}</figcaption></figure>`;
function renumberFigures(root = editor) {
  let f = 0, t = 0;
  $$('figure:not(.av)', root).forEach(fig => {
    const cap = fig.querySelector(':scope > figcaption'); if (!cap) return;
    const lab = fig.classList.contains('tbl') ? 'Table ' + (++t) + '.' : 'Figure ' + (++f) + '.';
    if (cap.getAttribute('data-cp-n') !== lab) cap.setAttribute('data-cp-n', lab);
  });
}
function prepFigureDom(root) { // contenteditable plumbing after paste/import/open
  $$('figure.fig', root).forEach(f => { f.setAttribute('contenteditable', 'false'); const c = f.querySelector(':scope > figcaption'); if (c) c.setAttribute('contenteditable', 'true'); });
  $$('figure.tbl', root).forEach(f => f.removeAttribute('contenteditable'));
}
const refreshFigures = debounce(() => { hydrateImages(); renumberFigures(); }, 150);
editor.addEventListener('input', refreshFigures);
function focusCaption(fig) {
  const cap = fig && fig.querySelector('figcaption'); if (!cap) return;
  const r = document.createRange(); r.selectNodeContents(cap); r.collapse(false);
  const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange();
  fig.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}
async function insertFigureFiles(files) {
  const imgs = [...files].filter(f => /^image\//.test(f.type)); if (!imgs.length) return false;
  let html = '', last = '';
  for (const f of imgs) { try { last = await imageFileToAsset(f); html += figHTML(last); } catch (e) { toast(e.message); } }
  if (!html) return true;
  insertBlocksAtCursor(html + '<p><br></p>');
  hydrateImages(); renumberFigures(); markDirty();
  const img = $(`img[data-asset="${last}"]`, editor); if (img) focusCaption(img.closest('figure'));
  toast(imgs.length > 1 ? `${imgs.length} figures added. Type a caption under each.` : 'Figure added. Type its caption underneath.');
  return true;
}
$('#btnFigure').addEventListener('click', () => openFigureMenu());
$('#fileFigure').addEventListener('change', async e => {
  const fs = [...e.target.files]; e.target.value = '';
  if (figReplace) { const fig = figReplace; figReplace = null; if (!fs[0]) return; try { const id = await imageFileToAsset(fs[0]); fig.querySelector('img').dataset.asset = id; hydrateImages(); onEdit(); } catch (err) { toast(err.message); } return; }
  insertFigureFiles(fs);
});
function saveSelectionNow() { const s = getSelection(); if (s.rangeCount && editor.contains(s.anchorNode)) savedRange = s.getRangeAt(0).cloneRange(); }
$('#toolbar').addEventListener('mousedown', e => { if (e.target.closest('#btnFigure,#btnTable')) { saveSelectionNow(); e.preventDefault(); } });

/* tables */
function insertTable(rows, cols, header) {
  const cell = t => `<${t}><br></${t}>`, row = t => `<tr>${Array.from({ length: cols }, () => cell(t)).join('')}</tr>`;
  insertBlocksAtCursor(`<figure class="tbl"><figcaption><br></figcaption><table>${header ? `<thead>${row('th')}</thead>` : ''}<tbody>${Array.from({ length: rows }, () => row('td')).join('')}</tbody></table></figure><p><br></p>`);
  renumberFigures();
  const figs = $$('figure.tbl', editor), sel = getSelection();
  const fig = figs.find(f => f.contains(sel.anchorNode)) || figs.filter(f => !f.querySelector('figcaption').textContent.trim()).pop();
  if (fig) focusCaption(fig);
}
$('#btnTable').addEventListener('click', () => { $('#tbRows').value = 3; $('#tbCols').value = 3; $('#tbHead').checked = true; $('#tblDlg').showModal(); });
$('#tbCancel').addEventListener('click', () => $('#tblDlg').close());
$('#tbOk').addEventListener('click', () => {
  const r = Math.min(60, Math.max(1, parseInt($('#tbRows').value, 10) || 3)), c = Math.min(12, Math.max(1, parseInt($('#tbCols').value, 10) || 3));
  $('#tblDlg').close(); restoreSelection(); insertTable(r, c, $('#tbHead').checked);
});
function selCell() { const s = getSelection(); if (!s.rangeCount) return null; let n = s.anchorNode; n = n && (n.nodeType === 1 ? n : n.parentElement); return n && editor.contains(n) ? n.closest('td,th') : null; }
function caretInto(el, end = false) { const r = document.createRange(); r.selectNodeContents(el); r.collapse(!end); const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); }
function tableOp(op) {
  const cell = selCell(); if (!cell) return;
  const tr = cell.parentElement, table = cell.closest('table'), fig = table.closest('figure') || table, idx = cell.cellIndex;
  const blank = tag => { const c = document.createElement(tag); c.innerHTML = '<br>'; return c; };
  if (op === 'row') { const nr = document.createElement('tr'); [...tr.cells].forEach(() => nr.append(blank('td'))); if (tr.parentElement.nodeName === 'THEAD') { let tb = table.tBodies[0]; if (!tb) { tb = document.createElement('tbody'); table.append(tb); } tb.prepend(nr); } else tr.after(nr); caretInto(nr.cells[0]); }
  if (op === 'col') { [...table.rows].forEach(r => { const c = r.cells[Math.min(idx, r.cells.length - 1)]; if (c) c.after(blank(c.nodeName.toLowerCase())); }); caretInto(tr.cells[idx + 1]); }
  if (op === 'delrow') { const next = tr.nextElementSibling || tr.previousElementSibling; tr.remove(); if (!table.rows.length) { fig.remove(); } else if (next && next.cells[0]) caretInto(next.cells[0]); else caretInto(table.rows[0].cells[0]); $$('thead,tbody', table).forEach(s => { if (!s.rows.length) s.remove(); }); }
  if (op === 'delcol') { [...table.rows].forEach(r => r.cells[Math.min(idx, r.cells.length - 1)]?.remove()); [...table.rows].forEach(r => { if (!r.cells.length) r.remove(); }); if (!table.rows.length) fig.remove(); else caretInto(table.rows[0].cells[Math.max(0, idx - 1)]); }
  if (op === 'head') {
    if (table.tHead) { const rows = [...table.tHead.rows]; let tb = table.tBodies[0]; if (!tb) { tb = document.createElement('tbody'); table.append(tb); } rows.reverse().forEach(r => { [...r.cells].forEach(c => { const d = document.createElement('td'); d.innerHTML = c.innerHTML; c.replaceWith(d); }); tb.prepend(r); }); table.tHead.remove(); }
    else { const first = table.rows[0]; if (first) { const th = document.createElement('thead'); [...first.cells].forEach(c => { const h = document.createElement('th'); h.innerHTML = c.innerHTML; c.replaceWith(h); }); th.append(first); table.prepend(th); } }
  }
  if (op === 'del') { const after = fig.nextElementSibling; fig.remove(); if (after) caretInto(after); }
  tblBar.classList.add('hidden'); onEdit(); renumberFigures(); placeTblBar();
}
const tblBar = $('#tblBar');
tblBar.addEventListener('mousedown', e => e.preventDefault());
tblBar.addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (b) tableOp(b.dataset.t); });
function placeTblBar() {
  if (!P) return;
  const cell = selCell(); if (!cell || homeOn || boardOn || planOn || draftsOn) { tblBar.classList.add('hidden'); return; }
  const t = cell.closest('table'), pr = $('#page').getBoundingClientRect(), tr = t.getBoundingClientRect();
  tblBar.classList.remove('hidden');
  tblBar.style.top = Math.max(0, tr.top - pr.top - tblBar.offsetHeight - 6) + 'px';
  tblBar.style.left = Math.max(0, tr.left - pr.left) + 'px';
  $('[data-t=head]', tblBar).classList.toggle('on', !!t.tHead);
}
document.addEventListener('selectionchange', debounce(placeTblBar, 60));

/* keys inside captions and tables */
editor.addEventListener('keydown', e => {
  const s = getSelection(); if (!s.rangeCount) return;
  let n = s.anchorNode; n = n && (n.nodeType === 1 ? n : n.parentElement); if (!n || !editor.contains(n)) return;
  const cap = n.closest('figcaption'), cell = n.closest('td,th');
  if (cap && e.key === 'Enter') {
    e.preventDefault(); e.stopImmediatePropagation();
    const fig = cap.closest('figure');
    if (fig.classList.contains('tbl') && cap === fig.firstElementChild) { const c = fig.querySelector('td,th'); if (c) { caretInto(c); return; } }
    let next = fig.nextElementSibling; if (!next || !/^(P|H[1-3]|BLOCKQUOTE|UL|OL)$/.test(next.nodeName)) { next = document.createElement('p'); next.innerHTML = '<br>'; fig.after(next); }
    caretInto(next); onEdit(); return;
  }
  if (cap && e.key === 'Backspace' && !cap.textContent.length && s.isCollapsed) { e.preventDefault(); e.stopImmediatePropagation(); return; }
  if (cell && e.key === 'Tab') {
    e.preventDefault(); e.stopImmediatePropagation();
    const cells = $$('td,th', cell.closest('table')), i = cells.indexOf(cell);
    if (e.shiftKey) { if (i > 0) caretInto(cells[i - 1], true); return; }
    if (i < cells.length - 1) caretInto(cells[i + 1], true); else tableOp('row');
    return;
  }
  if (cell && e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.stopImmediatePropagation(); document.execCommand('insertLineBreak'); onEdit(); }
}, true);

/* clicking a figure image */
let figReplace = null;
editor.addEventListener('click', e => {
  const img = e.target.closest('figure.fig img'); if (!img) return;
  const fig = img.closest('figure'); closePop();
  const r = img.getBoundingClientRect();
  popEl = document.createElement('div'); popEl.className = 'pop';
  const sz = fig.dataset.size || 'full';
  const spec = (P.assets[img.dataset.asset] || {}).spec;
  const specLabel = spec ? { chart: 'chart', map: 'map', timeline: 'timeline', network: 'relationship map' }[spec.type] : '';
  popEl.innerHTML = `${spec ? `<div class="pbtns" style="margin-bottom:8px"><button class="primary" data-a="spec">Edit ${specLabel}…</button></div>` : ''}<div class="small muted" style="margin-bottom:6px">Figure size</div><div class="pbtns" style="margin-bottom:8px">${[['full', 'Full width'], ['large', 'Large'], ['half', 'Half']].map(([k, l]) => `<button data-a="sz" data-v="${k}" class="${k === sz ? 'primary' : ''}">${l}</button>`).join('')}</div><div class="pbtns"><button data-a="alt">Alt text…</button><button data-a="rep">Replace image…</button><button class="danger" data-a="del">Remove</button></div>`;
  document.body.appendChild(popEl);
  popEl.style.left = Math.max(8, Math.min(innerWidth - popEl.offsetWidth - 8, r.left + r.width / 2 - popEl.offsetWidth / 2)) + 'px';
  popEl.style.top = Math.max(8, Math.min(innerHeight - popEl.offsetHeight - 8, r.top + 12)) + 'px';
  popEl.addEventListener('click', async ev => {
    const b = ev.target.closest('button'); if (!b) return; const a = b.dataset.a; closePop();
    if (a === 'spec') { openSpecEditor(spec, fig); return; }
    if (a === 'sz') { fig.dataset.size = b.dataset.v; onEdit(); }
    if (a === 'alt') { const t = await ask('Alt text', 'Describe the image for screen readers and e-books (the caption is separate).', 'Save', img.alt || ''); if (t !== null) { img.alt = t; onEdit(); } }
    if (a === 'rep') { figReplace = fig; $('#fileFigure').click(); }
    if (a === 'del') { const nx = fig.nextElementSibling; fig.remove(); if (nx) caretInto(nx); onEdit(); renumberFigures(); }
  });
});

/* paste & drop image files straight into the editor */
editor.addEventListener('paste', e => {
  const files = [...(e.clipboardData?.files || [])].filter(f => /^image\//.test(f.type));
  if (!files.length || e.clipboardData.getData('text/html').includes('<table')) return;
  e.preventDefault(); e.stopImmediatePropagation(); saveSelectionNow(); insertFigureFiles(files);
}, true);
editor.addEventListener('drop', e => {
  const files = [...(e.dataTransfer?.files || [])].filter(f => /^image\//.test(f.type)); if (!files.length) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const r = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null;
  if (r && editor.contains(r.startContainer)) { const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); }
  insertFigureFiles(files);
}, true);
/* data: images inside pasted HTML become assets after the paste lands */
async function adoptInlineImages(root = editor) {
  const imgs = $$('img:not([data-asset])', root); if (!imgs.length) return 0;
  let n = 0;
  for (const img of imgs) {
    const src = img.getAttribute('src') || '';
    if (/^data:image\//.test(src)) { const id = await dataURLToAsset(src); if (id) { img.removeAttribute('src'); img.dataset.asset = id; n++; } else img.remove(); }
    else img.remove();
  }
  $$('img[data-asset]', root).forEach(img => { if (!img.closest('figure')) { const f = document.createElement('figure'); f.className = 'fig'; f.dataset.size = 'full'; const blk = img.closest('p') && img.closest('p').parentNode === root && !img.closest('p').textContent.trim() ? img.closest('p') : null; (blk || img).replaceWith(f); f.append(img); const c = document.createElement('figcaption'); c.innerHTML = '<br>'; f.append(c); } });
  prepFigureDom(root); return n;
}

/* ---------- export helpers ---------- */
function prepExportFigures(tmp) {
  let f = 0, t = 0; const list = [];
  $$('figure.av', tmp).forEach(f => f.removeAttribute('contenteditable'));
  $$('figure:not(.av)', tmp).forEach(fig => {
    fig.removeAttribute('contenteditable');
    const isT = fig.classList.contains('tbl');
    let cap = fig.querySelector(':scope > figcaption');
    if (!cap) { cap = document.createElement('figcaption'); isT ? fig.prepend(cap) : fig.append(cap); }
    cap.removeAttribute('contenteditable');
    const n = isT ? ++t : ++f, label = (isT ? 'Table ' : 'Figure ') + n + '.';
    fig.id = (isT ? 'tbl-' : 'fig-') + n;
    const clean = cap.cloneNode(true); $$('.cite,.fn,.flag,.cmt-pt', clean).forEach(x => x.remove());
    const text = clean.textContent.replace(/\s+/g, ' ').trim();
    list.push({ isT, n, id: fig.id, label, text });
    if (!text && !cap.querySelector('.cite,.fn,.flag')) cap.innerHTML = '';
    const lab = document.createElement('span'); lab.className = 'fig-n'; lab.textContent = label;
    cap.prepend(lab, document.createTextNode(cap.childNodes.length ? ' ' : ''));
    $$('img', fig).forEach(img => { const a = P.assets[img.dataset.asset]; if (a) { img.setAttribute('src', a.data); if (!img.hasAttribute('alt')) img.setAttribute('alt', ''); } else img.remove(); });
  });
  $$('nav.lof', tmp).forEach(nav => {
    nav.removeAttribute('contenteditable');
    if (!list.length) { nav.remove(); return; }
    const sec = (arr, h) => arr.length ? `<h2 class="lof-h">${h}</h2><ol>${arr.map(x => `<li><a href="#${x.id}">${esc(x.label)} ${esc(x.text)}</a></li>`).join('')}</ol>` : '';
    nav.innerHTML = `<h1 class="toc-title">Figures and Tables</h1>${sec(list.filter(x => !x.isT), 'Figures')}${sec(list.filter(x => x.isT), 'Tables')}`;
  });
  return list;
}
function lofPlaceholder() { return '<nav class="lof" contenteditable="false"><p>List of figures and tables — filled in when you export.</p></nav>'; }
function addTableRules(td) {
  td.addRule('figTable', {
    filter: n => n.nodeName === 'FIGURE' && n.classList.contains('tbl'),
    replacement: (c, n) => {
      const cap = n.querySelector('figcaption'), rows = [...n.querySelectorAll('tr')].map(tr => [...tr.cells].map(x => td.turndown(x.innerHTML).replace(/\n+/g, ' ').replace(/\|/g, '\\|').trim()));
      if (!rows.length) return '';
      const w = Math.max(...rows.map(r => r.length)); rows.forEach(r => { while (r.length < w) r.push(''); });
      const line = r => '| ' + r.join(' | ') + ' |';
      return `\n\n${cap ? '**' + td.turndown(cap.innerHTML).replace(/\*\*/g, '').trim() + '**\n\n' : ''}${line(rows[0])}\n${line(rows[0].map(() => '---'))}\n${rows.slice(1).map(line).join('\n')}\n\n`;
    },
  });
  td.addRule('figImage', {
    filter: n => n.nodeName === 'FIGURE' && !n.classList.contains('tbl'),
    replacement: (c, n) => { const img = n.querySelector('img'), cap = n.querySelector('figcaption'); const ct = cap ? td.turndown(cap.innerHTML).trim() : ''; return `\n\n${img ? `![${(img.alt || ct.replace(/[\[\]*]/g, '')).slice(0, 120)}](${img.getAttribute('src')})` : ''}\n\n${ct ? '*' + ct.replace(/^\*\*|\*\*$/g, '') + '*' : ''}\n\n`; },
  });
  return td;
}

/* Word (.docx) pieces */
function figureToDocx(fig, ctx, runs, trimRuns) {
  const D = docx, out = [], isT = fig.classList.contains('tbl');
  const cap = fig.querySelector(':scope > figcaption');
  const capPara = keepNext => { if (!cap) return null; const c = cap.cloneNode(true); $$('.fig-n', c).forEach(s => { const b = document.createElement('strong'); b.textContent = s.textContent; s.replaceWith(b); }); return new D.Paragraph({ children: runs(trimRuns(c), {}, Math.max(16, ctx.size - 2)), alignment: isT ? D.AlignmentType.LEFT : D.AlignmentType.CENTER, keepNext, spacing: { before: isT ? 200 : 60, after: isT ? 80 : 240, line: 260 } }); };
  if (isT) { const p = capPara(true); if (p) out.push(p); const t = fig.querySelector('table'); if (t) out.push(tableToDocx(t, ctx, runs, trimRuns)); out.push(new D.Paragraph({ spacing: { after: 120 }, children: [] })); return out; }
  $$('img', fig).forEach(img => {
    const p = dataURLParts(img.getAttribute('src')); if (!p) return;
    const type = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/bmp': 'bmp' }[p.mime]; if (!type) return;
    const a = P.assets[img.dataset.asset] || {}, max = { full: 624, large: 468, half: 312 }[fig.dataset.size || 'full'] || 624;
    const W = Math.min(max, a.w || max), H = Math.round(W * ((a.h || 3) / (a.w || 4)));
    out.push(new D.Paragraph({ alignment: D.AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 60 }, children: [new D.ImageRun({ type, data: p.bytes, transformation: { width: W, height: H }, altText: { name: 'figure', title: (cap && cap.textContent.trim().slice(0, 80)) || 'Figure', description: img.alt || (cap ? cap.textContent.trim() : '') } })] }));
  });
  const p = capPara(false); if (p) out.push(p);
  return out;
}
function tableToDocx(t, ctx, runs, trimRuns) {
  const D = docx, rows = [...t.rows];
  const cols = Math.max(1, ...rows.map(r => [...r.cells].reduce((n, c) => n + (c.colSpan || 1), 0)));
  const total = 9360, cw = Math.floor(total / cols);
  return new D.Table({
    width: { size: total, type: D.WidthType.DXA }, columnWidths: Array(cols).fill(cw),
    rows: rows.map(tr => new D.TableRow({
      tableHeader: tr.parentElement.nodeName === 'THEAD',
      children: [...tr.cells].map(c => new D.TableCell({
        columnSpan: c.colSpan > 1 ? c.colSpan : undefined, rowSpan: c.rowSpan > 1 ? c.rowSpan : undefined,
        width: { size: cw * (c.colSpan || 1), type: D.WidthType.DXA },
        shading: c.nodeName === 'TH' ? { fill: 'EDEDED', type: D.ShadingType.CLEAR, color: 'auto' } : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new D.Paragraph({ children: runs(trimRuns(c), c.nodeName === 'TH' ? { b: true } : {}, Math.max(16, ctx.size - 2)), spacing: { line: 240, after: 0 } })],
      })),
    })),
  });
}

/* ePub: data-URL images become files in the book */
function epubImages(htmlChunks) {
  const files = [], seen = {}; let k = 0;
  const swap = html => html.replace(/(<img\b[^>]*?\bsrc=")(data:image\/(png|jpeg|gif|webp|svg\+xml);base64,[^"]+)(")/g, (m, a, src, t, z) => {
    if (!seen[src]) { const ext = { png: 'png', jpeg: 'jpg', gif: 'gif', webp: 'webp', 'svg+xml': 'svg' }[t]; const name = `img/f${++k}.${ext}`; seen[src] = name; files.push({ name, mime: 'image/' + t, id: 'img' + k, bytes: b64ToBytes(src.split(',')[1]) }); }
    return a + seen[src] + z;
  });
  return { chunks: htmlChunks.map(swap), files };
}

/* ================================================================
   Marginalia: notes in the margin, anchored to text
   Built on the document's comments (doc.comments + .cmt anchors), so they still
   export to Word as real comments when you want that.
   ================================================================ */
const margin = $('#margin');
let mgMode = 'wide';
function mgVisible() { return PREFS.showMargin !== false && !document.body.classList.contains('focus'); }
function mgAnchors() { return $$('.cmt', editor).map(el => ({ el, c: findComment(el.dataset.cmt) })).filter(x => x.c); }
function renderMargin(focusId = null) {
  if (!margin || !P) return;
  const doc = curDoc(); if (!doc || homeOn || boardOn || planOn || draftsOn) { margin.innerHTML = ''; return; }
  const items = mgAnchors();
  document.body.classList.toggle('has-margin', !!items.length && mgVisible());
  $('#btnMargin').classList.toggle('on', PREFS.showMargin !== false);
  $('#btnMargin').querySelector('span').textContent = items.length ? String(items.length) : '';
  if (!items.length || !mgVisible()) { margin.innerHTML = ''; return; }
  const page = $('#page'), sc = $('#scroller');
  const room = sc.clientWidth - page.offsetWidth;
  mgMode = room >= 2 * 250 ? 'wide' : room >= 250 ? 'shift' : 'narrow';
  document.body.classList.toggle('mg-shift', mgMode === 'shift');
  document.body.classList.toggle('mg-narrow', mgMode === 'narrow');
  const seen = new Set(), keep = {};
  $$('.mg-card', margin).forEach(c => { keep[c.dataset.id] = c; });
  const pr = page.getBoundingClientRect();
  let bottom = 0;
  items.forEach(({ el, c }, i) => {
    if (seen.has(c.id)) return; seen.add(c.id);
    let card = keep[c.id];
    if (!card) {
      card = document.createElement('div'); card.className = 'mg-card'; card.dataset.id = c.id;
      card.innerHTML = `<div class="mg-head"><span class="mg-n"></span><span class="mg-when"></span><button class="ghost small mg-del" title="Delete this margin note">✕</button></div><textarea rows="1" placeholder="Margin note…" aria-label="Margin note"></textarea>`;
      margin.appendChild(card);
    }
    delete keep[c.id];
    const ta = card.querySelector('textarea');
    if (document.activeElement !== ta && ta.value !== c.text) ta.value = c.text;
    card.querySelector('.mg-n').textContent = i + 1;
    card.querySelector('.mg-when').textContent = relTime(c.date);
    card.classList.toggle('mg-collapsed', mgMode === 'narrow' && document.activeElement !== ta && !card.classList.contains('mg-open'));
    autoGrow(ta);
    const top = el.getBoundingClientRect().top - pr.top - 4;
    const y = Math.max(top, bottom + 6);
    card.style.top = y + 'px';
    bottom = y + card.offsetHeight;
  });
  Object.values(keep).forEach(c => c.remove());
  if (focusId) { const card = $(`.mg-card[data-id="${focusId}"]`, margin); if (card) { card.classList.add('mg-open'); card.classList.remove('mg-collapsed'); const ta = card.querySelector('textarea'); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); card.scrollIntoView({ block: 'nearest' }); } }
}
const renderMarginSoon = debounce(() => renderMargin(), 120);
function autoGrow(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(320, ta.scrollHeight + 2) + 'px'; }
editor.addEventListener('input', renderMarginSoon);
window.addEventListener('resize', renderMarginSoon);
if (window.ResizeObserver) new ResizeObserver(renderMarginSoon).observe(editor);
editor.addEventListener('load', renderMarginSoon, true);
function hotAnchor(id, on) { $$(`.cmt[data-cmt="${id}"]`, editor).forEach(a => on ? a.setAttribute('data-cp-hot', '') : a.removeAttribute('data-cp-hot')); }
margin.addEventListener('input', e => {
  const card = e.target.closest('.mg-card'); if (!card) return;
  const c = findComment(card.dataset.id); if (!c) return;
  c.text = e.target.value; autoGrow(e.target); markDirty(); renderMarginSoon();
});
margin.addEventListener('focusin', e => { const card = e.target.closest('.mg-card'); if (card) { card.classList.add('mg-open'); card.classList.remove('mg-collapsed'); hotAnchor(card.dataset.id, true); } });
margin.addEventListener('focusout', e => {
  const card = e.target.closest('.mg-card'); if (!card) return;
  hotAnchor(card.dataset.id, false); card.classList.remove('mg-open');
  setTimeout(() => {
    const c = findComment(card.dataset.id);
    if (c && !c.text.trim() && !card.contains(document.activeElement)) { removeComment(c.id); }
    renderMargin(); renderOutline();
  }, 120);
});
margin.addEventListener('mouseover', e => { const card = e.target.closest('.mg-card'); if (card) hotAnchor(card.dataset.id, true); });
margin.addEventListener('mouseout', e => { const card = e.target.closest('.mg-card'); if (card && !card.contains(e.relatedTarget) && !card.contains(document.activeElement)) hotAnchor(card.dataset.id, false); });
margin.addEventListener('click', e => {
  const card = e.target.closest('.mg-card'); if (!card) return;
  if (e.target.closest('.mg-del')) { removeComment(card.dataset.id); renderMargin(); toast('Margin note deleted.'); return; }
  if (card.classList.contains('mg-collapsed')) { renderMargin(card.dataset.id); }
});
margin.addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.preventDefault(); const id = e.target.closest('.mg-card')?.dataset.id; const a = id && $(`.cmt[data-cmt="${id}"]`, editor); e.target.blur(); if (a) { const r = document.createRange(); r.setStartAfter(a); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus({ preventScroll: true }); } }
});
async function addComment() {
  const doc = curDoc(), sel = getSelection();
  if (!sel.rangeCount || !editor.contains(sel.anchorNode)) { restoreSelection(); }
  if (!sel.rangeCount || !editor.contains(sel.anchorNode)) { toast('Click in the text where the margin note belongs.'); return; }
  const r = sel.getRangeAt(0).cloneRange();
  const blk = n => { while (n && n.parentNode !== editor) n = n.parentNode; return n; };
  const id = uid('c'), span = document.createElement('span'); span.className = 'cmt'; span.dataset.cmt = id;
  if (!r.collapsed && blk(r.startContainer) === blk(r.endContainer) && !r.cloneContents().querySelector('figure,table,.cmt')) { span.appendChild(r.extractContents()); r.insertNode(span); }
  else { r.collapse(false); span.classList.add('cmt-pt'); span.setAttribute('contenteditable', 'false'); r.insertNode(span); }
  doc.comments.push({ id, text: '', author: doc.meta.author || '', date: nowISO() });
  if (PREFS.showMargin === false) { PREFS.showMargin = true; savePrefs(); }
  syncEditor(); markDirty();
  renderMargin(id); renderOutline();
}
function removeComment(id, el) {
  const doc = curDoc(); doc.comments = doc.comments.filter(c => c.id !== id);
  $$(`.cmt[data-cmt="${id}"]`, editor).forEach(a => a.replaceWith(...a.childNodes));
  syncEditor(); markDirty(); renderOutline(); renderMarginSoon();
}
$('#btnMargin').addEventListener('click', () => { PREFS.showMargin = PREFS.showMargin === false; savePrefs(); renderMargin(); toast(PREFS.showMargin ? 'Margin notes shown.' : 'Margin notes hidden. They stay in the document.'); });
/* clicking an anchor in the text opens its card */
editor.addEventListener('click', e => {
  const s = e.target.closest('.cmt'); if (!s || e.target.closest('.cite,.fn,.flag')) return;
  if (PREFS.showMargin === false) { PREFS.showMargin = true; savePrefs(); }
  renderMargin(s.dataset.cmt);
});
/* export: gather marginalia onto a separate page */
function collectMarginalia(tmp, mode) {
  const out = [];
  let sec = '';
  const walker = document.createTreeWalker(tmp, NodeFilter.SHOW_ELEMENT);
  while (walker.nextNode()) {
    const el = walker.currentNode;
    if (/^H[1-3]$/.test(el.nodeName) && !el.closest('nav')) sec = el.textContent.replace(/\s+/g, ' ').trim();
    if (!el.classList.contains('cmt')) continue;
    const c = findComment(el.dataset.cmt); if (!c || !c.text.trim()) continue;
    const id = 'mg-' + (out.length + 1);
    let passage = el.textContent.replace(/\s+/g, ' ').trim();
    if (!passage) {
      const blk = el.closest('p,li,blockquote,h1,h2,h3,figcaption,td,th');
      if (blk) { const r = document.createRange(); r.setStartAfter(el); r.setEnd(blk, blk.childNodes.length); const after = r.toString().replace(/\s+/g, ' ').trim(); passage = after ? after.split(' ').slice(0, 14).join(' ') + (after.split(' ').length > 14 ? '…' : '') : blockSnippet(blk, 80); }
    } else if (passage.split(' ').length > 30) passage = passage.split(' ').slice(0, 30).join(' ') + '…';
    const a = document.createElement('a'); a.id = id; a.className = 'mg-a'; el.before(a);
    out.push({ id, n: out.length + 1, passage, text: c.text.trim(), sec, date: c.date });
  }
  return out;
}
function marginaliaHTML(list, mode) {
  if (!list.length) return '';
  const page = mode === 'paged' ? x => `<a class="mg-ref" href="#${x.id}"></a>` : () => '';
  return `<section class="end-sec marginalia"><h2 class="end-h">Marginalia</h2>${list.map(x => `<div class="mg-entry"><p class="mg-loc"><b>${x.n}.</b> ${mode === 'paged' ? 'p. ' + page(x) + ' · ' : ''}${esc(x.sec || 'Opening')}</p>${x.passage ? `<p class="mg-pass">“${esc(x.passage)}”</p>` : ''}<p class="mg-note">${esc(x.text).replace(/\n/g, '<br>')}</p></div>`).join('')}</section>`;
}

/* ================================================================
   Substack: endnotes, inline images, tables drawn as images
   ================================================================ */
function tableToPNG(table, caption = '') {
  const rows = [...table.rows].map(tr => [...tr.cells].map(c => ({ t: c.innerText.replace(/\s+/g, ' ').trim(), h: c.nodeName === 'TH' || tr.parentElement.nodeName === 'THEAD' })));
  const ncol = Math.max(1, ...rows.map(r => r.length));
  const S = 2, pad = 10, lh = 21, maxW = 1100;
  const c = document.createElement('canvas'), g = c.getContext('2d');
  const font = h => (h ? 'bold ' : '') + '15px Georgia, "Times New Roman", serif';
  const natural = Array(ncol).fill(60);
  rows.forEach(r => r.forEach((cell, i) => { g.font = font(cell.h); natural[i] = Math.max(natural[i], Math.min(300, g.measureText(cell.t).width + pad * 2)); }));
  let total = natural.reduce((a, b) => a + b, 0); const k = total > maxW ? maxW / total : 1; const widths = natural.map(w => Math.floor(w * k)); total = widths.reduce((a, b) => a + b, 0);
  const wrap = (t, w, h) => { g.font = font(h); const words = t.split(' '), lines = []; let cur = ''; words.forEach(wd => { const tryL = cur ? cur + ' ' + wd : wd; if (g.measureText(tryL).width > w - pad * 2 && cur) { lines.push(cur); cur = wd; } else cur = tryL; }); lines.push(cur); return lines; };
  const laid = rows.map(r => { const cells = Array.from({ length: ncol }, (_, i) => r[i] || { t: '', h: false }).map((cell, i) => ({ ...cell, lines: wrap(cell.t, widths[i], cell.h) })); return { cells, h: Math.max(...cells.map(x => x.lines.length)) * lh + pad * 2 - 4 }; });
  const capLines = caption ? wrap(caption, total, true) : [];
  const capH = capLines.length ? capLines.length * lh + 8 : 0;
  const H = laid.reduce((a, r) => a + r.h, 0) + capH;
  c.width = (total + 2) * S; c.height = (H + 2) * S; g.scale(S, S);
  g.fillStyle = '#fff'; g.fillRect(0, 0, total + 2, H + 2); g.textBaseline = 'top';
  g.fillStyle = '#111'; capLines.forEach((l, i) => { g.font = font(true); g.fillText(l, 1, i * lh); });
  let y = capH + 1;
  laid.forEach(r => {
    let x = 1;
    r.cells.forEach((cell, i) => {
      if (cell.h) { g.fillStyle = '#efefef'; g.fillRect(x, y, widths[i], r.h); }
      g.strokeStyle = '#9a9a9a'; g.lineWidth = 1; g.strokeRect(x + .5, y + .5, widths[i], r.h);
      g.fillStyle = '#111'; g.font = font(cell.h); cell.lines.forEach((l, j) => g.fillText(l, x + pad, y + pad - 2 + j * lh));
      x += widths[i];
    });
    y += r.h;
  });
  return c.toDataURL('image/png');
}
function substackBuild(doc) {
  const x = buildExport(doc, 'html');
  const box = document.createElement('div'); box.innerHTML = (x.title ? x.title.replace(/<p class="tb-title">([\s\S]*?)<\/p>/, '<h1>$1</h1>') : '') + x.body;
  let tables = 0; const images = [];
  $$('figure.tbl', box).forEach(f => {
    const t = f.querySelector('table'); if (!t) return;
    const cap = f.querySelector('figcaption'); const ct = cap ? cap.textContent.replace(/\s+/g, ' ').trim() : '';
    document.body.appendChild(box); box.style.cssText = 'position:fixed;left:-9999px;top:0;width:900px';
    const png = tableToPNG(t, ''); box.remove(); box.style.cssText = '';
    const img = document.createElement('img'); img.src = png; img.alt = ct || 'Table'; t.replaceWith(img); tables++;
    if (cap) f.append(cap); // caption below the image, as on Substack
  });
  $$('img', box).forEach((img, i) => { const src = img.getAttribute('src') || ''; if (src.startsWith('data:')) images.push({ src, alt: img.alt }); });
  $$('sup.fnref', box).forEach(s => { const n = s.textContent; s.innerHTML = `<a href="#fn-${n}" id="fnref-${n}">${n}</a>`; });
  $$('mark', box).length;
  const flags = $$('mark', box).length;
  let notes = '';
  if (x.out.notes.length) notes = `<hr><h3>Notes</h3>${x.out.notes.map(n => `<p id="fn-${n.n}"><a href="#fnref-${n.n}">${n.n}.</a> ${n.html}</p>`).join('')}`;
  let bib = '';
  if (x.out.bib) bib = `<h3>${esc(x.out.heading)}</h3>${x.out.bib.entries.map(e => `<p>${e.replace(/<\/?div[^>]*>/g, '')}</p>`).join('')}`;
  const html = box.innerHTML + notes + bib;
  return { html, images, tables, notes: x.out.notes.length, flags, title: doc.title };
}
function openSubstack() {
  const doc = curDoc(); if (!doc) return;
  const s = substackBuild(doc); substackLast = s;
  const figs = (doc.html.match(/<figure class="fig/g) || []).length;
  $('#ssSum').innerHTML = `<ul class="ss-list">
    <li><b>${s.notes}</b> note${s.notes === 1 ? '' : 's'} → a numbered <i>Notes</i> section at the end, linked from the text</li>
    <li><b>${figs}</b> figure${figs === 1 ? '' : 's'} → images with captions</li>
    <li><b>${s.tables}</b> table${s.tables === 1 ? '' : 's'} → drawn as image${s.tables === 1 ? '' : 's'} (Substack has no tables)</li>
    ${s.flags ? `<li class="warn"><b>${s.flags}</b> unresolved flag${s.flags === 1 ? '' : 's'} (TK, cite?, check) would print as [TK] — clear them first</li>` : ''}
  </ul>`;
  $('#ssDlg').showModal();
}
let substackLast = null;
$('#ssCopy').addEventListener('click', async () => {
  const s = substackLast || substackBuild(curDoc());
  try {
    await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([s.html], { type: 'text/html' }), 'text/plain': new Blob([htmlToText(s.html)], { type: 'text/plain' }) })]);
    toast('Copied. Paste into a new Substack post. If an image doesn’t come through, upload it from the downloaded package.');
  } catch (e) { toast('The browser blocked clipboard access. Use Download package instead.'); }
});
$('#ssZip').addEventListener('click', () => {
  const s = substackLast || substackBuild(curDoc());
  let k = 0; const files = [];
  const html = s.html.replace(/src="(data:image\/(png|jpeg|gif|webp);base64,[^"]+)"/g, (m, src, t) => { const name = `images/${String(++k).padStart(2, '0')}.${t === 'jpeg' ? 'jpg' : t}`; files.push({ name, data: b64ToBytes(src.split(',')[1]) }); return `src="${name}"`; });
  const page = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${esc(s.title)}</title><style>body{font:18px/1.6 Georgia,serif;max-width:680px;margin:40px auto;padding:0 16px;color:#111}img{max-width:100%;height:auto}figure{margin:1.5em 0}figcaption{font-size:.85em;color:#555}.fig-n{font-weight:bold}</style></head><body>${html}</body></html>`;
  const readme = `Substack package for “${s.title}”\n\npost.html — open it in a browser, select all, copy, and paste into a new Substack post.\nimages/ — the figures and tables in order (01, 02, …). If an image doesn’t paste, upload it in Substack where it belongs.\n\nNotes appear as a numbered Notes section at the end of the post.\n`;
  const blob = zipStore([{ name: 'post.html', data: page }, { name: 'README.txt', data: readme }, ...files]);
  download(fileSafe(s.title) + ' - Substack.zip', new Blob([blob], { type: 'application/zip' }), 'application/zip');
  $('#ssDlg').close();
});
$('#ssClose').addEventListener('click', () => $('#ssDlg').close());

/* ================================================================
   Markdown import: Notecards folders and Obsidian vaults
   ================================================================ */
function parseYaml(y) {
  const o = {}; let key = null;
  y.split(/\r?\n/).forEach(line => {
    const li = line.match(/^\s*-\s+(.*)$/);
    if (li && key) { (Array.isArray(o[key]) ? o[key] : (o[key] = [])).push(unq(li[1])); return; }
    const kv = line.match(/^([A-Za-z_][\w-]*)\s*:\s*(.*)$/); if (!kv) return;
    key = kv[1].toLowerCase(); const v = kv[2].trim();
    if (!v) { o[key] = []; return; }
    if (/^\[.*\]$/.test(v)) o[key] = v.slice(1, -1).split(',').map(unq).filter(Boolean); else o[key] = unq(v);
  });
  return o;
  function unq(s) { return String(s).trim().replace(/^["']|["']$/g, ''); }
}
function mdToNote(text, file, root) {
  let fm = {};
  const m = text.match(/^﻿?---\s*\r?\n([\s\S]*?)\r?\n---\s*(\r?\n|$)/);
  if (m) { fm = parseYaml(m[1]); text = text.slice(m[0].length); }
  let title = typeof fm.title === 'string' ? fm.title : '';
  const h = text.match(/^\s*#\s+(.+)\r?\n?/);
  if (h && !title) { title = h[1].trim(); text = text.slice(h[0].length); }
  if (!title) title = file.name.replace(/\.(md|markdown|txt)$/i, '');
  const tags = [];
  const fmTags = fm.tags ?? fm.tag ?? fm.keywords;
  if (Array.isArray(fmTags)) tags.push(...fmTags); else if (typeof fmTags === 'string') tags.push(...fmTags.split(/[,\s]+/));
  const prose = text.replace(/```[\s\S]*?```/g, '').replace(/`[^`]*`/g, '');
  prose.split(/\r?\n/).forEach(l => { if (/^\s*#{1,6}\s/.test(l)) return; (l.match(/(^|\s)#([A-Za-z][\w/-]{0,60})/g) || []).forEach(t => tags.push(t.trim().slice(1))); });
  let skipped = 0;
  text = text.replace(/!\[\[([^\]]+)\]\]/g, (x, f) => { skipped++; return `[attachment: ${f.split('|')[0]}]`; })
    .replace(/!\[([^\]]*)\]\((?!https?:)([^)]+)\)/g, (x, alt, f) => { skipped++; return `[image: ${alt || f}]`; });
  const url = [fm.source, fm.url, fm.link, fm.href].find(v => typeof v === 'string' && /^https?:\/\//.test(v));
  const src = url ? P.sources.find(s => (s.csl.URL || '').replace(/\/$/, '') === url.replace(/\/$/, '')) : null;
  if (url && !src && !text.includes(url)) text = text.trimEnd() + `\n\nSource: ${url}`;
  const when = [fm.created, fm.date, fm['date created']].find(v => typeof v === 'string' && !isNaN(Date.parse(v)));
  const kind = typeof fm.kind === 'string' && KINDS.some(k => k[0] === fm.kind) ? fm.kind : typeof fm.type === 'string' && KINDS.some(k => k[0] === fm.type) ? fm.type : 'idea';
  const rel = (file.webkitRelativePath || '').split('/');
  const folder = rel.length > 2 ? rel[1] : '';
  return { note: Object.assign(newNote(), { title, body: text.trim(), tags: [...new Set(tags.map(t => t.replace(/^#/, '').trim()).filter(Boolean))], kind, sourceId: src ? src.id : '', created: when ? new Date(when).toISOString() : new Date(file.lastModified || Date.now()).toISOString(), modified: new Date(file.lastModified || Date.now()).toISOString() }), folder, skipped };
}
async function importMarkdownFiles(fileList) {
  const all = [...fileList];
  const files = all.filter(f => /\.(md|markdown|txt)$/i.test(f.name) && !(f.webkitRelativePath || '').split('/').some(s => s.startsWith('.') || s === 'node_modules'));
  if (!files.length) { toast('No Markdown (.md) files found there.'); return; }
  const parsed = [];
  for (const f of files) { try { parsed.push(mdToNote(await f.text(), f)); } catch (e) { console.warn(f.name, e); } }
  const folders = [...new Set(parsed.map(p => p.folder).filter(Boolean))];
  const usePiles = $('#mdPiles').checked && folders.length > 0;
  const key = n => (n.title + '\n' + n.body).trim().toLowerCase();
  const existing = new Set(P.notes.map(key));
  const fresh = parsed.filter(p => !existing.has(key(p.note)));
  const dup = parsed.length - fresh.length, skipped = parsed.reduce((n, p) => n + p.skipped, 0);
  const ok = await ask('Import notes', `${fresh.length} note${fresh.length === 1 ? '' : 's'} to import${dup ? `, ${dup} already here (skipped)` : ''}.${usePiles ? ` ${folders.length} folder${folders.length === 1 ? '' : 's'} become board piles.` : ''}${skipped ? ` ${skipped} embedded image${skipped === 1 ? '' : 's'} or attachment${skipped === 1 ? '' : 's'} become text placeholders.` : ''}`, 'Import');
  if (!ok) return;
  if (usePiles) folders.forEach(name => { if (!P.piles.some(p => p.name === name)) P.piles.push({ id: uid('pl'), name }); });
  let order = P.notes.length ? Math.max(...P.notes.map(n => +n.order || 0)) + 1 : 0;
  fresh.sort((a, b) => a.note.created.localeCompare(b.note.created)).forEach(p => {
    p.note.order = order++;
    if (usePiles && p.folder) p.note.pile = (P.piles.find(x => x.name === p.folder) || {}).id || '';
    P.notes.push(p.note);
  });
  renderNoteList(); switchTab('notes'); markDirty();
  const links = fresh.reduce((n, p) => n + (p.note.body.match(/\[\[/g) || []).length, 0);
  toast(`Imported ${fresh.length} note${fresh.length === 1 ? '' : 's'}${links ? `, with ${links} [[link${links === 1 ? '' : 's'}]] between notes` : ''}.`);
}
function openMdImport() { $('#mdPiles').checked = true; $('#mdDlg').showModal(); }
$('#mdFolder').addEventListener('click', () => { $('#mdDlg').close(); $('#fileMdDir').click(); });
$('#mdFiles').addEventListener('click', () => { $('#mdDlg').close(); $('#fileMd').click(); });
$('#mdCancel').addEventListener('click', () => $('#mdDlg').close());
$('#fileMdDir').addEventListener('change', e => { const f = [...e.target.files]; e.target.value = ''; if (f.length) importMarkdownFiles(f); });

/* ================================================================
   Autosave to the project file (Chrome / Edge, File System Access)
   ================================================================ */
let pendingHandle = null, autoFailed = false;
const canFileAutosave = () => !!window.showSaveFilePicker;
async function permOf(h) { try { return h.queryPermission ? await h.queryPermission({ mode: 'readwrite' }) : 'granted'; } catch (e) { return 'denied'; } }
const fileAutosave = debounce(async () => {
  if (!PREFS.fileAutosave || !canFileAutosave() || !dirtyFile) return;
  const h = fileHandle; if (!h) { updateAutoState(); return; }
  if (await permOf(h) !== 'granted') { pendingHandle = h; updateAutoState(); return; }
  try {
    const text = await projectFileText();
    const w = await h.createWritable(); await w.write(text); await w.close();
    dirtyFile = false; dirtySince = null; snoozeUntil = 0; lastFileSave = new Date(); lastFileName = h.name; autoFailed = false;
    persistLocal(); updateSaveState(); ghAfterSave(true);
  } catch (e) { console.warn('autosave', e); autoFailed = true; updateAutoState(); }
}, 3000);
function updateAutoState() {
  const b = $('#autoResume'); if (!b) return;
  const need = PREFS.fileAutosave && canFileAutosave() && dirtyFile && ((pendingHandle && !fileHandle) || (fileHandle && pendingHandle === fileHandle) || autoFailed);
  b.classList.toggle('hidden', !need);
  b.textContent = autoFailed ? 'Autosave failed · retry' : 'Resume autosave';
}
$('#autoResume').addEventListener('click', async () => {
  const h = fileHandle || pendingHandle; if (!h) { saveProject(false); return; }
  try { if (h.requestPermission && (await h.requestPermission({ mode: 'readwrite' })) !== 'granted') { toast('Anabasis needs permission to write to the file.'); return; } } catch (e) {}
  fileHandle = h; pendingHandle = null; autoFailed = false; updateAutoState(); fileAutosave(); toast('Autosave is on for ' + h.name + '.');
});
async function restoreAutosaveHandle() {
  if (!PREFS.fileAutosave || !canFileAutosave() || fileHandle) return;
  const r = (await recentList()).find(x => x.pid === P.id && x.handle);
  if (!r) return;
  if (await permOf(r.handle) === 'granted') { fileHandle = r.handle; if (dirtyFile) fileAutosave(); }
  else pendingHandle = r.handle;
  updateAutoState();
}

/* ================================================================
   Password protection: AES-GCM with a PBKDF2 key. The key stays in memory only.
   ================================================================ */
let LOCK = null; // { key, salt, iter }
const ITER = 600000;
const isLocked = o => !!(o && o.encrypted === 1 && o.data && o.iv && o.kdf);
async function deriveKey(pass, salt, iter = ITER) {
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pass), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: iter }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}
async function sealText(text, extra = {}) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, LOCK.key, new TextEncoder().encode(text)));
  return JSON.stringify(Object.assign({ app: 'Anabasis', encrypted: 1, v: 1, kdf: { name: 'PBKDF2', hash: 'SHA-256', iter: LOCK.iter, salt: bytesToB64(LOCK.salt) }, cipher: 'AES-GCM', iv: bytesToB64(iv), data: bytesToB64(ct) }, extra));
}
async function openSealed(env, pass) {
  const salt = b64ToBytes(env.kdf.salt), iter = +env.kdf.iter || ITER, key = await deriveKey(pass, salt, iter);
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64ToBytes(env.iv) }, key, b64ToBytes(env.data)); // throws on a wrong password
  return { text: new TextDecoder().decode(pt), lock: { key, salt, iter } };
}
async function projectFileText() {
  const t = projectJSON(); if (!LOCK) return t;
  const sealed = await sealText(t);
  try { const env = JSON.parse(sealed), back = new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64ToBytes(env.iv) }, LOCK.key, b64ToBytes(env.data))); if (back === t) return sealed; } catch (e) {}
  throw new Error('The locked copy didn’t read back correctly, so nothing was written. Try again; if it keeps happening, remove the lock and save.');
}
function askPassword(title, msg, { confirm = false, allowFresh = false } = {}) {
  return new Promise(res => {
    const d = $('#pwDlg');
    $('#pwTitle').textContent = title; $('#pwMsg').textContent = msg; $('#pwErr').textContent = '';
    $('#pw1').value = ''; $('#pw2').value = ''; $('#pw2Row').classList.toggle('hidden', !confirm);
    $('#pwFresh').classList.toggle('hidden', !allowFresh);
    $('#pwWarn').classList.toggle('hidden', !confirm);
    $('#pwOk').textContent = confirm ? 'Lock project' : 'Unlock';
    $('#pwCancel').classList.toggle('hidden', allowFresh);
    const fin = v => { d.close(); $('#pwOk').onclick = $('#pwCancel').onclick = $('#pwFresh').onclick = d.oncancel = null; res(v); };
    $('#pwOk').onclick = () => {
      const a = $('#pw1').value;
      if (confirm) { if (a.length < 8) { $('#pwErr').textContent = 'Use at least 8 characters (a short phrase is best).'; return; } if (a !== $('#pw2').value) { $('#pwErr').textContent = 'The two passwords don’t match.'; return; } }
      if (!a) return; fin(a);
    };
    $('#pwCancel').onclick = () => fin(null);
    $('#pwFresh').onclick = () => fin('__fresh');
    d.oncancel = e => { if (allowFresh) { e.preventDefault(); return; } fin(null); };
    d.showModal(); setTimeout(() => $('#pw1').focus(), 30);
  });
}
$('#pwDlg').addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches('input')) { e.preventDefault(); $('#pwOk').click(); } });
async function unlockLoop(env, title, msg, allowFresh) {
  for (;;) {
    const pass = await askPassword(title, msg, { allowFresh });
    if (pass === null) return null;
    if (pass === '__fresh') return '__fresh';
    try { $('#pwOk').disabled = true; const r = await openSealed(env, pass); return r; }
    catch (e) { msg = 'That password didn’t unlock it. Try again.'; }
    finally { $('#pwOk').disabled = false; }
  }
}
async function openLockSettings() {
  if (LOCK) {
    const d = $('#lkDlg'); d.showModal(); return;
  }
  const pass = await askPassword('Lock this project', 'Anyone opening the project file, or this browser’s working copy, will need the password.', { confirm: true });
  if (!pass) return;
  const salt = crypto.getRandomValues(new Uint8Array(16));
  LOCK = { key: await deriveKey(pass, salt), salt, iter: ITER };
  document.body.classList.add('locked'); markDirty(); await persistLocal();
  if (fileHandle && PREFS.fileAutosave) fileAutosave();
  toast('Locked. Save the project now so the file on disk is locked too.');
}
$('#lkChange').addEventListener('click', async () => { $('#lkDlg').close(); const old = LOCK; LOCK = null; const pass = await askPassword('New password', 'Choose a new password for this project.', { confirm: true }); if (!pass) { LOCK = old; return; } const salt = crypto.getRandomValues(new Uint8Array(16)); LOCK = { key: await deriveKey(pass, salt), salt, iter: ITER }; markDirty(); persistLocal(); toast('Password changed. Save the project to update the file.'); });
$('#lkRemove').addEventListener('click', async () => { $('#lkDlg').close(); if (!(await ask('Remove the lock?', 'The project file and this browser’s copy will be stored as plain text again after the next save.', 'Remove lock'))) return; LOCK = null; document.body.classList.remove('locked'); markDirty(); persistLocal(); toast('Lock removed. Save to write an unlocked file.'); });
$('#lkClose').addEventListener('click', () => $('#lkDlg').close());
$('#lockBadge').addEventListener('click', openLockSettings);

/* ================================================================
   Figures you can edit again: charts, maps, timelines, relationship maps.
   Each is stored as an image asset plus the settings that made it (asset.spec),
   so it exports everywhere a picture does and reopens in its editor.
   ================================================================ */
const LIBS = {};
function useLib(id) { if (LIBS[id]) return; const s = document.createElement('script'); s.textContent = document.getElementById(id).textContent; document.head.appendChild(s); LIBS[id] = true; }
const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']; // validated categorical order (fixed, never cycled)
const VIZ = { ink: '#1d2733', ink2: '#52514e', grid: '#e4e6e3', surface: '#ffffff', font: '"Helvetica Neue", Helvetica, Arial, sans-serif', mapFont: 'Arial, Helvetica, sans-serif' };
const captionFor = s => [s.caption && s.caption.trim().replace(/([^.!?])$/, '$1.'), s.source && 'Source: ' + s.source.trim().replace(/([^.!?])$/, '$1.')].filter(Boolean).join(' ');
async function svgToPNG(svg, w, h, scale = 2) {
  const img = await loadImage('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg));
  const c = document.createElement('canvas'); c.width = Math.round(w * scale); c.height = Math.round(h * scale);
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
  return { data: c.toDataURL('image/png'), w: c.width, h: c.height };
}
async function renderSpec(spec) {
  if (spec.type === 'chart') return chartPNG(spec);
  if (spec.type === 'map') { const { svg, w, h } = mapSVG(spec); return svgToPNG(svg, w, h, 1.6); }
  if (spec.type === 'timeline') { const { svg, w, h } = timelineSVG(spec); return svgToPNG(svg, w, h, 1.6); }
  if (spec.type === 'network') { const { svg, w, h } = networkSVG(spec); return svgToPNG(svg, w, h, 1.6); }
  throw new Error('Unknown figure type');
}
let specTarget = null; // the figure being edited, if any
async function placeSpecFigure(spec, oldSpec) {
  const r = await renderSpec(spec);
  const id = addAsset(r.data, spec.type, r.w, r.h); P.assets[id].spec = JSON.parse(JSON.stringify(spec));
  const fig = specTarget; specTarget = null;
  if (fig && fig.isConnected) {
    fig.querySelector('img').dataset.asset = id;
    const cap = fig.querySelector('figcaption'), auto = oldSpec ? captionFor(oldSpec) : '';
    if (cap && (!cap.textContent.trim() || cap.textContent.trim() === auto.trim())) { const t = captionFor(spec); if (t) cap.textContent = t; else cap.innerHTML = '<br>'; }
    hydrateImages(); renumberFigures(); onEdit(); toast('Figure updated.');
    return;
  }
  if (boardOn) closeBoard(); if (relOn) closeRel(); if (planOn) closePlan(); if (homeOn) closeHome(); if (draftsOn) closeDrafts();
  restoreSelection();
  insertBlocksAtCursor(figHTML(id, captionFor(spec)) + '<p><br></p>');
  hydrateImages(); renumberFigures(); markDirty();
  toast('Figure added. Click it any time to edit.');
}
function openSpecEditor(spec, fig) {
  specTarget = fig || null;
  const s = JSON.parse(JSON.stringify(spec));
  if (s.type === 'chart') openChart(s);
  else if (s.type === 'map') openMap(s);
  else if (s.type === 'timeline') openTimelineFig(s);
  else if (s.type === 'network') openNetworkFig(s);
}
/* the toolbar figure button becomes a small menu */
function openFigureMenu() {
  saveSelectionNow(); closePop();
  const b = $('#btnFigure').getBoundingClientRect();
  popEl = document.createElement('div'); popEl.className = 'pop fig-menu';
  popEl.innerHTML = [['img', 'Image from a file…', 'Photo, scan, screenshot or chart you made elsewhere'], ['chart', 'Chart from data…', 'Paste a table: columns, bars, lines'], ['map', 'Map…', 'Shade countries, place markers, draw routes and areas'], ['timeline', 'Timeline…', 'From your dated notes'], ['network', 'Relationship map…', 'Who’s connected to whom, from your names list']]
    .map(([k, t, d]) => `<button data-f="${k}"><b>${t}</b><span>${d}</span></button>`).join('');
  document.body.appendChild(popEl);
  popEl.style.left = Math.max(8, Math.min(innerWidth - popEl.offsetWidth - 8, b.left)) + 'px'; popEl.style.top = (b.bottom + 6) + 'px';
  popEl.addEventListener('click', e => {
    const k = e.target.closest('[data-f]')?.dataset.f; if (!k) return; closePop(); specTarget = null;
    if (k === 'img') $('#fileFigure').click();
    if (k === 'chart') openChart();
    if (k === 'map') openMap();
    if (k === 'timeline') openTimelineFig();
    if (k === 'network') openRel(true);
  });
}

/* ---------------- charts ---------------- */
function parseTable(text) {
  const lines = String(text || '').replace(/\r/g, '').split('\n').filter(l => l.trim());
  if (!lines.length) return null;
  const delim = lines[0].includes('\t') ? '\t' : (lines[0].split(';').length > lines[0].split(',').length ? ';' : ',');
  const split = l => { if (delim !== ',') return l.split(delim).map(x => x.trim()); const out = []; let cur = '', q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === ',' && !q) { out.push(cur.trim()); cur = ''; } else cur += ch; } out.push(cur.trim()); return out; };
  const rows = lines.map(split);
  const head = rows[0], body = rows.slice(1);
  const num = v => { if (v == null) return null; let s = String(v).trim(); if (!s || s === '-' || s === '—') return null; const neg = /^\(.*\)$/.test(s); s = s.replace(/[()$€£¥%\s]/g, '').replace(/,(?=\d{3}\b)/g, ''); const n = parseFloat(s); return isNaN(n) ? null : neg ? -n : n; };
  const series = head.slice(1).map((name, i) => ({ name: name || 'Series ' + (i + 1), values: body.map(r => num(r[i + 1])) }));
  return { labels: body.map(r => r[0]), series, pct: /%/.test(text) };
}
function fmtNum(v, f) {
  if (v == null || isNaN(v)) return '';
  if (f === 'pct') return (Math.round(v * 10) / 10).toLocaleString() + '%';
  if (f === 'usd') return (v < 0 ? '−$' : '$') + Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (f === 'k') { const a = Math.abs(v); return (v < 0 ? '−' : '') + (a >= 1e9 ? +(a / 1e9).toFixed(1) + 'B' : a >= 1e6 ? +(a / 1e6).toFixed(1) + 'M' : a >= 1e3 ? +(a / 1e3).toFixed(1) + 'K' : a.toLocaleString()); }
  if (f === 'd1') return v.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 }).replace('-', '−');
}
const CH_SIZE = { wide: [800, 450], std: [800, 600], tall: [640, 800] };
function chartConfig(spec, data) {
  useLib('lib-chart');
  let kind = spec.kind || 'bar'; const area = kind === 'area'; if (area || kind === 'multi') kind = 'line';
  const horiz = kind === 'hbar' || kind === 'dot', many = data.series.length > 1;
  const ds = data.series.slice(0, 8).map((s, i) => {
    const c = SERIES[i];
    if (kind === 'line') return { label: s.name, data: s.values, borderColor: c, backgroundColor: c, fill: area ? { target: 'origin', above: c + (many ? '1f' : '2e') } : false, borderWidth: 2, pointRadius: data.labels.length > 24 ? 0 : 4, pointHoverRadius: 6, pointBorderColor: '#fff', pointBorderWidth: 2, tension: 0, spanGaps: true };
    if (kind === 'dot') return { label: s.name, data: s.values, type: 'line', showLine: false, borderColor: c, backgroundColor: c, pointRadius: 6, pointHoverRadius: 8, pointBorderColor: '#fff', pointBorderWidth: 2 };
    return { label: s.name, data: s.values, backgroundColor: c, borderColor: '#fff', borderWidth: kind === 'stack' ? { top: 2 } : 0, borderRadius: kind === 'stack' ? 0 : 4, borderSkipped: 'start', maxBarThickness: 46, categoryPercentage: .72, barPercentage: .9 };
  });
  const tick = { color: VIZ.ink2, font: { family: VIZ.font, size: 12 } };
  const valAxis = { beginAtZero: kind !== 'line' || area, stacked: kind === 'stack', grid: { color: VIZ.grid, drawTicks: false }, border: { display: false }, ticks: Object.assign({ padding: 6, callback: v => fmtNum(v, spec.fmt) }, tick), title: { display: !!spec.ylabel, text: spec.ylabel || '', color: VIZ.ink2, font: { family: VIZ.font, size: 12, weight: '600' } } };
  const catAxis = { stacked: kind === 'stack', grid: { display: false }, border: { color: '#c9c9c4' }, ticks: Object.assign({ autoSkip: true, maxRotation: 0 }, tick) };
  const endLabels = { id: 'endLabels', afterDatasetsDraw(ch) {
    if (kind !== 'line' || ch.data.datasets.length < 2 || ch.data.datasets.length > 4) return;
    const g = ch.ctx; g.save(); g.font = `600 12px ${VIZ.font}`; g.textBaseline = 'middle';
    const placed = [];
    ch.data.datasets.forEach((d, i) => { const meta = ch.getDatasetMeta(i); let k = d.data.length - 1; while (k >= 0 && d.data[k] == null) k--; if (k < 0) return; const pt = meta.data[k]; let y = pt.y; placed.forEach(p => { if (Math.abs(p - y) < 15) y = p + (y >= p ? 15 : -15); }); placed.push(y); g.fillStyle = VIZ.ink; g.fillText(d.label, pt.x + 9, y); });
    g.restore(); } };
  const bg = { id: 'bg', beforeDraw(ch) { const g = ch.ctx; g.save(); g.fillStyle = VIZ.surface; g.fillRect(0, 0, ch.width, ch.height); g.restore(); } };
  const lineEnds = kind === 'line' && many && data.series.length <= 4;
  return {
    type: kind === 'line' || kind === 'dot' ? 'line' : 'bar',
    data: { labels: data.labels, datasets: ds },
    plugins: [bg, eventsPlugin(spec, data.labels), endLabels],
    options: {
      indexAxis: horiz ? 'y' : 'x', animation: false, responsive: false, maintainAspectRatio: false,
      layout: { padding: { top: 8 + (!horiz && parseEvents(spec.events, data.labels).some(e => e.label) ? 20 : 0), right: lineEnds ? 110 : 16, bottom: 4, left: 4 } }, elements: { line: { fill: false } },
      interaction: { mode: kind === 'line' ? 'index' : 'nearest', intersect: kind !== 'line' },
      plugins: {
        legend: { display: many, position: 'top', align: 'start', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 8, boxHeight: 8, color: VIZ.ink, font: { family: VIZ.font, size: 12.5 }, padding: 14 } },
        tooltip: { backgroundColor: '#1d2733', titleFont: { family: VIZ.font }, bodyFont: { family: VIZ.font }, callbacks: { label: c => `${c.dataset.label}: ${fmtNum(c.parsed[horiz ? 'x' : 'y'], spec.fmt)}` } },
      },
      scales: horiz ? { x: valAxis, y: Object.assign({}, catAxis, { grid: { display: false }, border: { display: false } }) } : { x: catAxis, y: valAxis },
    },
  };
}
async function chartPNG(spec) {
  const data = parseTable(spec.data); if (!data || !data.series.length) throw new Error('No data to chart.');
  if (spec.kind === 'multi') return multiplesPNG(spec, data, 2);
  const [w, h] = CH_SIZE[spec.aspect] || CH_SIZE.wide;
  const holder = document.createElement('div'); holder.style.cssText = `position:fixed;left:-10000px;top:0;width:${w}px;height:${h}px`;
  const c = document.createElement('canvas'); c.width = w; c.height = h; c.style.width = w + 'px'; c.style.height = h + 'px'; holder.append(c); document.body.append(holder);
  const cfg = chartConfig(spec, data); cfg.options.devicePixelRatio = 2;
  const ch = new Chart(c, cfg); ch.draw();
  const out = { data: c.toDataURL('image/png'), w: w * 2, h: h * 2 };
  ch.destroy(); holder.remove(); return out;
}
let chLive = null, chSpec = null;
function tablesAsText() {
  return $$('figure.tbl', editor).map((f, i) => { const t = f.querySelector('table'); const cap = f.querySelector('figcaption'); return { label: `Table ${i + 1}${cap && cap.textContent.trim() ? ': ' + cap.textContent.trim().slice(0, 50) : ''}`, text: t ? [...t.rows].map(r => [...r.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim()).join('\t')).join('\n') : '' }; });
}
function openChart(spec) {
  chSpec = spec || { type: 'chart', kind: 'bar', data: '', ylabel: '', fmt: 'n', aspect: 'wide', caption: '', source: '' };
  const tbls = tablesAsText();
  $('#chFromTable').innerHTML = '<option value="">Paste or type data below</option>' + tbls.map((t, i) => `<option value="${i}">Use ${esc(t.label)}</option>`).join('');
  $('#chFromTable').disabled = !tbls.length; $('#chFromTable')._t = tbls;
  $('#chData').value = chSpec.data; $('#chEvents').value = chSpec.events || ''; $('#chType').value = chSpec.kind; $('#chYLabel').value = chSpec.ylabel; $('#chFmt').value = chSpec.fmt; $('#chAspect').value = chSpec.aspect; $('#chCaption').value = chSpec.caption; $('#chSource').value = chSpec.source;
  $('#chOk').textContent = specTarget ? 'Update chart' : 'Insert chart';
  $('#chDlg').showModal(); chartPreview();
}
function chartSpecFromForm() { return Object.assign({}, chSpec, { data: $('#chData').value, events: $('#chEvents').value, kind: $('#chType').value, ylabel: $('#chYLabel').value.trim(), fmt: $('#chFmt').value, aspect: $('#chAspect').value, caption: $('#chCaption').value.trim(), source: $('#chSource').value.trim() }); }
const chartPreview = debounce(() => {
  const spec = chartSpecFromForm(), data = parseTable(spec.data);
  if (chLive) { chLive.destroy(); chLive = null; }
  const err = !data ? 'Paste or type a table: the first row names the series, the first column labels the categories.' : !data.series.length ? 'Add at least one column of numbers after the label column.' : !data.series.some(s => s.values.some(v => v != null)) ? 'No numbers found in the data yet.' : '';
  $('#chErr').textContent = err;
  const note = data && data.series.length > 8 ? `Only the first 8 series are drawn. Past that, colors can’t be told apart reliably. Combine the rest into an “Other” column or make a second chart.` : data && spec.kind === 'stack' && data.series.some(s => s.values.some(v => v < 0)) ? 'Stacked columns don’t work with negative numbers; try columns or a line.' : '';
  $('#chNote').textContent = note;
  const [w, h] = CH_SIZE[spec.aspect] || CH_SIZE.wide, c = $('#chCanvas');
  const box = $('#chStage').clientWidth || 560, scale = Math.min(1, box / w);
  c.width = w; c.height = h; c.style.width = (w * scale) + 'px'; c.style.height = (h * scale) + 'px';
  if (err) { c.getContext('2d').clearRect(0, 0, w, h); return; }
  if (spec.kind === 'multi') { if (data.series.length < 2) $('#chNote').textContent = 'Small multiples need two or more series: one small chart per series, all on the same scale.'; if (data.series.length > 9) $('#chNote').textContent = 'Only the first 9 series are drawn as small multiples.'; multiplesPNG(spec, data, 1).then(r => { const im = new Image(); im.onload = () => { const g = c.getContext('2d'); g.clearRect(0, 0, w, h); g.drawImage(im, 0, 0, w, h); }; im.src = r.data; }); return; }
  const cfg = chartConfig(spec, data); cfg.options.devicePixelRatio = 1;
  chLive = new Chart(c, cfg);
}, 150);
['#chData', '#chEvents', '#chYLabel', '#chCaption', '#chSource'].forEach(s => $(s).addEventListener('input', chartPreview));
['#chType', '#chFmt', '#chAspect'].forEach(s => $(s).addEventListener('change', chartPreview));
$('#chFromTable').addEventListener('change', e => { const t = (e.target._t || [])[+e.target.value]; if (t) { $('#chData').value = t.text; chartPreview(); } });
$('#chCancel').addEventListener('click', () => { $('#chDlg').close(); specTarget = null; });
$('#chOk').addEventListener('click', async () => {
  const spec = chartSpecFromForm(), data = parseTable(spec.data);
  if (!data || !data.series.some(s => s.values.some(v => v != null))) { $('#chErr').textContent = 'There’s nothing to chart yet.'; return; }
  const old = chSpec; $('#chDlg').close();
  try { await placeSpecFigure(spec, old); } catch (e) { toast(e.message); }
});

/* ---------------- maps ---------------- */
let WORLD = null, PLACES = null;
function geo() {
  useLib('lib-geo');
  if (!WORLD) { const w = JSON.parse($('#data-world').textContent); const fc = topojson.feature(w, w.objects.countries); WORLD = { topo: w, fc, borders: topojson.mesh(w, w.objects.countries, (a, b) => a !== b), coast: topojson.mesh(w, w.objects.countries, (a, b) => a === b), byName: Object.fromEntries(fc.features.map(f => [f.properties.name, f])) }; }
  return WORLD;
}
function places() {
  if (!PLACES) PLACES = $('#data-places').textContent.split('\n').map(l => { const [name, alt, adm1, country, lat, lon, pop, cap] = l.split('|'); return { name, alt, adm1, country, lat: +lat, lon: +lon, pop: +pop, cap: cap === '1' }; });
  return PLACES;
}
const MAP_KEYS = () => [{ id: 'a', label: '', color: SERIES[0] }, { id: 'b', label: '', color: SERIES[1] }, { id: 'c', label: '', color: SERIES[2] }, { id: 'n', label: '', color: '#8a8f98' }, { id: 'h', label: 'Contested or occupied', color: '#c0392b', hatch: true }];
const MAP_PRESETS = { world: ['World', [10, 12], 160], europe: ['Europe', [15, 52], 950], east: ['Eastern Europe & Black Sea', [33, 48], 1500], ukraine: ['Ukraine', [31.5, 48.6], 2700], mideast: ['Middle East', [44, 29], 1100], asia: ['East Asia & Western Pacific', [125, 28], 650], taiwan: ['Taiwan Strait', [120.5, 24.3], 4200], south: ['South Asia', [78, 23], 1000], africa: ['Africa', [18, 3], 430], na: ['North America', [-100, 44], 500], la: ['Latin America', [-68, -14], 430], arctic: ['Arctic', [10, 78], 700] };
function blankMap() { return { type: 'map', w: 960, h: 600, view: { center: [33, 48], scale: 1500 }, keys: MAP_KEYS(), countries: {}, markers: [], routes: [], areas: [], countryLabels: true, graticule: false, caption: '', source: '' }; }
function mapProj(spec) {
  const g = geo(), { w, h } = spec, [lon, lat] = spec.view.center, s = spec.view.scale;
  const p = s < 330 ? d3.geoNaturalEarth1().rotate([-lon, 0]).center([0, lat]) : d3.geoAzimuthalEqualArea().rotate([-lon, -lat]).clipAngle(90);
  return p.scale(s).translate([w / 2, h / 2]).precision(0.3);
}
const tint = (hex, t) => { const n = parseInt(hex.slice(1), 16), r = n >> 16, gg = (n >> 8) & 255, b = n & 255, m = v => Math.round(v + (255 - v) * t); return `rgb(${m(r)},${m(gg)},${m(b)})`; };
const keyOf = (spec, id) => spec.keys.find(k => k.id === id) || spec.keys[0];
function symbolPath(sym, x, y, r = 6) {
  if (sym === 'star') { let d = ''; for (let i = 0; i < 10; i++) { const a = Math.PI / 5 * i - Math.PI / 2, rr = i % 2 ? r * .45 : r * 1.15; d += (i ? 'L' : 'M') + (x + rr * Math.cos(a)).toFixed(1) + ' ' + (y + rr * Math.sin(a)).toFixed(1); } return d + 'Z'; }
  if (sym === 'square') return `M${x - r * .8} ${y - r * .8}h${r * 1.6}v${r * 1.6}h${-r * 1.6}Z`;
  if (sym === 'triangle') return `M${x} ${y - r}L${x + r} ${y + r * .8}H${x - r}Z`;
  if (sym === 'cross') return `M${x - r * .7} ${y - r * .7}L${x + r * .7} ${y + r * .7}M${x + r * .7} ${y - r * .7}L${x - r * .7} ${y + r * .7}`;
  return `M${x - r * .7} ${y}a${r * .7} ${r * .7} 0 1 0 ${r * 1.4} 0a${r * .7} ${r * .7} 0 1 0 ${-r * 1.4} 0`;
}
function mapSVG(spec, opt = {}) {
  const g = geo(), proj = mapProj(spec), path = d3.geoPath(proj), { w, h } = spec;
  const used = new Set();
  const halo = t => `<text>${t}</text>`;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${VIZ.mapFont}">`;
  s += `<defs><clipPath id="mc"><rect width="${w}" height="${h}"/></clipPath>${spec.keys.map(k => `<pattern id="hp-${k.id}" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" fill="${tint(k.color, .82)}"/><line x1="0" y1="0" x2="0" y2="7" stroke="${k.color}" stroke-width="2"/></pattern>`).join('')}<marker id="ah" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker>${spec.keys.map(k => `<marker id="ah-${k.id}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${k.color}"/></marker>`).join('')}</defs>`;
  s += `<g clip-path="url(#mc)"><rect width="${w}" height="${h}" fill="#dde7ee"/>`;
  s += `<path d="${path({ type: 'Sphere' }) || ''}" fill="#dde7ee"/>`;
  if (spec.graticule) s += `<path d="${path(d3.geoGraticule10())}" fill="none" stroke="#c8d5de" stroke-width=".6"/>`;
  s += `<g>${g.fc.features.map(f => { const k = spec.countries[f.properties.name]; let fill = '#f3f1ea'; if (k) { const kk = keyOf(spec, k); used.add(kk.id); fill = kk.hatch ? `url(#hp-${kk.id})` : tint(kk.color, .45); } const d = path(f); return d ? `<path d="${d}" fill="${fill}" data-c="${esc(f.properties.name)}"/>` : ''; }).join('')}</g>`;
  s += mapLayersSVG(spec, proj, path, used, keyOf, tint);
  s += `<path d="${path(g.borders) || ''}" fill="none" stroke="#a8a497" stroke-width=".7" stroke-linejoin="round"/>`;
  s += `<path d="${path(g.coast) || ''}" fill="none" stroke="#8c9aa5" stroke-width=".6"/>`;
  (spec.areas || []).forEach(a => { if (a.pts.length < 3) return; const k = keyOf(spec, a.key); used.add(k.id); const ring = [...a.pts, a.pts[0]]; const poly = { type: 'Polygon', coordinates: [d3.geoArea({ type: 'Polygon', coordinates: [ring] }) > 2 * Math.PI ? ring.slice().reverse() : ring] }; s += `<path d="${path(poly) || ''}" fill="${k.hatch ? `url(#hp-${k.id})` : tint(k.color, .45)}" fill-opacity="${k.hatch ? 1 : .75}" stroke="${k.color}" stroke-width="1.4" stroke-dasharray="5 3" data-item="${a.id}"/>`; });
  s += riverLabelsSVG(spec, proj);
  if (spec.countryLabels) {
    const labels = []; g.fc.features.forEach(f => { const b = path.bounds(f); const aw = b[1][0] - b[0][0], ah = b[1][1] - b[0][1]; if (!isFinite(aw) || aw < 46 || ah < 18) return; const c = path.centroid(f); if (!c || isNaN(c[0]) || c[0] < 10 || c[0] > w - 10 || c[1] < 10 || c[1] > h - 10) return; labels.push({ x: c[0], y: c[1], t: f.properties.name, a: aw * ah }); });
    labels.sort((a, b) => b.a - a.a).slice(0, 40).forEach(l => { s += `<text x="${l.x.toFixed(1)}" y="${l.y.toFixed(1)}" text-anchor="middle" font-size="${l.a > 40000 ? 13 : 11}" fill="#6b6a60" letter-spacing=".4" paint-order="stroke" stroke="#f3f1ea" stroke-width="3" stroke-linejoin="round">${esc(l.t)}</text>`; });
  }
  (spec.routes || []).forEach(r => {
    if (r.pts.length < 2) return; const k = keyOf(spec, r.key); used.add(k.id);
    const d = path({ type: 'LineString', coordinates: r.pts }); if (!d) return;
    s += `<path d="${d}" fill="none" stroke="#fff" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round" opacity=".85"/><path d="${d}" fill="none" stroke="${k.color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" ${r.dash ? 'stroke-dasharray="7 5"' : ''} ${r.arrow !== false ? `marker-end="url(#ah-${k.id})"` : ''} data-item="${r.id}"/>`;
    if (r.label) { const mid = proj(d3.geoInterpolate(r.pts[Math.floor((r.pts.length - 1) / 2)], r.pts[Math.ceil((r.pts.length - 1) / 2)])(.5)); if (mid) s += `<text x="${mid[0].toFixed(1)}" y="${(mid[1] - 9).toFixed(1)}" text-anchor="middle" font-size="12.5" font-style="italic" fill="${VIZ.ink}" paint-order="stroke" stroke="#fff" stroke-width="3.5" stroke-linejoin="round">${esc(r.label)}</text>`; }
  });
  (spec.markers || []).forEach(m => {
    const p = proj([m.lon, m.lat]); if (!p || p[0] < -20 || p[0] > w + 20 || p[1] < -20 || p[1] > h + 20) return;
    const k = m.key ? keyOf(spec, m.key) : null; if (k) used.add(k.id);
    const col = k ? k.color : VIZ.ink, [x, y] = p;
    s += m.sym === 'cross' ? `<path d="${symbolPath('cross', x, y, 7)}" stroke="#fff" stroke-width="5" stroke-linecap="round"/><path d="${symbolPath('cross', x, y, 7)}" stroke="${col}" stroke-width="2.6" stroke-linecap="round" data-item="${m.id}"/>`
      : `<path d="${symbolPath(m.sym, x, y, m.sym === 'star' ? 7.5 : 6.5)}" fill="${col}" stroke="#fff" stroke-width="2" data-item="${m.id}"/>`;
    if (m.label) { const pos = m.pos || 'r', dx = pos === 'r' ? 10 : pos === 'l' ? -10 : 0, dy = pos === 't' ? -11 : pos === 'b' ? 17 : 4.5, anc = pos === 'r' ? 'start' : pos === 'l' ? 'end' : 'middle';
      s += `<text x="${(x + dx).toFixed(1)}" y="${(y + dy).toFixed(1)}" text-anchor="${anc}" font-size="${m.sym === 'star' ? 13.5 : 12.5}" font-weight="${m.sym === 'star' ? 700 : 400}" fill="${VIZ.ink}" paint-order="stroke" stroke="#fff" stroke-width="3.5" stroke-linejoin="round">${esc(m.label)}</text>`; }
  });
  s += '</g>';
  const leg = spec.keys.filter(k => used.has(k.id) && k.label.trim());
  if (leg.length) {
    const lh = 20, bw = Math.min(330, 34 + Math.max(...leg.map(k => k.label.length)) * 7.2), bh = 12 + leg.length * lh;
    s += `<g transform="translate(12 ${h - bh - 12})"><rect width="${bw}" height="${bh}" rx="4" fill="#fff" fill-opacity=".92" stroke="#c9c6bb"/>${leg.map((k, i) => `<rect x="10" y="${9 + i * lh}" width="16" height="12" rx="2" fill="${k.hatch ? `url(#hp-${k.id})` : tint(k.color, .45)}" stroke="${k.color}" stroke-width="1"/><text x="34" y="${19.5 + i * lh}" font-size="12.5" fill="${VIZ.ink}">${esc(k.label)}</text>`).join('')}</g>`;
  }
  s += scaleBarSVG(spec, proj) + locatorSVG(spec, proj);
  s += `<text x="${w - 8}" y="${h - 7}" text-anchor="end" font-size="9.5" fill="#6f7a84">Map data: Natural Earth</text>`;
  s += `<rect width="${w}" height="${h}" fill="none" stroke="#b9c3ca"/></svg>`;
  return { svg: s, w, h, proj };
}
/* map editor */
let MP = null, mpMode = 'pan', mpKey = 'a', mpDraft = null, mpSel = null, mpDrag = null;
function openMap(spec) {
  try { geo(); } catch (e) { toast('The map couldn’t load: ' + e.message); return; }
  MP = spec || blankMap(); MP.keys = MP.keys && MP.keys.length ? MP.keys : MAP_KEYS(); mpOld = spec ? JSON.parse(JSON.stringify(spec)) : null;
  mpMode = 'pan'; mpDraft = null; mpSel = null;
  $('#mpPreset').innerHTML = '<option value="">Jump to a region…</option>' + Object.entries(MAP_PRESETS).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join('');
  $('#mpCaption').value = MP.caption || ''; $('#mpSource').value = MP.source || ''; $('#mpLabels').checked = !!MP.countryLabels; $('#mpGrat').checked = !!MP.graticule; MP.regions = MP.regions || {}; $('#mpProv').checked = !!MP.provinces; $('#mpRivers').checked = !!MP.rivers; $('#mpRiverNames').checked = !!MP.riverNames; $('#mpScale').checked = MP.scaleBar !== false; $('#mpLocator').checked = MP.locator !== false;
  $('#mpOk').textContent = specTarget ? 'Update map' : 'Insert map';
  $('#mpDlg').showModal(); mpRender(); mpPanel(); mpTools();
}
let mpOld = null;
function mpTools() { $$('#mpTools [data-m]').forEach(b => b.classList.toggle('on', b.dataset.m === mpMode)); $('#mpHint').textContent = { pan: 'Drag to move the map; scroll or use + / − to zoom. Click a marker, route or area to edit it.', shade: MP.provinces ? 'Click a province or region to shade it (countries outside province coverage shade whole). Click again to clear.' : 'Click countries to shade them with the chosen key. Click again to clear.', marker: 'Click the map to place a marker, or search for a place above.', route: 'Click points along the route; double-click (or Finish) to end it. Esc cancels.', area: 'Click around the area; double-click (or Finish) to close it. Esc cancels.' }[mpMode]; $('#mpFinish').classList.toggle('hidden', !mpDraft); $('#mpKeys').innerHTML = MP.keys.map(k => `<button class="mp-key ${k.id === mpKey ? 'on' : ''}" data-k="${k.id}" title="${esc(k.label || 'Key')}"><i style="background:${k.hatch ? `repeating-linear-gradient(45deg,${k.color} 0 2px,${tint(k.color, .82)} 2px 5px)` : tint(k.color, .45)};border-color:${k.color}"></i>${esc(k.label || { a: 'Blue', b: 'Orange', c: 'Green', n: 'Grey', h: 'Hatched' }[k.id] || 'Key')}</button>`).join(''); }
function mpRender() {
  const st = $('#mpStage'); const draft = mpDraft && mpDraft.pts.length ? Object.assign({}, MP, mpDraft.kind === 'route' ? { routes: [...MP.routes, { id: '_d', pts: mpDraft.pts, key: mpKey, arrow: false }] } : { areas: [...MP.areas, { id: '_d', pts: mpDraft.pts, key: mpKey }] }) : MP;
  const r = mapSVG(draft); st.innerHTML = r.svg; mpProj = r.proj;
  const svg = st.querySelector('svg'); svg.style.width = '100%'; svg.style.height = 'auto'; svg.removeAttribute('width'); svg.removeAttribute('height');
  if (mpSel) $$(`[data-item="${mpSel}"]`, st).forEach(el => el.classList.add('mp-sel'));
  if (mpDraft) mpDraft.pts.forEach(p => { const q = mpProj(p); if (q) svg.insertAdjacentHTML('beforeend', `<circle cx="${q[0]}" cy="${q[1]}" r="4" fill="#fff" stroke="#1d2733" stroke-width="1.5"/>`); });
}
let mpProj = null;
const mpPt = e => { const svg = $('#mpStage svg'), r = svg.getBoundingClientRect(); return [(e.clientX - r.left) * MP.w / r.width, (e.clientY - r.top) * MP.h / r.height]; };
function mpCountryAt(ll) { const g = geo(); return g.fc.features.find(f => d3.geoContains(f, ll)); }
$('#mpStage').addEventListener('pointerdown', e => {
  if (!MP || e.button !== 0) return; const pt = mpPt(e), ll = mpProj.invert(pt);
  const item = e.target.closest('[data-item]')?.dataset.item;
  if (mpMode === 'pan') {
    if (item && item !== '_d') { mpSel = item; mpPanel(); mpRender(); const m = MP.markers.find(x => x.id === item); if (m) { mpDrag = { kind: 'marker', m }; $('#mpStage').setPointerCapture(e.pointerId); } return; }
    mpDrag = { kind: 'pan', x: e.clientX, y: e.clientY, start: pt, c0: MP.view.center.slice() }; $('#mpStage').setPointerCapture(e.pointerId); return;
  }
  if (!ll || isNaN(ll[0])) return;
  if (mpMode === 'shade' && MP.provinces) { const G = geo2(), pf = G.prov.features.find(f => d3.geoContains(f, ll)); if (pf) { const k = pf.properties.c + '|' + pf.properties.n; MP.regions = MP.regions || {}; if (MP.regions[k] === mpKey) delete MP.regions[k]; else MP.regions[k] = mpKey; mpRender(); mpPanel(); return; } }
  if (mpMode === 'shade') { const f = mpCountryAt(ll); if (!f) return; const n = f.properties.name; if (MP.countries[n] === mpKey) delete MP.countries[n]; else MP.countries[n] = mpKey; mpRender(); mpPanel(); return; }
  if (mpMode === 'marker') { ask('Marker label', 'Name for this point (leave blank for none).', 'Add marker', '').then(t => { if (t === null) return; const m = { id: uid('m'), lon: +ll[0].toFixed(3), lat: +ll[1].toFixed(3), label: t.trim(), sym: 'dot', key: '', pos: 'r' }; MP.markers.push(m); mpSel = m.id; mpRender(); mpPanel(); $('#mpDlg').open || $('#mpDlg').showModal(); }); return; }
  if (mpMode === 'route' || mpMode === 'area') { if (!mpDraft) mpDraft = { kind: mpMode, pts: [] }; mpDraft.pts.push([+ll[0].toFixed(3), +ll[1].toFixed(3)]); mpRender(); mpTools(); }
});
$('#mpStage').addEventListener('pointermove', e => {
  if (!mpDrag) return;
  if (mpDrag.kind === 'marker') { const ll = mpProj.invert(mpPt(e)); if (ll) { mpDrag.m.lon = +ll[0].toFixed(3); mpDrag.m.lat = +ll[1].toFixed(3); mpDrag.moved = true; mpRenderSoon(); } return; }
  const svg = $('#mpStage svg'), r = svg.getBoundingClientRect(); svg.style.transform = `translate(${e.clientX - mpDrag.x}px,${e.clientY - mpDrag.y}px)`; mpDrag.dx = (e.clientX - mpDrag.x) * MP.w / r.width; mpDrag.dy = (e.clientY - mpDrag.y) * MP.h / r.height;
});
$('#mpStage').addEventListener('pointerup', () => {
  if (!mpDrag) return; const d = mpDrag; mpDrag = null;
  if (d.kind === 'marker') { mpRender(); mpPanel(); return; }
  if (d.dx || d.dy) { const ll = mpProj.invert([MP.w / 2 - d.dx, MP.h / 2 - d.dy]); if (ll && !isNaN(ll[0])) MP.view.center = [+ll[0].toFixed(3), +Math.max(-85, Math.min(85, ll[1])).toFixed(3)]; }
  mpRender();
});
const mpRenderSoon = debounce(mpRender, 30);
$('#mpStage').addEventListener('dblclick', e => { if (mpDraft) { e.preventDefault(); mpFinish(); } });
$('#mpStage').addEventListener('wheel', e => { if (!MP) return; e.preventDefault(); mpZoom(e.deltaY < 0 ? 1.18 : 1 / 1.18); }, { passive: false });
function mpZoom(f) { MP.view.scale = Math.max(120, Math.min(40000, Math.round(MP.view.scale * f))); mpRenderSoon(); }
function mpFinish() {
  if (!mpDraft) return; const d = mpDraft; mpDraft = null;
  if (d.kind === 'route' && d.pts.length >= 2) { const r = { id: uid('r'), pts: d.pts, key: mpKey, dash: false, arrow: true, label: '' }; MP.routes.push(r); mpSel = r.id; }
  if (d.kind === 'area' && d.pts.length >= 3) { const a = { id: uid('a'), pts: d.pts, key: mpKey, label: '' }; MP.areas.push(a); mpSel = a.id; }
  mpRender(); mpPanel(); mpTools();
}
$('#mpFinish').addEventListener('click', mpFinish);
$('#mpDlg').addEventListener('keydown', e => { if (e.target.matches('input,textarea,select')) return; if (e.key === 'Escape' && mpDraft) { e.preventDefault(); mpDraft = null; mpRender(); mpTools(); } if (e.key === 'Enter' && mpDraft) { e.preventDefault(); mpFinish(); } if ((e.key === 'Delete' || e.key === 'Backspace') && mpSel) { e.preventDefault(); mpDelete(mpSel); } });
$('#mpTools').addEventListener('click', e => { const b = e.target.closest('[data-m]'); if (!b) return; if (mpDraft) mpFinish(); mpMode = b.dataset.m; mpTools(); });
$('#mpKeys').addEventListener('click', e => { const b = e.target.closest('[data-k]'); if (!b) return; mpKey = b.dataset.k; mpTools(); if (mpSel) { const it = [...MP.markers, ...MP.routes, ...MP.areas].find(x => x.id === mpSel); if (it) { it.key = mpKey; mpRender(); mpPanel(); } } });
$('#mpZoomIn').addEventListener('click', () => mpZoom(1.4)); $('#mpZoomOut').addEventListener('click', () => mpZoom(1 / 1.4));
$('#mpPreset').addEventListener('change', e => { const p = MAP_PRESETS[e.target.value]; if (p) { MP.view = { center: p[1].slice(), scale: p[2] }; mpRender(); } e.target.value = ''; });
$('#mpFit').addEventListener('click', () => mpFitAll());
function mpFitAll() {
  const feats = [...Object.keys(MP.countries).map(n => geo().byName[n]).filter(Boolean), ...MP.markers.map(m => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [m.lon, m.lat] } })), ...MP.routes.map(r => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: r.pts } })), ...MP.areas.map(a => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...a.pts, a.pts[0]] } }))];
  if (!feats.length) { toast('Add something to the map first.'); return; }
  const fc = { type: 'FeatureCollection', features: feats };
  const c = d3.geoCentroid(fc); const p = d3.geoAzimuthalEqualArea().rotate([-c[0], -c[1]]).clipAngle(90).fitExtent([[60, 50], [MP.w - 60, MP.h - 50]], fc);
  let s = p.scale(); if (feats.length === 1 && feats[0].geometry.type === 'Point') s = 2600;
  MP.view = { center: [+c[0].toFixed(3), +c[1].toFixed(3)], scale: Math.round(Math.max(130, Math.min(30000, s))) }; mpRender();
}
['#mpLabels', '#mpGrat', '#mpProv', '#mpRivers', '#mpRiverNames', '#mpScale', '#mpLocator'].forEach(s => $(s).addEventListener('change', () => { MP.countryLabels = $('#mpLabels').checked; MP.graticule = $('#mpGrat').checked; MP.provinces = $('#mpProv').checked; MP.rivers = $('#mpRivers').checked; MP.riverNames = $('#mpRiverNames').checked; MP.scaleBar = $('#mpScale').checked; MP.locator = $('#mpLocator').checked; if (MP.provinces || MP.rivers) { try { geo2(); } catch (e) { toast('Map layers couldn’t load: ' + e.message); } } mpRender(); mpTools(); }));
/* place search */
$('#mpSearch').addEventListener('input', debounce(() => {
  const q = $('#mpSearch').value.trim().toLowerCase(); const box = $('#mpResults');
  if (q.length < 2) { box.innerHTML = ''; box.classList.add('hidden'); return; }
  const own = (P.places || []).filter(p => p.name.toLowerCase().includes(q)).map(p => Object.assign({ own: true }, p));
  const hits = [...own, ...places().filter(p => p.name.toLowerCase().startsWith(q) || (p.alt && p.alt.toLowerCase().startsWith(q)))].slice(0, 8);
  const cMatch = Object.keys(geo().byName).filter(n => n.toLowerCase().startsWith(q)).slice(0, 3);
  let rMatch = []; try { rMatch = Object.keys(geo2().byKey).filter(k => k.split('|')[1].toLowerCase().startsWith(q)).slice(0, 3); } catch (e) { }
  box.innerHTML = cMatch.map(n => `<button data-country="${esc(n)}"><b>${esc(n)}</b><span>country: shade it</span></button>`).join('') + rMatch.map(k => `<button data-region="${esc(k)}"><b>${esc(k.split('|')[1])}</b><span>province or region, ${esc(k.split('|')[0])}: shade it</span></button>`).join('') + hits.map((p, i) => `<button data-place="${i}"><b>${esc(p.name)}</b><span>${esc([p.adm1, p.country].filter(Boolean).join(', '))}${p.own ? ' · your place' : ''}</span></button>`).join('') + (hits.length || cMatch.length || rMatch.length ? '' : `<div class="mp-none">Not in the built-in list. Click the map to place it, then save it as one of your places.</div>`);
  box._hits = hits; box.classList.remove('hidden');
}, 120));
$('#mpResults').addEventListener('click', e => {
  const box = $('#mpResults');
  const rq = e.target.closest('[data-region]'); if (rq) { MP.regions = MP.regions || {}; MP.regions[rq.dataset.region] = mpKey; MP.provinces = true; $('#mpProv').checked = true; box.classList.add('hidden'); $('#mpSearch').value = ''; mpRender(); mpPanel(); return; }
  const c = e.target.closest('[data-country]'); if (c) { MP.countries[c.dataset.country] = mpKey; box.classList.add('hidden'); $('#mpSearch').value = ''; mpRender(); mpPanel(); return; }
  const b = e.target.closest('[data-place]'); if (!b) return; const p = box._hits[+b.dataset.place];
  const m = { id: uid('m'), lon: p.lon, lat: p.lat, label: p.name, sym: p.cap ? 'star' : 'dot', key: '', pos: 'r' }; MP.markers.push(m); mpSel = m.id;
  const q = mpProj([p.lon, p.lat]); if (!q || q[0] < 0 || q[0] > MP.w || q[1] < 0 || q[1] > MP.h) MP.view.center = [p.lon, p.lat];
  box.classList.add('hidden'); $('#mpSearch').value = ''; mpRender(); mpPanel();
});
/* the layer list */
function mpPanel() {
  const K = k => MP.keys.find(x => x.id === k);
  const keyOpts = (sel, none) => (none ? `<option value="" ${!sel ? 'selected' : ''}>Black</option>` : '') + MP.keys.map(k => `<option value="${k.id}" ${k.id === sel ? 'selected' : ''}>${esc(k.label || { a: 'Blue', b: 'Orange', c: 'Green', n: 'Grey', h: 'Hatched' }[k.id])}</option>`).join('');
  const shaded = Object.entries(MP.countries), regs = Object.entries(MP.regions || {});
  $('#mpLegend').innerHTML = MP.keys.map(k => `<div class="mp-lk"><i style="background:${k.hatch ? `repeating-linear-gradient(45deg,${k.color} 0 2px,${tint(k.color, .82)} 2px 5px)` : tint(k.color, .45)};border-color:${k.color}"></i><input data-key="${k.id}" value="${esc(k.label)}" placeholder="${k.hatch ? 'e.g. Occupied since 2022' : 'Legend label, e.g. NATO members'}"></div>`).join('');
  $('#mpItems').innerHTML = (shaded.length ? `<div class="mp-grp">Shaded countries</div>` + shaded.map(([n, k]) => `<div class="mp-it"><span>${esc(n)}</span><select data-cty="${esc(n)}">${keyOpts(k)}</select><button class="ghost small" data-delc="${esc(n)}" title="Clear">✕</button></div>`).join('') : '') +
    (regs.length ? `<div class="mp-grp">Shaded regions</div>` + regs.map(([n, k]) => `<div class="mp-it"><span>${esc(n.split('|')[1])} <span class="muted small">${esc(n.split('|')[0])}</span></span><select data-reg="${esc(n)}">${keyOpts(k)}</select><button class="ghost small" data-delr="${esc(n)}" title="Clear">✕</button></div>`).join('') : '') +
    (MP.markers.length ? `<div class="mp-grp">Markers</div>` + MP.markers.map(m => `<div class="mp-it ${m.id === mpSel ? 'sel' : ''}" data-id="${m.id}"><input data-f="label" value="${esc(m.label)}" placeholder="Label"><select data-f="sym">${['dot', 'star', 'square', 'triangle', 'cross'].map(s => `<option ${s === m.sym ? 'selected' : ''}>${s}</option>`).join('')}</select><select data-f="key">${keyOpts(m.key, true)}</select><select data-f="pos" title="Label position">${[['r', 'Right'], ['l', 'Left'], ['t', 'Above'], ['b', 'Below']].map(([v, l]) => `<option value="${v}" ${v === (m.pos || 'r') ? 'selected' : ''}>${l}</option>`).join('')}</select><button class="ghost small" data-save="${m.id}" title="Save as one of your places">☆</button><button class="ghost small" data-del="${m.id}" title="Delete">✕</button></div>`).join('') : '') +
    (MP.routes.length ? `<div class="mp-grp">Routes and arrows</div>` + MP.routes.map(r => `<div class="mp-it ${r.id === mpSel ? 'sel' : ''}" data-id="${r.id}"><input data-f="label" value="${esc(r.label)}" placeholder="Label (optional)"><select data-f="key">${keyOpts(r.key)}</select><label class="mp-chk"><input type="checkbox" data-f="arrow" ${r.arrow !== false ? 'checked' : ''}> arrow</label><label class="mp-chk"><input type="checkbox" data-f="dash" ${r.dash ? 'checked' : ''}> dashed</label><button class="ghost small" data-del="${r.id}" title="Delete">✕</button></div>`).join('') : '') +
    (MP.areas.length ? `<div class="mp-grp">Areas</div>` + MP.areas.map(a => `<div class="mp-it ${a.id === mpSel ? 'sel' : ''}" data-id="${a.id}"><span>${a.pts.length} points</span><select data-f="key">${keyOpts(a.key)}</select><button class="ghost small" data-del="${a.id}" title="Delete">✕</button></div>`).join('') : '') ||
    '<div class="mp-none">Nothing on the map yet. Pick a tool above.</div>';
}
function mpDelete(id) { MP.markers = MP.markers.filter(x => x.id !== id); MP.routes = MP.routes.filter(x => x.id !== id); MP.areas = MP.areas.filter(x => x.id !== id); if (mpSel === id) mpSel = null; mpRender(); mpPanel(); }
$('#mpSide').addEventListener('input', e => {
  const t = e.target;
  if (t.dataset.key) { const k = MP.keys.find(x => x.id === t.dataset.key); k.label = t.value; mpRenderSoon(); mpTools(); return; }
  const row = t.closest('[data-id]'); if (!row || !t.dataset.f) return;
  const it = [...MP.markers, ...MP.routes, ...MP.areas].find(x => x.id === row.dataset.id); if (!it) return;
  it[t.dataset.f] = t.type === 'checkbox' ? t.checked : t.value; mpRenderSoon();
});
$('#mpSide').addEventListener('change', e => { const t = e.target; if (t.dataset.cty) { MP.countries[t.dataset.cty] = t.value; mpRender(); } if (t.dataset.reg) { MP.regions[t.dataset.reg] = t.value; mpRender(); } });
$('#mpSide').addEventListener('click', e => {
  const d = e.target.closest('[data-del]'); if (d) { mpDelete(d.dataset.del); return; }
  const c = e.target.closest('[data-delc]'); if (c) { delete MP.countries[c.dataset.delc]; mpRender(); mpPanel(); return; }
  const rg = e.target.closest('[data-delr]'); if (rg) { delete MP.regions[rg.dataset.delr]; mpRender(); mpPanel(); return; }
  const sv = e.target.closest('[data-save]'); if (sv) { const m = MP.markers.find(x => x.id === sv.dataset.save); if (m && m.label) { P.places = P.places || []; if (!P.places.some(p => p.name === m.label)) { P.places.push({ name: m.label, lat: m.lat, lon: m.lon, adm1: '', country: '' }); markDirty(); } toast(`“${m.label}” saved to your places. It now shows up in map search.`); } else toast('Give the marker a label first.'); return; }
  const row = e.target.closest('.mp-it[data-id]'); if (row && !e.target.closest('input,select,button,label')) { mpSel = row.dataset.id; mpRender(); mpPanel(); }
});
$('#mpCancel').addEventListener('click', () => { $('#mpDlg').close(); specTarget = null; MP = null; });
$('#mpOk').addEventListener('click', async () => {
  if (mpDraft) mpFinish();
  MP.caption = $('#mpCaption').value.trim(); MP.source = $('#mpSource').value.trim();
  const spec = MP; $('#mpDlg').close(); MP = null;
  try { await placeSpecFigure(spec, mpOld); } catch (e) { toast('The map couldn’t be drawn: ' + e.message); }
});

/* ---------------- timeline figures ---------------- */
function dateRangeKeys(s) {
  s = String(s || '').trim(); if (!s) return null;
  const parts = s.split(/\s*(?:–|—|\bto\b|(?<=\d)\s*-\s*(?=[A-Za-z]*\s*\d))\s*/);
  const a = dateKey(parts[0]); if (a === null) return null;
  let b = parts[1] ? dateKey(/\d{3,4}/.test(parts[1]) ? parts[1] : parts[1] + ' ' + Math.trunc(Math.abs(a) / 10000)) : null;
  if (b !== null && /\b(BCE?|B\.C\.)\b/i.test(s) && b > 0) b = -b;
  return [a, b !== null && b > a ? b : null];
}
const keyYear = k => { const y = Math.trunc(k / 10000), m = Math.trunc(Math.abs(k) % 10000 / 100), d = Math.abs(k) % 100; return y + (m ? (m - 1) / 12 : 0) + (d ? (d - 1) / 372 : 0); };
function yearLabel(y) { const yy = Math.floor(y); return yy < 0 ? -yy + ' BCE' : String(yy); }
function timelineSVG(spec) {
  const ev = spec.events.filter(e => e.on !== false).map(e => { const r = dateRangeKeys(e.date); return r ? Object.assign({}, e, { a: keyYear(r[0]), b: r[1] !== null ? keyYear(r[1]) : null }) : null; }).filter(Boolean).sort((x, y) => x.a - y.a);
  const w = spec.w || 960, pad = 50;
  if (!ev.length) return { svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="120"><text x="20" y="60" font-family="Arial" font-size="14">No dated events selected.</text></svg>`, w, h: 120 };
  let lo = Math.min(...ev.map(e => e.a)), hi = Math.max(...ev.map(e => e.b ?? e.a)); if (hi - lo < 0.08) { lo -= .05; hi += .05; }
  const span = hi - lo; lo -= span * .03; hi += span * .03;
  const X = y => pad + (y - lo) / (hi - lo) * (w - 2 * pad);
  // stagger labels into levels above and below the axis so none overlap
  const lvl = [], words = s => s.split(/\s+/), wrap = (t, n = 24) => { const out = []; let cur = ''; words(t).forEach(wd => { if ((cur + ' ' + wd).trim().length > n && cur) { out.push(cur); cur = wd; } else cur = (cur + ' ' + wd).trim(); }); if (cur) out.push(cur); return out.slice(0, 3); };
  const place = ev.map(e => {
    const lines = wrap(e.label || ''), tw = Math.max(70, ...lines.map(l => l.length * 6.7), (e.date || '').length * 6.3) + 10, x = X(e.a), flip = x + tw > w - 8;
    const span = flip ? [x - tw, x + 4] : [x - 4, x + tw];
    let L = 0; for (; L < 8; L++) { const used = lvl[L] || []; if (!used.some(([a, b]) => span[0] < b && span[1] > a)) { (lvl[L] = used).push(span); break; } }
    return { e, lines, x, flip, L: Math.min(L, 7), side: L % 2 ? 1 : -1 };
  });
  const lvAbove = Math.max(0, ...place.filter(p => p.side < 0).map(p => Math.floor(p.L / 2) + 1)), lvBelow = Math.max(0, ...place.filter(p => p.side > 0).map(p => Math.floor(p.L / 2) + 1));
  const step = 66, axisY = 24 + lvAbove * step, h = axisY + 34 + lvBelow * step + 10;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${VIZ.mapFont}"><rect width="${w}" height="${h}" fill="#fff"/>`;
  const cand = [1 / 12, 1 / 4, 1 / 2, 1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]; const tstep = cand.find(c => (hi - lo) / c <= 10) || 1000;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  s += `<line x1="${pad - 10}" x2="${w - pad + 10}" y1="${axisY}" y2="${axisY}" stroke="#9aa1a8" stroke-width="1.5"/>`;
  for (let t = Math.ceil(lo / tstep - 1e-9) * tstep; t <= hi + 1e-9; t += tstep) { const x = X(t); const sub = tstep < 1 ? Math.round((t - Math.floor(t)) * 12) % 12 : 0; const lab = tstep < 1 ? (sub ? MON[sub] : yearLabel(Math.round(t))) : yearLabel(t); s += `<line x1="${x}" x2="${x}" y1="${axisY - 4}" y2="${axisY + 4}" stroke="#9aa1a8"/><text x="${x}" y="${axisY + 18}" text-anchor="middle" font-size="11" fill="#6f7a84" font-weight="${sub ? 400 : 700}">${lab}</text>`; }
  place.forEach(p => {
    const lv = Math.floor(p.L / 2) + 1, x = p.x, anc = p.flip ? 'end' : 'start', tx = p.flip ? x - 5 : x + 5;
    if (p.e.b !== null) { const x2 = X(p.e.b); s += `<rect x="${x}" y="${axisY - 4}" width="${Math.max(3, x2 - x)}" height="8" rx="4" fill="${SERIES[0]}" fill-opacity=".55"/>`; }
    let top; // y of the date line
    if (p.side < 0) { const bottom = axisY - 14 - (lv - 1) * step; top = bottom - p.lines.length * 15; s += `<line x1="${x}" x2="${x}" y1="${axisY}" y2="${bottom}" stroke="#b7bdc3"/>`; }
    else { top = axisY + 40 + (lv - 1) * step; s += `<line x1="${x}" x2="${x}" y1="${axisY}" y2="${top - 12}" stroke="#b7bdc3"/>`; }
    s += `<circle cx="${x}" cy="${axisY}" r="5" fill="${SERIES[0]}" stroke="#fff" stroke-width="2"/>`;
    s += `<text x="${tx}" y="${top}" text-anchor="${anc}" font-size="11" font-weight="700" fill="#52514e">${esc(p.e.date || '')}</text>`;
    p.lines.forEach((l, i) => { s += `<text x="${tx}" y="${top + 15 + i * 15}" text-anchor="${anc}" font-size="13" fill="${VIZ.ink}">${esc(l)}</text>`; });
  });
  return { svg: s + '</svg>', w, h };
}
let tfSpec = null, tfOld = null;
function openTimelineFig(spec) {
  tfOld = spec ? JSON.parse(JSON.stringify(spec)) : null;
  if (!spec) {
    const src = boardOn && BG() === 'timeline' ? boardNotes() : P.notes;
    const ev = src.filter(n => dateKey(n.date) !== null).map(n => ({ id: n.id, date: n.date, label: n.title || firstLine(n.body), on: true })).sort((a, b) => dateKey(a.date) - dateKey(b.date));
    if (!ev.length) { toast('No dated notes yet. Give notes an event date (when it happened) first; they then appear on the board’s Timeline view.'); return; }
    spec = { type: 'timeline', w: 960, events: ev, caption: '', source: '' };
  }
  tfSpec = spec;
  $('#tfCaption').value = spec.caption || ''; $('#tfSource').value = spec.source || '';
  $('#tfList').innerHTML = spec.events.map((e, i) => `<div class="tf-ev"><input type="checkbox" data-i="${i}" data-f="on" ${e.on !== false ? 'checked' : ''}><input data-i="${i}" data-f="date" value="${esc(e.date)}" class="tf-date"><input data-i="${i}" data-f="label" value="${esc(e.label)}"></div>`).join('');
  $('#tfOk').textContent = specTarget ? 'Update timeline' : 'Insert timeline';
  $('#tfDlg').showModal(); tfPreview();
}
const tfPreview = debounce(() => { const r = timelineSVG(tfSpec); $('#tfStage').innerHTML = r.svg; const svg = $('#tfStage svg'); svg.removeAttribute('width'); svg.removeAttribute('height'); svg.style.width = '100%'; svg.style.height = 'auto'; }, 120);
$('#tfList').addEventListener('input', e => { const t = e.target, ev = tfSpec.events[+t.dataset.i]; if (!ev) return; ev[t.dataset.f] = t.type === 'checkbox' ? t.checked : t.value; tfPreview(); });
$('#tfAll').addEventListener('click', () => { const on = !tfSpec.events.every(e => e.on !== false); tfSpec.events.forEach(e => e.on = on); openTimelineFig(tfSpec); });
$('#tfCancel').addEventListener('click', () => { $('#tfDlg').close(); specTarget = null; });
$('#bdTlFig').addEventListener('click', () => { specTarget = null; openTimelineFig(); });
$('#tfOk').addEventListener('click', async () => { tfSpec.caption = $('#tfCaption').value.trim(); tfSpec.source = $('#tfSource').value.trim(); const s = tfSpec; $('#tfDlg').close(); try { await placeSpecFigure(s, tfOld); } catch (e) { toast(e.message); } });

/* ---------------- relationship map ---------------- */
let relOn = false, REL = null, relSel = null, relPick = null, relForFigure = false;
function relMatchers() {
  return P.entities.filter(e => e.name.trim()).map(e => { const forms = [e.name, ...e.variants].map(s => s.trim()).filter(Boolean); return { e, re: new RegExp('(?<![\\p{L}\\p{N}])(' + forms.map(escRe).join('|') + ')(?![\\p{L}\\p{N}])', 'u') }; });
}
function relUnits() {
  const out = [];
  P.notes.forEach(n => out.push({ kind: 'note', id: n.id, title: noteTitle(n) || 'Untitled note', text: (n.title + '\n' + plainMd(n.body)).replace(/\s+/g, ' ') }));
  P.docs.forEach(d => { const t = document.createElement('div'); t.innerHTML = d.id === curDocId ? editor.innerHTML : d.html; $$('.cite,.fn,.flag', t).forEach(m => m.remove()); [...t.children].forEach((el, i) => { const tx = el.textContent.replace(/\s+/g, ' ').trim(); if (tx) out.push({ kind: 'doc', id: d.id, at: i, title: d.title || 'Untitled', text: tx }); }); });
  return out;
}
function relCompute() {
  const ms = relMatchers(), units = relUnits(), mentions = {}, pairs = {}, where = {};
  units.forEach((u, ui) => {
    const hit = ms.filter(m => m.re.test(u.text)).map(m => m.e.id); if (!hit.length) return;
    hit.forEach(id => { mentions[id] = (mentions[id] || 0) + 1; });
    for (let i = 0; i < hit.length; i++) for (let j = i + 1; j < hit.length; j++) { const k = [hit[i], hit[j]].sort().join('|'); pairs[k] = (pairs[k] || 0) + 1; (where[k] = where[k] || []).push(ui); }
  });
  REL = { units, mentions, pairs, where };
}
const REL_COL = { person: SERIES[0], organization: SERIES[1], place: SERIES[2], term: '#8a8f98' };
function relGraph() {
  const minW = +$('#relMin').value || 1, kinds = new Set($$('#relKinds input:checked').map(i => i.value)), showCo = $('#relCo').checked;
  const rels = (P.relations || []);
  let nodes = P.entities.filter(e => kinds.has(e.kind || 'person') && (REL.mentions[e.id] || rels.some(r => r.a === e.id || r.b === e.id)));
  const ids = new Set(nodes.map(n => n.id));
  const co = showCo ? Object.entries(REL.pairs).filter(([k, w]) => w >= minW).map(([k, w]) => { const [a, b] = k.split('|'); return { a, b, w, key: k }; }).filter(e => ids.has(e.a) && ids.has(e.b)) : [];
  const man = rels.filter(r => ids.has(r.a) && ids.has(r.b));
  if (minW > 1) { const linked = new Set([...co, ...man].flatMap(e => [e.a, e.b])); nodes = nodes.filter(n => linked.has(n.id)); }
  return { nodes, co, man };
}
function relLayout(gr, w, h) {
  const L = P.relLayout = P.relLayout || {};
  const N = gr.nodes.map((n, i) => { const p = L[n.id]; const a = i / gr.nodes.length * Math.PI * 2; return { id: n.id, x: p ? p.x : w / 2 + Math.cos(a) * Math.min(w, h) * .32, y: p ? p.y : h / 2 + Math.sin(a) * Math.min(w, h) * .32, pin: !!p, vx: 0, vy: 0 }; });
  const byId = Object.fromEntries(N.map(n => [n.id, n])), E = [...gr.co.map(e => ({ s: byId[e.a], t: byId[e.b], w: e.w })), ...gr.man.map(e => ({ s: byId[e.a], t: byId[e.b], w: 3 }))].filter(e => e.s && e.t);
  const Lk = Math.max(130, Math.min(280, Math.sqrt(w * h / Math.max(1, N.length)) * .55)), rep = Lk * Lk * .9;
  for (let it = 0; it < 320; it++) {
    const alpha = 1 - it / 320;
    for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) { const a = N[i], b = N[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + .01; const f = rep / d2 * alpha; const d = Math.sqrt(d2); dx /= d; dy /= d; a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f; }
    E.forEach(e => { const dx = e.t.x - e.s.x, dy = e.t.y - e.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, k = (d - Lk) * .02 * Math.min(3, e.w) * alpha; e.s.vx += dx / d * k; e.s.vy += dy / d * k; e.t.vx -= dx / d * k; e.t.vy -= dy / d * k; });
    N.forEach(n => { n.vx += (w / 2 - n.x) * .004 * alpha; n.vy += (h / 2 - n.y) * .004 * alpha; if (!n.pin) { n.x += Math.max(-20, Math.min(20, n.vx)); n.y += Math.max(-20, Math.min(20, n.vy)); } n.vx *= .55; n.vy *= .55; n.x = Math.max(40, Math.min(w - 40, n.x)); n.y = Math.max(30, Math.min(h - 30, n.y)); });
  }
  if (N.length > 1 && !N.some(n => n.pin)) { // spread the drawing to fill the frame, leaving room for labels on the right
    const xs = N.map(n => n.x), ys = N.map(n => n.y), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const sx = (w - 260) / Math.max(1, x1 - x0), sy = (h - 140) / Math.max(1, y1 - y0), k = Math.min(sx, sy, 3);
    N.forEach(n => { n.x = 70 + (n.x - x0) * k + ((w - 260) - (x1 - x0) * k) / 2; n.y = 60 + (n.y - y0) * k + ((h - 140) - (y1 - y0) * k) / 2; });
  }
  return byId;
}
function networkSVG(spec, opt = {}) {
  const { w, h, nodes, edges } = spec;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${VIZ.mapFont}"><rect width="${w}" height="${h}" fill="#fff"/><defs><marker id="rh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#24456e"/></marker></defs>`;
  const N = Object.fromEntries(nodes.map(n => [n.id, n]));
  edges.filter(e => !e.label && e.label !== '').forEach(e => { const a = N[e.a], b = N[e.b]; if (!a || !b) return; s += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#a9b0b8" stroke-width="${Math.min(6, 1 + Math.log2(e.w || 1) * 1.3).toFixed(2)}" stroke-opacity=".75" ${opt.ui ? `data-edge="${e.key}"` : ''}/>`; });
  edges.filter(e => e.label || e.label === '').forEach(e => { const a = N[e.a], b = N[e.b]; if (!a || !b) return; const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, rb = b.r + 4; const x2 = b.x - dx / d * rb, y2 = b.y - dy / d * rb; s += `<line x1="${a.x}" y1="${a.y}" x2="${x2}" y2="${y2}" stroke="#24456e" stroke-width="2" ${e.dir ? 'marker-end="url(#rh)"' : ''} ${opt.ui ? `data-rel="${e.id}"` : ''}/>`; if (e.label) s += `<text x="${(a.x + b.x) / 2}" y="${(a.y + b.y) / 2 - 5}" text-anchor="middle" font-size="11.5" font-style="italic" fill="#24456e" paint-order="stroke" stroke="#fff" stroke-width="3.5">${esc(e.label)}</text>`; });
  nodes.forEach(n => { s += `<circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${REL_COL[n.kind] || REL_COL.term}" stroke="#fff" stroke-width="2" ${opt.ui ? `data-node="${n.id}" class="${opt.sel === n.id ? 'rel-sel' : ''} ${opt.pick === n.id ? 'rel-pick' : ''}"` : ''}/><text x="${n.x + n.r + 5}" y="${n.y + 4}" font-size="${n.r > 12 ? 13.5 : 12.5}" font-weight="${n.r > 12 ? 700 : 400}" fill="${VIZ.ink}" paint-order="stroke" stroke="#fff" stroke-width="3.5" stroke-linejoin="round" ${opt.ui ? `data-node="${n.id}"` : ''}>${esc(n.label)}</text>`; });
  const kinds = [...new Set(nodes.map(n => n.kind))];
  s += `<g transform="translate(12 ${h - 12 - kinds.length * 18})">${kinds.map((k, i) => `<circle cx="7" cy="${i * 18 + 7}" r="5.5" fill="${REL_COL[k] || REL_COL.term}"/><text x="18" y="${i * 18 + 11}" font-size="11.5" fill="#52514e">${{ person: 'People', organization: 'Organizations', place: 'Places', term: 'Terms' }[k] || k}</text>`).join('')}</g>`;
  return { svg: s + '</svg>', w, h };
}
function relSpecNow() {
  const w = 960, h = 620, gr = relGraph(), pos = relLayout(gr, w, h);
  const nodes = gr.nodes.map(e => ({ id: e.id, label: e.name, kind: e.kind || 'person', x: Math.round(pos[e.id].x), y: Math.round(pos[e.id].y), r: Math.round(6 + Math.min(14, Math.sqrt(REL.mentions[e.id] || 1) * 2.2)) }));
  const edges = [...gr.co.map(e => ({ a: e.a, b: e.b, w: e.w, key: e.key })), ...gr.man.map(r => ({ id: r.id, a: r.a, b: r.b, label: r.label || '', dir: !!r.dir }))];
  return { type: 'network', w, h, nodes, edges };
}
function openRel(forFigure = false) {
  syncEditor(); if (boardOn) closeBoard(); if (planOn) closePlan(); if (homeOn) closeHome(); if (draftsOn) closeDrafts();
  relOn = true; relForFigure = forFigure; relSel = null; relPick = null;
  document.body.classList.add('rel-on'); $('#rel').classList.remove('hidden'); document.body.classList.remove('side-open');
  $('#relFig').textContent = specTarget ? 'Update figure' : 'Insert as figure…';
  relCompute(); renderRel();
}
function closeRel() { relOn = false; document.body.classList.remove('rel-on'); $('#rel').classList.add('hidden'); }
function renderRel() {
  if (!P.entities.filter(e => e.name.trim()).length) { $('#relStage').innerHTML = `<div class="rel-empty"><p><b>Map who’s connected to whom.</b></p><p>Add the people, organizations and places you track to <b>Names &amp; spellings</b>. Anabasis counts how often they turn up together in the same paragraph or note and draws the links. You can add your own labeled links too, like “funded” or “commanded”.</p><button class="primary" id="relNames">Add names…</button></div>`; $('#relSide').innerHTML = ''; return; }
  const spec = relSpecNow(); REL.spec = spec;
  $('#relStage').innerHTML = networkSVG(spec, { ui: true, sel: relSel, pick: relPick }).svg;
  const svg = $('#relStage svg'); svg.removeAttribute('width'); svg.removeAttribute('height'); svg.style.width = '100%'; svg.style.height = 'auto';
  relSide();
}
function relSide(edgeKey) {
  const ent = id => P.entities.find(e => e.id === id);
  let h = '';
  if (edgeKey) {
    const [a, b] = edgeKey.split('|'); const us = (REL.where[edgeKey] || []).map(i => REL.units[i]);
    h = `<h5>${esc(ent(a)?.name)} &amp; ${esc(ent(b)?.name)}</h5><p class="small muted">Together in ${us.length} paragraph${us.length === 1 ? '' : 's'} or note${us.length === 1 ? '' : 's'}.</p><ul class="rel-list">${us.slice(0, 40).map((u, i) => `<li data-u="${REL.units.indexOf(u)}"><b>${esc(u.title)}</b><span>${esc(u.text.slice(0, 160))}${u.text.length > 160 ? '…' : ''}</span></li>`).join('')}</ul>`;
  } else if (relSel) {
    const e = ent(relSel); const co = Object.entries(REL.pairs).filter(([k]) => k.split('|').includes(relSel)).map(([k, w]) => ({ other: k.split('|').find(x => x !== relSel), w, k })).sort((x, y) => y.w - x.w);
    const rels = (P.relations || []).filter(r => r.a === relSel || r.b === relSel);
    h = `<h5>${esc(e?.name || '')}</h5><p class="small muted">${{ person: 'Person', organization: 'Organization', place: 'Place', term: 'Term' }[e?.kind] || ''}${e?.note ? ' · ' + esc(e.note) : ''}. Mentioned in ${REL.mentions[relSel] || 0} paragraph${REL.mentions[relSel] === 1 ? '' : 's'} or note${REL.mentions[relSel] === 1 ? '' : 's'}.</p>
      ${rels.length ? `<h6>Your links</h6><ul class="rel-list">${rels.map(r => `<li class="rel-man"><span><b>${esc(ent(r.a)?.name)}</b> ${esc(r.label || 'linked to')} <b>${esc(ent(r.b)?.name)}</b></span><button class="ghost small" data-relde="${r.id}">Remove</button></li>`).join('')}</ul>` : ''}
      ${co.length ? `<h6>Appears with</h6><ul class="rel-list">${co.slice(0, 25).map(c => `<li data-edge="${c.k}"><b>${esc(ent(c.other)?.name)}</b><span>${c.w} time${c.w === 1 ? '' : 's'}</span></li>`).join('')}</ul>` : ''}
      <p class="small muted">Shift-click another name to add a labeled link between them.</p>`;
  } else h = `<p class="small muted">Click a name to see who it appears with, or a line to read the passages. Drag names to arrange them; the map remembers where you put them. Shift-click two names to add your own labeled link.</p>`;
  $('#relSide').innerHTML = h;
}
let relDrag = null;
$('#relStage').addEventListener('pointerdown', e => {
  const n = e.target.closest('[data-node]'); if (!n) return;
  const id = n.dataset.node;
  if (e.shiftKey) { if (!relSel || relSel === id) { relSel = id; renderRel(); return; } const a = relSel, b = id; ask('Add a link', `How are they connected? (e.g. “funded”, “commanded”, “met”). It points from ${P.entities.find(x => x.id === a).name} to ${P.entities.find(x => x.id === b).name}.`, 'Add link', '').then(t => { if (t === null) return; P.relations = P.relations || []; P.relations.push({ id: uid('rl'), a, b, label: t.trim(), dir: !!t.trim() }); markDirty(); renderRel(); }); return; }
  const svg = $('#relStage svg'), r = svg.getBoundingClientRect(), sc = REL.spec.w / r.width;
  relDrag = { id, sc, r, moved: false }; svg.setPointerCapture(e.pointerId);
});
$('#relStage').addEventListener('pointermove', e => { if (!relDrag) return; const { r, sc, id } = relDrag; const x = (e.clientX - r.left) * sc, y = (e.clientY - r.top) * sc; P.relLayout = P.relLayout || {}; P.relLayout[id] = { x: Math.round(x), y: Math.round(y) }; relDrag.moved = true; const nd = REL.spec.nodes.find(n => n.id === id); if (nd) { nd.x = x; nd.y = y; $('#relStage').innerHTML = networkSVG(REL.spec, { ui: true, sel: relSel }).svg; const svg = $('#relStage svg'); svg.removeAttribute('width'); svg.removeAttribute('height'); svg.style.width = '100%'; svg.style.height = 'auto'; } });
$('#relStage').addEventListener('pointerup', e => { if (!relDrag) return; const d = relDrag; relDrag = null; if (d.moved) { markDirty(); renderRel(); return; } relSel = d.id; renderRel(); });
$('#relStage').addEventListener('click', e => { if (e.target.id === 'relNames') { openNames(); return; } const ed = e.target.closest('[data-edge]'); if (ed) relSide(ed.dataset.edge); });
$('#relSide').addEventListener('click', e => {
  const ed = e.target.closest('[data-edge]'); if (ed) { relSide(ed.dataset.edge); return; }
  const de = e.target.closest('[data-relde]'); if (de) { P.relations = P.relations.filter(r => r.id !== de.dataset.relde); markDirty(); renderRel(); return; }
  const u = e.target.closest('[data-u]'); if (u) { const unit = REL.units[+u.dataset.u]; if (!unit) return; if (unit.kind === 'note') openNote(unit.id); else { closeRel(); jumpTo(unit.id, unit.at); } }
});
['#relMin', '#relCo'].forEach(s => $(s).addEventListener('input', () => { $('#relMinV').textContent = $('#relMin').value; renderRel(); }));
$('#relKinds').addEventListener('change', renderRel);
$('#relBack').addEventListener('click', () => { closeRel(); openDoc(curDocId); });
$('#relRelayout').addEventListener('click', () => { P.relLayout = {}; markDirty(); renderRel(); });
$('#relFig').addEventListener('click', () => { if (!REL || !REL.spec || !REL.spec.nodes.length) { toast('Nothing to put in a figure yet.'); return; } openNetworkFig(Object.assign({}, REL.spec, { caption: '', source: '' })); });
let nfSpec = null, nfOld = null;
function openNetworkFig(spec) {
  nfOld = specTarget ? JSON.parse(JSON.stringify(spec)) : null; nfSpec = spec;
  $('#nfCaption').value = spec.caption || ''; $('#nfSource').value = spec.source || '';
  $('#nfStage').innerHTML = networkSVG(spec).svg; const svg = $('#nfStage svg'); svg.removeAttribute('width'); svg.removeAttribute('height'); svg.style.width = '100%'; svg.style.height = 'auto';
  $('#nfRefresh').classList.toggle('hidden', !specTarget); $('#nfOk').textContent = specTarget ? 'Update figure' : 'Insert figure';
  $('#nfDlg').showModal();
}
$('#nfRefresh').addEventListener('click', () => { relCompute(); const fresh = relSpecNow(); nfSpec = Object.assign(fresh, { caption: $('#nfCaption').value, source: $('#nfSource').value }); openNetworkFig(nfSpec); toast('Redrawn from your current names and notes.'); });
$('#nfCancel').addEventListener('click', () => { $('#nfDlg').close(); });
$('#nfOk').addEventListener('click', async () => { nfSpec.caption = $('#nfCaption').value.trim(); nfSpec.source = $('#nfSource').value.trim(); const s = nfSpec; $('#nfDlg').close(); try { await placeSpecFigure(s, nfOld); } catch (e) { toast(e.message); } });
$('#btnRel').addEventListener('click', () => openRel());

/* ================================================================
   Acronyms & abbreviations
   ================================================================ */
const ACRO_IGNORE = new Set('US USA UK UN EU TV AM PM AD BC BCE CE OK ID DC II III IV VI VII VIII IX XI XII XIII XIV XV XVI XVII XVIII XIX XX XXI CEO PhD NB PS'.split(' '));
const ACRO_STOP = new Set(['of', 'and', 'for', 'the', 'in', 'on', 'to', 'de', 'del', 'la', '&', 'a', 'an', 'at', 'by', 'with', 'du', 'des', 'et', 'al']);
const isRoman = s => /^[IVXLCDM]+$/.test(s);
function acroList() { P.acronyms = P.acronyms || []; return P.acronyms; }
function acroIgnored(s) { return ACRO_IGNORE.has(s) || (P.acroIgnore || []).includes(s) || isRoman(s); }
function acroMatchLong(words, acr) {
  const A = acr.replace(/s$/, '').toUpperCase();
  for (let start = words.length - 1; start >= Math.max(0, words.length - 12); start--) {
    const seg = words.slice(start), sig = seg.filter(w => !ACRO_STOP.has(w.toLowerCase()));
    if (!sig.length || ACRO_STOP.has(seg[0].toLowerCase())) continue;
    const inits = sig.map(w => w.replace(/^[^\p{L}\p{N}]+/u, '')[0] || '').join('').toUpperCase();
    const hyph = sig.flatMap(w => w.split('-')).map(w => w[0] || '').join('').toUpperCase();
    if (inits === A || hyph === A) return seg.join(' ');
    if (inits[0] === A[0] && sig.length >= A.length - 1 && sig.length <= A.length + 1 && start <= words.length - A.length + 1) { const strict = [...A].every(ch => inits.includes(ch)); if (strict) return seg.join(' '); }
  }
  return '';
}
/* scan the open document: first uses, definitions, counts */
function acroScan() {
  const out = {}, blocks = $$(':scope > p, :scope > ul > li, :scope > ol > li, :scope > blockquote, :scope > figure figcaption, :scope > figure td, :scope > figure th', editor);
  blocks.forEach((el, bi) => {
    if (el.matches('blockquote') && el.querySelector('p')) return;
    const { text, range } = blockMap(el);
    const defs = [];
    const dre = /\(([A-Z][A-Za-z0-9&]{1,9})\)/g; let m;
    while ((m = dre.exec(text))) {
      const acr = m[1]; if (!/[A-Z].*[A-Z]/.test(acr) || acroIgnored(acr.replace(/s$/, ''))) continue;
      const before = text.slice(Math.max(0, m.index - 160), m.index).replace(/\s+$/, '');
      const words = before.split(/\s+/).filter(Boolean); const long = acroMatchLong(words, acr);
      if (!long) continue;
      const short = acr.replace(/(?<=[A-Z])s$/, '');
      const startIdx = m.index - (before.length - before.lastIndexOf(long)) - (text.slice(0, m.index).length - text.slice(0, m.index).replace(/\s+$/, '').length);
      const s0 = text.lastIndexOf(long, m.index);
      defs.push({ short, long: long.replace(/s$/, short.endsWith('s') ? 's' : '').replace(/[,;:]$/, ''), longRaw: long, at: s0 >= 0 ? s0 : startIdx, end: m.index + m[0].length, parenAt: m.index });
    }
    defs.forEach(d => { const o = out[d.short] = out[d.short] || { short: d.short, uses: [], defs: [] }; o.defs.push({ el, bi, at: d.at, end: d.end, long: d.long, range: () => range(d.at, d.end) }); });
    const ure = /(?<![\p{L}\p{N}&])([A-Z][A-Z0-9&]{1,8})(s)?(?![\p{L}\p{N}&])/gu;
    while ((m = ure.exec(text))) {
      const short = m[1]; if (!/[A-Z].*[A-Z]/.test(short) || acroIgnored(short)) continue;
      if (defs.some(d => m.index > d.parenAt && m.index < d.end)) continue;  // the (ABC) of a definition
      const o = out[short] = out[short] || { short, uses: [], defs: [] };
      const at = m.index, len = m[0].length, plural = !!m[2];
      o.uses.push({ el, bi, at, plural, range: () => range(at, at + len) });
    }
  });
  return out;
}
function acroLearn(scan) {
  const list = acroList(); let added = 0;
  Object.values(scan).forEach(o => { const d = o.defs[0]; if (d && !list.some(a => a.short === o.short)) { list.push({ id: uid('ac'), short: o.short, long: d.long.replace(/^(the|a|an)\s+/i, '') }); added++; } });
  if (added) markDirty();
}
function acroIssues() {
  const scan = acroScan(); acroLearn(scan);
  const list = acroList(), known = s => list.find(a => a.short === s), issues = [];
  Object.values(scan).forEach(o => {
    const firstUse = o.uses[0], firstDef = o.defs[0], total = o.uses.length + o.defs.length;
    const k = known(o.short);
    const before = (x, y) => x.bi < y.bi || (x.bi === y.bi && x.at < y.at);
    if (!o.defs.length) { if (o.uses.length) issues.push({ t: 'undef', o, k, msg: k ? `Not spelled out. First use should read “${k.long} (${o.short})”.` : 'Used but never spelled out.' }); return; }
    if (firstUse && before(firstUse, firstDef)) issues.push({ t: 'late', o, msg: `Spelled out only after its first use.` });
    if (o.defs.length > 1) issues.push({ t: 'dup', o, msg: `Spelled out ${o.defs.length} times. Once is enough.` });
    if (total === 1) issues.push({ t: 'once', o, msg: `Defined but never used again. Just spell it out.` });
  });
  return { issues, scan };
}
function replaceRange(r, text) { if (!r) return; r.deleteContents(); r.insertNode(document.createTextNode(text)); }
function atSentenceStart(r) { try { const pre = document.createRange(); const blk = (r.startContainer.nodeType === 1 ? r.startContainer : r.startContainer.parentElement).closest('p,li,blockquote,figcaption,td,th,h1,h2,h3') || editor; pre.setStart(blk, 0); pre.setEnd(r.startContainer, r.startOffset); const t = pre.toString(); return !t.trim() || /[.!?:]["”’)\]]?\s+$/.test(t); } catch (e) { return false; } }
const capFirst = s => s ? s[0].toUpperCase() + s.slice(1) : s;
function longFor(long, plural) { return plural && !/s$/.test(long) ? long + 's' : long; }
function acroFix(i) {
  const it = ACRO_LAST[i]; if (!it) return; const o = it.o;
  const longOf = () => (it.k || acroList().find(a => a.short === o.short) || {}).long || o.defs[0]?.long;
  if (it.t === 'undef') {
    let long = longOf();
    const go = l => { const u = o.uses[0], r = u.range(); let t = `${longFor(l, u.plural)} (${o.short}${u.plural ? 's' : ''})`; if (atSentenceStart(r)) t = capFirst(t); replaceRange(r, t); if (!acroList().some(a => a.short === o.short)) acroList().push({ id: uid('ac'), short: o.short, long: l }); onEdit(); renderAcronyms(); toast(`Spelled out ${o.short} at its first use.`); };
    if (long) go(long); else ask(`What does ${o.short} stand for?`, 'It’s spelled out at the first use and added to your abbreviations list.', 'Spell it out', '').then(t => { if (t && t.trim()) go(t.trim()); });
    return;
  }
  if (it.t === 'late') { const d = o.defs[0], u = o.uses[0], long = d.long; const rd = d.range(), ru = u.range(); // change the later one first so offsets hold
    const dPlural = /s\)$/.test(rd.toString()); let dt = o.short + (dPlural ? 's' : ''); if (atSentenceStart(rd)) dt = capFirst(dt);
    let ut = `${longFor(long, u.plural)} (${o.short}${u.plural ? 's' : ''})`; if (atSentenceStart(ru)) ut = capFirst(ut);
    replaceRange(rd, dt); replaceRange(ru, ut); onEdit(); renderAcronyms(); toast(`Moved the definition of ${o.short} to its first use.`); return; }
  if (it.t === 'dup') { o.defs.slice(1).reverse().forEach(d => { const r = d.range(); replaceRange(r, o.short + (/s\)$/.test(r.toString()) ? 's' : '')); }); onEdit(); renderAcronyms(); toast(`Kept only the first definition of ${o.short}.`); return; }
  if (it.t === 'once') { const d = o.defs[0], r = d.range(); replaceRange(r, r.toString().replace(/\s*\([^)]*\)$/, '')); onEdit(); renderAcronyms(); toast(`Spelled out ${d.long} without the abbreviation.`); return; }
}
let ACRO_LAST = [];
function renderAcronyms() {
  if (!$('#acroList') || !curDoc()) return;
  const { issues } = acroIssues(); ACRO_LAST = issues;
  $('#acroCount').textContent = issues.length || '';
  $('#acroList').innerHTML = issues.length ? issues.map((it, i) => `<li><span><b>${esc(it.o.short)}</b> ${esc(it.msg)}</span><span class="ol-acts"><button class="small" data-acfix="${i}">${{ undef: it.k ? 'Spell out' : 'Define…', late: 'Move definition', dup: 'Fix', once: 'Spell out' }[it.t]}</button>${it.t === 'undef' ? `<button class="small ghost" data-acign="${esc(it.o.short)}" title="Never flag this one">Ignore</button>` : ''}<button class="small ghost" data-acgo="${i}">Show</button></span></li>`).join('') : '<li class="muted small none">Every acronym is spelled out once, at its first use.</li>';
}
const renderAcronymsSoon = debounce(() => { if (!homeOn && !boardOn && !planOn) renderAcronyms(); }, 900);
editor.addEventListener('input', renderAcronymsSoon);
$('#acroList').addEventListener('click', e => {
  const f = e.target.closest('[data-acfix]'); if (f) { acroFix(+f.dataset.acfix); return; }
  const g = e.target.closest('[data-acign]'); if (g) { P.acroIgnore = [...new Set([...(P.acroIgnore || []), g.dataset.acign])]; markDirty(); renderAcronyms(); return; }
  const s = e.target.closest('[data-acgo]'); if (s) { const it = ACRO_LAST[+s.dataset.acgo]; const u = it.o.uses[0] || it.o.defs[0]; const r = u && u.range(); if (r) { const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); u.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } }
});
function openAcronyms() {
  acroIssues();
  const used = acroScan();
  $('#acRows').innerHTML = acroList().slice().sort((a, b) => a.short.localeCompare(b.short)).map(a => `<div class="ac-row" data-id="${a.id}"><input data-f="short" value="${esc(a.short)}" class="ac-s"><input data-f="long" value="${esc(a.long)}"><span class="small muted">${used[a.short] ? (used[a.short].uses.length + used[a.short].defs.length) + '× here' : ''}</span><button class="ghost small" data-del="${a.id}" title="Remove">✕</button></div>`).join('') || '<div class="small muted">None yet. Acronyms you spell out in the text, like “Islamic Revolutionary Guard Corps (IRGC)”, are added here automatically.</div>';
  $('#acIgnore').value = (P.acroIgnore || []).join(', ');
  $('#acDlg').showModal();
}
$('#acRows').addEventListener('input', e => { const row = e.target.closest('[data-id]'); const a = acroList().find(x => x.id === row?.dataset.id); if (a) { a[e.target.dataset.f] = e.target.value.trim(); markDirty(); } });
$('#acRows').addEventListener('click', e => { const d = e.target.closest('[data-del]'); if (d) { P.acronyms = acroList().filter(a => a.id !== d.dataset.del); markDirty(); openAcronyms(); } });
$('#acAdd').addEventListener('click', () => { acroList().push({ id: uid('ac'), short: '', long: '' }); markDirty(); openAcronyms(); setTimeout(() => $$('#acRows .ac-s').pop()?.focus(), 30); });
$('#acDone').addEventListener('click', () => { P.acroIgnore = $('#acIgnore').value.split(/[,\s]+/).map(s => s.trim()).filter(Boolean); P.acronyms = acroList().filter(a => a.short && a.long); markDirty(); $('#acDlg').close(); renderAcronyms(); });
$('#btnAcro').addEventListener('click', openAcronyms);
function abbrPlaceholder() { return '<nav class="abbr" contenteditable="false"><p>List of abbreviations — filled in when you export.</p></nav>'; }
function fillAbbreviations(tmp) {
  const navs = $$('nav.abbr', tmp); if (!navs.length) return;
  const text = tmp.textContent; const used = acroList().filter(a => a.short && a.long && new RegExp('(?<![\\p{L}\\p{N}])' + escRe(a.short) + 's?(?![\\p{L}\\p{N}])', 'u').test(text)).sort((a, b) => a.short.localeCompare(b.short));
  navs.forEach(nav => { nav.removeAttribute('contenteditable'); if (!used.length) { nav.remove(); return; } nav.innerHTML = `<h1 class="toc-title">Abbreviations</h1>${used.map(a => `<p class="abbr-row"><b>${esc(a.short)}</b> ${esc(a.long)}</p>`).join('')}`; });
}

/* ================================================================
   Estimative language (ICD 203)
   ================================================================ */
const ICD = [['almost no chance', 'remote', '1–5%'], ['very unlikely', 'highly improbable', '5–20%'], ['unlikely', 'improbable', '20–45%'], ['roughly even chance', 'roughly even odds', '45–55%'], ['likely', 'probable', '55–80%'], ['very likely', 'highly probable', '80–95%'], ['almost certain', 'nearly certain', '95–99%']];
const EST_A = /\b(almost no chance|very unlikely|unlikely|roughly even chance|very likely|likely|almost certain(?:ly)?)\b/gi;
const EST_B = /\b(remote(?=\s+(?:chance|possibility|probability|likelihood))|highly improbable|improbabl[ey]|roughly even odds|highly probable|probabl[ey]|nearly certain(?:ly)?)\b/gi;
const EST_VAGUE = /\b(may|might|could|possibly|possible|perhaps|potentially|conceivably|cannot be ruled out|can(?:not|'t) rule out|it is possible|there is a (?:chance|possibility)|suggests?|appears? to|seems? to)\b/gi;
const EST_CONF = /\b(high|moderate|medium|low)\s+confidence\b/gi;
let estOn = null, EST = { vague: [], scale: [], issues: [] };
function estDefaultOn() { return ['brief', 'whitepaper'].includes((P.goal || {}).kind); }
function runEstimative() {
  const on = estOn ?? estDefaultOn(); const hl = window.CSS && CSS.highlights && window.Highlight;
  EST = { vague: [], scale: [], issues: [], a: 0, b: 0 };
  const sentIssues = [];
  let kjSec = null, kjConf = false, inKJ = false, kjEl = null;
  [...editor.children].forEach(el => {
    if (/^H[1-3]$/.test(el.nodeName)) { if (inKJ && !kjConf) sentIssues.push({ msg: `“${kjSec}” has no confidence level (high, moderate or low).`, el: kjEl }); inKJ = /key judg/i.test(el.textContent); kjSec = el.textContent.trim(); kjConf = false; kjEl = el; return; }
    if (!el.matches('p,ul,ol,blockquote')) return;
    const targets = el.matches('ul,ol') ? $$('li', el) : [el];
    targets.forEach(t => {
      const { text, range } = blockMap(t); if (!text.trim()) return;
      let m; const push = (re, arr, tag) => { re.lastIndex = 0; while ((m = re.exec(text))) { const r = range(m.index, m.index + m[0].length); if (r) arr.push({ r, word: m[0], el: t, at: m.index, tag }); } };
      push(EST_VAGUE, EST.vague); push(EST_A, EST.scale, 'a'); push(EST_B, EST.scale, 'b');
      const sre = /[^.!?]+(?:[.!?]+["”’)\]]*|$)/g; let s;
      while ((s = sre.exec(text))) {
        const sent = s[0]; EST_CONF.lastIndex = 0; const conf = EST_CONF.exec(sent);
        if (conf) { if (inKJ) kjConf = true; if (/medium/i.test(conf[1])) sentIssues.push({ msg: `“medium confidence”: the standard levels are high, moderate and low.`, el: t }); EST_A.lastIndex = 0; EST_B.lastIndex = 0; if (EST_A.test(sent) || EST_B.test(sent)) sentIssues.push({ msg: `Confidence and likelihood in one sentence: “${sent.trim().slice(0, 90)}${sent.trim().length > 90 ? '…' : ''}” Give them separate sentences.`, el: t }); }
      }
    });
  });
  if (inKJ && !kjConf) sentIssues.push({ msg: `“${kjSec}” has no confidence level (high, moderate or low).`, el: kjEl });
  EST.a = EST.scale.filter(x => x.tag === 'a').length; EST.b = EST.scale.filter(x => x.tag === 'b').length;
  if (EST.a && EST.b) sentIssues.unshift({ msg: `Mixes the two wordings of the scale (${EST.a}× “likely”-style, ${EST.b}× “probable”-style). Pick one column and stick to it.` });
  EST.issues = sentIssues;
  if (hl) { if (on && EST.vague.length) CSS.highlights.set('cp-vague', new Highlight(...EST.vague.map(x => x.r))); else CSS.highlights.delete('cp-vague'); if (on && EST.scale.length) CSS.highlights.set('cp-scale', new Highlight(...EST.scale.map(x => x.r))); else CSS.highlights.delete('cp-scale'); }
  renderEstPanel(on);
  return on;
}
function renderEstPanel(on) {
  if (!$('#estList')) return;
  $('#estToggle').checked = on;
  const n = EST.vague.length + EST.issues.length; $('#estCount').textContent = on && n ? n : '';
  $('#estList').innerHTML = !on ? '<li class="muted small none">Turn on to check intelligence-style judgments against the ICD 203 likelihood scale. It’s on automatically for briefs and white papers.</li>'
    : (EST.issues.map((x, i) => `<li><span>${esc(x.msg)}</span>${x.el ? `<span class="ol-acts"><button class="small ghost" data-estgo="i${i}">Show</button></span>` : ''}</li>`).join('') +
      (EST.vague.length ? `<li><span><b>${EST.vague.length}</b> vague word${EST.vague.length === 1 ? '' : 's'} (${[...new Set(EST.vague.map(v => v.word.toLowerCase()))].slice(0, 6).map(esc).join(', ')}) that don’t say how likely. They’re underlined in orange; click one to pick a term from the scale.</span><span class="ol-acts"><button class="small ghost" data-estgo="v0">Next</button></span></li>` : '') +
      (!EST.issues.length && !EST.vague.length ? `<li class="muted small none">${EST.scale.length ? `${EST.scale.length} likelihood term${EST.scale.length === 1 ? '' : 's'}, all from the standard scale.` : 'No likelihood language yet.'}</li>` : '')) +
    `<li class="est-scale">${ICD.map(r => `<span><b>${r[0]}</b> / ${r[1]}</span><span class="muted">${r[2]}</span>`).join('')}</li>`;
}
let estNext = 0;
$('#estList').addEventListener('click', e => {
  const g = e.target.closest('[data-estgo]'); if (!g) return; const k = g.dataset.estgo;
  let el, r;
  if (k[0] === 'i') el = EST.issues[+k.slice(1)]?.el; else { const v = EST.vague[estNext++ % EST.vague.length]; el = v?.el; r = v?.r; }
  if (r) { const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  el && el.scrollIntoView({ block: 'center', behavior: 'smooth' });
});
$('#estToggle').addEventListener('change', e => { estOn = e.target.checked; runEstimative(); });
const runEstSoon = debounce(() => { if (!homeOn && !boardOn && !planOn) runEstimative(); }, 800);
editor.addEventListener('input', runEstSoon);
editor.addEventListener('click', e => {
  if (!(estOn ?? estDefaultOn()) || !EST.vague.length) return;
  const hit = EST.vague.find(v => { try { return v.r.isPointInRange(...caretAt(e)); } catch (_) { return false; } });
  if (!hit) return;
  closePop(); const rect = hit.r.getBoundingClientRect();
  popEl = document.createElement('div'); popEl.className = 'pop est-pop';
  const modal = /^(may|might|could)$/i.test(hit.word);
  const opts = modal ? [['will almost certainly', '95–99%'], ['will very likely', '80–95%'], ['will likely', '55–80%'], ['has a roughly even chance to', '45–55%'], ['is unlikely to', '20–45%'], ['is very unlikely to', '5–20%']] : [['almost certainly', '95–99%'], ['very likely', '80–95%'], ['likely', '55–80%'], ['roughly even chance', '45–55%'], ['unlikely', '20–45%'], ['very unlikely', '5–20%'], ['almost no chance', '1–5%']];
  popEl.innerHTML = `<div class="small muted" style="margin-bottom:6px">“${esc(hit.word)}” doesn’t say how likely. Replace with:</div>${opts.map(([t, p]) => `<button data-t="${esc(t)}"><span>${esc(t)}</span><span class="muted">${p}</span></button>`).join('')}<div class="small muted" style="margin-top:6px">${modal ? 'Check the grammar around it after replacing.' : ''}</div>`;
  document.body.appendChild(popEl);
  popEl.style.left = Math.max(8, Math.min(innerWidth - popEl.offsetWidth - 8, rect.left)) + 'px'; popEl.style.top = Math.min(innerHeight - popEl.offsetHeight - 8, rect.bottom + 6) + 'px';
  popEl.addEventListener('click', ev => { const b = ev.target.closest('[data-t]'); if (!b) return; let t = b.dataset.t; if (/^[A-Z]/.test(hit.word)) t = t[0].toUpperCase() + t.slice(1); replaceRange(hit.r, t); closePop(); onEdit(); runEstimative(); });
});
function caretAt(e) { const r = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null; if (r) return [r.startContainer, r.startOffset]; const p = document.caretPositionFromPoint(e.clientX, e.clientY); return [p.offsetNode, p.offset]; }

/* ================================================================
   Script mode: A/V scripts, run time, teleprompter
   ================================================================ */
const SCRIPT_CUE = /^\s*(VISUALS?|B-ROLL|GFX|SFX|MUSIC|ON SCREEN|CUT TO|LOWER THIRD|SUPER|MAP|CHART|VO|SOT|NAT SOUND)\s*:/i;
const isScript = d => !!(d && d.layout && d.layout.script && d.layout.script.on);
function narrationOf(el) { return el.textContent.replace(/\[[^\]]*\]/g, ' ').replace(/\s+/g, ' ').trim(); }
function scriptUnits() {
  const units = [];
  [...editor.children].forEach(el => {
    if (el.matches('figure.av')) { $$('tbody tr', el).forEach(tr => { const cells = [...tr.cells]; if (!cells.length) return; const nar = cells[cells.length - 1]; units.push({ el: nar, row: tr, vis: cells.length > 1 ? cells[0].textContent.trim() : '', text: narrationOf(nar) }); }); return; }
    if (/^H[1-3]$/.test(el.nodeName)) { units.push({ el, head: true, text: '' }); return; }
    if (el.matches('p,blockquote,ul,ol') && !SCRIPT_CUE.test(el.textContent)) units.push({ el, text: narrationOf(el) });
    else if (el.matches('p')) units.push({ el, cue: true, vis: el.textContent.trim(), text: '' });
  });
  return units;
}
const mmss = s => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(ss).padStart(2, '0'); };
function updateScript() {
  const d = curDoc(), on = isScript(d) && !homeOn && !boardOn && !planOn && !draftsOn;
  document.body.classList.toggle('script-on', !!(isScript(d)));
  $('#scriptBar').classList.toggle('hidden', !isScript(d));
  $$('[data-cp-tc]', editor).forEach(x => x.removeAttribute('data-cp-tc'));
  if (!isScript(d)) return;
  const wpm = d.layout.script.wpm || 150; let t = 0, words = 0;
  scriptUnits().forEach(u => { if (u.head) return; const n = wc(u.text); if (n || (u.row && u.vis)) u.el.setAttribute('data-cp-tc', mmss(t)); t += n / wpm * 60; words += n; });
  $('#scRun').textContent = mmss(t); $('#scWords').textContent = words.toLocaleString();
  $('#scWpm').value = wpm;
}
const updateScriptSoon = debounce(updateScript, 400);
editor.addEventListener('input', updateScriptSoon);
$('#scWpm').addEventListener('change', e => { const d = curDoc(); d.layout.script.wpm = Math.max(60, Math.min(260, parseInt(e.target.value, 10) || 150)); markDirty(); updateScript(); });
$('#scAV').addEventListener('click', () => { insertBlocksAtCursor(`<figure class="tbl av"><table><thead><tr><th>Visuals</th><th>Narration</th></tr></thead><tbody>${'<tr><td><br></td><td><br></td></tr>'.repeat(3)}</tbody></table></figure><p><br></p>`); onEdit(); updateScript(); const td = $$('figure.av td', editor).find(c => !c.textContent.trim()); if (td) caretInto(td); });
$('#scCopy').addEventListener('click', async () => { const txt = scriptUnits().filter(u => u.text).map(u => u.text).join('\n\n'); try { await navigator.clipboard.writeText(txt); toast(`Copied the narration (${wc(txt).toLocaleString()} words), without visuals or cues.`); } catch (e) { download(fileSafe(curDoc().title) + ' - narration.txt', txt, 'text/plain'); } });
$('#scPrompt').addEventListener('click', () => openPrompter());
/* teleprompter */
let TP = null;
function openPrompter() {
  const d = curDoc(); if (!d) return; syncEditor();
  const units = scriptUnits(); const showCues = PREFS.tpCues !== false;
  const html = units.map(u => u.head ? `<h3>${esc(u.el.textContent.trim())}</h3>` : u.cue ? (showCues ? `<p class="tp-cue">${esc(u.vis)}</p>` : '') : `${showCues && u.vis ? `<p class="tp-cue">${esc(u.vis)}</p>` : ''}${u.text ? `<p>${esc(u.text)}</p>` : ''}`).join('');
  const words = units.reduce((n, u) => n + wc(u.text), 0);
  $('#tpText').innerHTML = html || '<p>Nothing to read yet.</p>';
  TP = { wpm: d.layout.script?.wpm || 150, words, playing: false, y: 0, last: 0, size: PREFS.tpSize || 44, mirror: !!PREFS.tpMirror };
  $('#tpCues').checked = showCues; tpApply(); $('#tp').classList.remove('hidden'); document.body.classList.add('tp-on'); $('#tpScroll').scrollTop = 0; TP.y = 0; tpStatus(); $('#tpPlay').focus();
}
function tpApply() { $('#tpText').style.fontSize = TP.size + 'px'; $('#tpScroll').classList.toggle('mirror', TP.mirror); $('#tpWpm').textContent = TP.wpm; }
function tpStatus() { const sc = $('#tpScroll'), max = sc.scrollHeight - sc.clientHeight, f = max > 0 ? sc.scrollTop / max : 0; $('#tpBar').style.width = (f * 100) + '%'; $('#tpLeft').textContent = mmss(TP.words * (1 - f) / TP.wpm * 60) + ' left'; $('#tpPlay').textContent = TP.playing ? 'Pause' : 'Play'; }
function tpTick(ts) {
  if (!TP || !TP.playing) return; const sc = $('#tpScroll');
  const dt = TP.last ? (ts - TP.last) / 1000 : 0; TP.last = ts;
  const max = sc.scrollHeight - sc.clientHeight, secs = TP.words / TP.wpm * 60;
  TP.y = Math.min(max, (TP.y || sc.scrollTop) + (secs > 0 ? max / secs * dt : 0)); sc.scrollTop = TP.y;
  tpStatus(); if (TP.y >= max) { TP.playing = false; tpStatus(); return; } requestAnimationFrame(tpTick);
}
function tpToggle() { TP.playing = !TP.playing; TP.last = 0; TP.y = $('#tpScroll').scrollTop; tpStatus(); if (TP.playing) requestAnimationFrame(tpTick); }
function closePrompter() { if (TP) TP.playing = false; $('#tp').classList.add('hidden'); document.body.classList.remove('tp-on'); }
$('#tpPlay').addEventListener('click', tpToggle);
$('#tpClose').addEventListener('click', closePrompter);
$('#tpFaster').addEventListener('click', () => { TP.wpm = Math.min(260, TP.wpm + 10); tpApply(); tpStatus(); });
$('#tpSlower').addEventListener('click', () => { TP.wpm = Math.max(60, TP.wpm - 10); tpApply(); tpStatus(); });
$('#tpBigger').addEventListener('click', () => { TP.size = Math.min(96, TP.size + 4); PREFS.tpSize = TP.size; savePrefs(); tpApply(); });
$('#tpSmaller').addEventListener('click', () => { TP.size = Math.max(24, TP.size - 4); PREFS.tpSize = TP.size; savePrefs(); tpApply(); });
$('#tpMirror').addEventListener('click', () => { TP.mirror = !TP.mirror; PREFS.tpMirror = TP.mirror; savePrefs(); tpApply(); });
$('#tpCues').addEventListener('change', e => { PREFS.tpCues = e.target.checked; savePrefs(); const y = $('#tpScroll').scrollTop; openPrompter(); $('#tpScroll').scrollTop = y; });
$('#tpScroll').addEventListener('scroll', () => { if (TP && !TP.playing) { TP.y = $('#tpScroll').scrollTop; tpStatus(); } });
document.addEventListener('keydown', e => {
  if (!TP || $('#tp').classList.contains('hidden')) return;
  if (e.key === ' ') { e.preventDefault(); tpToggle(); }
  else if (e.key === 'Escape') { e.preventDefault(); closePrompter(); }
  else if (e.key === 'ArrowUp' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $('#tpFaster').click(); }
  else if (e.key === 'ArrowDown' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $('#tpSlower').click(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); $('#tpScroll').scrollTop -= 60; TP.y = $('#tpScroll').scrollTop; }
  else if (e.key === 'ArrowDown') { e.preventDefault(); $('#tpScroll').scrollTop += 60; TP.y = $('#tpScroll').scrollTop; }
}, true);

/* ================================================================
   GitHub backup (Git Data API, so large projects work)
   ================================================================ */
let ghTokenMem = '';
const GH_TOKEN_KEY = 'anabasis.ghToken';
function ghCfg() { PREFS.gh = PREFS.gh || { repo: '', branch: 'main', folder: 'anabasis', auto: false, paths: {}, remember: false }; PREFS.gh.paths = PREFS.gh.paths || {}; return PREFS.gh; }
function ghToken() { return ghTokenMem || (ghCfg().remember ? (localStorage.getItem(GH_TOKEN_KEY) || '') : ''); }
function ghPath() { const c = ghCfg(); return c.paths[P.id] || `${(c.folder || 'anabasis').replace(/^\/+|\/+$/g, '')}/${fileSafe(P.title || 'project').replace(/\s+/g, '-')}-${P.id.slice(-6)}.json`; }
function ghErr(status, body) {
  let m = ''; try { m = JSON.parse(body).message || ''; } catch (e) {}
  if (status === 401) return 'GitHub didn’t accept the token. Check it, or make a new one.';
  if (status === 403) return /rate limit/i.test(m) ? 'GitHub’s rate limit was hit. Try again in a few minutes.' : 'The token can’t write to that repository. Give it “Contents: Read and write” for this repo.';
  if (status === 404) return 'Repository not found. Check owner/name, and that the token has access to it.';
  if (status === 409) return 'empty';
  return `GitHub said: ${m || 'error ' + status}`;
}
async function gh(path, opt = {}) {
  const tok = ghToken(); if (!tok) throw new Error('Add a GitHub token first.');
  const r = await fetch('https://api.github.com' + path, { method: opt.method || 'GET', headers: Object.assign({ Authorization: 'Bearer ' + tok, Accept: opt.raw ? 'application/vnd.github.raw' : 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' }, opt.body ? { 'Content-Type': 'application/json' } : {}), body: opt.body ? JSON.stringify(opt.body) : undefined });
  if (!r.ok) { const e = new Error(ghErr(r.status, await r.text())); e.status = r.status; throw e; }
  return opt.raw ? r.text() : r.status === 204 ? null : r.json();
}
const ghRepo = () => { const c = ghCfg(), m = (c.repo || '').trim().replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '').match(/^([\w.-]+)\/([\w.-]+)$/); if (!m) throw new Error('Enter the repository as owner/name, e.g. gmrapp/anabasis-backups.'); return `/repos/${m[1]}/${m[2]}`; };
async function ghTest() {
  const repo = await gh(ghRepo());
  const warn = repo.private ? '' : ' Warning: this repository is public, so anyone can read your backups. Use a private repository.';
  if (repo.permissions && !repo.permissions.push) throw new Error('The token can read this repository but not write to it.');
  return `Connected to ${repo.full_name} (${repo.private ? 'private' : 'public'}).${warn}`;
}
let ghBusy = false;
async function ghBackup(manual = true) {
  if (ghBusy) return; ghBusy = true; const c = ghCfg(), R = ghRepo(), path = ghPath(), branch = (c.branch || 'main').trim();
  try {
    if (manual) ghStatus('Backing up…');
    const text = await projectFileText(), b64 = bytesToB64(new TextEncoder().encode(text));
    const words = P.docs.reduce((n, d) => n + docWords(d), 0);
    const message = `Back up “${LOCK ? 'locked project' : P.title}”: ${words.toLocaleString()} words, ${P.docs.length} document${P.docs.length === 1 ? '' : 's'}, ${P.notes.length} notes`;
    let ref = null;
    try { ref = await gh(`${R}/git/ref/heads/${encodeURIComponent(branch)}`); } catch (e) { if (e.status !== 404 && e.status !== 409) throw e; }
    if (!ref) { // empty repository or new branch: the contents API can create the first commit
      await gh(`${R}/contents/${path.split('/').map(encodeURIComponent).join('/')}`, { method: 'PUT', body: { message, content: b64, branch } });
    } else {
      const head = await gh(`${R}/git/commits/${ref.object.sha}`);
      const blob = await gh(`${R}/git/blobs`, { method: 'POST', body: { content: b64, encoding: 'base64' } });
      const tree = await gh(`${R}/git/trees`, { method: 'POST', body: { base_tree: head.tree.sha, tree: [{ path, mode: '100644', type: 'blob', sha: blob.sha }] } });
      const commit = await gh(`${R}/git/commits`, { method: 'POST', body: { message, tree: tree.sha, parents: [ref.object.sha] } });
      await gh(`${R}/git/refs/heads/${encodeURIComponent(branch)}`, { method: 'PATCH', body: { sha: commit.sha } });
    }
    c.paths[P.id] = path; c.last = { at: nowISO(), pid: P.id }; savePrefs();
    ghStatus(`Backed up ${relTime(nowISO())} to ${c.repo} → ${path}`);
    if (manual) toast('Backed up to GitHub.'); else $('#saveState') && ($('#saveState').title = 'Last GitHub backup: ' + new Date().toLocaleTimeString());
  } catch (e) { ghStatus(e.message, true); if (manual) toast(e.message); else toast('GitHub backup failed: ' + e.message); throw e; }
  finally { ghBusy = false; }
}
let ghLastAuto = 0;
function ghAfterSave(fromAutosave) {
  const c = ghCfg(); if (!c.auto || !c.repo || !ghToken()) return;
  const gap = fromAutosave ? 10 * 60e3 : 30e3; if (Date.now() - ghLastAuto < gap) return;
  ghLastAuto = Date.now(); ghBackup(false).catch(() => {});
}
function ghStatus(msg, bad) { const s = $('#ghStatus'); if (s) { s.textContent = msg; s.classList.toggle('bad', !!bad); } }
function openGitHub() {
  const c = ghCfg();
  $('#ghRepo').value = c.repo || ''; $('#ghBranch').value = c.branch || 'main'; $('#ghFolder').value = c.folder || 'anabasis';
  $('#ghToken').value = ghToken(); $('#ghRemember').checked = !!c.remember; $('#ghAuto').checked = !!c.auto;
  $('#ghPath').textContent = ghPath(); ghStatus(c.last && c.last.pid === P.id ? `Last backup of this project: ${relTime(c.last.at)}` : 'Not backed up from this browser yet.');
  $('#ghHist').innerHTML = ''; $('#ghDlg').showModal();
}
function ghSaveForm() {
  const c = ghCfg(); c.repo = $('#ghRepo').value.trim(); c.branch = $('#ghBranch').value.trim() || 'main'; c.folder = $('#ghFolder').value.trim() || 'anabasis'; c.auto = $('#ghAuto').checked; c.remember = $('#ghRemember').checked;
  ghTokenMem = $('#ghToken').value.trim();
  if (c.remember && ghTokenMem) localStorage.setItem(GH_TOKEN_KEY, ghTokenMem); else localStorage.removeItem(GH_TOKEN_KEY);
  savePrefs(); $('#ghPath').textContent = ghPath();
}
['#ghRepo', '#ghBranch', '#ghFolder', '#ghToken'].forEach(s => $(s).addEventListener('change', ghSaveForm));
['#ghRemember', '#ghAuto'].forEach(s => $(s).addEventListener('change', ghSaveForm));
$('#ghTest').addEventListener('click', async () => { ghSaveForm(); ghStatus('Checking…'); try { ghStatus(await ghTest()); } catch (e) { ghStatus(e.message, true); } });
$('#ghNow').addEventListener('click', async () => { ghSaveForm(); try { await ghBackup(true); } catch (e) {} });
$('#ghHistory').addEventListener('click', async () => {
  ghSaveForm(); ghStatus('Loading history…');
  try {
    const list = await gh(`${ghRepo()}/commits?path=${encodeURIComponent(ghPath())}&sha=${encodeURIComponent(ghCfg().branch || 'main')}&per_page=30`);
    ghStatus(list.length ? `${list.length} backup${list.length === 1 ? '' : 's'} of this project:` : 'No backups of this project yet.');
    $('#ghHist').innerHTML = list.map(c => `<li><span><b>${new Date(c.commit.author.date).toLocaleString([], { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</b> <span class="muted small">${esc(c.commit.message.replace(/^Back up /, ''))}</span></span><button class="small" data-sha="${c.sha}">Open</button></li>`).join('');
  } catch (e) { ghStatus(e.message, true); }
});
$('#ghHist').addEventListener('click', async e => {
  const b = e.target.closest('[data-sha]'); if (!b) return;
  if (!(await ask('Open this backup?', 'It replaces the project open in this browser. Save first if you want to keep the current one.', 'Open backup'))) { $('#ghDlg').open || $('#ghDlg').showModal(); return; }
  try { const text = await gh(`${ghRepo()}/contents/${ghPath().split('/').map(encodeURIComponent).join('/')}?ref=${b.dataset.sha}`, { raw: true }); $('#ghDlg').open && $('#ghDlg').close(); dirtyFile = false; await loadProjectText(text, null, ghPath().split('/').pop()); toast('Opened the backup. Save it to a file to keep it.'); }
  catch (err) { ghStatus(err.message, true); }
});
$('#ghClose').addEventListener('click', () => { ghSaveForm(); $('#ghDlg').close(); });

/* ================================================================
   Map layers: provinces, rivers & lakes, scale bar, locator inset
   ================================================================ */
let GEO2 = null;
function geo2() {
  geo();
  if (!GEO2) {
    const rewind = fc => { fc.features.forEach(f => { const g = f.geometry; if (!g) return; const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []; polys.forEach(p => { if (d3.geoArea({ type: 'Polygon', coordinates: p }) > 2 * Math.PI) p.forEach(r => r.reverse()); }); }); return fc; };
    const a = JSON.parse($('#data-admin1').textContent), r = JSON.parse($('#data-rivers').textContent);
    const prov = rewind(topojson.feature(a, a.objects.a));
    GEO2 = { prov, provMesh: topojson.mesh(a, a.objects.a, (x, y) => x !== y), byKey: prov.features.reduce((o, f) => { const k = f.properties.c + '|' + f.properties.n, polys = g => g.type === 'Polygon' ? [g.coordinates] : g.coordinates; if (o[k]) o[k] = { type: 'Feature', properties: f.properties, geometry: { type: 'MultiPolygon', coordinates: [...polys(o[k].geometry), ...polys(f.geometry)] } }; else o[k] = f; return o; }, {}), rivers: topojson.feature(r, r.objects.r), lakes: rewind(topojson.feature(r, r.objects.l)), countries: new Set(prov.features.map(f => f.properties.c)) };
  }
  return GEO2;
}
function mapLayersSVG(spec, proj, path, used, keyOf, tint) {
  if (!spec.provinces && !spec.rivers && !Object.keys(spec.regions || {}).length) return '';
  const G = geo2(); let s = '';
  Object.entries(spec.regions || {}).forEach(([k, kid]) => { const f = G.byKey[k]; if (!f) return; const kk = keyOf(spec, kid); used.add(kk.id); const d = path(f); if (d) s += `<path d="${d}" fill="${kk.hatch ? `url(#hp-${kk.id})` : tint(kk.color, .45)}" data-r="${esc(k)}"/>`; });
  if (spec.rivers) {
    s += `<path d="${path(G.lakes) || ''}" fill="#dde7ee" stroke="#8fa9bd" stroke-width=".5"/>`;
    G.rivers.features.forEach(f => { const d = path(f); if (d) s += `<path d="${d}" fill="none" stroke="#7fa7c4" stroke-width="${f.properties.r <= 3 ? 1.5 : f.properties.r <= 5 ? 1.1 : .8}" stroke-linecap="round" stroke-linejoin="round"/>`; });
  }
  if (spec.provinces) s += `<path d="${path(G.provMesh) || ''}" fill="none" stroke="#aaa392" stroke-width=".6" stroke-dasharray="2.5 2"/>`;
  return s;
}
function riverLabelsSVG(spec, proj) {
  if (!spec.rivers || !spec.riverNames) return '';
  const G = geo2(), { w, h } = spec; let s = ''; const done = new Set();
  G.rivers.features.forEach(f => {
    const n = f.properties.n; if (!n || done.has(n)) return;
    const lines = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.type === 'MultiLineString' ? f.geometry.coordinates : [];
    let best = null;
    lines.forEach(L => { const pts = L.map(c => proj(c)).filter(p => p && p[0] > 20 && p[0] < w - 20 && p[1] > 20 && p[1] < h - 20); let len = 0; for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); if (pts.length > 2 && len > 110 && (!best || len > best.len)) best = { pts, len }; });
    if (!best) return; done.add(n);
    const i = Math.floor(best.pts.length / 2), a = best.pts[Math.max(0, i - 1)], b = best.pts[Math.min(best.pts.length - 1, i + 1)];
    let ang = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI; if (ang > 90) ang -= 180; if (ang < -90) ang += 180;
    const [x, y] = best.pts[i];
    s += `<text x="${x.toFixed(1)}" y="${(y - 4).toFixed(1)}" transform="rotate(${ang.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)})" text-anchor="middle" font-size="11" font-style="italic" fill="#3f6f93" paint-order="stroke" stroke="#f3f1ea" stroke-width="3" stroke-linejoin="round">${esc(n)}</text>`;
  });
  return s;
}
function scaleBarSVG(spec, proj) {
  if (spec.scaleBar === false || spec.view.scale < 330) return '';
  const { w, h } = spec, y = h - 30, x1 = w - 190, x2 = w - 40;
  const a = proj.invert([x1, y]), b = proj.invert([x2, y]); if (!a || !b) return '';
  const km = d3.geoDistance(a, b) * 6371; if (!isFinite(km) || km <= 0) return '';
  const nice = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000].filter(n => n <= km).pop() || 1;
  const px = (x2 - x1) * nice / km, mi = Math.round(nice * 0.621371 * 10) / 10;
  const X = x2 - px;
  return `<g font-size="10.5" fill="#1d2733"><rect x="${X - 8}" y="${y - 20}" width="${px + 16}" height="31" rx="3" fill="#fff" fill-opacity=".85"/><rect x="${X}" y="${y - 4}" width="${px / 2}" height="4" fill="#1d2733"/><rect x="${X + px / 2}" y="${y - 4}" width="${px / 2}" height="4" fill="#fff" stroke="#1d2733" stroke-width=".8"/><text x="${X}" y="${y - 8}" text-anchor="start">0</text><text x="${X + px}" y="${y - 8}" text-anchor="end">${nice.toLocaleString()} km (${mi.toLocaleString()} mi)</text></g>`;
}
function locatorSVG(spec, proj) {
  if (spec.locator === false || spec.view.scale < 700) return '';
  const g = geo(), { w, h } = spec, iw = 170, ih = 112, ix = w - iw - 10, iy = 10;
  const [lon, lat] = spec.view.center;
  const ip = d3.geoAzimuthalEqualArea().rotate([-lon, -lat]).clipAngle(90).scale(spec.view.scale / 9).translate([ix + iw / 2, iy + ih / 2]);
  const ipath = d3.geoPath(ip);
  const edge = []; const N = 12;
  for (let i = 0; i <= N; i++) edge.push([w * i / N, 0]); for (let i = 1; i <= N; i++) edge.push([w, h * i / N]); for (let i = N - 1; i >= 0; i--) edge.push([w * i / N, h]); for (let i = N - 1; i > 0; i--) edge.push([0, h * i / N]);
  const ring = edge.map(p => proj.invert(p)).filter(Boolean).map(ll => ip(ll)).filter(Boolean);
  if (ring.length < 4) return '';
  return `<g><clipPath id="lc"><rect x="${ix}" y="${iy}" width="${iw}" height="${ih}"/></clipPath><rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="#dde7ee" stroke="#8c9aa5"/><g clip-path="url(#lc)"><path d="${ipath(g.fc) || ''}" fill="#efece3" stroke="#b9b3a3" stroke-width=".4"/><path d="M${ring.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L')}Z" fill="#c0392b" fill-opacity=".12" stroke="#c0392b" stroke-width="1.5"/></g></g>`;
}

/* ================================================================
   Chart extras: events and periods, area charts, small multiples
   ================================================================ */
function parseEvents(text, labels) {
  const idx = v => { v = String(v).trim(); let i = labels.findIndex(l => String(l).trim().toLowerCase() === v.toLowerCase()); if (i >= 0) return i; const n = parseFloat(v), nums = labels.map(l => parseFloat(l)); if (!isNaN(n) && nums.every(x => !isNaN(x))) { for (let k = 0; k < nums.length - 1; k++) if (n >= nums[k] && n <= nums[k + 1]) return k + (n - nums[k]) / ((nums[k + 1] - nums[k]) || 1); } return null; };
  return String(text || '').split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const [when, ...rest] = l.split('|'); const label = rest.join('|').trim();
    const r = when.split(/\s*(?:–|—|\bto\b|-(?=\s*\d|\s*[A-Z]))\s*/);
    const a = idx(r[0]), b = r[1] ? idx(r[1]) : null;
    return a === null ? null : { a, b: b !== null && b > a ? b : null, label };
  }).filter(Boolean);
}
function eventsPlugin(spec, labels) {
  const evs = parseEvents(spec.events, labels);
  return { id: 'events', beforeDatasetsDraw(ch) {
      if (!evs.length || ch.options.indexAxis === 'y') return; const x = ch.scales.x, top = ch.chartArea.top, bot = ch.chartArea.bottom, g = ch.ctx;
      const px = v => { const f = Math.floor(v), t = v - f; const p0 = x.getPixelForValue(f), p1 = x.getPixelForValue(Math.min(labels.length - 1, f + 1)); return p0 + (p1 - p0) * t; };
      g.save(); evs.filter(e => e.b !== null).forEach(e => { g.fillStyle = 'rgba(138,143,152,.14)'; g.fillRect(px(e.a), top, px(e.b) - px(e.a), bot - top); }); g.restore();
    }, afterDatasetsDraw(ch) {
      if (!evs.length || ch.options.indexAxis === 'y') return; const x = ch.scales.x, top = ch.chartArea.top, bot = ch.chartArea.bottom, g = ch.ctx;
      const px = v => { const f = Math.floor(v), t = v - f; const p0 = x.getPixelForValue(f), p1 = x.getPixelForValue(Math.min(labels.length - 1, f + 1)); return p0 + (p1 - p0) * t; };
      g.save(); g.font = `600 11.5px ${VIZ.font}`; g.textBaseline = 'top'; const placed = [];
      evs.forEach(e => {
        const xa = px(e.a), xb = e.b !== null ? px(e.b) : xa;
        if (e.b === null) { g.strokeStyle = '#52514e'; g.setLineDash([4, 3]); g.lineWidth = 1.2; g.beginPath(); g.moveTo(xa, top); g.lineTo(xa, bot); g.stroke(); g.setLineDash([]); }
        if (!e.label) return; const tw = g.measureText(e.label).width; let tx = e.b !== null ? (xa + xb) / 2 - tw / 2 : xa + 5; if (tx + tw > ch.chartArea.right) tx = (e.b !== null ? xb : xa) - tw - 5;
        let ty = top - 17; while (placed.some(p => ty < p.y + 15 && ty + 15 > p.y && tx < p.x + p.w + 6 && tx + tw + 6 > p.x)) ty += 15; placed.push({ x: tx, y: ty, w: tw });
        g.fillStyle = 'rgba(255,255,255,.85)'; g.fillRect(tx - 2, ty - 1, tw + 4, 15); g.fillStyle = VIZ.ink; g.fillText(e.label, tx, ty);
      }); g.restore();
    } };
}
async function multiplesPNG(spec, data, scale = 2) {
  useLib('lib-chart');
  const [W, H] = CH_SIZE[spec.aspect] || CH_SIZE.wide, series = data.series.slice(0, 9), n = series.length, cols = Math.min(3, n), rows = Math.ceil(n / cols);
  const cw = Math.floor(W / cols), chh = Math.floor(H / rows);
  const max = Math.max(...series.flatMap(s => s.values.filter(v => v != null))), min = Math.min(0, ...series.flatMap(s => s.values.filter(v => v != null)));
  const out = document.createElement('canvas'); out.width = W * scale; out.height = H * scale; const g = out.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, out.width, out.height);
  for (let i = 0; i < n; i++) {
    const holder = document.createElement('div'); holder.style.cssText = `position:fixed;left:-10000px;top:0;width:${cw}px;height:${chh}px`; const c = document.createElement('canvas'); c.width = cw; c.height = chh; holder.append(c); document.body.append(holder);
    const sub = Object.assign({}, spec, { kind: 'area' }); const cfg = chartConfig(sub, { labels: data.labels, series: [series[i]] });
    cfg.data.datasets[0].borderColor = cfg.data.datasets[0].backgroundColor = SERIES[i % SERIES.length]; cfg.data.datasets[0].fill = { target: 'origin', above: SERIES[i % SERIES.length] + '22' };
    cfg.options.devicePixelRatio = scale; cfg.options.plugins.legend.display = false; const evl = parseEvents(spec.events, data.labels).some(e => e.label); cfg.options.plugins.title = { display: true, text: series[i].name, align: 'start', color: VIZ.ink, font: { family: VIZ.font, size: 13, weight: '700' }, padding: { bottom: evl && i < cols ? 24 : 4 } };
    const p10 = 10 ** Math.floor(Math.log10(Math.abs(max) || 1)); cfg.options.scales.y.min = min; cfg.options.scales.y.max = Math.ceil(max / p10 * 2) / 2 * p10; cfg.options.scales.y.title.display = false; cfg.options.scales.x.ticks.maxTicksLimit = 4; cfg.options.scales.y.ticks.maxTicksLimit = 4; cfg.options.layout.padding = { top: 6, right: 12, bottom: 4, left: 4 }; if (i > 0) cfg.plugins = cfg.plugins.map(p => p.id === 'events' ? eventsPlugin(Object.assign({}, spec, { events: (spec.events || '').split('\n').map(l => l.split('|')[0]).join('\n') }), data.labels) : p);
    const ch = new Chart(c, cfg); ch.draw(); g.drawImage(c, (i % cols) * cw * scale, Math.floor(i / cols) * chh * scale); ch.destroy(); holder.remove();
  }
  return { data: out.toDataURL('image/png'), w: W * scale, h: H * scale };
}

/* ================================================================
   Corroboration: paragraphs resting on one source, or only on weak ones
   ================================================================ */
const srcShort = s => { if (!s) return 'Unknown source'; const l = sourceLabel(s); return l.who ? l.who + (l.yr ? ' ' + l.yr : '') : (l.title.length > 40 ? l.title.slice(0, 38) + '…' : l.title); };
const RATE_LOW = r => !!r && (/^[DE]/.test(r) || /[45]$/.test(r));
function corroboration() {
  const d = curDoc(); if (!d) return { items: [], weight: [] };
  const byId = Object.fromEntries(P.sources.map(s => [s.id, s]));
  const items = [], count = {}; let total = 0;
  $$(':scope > p, :scope > blockquote, :scope > ul > li, :scope > ol > li', editor).forEach(el => {
    const marks = $$('.cite', el); if (!marks.length) return;
    const ids = [...new Set(marks.flatMap(m => markerItems(m).map(it => it.id)).filter(Boolean))];
    marks.forEach(m => markerItems(m).forEach(it => { count[it.id] = (count[it.id] || 0) + 1; total++; }));
    const rated = ids.map(id => (byId[id] && byId[id].osint && byId[id].osint.rating) || '');
    const snip = blockSnippet(el, 70);
    if (ids.length && rated.every(RATE_LOW)) items.push({ el, sev: 2, msg: `Rests only on low-rated source${ids.length > 1 ? 's' : ''} (${rated.join(', ')})`, snip });
    else if (ids.length === 1 && wordsIn(el) >= (PREFS.corrMin || 20)) { const s = byId[ids[0]]; items.push({ el, sev: 1, msg: `One source: ${srcShort(s)}${rated[0] ? ' (' + rated[0] + ')' : ''}`, snip }); }
  });
  const weight = Object.entries(count).map(([id, n]) => ({ id, n, share: n / Math.max(1, total), s: byId[id] })).sort((a, b) => b.n - a.n);
  return { items, weight, total };
}
function renderCorroboration() {
  if (!$('#corList') || !curDoc()) return;
  const on = PREFS.corrOn ?? ['brief', 'whitepaper', 'article', 'series', 'book', 'narrative'].includes((P.goal || {}).kind);
  $('#corToggle').checked = !!on;
  if (!on) { $('#corCount').textContent = ''; $('#corList').innerHTML = '<li class="muted small none">Turn on to flag paragraphs that rest on a single source, or only on sources rated D–E or 4–5, and to see which sources carry the piece.</li>'; return; }
  const c = corroboration(); COR = c;
  const weak = c.items.filter(i => i.sev === 2), single = c.items.filter(i => i.sev === 1);
  $('#corCount').textContent = weak.length || '';
  const top = c.weight.slice(0, 5);
  const lean = top[0] && top[0].share > .35 && c.total >= 6;
  $('#corList').innerHTML = (c.total ? `<li class="cor-weight"><span class="small muted">Citations by source (${c.total} in this document)</span>${top.map(x => `<div class="cor-bar"><span class="t">${esc(srcShort(x.s))}${x.s && x.s.osint && x.s.osint.rating ? ` <span class="muted">${esc(x.s.osint.rating)}</span>` : ''}</span><i style="width:${Math.round(x.share * 100)}%"></i><span class="n">${Math.round(x.share * 100)}%</span></div>`).join('')}${lean ? `<div class="small cor-lean">More than a third of the citations go to one source. Can anything else back it up?</div>` : ''}</li>` : '') +
    weak.map((x, i) => `<li data-cor="${c.items.indexOf(x)}"><span><b class="fk fk-cite">weak</b> ${esc(x.msg)}<br><span class="muted small">${esc(x.snip)}</span></span></li>`).join('') +
    (single.length ? `<li class="cor-single"><details><summary>${single.length} paragraph${single.length === 1 ? '' : 's'} with one source</summary><ul class="outline">${single.map(x => `<li data-cor="${c.items.indexOf(x)}"><span>${esc(x.msg)}<br><span class="muted small">${esc(x.snip)}</span></span></li>`).join('')}</ul></details></li>` : '') +
    (!c.total ? '<li class="muted small none">No citations in this document yet.</li>' : !c.items.length ? '<li class="muted small none">Every cited paragraph has more than one source, and none rests only on low-rated ones.</li>' : '');
}
let COR = { items: [] };
$('#corList').addEventListener('click', e => { const li = e.target.closest('[data-cor]'); if (!li) return; const it = COR.items[+li.dataset.cor]; if (it) { it.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); it.el.classList.remove('hm-flash'); void it.el.offsetWidth; it.el.classList.add('hm-flash'); } });
$('#corToggle').addEventListener('change', e => { PREFS.corrOn = e.target.checked; savePrefs(); renderCorroboration(); });
editor.addEventListener('input', debounce(() => { if (!homeOn && !boardOn && !planOn) renderCorroboration(); }, 1000));

/* ================================================================
   House style
   ================================================================ */
const HS_DEFAULT = () => ({ numbers: 'off', percent: 'off', us: 'off', serial: 'off', dates: 'off', dash: 'off', quotes: true, ellipsis: 'off', doubleSpace: true, prefer: 'Kyiv = Kiev\nKharkiv = Kharkov\nOdesa = Odessa\nLuhansk = Lugansk\nMykolaiv = Nikolaev, Nikolayev\nZaporizhzhia = Zaporozhye, Zaporizhia\nChernihiv = Chernigov\nLviv = Lvov, Lwow\nBelarus = Byelorussia\nUkraine = the Ukraine\nDnipro = Dnepr' });
function hsCfg() { P.house = Object.assign(HS_DEFAULT(), P.house || {}); return P.house; }
const NUMW = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'], TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
const numWord = n => n < 20 ? NUMW[n] : n < 100 ? TENS[Math.floor(n / 10)] + (n % 10 ? '-' + NUMW[n % 10] : '') : n === 100 ? 'one hundred' : String(n);
const HS_MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December';
function hsRules() {
  const c = hsCfg(), R = [];
  const add = (id, label, re, fix, test) => R.push({ id, label, re, fix, test });
  (c.prefer || '').split('\n').forEach(line => { const m = line.split('='); if (m.length < 2) return; const want = m[0].trim(); m[1].split(',').map(s => s.trim()).filter(Boolean).forEach(avoid => { add('prefer', `“${avoid}” → “${want}”`, new RegExp(`(?<![\\p{L}\\p{N}])${escRe(avoid)}(?![\\p{L}\\p{N}])${/^the /i.test(avoid) ? '(?!\\s+\\p{Ll})' : ''}`, 'gu'), mt => (mt[0] === mt[0].toUpperCase() && want[0] !== want[0].toUpperCase() ? capFirst(want) : want)); }); });
  if (c.numbers !== 'off') { const max = c.numbers === 'chicago' ? 100 : 9; add('numbers', `Spell out numbers up to ${max === 9 ? 'nine' : 'one hundred'}`, /(?<![\d$£€.,:/#-])\b(\d{1,3})\b(?![\d.,:%/°]|\s?(?:%|percent|km|mi|kg|mm|cm|m\b|ft|in\b|lb|mph|kph|am|pm|a\.m\.|p\.m\.|BCE|CE|AD|BC))/g, mt => numWord(+mt[1]), (mt, text) => { const n = +mt[1]; if (n > max || n === 0 && max === 9) return false; const before = text.slice(Math.max(0, mt.index - 14), mt.index); if (new RegExp(`(?:${HS_MONTHS}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\\.?\\s*$`, 'i').test(before)) return false; if (/(?:Figure|Fig\.|Table|Article|Chapter|Part|No\.|Vol\.|page|p\.|pp\.|Section|§|Map|Chart|Draft|Phase|Level|Category|Day|Grade|Type)\s*$/i.test(before)) return false; if (/^\s*[-–](?=\d)/.test(text.slice(mt.index + mt[0].length))) return false; return true; }); }
  if (c.percent === 'word') add('percent', '“%” → “percent”', /(\d)\s?%/g, mt => mt[1] + ' percent');
  if (c.percent === 'symbol') add('percent', '“percent” → “%”', /(\d)\s(?:percent|per cent)\b/g, mt => mt[1] + '%');
  if (c.us === 'US') add('us', '“U.S.” → “US”', /\bU\.S\.(?![\w])/g, () => 'US');
  if (c.us === 'U.S.') add('us', '“US” → “U.S.”', /\bUS\b(?!\$)/g, () => 'U.S.');
  if (c.serial === 'on') add('serial', 'Serial comma missing', /(\b[\p{L}’'-]+(?: [\p{L}’'-]+){0,2}), ([\p{L}’'-]+(?: [\p{L}’'-]+){0,2}) (and|or) /gu, mt => `${mt[1]}, ${mt[2]}, ${mt[3]} `);
  if (c.serial === 'off-rule') add('serial', 'Serial comma (house style drops it)', /(\b[\p{L}’'-]+(?: [\p{L}’'-]+){0,2}), ([\p{L}’'-]+(?: [\p{L}’'-]+){0,2}), (and|or) /gu, mt => `${mt[1]}, ${mt[2]} ${mt[3]} `);
  if (c.dates === 'us') add('dates', 'Dates as “Month D, YYYY”', new RegExp(`\\b(\\d{1,2}) (${HS_MONTHS}) (\\d{4})\\b`, 'g'), mt => `${mt[2]} ${mt[1]}, ${mt[3]}`);
  if (c.dates === 'intl') add('dates', 'Dates as “D Month YYYY”', new RegExp(`\\b(${HS_MONTHS}) (\\d{1,2}), (\\d{4})\\b`, 'g'), mt => `${mt[2]} ${mt[1]} ${mt[3]}`);
  if (c.dash === 'closed') add('dash', 'Em dash without spaces', /\s+(?:—|--)\s+/g, () => '—');
  if (c.dash === 'spaced') add('dash', 'Em dash with spaces', /(?<=\S)(?:—|--)(?=\S)/g, () => ' — ');
  if (c.quotes) add('quotes', 'Straight quotes → curly', /["']/g, (mt, text) => { const i = mt.index, prev = text[i - 1] || ' '; if (mt[0] === "'") return /[\p{L}\p{N}.,!?;:)\]]/u.test(prev) ? '’' : '‘'; return /[\s([{—–-]/.test(prev) || i === 0 ? '“' : '”'; });
  if (c.ellipsis === 'char') add('ellipsis', 'Ellipsis character', /\.\s?\.\s?\./g, () => '…');
  if (c.ellipsis === 'spaced') add('ellipsis', 'Spaced ellipsis (. . .)', /…|(?<!\.\s)\.\.\.(?!\s\.)/g, () => '. . .');
  if (c.doubleSpace) add('space', 'Double spaces', / {2,}/g, () => ' ');
  return R;
}
let HS = [];
function houseScan() {
  const rules = hsRules(), out = [];
  $$(':scope > p, :scope > blockquote, :scope > blockquote > p, :scope > ul > li, :scope > ol > li, :scope > h1, :scope > h2, :scope > h3, :scope > figure figcaption', editor).forEach(el => {
    if (el.matches('blockquote') && el.querySelector('p')) return;
    const { text, range } = blockMap(el);
    rules.forEach(r => { r.re.lastIndex = 0; let mt; while ((mt = r.re.exec(text))) { if (r.test && !r.test(mt, text)) { if (!mt[0]) r.re.lastIndex++; continue; } const rep = r.fix ? r.fix(mt, text) : null; const rg = range(mt.index, mt.index + mt[0].length); if (rg) out.push({ rule: r, el, r: rg, from: mt[0], to: rep, at: mt.index }); if (!mt[0]) r.re.lastIndex++; } });
  });
  return out;
}
function renderHouse() {
  if (!$('#hsList') || !curDoc()) return;
  HS = houseScan();
  if (window.CSS && CSS.highlights && window.Highlight) { if (HS.length) CSS.highlights.set('cp-style', new Highlight(...HS.map(x => x.r))); else CSS.highlights.delete('cp-style'); }
  $('#hsCount').textContent = HS.length || '';
  const groups = {}; HS.forEach((x, i) => { (groups[x.rule.label] = groups[x.rule.label] || []).push(i); });
  $('#hsList').innerHTML = Object.keys(groups).length ? Object.entries(groups).map(([label, ix]) => `<li><span><b>${esc(label)}</b> <span class="muted">${ix.length}×</span>${ix.length <= 3 ? '<br>' + ix.map(i => `<span class="small muted hs-ex">${esc(HS[i].from.trim() || '␣␣')} → ${esc((HS[i].to || '').trim() || '␣')}</span>`).join(' ') : ''}</span><span class="ol-acts"><button class="small" data-hsall="${esc(label)}">Fix ${ix.length > 1 ? 'all' : ''}</button><button class="small ghost" data-hsgo="${ix[0]}">Show</button></span></li>`).join('') : '<li class="muted small none">Everything follows your house style. Set the rules under House style… above.</li>';
}
$('#hsList').addEventListener('click', e => {
  const a = e.target.closest('[data-hsall]'); if (a) { const items = HS.filter(x => x.rule.label === a.dataset.hsall && x.to !== null); items.slice().reverse().forEach(x => replaceRange(x.r, x.to)); onEdit(); renderHouse(); toast(`Fixed ${items.length}.`); return; }
  const g = e.target.closest('[data-hsgo]'); if (g) { const x = HS[+g.dataset.hsgo]; if (x) { const s = getSelection(); s.removeAllRanges(); s.addRange(x.r); x.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } }
});
editor.addEventListener('input', debounce(() => { if (!homeOn && !boardOn && !planOn) renderHouse(); }, 1100));
function openHouse() {
  const c = hsCfg();
  ['numbers', 'percent', 'us', 'serial', 'dates', 'dash', 'ellipsis'].forEach(k => { $('#hs_' + k).value = c[k]; });
  $('#hs_quotes').checked = !!c.quotes; $('#hs_doubleSpace').checked = !!c.doubleSpace; $('#hs_prefer').value = c.prefer || '';
  $('#hsDlg').showModal();
}
$('#hsSave').addEventListener('click', () => {
  const c = hsCfg(); ['numbers', 'percent', 'us', 'serial', 'dates', 'dash', 'ellipsis'].forEach(k => { c[k] = $('#hs_' + k).value; });
  c.quotes = $('#hs_quotes').checked; c.doubleSpace = $('#hs_doubleSpace').checked; c.prefer = $('#hs_prefer').value;
  markDirty(); $('#hsDlg').close(); renderHouse();
});
$('#hsCancel').addEventListener('click', () => $('#hsDlg').close());
$('#hsReset').addEventListener('click', () => { P.house = HS_DEFAULT(); openHouse(); });
$('#btnHouse').addEventListener('click', openHouse);

/* ================================================================
   Find & replace across documents (and notes)
   ================================================================ */
let FR = { hits: [] };
function frRegex() {
  const q = $('#frFind').value; if (!q) return null;
  let src = $('#frRe').checked ? q : escRe(q); if ($('#frWord').checked) src = `(?<![\\p{L}\\p{N}_])(?:${src})(?![\\p{L}\\p{N}_])`;
  try { return new RegExp(src, 'gu' + ($('#frCase').checked ? '' : 'i')); } catch (e) { $('#frMsg').textContent = 'That pattern isn’t valid: ' + e.message; return null; }
}
function frTextNodes(root) { const out = [], w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentElement.closest('.cite,.fn,.flag,.ix-a,.cmt-pt,nav.lof,nav.abbr') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT }); while (w.nextNode()) out.push(w.currentNode); return out; }
function frScopeDocs() {
  const sc = $('#frScope').value, d = curDoc();
  if (sc === 'doc') return [d];
  if (sc === 'part') return binderOrder().filter(x => (x.partId || '') === (d.partId || ''));
  return binderOrder();
}
function frSearch() {
  syncEditor(); $('#frMsg').textContent = ''; const re = frRegex(); FR = { hits: [], re };
  if (!re) { $('#frResults').innerHTML = ''; return; }
  frScopeDocs().forEach(d => {
    const root = document.createElement('div'); root.innerHTML = d.html;
    frTextNodes(root).forEach((n, ni) => { re.lastIndex = 0; let m; while ((m = re.exec(n.data))) { if (!m[0]) { re.lastIndex++; continue; } FR.hits.push({ kind: 'doc', id: d.id, title: d.title || 'Untitled', ni, at: m.index, len: m[0].length, ctx: n.data.slice(Math.max(0, m.index - 40), m.index), hit: m[0], after: n.data.slice(m.index + m[0].length, m.index + m[0].length + 40), on: true }); } });
  });
  if ($('#frNotes').checked) P.notes.forEach(n => { ['title', 'body'].forEach(f => { const t = n[f] || ''; re.lastIndex = 0; let m; while ((m = re.exec(t))) { if (!m[0]) { re.lastIndex++; continue; } FR.hits.push({ kind: 'note', id: n.id, field: f, title: noteTitle(n) || 'Untitled note', at: m.index, len: m[0].length, ctx: t.slice(Math.max(0, m.index - 40), m.index), hit: m[0], after: t.slice(m.index + m[0].length, m.index + m[0].length + 40), on: true }); } }); });
  const groups = {}; FR.hits.forEach((h, i) => { const k = h.kind + ':' + h.id; (groups[k] = groups[k] || { title: (h.kind === 'note' ? 'Note: ' : '') + h.title, ix: [] }).ix.push(i); });
  $('#frSum').textContent = FR.hits.length ? `${FR.hits.length} match${FR.hits.length === 1 ? '' : 'es'} in ${Object.keys(groups).length} place${Object.keys(groups).length === 1 ? '' : 's'}` : 'No matches.';
  $('#frResults').innerHTML = Object.values(groups).map(g => `<li class="fr-g"><label class="fr-gh"><input type="checkbox" checked data-grp="${g.ix.join(',')}"> <b>${esc(g.title)}</b> <span class="muted">${g.ix.length}</span></label><ul>${g.ix.slice(0, 60).map(i => { const h = FR.hits[i]; return `<li><label><input type="checkbox" checked data-h="${i}"> <span class="fr-ctx">…${esc(h.ctx)}<mark>${esc(h.hit)}</mark>${esc(h.after)}…</span></label></li>`; }).join('')}${g.ix.length > 60 ? `<li class="muted small">…and ${g.ix.length - 60} more (all included)</li>` : ''}</ul></li>`).join('');
  $('#frGo').disabled = !FR.hits.length;
}
$('#frResults').addEventListener('change', e => {
  if (e.target.dataset.grp) { e.target.dataset.grp.split(',').forEach(i => { FR.hits[+i].on = e.target.checked; const cb = $(`[data-h="${i}"]`, $('#frResults')); if (cb) cb.checked = e.target.checked; }); }
  if (e.target.dataset.h) FR.hits[+e.target.dataset.h].on = e.target.checked;
  $('#frSum').textContent = `${FR.hits.filter(h => h.on).length} of ${FR.hits.length} selected`;
});
function frReplaceText(t, re, rep) { return $('#frRe').checked ? t.replace(new RegExp(re.source, re.flags.replace('g', '')), rep) : rep; }
$('#frGo').addEventListener('click', () => {
  const re = FR.re; if (!re) return; const rep = $('#frRepl').value, on = FR.hits.filter(h => h.on); if (!on.length) return;
  const byDoc = {}; on.forEach(h => { (byDoc[h.kind + ':' + h.id] = byDoc[h.kind + ':' + h.id] || []).push(h); });
  let docs = 0, n = 0;
  Object.entries(byDoc).forEach(([k, hs]) => {
    if (k.startsWith('doc:')) {
      const d = P.docs.find(x => x.id === k.slice(4)); if (!d) return;
      snapshot(d, `Before replacing “${$('#frFind').value.slice(0, 30)}”`, 'safety');
      const live = d.id === curDocId, root = live ? editor : (() => { const t = document.createElement('div'); t.innerHTML = d.html; return t; })();
      const nodes = frTextNodes(root);
      hs.sort((a, b) => b.ni - a.ni || b.at - a.at).forEach(h => { const nd = nodes[h.ni]; if (!nd) return; const seg = nd.data.substr(h.at, h.len); nd.data = nd.data.slice(0, h.at) + frReplaceText(seg, re, rep) + nd.data.slice(h.at + h.len); n++; });
      if (live) { syncEditor(); renderRefs(true); updateWordCount(); } else { d.html = root.innerHTML; d.modified = nowISO(); }
      docs++;
    } else {
      const note = P.notes.find(x => x.id === k.slice(5)); if (!note) return;
      hs.sort((a, b) => (a.field === b.field ? b.at - a.at : a.field < b.field ? 1 : -1)).forEach(h => { const t = note[h.field]; const seg = t.substr(h.at, h.len); note[h.field] = t.slice(0, h.at) + frReplaceText(seg, re, rep) + t.slice(h.at + h.len); n++; });
      note.modified = nowISO(); docs++;
    }
  });
  markDirty(); renderAll(); frSearch();
  toast(`Replaced ${n} in ${docs} place${docs === 1 ? '' : 's'}. Each changed document has a safety copy under Drafts.`);
});
function openFindAll() { const sel = String(getSelection()).trim(); if (sel && sel.length < 80) $('#frFind').value = sel; else if ($('#findQ').value) $('#frFind').value = $('#findQ').value; $('#frRepl').value = $('#replQ').value || ''; $('#frDlg').showModal(); frSearch(); setTimeout(() => $('#frFind').focus(), 30); }
['#frFind', '#frCase', '#frWord', '#frRe', '#frNotes', '#frScope'].forEach(s => $(s).addEventListener(s === '#frFind' ? 'input' : 'change', debounce(frSearch, 200)));
$('#frClose').addEventListener('click', () => $('#frDlg').close());
$('#findAllDocs').addEventListener('click', openFindAll);

/* ================================================================
   Transcripts: open caption and transcript files, search them
   ================================================================ */
const tsFmt = s => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : String(m)) + ':' + String(x).padStart(2, '0'); };
function captionsToTranscript(text) {
  const cues = []; const blocks = text.replace(/\r/g, '').split(/\n{2,}/);
  blocks.forEach(b => {
    const m = b.match(/(\d{1,2}:)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}:)?(\d{1,2}):(\d{2})/); if (!m) return;
    const start = (m[1] ? parseInt(m[1]) * 3600 : 0) + parseInt(m[2]) * 60 + parseInt(m[3]);
    let body = b.slice(b.indexOf(m[0]) + m[0].length).replace(/^[^\n]*\n/, '').trim(); if (!body) return;
    let sp = ''; const v = body.match(/<v(?:\.[^ >]+)?\s+([^>]+)>/); if (v) sp = v[1].trim();
    body = body.replace(/<[^>]+>/g, '').replace(/\{[^}]+\}/g, '').replace(/\s*\n\s*/g, ' ').trim();
    const pre = body.match(/^(?:-\s*)?([A-Z][\w .'’-]{1,30}):\s+(.*)$/); if (pre && !sp) { sp = pre[1]; body = pre[2]; }
    cues.push({ start, sp, text: body });
  });
  const out = []; let cur = null;
  cues.forEach(c => {
    if (cur && cur.text === c.text) return;
    const join = cur && (c.sp === cur.sp || !c.sp) && !/[.?!…]["”’)]?$/.test(cur.text) && cur.text.split(' ').length < 60;
    if (join) cur.text += ' ' + c.text; else { if (cur) out.push(cur); cur = { start: c.start, sp: c.sp || (cur && !c.sp ? cur.sp : ''), text: c.text }; }
  });
  if (cur) out.push(cur);
  return out.map(c => `[${tsFmt(c.start)}] ${c.sp ? c.sp + ': ' : ''}${c.text}`).join('\n');
}
$('#trOpenFile').addEventListener('click', () => $('#fileTranscript').click());
$('#fileTranscript').addEventListener('change', async e => {
  const f = e.target.files[0]; e.target.value = ''; if (!f) return;
  let text = '';
  try {
    if (/\.docx$/i.test(f.name)) { const r = await mammoth.extractRawText({ arrayBuffer: await f.arrayBuffer() }); text = r.value; }
    else text = await f.text();
  } catch (err) { toast('That file couldn’t be read.'); return; }
  if (/-->/.test(text)) text = captionsToTranscript(text);
  if (!$('#trSource').value) { toast('Choose the interview (source) first, or make a new one.'); }
  $('#trText').value = text; $('#trText').dispatchEvent(new Event('input'));
  toast(`Loaded ${f.name}: ${text.split('\n').filter(Boolean).length} lines.`);
});
$('#trFind').addEventListener('input', () => { const q = $('#trFind').value.trim().toLowerCase(); let n = 0; $$('#trLines li').forEach(li => { const hit = !q || li.textContent.toLowerCase().includes(q); li.classList.toggle('hidden', !hit); if (hit && q) n++; }); $('#trFindN').textContent = q ? `${n} line${n === 1 ? '' : 's'}` : ''; });

/* ================================================================
   Promo kit: social threads, Substack subtitle & description, quote cards
   ================================================================ */
const PLATFORMS = { x: ['X', 280], bsky: ['Bluesky', 300], threads: ['Threads', 500], mastodon: ['Mastodon', 500], linkedin: ['LinkedIn', 3000] };
function docSentences() {
  const out = [];
  [...editor.children].forEach(el => { if (!el.matches('p,blockquote')) return; const t = el.cloneNode(true); $$('.cite,.fn,.flag,.cmt-pt', t).forEach(m => m.remove()); const txt = t.textContent.replace(/\s+/g, ' ').trim(); (txt.match(/[^.!?]+[.!?]+["”’)]*/g) || [txt]).forEach(s => { s = s.trim(); if (s) out.push({ s, el }); }); });
  return out;
}
function plainBlocks() { return [...editor.children].map(el => { const t = el.cloneNode(true); $$('.cite,.fn,.flag,.cmt-pt', t).forEach(m => m.remove()); return { tag: el.nodeName, text: t.textContent.replace(/\s+/g, ' ').trim() }; }).filter(b => b.text); }
const pkFirst = t => (t.match(/^[^.!?]+[.!?]+["”’)]*/) || [t])[0].trim();
function fitTo(t, n) { if (t.length <= n) return t; const cut = t.slice(0, n - 1); return cut.slice(0, Math.max(cut.lastIndexOf(' '), n * .6)).replace(/[,;:—–-]$/, '') + '…'; }
function buildThread() {
  const [, lim] = PLATFORMS[$('#pkPlat').value], link = $('#pkLink').value.trim(), number = $('#pkNum').checked;
  const blocks = plainBlocks(), body = blocks.filter(b => b.tag === 'P' || b.tag === 'BLOCKQUOTE');
  const posts = [];
  const hook = body[0] ? body[0].text : curDoc().title;
  posts.push(pkFirst(hook) + (body[0] && pkFirst(hook).length < lim * .5 ? ' ' + pkFirst(hook.slice(pkFirst(hook).length).trim() || '') : ''));
  const heads = blocks.map((b, i) => ({ b, i })).filter(x => /^H[23]$/.test(x.b.tag));
  if (heads.length >= 2) heads.slice(0, 8).forEach(h => { const nxt = blocks.slice(h.i + 1).find(b => b.tag === 'P'); if (nxt && body[0] && nxt.text === body[0].text) return; posts.push(h.b.text.replace(/[.:]$/, '') + ': ' + (nxt ? pkFirst(nxt.text) : '')); });
  else body.slice(1).map(b => pkFirst(b.text)).filter(s => s.split(' ').length >= 8).slice(0, 6).forEach(s => posts.push(s));
  posts.push(link ? `Read the whole piece: ${link}` : 'Read the whole piece: [link]');
  const total = posts.length, room = number ? lim - 6 : lim;
  return posts.map((p, i) => fitTo(p.trim(), room) + (number ? ` ${i + 1}/${total}` : ''));
}
function renderThread(posts) {
  const [, lim] = PLATFORMS[$('#pkPlat').value];
  $('#pkPosts').innerHTML = posts.map((p, i) => `<div class="pk-post"><textarea rows="3" data-i="${i}" aria-label="Post ${i + 1} of ${posts.length}">${esc(p)}</textarea><div class="pk-meta"><span class="pk-n ${p.length > lim ? 'over' : ''}">${p.length}/${lim}</span><button class="small ghost" data-copy="${i}">Copy</button></div></div>`).join('');
}
function pkRefresh() { renderThread(buildThread()); }
$('#pkPosts').addEventListener('input', e => { const t = e.target; if (!t.matches('textarea')) return; const [, lim] = PLATFORMS[$('#pkPlat').value]; const n = t.parentElement.querySelector('.pk-n'); n.textContent = `${t.value.length}/${lim}`; n.classList.toggle('over', t.value.length > lim); });
$('#pkPosts').addEventListener('click', async e => { const b = e.target.closest('[data-copy]'); if (!b) return; const t = $(`#pkPosts textarea[data-i="${b.dataset.copy}"]`).value; try { await navigator.clipboard.writeText(t); toast('Copied.'); } catch (err) { toast('Clipboard blocked by the browser.'); } });
$('#pkCopyAll').addEventListener('click', async () => { const t = $$('#pkPosts textarea').map(x => x.value).join('\n\n'); try { await navigator.clipboard.writeText(t); toast('Copied the whole thread.'); } catch (err) { toast('Clipboard blocked by the browser.'); } });
['#pkPlat', '#pkNum'].forEach(s => $(s).addEventListener('change', pkRefresh)); $('#pkLink').addEventListener('change', pkRefresh); $('#pkRegen').addEventListener('click', pkRefresh);
function pkSubstack() {
  const b = plainBlocks().filter(x => x.tag === 'P'); const first = b[0] ? b[0].text : '';
  $('#pkTitle').value = curDoc().title || ''; $('#pkSub').value = fitTo(pkFirst(first), 140); $('#pkDesc').value = fitTo(first, 160);
  ['#pkTitle', '#pkSub', '#pkDesc'].forEach(s => $(s).dispatchEvent(new Event('input')));
}
[['#pkTitle', 80], ['#pkSub', 140], ['#pkDesc', 160]].forEach(([s, n]) => $(s).addEventListener('input', () => { const c = $(s).value.length; const el = $(s + 'N'); el.textContent = `${c}/${n}`; el.classList.toggle('over', c > n); }));
$('#pkCopySub').addEventListener('click', async () => { try { await navigator.clipboard.writeText(`${$('#pkTitle').value}\n${$('#pkSub').value}\n\n${$('#pkDesc').value}`); toast('Copied title, subtitle and description.'); } catch (e) { toast('Clipboard blocked by the browser.'); } });
/* quote cards */
const CARD_THEMES = { paper: { bg: '#f4f2ec', ink: '#16202c', accent: '#b5841f', sub: '#4a5763' }, navy: { bg: '#16263d', ink: '#f3f1ea', accent: '#e0b04f', sub: '#aab5c1' }, white: { bg: '#ffffff', ink: '#14181d', accent: '#24456e', sub: '#52514e' } };
const CARD_SIZES = { square: [1080, 1080], wide: [1200, 675], tall: [1080, 1350] };
function drawCard() {
  const c = $('#pkCanvas'), [W, H] = CARD_SIZES[$('#pkSize').value], T = CARD_THEMES[$('#pkTheme').value], g = c.getContext('2d');
  c.width = W; c.height = H; g.fillStyle = T.bg; g.fillRect(0, 0, W, H);
  const pad = Math.round(W * .09), q = $('#pkQuote').value.trim() || 'Pick a sentence, or type a quote.';
  g.fillStyle = T.accent; g.font = `700 ${Math.round(W * .2)}px Georgia, serif`; g.textBaseline = 'top'; g.fillText('“', pad - W * .02, pad - W * .06);
  let size = Math.round(W * .062), lines;
  const wrap = sz => { g.font = `500 ${sz}px Georgia, "Times New Roman", serif`; const words = q.split(/\s+/), L = []; let cur = ''; words.forEach(w => { const t = cur ? cur + ' ' + w : w; if (g.measureText(t).width > W - pad * 2 && cur) { L.push(cur); cur = w; } else cur = t; }); L.push(cur); return L; };
  for (; size > 22; size -= 2) { lines = wrap(size); if (lines.length * size * 1.32 < H - pad * 2 - W * .2) break; }
  g.fillStyle = T.ink; g.font = `500 ${size}px Georgia, "Times New Roman", serif`;
  const top = pad + W * .12 + Math.max(0, (H - pad * 2 - W * .22 - lines.length * size * 1.32) / 2);
  lines.forEach((l, i) => g.fillText(l, pad, top + i * size * 1.32));
  const who = $('#pkWho').value.trim(), handle = $('#pkHandle').value.trim();
  g.fillStyle = T.accent; g.fillRect(pad, H - pad - W * .075, W * .06, 4);
  g.fillStyle = T.ink; g.font = `700 ${Math.round(W * .027)}px "Helvetica Neue", Arial, sans-serif`; g.fillText(who, pad, H - pad - W * .055);
  g.fillStyle = T.sub; g.font = `400 ${Math.round(W * .024)}px "Helvetica Neue", Arial, sans-serif`; g.fillText(handle, pad, H - pad - W * .022);
}
function pkCards() {
  const cands = docSentences().map(x => x.s).filter(s => { const n = s.split(' ').length; return n >= 8 && n <= 34; }).sort((a, b) => (/[—:;]/.test(b) - /[—:;]/.test(a)) || a.length - b.length).slice(0, 12);
  $('#pkCands').innerHTML = cands.map((s, i) => `<button class="pk-cand" data-s="${i}">${esc(s)}</button>`).join('') || '<div class="small muted">No sentences of quote length yet.</div>';
  $('#pkCands')._c = cands; const sel = String(getSelection()).trim();
  if (!$('#pkQuote').value) $('#pkQuote').value = sel && sel.split(' ').length < 60 ? sel : (cands[0] || '');
  $('#pkWho').value = $('#pkWho').value || curDoc().meta.author || ''; $('#pkHandle').value = $('#pkHandle').value || PREFS.pubHandle || '';
  drawCard();
}
$('#pkCands').addEventListener('click', e => { const b = e.target.closest('[data-s]'); if (!b) return; $('#pkQuote').value = $('#pkCands')._c[+b.dataset.s]; drawCard(); });
['#pkQuote', '#pkWho', '#pkHandle'].forEach(s => $(s).addEventListener('input', debounce(() => { PREFS.pubHandle = $('#pkHandle').value.trim(); savePrefs(); drawCard(); }, 120)));
['#pkSize', '#pkTheme'].forEach(s => $(s).addEventListener('change', drawCard));
$('#pkDl').addEventListener('click', () => { drawCard(); const a = document.createElement('a'); a.href = $('#pkCanvas').toDataURL('image/png'); a.download = fileSafe(curDoc().title || 'quote') + ' - quote card.png'; document.body.append(a); a.click(); a.remove(); });
function openPromo(tab = 'thread') { syncEditor(); $('#pkDlg').showModal(); pkTab(tab); pkRefresh(); pkSubstack(); pkCards(); }
function pkTab(t) { $$('#pkTabs [data-t]').forEach(b => b.classList.toggle('on', b.dataset.t === t)); $$('#pkDlg .pk-pane').forEach(p => p.classList.toggle('hidden', p.dataset.p !== t)); if (t === 'card') drawCard(); }
$('#pkTabs').addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (b) pkTab(b.dataset.t); });
$('#pkClose').addEventListener('click', () => $('#pkDlg').close());

/* ================================================================
   Project checkpoints: a saved copy of the whole project
   ================================================================ */
const cpW = d => wc(docPlain(d.id === curDocId && P.docs.includes(d) ? (syncEditor(), d.html) : d.html));
const CPK = id => `cp:${P.id}:${id}`, CP_CACHE = {};
function cpList() { P.checkpoints = Array.isArray(P.checkpoints) ? P.checkpoints : []; return P.checkpoints; }
async function cpSave(name, note, auto = false) {
  syncEditor();
  const id = uid('cp'), text = projectJSON(), words = P.docs.reduce((n, d) => n + cpW(d), 0);
  await idb.set(CPK(id), LOCK ? await sealText(text) : text);
  const meta = { id, name: name || `Checkpoint ${cpList().filter(c => !c.auto).length + 1}`, note: note || '', date: nowISO(), words, docs: P.docs.length, notes: P.notes.length, sources: P.sources.length, size: text.length, auto };
  cpList().unshift(meta); markDirty(); return meta;
}
async function cpText(id) {
  const t = await idb.get(CPK(id)); if (!t) return null;
  if (t[0] === '{' && t.slice(0, 200).includes('"encrypted"')) { try { const env = JSON.parse(t); if (!env.encrypted) return t; if (!LOCK) return null; const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64ToBytes(env.iv) }, LOCK.key, b64ToBytes(env.data)); return new TextDecoder().decode(pt); } catch (e) { return null; } }
  return t;
}
async function cpLoad(id) { if (CP_CACHE[id]) return CP_CACHE[id]; const t = await cpText(id); if (!t) return null; try { CP_CACHE[id] = normalize(JSON.parse(t)); return CP_CACHE[id]; } catch (e) { return null; } }
async function renderCheckpoints() {
  const list = cpList(), have = {};
  for (const c of list) have[c.id] = !!(await idb.get(CPK(c.id)).catch(() => null));
  $('#cpList').innerHTML = list.length ? list.map(c => `<li class="${c.auto ? 'cp-auto' : ''}" data-id="${c.id}"><div class="cp-h"><b>${esc(c.name)}</b><span class="muted small">${dfWhen(c.date)} · ${c.words.toLocaleString()} words · ${c.docs} docs · ${c.notes} notes · ${c.sources} sources</span>${c.note ? `<span class="small">${esc(c.note)}</span>` : ''}${have[c.id] ? '' : '<span class="small cp-missing">Saved in another browser; not available here.</span>'}</div><div class="cp-acts">${have[c.id] ? '<button class="small" data-a="cmp">Compare</button><button class="small" data-a="restore">Restore</button><button class="small ghost" data-a="dl">Download</button>' : ''}<button class="small ghost danger" data-a="del">Delete</button></div><div class="cp-diff hidden"></div></li>`).join('') : '<li class="muted small none">No checkpoints yet. Save one before a big restructure, or at a milestone such as sending the manuscript out.</li>';
}
function openCheckpoints() { $('#cpName').value = ''; $('#cpNote').value = ''; $('#cpName').placeholder = `Checkpoint ${cpList().filter(c => !c.auto).length + 1}`; $('#cpDlg').showModal(); renderCheckpoints(); }
$('#cpSave').addEventListener('click', async () => { try { const m = await cpSave($('#cpName').value.trim(), $('#cpNote').value.trim()); $('#cpName').value = ''; $('#cpNote').value = ''; renderCheckpoints(); toast(`Saved “${m.name}”.`); } catch (e) { toast('The checkpoint couldn’t be saved: ' + e.message); } });
$('#cpList').addEventListener('click', async e => {
  const li = e.target.closest('[data-id]'), a = e.target.closest('[data-a]')?.dataset.a; if (!li || !a) return;
  const c = cpList().find(x => x.id === li.dataset.id); if (!c) return;
  if (a === 'del') { if (!(await ask('Delete this checkpoint?', `“${c.name}” will be removed from this browser.`, 'Delete'))) return; await idb.set(CPK(c.id), ''); P.checkpoints = cpList().filter(x => x !== c); markDirty(); $('#cpDlg').open || $('#cpDlg').showModal(); renderCheckpoints(); return; }
  if (a === 'dl') { const t = await cpText(c.id); if (t) download(fileSafe(`${P.title} - ${c.name}`) + '.json', LOCK ? await sealText(t) : t, 'application/json'); return; }
  const snap = await cpLoad(c.id); if (!snap) { toast('That checkpoint isn’t in this browser.'); return; }
  if (a === 'cmp') {
    syncEditor(); const box = li.querySelector('.cp-diff'); const then = Object.fromEntries(snap.docs.map(d => [d.id, d])), now = Object.fromEntries(P.docs.map(d => [d.id, d]));
    const rows = [];
    P.docs.forEach(d => { const o = then[d.id]; if (!o) rows.push(`<li><span class="cp-tag add">new</span> ${esc(d.title || 'Untitled')} <span class="muted">${cpW(d).toLocaleString()} word${cpW(d) === 1 ? '' : 's'}</span></li>`); else if (o.html !== d.html) { const dw = cpW(d) - cpW(o); rows.push(`<li><span class="cp-tag chg">changed</span> ${esc(d.title || 'Untitled')} <span class="muted">${dw >= 0 ? '+' : '−'}${Math.abs(dw).toLocaleString()} words</span> <button class="small ghost" data-cmpdoc="${d.id}">Compare side by side</button></li>`); } });
    snap.docs.forEach(o => { if (!now[o.id]) rows.push(`<li><span class="cp-tag del">removed</span> ${esc(o.title || 'Untitled')} <span class="muted">${cpW(o).toLocaleString()} word${cpW(o) === 1 ? '' : 's'}</span></li>`); });
    const dn = P.notes.length - snap.notes.length, ds = P.sources.length - snap.sources.length;
    box.innerHTML = `<ul class="cp-rows">${rows.join('') || '<li class="muted">No document has changed.</li>'}</ul><div class="small muted">Notes ${dn >= 0 ? '+' : '−'}${Math.abs(dn)} · sources ${ds >= 0 ? '+' : '−'}${Math.abs(ds)} since then.</div>`;
    box.classList.toggle('hidden'); return;
  }
  if (a === 'restore') {
    if (!(await ask('Restore this checkpoint?', `The whole project goes back to “${c.name}” (${dfWhen(c.date)}). The current state is saved as a checkpoint first, so you can return to it.`, 'Restore checkpoint'))) return;
    await cpSave(`Before restoring “${c.name}”`, '', true);
    const keep = cpList(), keepId = P.id, t = await cpText(c.id); if (!t) { toast('That checkpoint couldn’t be opened.'); return; }
    P = normalize(JSON.parse(t)); P.id = keepId; P.checkpoints = keep; Object.keys(CP_CACHE).forEach(k => delete CP_CACHE[k]);
    curDocId = P.docs[0] ? P.docs[0].id : null; closePanel(); renderAll(); if (curDocId) openDoc(curDocId, true); markDirty();
    $('#cpDlg').close(); toast(`Restored “${c.name}”. The state you left is saved as a checkpoint.`);
  }
});
$('#cpList').addEventListener('click', async e => {
  const b = e.target.closest('[data-cmpdoc]'); if (!b) return; const cid = b.closest('[data-id]').dataset.id;
  await cpLoad(cid); $('#cpDlg').close(); openDoc(b.dataset.cmpdoc); openDrafts(`cp:${cid}:${b.dataset.cmpdoc}`);
});
$('#cpClose').addEventListener('click', () => $('#cpDlg').close());

/* ================================================================
   Accessibility check
   ================================================================ */
function a11yIssues() {
  const out = []; const d = curDoc(); if (!d) return out;
  let last = 0;
  [...editor.children].forEach(el => {
    const m = /^H([1-3])$/.exec(el.nodeName);
    if (m) { const lv = +m[1]; if (!el.textContent.trim()) out.push({ el, msg: 'Empty heading.' }); if (lv > last + 1) out.push({ el, msg: `Heading jumps from ${last ? 'level ' + last : 'the start'} to level ${lv}${last ? '' : ' (start with Heading 1 or 2)'}.` }); last = lv; }
  });
  let fN = 0;
  $$('figure.fig', editor).forEach(f => { fN++; const img = f.querySelector('img'); if (img && !(img.getAttribute('alt') || '').trim()) out.push({ el: f, msg: `Figure ${fN} has no alt text.`, fix: 'alt', img }); });
  $$('figure.tbl:not(.av) table', editor).forEach(t => { if (!t.tHead && !t.querySelector('th')) out.push({ el: t.closest('figure'), msg: 'A table has no header row.', fix: 'head', t }); });
  $$('a[href]', editor).forEach(a => { const t = a.textContent.trim().toLowerCase(); if (/^(here|click here|this|link|read more|more|this link)$/.test(t) || /^https?:\/\//.test(t)) out.push({ el: a.closest('p,li') || a, msg: `Link text “${a.textContent.trim().slice(0, 40)}” doesn’t say where it goes.` }); });
  return out;
}
let A11Y = [];
function renderA11y() {
  if (!$('#a11yList') || !curDoc()) return;
  A11Y = a11yIssues(); $('#a11yCount').textContent = A11Y.length || '';
  $('#a11yList').innerHTML = A11Y.length ? A11Y.map((x, i) => `<li><span>${esc(x.msg)}</span><span class="ol-acts">${x.fix === 'alt' ? `<button class="small" data-afix="${i}">Add alt text…</button>` : x.fix === 'head' ? `<button class="small" data-afix="${i}">Add header row</button>` : ''}<button class="small ghost" data-ago="${i}">Show</button></span></li>`).join('') : '<li class="muted small none">No problems found: headings in order, alt text on figures, header rows on tables, and descriptive links.</li>';
}
$('#a11yList').addEventListener('click', async e => {
  const g = e.target.closest('[data-ago]'); if (g) { const x = A11Y[+g.dataset.ago]; x && x.el.scrollIntoView({ block: 'center', behavior: 'smooth' }); return; }
  const f = e.target.closest('[data-afix]'); if (!f) return; const x = A11Y[+f.dataset.afix];
  if (x.fix === 'alt') { const cap = x.el.querySelector('figcaption'); const t = await ask('Alt text', 'Describe what the image shows for someone who can’t see it. The caption is read separately.', 'Save', cap ? cap.textContent.replace(/^(Figure|Table)\s+\d+\.\s*/, '').trim().slice(0, 180) : ''); if (t !== null && t.trim()) { x.img.alt = t.trim(); onEdit(); renderA11y(); } }
  if (x.fix === 'head') { const c = x.t.rows[0] && x.t.rows[0].cells[0]; if (c) { caretInto(c); tableOp('head'); renderA11y(); } }
});
editor.addEventListener('input', debounce(() => { if (!homeOn && !boardOn && !planOn) renderA11y(); }, 1200));
function a11yNudge() { const n = a11yIssues().length; if (n) setTimeout(() => toast(`${n} accessibility issue${n === 1 ? '' : 's'} in this document (alt text, headings, tables or links). See the Outline tab.`), 900); }


/* ================================================================
   First-run tour
   ================================================================ */
const TOUR = [
  { t: 'Welcome to Anabasis', x: 'A writing desk for nonfiction: documents, notes and sources in one project. Your work stays on this computer. There’s no account and no server; Anabasis goes online only to look up a source or back up to GitHub when you ask. This tour takes about two minutes.' },
  { sel: '.tabs', t: 'Docs, notes and sources', x: 'Docs holds your chapters and parts. Notes are quotes and ideas you can drag into a draft. Sources are your bibliography, each with its own reliability rating.' },
  { sel: '#btnCite', t: 'Cite as you write', x: 'Put the cursor where the citation goes and choose Cite. Notes and the bibliography rebuild below the text as you write.' },
  { sel: '#docStyle', t: 'Pick a style', x: 'Chicago, APA, MLA or the OSINT Style Guide. Switch at any time and every citation reformats.' },
  { sel: '#btnFigure', t: 'Figures', x: 'Charts from a table, maps that work offline, timelines from dated notes, and relationship maps. Each figure stays editable.' },
  { sel: '.tabs button[data-tab=outline]', t: 'Checks', x: 'The Outline tab flags undefined acronyms, vague estimative words, thin sourcing, house-style slips and accessibility problems, with one-click fixes.' },
  { sel: '#btnExport', t: 'Export and share', x: 'PDF, Word, ePub, Markdown, a Substack post or a promo kit. Checkpoints and GitHub backup live here too.' },
  { sel: '#btnSave', t: 'Save the project file', x: 'Save writes the whole project to one .json file. Keep it in a synced or backed-up folder. Help (the ? button) has the full guide and can replay this tour.' },
];
let tourAt = -1;
function tourVisible(sel) { const el = sel && $(sel); if (!el) return null; const r = el.getBoundingClientRect(); return r.width && r.height && r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight && getComputedStyle(el).visibility !== 'hidden' ? el : null; }
function startTour() {
  if (homeOn) closeHome(); if (boardOn) closeBoard(); if (planOn) closePlan();
  tourAt = -1; $('#tour').classList.remove('hidden'); tourGo(1);
}
function endTour() { $('#tour').classList.add('hidden'); tourAt = -1; PREFS.toured = true; savePrefs(); editor.focus({ preventScroll: true }); }
function tourGo(dir) {
  let i = tourAt;
  do { i += dir; } while (i > 0 && i < TOUR.length && TOUR[i].sel && !tourVisible(TOUR[i].sel));
  if (i < 0) i = 0; if (i >= TOUR.length) { endTour(); return; }
  tourAt = i; tourPlace();
}
function tourPlace() {
  const st = TOUR[tourAt], el = tourVisible(st.sel), box = $('#tourBox'), spot = $('#tourSpot');
  $('#tourTitle').textContent = st.t; $('#tourText').textContent = st.x;
  $('#tourStep').textContent = `${tourAt + 1} of ${TOUR.length}`;
  $('#tourBack').disabled = tourAt === 0; $('#tourNext').textContent = tourAt === TOUR.length - 1 ? 'Start writing' : 'Next';
  const W = innerWidth, H = innerHeight, bw = Math.min(360, W - 24);
  box.style.width = bw + 'px';
  if (!el) { spot.style.display = 'none'; box.style.left = (W - bw) / 2 + 'px'; box.style.top = Math.max(24, H / 2 - 120) + 'px'; }
  else {
    const r = el.getBoundingClientRect(), pad = 6;
    Object.assign(spot.style, { display: 'block', left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + pad * 2 + 'px', height: r.height + pad * 2 + 'px' });
    const bh = box.offsetHeight || 170; let top = r.bottom + 14; if (top + bh > H - 12) top = Math.max(12, r.top - bh - 14);
    box.style.left = Math.min(W - bw - 12, Math.max(12, r.left + r.width / 2 - bw / 2)) + 'px'; box.style.top = top + 'px';
  }
  $('#tourNext').focus();
}
$('#tourNext').addEventListener('click', () => tourGo(1));
$('#tourBack').addEventListener('click', () => tourGo(-1));
$('#tourSkip').addEventListener('click', endTour);
$('#tour').addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); endTour(); } if (e.key === 'ArrowRight') tourGo(1); if (e.key === 'ArrowLeft') tourGo(-1); });
addEventListener('resize', () => { if (tourAt >= 0) tourPlace(); });
$('#helpTour').addEventListener('click', () => { $('#helpDlg').close(); startTour(); });
$('#aboutVersion').textContent = APP_VERSION;

/* Labels written as a sibling of their field get tied to it, so screen readers announce every field by name. */
function linkLabels(root = document) {
  $$('label:not([for])', root).forEach(l => {
    if (l.querySelector('input,select,textarea')) return;
    let c = l.nextElementSibling;
    if (!c || !c.matches('input,select,textarea')) c = l.parentElement && [...l.parentElement.children].find(x => x !== l && x.matches('input,select,textarea') && l.compareDocumentPosition(x) & Node.DOCUMENT_POSITION_FOLLOWING);
    if (!c || c.type === 'checkbox' || c.type === 'radio') return;
    if (!c.id) c.id = uid('f');
    l.htmlFor = c.id;
  });
}
linkLabels();
{ const relink = debounce(() => linkLabels(), 150); new MutationObserver(recs => { if (recs.some(r => !editor.contains(r.target))) relink(); }).observe(document.body, { childList: true, subtree: true }); }
/* ---------------- boot ---------------- */
function sendClip(to, clip) {
  return new Promise(res => {
    const t = setTimeout(() => { bc.removeEventListener('message', on); res(false); }, 1500);
    const on = e => { const m = e.data || {}; if (m.type === 'clip-ok' && m.to === TAB_ID) { clearTimeout(t); bc.removeEventListener('message', on); res(true); } };
    bc.addEventListener('message', on);
    bc.postMessage({ type: 'clip', to, from: TAB_ID, clip });
  });
}
(async function boot() {
  const clip = readClipFromHash();
  if (clip) {
    const other = await findOtherTab(true);
    if (other && await sendClip(other, clip)) {
      document.body.innerHTML = '<div class="handoff"><div><b>Clipped to Anabasis ✓</b><p>It’s in your open Anabasis tab. You can close this one.</p></div></div>';
      try { window.close(); } catch (e) {}
      return;
    }
  }
  window.name = 'commonplace';
  const th = lsGet(THEME_KEY) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = th;
  let rec = await loadLocal();
  if (isLocked(rec)) {
    const r = await unlockLoop(rec, 'Unlock Anabasis', 'Your project in this browser is locked with a password.', true);
    if (r === '__fresh') {
      if (await ask('Start without it?', 'This erases the locked copy kept in this browser. Locked project files you saved are not touched, and you can open them with the password later.', 'Erase browser copy')) { try { await idb.set(STORE_KEY, ''); } catch (e) {} lsSet(STORE_KEY, ''); rec = null; lsSet('commonplace.fresh', '1'); }
      else { location.reload(); return; }
    } else if (r && r.text) { try { rec = JSON.parse(r.text); LOCK = r.lock; document.body.classList.add('locked'); } catch (e) { rec = null; } }
    else rec = null;
  }
  if (rec && rec.project) {
    P = normalize(rec.project); curDocId = rec.curDocId;
    dirtyFile = rec.dirtyFile !== undefined ? !!rec.dirtyFile : true;
    dirtySince = dirtyFile ? (rec.dirtySince || Date.now()) : null;
    lastFileSave = rec.lastFileSave ? new Date(rec.lastFileSave) : null; lastFileName = rec.lastFileName || '';
  } else if (lsGet('commonplace.fresh')) { P = blankProject(); P.docs.push(newDoc()); try { localStorage.removeItem('commonplace.fresh'); } catch (e) {} }
  else P = sampleProject();
  if (!P.docs.length) P.docs.push(newDoc());
  openDoc(P.docs.find(d => d.id === curDocId) ? curDocId : binderOrder()[0].id, true);
  renderAll(); updateSaveState();
  appReady = true;
  restoreAutosaveHandle();
  if (!clip) findOtherTab(false).then(o => { if (o) showTabWarning(); });
  if (!clip && FIRST_VISIT && !PREFS.toured) setTimeout(() => startTour(), 350);
  else if (!clip && PREFS.startHome !== false) openHome();
  if (rec && rec.project && dirtyFile && !clip) toast('Restored your unsaved work from this browser.');
  if (clip) handleClip(clip);
})();
