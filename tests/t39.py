"""1.8.0: equations. The equation box (preview, problems, inline and display, numbering, editing, removing),
shortcuts, TeX typed as text, saving and pasting, hostile input, every export (Word as real Word equations,
Markdown, Pandoc, LaTeX, web page, EPUB), Word import back to TeX, the split view, and no network."""
import asyncio, json, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs, reqs = [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        # the hostile paste below carries onclick/onmouseover: Chrome reports the strict CSP refusing them the moment
        # the markup is parsed (even into an inert document), before the paste filter strips them. That report is expected.
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Executing inline event handler' not in m.text else None)
        pg.on('request', lambda r: reqs.append(r.url) if not r.url.startswith(('data:', 'blob:', 'file:', 'about:')) and '127.0.0.1' not in r.url and 'localhost' not in r.url else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        check('MathJax isn’t loaded until an equation needs it', await pg.evaluate("() => !window.MathJax && !MATH.ready"))

        # ---- the equation box: inline, in a sentence
        await pg.evaluate("() => { editor.innerHTML = '<p>Einstein wrote  in 1905.</p><p><br></p>'; syncEditor(); const t = editor.querySelector('p').firstChild; const r = document.createRange(); r.setStart(t, 15); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); }")
        await pg.click('#btnInsert'); await pg.click('.ins-menu [data-i=eq]'); await pg.wait_for_timeout(900)
        r = await pg.evaluate("() => ({ open: $('#eqDlg').open, inline: $('#eqInline').checked, num: $('#eqNum').disabled, title: $('#eqTitle').textContent })")
        check('the toolbar button opens the equation box, set to “in the sentence” when the caret is in text', r == {'open': True, 'inline': True, 'num': True, 'title': 'Insert an equation'}, r)
        await pg.fill('#eqTex', r'\foo + 1'); await pg.wait_for_timeout(400)
        check('…a command MathJax doesn’t know is pointed out', '\\foo' in await pg.inner_text('#eqMsg'), await pg.inner_text('#eqMsg'))
        await pg.fill('#eqTex', r'\frac{a}{b'); await pg.wait_for_timeout(400)
        check('…so is a missing brace', 'brace' in (await pg.inner_text('#eqMsg')).lower(), await pg.inner_text('#eqMsg'))
        await pg.fill('#eqTex', 'E = mc^2'); await pg.wait_for_timeout(400)
        check('…and a good one shows a preview at full size, with no complaint', await pg.locator('#eqPrev svg').count() == 1 and (await pg.inner_text('#eqMsg')) == '' and await pg.evaluate("() => $('#eqPrev svg').getBoundingClientRect().width > 60"))
        await pg.click('#eqSnips button:has-text("Fraction")'); await pg.wait_for_timeout(200)
        check('…the quick pieces go in at the cursor', (await pg.input_value('#eqTex')) == r'E = mc^2\frac{a}{b}')
        await pg.fill('#eqTex', 'E = mc^2')
        await pg.click('#eqOk'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => { const m = editor.querySelector('span.math'); return m && { tex: m.dataset.tex, ce: m.getAttribute('contenteditable'), svg: !!(m.shadowRoot && m.shadowRoot.querySelector('svg')), light: m.textContent, text: editor.querySelector('p').textContent, mml: !!(m.shadowRoot && m.shadowRoot.querySelector('mjx-assistive-mml math')) }; }")
        check('Insert puts it in the sentence, drawn, as one piece', r and r['tex'] == 'E = mc^2' and r['ce'] == 'false' and r['svg'] and r['text'].replace('\xa0', ' ') == 'Einstein wrote E = mc^2 in 1905.', r)
        check('…readable by screen readers (MathML) and saved as its TeX', r and r['mml'] and r['light'] == 'E = mc^2')
        saved = await pg.evaluate("() => { syncEditor(); return curDoc().html; }")
        check('…the saved document holds the TeX, not the drawing', 'data-tex="E = mc^2"' in saved and '<svg' not in saved and 'data-cp-r' not in saved, saved[:300])

        # ---- display, numbered, from an empty paragraph; then an unnumbered one; numbering follows
        await pg.evaluate("() => { const p = editor.querySelectorAll('p')[1]; const r = document.createRange(); r.selectNodeContents(p); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); }")
        await pg.keyboard.press('Alt+Equal'); await pg.wait_for_timeout(500)
        check('Alt+= (as in Word) opens it, set to “on its own line” in an empty paragraph', await pg.evaluate("() => $('#eqDlg').open && $('#eqBlock').checked && $('#eqNum').checked && !$('#eqNum').disabled"))
        await pg.fill('#eqTex', r'x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}'); await pg.keyboard.press('Control+Enter'); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { const p = editor.lastElementChild; const r = document.createRange(); r.selectNodeContents(p); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); }")
        await pg.keyboard.press('Control+Alt+KeyE'); await pg.wait_for_timeout(400)
        await pg.fill('#eqTex', r'\int_0^1 x\,dx = \tfrac12'); await pg.uncheck('#eqNum'); await pg.click('#eqOk'); await pg.wait_for_timeout(400)
        await pg.evaluate("() => { const p = editor.lastElementChild; const r = document.createRange(); r.selectNodeContents(p); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); openEq(); }"); await pg.wait_for_timeout(300)
        await pg.fill('#eqTex', r'\sum_{i=1}^n i = \frac{n(n+1)}{2}'); await pg.click('#eqOk'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => [...editor.querySelectorAll('p.eq')].map(p => [p.className, p.getAttribute('data-cp-n') || '', p.shadowRoot.querySelector('.n').textContent, !!p.shadowRoot.querySelector('mjx-container[display=true]')])")
        check('display equations sit on their own line, numbered (1), (2) and skipping unnumbered ones', r == [['eq num', '(1)', '(1)', True], ['eq', '', '', True], ['eq num', '(2)', '(2)', True]], r)
        await pg.screenshot(path=f'{OUT}/t39-equations.png')

        # ---- editing: click, change, switch kind, remove
        await pg.click('#editor p.eq >> nth=0'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ t: $('#eqTitle').textContent, tex: $('#eqTex').value, del: !$('#eqDel').classList.contains('hidden'), ok: $('#eqOk').textContent })")
        check('clicking an equation opens it for editing', r['t'] == 'Edit equation' and r['tex'].startswith('x = ') and r['del'] and r['ok'] == 'Update', r)
        await pg.fill('#eqTex', r'x_{1,2} = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}'); await pg.click('#eqOk'); await pg.wait_for_timeout(400)
        check('…Update changes it in place', await pg.evaluate("() => editor.querySelector('p.eq').dataset.tex.startsWith('x_{1,2}') && editor.querySelectorAll('p.eq').length === 3"))
        await pg.click('#editor span.math'); await pg.wait_for_timeout(300); await pg.check('#eqBlock'); await pg.click('#eqOk'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ p0: editor.querySelector('p').textContent, eq: editor.children[1].matches('p.eq') && editor.children[1].dataset.tex, n: [...editor.querySelectorAll('p.eq')].map(p => p.getAttribute('data-cp-n') || '') })")
        check('…switching an inline equation to its own line puts it after its paragraph, and renumbers', r['p0'].replace('\xa0', ' ') == 'Einstein wrote in 1905.' and r['eq'] == 'E = mc^2' and r['n'] == ['(1)', '(2)', '', '(3)'], r)
        await pg.click('#editor p.eq >> nth=0'); await pg.wait_for_timeout(300); await pg.click('#eqDel'); await pg.wait_for_timeout(300)
        check('…Remove takes it out', await pg.evaluate("() => editor.querySelectorAll('p.eq').length === 3 && !editor.querySelector('[data-tex=\"E = mc^2\"]')"))

        # ---- selection with TeX in it, and Undo
        await pg.evaluate("() => { editor.insertAdjacentHTML('afterbegin', '<p>where $\\\\alpha_i$ is a weight</p>'); const t = editor.firstChild.firstChild; const r = document.createRange(); r.setStart(t, 6); r.setEnd(t, 16); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); }")
        await pg.keyboard.press('Alt+Equal'); await pg.wait_for_timeout(300)
        check('selected TeX in dollars fills the box, without the dollars', (await pg.input_value('#eqTex')) == r'\alpha_i' and await pg.is_checked('#eqInline'), await pg.input_value('#eqTex'))
        await pg.click('#eqOk'); await pg.wait_for_timeout(400)
        check('…and Insert replaces the selection', await pg.evaluate("() => editor.firstChild.textContent.replace(/\\u00a0/g, ' ') === 'where \\\\alpha_i is a weight' && !!editor.firstChild.querySelector('span.math')"), await pg.evaluate("() => editor.firstChild.innerHTML"))
        await pg.keyboard.press('Control+z'); await pg.wait_for_timeout(400)
        check('Undo takes the equation back out', await pg.evaluate("() => !editor.firstChild.querySelector('span.math')"), await pg.evaluate("() => editor.firstChild.innerHTML"))
        await pg.keyboard.press('Control+Shift+z'); await pg.wait_for_timeout(600)
        check('…and Redo brings it back, drawn again', await pg.evaluate("() => { const m = editor.firstChild.querySelector('span.math'); return !!(m && m.shadowRoot && m.shadowRoot.querySelector('svg')); }"))

        # ---- TeX typed as text
        await pg.evaluate("""() => { editor.insertAdjacentHTML('beforeend', '<p>It costs $5 and $10, while $x^2$ and \\\\(y_1\\\\) are math. Escaped \\\\$ stays.</p><p>$$\\\\int_a^b f$$</p><p>\\\\[ e^{i\\\\pi} + 1 = 0 \\\\]</p>'); syncEditor(); texTextToMath(); }"""); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => { const ps = [...editor.children].slice(-3); return { text: ps[0].textContent, inl: [...ps[0].querySelectorAll('span.math')].map(m => m.dataset.tex), d: ps.slice(1).map(p => p.matches('p.eq') && p.dataset.tex), toast: $('#toast').textContent }; }")
        check('“Turn TeX into equations” finds $…$ and \\(…\\), and leaves money alone', r['inl'] == ['x^2', 'y_1'] and 'costs $5 and $10' in r['text'], r)
        check('…and $$…$$ or \\[…\\] paragraphs become display equations', r['d'] == [r'\int_a^b f', r'e^{i\pi} + 1 = 0'] and '4 pieces' in r['toast'], r)

        # ---- word count and reading aloud
        r = await pg.evaluate("() => { updateWordCount(); return { wc: $('#wordCount').textContent, tts: plainBlocks().map(b => b.text).filter(t => /Equation|equation|x\\^2|alpha/.test(t)) }; }")
        check('display equations don’t count as words', r['wc'].startswith(str(await pg.evaluate("() => { const c = editor.cloneNode(true); c.querySelectorAll('p.eq').forEach(p => p.remove()); c.querySelectorAll('span.math').forEach(m => m.textContent = 'x'); c.querySelectorAll('p,h1,h2,h3,li,blockquote').forEach(b => b.append(' ')); return c.textContent.trim().split(/\\s+/).filter(Boolean).length; }")) + ' words'), r)
        check('reading aloud says “equation” rather than reading TeX', any(t == 'Equation.' for t in r['tts']) and not any(re.search(r'alpha|\^', t) for t in r['tts']), r['tts'])

        # ---- pasting: equations survive, nothing else does
        await pg.evaluate("""() => { const dt = new DataTransfer();
          dt.setData('text/html', '<p>Pasted <span class="math" data-tex="a^2+b^2" onclick="alert(1)" style="color:red">junk<b>x</b></span> and</p><p class="eq num" data-tex="c^2" onmouseover="alert(2)">c</p><p class="eq" data-tex="\\\\href{javascript:alert(3)}{click}">x</p><p class="eq">no tex</p>');
          editor.insertAdjacentHTML('beforeend', '<p>Paste here: </p>'); const r = document.createRange(); r.selectNodeContents(editor.lastElementChild); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r);
          editor.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }"""); await pg.wait_for_timeout(700)
        r = await pg.evaluate("""() => { const all = [...editor.querySelectorAll('[data-tex]')]; const m = all.find(x => x.dataset.tex === 'a^2+b^2'), e = all.find(x => x.dataset.tex === 'c^2'), h = all.find(x => /href/.test(x.dataset.tex));
          return { m: m && [m.getAttribute('onclick'), m.getAttribute('style'), m.textContent, m.getAttribute('contenteditable')], e: e && [e.className, e.getAttribute('onmouseover')], link: h ? !!h.shadowRoot.querySelector('a, [href]') : 'none', bare: editor.innerHTML.includes('class="eq">no tex') }; }""")
        check('pasted equations keep their TeX and lose everything else', r['m'] == [None, None, 'a^2+b^2', 'false'] and r['e'] == ['eq num', None], r)
        check('…\\href makes no link (that part of MathJax is off), and a class without TeX is just a paragraph', r['link'] is False and not r['bare'], r)

        # ---- exports
        await pg.evaluate("() => { editor.innerHTML = '<h1>Results</h1><p>The energy is ' + eqHTML('E = mc^2', false) + ' here.</p>' + eqHTML('\\\\sum_{i=1}^{n} x_i = \\\\left( \\\\frac{a}{b} \\\\right)^2', true, true) + eqHTML('|x| \\\\le \\\\lim_{t \\\\to 0} \\\\sqrt{t}', true, false) + eqHTML('\\\\begin{aligned} y &= 2x \\\\\\\\ &= 4 \\\\end{aligned}', true, true); syncEditor(); hydrateImages(); renumberFigures(); }"); await pg.wait_for_timeout(600)
        md = await pg.evaluate("() => exportMarkdown(curDoc())")
        check('Markdown: $…$ in the sentence and $$…$$ blocks, TeX unescaped', 'The energy is $E = mc^2$ here.' in md and '$$\n\\sum_{i=1}^{n} x_i = \\left( \\frac{a}{b} \\right)^2\n$$' in md, md)
        html = await pg.evaluate("() => exportStandaloneHTML(curDoc())")
        check('web page: equations are drawn (SVG), numbered, and styled', html.count('<mjx-container') == 4 and '<span class="eq-n">(1)</span>' in html and '<span class="eq-n">(2)</span>' in html and 'mjx-assistive-mml{' in html.replace(' ', '') and 'data-tex' not in html)
        ss = await pg.evaluate("() => JSON.stringify(substackBuild(curDoc()))")
        check('Substack: TeX in dollars (it drops pasted drawings), for its own equation block', '$E = mc^2$' in ss and '<svg' not in ss)
        async with pg.expect_download() as d: await pg.evaluate("() => exportLatex(curDoc())")
        z = zipfile.ZipFile(await (await d.value).path()); tex = z.read([n for n in z.namelist() if n.endswith('.tex')][0]).decode()
        check('LaTeX: \\(…\\) inline, equation for numbered, \\[…\\] for unnumbered, amsmath loaded', '\\(E = mc^2\\)' in tex and '\\begin{equation}\n\\sum_{i=1}^{n}' in tex and '\\[\n|x| \\le' in tex and '\\usepackage{amsmath,amssymb}' in tex and 'mc\\^{}' not in tex, tex[:1500])
        async with pg.expect_download() as d: await pg.evaluate("() => exportPandoc(curDoc())")
        z = zipfile.ZipFile(await (await d.value).path()); pmd = z.read([n for n in z.namelist() if n.endswith('.md')][0]).decode()
        check('Pandoc: dollars, as Pandoc reads them', '$E = mc^2$' in pmd and '$$\n|x| \\le' in pmd)
        async with pg.expect_download() as d: await pg.evaluate("() => exportDocx(curDoc())")
        dpath = await (await d.value).path(); z = zipfile.ZipFile(dpath); xml = z.read('word/document.xml').decode()
        check('Word: four real Word equations, one of them a centred unnumbered block', xml.count('<m:oMath>') == 4 and xml.count('<m:oMathPara>') == 1 and 'xmlns:m=' in xml)
        check('…numbered ones carry their number at the right margin', '(1)</w:t>' in xml and '(2)</w:t>' in xml and xml.count('w:val="right"') >= 2)
        check('…built from Word’s own pieces: fraction, sum, bracket, root, limit, aligned rows', all(t in xml for t in ['<m:f>', '<m:nary>', '<m:chr m:val="∑"/>', '<m:d>', '<m:begChr m:val="|"/>', '<m:rad>', '<m:limLow>', '<m:func>', '<m:eqArr>', '<m:aln/>']), [t for t in ['<m:f>', '<m:nary>', '<m:d>', '<m:rad>', '<m:limLow>', '<m:func>', '<m:eqArr>', '<m:aln/>'] if t not in xml])
        # …and back in again
        await pg.set_input_files('#fileDocx', dpath); await pg.wait_for_timeout(2500)
        r = await pg.evaluate("() => ({ t: $('#toast').textContent, inl: [...editor.querySelectorAll('span.math')].map(m => m.dataset.tex), d: [...editor.querySelectorAll('p.eq')].map(p => [p.className, p.dataset.tex]), svg: editor.querySelectorAll('p.eq').length && !!editor.querySelector('p.eq').shadowRoot })")
        check('Word import turns Word equations back into TeX equations, and says how many', 'with 4 equations' in r['t'] and r['inl'] == ['E=mc^{2}'], r)
        check('…a paragraph holding one equation (and its number) is a display equation again', [x[0] for x in r['d']] == ['eq num', 'eq', 'eq num'] and r['d'][0][1].startswith('\\sum_{i=1}^{n} x_{i}=') and '\\left( \\frac{a}{b} \\right)' in r['d'][0][1] and '\\lim_{t\\to 0}' in r['d'][1][1] and r['d'][2][1].startswith('\\begin{aligned} y&=2x \\\\ &=4'), r)
        check('…and they draw', r['svg'])

        # EPUB
        await pg.evaluate("() => { editor.innerHTML = '<p>Inline ' + eqHTML('a^2', false) + '.</p>' + eqHTML('b^2', true, true); syncEditor(); }")
        async with pg.expect_download() as d: await pg.evaluate("() => exportEpub(curDoc())")
        z = zipfile.ZipFile(await (await d.value).path()); opf = z.read('OEBPS/content.opf').decode(); c1 = z.read('OEBPS/c1.xhtml').decode()
        check('EPUB: equations are labelled SVG, and the book says it uses SVG', 'properties="svg"' in opf and 'role="img" aria-label="a^2"' in c1 and '<mjx-container' not in c1 and '(1)' in c1, c1[:600])

        # ---- save and reopen; the split view
        saved = await pg.evaluate("() => { syncEditor(); return projectJSON(); }")
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'x.json'); }", saved); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("() => ({ n: editor.querySelectorAll('[data-tex]').length, want: (curDoc().html.match(/data-tex=/g) || []).length, all: P.docs.reduce((k, d) => k + (d.html.match(/data-tex=/g) || []).length, 0), drawn: [...editor.querySelectorAll('[data-tex]')].every(e => e.shadowRoot && e.shadowRoot.querySelector('svg')), num: editor.querySelector('p.eq.num').getAttribute('data-cp-n') })")
        check('equations survive saving and reopening, drawn and numbered', r['n'] >= 2 and r['n'] == r['want'] and r['all'] >= 6 and r['drawn'] and r['num'] == '(1)', r)
        await pg.evaluate("() => splitOpen('doc')"); await pg.wait_for_timeout(800)
        check('the split view shows them drawn too', await pg.evaluate("() => { const e = $('#spBody p.eq'); return !!(e && e.shadowRoot && e.shadowRoot.querySelector('svg') && e.shadowRoot.querySelector('.n').textContent === '(1)'); }"))
        await pg.evaluate("() => splitClose()")
        await b.close()
    check('nothing was fetched from the network', not reqs, reqs)
    print('ERRS', [e for e in errs if 'favicon' not in e])
    return ok and not [e for e in errs if 'favicon' not in e]

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
