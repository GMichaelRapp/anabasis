"""2.6.0: close to your notes, PDF highlights, the literature grid, codes, archive photos, pseudonyms and consent,
the retraction check (Crossref mocked), duplicate sources, the reading list, evidence fingerprints, the research
guide, a round trip through the project file, and the lock dialog's own ids."""
import asyncio, glob, json, sys, tempfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

FIX = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fixtures', 'sample.pdf')


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))")
        sent = []
        async def crossref(route):
            u = route.request.url; sent.append(u)
            body = {'message': {'type': 'journal-article', 'title': ['A study'], 'updated-by': [{'type': 'retraction', 'DOI': '10.9/notice', 'updated': {'date-parts': [[2021, 3, 4]]}, 'source': 'retraction-watch'}]}} if 'retracted' in u else {'message': {'type': 'journal-article', 'title': ['Fine']}}
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
        await ctx.route('https://api.crossref.org/**', crossref)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---- close to your notes
        r = await pg.evaluate("""() => { const s = P.sources[0]; const n = Object.assign(newNote(), { kind: 'quote', title: 'Halts', sourceId: s.id, locator: '12', body: 'The generals chose valleys over passes when the valleys were inhabited, and they halted for days where the stores were large.' }); P.notes.push(n);
          const p = document.createElement('p'); p.id = 'pxT'; p.textContent = 'In the hills the generals chose valleys over passes when the valleys were inhabited, which tells us much. Elsewhere, as Lee says, “they halted for days where the stores were large.”';
          editor.prepend(p); onEdit(); switchTab('outline'); renderCloseToNotes(); return { n: PX.length, words: PX[0] && PX[0].words, text: PX[0] && PX[0].text }; }""")
        check('close to your notes: a quote note’s wording outside quotation marks is found, quoted wording isn’t', r['n'] == 1 and r['words'] >= 10 and r['text'].startswith('the generals chose'), r)
        await pg.click('[data-pxq="0"]'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("() => ({ t: $('#pxT').textContent, cites: $$('#pxT .cite').length, left: PX.length })")
        check('…Add quotation marks quotes it and cites the note’s source', '“the generals chose valleys over passes when the valleys were inhabited”' in r['t'] and r['cites'] == 1 and r['left'] == 0, r)
        r = await pg.evaluate("() => { const n = P.notes.find(x => x.title === 'Halts'); n.kind = 'idea'; PX_IX.key = ''; const p = document.createElement('p'); p.id = 'pxI'; p.textContent = 'The generals chose valleys over passes when the valleys were inhabited and the harvest was in.'; editor.prepend(p); onEdit(); renderCloseToNotes(); return PX.length; }")
        check('…your own idea notes are never flagged', r == 0, r)
        await pg.evaluate("() => { $('#pxT').remove(); $('#pxI').remove(); onEdit(); }")

        # ---- PDF highlights
        await pg.evaluate("() => showReader(true)")
        await pg.set_input_files('#filePdf', FIX); await pg.wait_for_timeout(2500)
        await pg.evaluate("() => { const s = P.sources[0]; $('#rdSource').value = s.id; $('#rdSource').dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(600)
        await pg.evaluate("""() => { const sp = [...document.querySelectorAll('#reader .textLayer span')].filter(e => e.textContent.trim().length > 10); const r = document.createRange(); r.setStart(sp[0].firstChild, 0); r.setEnd(sp[0].firstChild, sp[0].textContent.length); getSelection().removeAllRanges(); getSelection().addRange(r); }""")
        await pg.wait_for_timeout(400); await pg.click('#rdSelBar [data-k=quote]'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ hl: P.notes[0].pdfHl, marks: $$('.rd-hl').length, pins: $$('.rd-hl-pin').length })")
        check('a quote from the PDF keeps where it was on the page, and shows as a highlight with a marker', r['hl'] and r['hl'][0]['p'] == 1 and all(0 <= v <= 1 for q in r['hl'][0]['r'] for v in q) and r['marks'] >= 1 and r['pins'] == 1, r)
        await pg.evaluate("() => layoutPages()"); await pg.wait_for_timeout(1500)
        check('…the highlight is drawn again when the pages are', await pg.evaluate("() => $$('.rd-hl').length") >= 1)
        await pg.click('.rd-hl-pin'); await pg.wait_for_timeout(300)
        check('…and its marker opens the note', await pg.evaluate("() => panelState && panelState.id === P.notes[0].id"))
        await pg.evaluate("() => { closePanel && closePanel(); showReader(false); }")

        # ---- literature grid
        await pg.evaluate("() => { P.notes.find(n => n.sourceId)?.tags.push('main argument'); openDesk('lit'); }"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ rows: $$('#deskBody tbody tr').length, cols: P.litGrid.cols.map(c => c.name), notes: $$('.lg-note').length, q: $('#lgAddQ') ? $('#lgAddQ').options.length : 0 })")
        check('literature grid: sources with notes against five starting columns, with tagged notes in the cells', r['rows'] >= 2 and r['cols'][0] == 'Main argument' and len(r['cols']) == 5 and r['notes'] >= 1, r)
        await pg.fill('.lg-cell >> nth=0', 'Supply set the route.'); await pg.wait_for_timeout(500)
        await pg.select_option('#lgAddQ', index=1); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ first: P.litGrid.cols[0].q, cells: JSON.stringify(P.litGrid.cells) })")
        check('…cells are kept, and a research question can be a column', bool(r['first']) and 'Supply set the route.' in r['cells'], r)
        async with pg.expect_download() as dl:
            await pg.click('#deskTools >> text=Download CSV')
        csv = open(await (await dl.value).path(), encoding='utf-8-sig').read()
        check('…as CSV', csv.startswith('"Source","Title"') and 'Supply set the route.' in csv, csv[:120])
        await pg.click('#deskTools >> text=Make a document'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ t: curDoc().title, rows: $$('#editor table tr').length, cites: editor.querySelectorAll('.cite').length })")
        check('…and as a document with each source cited', r['t'] == 'Literature Review Grid' and r['rows'] >= 3 and r['cites'] >= 2, r)
        await pg.evaluate("() => { const d = P.docs.find(x => x.title !== 'Literature Review Grid'); openDoc(d.id); }"); await pg.wait_for_timeout(500)

        # ---- codes
        sel = """n => { const ps = [...editor.querySelectorAll('p')].filter(x => x.textContent.length > 100 && [...x.childNodes].some(c => c.nodeType === 3 && c.data.length > 30));
            const t = [...ps[n].childNodes].find(c => c.nodeType === 3 && c.data.length > 30); const r = document.createRange(); r.setStart(t, 0); r.setEnd(t, 20); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); }"""
        await pg.evaluate(sel, 0); await pg.evaluate("openCodePick()"); await pg.wait_for_timeout(200)
        await pg.fill('#cdName', 'Supply shortage'); await pg.fill('#cdDef', 'Running short of food or fodder.'); await pg.click('#cdNew'); await pg.wait_for_timeout(400)
        await pg.evaluate(sel, 1); await pg.keyboard.press('Control+Alt+g'); await pg.keyboard.press('k'); await pg.wait_for_timeout(300)
        check('Mark → Code passage (K) opens the codebook', await pg.evaluate("() => $('#cdDlg').open"))
        await pg.click('#cdPickList [data-cd]'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ codes: P.codes.length, marks: editor.querySelectorAll('.rm[data-k=cd]').length, def: P.codes[0].def })")
        check('codes: a code with its definition, on two passages', r == {'codes': 1, 'marks': 2, 'def': 'Running short of food or fodder.'}, r)
        await pg.evaluate("() => { switchTab('notes'); openNote(P.notes[0].id); }"); await pg.wait_for_timeout(300)
        await pg.select_option('#nCodes select', label='Supply shortage'); await pg.wait_for_timeout(200)
        await pg.select_option('#nCodes select', '__new'); await pg.wait_for_timeout(200); await pg.fill('#askInput', 'Command'); await pg.click('#askOk'); await pg.wait_for_timeout(300)
        check('…notes take codes, new ones too', await pg.evaluate("() => P.notes[0].codes.length === 2 && $$('#nCodes .cd-chip').length === 2"))
        await pg.evaluate("() => { closePanel && closePanel(); openDesk('codes', P.codes[0].id); }"); await pg.wait_for_timeout(500)
        check('…the desk lists everything under a code', await pg.evaluate("() => $$('#deskBody .cd-list li').length") == 3)
        await pg.click('#deskBody .desk-list li >> nth=0'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ rows: $$('#deskBody .cd-mx tbody tr').length, co: $('#deskBody .cd-co')?.textContent || '' })")
        check('…counts codes by document and source, and the codes that turn up together', r['rows'] == 2 and 'Supply shortage' in r['co'] and 'Command' in r['co'], r)
        async with pg.expect_download() as dl:
            await pg.click('#deskTools >> text=Codebook (.md)')
        md = open(await (await dl.value).path(), encoding='utf-8').read()
        check('…and exports the codebook', '## Supply shortage' in md and 'Running short of food' in md, md[:100])
        h = await pg.evaluate("() => buildExport(curDoc(), 'html')")
        check('…code marks never reach an export', 'data-k="cd"' not in (h if isinstance(h, str) else json.dumps(h)))
        await pg.evaluate("() => closeDesk()")

        # ---- archive photos (three different images drawn by the browser)
        files = await pg.evaluate("""async () => { const out = []; for (let i = 0; i < 3; i++) { const c = document.createElement('canvas'); c.width = 900; c.height = 600; const g = c.getContext('2d'); g.fillStyle = '#efe6d2'; g.fillRect(0, 0, 900, 600); g.fillStyle = '#333'; for (let y = 60 + i * 9; y < 560; y += 40) g.fillRect(60, y, 700 - i * 90, 4);
            const b = await new Promise(r => c.toBlob(r, 'image/jpeg', .9)); out.push(Array.from(new Uint8Array(await b.arrayBuffer()))); } return out; }""")
        tmp = tempfile.mkdtemp(); paths = []
        for i, f in enumerate(files):
            p = _os.path.join(tmp, f'IMG_00{i}.jpg'); open(p, 'wb').write(bytes(f)); paths.append(p)
        await pg.evaluate("() => openPhotos()"); await pg.select_option('#phSrc', '__new'); await pg.wait_for_timeout(200)
        await pg.fill('#askInput', 'Papers of a provincial governor'); await pg.click('#askOk'); await pg.wait_for_timeout(300)
        await pg.set_input_files('#phFile', paths[:1]); await pg.wait_for_timeout(1500)
        await pg.fill('#ph_box', '3'); await pg.fill('#ph_folder', '12'); await pg.fill('#ph_item', '4')
        await pg.fill('#phText', 'The Spaniards withdrew from Santa Fe on the twenty-first of August.'); await pg.wait_for_timeout(1200)
        await pg.set_input_files('#phFile', paths); await pg.wait_for_timeout(2500)
        r = await pg.evaluate("() => { const s = phSrc(); return { n: s.photos.length, type: s.csl.type, hash: s.photos.every(f => /^[0-9a-f]{64}$/.test(f.sha256)), inherit: s.photos.slice(1).map(f => f.box + '/' + f.folder), img: !!$('#phImg') }; }")
        check('archive photos: a new collection, photos added once each with a fingerprint, new ones filed under the box and folder you were on', r == {'n': 3, 'type': 'manuscript', 'hash': True, 'inherit': ['3/12', '3/12'], 'img': True}, r)
        await pg.evaluate("() => { PH.cur = phSrc().photos[0].id; phRender(); }"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { const t = $('#phText'); t.focus(); t.setSelectionRange(4, 40); }"); await pg.click('#phQuote'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ loc: P.notes[0].locator, body: P.notes[0].body, linked: P.notes[0].photo === phSrc().photos[0].id, listed: $$('#phNotes [data-phn]').length })")
        check('…a quote note from the transcription cites the box, folder and item', r == {'loc': 'box 3, folder 12, item 4', 'body': 'Spaniards withdrew from Santa Fe on', 'linked': True, 'listed': 1}, r)
        await pg.keyboard.press('ArrowRight'); await pg.evaluate("() => $('#phDlg').focus()"); await pg.wait_for_timeout(100)
        await pg.click('#phNext'); await pg.wait_for_timeout(400)
        check('…and you can step through them', await pg.evaluate("() => phList().indexOf(phCur())") >= 1)
        await pg.click('#phClose')

        # ---- pseudonyms and consent
        r = await pg.evaluate("""() => { const p = document.createElement('p'); p.id = 'psT'; p.textContent = 'Maria Ortega told me the convoy stopped twice. Ortega was sure of it.'; editor.prepend(p); onEdit();
          P.entities.push({ id: uid('e'), name: 'Maria Ortega', kind: 'person', variants: [], note: '', pseudo: 'Ana', aka: ['Ortega'], consent: 'withdrawn' });
          const h = buildExport(curDoc(), 'html'), t = typeof h === 'string' ? h : JSON.stringify(h); renderOutline();
          return { real: t.includes('Ortega'), ana: (t.match(/Ana\\b/g) || []).length, draft: $('#psT').textContent.includes('Maria Ortega'), flag: $('#nameList').textContent }; }""")
        check('pseudonyms: every form of the name is replaced in exports, the draft keeps the real name', not r['real'] and r['ana'] == 2 and r['draft'], r)
        check('…and a person who withdrew consent is flagged in the Outline', 'consent withdrawn' in r['flag'], r['flag'])
        await pg.evaluate("() => { P.pseudoOn = false; }")
        r = await pg.evaluate("() => { const h = buildExport(curDoc(), 'html'); return (typeof h === 'string' ? h : JSON.stringify(h)).includes('Maria Ortega'); }")
        check('…they can be switched off', r)
        await pg.evaluate("() => { P.pseudoOn = true; $('#psT').remove(); onEdit(); }")

        # ---- retractions, duplicates, the reading list, fingerprints
        await pg.evaluate("""() => { const mk = (title, doi, extra) => { const s = Object.assign({ id: uid('s'), csl: { type: 'article-journal', title, DOI: doi, author: [{ family: 'Smith', given: 'A.' }], issued: { 'date-parts': [[2019]] } }, created: nowISO(), modified: nowISO() }, extra || {}); s.csl.id = s.id; P.sources.push(s); return s; };
          const a = mk('Grain supply in the Persian empire', '10.1/retracted'), b2 = mk('Grain Supply in the Persian Empire', ''); b2.csl.publisher = 'Brill';
          const p = document.createElement('p'); p.innerHTML = 'Test ' + citeHTML([{ id: b2.id }]); editor.prepend(p); onEdit();
          const n = newNote(); n.sourceId = b2.id; n.body = 'x'; P.notes.push(n); renderSourceList(); window._ab = [a.id, b2.id, n.id]; }""")
        await pg.evaluate("() => openRetractions()"); await pg.click('#rcRun'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("() => ({ worst: rcWorst(P.sources.find(s => s.id === _ab[0])), sum: $('#rcSum').textContent, badge: $(`#sourceList [data-id='${_ab[0]}'] .rc-bad`)?.textContent })")
        check('retractions: Crossref’s notice is found and shown on the source', r['worst'] == 'retraction' and '1 with a retraction' in r['sum'] and r['badge'] == 'Retracted', r)
        check('…only the DOIs went to Crossref', sent and all(u.startswith('https://api.crossref.org/works/') for u in sent) and any('retracted' in u for u in sent), sent)
        await pg.click('#rcClose')
        await pg.evaluate("() => openDups()"); await pg.wait_for_timeout(300)
        check('duplicates: the same title, author and year are found', await pg.evaluate("() => DUPS.length === 1 && DUPS[0].why.startsWith('Same title')"))
        await pg.click('#dupBody [data-keep=a]'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => { const a = P.sources.find(s => s.id === _ab[0]); return { gone: !P.sources.some(s => s.id === _ab[1]), filled: a.csl.publisher, note: P.notes.find(n => n.id === _ab[2]).sourceId === a.id, cite: P.docs.some(d => d.html.includes(_ab[0])) && !P.docs.some(d => d.html.includes(_ab[1])) }; }")
        check('…merging keeps one, fills its gaps, and moves citations and notes across', r == {'gone': True, 'filled': 'Brill', 'note': True, 'cite': True}, r)
        await pg.click('#dupClose')
        await pg.evaluate("() => { switchTab('sources'); openSource(_ab[0]); }"); await pg.wait_for_timeout(300)
        await pg.check('#srcPrio'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => { const a = P.sources.find(s => s.id === _ab[0]); return { read: a.read, prio: a.prio, chip: $('#srcChips').textContent.includes('To read 1'), home: looseEnds().toread.length, bad: looseEnds().retracted.length }; }")
        check('reading list: Read this first puts it on the list, with a filter and a place on Project home', r == {'read': 'toread', 'prio': 1, 'chip': True, 'home': 1, 'bad': 1}, r)
        await pg.click('#panelBody .src-ev summary')
        async with pg.expect_file_chooser() as fc:
            await pg.click('#panelBody [data-a=evadd]')
        await (await fc.value).set_files(FIX); await pg.wait_for_timeout(600)
        r = await pg.evaluate("() => { const a = P.sources.find(s => s.id === _ab[0]); return { n: a.evidence.length, h: a.evidence[0].sha256 }; }")
        check('evidence: a file’s SHA-256 is worked out in the browser', r['n'] == 1 and len(r['h']) == 64, r)
        async with pg.expect_file_chooser() as fc:
            await pg.click('#panelBody [data-a=evcheck]')
        await (await fc.value).set_files(FIX); await pg.wait_for_timeout(600)
        check('…and a copy can be checked against it', 'Matches.' in await pg.evaluate("() => $('#infoBody').textContent"))
        await pg.click('#infoOk')
        async with pg.expect_file_chooser() as fc:
            await pg.click('#panelBody [data-a=evcheck]')
        await (await fc.value).set_files(paths[0]); await pg.wait_for_timeout(600)
        check('…a photo from the archive matches its own fingerprint', 'Matches.' in await pg.evaluate("() => $('#infoBody').textContent"))
        await pg.click('#infoOk')

        # ---- research guide
        await pg.evaluate("() => openGuide()"); await pg.wait_for_timeout(400)
        g = await pg.evaluate("() => { const G = guideData(); return { stages: J_PROMPTS.every(p => G.stage[p[0]] && G.stage[p[0]].parts.Do && G.stage[p[0]].parts['Done when']), checks: G.check.length, items: G.check.reduce((n, c) => n + c.items.length, 0), methods: Object.keys(G.method).every(k => J_TPL[k]) && Object.keys(G.method).length === Object.keys(J_TPL).length, terms: G.term.length, see: G.term.every(t => t.see.every(x => G.term.some(y => y.title.toLowerCase() === x.toLowerCase() || y.key === x.toLowerCase()))) }; }")
        check('research guide: every stage has a guide, every method in the design has one, and every glossary cross-reference resolves', g['stages'] and g['methods'] and g['checks'] >= 5 and g['items'] >= 40 and g['terms'] >= 50 and g['see'], g)
        await pg.click('[data-gdtab=checks]'); await pg.check('[data-gdc=submit][data-gdi=flags]'); await pg.wait_for_timeout(200)
        check('…checklist ticks are saved with the project', await pg.evaluate("() => !!jr().checks.submit.flags"))
        await pg.click('[data-gdtab=stages]'); await pg.click('[data-gdwrite="0"]'); await pg.wait_for_timeout(400)
        check('…and Write about this starts a log entry for the stage', await pg.evaluate("() => PREFS.jSec === 'log' && $('#jText').value.startsWith('Research topic')"))
        await pg.evaluate("() => closeDesk()")

        # ---- the project file keeps it all, and rejects nonsense
        r = await pg.evaluate("""() => { syncEditor(); const j = JSON.parse(JSON.stringify(P)); j.notes[0].pdfHl = [{ p: 1, r: [[2, -1, .5, .1]] }, { p: 'x', r: [] }]; j.sources[0].evidence = [{ sha256: 'nope' }]; j.codes.push({ id: 'cdX', name: 'X', color: 'red' });
          const n = normalize(j); const ph = n.sources.find(s => s.photos); return { hl: JSON.stringify(n.notes[0].pdfHl), ev: !!n.sources[0].evidence, color: n.codes.find(c => c.id === 'cdX').color, grid: n.litGrid.cols.length, photos: ph ? ph.photos.length : 0, checks: !!n.journal.checks.submit, ent: n.entities.find(e => e.pseudo === 'Ana')?.consent }; }""")
        check('the project file keeps the new records and cleans damaged ones', r['hl'] == '[{"p":1,"r":[[1,0,0.5,0.1]]}]' and not r['ev'] and r['color'].startswith('#') and r['grid'] >= 5 and r['photos'] == 3 and r['checks'] and r['ent'] == 'withdrawn', r)

        # ---- the lock dialog no longer shares ids with Check links
        check('the lock dialog and Check links have their own dialogs', await pg.evaluate("() => $$('#lkDlg').length === 1 && !!$('#lockDlg') && $('#lkDlg h3').textContent === 'Check links'"))

        check('no errors', not errs, errs[:5])
        await b.close()
    print('t46', 'OK' if ok else 'FAILED')
    sys.exit(0 if ok else 1)

asyncio.run(main())
