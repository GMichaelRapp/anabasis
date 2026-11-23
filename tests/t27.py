"""Note text on citations: your own words after a citation, in note styles, author-date styles and OSINT, through every export."""
import asyncio, json, os, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

NOTE = 'Dakyns places the mountain farther east; see *History of Greece*.'


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra); ok = ok and bool(cond)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true}))")
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("""() => {
          const s = addSource({ type: 'book', title: 'Anabasis', author: [{ family: 'Xenophon' }], translator: [{ family: 'Dakyns', given: 'H. G.' }], publisher: 'Macmillan', issued: { 'date-parts': [[1897]] } });
          window.SID = s.id;
          addDoc(newDoc('Notes test', '<h1>Notes test</h1><p>The army saw the sea.</p><p>Later they reached Trapezus.</p>'));
          openDoc(P.docs[P.docs.length - 1].id);
          const d = curDoc(); d.style = 'chicago-notes-bibliography'; $('#docStyle').value = d.style;
          const p = editor.querySelector('p'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false);
          const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); saveSelectionNow(); }""")
        # ---- the dialog: add note text to a new citation
        await pg.click('#btnCite'); await pg.wait_for_timeout(300)
        await pg.click('#citePick li[data-id]:has-text("Anabasis")'); await pg.fill('#citeCluster .loc', 'IV.7')
        await pg.fill('#citeNote', NOTE); await pg.wait_for_timeout(400)
        prev = await pg.inner_text('#citePreview')
        check('preview shows the note text after the citation', 'IV.7. Dakyns places' in prev, prev[:160])
        await pg.click('#citeOk'); await pg.wait_for_timeout(600)
        # a second citation of the same source, and a plain text footnote, in the next paragraph
        await pg.evaluate("""() => { const p = editor.querySelectorAll('p')[1]; p.insertAdjacentHTML('beforeend', citeHTML([{ id: SID, locator: 'V.1', label: 'page' }]) + fnHTML('A plain footnote.')); onEdit(); renderRefs(true); }""")
        await pg.wait_for_timeout(500)
        notes = await pg.evaluate("[...document.querySelectorAll('#refs .note')].map(p => p.innerText)")
        check('Chicago: note 1 is citation then commentary', len(notes) == 3 and re.search(r'^1\. Xenophon, Anabasis, trans\. H\. G\. Dakyns \(Macmillan, 1897\), IV\.7\. Dakyns places the mountain farther east; see History of Greece\.$', notes[0]), notes)
        check('Chicago: italics in the note text', await pg.evaluate("!!document.querySelector('#refs .note em, #refs .note i')"))
        check('Chicago: numbering continues (short form, then text footnote)', notes[1].startswith('2. Xenophon, Anabasis, V.1') and notes[2].startswith('3. A plain footnote'), notes[1:])
        # ---- editing keeps it; the marker stores it
        await pg.click('#editor p .cite'); await pg.click('.pop [data-a=edit]'); await pg.wait_for_timeout(400)
        check('editing a citation reloads its note text', await pg.input_value('#citeNote') == NOTE)
        await pg.fill('#citeNote', NOTE.replace('farther east', 'farther west')); await pg.click('#citeOk'); await pg.wait_for_timeout(500)
        check('updated note text renders', 'farther west' in await pg.inner_text('#refs'))
        saved = json.loads(await pg.evaluate("projectJSON()"))
        html = [d for d in saved['docs'] if d['title'] == 'Notes test'][0]['html']
        check('saved in the project file as data-cnote', 'data-cnote="Dakyns places the mountain farther west' in html)
        check('nothing generated leaks into the saved file', 'data-cp-' not in html)
        # ---- exports in a note style
        md = await pg.evaluate("exportMarkdown(curDoc())")
        check('Markdown: commentary in footnote 1', re.search(r'\[\^1\]: Xenophon, \*Anabasis\*, trans\. H\. G\. Dakyns \(Macmillan, 1897\), IV\.7\. Dakyns places the mountain farther west; see \*History of Greece\*\.', md), md[-500:])
        ex = await pg.evaluate("(() => { const x = buildExport(curDoc(), 'paged'); return x.body; })()")
        check('PDF: commentary travels with the footnote', 'farther west' in ex and 'fn-note' in ex)
        await pg.click('#btnExport')
        async with pg.expect_download() as d: await pg.click('#exportMenu [data-x=docx]')
        p = OUT + '/notes-test.docx'; await (await d.value).save_as(p)
        fx = zipfile.ZipFile(p).read('word/footnotes.xml').decode()
        check('Word: commentary inside a real footnote', 'farther west' in fx and 'History of Greece' in fx)
        await pg.keyboard.press('Escape')
        # ---- author-date: parenthetical stays, commentary becomes a numbered footnote
        await pg.select_option('#docStyle', 'apa'); await pg.wait_for_timeout(800)
        cite = await pg.inner_text('#editor p .cite')
        check('APA: parenthetical plus note number', re.search(r'\(Xenophon, 1897, p\. IV\.7\)1$', cite.replace('​', '')), cite)
        notes = await pg.evaluate("[...document.querySelectorAll('#refs .note')].map(p => p.innerText)")
        check('APA: commentary and the text footnote numbered in order', notes[:2] == ['1. Dakyns places the mountain farther west; see History of Greece.', '2. A plain footnote.'], notes)
        html = await pg.evaluate("exportStandaloneHTML(curDoc())")
        check('APA HTML: parenthetical kept, note reference after it', re.search(r'\(Xenophon, 1897, p\. IV\.7\)</span><sup class="fnref">1</sup>', html) is not None, re.findall(r'IV\.7\).{0,80}', html)[:1])
        check('APA HTML: no stray marker number in the text', 'cite-nref' not in html)
        md = await pg.evaluate("exportMarkdown(curDoc())")
        check('APA Markdown: footnote reference and text', '(Xenophon, 1897, p. IV.7)[^1]' in md and '[^1]: Dakyns places' in md, md[:300])
        epub = await pg.evaluate("(() => buildExport(curDoc(), 'epub').body)()")
        check('APA ePub: tappable note reference', 'class="noteref" data-n="1"' in epub)
        await pg.click('#btnExport')
        async with pg.expect_download() as d: await pg.click('#exportMenu [data-x=docx]')
        p = OUT + '/notes-test-apa.docx'; await (await d.value).save_as(p)
        z = zipfile.ZipFile(p); fx = z.read('word/footnotes.xml').decode(); dx = z.read('word/document.xml').decode()
        check('APA Word: commentary is a real footnote', 'farther west' in fx and 'w:footnoteReference' in dx)
        await pg.keyboard.press('Escape')
        # ---- OSINT Style Guide
        await pg.select_option('#docStyle', 'osint'); await pg.wait_for_timeout(800)
        notes = await pg.evaluate("[...document.querySelectorAll('#refs .note')].map(p => p.innerText)")
        check('OSINT: commentary after the citation', notes and notes[0].endswith('Dakyns places the mountain farther west; see History of Greece.'), notes[:1])
        # ---- removing the note text
        await pg.select_option('#docStyle', 'chicago-notes-bibliography'); await pg.wait_for_timeout(500)
        await pg.click('#editor p .cite'); await pg.click('.pop [data-a=edit]'); await pg.wait_for_timeout(300); await pg.fill('#citeNote', ''); await pg.click('#citeOk'); await pg.wait_for_timeout(500)
        check('clearing the note text removes it', 'farther west' not in await pg.inner_text('#refs') and not await pg.evaluate("editor.querySelector('.cite').hasAttribute('data-cnote')"))
        # ---- paste keeps it
        kept = await pg.evaluate("(() => { const h = sanitize('<p>x ' + citeHTML([{ id: SID }], 'A pasted note.') + '</p>'); return h.includes('data-cnote'); })()")
        check('copy and paste inside Anabasis keeps the note text', kept)
        print('ERRS', errs)
        await b.close()
    sys.exit(0 if ok and not errs else 1)
asyncio.run(main())
