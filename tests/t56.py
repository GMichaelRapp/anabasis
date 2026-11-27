"""2.10.0: the reader opens ePubs; contents, pages, highlights, find results and a reading list beside the page;
where you left off; paper, sepia and night; two pages; highlights without notes; quoting into the draft; reading aloud."""
import asyncio, base64, io, json, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

FIX = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fixtures', 'sample.pdf')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8DwnwEJMDGgAQBXIAMB6dVwJAAAAABJRU5ErkJggg==')


def epub(path, title, author, chapters, pages=False, drm=False, isbn='9780000000002'):
    """A small ePub 3: chapters = [(toc title or None, xhtml body)]. pages adds a page list."""
    z = zipfile.ZipFile(path, 'w')
    z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip')
    z.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>', zipfile.ZIP_DEFLATED)
    if drm: z.writestr('META-INF/encryption.xml', '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" xmlns:enc="http://www.w3.org/2001/04/xmlenc#"><enc:EncryptedData><enc:EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/><enc:CipherData><enc:CipherReference URI="OEBPS/Text/ch1.xhtml"/></enc:CipherData></enc:EncryptedData></encryption>')
    items, refs, nav = [], [], []
    for i, (t, body) in enumerate(chapters, 1):
        z.writestr(f'OEBPS/Text/ch{i}.xhtml', f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{t or ""}</title><style>p{{color:red}}</style><script>window.EPUB_RAN=1</script></head><body>{body}</body></html>', zipfile.ZIP_DEFLATED)
        items.append(f'<item id="c{i}" href="Text/ch{i}.xhtml" media-type="application/xhtml+xml"/>'); refs.append(f'<itemref idref="c{i}"/>')
        if t: nav.append(f'<li><a href="Text/ch{i}.xhtml">{t}</a></li>')
    pl = ''.join(f'<li><a href="Text/ch1.xhtml#pg{n}">{n}</a></li>' for n in (11, 12)) if pages else ''
    z.writestr('OEBPS/nav.xhtml', f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol>{"".join(nav)}</ol></nav>{f"<nav epub:type=page-list><ol>{pl}</ol></nav>" if pages else ""}</body></html>')
    z.writestr('OEBPS/Images/map.png', PNG)
    z.writestr('OEBPS/content.opf', f'<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:isbn:{isbn}</dc:identifier><dc:title>{title}</dc:title><dc:creator>{author}</dc:creator><dc:date>2019-05-01</dc:date><dc:publisher>Lantern Press</dc:publisher><dc:language>en</dc:language></metadata><manifest><item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/><item id="img" href="Images/map.png" media-type="image/png"/>{"".join(items)}</manifest><spine>{"".join(refs)}</spine></package>', zipfile.ZIP_DEFLATED)
    z.close()


SALT = [
    ('Chapter 1: The Coast', '<h1>Chapter 1: The Coast</h1><p>The caravan left the harbour before dawn.<span epub:type="pagebreak" id="pg11" title="11"/> Salt was worth more than silver that year, and every porter knew it.</p>'
     '<p onclick="window.EPUB_RAN=2">The guides argued about the <i>western pass</i> for three days.<a epub:type="noteref" href="ch3.xhtml#n1">1</a></p><p><img src="../Images/map.png" alt="A map of the road"/></p>'
     '<span epub:type="pagebreak" id="pg12" title="12"></span><p>At the first well the water was bitter, and the camels refused it.</p><p>See <a href="https://example.org/road">the survey</a>.</p><iframe src="https://example.org"></iframe><form><input/></form>'),
    ('Chapter 2: The Hills', '<h1>Chapter 2: The Hills</h1><p>In the hills the road narrowed to a single track.</p><p>The porters sang to keep their spirits up, and the salt held.</p>'),
    ('Notes', '<h2>Notes</h2><p id="n1">1. The western pass is now a paved road.</p>'),
]
FORD = [
    (None, '<p class="title">The Ford</p>'),
    ('Chapter 1 The Ford', '<h1>Chapter 1 The Ford</h1><p>The river was high in spring.</p><p>They crossed at the ford below the mill, where the water ran fast over the stones.</p><p>Nobody spoke until the far bank.</p>'),
    ('Interlude', '<h1>Interlude</h1><p>A short pause between the crossings, in which the mill wheel turned.</p>'),
]


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    epub(_os.path.join(OUT, 'salt.epub'), 'The Salt Road', 'Mara Velloso', SALT, pages=True)
    epub(_os.path.join(OUT, 'ford.epub'), 'Crossings', 'Tomas Aldren', FORD, isbn='9780000000019')
    epub(_os.path.join(OUT, 'locked.epub'), 'Locked', 'Nobody', FORD, drm=True, isbn='9780000000026')
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; if(!sessionStorage.getItem('t56'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Ada Ferro',orcDay:new Date().toISOString().slice(0,10)})); sessionStorage.setItem('t56','1')")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")
        await pg.evaluate("() => { const d = newDoc('Salt', '<h1>Salt</h1><p>The trade began on the coast. As one historian puts it, </p><p>Next paragraph.</p>'); addDoc(d); renderDocList(); openDoc(d.id); }"); await pg.wait_for_timeout(400)

        # ---- an ePub opens, cleaned, with contents and its own metadata
        await pg.click('.tabs button[data-tab=sources]'); await pg.click('#btnReader'); await pg.wait_for_timeout(300)
        check('empty reader offers to open a file', await pg.is_visible('#rdEmptyOpen'))
        await pg.set_input_files('#filePdf', _os.path.join(OUT, 'salt.epub'))
        await pg.wait_for_selector('.rd-page.ep-ch[data-n="3"]', timeout=10000); await pg.wait_for_timeout(300)
        info = await pg.evaluate("""() => ({ kind: R.kind, n: R.doc.numPages, name: document.querySelector('#rdName').textContent, of: document.querySelector('#rdOf').textContent,
          scripts: document.querySelectorAll('#rdPages script,#rdPages style,#rdPages iframe,#rdPages form,#rdPages input,#rdPages [onclick]').length, ran: window.EPUB_RAN || 0,
          img: (document.querySelector('#rdPages img') || {}).src || '', ext: (document.querySelector('#rdPages a[target=_blank]') || {}).href || '', internal: !!document.querySelector('#rdPages a[data-ep]'),
          pbs: [...document.querySelectorAll('.ep-pb')].map(x => x.dataset.pb), pbText: document.querySelector('.ep-pb').textContent, epubCls: document.querySelector('#reader').classList.contains('is-epub'), ital: !!document.querySelector('.ep-body i') })""")
        check('ePub opens as chapters', info['kind'] == 'epub' and info['n'] == 3 and info['of'] == '/ 3', info)
        check('book title shown', info['name'] == 'The Salt Road', info)
        check('scripts, styles, frames, forms and handlers are dropped', info['scripts'] == 0 and info['ran'] == 0, info)
        check('images come from the book, links outside open apart, links inside are caught', info['img'].startswith('blob:') and info['ext'] == 'https://example.org/road' and info['internal'], info)
        check('page breaks kept as markers that are not text', info['pbs'] == ['11', '12'] and info['pbText'] == '', info)
        check('emphasis kept', info['ital'])
        # internal link goes to the note
        await pg.click('#rdPages a[data-ep]'); await pg.wait_for_timeout(300)
        check('a note link goes to its chapter', await pg.evaluate("currentPage()") == 3)
        await pg.evaluate("goPage(1)")
        # side panel: contents
        await pg.click('#rdSideBtn'); await pg.wait_for_timeout(300)
        toc = await pg.eval_on_selector_all('#rdTab [data-tp]', 'b => b.map(x => x.textContent + "@" + x.dataset.tp)')
        check('contents from the book', toc == ['Chapter 1: The Coast@1', 'Chapter 2: The Hills@2', 'Notes@3'], toc)
        check('no Pages tab for an ePub', not await pg.is_visible('#rdSide [data-rt=thumbs]'))
        await pg.click('#rdTab [data-tp="2"]'); await pg.wait_for_timeout(300)
        check('contents go to the chapter', await pg.evaluate("currentPage()") == 2)
        check('current chapter marked', await pg.evaluate("document.querySelector('#rdTab button.on')?.dataset.tp") == '2')

        # ---- selection: printed page from the book's page list; quote note; source from the book
        sel_js = """(args) => { const [n, word, len] = args; const body = R.pages[n - 1].div.querySelector('.ep-body'); const w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT); let t; while ((t = w.nextNode())) { const i = t.data.indexOf(word); if (i >= 0) { const r = document.createRange(); r.setStart(t, i); r.setEnd(t, Math.min(t.data.length, i + len)); const s = getSelection(); s.removeAllRanges(); s.addRange(r); return r.toString(); } } return ''; }"""
        await pg.evaluate("goPage(1)")
        got = await pg.evaluate(sel_js, [1, 'Salt was worth', 40]); await pg.wait_for_timeout(300)
        check('selection bar shows the printed page', (await pg.inner_text('#rdSelPage')).startswith('p. 11'), await pg.inner_text('#rdSelPage'))
        await pg.click('#rdSelBar [data-k=quote]'); await pg.wait_for_timeout(400)
        n0 = await pg.evaluate("(() => { const n = P.notes[0], s = P.sources.find(x => x.id === n.sourceId); return { body: n.body, loc: n.locator, label: n.label, hl: n.pdfHl, title: s.csl.title, au: s.csl.author, isbn: s.csl.ISBN, pub: s.csl.publisher, yr: s.csl.issued, file: s.pdfName }; })()")
        check('quote note with the printed page', n0['body'] == got.strip() and n0['loc'] == '11' and n0['label'] == 'page', n0)
        check('source made from the book', n0['title'] == 'The Salt Road' and n0['au'][0].get('family') == 'Velloso' and n0['isbn'] == '9780000000002' and n0['pub'] == 'Lantern Press' and n0['yr'] == {'date-parts': [[2019]]}, n0)
        check('note highlight anchored by text offsets', n0['hl'] and n0['hl'][0]['p'] == 1 and n0['hl'][0]['z'] - n0['hl'][0]['a'] == len(got), n0)
        check('quote highlight drawn', await pg.evaluate("CSS.highlights.has('rd-q') && [...CSS.highlights.get('rd-q')][0].toString()") == got)
        check('note pin beside the passage', await pg.evaluate("!!document.querySelector('.ep-ch .rd-hl-pin')"))
        check('book kept in this browser', await pg.evaluate("pdfStore.get(R.sourceId).then(r => r && r.kind === 'epub' && r.buf.byteLength > 1000)"))
        # a passage across the second page break
        await pg.evaluate(sel_js, [1, 'At the first well', 20]); await pg.wait_for_timeout(250)
        check('page after the second break', (await pg.inner_text('#rdSelPage')).startswith('p. 12'), await pg.inner_text('#rdSelPage'))

        # ---- plain highlights: colours, list, pop, export, notes
        await pg.evaluate(sel_js, [2, 'the road narrowed', 17]); await pg.wait_for_timeout(250)
        await pg.click('#rdSelBar [data-c=g]'); await pg.wait_for_timeout(300)
        hl = await pg.evaluate("(() => { const s = P.sources.find(x => x.id === R.sourceId); return s.hls; })()")
        check('a green highlight on the source, no note', len(hl) == 1 and hl[0]['c'] == 'g' and hl[0]['text'] == 'the road narrowed' and hl[0]['h'][0]['p'] == 2, hl)
        check('drawn green', await pg.evaluate("CSS.highlights.has('rd-cg') && [...CSS.highlights.get('rd-cg')][0].toString()") == 'the road narrowed')
        r = await pg.evaluate(sel_js, [2, 'The porters sang', 16]); await pg.wait_for_timeout(250)
        if not await pg.is_visible('#rdSelBar'): print('DEBUG', r, await pg.evaluate("String(getSelection())")); await pg.screenshot(path=_os.path.join(OUT, 'dbg.png'))
        await pg.click('#rdSelBar [data-c=y]'); await pg.wait_for_timeout(300)
        await pg.click('#rdSide [data-rt=hls]'); await pg.wait_for_timeout(300)
        items = await pg.eval_on_selector_all('#rdTab .rd-hli q', 'e => e.map(x => x.textContent)')
        check('highlights listed in book order', items == ['the road narrowed', 'The porters sang'], items)
        await pg.click('#rdTab [data-hlf=g]'); await pg.wait_for_timeout(200)
        check('filter by colour', await pg.eval_on_selector_all('#rdTab .rd-hli', 'e => e.length') == 1)
        await pg.click('#rdTab [data-hlf=""]'); await pg.wait_for_timeout(200)
        async with pg.expect_download() as d: await pg.click('#rdTab [data-hlx=md]')
        f = await d.value; md = open(await f.path()).read()
        check('highlights download as Markdown with places', md.startswith('# Highlights: The Salt Road') and '> the road narrowed' in md and '— sec. ' not in md and ('ch. 2' in md or 'p.' in md), md[:300])
        # click a highlight: change colour, then make it a note
        await pg.evaluate("(() => { const s = P.sources.find(x => x.id === R.sourceId), h = s.hls.find(x => x.c === 'y').h[0]; epRanges(h.p, [[h.a, h.z]])[0].startContainer.parentElement.scrollIntoView({block:'center'}); })()"); await pg.wait_for_timeout(300)
        box = await pg.evaluate("(() => { const s = P.sources.find(x => x.id === R.sourceId), h = s.hls.find(x => x.c === 'y').h[0]; const q = epRanges(h.p, [[h.a, h.z]])[0].getClientRects()[0]; return [q.left + q.width / 2, q.top + q.height / 2]; })()")
        await pg.mouse.click(box[0], box[1]); await pg.wait_for_timeout(300)
        check('clicking a highlight offers its choices', await pg.is_visible('#rdHlPop'))
        await pg.click('#rdHlPop [data-c=p]'); await pg.wait_for_timeout(200)
        check('colour changed', await pg.evaluate("P.sources.find(x => x.id === R.sourceId).hls.some(h => h.c === 'p')"))
        nn = await pg.evaluate("P.notes.length")
        await pg.click('#rdHlPop [data-hx=note]'); await pg.wait_for_timeout(300)
        check('highlight became a quote note', await pg.evaluate("P.notes.length") == nn + 1 and await pg.evaluate("P.notes[0].body") == 'The porters sang' and await pg.evaluate("P.sources.find(x => x.id === R.sourceId).hls.length") == 1)

        # ---- quote straight into the draft, with its citation
        await pg.evaluate("""() => { const p = [...editor.querySelectorAll('p')].find(x => x.textContent.includes('As one historian')); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); savedRange = r; }""")
        await pg.evaluate(sel_js, [1, 'the camels refused it', 21]); await pg.wait_for_timeout(250)
        await pg.click('#rdSelBar [data-k=insert]'); await pg.wait_for_timeout(500)
        ed = await pg.evaluate("(() => { const p = [...editor.querySelectorAll('p')].find(x => x.textContent.includes('As one historian')); return { text: p.textContent, cite: !!p.querySelector('.cite'), items: p.querySelector('.cite')?.dataset.items || '' }; })()")
        check('a short quote runs into the sentence with its citation', '“the camels refused it”' in ed['text'] and ed['cite'] and '"locator":"12"' in ed['items'], ed)

        # ---- find: every match listed with its chapter and words around
        await pg.fill('#rdFind', 'salt'); await pg.press('#rdFind', 'Enter'); await pg.wait_for_timeout(600)
        fl = await pg.eval_on_selector_all('#rdTab [data-fi]', 'e => e.map(x => x.textContent)')
        check('find lists every match, with the words around it', len(fl) == 2 and 'Coast\nThe caravan' not in fl[0] and 'The Coast The caravan' in fl[0].replace('\n', ' ') and 'Salt was worth' in fl[0], fl)
        check('find results grouped by chapter', await pg.eval_on_selector_all('#rdTab .rd-fnd b', 'e => e.map(x => x.textContent)') == ['Chapter 1: The Coast', 'Chapter 2: The Hills'])
        check('matches shaded', await pg.evaluate("[...CSS.highlights.get('rd-find')].length") == 2)
        c1 = await pg.inner_text('#rdFindN'); await pg.press('#rdFind', 'Enter'); await pg.wait_for_timeout(200); c2 = await pg.inner_text('#rdFindN')
        check('Enter goes to the next match', c1.endswith('/ 2') and c2.endswith('/ 2') and c2 != c1, [c1, c2])
        await pg.click('#rdTab [data-fi="0"]'); await pg.wait_for_timeout(300)
        check('clicking a result goes there', (await pg.inner_text('#rdFindN')).startswith('1 / 2') and await pg.evaluate("[...CSS.highlights.get('rd-findcur')][0].toString().toLowerCase()") == 'salt')
        await pg.fill('#rdFind', ''); await pg.press('#rdFind', 'Enter')

        # ---- view: sepia, night, type, size
        await pg.click('#rdViewBtn'); await pg.wait_for_timeout(150)
        check('ePub view has type, not layout', await pg.is_visible('#rdViewPop .rd-v-ep') and not await pg.is_visible('#rdViewPop .rd-v-pdf'))
        await pg.check('#rdViewPop [name=rdTheme][value=night]'); await pg.wait_for_timeout(150)
        bg = await pg.evaluate("getComputedStyle(document.querySelector('.ep-ch')).backgroundColor")
        check('night page', bg == 'rgb(29, 32, 37)', bg)
        await pg.check('#rdViewPop [name=rdTheme][value=sepia]'); await pg.check('#rdViewPop [name=rdFont][value=sans]'); await pg.wait_for_timeout(150)
        check('sepia and plain type', await pg.evaluate("getComputedStyle(document.querySelector('.ep-ch')).backgroundColor") == 'rgb(243, 233, 212)' and 'Atkinson' in await pg.evaluate("getComputedStyle(document.querySelector('.ep-ch')).fontFamily"))
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(100)
        check('view closes with Escape', not await pg.is_visible('#rdViewPop'))
        fs0 = await pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.ep-ch')).fontSize)")
        await pg.click('#rdZoomIn'); await pg.wait_for_timeout(200)
        check('larger type', await pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.ep-ch')).fontSize)") > fs0 and await pg.inner_text('#rdZoom') == '115%')
        await pg.click('#rdFit'); await pg.wait_for_timeout(200)

        # ---- read aloud (speech mocked)
        await pg.evaluate("""() => { window.SAID = []; speechSynthesis.speak = u => { SAID.push(u.text); setTimeout(() => u.onend && u.onend(), 5); }; speechSynthesis.cancel = () => {}; }""")
        await pg.evaluate("goPage(2)"); await pg.wait_for_timeout(200)
        await pg.click('#rdRead'); await pg.wait_for_timeout(500)
        said = await pg.evaluate("SAID")
        check('reads aloud from where you are, into the next chapter', said[:2] == ['Chapter 2: The Hills', 'In the hills the road narrowed to a single track.'] and any('western pass is now' in x for x in said), said)
        check('the reading bar closes at the end', not await pg.is_visible('#rdTts'))

        # ---- where you left off
        await pg.evaluate("goPage(2, 0.3)"); await pg.wait_for_timeout(700)
        sid = await pg.evaluate("R.sourceId")
        at = await pg.evaluate("JSON.parse(localStorage.getItem('commonplace.rdat'))['s:' + R.sourceId]")
        check('place kept in this browser', at and at['p'] == 2 and at['n'] == 3 and 0 < at['pr'] < 1, at)
        await pg.click('#rdClose'); await pg.wait_for_timeout(200)
        await pg.evaluate(f"readSourcePdf('{sid}')"); await pg.wait_for_selector('.rd-page.ep-ch', timeout=8000); await pg.wait_for_timeout(600)
        check('reopens where you left off', await pg.evaluate("currentPage()") == 2 and 'Picked up where you left off' in await pg.inner_text('#toast'), await pg.inner_text('#toast'))
        check('highlights come back', await pg.evaluate("CSS.highlights.has('rd-cg') && CSS.highlights.has('rd-q')"))
        # reading list
        await pg.evaluate(f"(() => {{ const s = P.sources.find(x => x.id === '{sid}'); s.read = 'toread'; }})()")
        await pg.click('#rdSide [data-rt=lib]'); await pg.wait_for_timeout(400)
        lib = await pg.inner_text('#rdTab')
        check('reading list with progress', 'The Salt Road' in lib and '%' in lib and await pg.evaluate("!!document.querySelector('#rdTab .rd-prog')"), lib)
        # finishing
        await pg.evaluate("(() => { RD.finished = {}; const b = document.querySelector('#rdPages'); b.scrollTop = b.scrollHeight; })()"); await pg.wait_for_timeout(800)
        check('at the end, offers to mark it read', 'Mark as read' in await pg.inner_text('#toast'), await pg.inner_text('#toast'))

        # ---- a book without page numbers: chapter and paragraph
        await pg.set_input_files('#filePdf', _os.path.join(OUT, 'ford.epub')); await pg.wait_for_selector('#rdName:text("Crossings")', timeout=8000); await pg.wait_for_timeout(300)
        await pg.evaluate(sel_js, [2, 'They crossed at the ford', 24]); await pg.wait_for_timeout(250)
        check('chapter and paragraph when the book has no pages', (await pg.inner_text('#rdSelPage')).startswith('ch. 1, para. 2'), await pg.inner_text('#rdSelPage'))
        await pg.evaluate(sel_js, [3, 'A short pause', 13]); await pg.wait_for_timeout(250)
        check('an unnumbered section by its title', (await pg.inner_text('#rdSelPage')).startswith('sec. Interlude, para. 1'), await pg.inner_text('#rdSelPage'))
        await pg.evaluate(sel_js, [2, 'They crossed at the ford', 24]); await pg.wait_for_timeout(250)
        await pg.click('#rdSelBar [data-k=quote]'); await pg.wait_for_timeout(400)
        n1 = await pg.evaluate("({ loc: P.notes[0].locator, label: P.notes[0].label, cite: htmlToText(previewCluster(curDoc().style, [{ id: P.notes[0].sourceId, locator: P.notes[0].locator, label: P.notes[0].label }])) })")
        check('the note cites the chapter', n1['loc'] == '1, para. 2' and n1['label'] == 'chapter' and '1, para. 2' in n1['cite'], n1)
        # take notes on an ePub: the pad follows the place and goes back to it
        await pg.click('#rdNotes'); await pg.wait_for_timeout(500)
        check('the note pad knows the place in a book', await pg.inner_text('#rrPgL') == 'at' and await pg.input_value('#rrPage') != '', await pg.input_value('#rrPage'))
        await pg.evaluate("goPage(1)"); await pg.wait_for_timeout(200)
        await pg.evaluate("goPage(1)")
        await pg.click('#rrList [data-rr-go]'); await pg.wait_for_timeout(300)
        check('a note’s place takes you back', await pg.evaluate("currentPage()") == 2)
        await pg.click('#rrDone'); await pg.wait_for_timeout(300)
        # locked book
        await pg.set_input_files('#filePdf', _os.path.join(OUT, 'locked.epub')); await pg.wait_for_timeout(800)
        check('a DRM-locked ePub says so', 'locked with DRM' in await pg.inner_text('#rdPages'))

        # ---- the app's own ePub export opens in the reader
        await pg.click('#btnExport')
        async with pg.expect_download() as d: await pg.click('[data-x=epub]')
        f = await d.value; own = _os.path.join(OUT, 'own.epub'); await f.save_as(own)
        await pg.keyboard.press('Escape')
        await pg.set_input_files('#filePdf', own); await pg.wait_for_selector('.rd-page.ep-ch', timeout=8000); await pg.wait_for_timeout(300)
        check('an ePub exported from Anabasis reads back', 'The trade began on the coast' in await pg.inner_text('#rdPages'))

        # ---- PDF: outline/pages, two pages, night, colour highlights, find list, read aloud, place
        await pg.set_input_files('#filePdf', FIX); await pg.wait_for_selector('.rd-page[data-n="2"] .textLayer span', timeout=20000); await pg.wait_for_timeout(300)
        check('back to a PDF', await pg.evaluate("R.kind") == 'pdf' and await pg.is_visible('#rdOcr'))
        await pg.click('#rdSide [data-rt=thumbs]'); await pg.wait_for_selector('#rdTab .th canvas', timeout=10000)
        th = await pg.eval_on_selector_all('#rdTab [data-tg]', 'e => e.length')
        check('page thumbnails', th == await pg.evaluate("R.doc.numPages"), th)
        await pg.click('#rdTab [data-tg="3"]'); await pg.wait_for_timeout(300)
        check('a thumbnail goes to its page', await pg.evaluate("currentPage()") == 3 and await pg.evaluate("document.querySelector('#rdTab [data-tg].on').dataset.tg") == '3')
        await pg.click('#rdSide [data-rt=toc]'); await pg.wait_for_timeout(400)
        check('contents tab for a PDF', await pg.evaluate("!!document.querySelector('#rdTab .rd-toc, #rdTab .rd-hint')"))
        w1 = await pg.evaluate("R.pages[0].div.offsetWidth")
        await pg.click('#rdViewBtn'); await pg.check('#rdViewPop [name=rdSpread][value=two]'); await pg.wait_for_timeout(500)
        sp = await pg.evaluate("(() => { const a = R.pages[1].div.getBoundingClientRect(), b = R.pages[2].div.getBoundingClientRect(); return { same: Math.abs(a.top - b.top) < 2, side: b.left > a.right - 1, spacer: !!document.querySelector('.rd-spacer') }; })()")
        check('two pages side by side, the first alone', sp['same'] and sp['side'] and sp['spacer'], sp)
        check('pages fit two across', await pg.evaluate("R.pages[0].div.offsetWidth") < w1 * 0.6)
        await pg.check('#rdViewPop [name=rdSpread][value=one]'); await pg.check('#rdViewPop [name=rdTheme][value=night]'); await pg.wait_for_timeout(400)
        check('night inverts the PDF page', 'invert' in await pg.evaluate("getComputedStyle(document.querySelector('.rd-page canvas')).filter"))
        await pg.check('#rdViewPop [name=rdTheme][value=paper]'); await pg.keyboard.press('Escape')
        await pg.evaluate("goPage(2)"); await pg.wait_for_timeout(400)
        await pg.evaluate("""() => { const sp = [...document.querySelectorAll('.rd-page[data-n="2"] .textLayer span')].filter(s => s.textContent.trim().length > 8)[0]; const r = document.createRange(); r.selectNodeContents(sp); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }"""); await pg.wait_for_timeout(300)
        await pg.click('#rdSelBar [data-c=b]'); await pg.wait_for_timeout(400)
        check('blue highlight drawn on the PDF page', await pg.evaluate("!!document.querySelector('.rd-page[data-n=\"2\"] .rd-hl.c-b')"))
        hb = await pg.evaluate("(() => { const q = document.querySelector('.rd-hl.c-b').getBoundingClientRect(); return [q.left + q.width / 2, q.top + q.height / 2]; })()")
        await pg.mouse.click(hb[0], hb[1]); await pg.wait_for_timeout(250)
        check('clicking a PDF highlight offers its choices', await pg.is_visible('#rdHlPop'))
        await pg.click('#rdHlPop [data-hx=del]'); await pg.wait_for_timeout(250)
        check('highlight removed', not await pg.evaluate("!!document.querySelector('.rd-hl.c-b')"))
        word = await pg.evaluate("(() => { const t = [...document.querySelectorAll('.rd-page[data-n=\"1\"] .textLayer span')].map(s => s.textContent).join(' ').match(/[A-Za-z]{6,}/g); return t[0]; })()")
        await pg.fill('#rdFind', word); await pg.press('#rdFind', 'Enter'); await pg.wait_for_timeout(1500)
        fl = await pg.eval_on_selector_all('#rdTab [data-fi]', 'e => e.length')
        check('PDF find lists matches with pages', fl >= 1 and (await pg.eval_on_selector_all('#rdTab .rd-fnd b', 'e => e.map(x => x.textContent)'))[0].startswith('p. '), [word, fl])
        check('current match marked on the page', await pg.evaluate("!!document.querySelector('.textLayer span.rd-hit.cur')"))
        await pg.evaluate("""() => { window.SAID = []; speechSynthesis.speak = u => { SAID.push(u.text); }; speechSynthesis.cancel = () => {}; }""")
        await pg.evaluate("goPage(1)"); await pg.wait_for_timeout(300)
        await pg.click('#rdRead'); await pg.wait_for_timeout(600)
        check('reads a PDF page aloud, a sentence at a time', len(await pg.evaluate("SAID")) == 1 and await pg.is_visible('#rdTts') and (await pg.inner_text('#rdTtsPos')).startswith('p. '), await pg.evaluate("SAID"))
        check('the sentence is shaded', await pg.evaluate("CSS.highlights.has('rd-tts')"))
        await pg.click('#rdTtsStop'); await pg.wait_for_timeout(100)
        check('stop', not await pg.is_visible('#rdTts') and not await pg.evaluate("CSS.highlights.has('rd-tts')"))

        # ---- search inside sources finds the book too
        cnt = await pg.evaluate("ftxIndex().then(() => ftxSearch('porters').length)")
        check('search inside sources reads ePubs', cnt >= 1, cnt)
        lab = await pg.evaluate("(() => { const r = ftxSearch('porters')[0]; return r ? r.R[0].label + '|' + r.R[0].ep : ''; })()")
        check('…by chapter', lab.startswith('Chapter') and lab.endswith('|true'), lab)

        # ---- saved and read back
        pj = await pg.evaluate("JSON.parse(JSON.stringify(normalize(JSON.parse(projectJSON()))))")
        s = [x for x in pj['sources'] if x['csl'].get('title') == 'The Salt Road'][0]
        check('highlights saved with the source', s.get('hls') and s['hls'][0]['h'][0].get('a') is not None, s.get('hls'))
        # phone width
        await pg.set_viewport_size({'width': 390, 'height': 800}); await pg.wait_for_timeout(400)
        await pg.set_input_files('#filePdf', _os.path.join(OUT, 'salt.epub')); await pg.wait_for_selector('.rd-page.ep-ch', timeout=8000); await pg.wait_for_timeout(500)
        ov = await pg.evaluate("(() => { const r = document.querySelector('#reader').getBoundingClientRect(); return [...document.querySelectorAll('#reader .rd-bar2 > *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > r.right + 1).map(e => e.id || e.className); })()")
        check('reader bar fits a phone', not ov, ov)
        await pg.screenshot(path=_os.path.join(OUT, 't56-phone.png'))
        await b.close()
    print('ERRS', json.dumps(errs))
    _sys.exit(0 if ok else 1)

asyncio.run(main())
