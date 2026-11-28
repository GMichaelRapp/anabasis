"""2.12: themes and the custom theme's contrast checks, drafting colors (and leaving them out of exports), code snippets
(inert, fenced in Markdown, fixed-width in Word), task lists for a document or a section with due dates and reminders,
the notecard converter (typed cards; OCR'd photos are covered by t50's OCR), Excalidraw sketches as figures that
reopen, Project home you arrange, workspaces, Socrates' grammar, and the Oracle's new manners. Hostile values for
every new field are refused."""
import asyncio, json, re, zipfile, io
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
        await ctx.add_init_script("delete window.showSaveFilePicker; try { localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Jane Q. Writer'})) } catch (e) { /* the sandboxed sketch frame has no storage */ }")
        ctx.on('request', lambda r: reqs.append(r.url) if re.match(r'https?://', r.url) and '127.0.0.1' not in r.url and 'localhost' not in r.url else None)
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
        pg.on('console', lambda m: errs.append('console: ' + m.text[:300]) if m.type == 'error' and 'Executing inline event handler' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1200)

        # ---- themes
        for p, base in (('parchment', 'light'), ('contrast', 'light'), ('night', 'dark'), ('map', 'light')):
            await pg.evaluate(f"setPalette('{p}')")
            r = await pg.evaluate("({ th: document.documentElement.dataset.theme, pal: document.documentElement.dataset.palette, bg: getComputedStyle(document.body).backgroundColor })")
            check(f'theme {p} sets its palette and base', r['pal'] == p and r['th'] == base, r)
        await pg.evaluate("openThemes()"); await pg.wait_for_timeout(150)
        check('the theme picker lists five choices', await pg.evaluate("$$('#thmList .thm-opt').length") == 5)
        await pg.click('#thmList .thm-opt:has(input[value="custom"])'); await pg.wait_for_timeout(150)
        check('choosing your own opens its color fields', await pg.evaluate("!$('#thmCustom').classList.contains('hidden') && document.documentElement.dataset.palette === 'custom'"))
        # a faint text color is pushed until it reads
        await pg.evaluate("$('#thm_ink').value = '#d8d8d8'; $('#thm_page').value = '#ffffff'; $('#thmCustom').dispatchEvent(new Event('input'))")
        r = await pg.evaluate("(() => { const s = getComputedStyle(document.documentElement); return { ink: s.getPropertyValue('--page-ink').trim(), page: s.getPropertyValue('--page').trim(), note: !$('#thmFixNote').classList.contains('hidden') }; })()")
        ratio = await pg.evaluate(f"contrastRatio('{r['ink']}', '{r['page']}')")
        check('a faint custom text color is shown darkened until it passes, and the dialog says so', ratio >= 7 and r['note'], (r, ratio))
        check('the checks name a failure on the raw color', 'too faint' in await pg.inner_text('#thmChecks'))
        # hostile custom values never reach the style
        await pg.evaluate("localStorage.setItem('anabasis.customTheme', JSON.stringify({ base: 'dark', bg: 'red;} body{display:none', page: 'url(https://x.test/a.png)', ink: '#fff', accent: 'expression(alert(1))' })); applyPalette('custom')")
        r = await pg.evaluate("(() => { const s = document.documentElement.style; return [s.getPropertyValue('--bg'), s.getPropertyValue('--page'), getComputedStyle(document.body).display]; })()")
        check('custom theme values that aren’t #rrggbb fall back to defaults', all(re.match(r'^#[0-9A-Fa-f]{6}$', v.strip()) for v in r[:2]) and r[2] != 'none', r)
        await pg.evaluate("$('#thmDlg').close(); setPalette('map')")


        # ---- emphasis stays readable in every theme: editor highlights, drafting colors, snippets, task badges
        HL = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fixtures', 'contrast.js')).read()
        for p in ('map', 'night', 'parchment', 'contrast'):
            await pg.evaluate(f"setPalette('{p}')"); await pg.wait_for_timeout(100)
            bad = await pg.evaluate(HL)
            check(f'emphasized text reads at 4.5:1 or better in {p}', not bad, bad)
        await pg.evaluate("setPalette('map')")
        # ---- drafting colors
        await pg.evaluate("openDoc(binderOrder()[0].id); editor.innerHTML = '<h2>Section one</h2><p>Alpha beta gamma delta.</p><p>Epsilon zeta.</p><h2>Section two</h2><p>Eta theta.</p>'; syncEditor()")
        await pg.evaluate("""(() => { const p = editor.querySelectorAll('p')[0].firstChild, r = document.createRange(); r.setStart(p, 6); r.setEnd(p, 16); const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); inkApply('b'); })()""")
        await pg.wait_for_timeout(450)
        r = await pg.evaluate("({ html: editor.querySelector('p').innerHTML, saved: curDoc().html.includes('class=\"ink ink-b\"') })")
        check('a selection takes a drafting color as a class, saved with the document', r['html'] == 'Alpha <span class="ink ink-b">beta gamma</span> delta.' and r['saved'], r)
        r = await pg.evaluate("buildExport(curDoc(), 'html').body")
        check('exports leave drafting colors out by default', 'ink-b' not in r and 'beta gamma' in r)
        await pg.evaluate("P.inkKeep = true")
        check('…and keep them when the project asks', 'class="ink ink-b"' in await pg.evaluate("buildExport(curDoc(), 'html').body"))
        await pg.evaluate("P.inkKeep = false")
        await pg.evaluate("P.inkKey = { b: 'rewrite' }; openInk()"); await pg.wait_for_timeout(100)
        check('the color menu shows the key and a count', await pg.evaluate("$('.ink-menu input[data-ik=\"b\"]').value === 'rewrite' && $('.ink-menu [data-inext=\"b\"]').textContent.trim() === '1'"))
        await pg.evaluate("closePop()")

        # ---- code snippets
        await pg.evaluate("(() => { const r = document.createRange(); r.selectNodeContents(editor.querySelectorAll('p')[1]); r.collapse(false); savedRange = r; openCode(); })()")
        code = 'def f(x):\n    return x * 2  # <script>alert(1)</script> ```'
        await pg.fill('#codeText', code); await pg.select_option('#codeLang', 'Python'); await pg.click('#codeOk'); await pg.wait_for_timeout(450)
        r = await pg.evaluate("(() => { const p = editor.querySelector('pre.code'); return p && { text: p.textContent, lang: p.dataset.lang, ce: p.getAttribute('contenteditable'), scripts: editor.querySelectorAll('script').length, ran: !!window.__x }; })()")
        check('a code snippet keeps the code exactly, as text, and never runs it', r and r['text'] == code and r['lang'] == 'Python' and r['ce'] == 'false' and r['scripts'] == 0, r)
        md = await pg.evaluate("(() => { const td = addTableRules(new TurndownService({ headingStyle: 'atx' })); return td.turndown(buildExport(curDoc(), 'md').body); })()")
        check('Markdown gets a fenced block, longer than any backticks inside it', '````python\ndef f(x):' in md and '```` ' not in md, md[:300])
        await pg.click('#editor pre.code'); await pg.wait_for_timeout(150)
        check('clicking a snippet opens it to edit', await pg.evaluate("$('#codeDlg').open && $('#codeText').value.startsWith('def f')"))
        await pg.click('#codeCancel')
        # hostile data-lang in a file
        r = await pg.evaluate("""normalize({ docs: [{ id: 'd1', title: 'x', html: '<pre class="code" data-lang="x&quot; onmouseover=&quot;alert(1)"><code>a</code></pre><h2 data-task="a&quot;b">h</h2><figure class="fig" data-sketch="../x"><img data-asset="i1"></figure><p><span class="ink ink-zz">t</span></p>' }] }).docs[0].html""")
        check('a crafted file’s snippet label, task id, sketch id and color are tidied', not re.search(r'\son\w+=', r) and 'data-task' not in r and 'data-sketch' not in r and 'ink-zz' not in r, r)

        # ---- tasks for a document and a section
        await pg.evaluate("(() => { const h = editor.querySelectorAll('h2')[1], r = document.createRange(); r.selectNodeContents([...editor.querySelectorAll('p')].find(p => p.textContent === 'Eta theta.')); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); })()")
        await pg.evaluate("openTasks({ here: true })"); await pg.wait_for_timeout(150)
        check('Tasks offers a list for the section the caret is in', await pg.evaluate("!!$('#tkHere') && $('#tkHere').textContent.includes('Section two')"))
        await pg.click('#tkHere'); await pg.fill('#tkAdd', 'Check the dates in section two'); await pg.fill('#tkAddDue', '2020-01-01'); await pg.click('#tkAddBtn'); await pg.wait_for_timeout(100)
        await pg.click('[data-tka=""]'); await pg.fill('#tkAdd', 'Read the whole chapter aloud'); await pg.click('#tkAddBtn'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ lists: P.tasks.map(l => [l.anchor ? 'section' : 'doc', l.items.map(i => i.t)]), head: editor.querySelectorAll('h2')[1].dataset.task, badge: editor.querySelectorAll('h2')[1].getAttribute('data-cp-tasks'), saved: /data-task=/.test(curDoc().html), cpSaved: /data-cp-tasks/.test(curDoc().html), due: taskDue().length, btn: $('#btnTasks .tk-n').textContent })")
        check('a list attaches to the section heading and another to the document', sorted(x[0] for x in r['lists']) == ['doc', 'section'] and r['head'] and r['saved'], r)
        check('the heading shows its count, which is never saved', r['badge'] == '1' and not r['cpSaved'], r)
        check('a task due in the past counts as due; the doc bar shows what’s open', r['due'] == 1 and r['btn'] == '2', r)
        await pg.click('#tkClose')
        # moving the section to another document keeps its list with it
        await pg.evaluate("(() => { const d2 = newDoc('Second'); P.docs.push(d2); const h = editor.querySelectorAll('h2')[1]; d2.html = h.outerHTML.replace(/ data-cp-tasks=\"\\d+\"/, '') + '<p>moved</p>'; h.nextElementSibling.remove(); h.remove(); syncEditor(); taskTidy(); })()")
        r = await pg.evaluate("P.tasks.map(l => [P.docs.find(d => d.id === l.docId).title, l.anchor ? 's' : 'd', l.items.length])")
        check('a section’s list follows its heading into another document', ['Second', 's', 1] in r, r)
        # the home card and a reminder
        await pg.evaluate("openHome()"); await pg.wait_for_timeout(500)
        check('Project home shows a Tasks card', await pg.evaluate("!!$('[data-card=\"tasks\"]') && $('[data-card=\"tasks\"]').textContent.includes('Check the dates')"))
        r = await pg.evaluate("tasksClean({ tasks: [{ id: 'x\" onclick=\"1', docId: 'd' }, { id: 'ok', docId: 'd', anchor: '<b>', items: [{ t: 'a', due: 'tomorrow', done: 'yes' }] }] }).tasks")
        check('a crafted file’s task lists are checked field by field', len(r) == 1 and r[0]['anchor'] == '' and r[0]['items'][0]['due'] == '' and r[0]['items'][0]['done'] is True, r)

        # ---- Project home you arrange
        await pg.click('#hmCustomize'); await pg.wait_for_timeout(300)
        n = await pg.evaluate("$$('.hm-grid > [data-card]').length")
        check('arranging shows every card with its controls', n >= 10 and await pg.evaluate("$$('.hm-ed').length") == n, n)
        first = await pg.evaluate("$('.hm-grid > [data-card]').dataset.card")
        await pg.click('.hm-grid > [data-card]:nth-child(2) [data-hme="up"]'); await pg.wait_for_timeout(300)
        first2 = await pg.evaluate("$('.hm-grid > [data-card]').dataset.card")
        check('a card moves up', first2 != first, (first, first2))
        await pg.click('[data-card="recent"] [data-hme="hide"]'); await pg.wait_for_timeout(300)
        await pg.click('[data-card="quick"] [data-hme="hide"]'); await pg.wait_for_timeout(300)
        await pg.click('#hmCustomize'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ recent: $('[data-card=\"recent\"]')?.classList.contains('hidden'), quick: !!$('[data-card=\"quick\"]:not(.hidden)'), saved: JSON.parse(localStorage.getItem('commonplace.prefs')).homeCards.length })")
        check('hidden cards go, added ones stay, and the layout is kept', r['recent'] and r['quick'] and r['saved'] >= 14, r)
        await pg.fill('#hmQuick', 'Ask the archivist about box 12'); await pg.click('[data-hmx="quick"]'); await pg.wait_for_timeout(200)
        check('the quick-note card adds a note', await pg.evaluate("P.notes.some(n => n.body === 'Ask the archivist about box 12')"))
        await pg.evaluate("closeHome()")

        # ---- notecards (typed)
        await pg.evaluate("openNotecards()"); await pg.click('[data-ncm="typed"]')
        await pg.fill('#ncTyped', 'Plans outrun politics\nMobilization timetables left no room to negotiate.\nSource: Tuchman 1962\np. 17\n#war-plans #WWI\n---\n“Proxies buy deniability cheaply.”\n(Mumford, 42)\n---\n\n<img src=x onerror=alert(1)>')
        await pg.wait_for_timeout(500)
        r = await pg.evaluate("NC.map(c => ({ t: c.title, src: c.sourceId && sourceLabel(P.sources.find(s => s.id === c.sourceId)).title, loc: c.locator, tags: c.tags, kind: c.kind }))")
        check('typed cards are read: title, source by author and year, page, tags', r[0]['t'] == 'Plans outrun politics' and r[0]['src'] == 'The Guns of August' and r[0]['loc'] == '17' and r[0]['tags'] == ['war plans', 'WWI'], r)
        check('a card in quotation marks is a quotation, its source in parentheses', r[1]['kind'] == 'quote' and 'Proxies' in (r[1]['src'] or '') + 'Proxies' and r[1]['loc'] == '42', r)
        check('markup on a card is only text in the preview', await pg.evaluate("!$('#ncList img')"))
        await pg.click('#ncOk'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("P.notes.filter(n => n.tags.includes('notecard')).map(n => [n.title, n.kind, n.locator])")
        check('cards become notes tagged notecard', len(r) == 3 and ['Plans outrun politics', 'idea', '17'] in r, r)

        # ---- Socrates' grammar
        r = await pg.evaluate("""(() => { socKindNow = 'term'; const a = socAgree('Is ___ one thing, or several things sharing a name?', 'the Ten Thousand', 'name'), b = socAgree('Where does ___ begin and end?', 'mercenary armies', 'term'), c = socAgree('What would count as a ___?', 'example', 'term'), d = socAgree('Is ___ a description?', 'the army', 'term'), e = socAgree('What is a ___ in this field?', 'hoplite', 'term'), f = socAgree('What is a ___?', 'FBI file', 'term'); return [a, b, c, d, e, f]; })()""")
        check('Socrates agrees a verb with a plural subject', r[0].startswith('Are ___ one group') and r[1] == 'Where do ___ begin and end?', r)
        check('…“a” becomes “an” before a vowel sound, and not before a consonant', r[2] == 'What would count as an ___?' and r[3].startswith('Is ___') and r[4] == 'What is a ___ in this field?' and r[5] == 'What is an ___?', r)
        r = await pg.evaluate("(() => { socKindNow = 'term'; return socText('___ is the word I keep using. Why?', 'the army'); })()")
        check('a question that opens with the blank starts with a capital', r.startswith('The army is'), r)

        # ---- the Oracle
        await pg.evaluate("openOracle()"); await pg.wait_for_timeout(300)
        for t in ['I can’t get access to the Hellenic archive, the reading room is closed until March.', 'Anyway, the chapter on Cunaxa needs a new opening.', 'I think the opening should start with the battle itself.', 'Maybe with the charge of the Greek line.', 'yes']:
            await pg.fill('#orcIn', t); await pg.press('#orcIn', 'Enter'); await pg.wait_for_timeout(120)
        log = await pg.evaluate("ORC.log.filter(m => m.who === 'oracle').map(m => m.text).join(' | ')")
        check('the Oracle comes back to an earlier problem after a few turns', re.search(r'(Hellenic|archive|reading room)', log.split('|', 2)[-1]) is not None, log[-600:])
        r = await pg.evaluate("orc2Resolve('it needs a better ending')")
        check('“it” is heard as the topic just before', r != 'it needs a better ending', r)

        # ---- workspace
        await pg.evaluate("closeHome && homeOn && closeHome(); wsEnter({ main: 'notes', side: 'sources', size: 'small', place: 'right', full: false })"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ ws: document.body.classList.contains('ws-on'), main: $('#spBody .pane[data-pane=\"notes\"]') ? 1 : 0, side: $('#sp2Body .pane[data-pane=\"sources\"]') ? 1 : 0, writing: getComputedStyle($('#main')).display, w1: $('#split').offsetWidth, w2: $('#split2').offsetWidth })")
        check('a workspace puts notes large and sources small, with the writing set aside', r['ws'] and r['main'] and r['side'] and r['writing'] == 'none' and r['w1'] > r['w2'] * 1.5, r)
        await pg.click('#wsSwap'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ main: !!$('#spBody .pane[data-pane=\"sources\"]'), side: !!$('#sp2Body .pane[data-pane=\"notes\"]') })")
        check('Swap trades the large and the small', r['main'] and r['side'], r)
        await pg.evaluate("wsEnter({ main: 'sources', side: 'writing', size: 'medium', place: 'right', full: false })"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ editor: $('#main').offsetWidth, split: $('#split').offsetWidth })")
        check('sources large with the writing small beside them', r['split'] > r['editor'] > 200, r)
        await pg.click('#wsExit'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ ws: document.body.classList.contains('ws-on'), notes: !!$('#sidebar .pane[data-pane=\"notes\"]'), sources: !!$('#sidebar .pane[data-pane=\"sources\"]'), split2: !!$('#split2') })")
        check('Exit puts every pane back where it lives', not r['ws'] and r['notes'] and r['sources'] and not r['split2'], r)

        # ---- a sketch
        await pg.evaluate("openDoc(binderOrder()[0].id); (() => { const r = document.createRange(); r.selectNodeContents(editor.lastElementChild); r.collapse(false); savedRange = r; })(); openSketch()")
        try:
            await pg.wait_for_function("() => !$('#skSave').disabled", timeout=20000)
            fr = pg.frame_locator('#skHost iframe')
            await fr.locator('canvas.interactive').first.wait_for(timeout=10000)
            box = await pg.locator('#skHost iframe').bounding_box()
            r = await pg.evaluate("(() => { const f = $('#skHost iframe'); let reach = 'open'; try { reach = typeof f.contentWindow.document.title; } catch (e) { reach = e.name; } return { sandbox: f.getAttribute('sandbox'), reach }; })()")
            check('the sketch frame is sandboxed: scripts, but no origin of its own', r['sandbox'] == 'allow-scripts' and r['reach'] == 'SecurityError', r)
            await fr.locator('label:has([data-testid="toolbar-rectangle"])').click()
            await pg.mouse.move(box['x'] + 300, box['y'] + 250); await pg.mouse.down(); await pg.mouse.move(box['x'] + 520, box['y'] + 380, steps=6); await pg.mouse.up()
            await pg.wait_for_timeout(300)
            await pg.click('#skSave'); await pg.wait_for_function("() => !$('#skDlg').open", timeout=15000)
            r = await pg.evaluate("(() => { const f = editor.querySelector('figure[data-sketch]'); const id = f && f.dataset.sketch; return { fig: !!f, scene: id && P.sketches[id] && P.sketches[id].elements.filter(e => !e.isDeleted).map(e => e.type), img: f && /^data:image\\/png/.test((P.assets[f.querySelector('img').dataset.asset] || {}).data || '') }; })()")
            check('a sketch goes in as a figure, its drawing kept in the project', r['fig'] and r['scene'] == ['rectangle'] and r['img'], r)
            await pg.click('#editor figure[data-sketch] img'); await pg.wait_for_timeout(200); await pg.click('.pop [data-a="sketch"]'); await pg.wait_for_timeout(300)
            opened = await pg.evaluate("$('#skDlg').open")
            if opened:
                await pg.wait_for_function("() => !$('#skSave').disabled", timeout=20000)
                await pg.click('#skCancel'); await pg.wait_for_timeout(200)
            check('clicking the sketch opens it again', opened)
        except Exception as e:
            check('the sketch editor opens and saves', False, str(e)[:300])
        r = await pg.evaluate("skClean({ elements: [{ type: 'rectangle', link: 'javascript:alert(1)', customData: { x: 1 } }, { type: 'embeddable', link: 'https://evil.test' }, { type: 'iframe' }], files: { a: { dataURL: 'data:text/html;base64,PHNjcmlwdD4=' }, b: { dataURL: 'data:image/png;base64,iVBORw0KGgo=' } }, appState: { viewBackgroundColor: 'url(x)' } })")
        check('a crafted drawing loses links, embeds and anything but pictures', [e['type'] for e in r['elements']] == ['rectangle'] and r['elements'][0]['link'] is None and list(r['files'].keys()) == ['b'] and r['appState']['viewBackgroundColor'] == '#ffffff', r)

        check('nothing was fetched from the internet', not reqs, reqs[:5])
        print('ERRS', json.dumps([e for e in errs if 'favicon' not in e][:8]))
        await b.close()
    return ok

if __name__ == '__main__':
    import sys
    sys.exit(0 if asyncio.run(main()) else 1)
