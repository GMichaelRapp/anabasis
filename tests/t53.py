"""2.8.0: the revision pass, a book for print, submission packages, a Zotero library file, editing marks from a reviewer,
and the faster citation engine."""
import asyncio, io, json, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

CH1 = ('<h1>The Dry Year</h1><p>At the end of the day the well ran dry. The town met in the hall that night. They argued until the lamps went out. '
       'Nobody had a plan for the summer. The mayor spoke first and quickly. The banker spoke second and slowly.</p>'
       '<p>The implementation of the ration was debated at length. It was decided by the council that water would be shared. Ada Ferro kept the minutes of every meeting.</p>')
CH2 = '<h1>The Rain</h1><p>Rain came in September. The creeks filled overnight, and the town walked down to the river to watch it rise.</p>'
FM = '<h1>Acknowledgments</h1><p>Thanks to the archivists of Quay County for their patience.</p>'
BM = '<h1>A note on sources</h1><p>The council minutes are held in the county clerk’s office.</p>'


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    _os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Ada Ferro',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        # ---- the citation engine: built after the window paints, and faster
        r = await pg.evaluate("({ memo: !!CSL.XmlJSON.prototype.__memo, refs: $('#refs').innerHTML.length > 0 })")
        check('the citation engine remembers macro lookups, and the references still render at startup', r == {'memo': True, 'refs': True}, r)
        r = await pg.evaluate("""(() => { const pr = CSL.XmlJSON.prototype, memo = pr.getNodesByName, bad = [];
            const run = st => { const e = new CSL.Engine({ retrieveLocale: l => cslLocaleText(l), retrieveItem: itemFor }, cslXml(st), 'en-US'); const ids = P.sources.map(s => s.id); e.updateItems(ids);
              return ids.map(id => e.makeCitationCluster([{ id, locator: '4', label: 'page' }])).join('|') + e.makeBibliography()[1].join(''); };
            for (const st of ['chicago-notes-bibliography-17th-edition', 'apa', 'modern-language-association', 'harvard-cite-them-right'].filter(k => k in STYLES)) { pr.getNodesByName = pr.__plain; const a = run(st); pr.getNodesByName = memo; if (run(st) !== a) bad.push(st); }
            pr.getNodesByName = memo; return bad; })()""")
        check('…and gives exactly the same citations and bibliography', r == [], r)

        # ---- a project to work on
        await pg.evaluate("""([fm, c1, c2, bm]) => { dirtyFile = false; P = blankProject(); P.title = 'The Dry Year';
            const mk = (t, h, role) => { const d = newDoc(t, h); d.role = role; P.docs.push(d); return d; };
            mk('Acknowledgments', fm, 'front'); mk('The Dry Year', c1, 'body'); mk('The Rain', c2, 'body'); mk('A note on sources', bm, 'back');
            openDoc(P.docs[1].id, true); renderAll(); }""", [FM, CH1, CH2, BM]); await pg.wait_for_timeout(500)

        # ---- the revision lens and the Revision desk
        r = await pg.evaluate("(() => { const s = lensScan(LENS_BLOCKS(editor), false); return { N: s.N, words: s.words }; })()")
        check('the lens finds clichés, -ly adverbs, buried verbs, passive voice and same-length runs', r['N']['cliche'] >= 1 and r['N']['adverb'] >= 2 and r['N']['nominal'] >= 1 and r['N']['passive'] >= 1 and r['N']['rhythm'] >= 1, r)
        r = await pg.evaluate("(() => { toggleLens(true); const chips = $$('#lensBar [data-l]').map(c => [c.dataset.l, c.classList.contains('off')]); toggleLens(false); return chips; })()")
        check('…the quieter checks start switched off', dict(r).get('adverb') is True and dict(r).get('nominal') is True and dict(r).get('cliche') is False and dict(r).get('long') is False, r)
        await pg.evaluate("openDesk('revision')"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ rows: $$('#deskBody .rev-table tbody tr').map(t => t.querySelector('th').textContent), checks: $$('#deskBody [data-revk]').length, head: $('#deskBody .rev-check h3')?.textContent })")
        check('Research desk → Revision: a row for each chapter, and the selected chapter’s checklist', r['rows'] == ['The Dry Year', 'The Rain'] and r['checks'] == 9 and 'The Dry Year' in r['head'], r)
        await pg.evaluate("() => { const c = $('#deskBody [data-revk=aloud]'); c.checked = true; c.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ rev: P.docs[1].revision, bar: $('#deskBody .rev-table tbody tr.on td:last-child').textContent.trim() })")
        check('…ticking an item dates it and fills the bar', list(r['rev'].keys()) == ['aloud'] and len(r['rev']['aloud']) == 10 and r['bar'].endswith('1/9'), r)
        check('…the checklist survives saving', await pg.evaluate("normalize(JSON.parse(JSON.stringify(P))).docs[1].revision.aloud === P.docs[1].revision.aloud && !normalize({ docs: [{ id: 'x', html: '', revision: { aloud: 5, junk: 'x' } }] }).docs[0].revision.aloud"))
        async with pg.expect_download() as dl:
            await pg.evaluate("$$('#deskTools button').find(b => b.textContent === 'CSV').click()")
        d = await dl.value; p = OUT + '/rev.csv'; await d.save_as(p); csv = open(p, encoding='utf-8-sig').read().splitlines()
        check('…and goes out as a CSV', len(csv) == 3 and csv[0].startswith('"Document","Words"') and csv[1].startswith('"The Dry Year"') and csv[1].endswith('"1/9"'), csv[:2])
        await pg.evaluate("closeDesk()")

        # ---- a book for print
        await pg.evaluate("openBook()"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ sum: $('#bkSum').textContent, author: $('#bkAuthor').value, trims: $$('#bkTrim option').length })")
        check('Export → Book for print counts the chapters and front and back matter', r['sum'].startswith('2 chapters, 1 front matter, 1 back matter') and r['author'] == 'Ada Ferro' and r['trims'] == 10, r)
        await pg.evaluate("() => { $('#bkTrim').value = '5.5x8.5'; $('#bkSubtitle').value = 'A town and its water'; $('#bkPublisher').value = 'Mesa Press'; $('#bkIsbn').value = '978-0-00-000000-0'; $('#bkDlg').dispatchEvent(new Event('input')); $('#bkCancel').click(); }")
        r = await pg.evaluate("({ trim: P.book.trim, isbn: P.book.isbn, kept: normalize(JSON.parse(JSON.stringify(P))).book.publisher })")
        check('…its settings are kept with the project', r == {'trim': '5.5x8.5', 'isbn': '978-0-00-000000-0', 'kept': 'Mesa Press'}, r)
        html = await pg.evaluate("bookHTML(bookOpts())")
        check('…a page the size of the trim, with mirrored margins', '@page{size:5.5in 8.5in' in html and '@page:left{margin-left:0.5in;margin-right:0.75in' in html and '@page:right{margin-left:0.75in;margin-right:0.5in' in html)
        check('…half title, title page and a copyright page with the ISBN and publisher', 'class="bk-half"' in html and 'A town and its water' in html and 'ISBN 978-0-00-000000-0' in html and 'Published by Mesa Press' in html and 'Copyright ©' in html)
        check('…front matter, then numbered chapters, then back matter, each opening on a right-hand page', html.index('Acknowledgments</h1>') < html.index('Chapter 1') < html.index('Chapter 2') < html.index('A note on sources</h1>') and '.bk-sec{break-before:right}' in html)
        bp = await ctx.new_page(); await bp.set_content(html);
        await bp.wait_for_function("document.querySelectorAll('.pagedjs_page').length > 0 && [...document.querySelectorAll('.pagedjs_page')].every(p => p.dataset.folio)", timeout=60000)
        r = await bp.evaluate("""(() => { const pages = [...document.querySelectorAll('.pagedjs_page')]; const at = sel => { const e = document.querySelector(sel); const p = e && e.closest('.pagedjs_page'); return p ? p.dataset.folio : null; };
            return { n: pages.length, first: pages.slice(0, 3).map(p => p.dataset.folio), ack: at('.bk-fm h1'), ch1: at('.bk-ch h1'), toc: [...document.querySelectorAll('.bk-toc a')].map(a => [a.textContent, a.dataset.folio]),
              ch1page: (() => { const e = document.querySelector('.bk-ch h1'); return [...pages].indexOf(e.closest('.pagedjs_page')) % 2; })() }; })()""")
        await bp.close()
        check('…laid out: roman page numbers in the front matter, 1 at the first chapter', r['first'] == ['i', 'ii', 'iii'] and r['ack'] not in (None, '1') and not r['ack'].isdigit() and r['ch1'] == '1', r)
        check('…the first chapter on a right-hand page', r['ch1page'] == 0, r)
        check('…and the contents carry the page numbers', [t[0] for t in r['toc']] == ['Acknowledgments', 'The Dry Year', 'The Rain', 'A note on sources'] and r['toc'][1][1] == '1' and all(t[1] for t in r['toc']), r['toc'])

        # ---- a submission package
        await pg.evaluate("openSubPackage(P.docs[1].id)"); await pg.wait_for_timeout(200)
        await pg.fill('#spkName', 'Ada Ferro'); await pg.fill('#spkAff', 'Clovis Historical Society'); await pg.fill('#spkOutlet', 'Western Historical Quarterly')
        await pg.select_option('#spkLetter', 'new:cover'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ sum: $('#spkSum').textContent, anon: $('#spkAnon').checked, title: $('#spkTitle').checked, letter: P.docs.find(d => d.id === $('#spkLetter').value)?.title })")
        check('Submission package: a journal gets blind review and a title page, and a cover letter from a template', r['anon'] and r['title'] and r['letter'] == 'Cover letter' and 'Your name appears 1 time' in r['sum'], r)
        async with pg.expect_download() as dl:
            await pg.click('#spkGo')
        d = await dl.value; p = OUT + '/pkg.zip'; await d.save_as(p); await pg.wait_for_timeout(300)
        z = zipfile.ZipFile(p); names = z.namelist()
        check('…one .zip: the piece, the title page, the letter and a read-me', names == ['The Dry Year - anonymized.docx', 'Title page.docx', 'Cover letter.docx', 'Read me.txt'] and 'to Western Historical Quarterly' in d.suggested_filename, [names, d.suggested_filename])
        piece = zipfile.ZipFile(io.BytesIO(z.read(names[0]))).read('word/document.xml').decode('utf8')
        check('…the piece has the author’s name taken out', 'Ada Ferro' not in piece and '[Author] kept the minutes' in piece)
        tp = zipfile.ZipFile(io.BytesIO(z.read('Title page.docx'))).read('word/document.xml').decode('utf8')
        letter = zipfile.ZipFile(io.BytesIO(z.read('Cover letter.docx'))).read('word/document.xml').decode('utf8')
        check('…the title page has the name, affiliation and word count; the letter has the title and outlet filled in', 'Ada Ferro' in tp and 'Clovis Historical Society' in tp and 'Word count:' in tp and 'The Dry Year' in letter and 'Western Historical Quarterly' in letter)
        r = await pg.evaluate("P.subs[0] && { status: P.subs[0].status, outlet: P.subs[0].outlet, doc: P.subs[0].docId === P.docs[1].id }")
        check('…and it goes on the Submissions list as planned', r == {'status': 'planned', 'outlet': 'Western Historical Quarterly', 'doc': True}, r)

        # ---- a library file that follows Zotero
        lib = [{'id': 'ferroWater2021', 'type': 'book', 'title': 'Water on the Plains', 'author': [{'family': 'Ferro', 'given': 'Ada'}], 'issued': {'date-parts': [[2021]]}},
               {'id': 'lopezRail2019', 'type': 'article-journal', 'title': 'The Railroad Towns', 'container-title': 'Plains History', 'DOI': '10.1000/XYZ1', 'author': [{'family': 'Lopez', 'given': 'Maria'}], 'issued': {'date-parts': [[2019]]}}]
        await pg.evaluate("() => { P.sources.push({ id: 's-old', csl: { type: 'book', title: 'Water on the plains', issued: { 'date-parts': [[2021]] }, note: 'my note' }, created: nowISO(), modified: nowISO() }); }")
        r = await pg.evaluate("(t) => { const f = new File([t], 'My Library.json', { type: 'application/json', lastModified: 1000 }); return zRead(f).then(() => ({ n: P.sources.length, z: P.zotero, old: P.sources.find(s => s.id === 's-old'), toast: $('#toast').innerText })); }", json.dumps(lib))
        check('Zotero: the library file’s references come in, matched to ones already here by title and year', r['n'] == 2 and r['old']['zkey'] == 'ferroWater2021' and r['old']['csl']['author'][0]['family'] == 'Ferro' and r['old']['csl']['note'] == 'my note', r)
        check('…the project remembers the file', r['z']['file'] == 'My Library.json' and r['z']['count'] == 2 and r['z']['modified'] == 1000 and '1 new' in r['toast'] and '1 updated' in r['toast'], [r['z'], r['toast']])
        lib[1]['title'] = 'The Railroad Towns of the Llano'; lib.append({'id': 'quayMinutes', 'type': 'manuscript', 'title': 'Council minutes', 'issued': {'date-parts': [[1934]]}})
        r = await pg.evaluate("(t) => zMerge(zParse(t, 'My Library.json'))", json.dumps(lib))
        check('…when Zotero rewrites the file, changes and new items follow', r == {'added': 1, 'changed': 1, 'total': 3}, r)
        r = await pg.evaluate("(t) => zMerge(zParse(t, 'x.json'))", json.dumps(lib))
        check('…and reading it again changes nothing', r == {'added': 0, 'changed': 0, 'total': 3}, r)
        bib = '@book{ferroWater2021,\n  title = {Water on the Plains},\n  author = {Ferro, Ada},\n  year = {2021},\n  publisher = {Mesa Press}\n}\n'
        r = await pg.evaluate("(t) => zMerge(zParse(t, 'My Library.bib'))", bib)
        check('…Better BibTeX’s .bib export works too, matched by its citation key', r['added'] == 0 and r['total'] == 1, r)
        r = await pg.evaluate("(() => { openZotero(); const s = $('#zStatus').innerText; $('#zDlg').close(); const n = normalize(JSON.parse(JSON.stringify(P))); return { s, zkey: n.sources.find(x => x.id === 's-old').zkey, file: n.zotero.file }; })()")
        check('…the dialog says which file and when, and it all survives saving', 'My Library.json' in r['s'] and r['zkey'] == 'ferroWater2021' and r['file'] == 'My Library.json', r)

        # ---- editing marks made on the reviewer page come back as marks
        await pg.evaluate("openDoc(P.docs[1].id)"); await pg.wait_for_timeout(300)
        rv = await pg.evaluate("reviewPageHTML(curDoc(), '')")
        rpath = OUT + '/review-marks.html'; open(rpath, 'w', encoding='utf-8').write(rv)
        rp = await ctx.new_page(); rp.on('pageerror', lambda e: errs.append('review page: ' + str(e)))
        answers = []
        async def on_dialog(dg): await dg.accept(answers.pop(0) if dg.type == 'prompt' and answers else '')
        rp.on('dialog', lambda dg: asyncio.ensure_future(on_dialog(dg)))
        await rp.goto('file://' + rpath); await rp.wait_for_timeout(500)
        selw = """(words) => { const el = [...document.querySelectorAll('[data-b]')].find(e => e.textContent.includes(words)); const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let t;
            while ((t = w.nextNode())) if (t.data.includes(words)) break; const a = t.data.indexOf(words), r = document.createRange(); r.setStart(t, a); r.setEnd(t, a + words.length); getSelection().removeAllRanges(); getSelection().addRange(r); }"""
        await rp.evaluate(selw, 'debated at length'); answers[:] = ['Is this the right meeting?', 'Lena Ortiz']
        await rp.select_option('#rvMark', 'aq'); await rp.wait_for_timeout(200)
        await rp.evaluate(selw, 'The mayor'); await rp.select_option('#rvMark', 'lc'); await rp.wait_for_timeout(200)
        r = await rp.evaluate("document.getElementById('rvN').textContent")
        check('The reviewer page has the copyeditor’s marks too', r == '2 notes', r)
        async with rp.expect_download() as dl:
            await rp.click('#rvSave')
        d = await dl.value; rv = json.loads(open(await d.path(), encoding='utf-8').read()); await rp.close()
        r = await pg.evaluate("(rev) => { const x = rvApply(rev, curDoc()); renderEditMarks(); return { placed: x.placed.length, lost: x.lost.length, marks: $$('span.edm', editor).map(s => [s.dataset.ek, s.textContent, s.dataset.by, s.dataset.t || '']) }; }", rv)
        check('…and they come back into the draft as editing marks, signed by the reviewer', r['placed'] == 2 and r['lost'] == 0 and ['aq', 'debated at length', 'Lena Ortiz', 'Is this the right meeting?'] in r['marks'] and ['lc', 'The mayor', 'Lena Ortiz', ''] in r['marks'], r)

        bad = [e for e in errs if 'favicon' not in e]
        check('no page errors', not bad, bad[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
