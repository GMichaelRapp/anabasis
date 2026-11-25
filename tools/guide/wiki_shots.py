#!/usr/bin/env python3
"""Regenerate the screenshots in the wiki pages (docs/wiki/) by driving the real app.

    python build.py && python tools/guide/wiki_shots.py           (Pillow, if installed, shrinks the images)
    python tools/guide/wiki_shots.py socrates oracle              (only the named shots)

Uses the thesis example project, so every screenshot shows a real chapter with sources, notes,
threads and claims. Writes docs/wiki/images/<name>.png. Rerun it after any interface change.
"""
import asyncio, pathlib, sys, tempfile
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = (ROOT / 'dist' / 'anabasis.html').as_uri()
OUT = ROOT / 'docs' / 'wiki' / 'images'
W, H = 1280, 800
PREFS = "localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))"
MARK = "outline:3px solid #A3271B!important;outline-offset:3px!important;border-radius:6px"

# A short sample article for the PDF reader shots. The author and the text are made up for this guide.
SAMPLE_PDF = """<!doctype html><meta charset="utf-8"><style>
@page { size: 6in 9in; margin: 0.8in 0.75in; }
body { font: 11pt/1.5 Georgia, serif; color: #111; }
h1 { font-size: 17pt; line-height: 1.2; margin: 0 0 4pt; } .by { font-style: italic; margin: 0 0 18pt; }
p { margin: 0 0 8pt; text-align: justify; hyphens: auto; } .pg { page-break-after: always; }
.n { text-align: center; font-size: 9pt; margin-top: 14pt; }
</style>
<div class="pg"><h1>Bread on the March: Supply and Choice in the Retreat of the Ten Thousand</h1>
<p class="by">A sample article for the Anabasis guide</p>
<p>Accounts of the retreat usually begin with the Persians, and with good reason: the satrap's cavalry harried the column for weeks, and the murder of the generals at the Zapatas left the army leaderless. Yet the daily problem the army faced was not the enemy. It was bread. An army of ten thousand soldiers, with its servants, women and pack animals, needed something like forty tonnes of grain a day, and it carried at most a few days' supply.</p>
<p>The route the army took through the mountains of Kurdistan makes most sense when it is read as a search for villages with stored grain. The generals chose valleys over passes when the valleys were inhabited, and they halted for days where the stores were large. Xenophon's narrative records these halts without comment, but they set the pace of the march more surely than any pursuit did.</p>
<p>This is not to say that the Persians did not matter. Where they held the plains, the army could not forage, and the decision to strike north into the hills was forced on it. But once in the hills, the army was largely left alone, and the decisive constraint became the harvest.</p>
<p class="n">12</p></div>
<div><p>The point can be pressed too far. The army did not always find grain where it went looking, and it sometimes went hungry in country that should have fed it, because the villagers had fled with their stores or burned them. However, the pattern holds across most of the march: the army moved fastest between harvests and slowest where it could eat.</p>
<p>Two objections deserve an answer. The first is that Xenophon, writing years later, may have smoothed the record of supply to flatter his own leadership. The second is that the numbers are uncertain: we do not know how many non-combatants marched with the soldiers, and estimates of daily rations vary by half. Neither objection, though, overturns the larger argument, which rests on the shape of the route rather than on any single figure.</p>
<p>What changes when supply is put first? The retreat looks less like a running battle and more like a long negotiation with hunger, conducted by men who knew that a week without stores would end the march more surely than any Persian army.</p>
<p class="n">13</p></div>"""


SAMPLE_NOTES = """() => {
  const src = { id: uid('s'), csl: { id: '', type: 'book', title: 'Anabasis', author: [{ family: 'Xenophon' }], translator: [{ family: 'Dakyns', given: 'H. G.' }], publisher: 'Macmillan', 'publisher-place': 'London', issued: { 'date-parts': [[1897]] } }, stype: 'primary', created: nowISO(), modified: nowISO() };
  src.csl.id = src.id; P.sources.push(src);
  const pile = name => { let p = P.piles.find(x => x.name === name); if (!p) { p = { id: uid('pl'), name }; P.piles.push(p); } return p.id; };
  const add = o => { const n = Object.assign(newNote(), o); P.notes.push(n); return n; };
  const lee = P.sources.find(x => /Greek Army/.test(x.csl.title)), wat = P.sources.find(x => /Retreat/.test(x.csl.title));
  add({ title: 'The sea! the sea!', kind: 'quote', sourceId: src.id, locator: 'IV.7', label: 'section', tags: ['arrival'], pile: pile('The coast'), date: '400 BCE', body: 'Presently they could hear the soldiers shouting and passing on the joyful word, "The sea! the sea!"' });
  add({ title: 'Where was Mount Theches?', kind: 'idea', tags: ['route'], pile: pile('The coast'), body: 'Find two modern identifications and say which the chapter follows, and why.' });
  add({ title: 'Halts follow the stores', kind: 'idea', tags: ['route', 'logistics'], pile: pile('The route'), color: 'green', body: 'Every long halt in the mountains is at a village with grain. Map them against the days of marching.' });
  add({ title: 'Valleys over passes', kind: 'paraphrase', sourceId: lee ? lee.id : '', locator: '31', tags: ['route'], pile: pile('The route'), body: 'Lee notes the generals preferred inhabited valleys to shorter passes when they had the choice.' });
  add({ title: 'Assemblies and food', kind: 'paraphrase', sourceId: wat ? wat.id : '', locator: '118', tags: ['command'], pile: pile('Who decided'), body: 'Waterfield reads the army assemblies as genuinely deliberative; most of the arguments recorded are about supply.' });
  P.notes.filter(n => /Rations|Camp/.test(n.title)).forEach(n => { n.pile = pile('Numbers'); });
  add({ title: 'Count the non-combatants', kind: 'idea', tags: ['numbers'], pile: pile('Numbers'), color: 'yellow', body: 'Every ration estimate depends on how many servants and traders marched. State the range, not one figure.' });
  renderNoteList(); renderSourceList && renderSourceList(); markDirty();
}"""


async def main(only):
    if not (ROOT / 'dist' / 'anabasis.html').exists(): sys.exit('Build first: python build.py')
    OUT.mkdir(parents=True, exist_ok=True)
    want = lambda n: not only or n in only
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        # the sample PDF, printed by the browser
        tmp = pathlib.Path(tempfile.mkdtemp()) / 'bread-on-the-march.pdf'
        pp = await b.new_page(); await pp.set_content(SAMPLE_PDF); await pp.pdf(path=str(tmp), prefer_css_page_size=True); await pp.close()

        ctx = await b.new_context(viewport={'width': W, 'height': H})
        await ctx.add_init_script(PREFS)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))

        async def mark(*sels):
            await pg.evaluate("""s => { document.querySelectorAll('[data-qs-mark]').forEach(e => { e.style.cssText = e.dataset.qsMark === '-' ? '' : e.dataset.qsMark; e.removeAttribute('data-qs-mark'); });
              s.forEach(sel => { const e = document.querySelector(sel); if (e) { e.dataset.qsMark = e.getAttribute('style') || '-'; e.style.cssText += ';' + MARKCSS; } }); }""".replace('MARKCSS', repr(MARK)), list(sels))

        async def clean():
            await pg.evaluate("() => { $('#toast')?.classList.remove('show'); dirtyFile = false; lastFileSave = new Date(); updateSaveState(); }"); await pg.wait_for_timeout(250)

        async def shot(name, target=None, *sels, pad=8, w=None):
            if not want(name): return
            await clean(); await mark(*sels); await pg.wait_for_timeout(250)
            vp = pg.viewport_size; w = w or vp['width']; h = vp['height']; clip = None
            if target:
                bx = await pg.locator(target).first.bounding_box()
                if bx:
                    x, y = max(0, bx['x'] - pad), max(0, bx['y'] - pad)
                    clip = {'x': x, 'y': y, 'width': min(w - x, bx['width'] + 2 * pad), 'height': min(h - y, bx['height'] + 2 * pad)}
            await pg.screenshot(path=str(OUT / f'{name}.png'), clip=clip)
            await mark()

        async def close_all():
            await pg.evaluate("""() => { document.querySelectorAll('dialog[open]').forEach(d => d.close());
              if (typeof homeOn !== 'undefined' && homeOn) closeHome(); if (deskOn) closeDesk(); if (boardOn) closeBoard(); if (planOn) closePlan();
              if (typeof rrOn !== 'undefined' && rrOn) rrToggle(false); if (typeof splitClose === 'function') splitClose(); closePanel && closePanel(); }""")
            await pg.wait_for_timeout(300)

        async def select_text(a, z):
            await pg.evaluate("""([a, z]) => { const w = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT); const ns = []; let n;
                while ((n = w.nextNode())) if (!n.parentElement.closest('.cite,.fn,.refs')) ns.push(n);
                const find = s => { for (const x of ns) { const i = x.data.indexOf(s); if (i >= 0) return [x, i]; } };
                const [sn, so] = find(a), [en, eo] = find(z); const r = document.createRange(); r.setStart(sn, so); r.setEnd(en, eo + z.length);
                const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); editor.focus(); }""", [a, z])

        await pg.goto(APP); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1500)
        await close_all()
        await pg.evaluate("() => { const d = P.docs.find(x => /retreat|supply|march/i.test(x.title)) || P.docs[0]; openDoc(d.id); switchTab('research'); }"); await pg.wait_for_timeout(800)

        # Home: the editor with the research tab
        await shot('home-editor')

        # Getting started: the main screen, its parts outlined
        await pg.evaluate("switchTab('docs')"); await pg.wait_for_timeout(300)
        await shot('main-screen', None, '#topBar', '.tabs', '#toolbar', '#docBar')

        # Project home
        await pg.evaluate("openHome()"); await pg.wait_for_timeout(900)
        await shot('project-home')
        await close_all()

        # New project
        if want('new-project'):
            await pg.click('#btnNewProj'); await pg.wait_for_timeout(500)
            if await pg.locator('#askOk').is_visible(): await pg.click('#askOk'); await pg.wait_for_timeout(500)
            await pg.fill('#npTitle', 'Supply and Survival')
            kind = pg.locator('#npKinds button, #npKinds label').filter(has_text='Article')
            if await kind.count(): await kind.first.click()
            await pg.wait_for_timeout(300)
            await shot('new-project', '#npDlg .dlg')
            await pg.click('#npDlg footer button:not(.primary)'); await pg.wait_for_timeout(300)
            await close_all()

        # Citations: the cite dialog
        if want('cite-dialog'):
            await pg.evaluate("""() => { const ps = [...editor.querySelectorAll('p')].filter(p => p.textContent.length > 120); const p = ps[1] || ps[0];
                const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); saveSelectionNow && saveSelectionNow(); }""")
            await pg.click('#btnCite'); await pg.wait_for_timeout(500)
            li = pg.locator('#citePick li').filter(has_text='Lee')
            await (li.first if await li.count() else pg.locator('#citePick li').first).click(); await pg.wait_for_timeout(300)
            loc = pg.locator('#citeCluster input.loc').first
            if await loc.count(): await loc.fill('45–47'); await loc.dispatch_event('input')
            await pg.fill('#citeNote', 'Lee reckons the daily ration at about a choinix of grain a man.')
            await pg.dispatch_event('#citeNote', 'input'); await pg.wait_for_timeout(600)
            await shot('cite-dialog', '#citeDlg .dlg')
            await pg.evaluate("$('#citeDlg').close()")

        # Citations: the notes and bibliography under the text
        if want('notes-bibliography'):
            await pg.evaluate("() => { const r = $('#refs'); if (r) r.scrollIntoView({ block: 'start' }); scrollBy(0, -200); }"); await pg.wait_for_timeout(400)
            await shot('notes-bibliography', '#refs', pad=12)
            await pg.evaluate("() => { editor.scrollIntoView({ block: 'start' }); }")

        # Sources
        await pg.evaluate("() => { switchTab('sources'); const s = P.sources.find(x => /Greek Army/.test(x.csl.title)) || P.sources[0]; openSource(s.id); }"); await pg.wait_for_timeout(700)
        await shot('sources')
        if want('source-audit'):
            await close_all(); await pg.evaluate("openAudit('all')"); await pg.wait_for_timeout(800)
            await shot('source-audit', '#auditDlg .dlg')
            await close_all()

        # Notes: a few more cards in named piles (the quotation is from Dakyns's 1897 translation, in the public domain)
        await pg.evaluate(SAMPLE_NOTES); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { switchTab('notes'); const n = P.notes.find(x => x.kind === 'quote' && x.sourceId) || P.notes[0]; openNote(n.id); }"); await pg.wait_for_timeout(700)
        await shot('note')
        await close_all()
        await pg.set_viewport_size({'width': 1680, 'height': H})
        await pg.evaluate("() => { PREFS.boardGroup = 'pile'; savePrefs && savePrefs(); openBoard(); }"); await pg.wait_for_timeout(900)
        await pg.click('#btnSide'); await pg.wait_for_timeout(400)
        await shot('board', None, w=1680)
        await pg.click('#btnSide'); await pg.wait_for_timeout(300)
        await pg.set_viewport_size({'width': W, 'height': H})
        await close_all()

        # PDF reader, then Take notes
        if want('pdf-reader') or want('take-notes') or want('pdf-highlight'):
            await pg.evaluate("() => { switchTab('sources'); showReader(true); }"); await pg.wait_for_timeout(400)
            await pg.set_input_files('#filePdf', str(tmp)); await pg.wait_for_timeout(2500)
            await pg.evaluate("""() => { const s = { id: uid('s'), csl: { type: 'article-journal', title: 'Bread on the March: Supply and Choice in the Retreat of the Ten Thousand', author: [{ literal: 'Sample Author' }], 'container-title': 'Sample article for the Anabasis guide', issued: { 'date-parts': [[2026]] }, page: '12-13' }, stype: 'secondary', created: nowISO(), modified: nowISO() };
                s.csl.id = s.id; P.sources.push(s); renderSourceList(); const sel = $('#rdSource'); sel.innerHTML += `<option value="${s.id}">Bread on the March</option>`; sel.value = s.id; sel.dispatchEvent(new Event('change', { bubbles: true }));
                const o = $('#rdOffset'); o.value = '-11'; o.dispatchEvent(new Event('change', { bubbles: true })); }""")
            await pg.wait_for_timeout(600)
            # select a sentence in the PDF's text layer
            await pg.evaluate("""() => { const spans = [...document.querySelectorAll('#reader .textLayer span')].filter(e => e.childNodes.length === 1 && e.firstChild.nodeType === 3);
                const i = spans.findIndex(e => /Yet the/.test(e.textContent)); const j = spans.findIndex((e, k) => k > i && /bread[.]/.test(e.textContent));
                if (i < 0 || j < 0) return; const r = document.createRange(); r.setStart(spans[i].firstChild, spans[i].textContent.indexOf('Yet')); r.setEnd(spans[j].firstChild, spans[j].textContent.indexOf('bread.') + 6);
                const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.dispatchEvent(new Event('selectionchange')); spans[j].dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); }""")
            await pg.wait_for_timeout(600)
            await shot('pdf-reader')
            await pg.click('#rdSelBar [data-k=quote]'); await pg.wait_for_timeout(600)
            await shot('pdf-highlight', '#rdPages .rd-page', pad=18)
            await pg.click('#btnSide'); await pg.wait_for_timeout(300)
            await pg.click('#rdNotes'); await pg.wait_for_timeout(700)
            for kind, text in (('idea', 'The halts, not the battles, set the pace. Worth setting against Lee on rations (pp. 45–47).'),
                               ('summary', 'Argues the route through the hills was a search for villages with stored grain; Persian pressure mattered only on the plains.')):
                await pg.select_option('#rrKind', kind); await pg.fill('#rrText', text); await pg.click('#rrSave'); await pg.wait_for_timeout(400)
            await pg.evaluate("""() => { const spans = [...document.querySelectorAll('#reader .textLayer span')].filter(e => e.childNodes.length === 1 && e.firstChild.nodeType === 3);
                const i = spans.findIndex(e => /pattern holds/.test(e.textContent)); const j = spans.findIndex((e, k) => k >= i && /could eat[.]/.test(e.textContent));
                if (i < 0 || j < 0) return; const r = document.createRange(); r.setStart(spans[i].firstChild, spans[i].textContent.indexOf('the pattern')); r.setEnd(spans[j].firstChild, spans[j].textContent.indexOf('could eat.') + 10);
                spans[i].scrollIntoView({ block: 'center' }); const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.dispatchEvent(new Event('selectionchange')); spans[j].dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); }""")
            await pg.wait_for_timeout(600)
            q = pg.locator('button:visible', has_text='Quote note')
            if await q.count(): await q.first.click(); await pg.wait_for_timeout(400)
            await pg.evaluate("() => { const t = $('#rrText'); t.value = t.value.replace(/\\s*$/, '') + '\\n\\nThe strongest form of the argument: speed tracks the harvest. Check against the day counts in book IV.'; t.dispatchEvent(new Event('input', { bubbles: true })); }")
            await pg.wait_for_timeout(300)
            await shot('take-notes')
            await pg.evaluate("() => rrToggle(false)"); await pg.wait_for_timeout(300)
            await pg.click('#btnSide'); await pg.wait_for_timeout(300)
            await pg.evaluate("() => showReader(false)"); await pg.wait_for_timeout(300)
            await close_all()

        # Close to your notes: a sentence that repeats the Dakyns quotation without quotation marks
        if want('close-to-notes'):
            await pg.evaluate("""() => { const d = P.docs.find(x => /retreat|supply|march/i.test(x.title)) || P.docs[0]; openDoc(d.id);
                const p = document.createElement('p'); p.id = 'wkPx'; p.textContent = 'At the summit, presently they could hear the soldiers shouting and passing on the joyful word down the column.';
                const h = editor.querySelectorAll('h2')[0]; editor.insertBefore(p, h || null); onEdit(); switchTab('outline'); $('#sidebar').style.width = '400px'; renderCloseToNotes(); }""")
            await pg.wait_for_timeout(800)
            await pg.evaluate("() => { $('#pxList').previousElementSibling.scrollIntoView({ block: 'start' }); $('#wkPx').scrollIntoView({ block: 'center' }); }"); await pg.wait_for_timeout(300)
            await shot('close-to-notes')
            await pg.evaluate("() => { $('#wkPx')?.remove(); onEdit(); $('#sidebar').style.width = ''; }")
            await close_all()

        # Literature grid, with a few cells filled
        if want('lit-grid'):
            await pg.evaluate("""() => { const by = re => P.sources.find(s => re.test(s.csl.title || '')); const lee = by(/Greek Army/), eng = by(/Logistics/), wat = by(/Retreat/), bread = by(/Bread on the March/);
                const g = lgCfg(); g.rows = 'notes'; const c = g.cols, put = (s, i, t) => { if (s) (g.cells[s.id] = g.cells[s.id] || {})[c[i].id] = t; };
                put(eng, 0, 'Supply, not battle, set the limits of Alexander’s campaigns.'); put(eng, 1, 'Daily needs worked out per man and animal, from comparative data.'); put(eng, 3, 'About Alexander, not Xenophon; assumptions carried over.'); put(eng, 4, 'Ration figures, as a range.');
                put(lee, 0, 'The army was a mobile community, and its non-combatants shaped what it could do.'); put(lee, 1, 'Close reading of the Anabasis against comparative evidence.'); put(lee, 2, 'Non-combatants were numerous; food was a daily political question.'); put(lee, 4, 'Main secondary source for chapters 2 and 3.');
                put(wat, 0, 'The assemblies were genuinely deliberative.'); put(wat, 3, 'Little on supply.');
                if (bread) { put(bread, 0, 'The route through the hills was a search for stored grain.'); put(bread, 2, 'Halts track harvests; speed tracks stores.'); }
                const n = P.notes.find(x => x.sourceId === (lee || {}).id); if (n && !n.tags.includes('key findings')) n.tags.push('key findings');
                openDesk('lit'); }""")
            await pg.wait_for_timeout(700)
            await shot('lit-grid')
            await close_all()

        # Codes: a small codebook, a few coded passages and notes, the overview
        if want('codes'):
            await pg.evaluate("""() => { P.codes = []; const a = newCode('Supply shortage', '', 'Any mention of the army running short of food or fodder, or fearing it.'), b = newCode('Command', '', 'Who decides, and how: generals, assemblies, votes.'), c = newCode('Terrain', '', 'Mountains, rivers, snow and roads, where they shape movement.');
                const d = P.docs.find(x => /retreat|supply|march/i.test(x.title)) || P.docs[0]; openDoc(d.id);
                const paras = [...editor.querySelectorAll('p')].filter(x => [...x.childNodes].some(n => n.nodeType === 3 && n.data.length > 40));
                const code = (p, id, len) => { const t = [...p.childNodes].find(n => n.nodeType === 3 && n.data.length > 40); const r = document.createRange(); r.setStart(t, 0); r.setEnd(t, Math.min(len, t.data.length)); rmApply(r, 'cd', { ref: id }); };
                if (paras[0]) code(paras[0], a.id, 40); if (paras[1]) code(paras[1], b.id, 30); if (paras[2]) code(paras[2], a.id, 35); if (paras[3]) code(paras[3], c.id, 30);
                P.notes.filter(n => n.sourceId).forEach((n, i) => { n.codes = [[a.id], [a.id, c.id], [b.id], [a.id, b.id], [c.id]][i % 5]; });
                syncEditor(); rmDirty(); rmStyle(); openDesk('codes', '__over'); }""")
            await pg.wait_for_timeout(800)
            await shot('codes')
            await close_all()

        # Archive photos: three pages of a made-up letter, drawn by the browser for this guide
        if want('archive-photos'):
            files = await pg.evaluate("""async () => { const lines = [['Santa Fe, 21 August', 'Most excellent Lord,', 'I write in haste from the villa, where we', 'have held out these nine days against the', 'rebels, who have cut the acequia and the', 'roads to the south. Our stores of maize'], ['are near spent and the horses without', 'fodder. With the advice of the cabildo I', 'have resolved to leave the villa and march', 'down the river to join the people at', 'La Isleta, taking what grain remains', 'and the sacred vessels of the church.'], ['May God keep Your Excellency many years.', '', '', '', '', '']];
                const out = []; for (let k = 0; k < 3; k++) { const c = document.createElement('canvas'); c.width = 1500; c.height = 2000; const g = c.getContext('2d');
                  const grd = g.createLinearGradient(0, 0, 1500, 2000); grd.addColorStop(0, '#efe3c6'); grd.addColorStop(1, '#e2cfa3'); g.fillStyle = grd; g.fillRect(0, 0, 1500, 2000);
                  g.fillStyle = 'rgba(120,90,40,.08)'; for (let i = 0; i < 40; i++) { g.beginPath(); g.arc(Math.random() * 1500, Math.random() * 2000, 20 + Math.random() * 120, 0, 7); g.fill(); }
                  g.fillStyle = '#3b2a17'; g.font = 'italic 64px Georgia, serif'; lines[k].forEach((t, i) => g.fillText(t, 150 + (i === 0 && k === 0 ? 500 : 0), 260 + i * 150));
                  if (k === 2) { g.font = 'italic 70px Georgia, serif'; g.fillText('The Governor', 760, 560); }
                  const b = await new Promise(r => c.toBlob(r, 'image/jpeg', .85)); out.push(Array.from(new Uint8Array(await b.arrayBuffer()))); } return out; }""")
            tmpd = pathlib.Path(tempfile.mkdtemp()); paths = []
            for i, f in enumerate(files):
                pth = tmpd / f'IMG_{4211 + i}.jpg'; pth.write_bytes(bytes(f)); paths.append(str(pth))
            await pg.evaluate("""() => { const src = { id: uid('s'), csl: { type: 'manuscript', title: 'Papers of a provincial governor (sample)', archive: 'Sample archive for this guide' }, stype: 'primary', created: nowISO(), modified: nowISO() }; src.csl.id = src.id; P.sources.push(src); renderSourceList(); openPhotos(src.id); }""")
            await pg.set_input_files('#phFile', paths[:1]); await pg.wait_for_function("() => phList().length === 1", timeout=15000); await pg.wait_for_timeout(500)
            await pg.fill('#ph_box', '3'); await pg.fill('#ph_folder', '12'); await pg.fill('#ph_item', '1'); await pg.wait_for_timeout(1000)
            await pg.set_input_files('#phFile', paths[1:]); await pg.wait_for_function("() => phList().length === 3", timeout=20000); await pg.wait_for_timeout(500)
            await pg.evaluate("() => { const l = phList(); l[1].item = '2'; l[2].item = '3'; PH.cur = l[0].id; l[0].date = '21 August 1680'; l[0].caption = 'Letter, the governor to the viceroy (sample)'; l[0].text = 'Santa Fe, 21 August\\n\\nMost excellent Lord,\\nI write in haste from the villa, where we have held out these nine days against the rebels, who have cut the acequia and the roads to the south. Our stores of maize'; phRender(); }")
            await pg.wait_for_timeout(1200)
            await shot('archive-photos', '#phDlg .dlg', pad=0)
            await pg.click('#phClose'); await close_all()

        # The research guide, on the stages
        if want('research-guide'):
            await pg.evaluate("() => { PREFS.gdStage = 'research question'; openGuide('stages'); }"); await pg.wait_for_timeout(700)
            await pg.evaluate("() => $('[data-gdstage=\"research question\"]')?.scrollIntoView({ block: 'start' })"); await pg.wait_for_timeout(300)
            await shot('research-guide')
            await close_all()

        # Research journal, open on the log with the prompts
        await pg.evaluate("() => openJournal('log')"); await pg.wait_for_timeout(900)
        await pg.evaluate("() => { const b = document.querySelector('[data-jp=\"3\"]'); if (b) b.click(); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const t = $('#jText'); if (t) { t.value += 'Did supply, more than the Persians, decide the route and pace of the retreat?'; } }")
        await shot('journal')
        await close_all()

        # Socrates, with a claim selected
        await pg.evaluate("() => { const d = P.docs.find(x => /retreat|supply|march/i.test(x.title)) || P.docs[0]; openDoc(d.id); switchTab('research'); }"); await pg.wait_for_timeout(600)
        claim = await pg.evaluate("""() => { const m = editor.innerText.match(/Where villages had grain[^.]*[.]/); return m ? m[0].trim() : ''; }""")
        if want('socrates'):
            await pg.evaluate("c => openSocrates({ fresh: true, about: c })", claim); await pg.wait_for_timeout(600)
            await shot('socrates', '#socDlg .dlg')
            await close_all()
        if want('examine'):
            await pg.evaluate("c => socTalkOpen(c)", claim); await pg.wait_for_timeout(500)
            await pg.fill('#socIn', 'Marching on most days, with no halt longer than a night, until the next village with stores.')
            await pg.press('#socIn', 'Enter'); await pg.wait_for_timeout(800)
            await shot('examine', '#socDlg .dlg')
            await close_all()

        # The Oracle beside the writing
        if want('oracle'):
            await pg.click('#btnOracle'); await pg.wait_for_timeout(600)
            for t in ['I think supply decided the route more than the Persians did.', 'what have I written about grain?']:
                await pg.fill('#orcIn', t); await pg.press('#orcIn', 'Enter'); await pg.wait_for_timeout(500)
            await pg.evaluate("() => { const l = $('#orcLog'); if (l) l.scrollTop = l.scrollHeight; }")
            await shot('oracle')
            await close_all()

        # Outline checks, with a few things for them to find
        if want('outline-checks'):
            await pg.set_viewport_size({'width': W, 'height': 1180})
            await pg.evaluate("""() => { const p = document.createElement('p'); p.id = 'wkChk';
                p.innerHTML = 'The LOC ran along the coast after Trapezus, and supplies may have come by sea for the first time. How many ships the army found is still <span class="flag flag-tk" data-kind="tk" data-note="ships at Trapezus" contenteditable="false">TK</span>.';
                editor.insertBefore(p, editor.querySelectorAll('h2')[1] || null); onEdit(); renderOutline(); $('#sidebar').style.width = '400px'; const t = $('#estToggle'); t.checked = true; t.dispatchEvent(new Event('change')); switchTab('outline'); }""")
            await pg.wait_for_timeout(2000)
            await shot('outline-checks', '#sidebar', pad=0)
            await pg.evaluate("() => { $('#wkChk')?.remove(); onEdit(); $('#sidebar').style.width = ''; const t = $('#estToggle'); t.checked = false; t.dispatchEvent(new Event('change')); }")
            await pg.set_viewport_size({'width': W, 'height': H})

        # Proofread, on a paragraph with a few mistakes
        if want('proofread'):
            await pg.evaluate("() => { const p = document.createElement('p'); p.id = 'wkProof'; p.innerHTML = 'The army recieved alot of grain at Trapezus, wich was more then it needed, and the the generals would of agreed.'; editor.insertBefore(p, editor.children[3]); syncEditor(); }")
            await pg.keyboard.press('F7'); await pg.wait_for_timeout(500)
            await shot('proofread', '#proofDlg .dlg')
            await close_all()
            await pg.evaluate("() => { $('#wkProof')?.remove(); syncEditor(); }")

        # Export menu
        if want('export-menu'):
            await pg.set_viewport_size({'width': W, 'height': 1100})
            await pg.click('#btnExport'); await pg.evaluate("() => { $('#exportMenu').style.maxHeight = 'none'; }"); await pg.wait_for_timeout(400)
            await shot('export-menu', '#exportMenu', pad=10)
            await pg.evaluate("() => { $('#exportMenu').style.maxHeight = ''; }")
            await pg.set_viewport_size({'width': W, 'height': H})
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)

        # Abstract and keywords
        if want('abstract'):
            await pg.set_viewport_size({'width': W, 'height': 1000})
            await pg.evaluate('openAbstract()'); await pg.wait_for_timeout(400)
            await pg.click('#absSuggest'); await pg.wait_for_timeout(300)
            await pg.click('#absKwSug'); await pg.wait_for_timeout(300)
            for k in ['Xenophon', 'grain']:
                bt = pg.locator(f'#absKwPick [data-kw-add="{k}"]')
                if await bt.count(): await bt.click()
            await pg.wait_for_timeout(300)
            await shot('abstract', '#absDlg .dlg')
            await close_all()
            await pg.set_viewport_size({'width': W, 'height': H})

        await b.close()
        if errs: sys.exit('page errors: ' + '; '.join(errs))
    try:  # interface screenshots need far fewer than 16 million colors
        from PIL import Image
        for f in OUT.glob('*.png'): Image.open(f).convert('RGB').quantize(colors=192, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
    except ImportError: pass
    print('wrote', len(list(OUT.glob('*.png'))), 'screenshots to', OUT.relative_to(ROOT))


if __name__ == '__main__':
    asyncio.run(main(set(sys.argv[1:])))
