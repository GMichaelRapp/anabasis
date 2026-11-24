"""1.9.0: cross-references that keep up (in the draft and every export), credits and permissions for figures
and tables with the permissions log, link check against the Wayback Machine (with the archive mocked),
the reviewer PDF with line numbers, and Word in manuscript format."""
import asyncio, json, pathlib, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

PX = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'archive.org' not in m.text and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        async def caret_end(sel_js):
            await pg.evaluate("s => { const p = eval(s); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); editor.focus(); }", sel_js)

        # ---- two documents: this one, and a second chapter with its own figure
        await pg.evaluate("""px => {
          P.docs.forEach(d => d.role = d.role || 'body');
          const a = addAsset(px, 'map', 1, 1), b2 = addAsset(px, 'photo', 1, 1), c = addAsset(px, 'other', 1, 1);
          const d2 = newDoc('Second chapter', '<h1>Roads</h1><p>Text.</p>' + figHTML(c, 'A road in winter') + '<p><br></p>'); P.docs.push(d2);
          editor.innerHTML = '<h1>Background</h1><p>As shown in</p><h2>Supply lines</h2>' + figHTML(a, 'The route east') + '<figure class="tbl"><figcaption>Rations per day</figcaption><table><tbody><tr><td>1</td></tr></tbody></table></figure>' + eqHTML('E = p B', true, true) + '<p>End.</p>';
          syncEditor(); hydrateImages(); renumberFigures(); renderDocList(); window._b2 = b2; }""", PX)
        await pg.wait_for_timeout(800)
        await caret_end("editor.querySelectorAll('p')[0]")
        await pg.click('#btnXref'); await pg.wait_for_timeout(300)
        items = await pg.evaluate("() => $$('#xrBody li[data-k]').map(li => li.textContent.replace(/\\s+/g, ' ').trim())")
        check('the cross-reference box lists headings, figures, tables, equations and documents', any(i.startswith('Figure 1 The route east') for i in items) and any(i.startswith('Table 1 Rations') for i in items) and any(i.startswith('Equation (1)') for i in items) and any('Supply lines' in i for i in items) and any(i.startswith('Chapter 2 Second chapter') for i in items) and any('A road in winter' in i for i in items), items)
        await pg.fill('#xrQ', 'route'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(150)
        check('…typing finds things, and the words can be chosen', await pg.evaluate("() => [...$('#xrForm').options].map(o => o.text).join('|') === 'Figure 1|figure 1|1'"))
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => { const x = editor.querySelector('span.xref'); const f = editor.querySelector('figure.fig'); return x && { t: x.textContent, ce: x.getAttribute('contenteditable'), ref: x.dataset.ref, fx: f.dataset.xid, p: editor.querySelectorAll('p')[0].textContent }; }")
        check('Insert puts “Figure 1” in the sentence, tied to the figure', r and r['t'] == 'Figure 1' and r['ce'] == 'false' and r['ref'] == r['fx'] and r['ref'].startswith('x') and r['p'].replace('\xa0', ' ').strip() == 'As shown in Figure 1', r)
        for q, form in [('Rations', 'lower'), ('Equation', 'num'), ('Supply', 'full'), ('road in winter', 'full'), ('Second chapter', 'full')]:
            await caret_end("editor.querySelectorAll('p')[0]")
            await pg.keyboard.press('Control+Alt+KeyR'); await pg.wait_for_timeout(200)
            await pg.fill('#xrQ', q); await pg.keyboard.press('Enter'); await pg.select_option('#xrForm', form); await pg.click('#xrOk'); await pg.wait_for_timeout(250)
        labels = await pg.evaluate("() => $$('#editor span.xref').map(x => x.textContent)")
        check('tables, equations, headings, another chapter’s figure and a whole chapter', labels == ['Figure 1', 'table 1', '(1)', '“Supply lines”', 'Figure 1', 'Chapter 2'], labels)
        check('…the other chapter’s figure was given a lasting id in that document', await pg.evaluate("() => { const d = P.docs.find(d => d.title === 'Second chapter'); const x = $$('#editor span.xref')[4].dataset.ref; return d.html.includes('data-xid=\"' + x + '\"'); }"))

        # numbers follow the figures
        await pg.evaluate("() => { editor.querySelector('h2').insertAdjacentHTML('afterend', figHTML(window._b2, 'A photograph') + eqHTML('x', true, true)); renumberFigures(); }")
        labels = await pg.evaluate("() => $$('#editor span.xref').map(x => x.textContent)")
        check('adding a figure and an equation ahead renumbers the references', labels[:3] == ['Figure 2', 'table 1', '(2)'], labels)
        await pg.evaluate("() => { editor.querySelectorAll('figure.fig')[1].remove(); renumberFigures(); }")
        r = await pg.evaluate("() => { const x = $$('#editor span.xref')[0]; return [x.textContent, x.hasAttribute('data-cp-miss'), getComputedStyle(x).color]; }")
        check('a reference to a deleted figure is marked in red, keeping its last words', r[0] == 'Figure 2' and r[1], r)
        await pg.click('#editor span.xref >> nth=0'); await pg.wait_for_timeout(200)
        check('…and clicking it says so', 'deleted' in await pg.inner_text('#toast'))
        await pg.evaluate("() => { $$('#editor span.xref')[0].remove(); syncEditor(); }")
        # dedupe: a pasted copy of a heading's id
        await pg.evaluate("() => { const h = editor.querySelector('h2'); const c = h.cloneNode(true); c.textContent = 'Copy'; editor.append(c); renumberFigures(); }")
        check('a copied heading doesn’t steal the original’s references', await pg.evaluate("() => $$('#editor h2[data-xid]').length === 1 && editor.querySelector('h2[data-xid]').textContent === 'Supply lines'"))
        # click: go there (another document)
        await pg.click('#editor span.xref >> nth=3'); await pg.wait_for_timeout(200)
        t = await pg.inner_text('#toast')
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(700)
        check('clicking a reference says where it points, and Go there opens that chapter at the figure', 'A road in winter' in t and 'Second chapter' in t and await pg.evaluate("() => curDoc().title === 'Second chapter' && !!editor.querySelector('figure.xr-flash, figure[data-xid]')"), t)
        first_id = await pg.evaluate("() => P.docs[0].id")
        await pg.evaluate("id => openDoc(id)", first_id); await pg.wait_for_timeout(400)

        # ---- exports
        html = await pg.evaluate("() => exportStandaloneHTML(curDoc())")
        links = re.findall(r'<a class="xref" href="#([^"]+)">([^<]+)</a>', html)
        check('web page: references are links to the figure, table, equation and heading', [l[1] for l in links] == ['table 1', '(2)', '“Supply lines”'] and all(f'id="{l[0]}"' in html for l in links), links)
        check('…one to another chapter is plain words when that chapter isn’t in the export', 'Figure 1' in re.sub('<[^>]+>', '', html.split('As shown in')[1][:400]), html.split('As shown in')[1][:400])
        md = await pg.evaluate("() => exportMarkdown(curDoc())")
        check('Markdown: the words, as text', 'As shown in table 1 (2) “Supply lines” Figure 1 Chapter 2' in md.replace('\xa0', ' ').replace('  ', ' '), md[:400])
        async with pg.expect_download() as d: await pg.evaluate("() => exportLatex(curDoc())")
        z = zipfile.ZipFile(await (await d.value).path()); tex = z.read([n for n in z.namelist() if n.endswith('.tex')][0]).decode()
        check('LaTeX: \\ref and \\eqref, with \\label on the table and equation', re.search(r'table~\\ref\{tab:(x\w+)\}', tex) and re.search(r'\\label\{tab:x\w+\}', tex) and re.search(r'\\eqref\{eq:(x\w+)\}', tex) and re.search(r'\\label\{eq:x\w+\}', tex), tex[tex.find('As shown'):tex.find('As shown') + 300])
        async with pg.expect_download() as d: await pg.evaluate("() => exportDocx(curDoc())")
        xml = zipfile.ZipFile(await (await d.value).path()).read('word/document.xml').decode()
        anchors = re.findall(r'<w:hyperlink [^>]*w:anchor="([^"]+)"', xml); marks = re.findall(r'<w:bookmarkStart w:name="([^"]+)"', xml)
        check('Word: references are links to bookmarks on the caption, equation number and heading', len(anchors) == 3 and all(a in marks for a in anchors), [anchors, marks])
        # compiled: the second chapter's figure is renumbered and linked
        await pg.evaluate("() => { openManuscript(); }"); await pg.wait_for_timeout(300)
        ms = await pg.evaluate("() => { const ms = buildManuscript(); $('#msDlg').close(); return exportStandaloneHTML(ms); }")
        lk = re.findall(r'<a class="xref" href="#([^"]+)">([^<]+)</a>', ms)
        check('compiled manuscript: Figure 1 of chapter two becomes Figure 2, linked, and “Chapter 2” links to the chapter', ('fig-2', 'Figure 2') in lk and any(l[1] == 'Chapter 2' for l in lk), lk)
        async with pg.expect_download() as d: await pg.evaluate("() => { openManuscript(); const ms = buildManuscript(); $('#msDlg').close(); return exportEpub(ms); }")
        z = zipfile.ZipFile(await (await d.value).path()); c1 = z.read('OEBPS/c1.xhtml').decode()
        check('EPUB: a reference into another section links to that file', re.search(r'href="c\d+\.xhtml#fig-2"', c1) is not None or 'href="#fig-2"' in c1, re.findall(r'<a class="xref"[^>]*>', c1))

        # ---- credits and permissions
        await pg.click('#editor figure.fig img'); await pg.wait_for_timeout(200)
        await pg.click('.pop button[data-a=cred]'); await pg.wait_for_timeout(200)
        await pg.fill('#crCredit', 'Map: Library of Congress'); await pg.select_option('#crRights', 'asked'); await pg.fill('#crHolder', 'LoC Rights Office'); await pg.fill('#crNote', 'Asked 3 Nov; fee $40'); await pg.click('#crOk'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => { const f = editor.querySelector('figure.fig'), c = f.querySelector('figcaption'); return [f.dataset.credit, f.dataset.rights, c.getAttribute('data-cp-credit'), getComputedStyle(c, '::after').content]; }")
        check('a figure gets a credit line and permission status, shown after the caption', r[0] == 'Map: Library of Congress' and r[1] == 'asked' and 'Library of Congress' in r[3], r)
        await pg.evaluate("() => { const td = editor.querySelector('figure.tbl td'); const r = document.createRange(); r.selectNodeContents(td); getSelection().removeAllRanges(); getSelection().addRange(r); }"); await pg.wait_for_timeout(300)
        await pg.click('#tblBar [data-t=cred]'); await pg.wait_for_timeout(200)
        await pg.fill('#crCredit', 'Adapted from Engels (1978)'); await pg.select_option('#crRights', 'fair'); await pg.click('#crOk'); await pg.wait_for_timeout(300)
        html = await pg.evaluate("() => exportStandaloneHTML(curDoc())")
        check('exports end the caption with the credit, and keep notes and status private', 'A photograph <span class="fig-credit">Map: Library of Congress.</span>' in html and 'Adapted from Engels (1978).' in html and 'fee $40' not in html and 'data-rights' not in html and 'LoC Rights' not in html)
        async with pg.expect_download() as d: await pg.evaluate("() => exportDocx(curDoc())")
        xml = zipfile.ZipFile(await (await d.value).path()).read('word/document.xml').decode()
        check('…Word too', 'Map: Library of Congress.' in xml and 'fee $40' not in xml)
        await pg.evaluate("() => switchTab('sources')"); await pg.click('#btnPerms'); await pg.wait_for_timeout(400)
        rows = await pg.evaluate("() => $$('#pmBody table.pm tbody tr').map(tr => [...tr.cells].map(c => c.textContent.trim()))")
        check('the permissions log lists every figure and table in the project, with status', len(rows) == 3 and rows[0][0].startswith('Figure 1') and rows[0][3] == 'Permission requested' and rows[1][3] == 'Fair use or fair dealing' and rows[2][3] == 'Not set: check', rows)
        await pg.select_option('#pmShow', 'todo'); await pg.wait_for_timeout(200)
        check('…“still to clear” shows what needs action', await pg.evaluate("() => $$('#pmBody table.pm tbody tr').length") == 2)
        async with pg.expect_download() as d: await pg.click('#pmCsv')
        csv = open(await (await d.value).path(), encoding='utf-8').read()
        check('…as a spreadsheet file', csv.startswith('Document,Item,Caption,Credit line,Status') and 'Asked 3 Nov; fee $40' in csv and 'Second chapter,Figure 1,A road in winter' in csv, csv[:300])
        await pg.click('#pmDoc'); await pg.wait_for_timeout(500)
        check('…or as a document to export for an editor', await pg.evaluate("() => curDoc().title === 'Permissions log' && editor.querySelectorAll('figure.tbl tbody tr').length === 3"))
        await pg.evaluate("id => openDoc(id)", first_id); await pg.wait_for_timeout(300)

        # ---- link check (the archive mocked)
        async def wb(route):
            u = route.request.url
            if 'gone.example' in u: body = {'archived_snapshots': {'closest': {'available': True, 'url': 'http://web.archive.org/web/20240102030405/https://gone.example/a', 'timestamp': '20240102030405', 'status': '404'}}}
            elif 'never.example' in u: body = {'archived_snapshots': {}}
            elif 'evil.example' in u: body = {'archived_snapshots': {'closest': {'available': True, 'url': 'javascript:alert(1)', 'timestamp': '2024', 'status': '200'}}}
            else: body = {'archived_snapshots': {'closest': {'available': True, 'url': 'http://web.archive.org/web/20251111000000/https://fine.example/', 'timestamp': '20251111000000', 'status': '200'}}}
            await route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
        await pg.route('https://archive.org/wayback/available*', wb)
        await pg.evaluate("""() => { P.sources = P.sources.filter(s => !/^https?:/.test(s.csl.URL || ''));
          [['Gone page', 'https://gone.example/a'], ['Never saved', 'https://never.example/b'], ['Fine page', 'https://fine.example/'], ['Odd answer', 'https://evil.example/']].forEach(([t, u], i) => P.sources.push({ id: 'w' + i, csl: { type: 'webpage', title: t, URL: u }, created: '2025-03-0' + (i + 1) + 'T12:00:00Z', modified: nowISO() }));
          P.sources.find(s => s.id === 'w2').csl.accessed = { 'date-parts': [[2025, 1, 1]] }; renderSourceList(); }""")
        await pg.evaluate("() => switchTab('sources')"); await pg.click('#btnLinks'); await pg.wait_for_timeout(200)
        check('Check links offers to check the web sources and fill in accessed dates', (await pg.inner_text('#lkRun')) == 'Check 4 web sources' and (await pg.inner_text('#lkAcc')) == 'Fill in 3 missing accessed dates')
        await pg.click('#lkRun'); await pg.wait_for_timeout(2500)
        v = await pg.evaluate("() => $$('#lkBody tbody tr').map(tr => [tr.cells[0].querySelector('.lk-url').textContent, tr.cells[2].textContent.trim(), tr.cells[1].textContent.trim()])")
        check('…the archive’s record: gone (404), no copy, fine, and a bad answer ignored', v[0][1] == 'Gone when last seen (404)' and v[1][1] == 'No saved copy' and v[2][1] == 'Fine when last seen' and v[3][1] == 'No saved copy' and v[0][2] != '—', v)
        check('…and how many are gone', '1 gone' in await pg.inner_text('#lkSum'))
        await pg.click('#lkAttach'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => P.sources.filter(s => /^w/.test(s.id)).map(s => (s.osint || {}).archiveUrl || '')")
        check('Keep saved copies stores the Wayback links with their sources (https)', r[0] == 'https://web.archive.org/web/20240102030405/https://gone.example/a' and r[1] == '' and r[2].startswith('https://web.archive.org/web/2025') and r[3] == '', r)
        await pg.check('#lkBody tr[data-id=w0] [data-arch]'); await pg.wait_for_timeout(200)
        check('…“cite the saved copy” swaps in the archived address for citations', await pg.evaluate("() => itemFor('w0').URL === 'https://web.archive.org/web/20240102030405/https://gone.example/a' && itemFor('w2').URL === 'https://fine.example/'"))
        await pg.click('#lkAcc'); await pg.wait_for_timeout(200)
        check('…accessed dates filled from the day each source was added', await pg.evaluate("() => JSON.stringify(P.sources.find(s => s.id === 'w0').csl.accessed) === JSON.stringify({ 'date-parts': [[2025, 3, 1]] }) && P.sources.find(s => s.id === 'w2').csl.accessed['date-parts'][0][0] === 2025 && P.sources.find(s => s.id === 'w2').csl.accessed['date-parts'][0][1] === 1"))
        saved = await pg.evaluate("() => { syncEditor(); return projectJSON(); }")
        check('…and it all saves', re.search(r'"citeArchive":\s*true', saved) and re.search(r'"lc":\s*\{', saved))
        await pg.unroute('https://archive.org/wayback/available*')
        await pg.route('https://archive.org/wayback/available*', lambda r: r.abort())
        await pg.click('#lkRun'); await pg.wait_for_timeout(2500)
        check('when the archive can’t be reached, it says so plainly', 'couldn’t be reached' in await pg.inner_text('#toast'), await pg.inner_text('#toast'))
        await pg.click('#lkClose')

        # ---- reviewer PDF
        await pg.evaluate("() => { editor.insertAdjacentHTML('beforeend', Array.from({ length: 30 }, (_, i) => '<p>Paragraph ' + (i + 1) + ' has enough words in it to wrap across more than one line on a printed page, which is what we want to count here.</p>').join('')); syncEditor(); }")
        html = await pg.evaluate("() => exportPagedPDF(curDoc(), { review: true })")
        check('the reviewer copy has wide margins, “Review copy” and line numbering', 'margin:1in 2.4in 1in 1.25in' in html and 'Review copy' in html and 'cpLineNums()' in html)
        p = pathlib.Path(OUT) / 'review.html'; p.write_text(html, encoding='utf-8')
        p2 = await ctx.new_page(); p2.on('pageerror', lambda e: errs.append('review ' + str(e)))
        await p2.goto(p.as_uri()); await p2.wait_for_function("document.querySelectorAll('.cp-ln').length > 0", timeout=60000); await p2.wait_for_timeout(500)
        r = await p2.evaluate("() => { const pgs = [...document.querySelectorAll('.pagedjs_page')]; return { pages: pgs.length, per: pgs.map(p => [...p.querySelectorAll('.cp-ln')].map(x => +x.textContent)), left: [...document.querySelectorAll('.cp-ln')].every(x => x.getBoundingClientRect().right <= x.closest('.pagedjs_page').querySelector('.pagedjs_page_content').getBoundingClientRect().left) }; }")
        seq_ok = all(p == list(range(1, len(p) + 1)) for p in r['per'] if p)
        check('…every line is numbered, starting again on each page, in the margin', r['pages'] >= 2 and seq_ok and sum(len(p) for p in r['per']) > 60 and r['left'], {'pages': r['pages'], 'counts': [len(p) for p in r['per']], 'left': r['left']})
        await p2.close()
        plain = await pg.evaluate("() => exportPagedPDF(curDoc())")
        check('…and the ordinary PDF has none of it', 'cpLineNums' not in plain and 'Review copy' not in plain)

        # ---- Word in manuscript format
        await pg.evaluate("() => { editor.insertAdjacentHTML('beforeend', '<hr><p>After the break.</p>'); syncEditor(); }")
        await pg.click('#btnExport'); await pg.click('#exportMenu [data-x=docxms]'); await pg.wait_for_timeout(300)
        await pg.fill('#msfName', 'G. Michael Rapp'); await pg.fill('#msfContact', '12 Main St\nClovis, NM\nme@example.com'); await pg.fill('#msfShort', 'Background')
        check('the manuscript box shows the running head and the rounded word count', (await pg.inner_text('#msfHead')).endswith('Rapp / Background / 2') and re.search(r'About [\d,]+00 words', await pg.inner_text('#msfWords')))
        async with pg.expect_download() as d: await pg.click('#msfOk')
        dl = await d.value; z = zipfile.ZipFile(await dl.path()); xml = z.read('word/document.xml').decode()
        hdrs = [z.read(n).decode() for n in z.namelist() if re.match(r'word/header\d*\.xml', n)]
        check('Word manuscript: the file is named for it, Times 12, double-spaced', dl.suggested_filename.endswith(' - manuscript.docx') and 'Times New Roman' in xml and 'w:line="480"' in xml)
        check('…first page: name, contact, word count, title and byline', 'G. Michael Rapp</w:t>' in xml and 'me@example.com' in xml and re.search(r'About [\d,]+ words', xml) and 'by G. Michael Rapp' in xml)
        check('…“Rapp / Background / page” at the top of every page but the first', '<w:titlePg' in xml and any('Rapp / Background / ' in h and 'PAGE' in h for h in hdrs), [h[-300:] for h in hdrs])
        check('…# marks a section break, and margin notes are left out', '>#</w:t>' in xml and 'commentReference' not in xml)
        check('…and your details are kept in this browser, not the project', await pg.evaluate("() => PREFS.msf.contact.includes('Clovis') && !projectJSON().includes('Clovis')"))
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
