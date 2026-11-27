"""2.7.2: the slush pile, for passages you cut and documents you delete."""
import asyncio
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950})
        await ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'Executing inline event handler' not in m.text else None)  # the policy refusing a hostile handler as it's parsed is expected
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")
        await pg.evaluate("openDoc(P.docs.find(d => /Army/.test(d.title)).id)"); await pg.wait_for_timeout(500)

        check('the Docs tab has a Slush pile button', await pg.evaluate("(() => { switchTab('docs'); const b = $('#btnSlush').getBoundingClientRect(); return b.width > 0 && b.height >= 24 && $('#slushN').textContent === ''; })()"))

        # ---- cut a passage
        sel = """(words) => { const p = [...editor.querySelectorAll('p')].find(e => e.textContent.includes(words)); const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let t; while ((t = w.nextNode())) if (t.data.includes(words)) break;
            const a = t.data.indexOf(words), r = document.createRange(); r.setStart(t, a); r.setEnd(t, a + words.length); editor.focus(); getSelection().removeAllRanges(); getSelection().addRange(r); }"""
        cut = 'usually turn on courage and command'
        await pg.evaluate(sel, cut)
        await pg.keyboard.press('Control+Alt+KeyJ'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ inDoc: editor.textContent.includes('" + cut + "'), pile: P.slush.map(x => [x.kind, slushText(x.html), x.fromTitle]), toast: $('#toast').innerText, n: $('#slushN').textContent, saved: curDoc().html.includes('" + cut + "') })")
        check('⌘/Ctrl Alt J moves the selection out of the writing and into the pile', not r['inDoc'] and not r['saved'] and r['pile'] == [['cut', cut, 'Chapter 2: An Army That Had to Eat']] and r['n'] == '1', r)
        check('…saying how many words, with Undo', '6 words moved to the slush pile' in r['toast'] and 'Undo' in r['toast'], r['toast'])
        await pg.click('#toast button'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ inDoc: editor.textContent.includes('" + cut + "'), n: P.slush.length })")
        check('…Undo puts the words back and empties the pile', r == {'inDoc': True, 'n': 0}, r)
        await pg.evaluate(sel, cut)
        await pg.evaluate("$('#btnMark').click()"); await pg.wait_for_timeout(200)
        await pg.click('#markMenu [data-m=slush]'); await pg.wait_for_timeout(300)
        check('Mark → Move to the slush pile does the same', await pg.evaluate("P.slush.length === 1 && !editor.textContent.includes('" + cut + "')"))

        # ---- copy, keeping the words, without the margin-note highlight
        cp = 'one that shaped the army’s route'
        await pg.evaluate(sel, cp)
        await pg.evaluate("() => { const r = getSelection().getRangeAt(0); const s = document.createElement('span'); s.className = 'cmt'; s.dataset.cmt = 'cX'; s.append(r.extractContents()); r.insertNode(s); const r2 = document.createRange(); r2.selectNodeContents(s); getSelection().removeAllRanges(); getSelection().addRange(r2); }")
        await pg.evaluate("COMMANDS.find(c => c[0] === 'Copy the selection to the slush pile')[1]()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ inDoc: editor.textContent.includes('" + cp + "'), x: P.slush[0] })")
        check('Copy the selection to the slush pile keeps the words in the writing', r['inDoc'] and r['x']['kind'] == 'copy' and 'cmt' not in r['x']['html'] and cp in r['x']['html'], r)

        # ---- a whole paragraph keeps its paragraph; nothing selected opens the pile
        await pg.evaluate("() => { const p = [...editor.querySelectorAll('p')].find(e => e.textContent.startsWith('Of the stops')); const r = document.createRange(); r.selectNode(p); editor.focus(); getSelection().removeAllRanges(); getSelection().addRange(r); }")
        await pg.keyboard.press('Control+Alt+KeyJ'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ h: P.slush[0].html.slice(0, 3), gone: !editor.textContent.includes('Of the stops Xenophon describes') })")
        check('a whole paragraph goes as a paragraph, citations and all', r == {'h': '<p>', 'gone': True} and await pg.evaluate("P.slush[0].html.includes('class=\"cite')"), r)
        await pg.evaluate("() => { const r = document.createRange(); r.setStart(editor.querySelector('p'), 0); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }")
        await pg.keyboard.press('Control+Alt+KeyJ'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ open: $('#slDlg').open, n: $$('#slList li[data-sl]').length, sum: $('#slSum').textContent, from: [...$('#slFrom').options].map(o => o.text) })")
        check('with nothing selected, ⌘/Ctrl Alt J opens the slush pile', r['open'] and r['n'] == 3 and r['sum'].startswith('3 pieces') and 'never exported' in r['sum'], r)

        # ---- search, notes on pieces, filter
        await pg.fill('#slQ', 'COURAGE'); await pg.wait_for_timeout(300)
        check('…search finds a piece by its words, ignoring case', await pg.evaluate("$$('#slList li[data-sl]').length") == 1)
        await pg.fill('#slList .sl-note', 'Might work in the conclusion'); await pg.press('#slList .sl-note', 'Tab'); await pg.wait_for_timeout(150)
        await pg.fill('#slQ', 'conclusion'); await pg.wait_for_timeout(300)
        check('…and by the note you add to it', await pg.evaluate("$$('#slList li[data-sl]').length === 1 && P.slush.some(x => x.note === 'Might work in the conclusion')"))
        await pg.fill('#slQ', ''); await pg.wait_for_timeout(200)

        # ---- insert at the cursor: inline, and out of the pile
        await pg.evaluate("$('#slDlg').close(); (() => { const p = [...editor.querySelectorAll('p')].find(e => e.textContent.startsWith('Histories')); const t = p.firstChild; const r = document.createRange(); r.setStart(t, t.data.indexOf('Ten Thousand') + 12); r.collapse(true); editor.focus(); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); })()")
        await pg.evaluate("openSlush()"); await pg.wait_for_timeout(200)
        await pg.evaluate("$$('#slList li[data-sl]').find(li => li.textContent.includes('courage')).querySelector('[data-sla=ins]').click()"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ p: [...editor.querySelectorAll('p')].find(e => e.textContent.startsWith('Histories')).textContent.slice(0, 90), n: P.slush.length, pc: [...editor.querySelectorAll('p')].length })")
        check('Insert at the cursor puts a piece back inside the sentence and takes it out of the pile', 'Ten Thousand' + cut in r['p'] and r['n'] == 2, r)

        # ---- delete a document: its text waits in the pile
        await pg.evaluate("() => { const d = newDoc('Deutsche Fassung', '<h1>Deutsche Fassung</h1><p>Die Armee musste essen.</p>'); d.lang = 'de'; addDoc(d); renderDocList(); }"); await pg.wait_for_timeout(300)
        did = await pg.evaluate("P.docs.find(d => d.title === 'Deutsche Fassung').id")
        await pg.evaluate(f"$('#docList li[data-id=\"{did}\"] [data-a=del]').click()"); await pg.wait_for_timeout(300)
        msg = await pg.evaluate("$('#askMsg').textContent")
        check('deleting a document says its text will wait in the slush pile', 'kept in the slush pile' in msg, msg)
        await pg.click('#askOk'); await pg.wait_for_timeout(400)
        r = await pg.evaluate(f"({{ gone: !P.docs.some(d => d.id === '{did}'), x: P.slush[0] }})")
        check('…and it does', r['gone'] and r['x']['kind'] == 'doc' and r['x']['title'] == 'Deutsche Fassung' and r['x']['doc']['lang'] == 'de', r)
        await pg.evaluate("() => { const d = newDoc('Empty one', '<p><br></p>'); addDoc(d); renderDocList(); }"); await pg.wait_for_timeout(200)
        eid = await pg.evaluate("P.docs.find(d => d.title === 'Empty one').id")
        await pg.evaluate(f"$('#docList li[data-id=\"{eid}\"] [data-a=del]').click()"); await pg.wait_for_timeout(300)
        msg = await pg.evaluate("$('#askMsg').textContent"); await pg.click('#askOk'); await pg.wait_for_timeout(300)
        check('…an empty document isn’t kept', 'slush' not in msg and await pg.evaluate("P.slush.length") == 3, msg)
        await pg.evaluate("openSlush()"); await pg.wait_for_timeout(200)
        await pg.select_option('#slFrom', '@doc'); await pg.wait_for_timeout(200)
        check('…the pile can show only deleted documents', await pg.evaluate("$$('#slList li[data-sl]').length === 1 && $('#slList li[data-sl] .sl-h').textContent.includes('Deleted document')"))
        await pg.evaluate("$('#slList [data-sla=doc]').click()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ t: curDoc().title, lang: curDoc().lang, h: editor.textContent, n: P.slush.length })")
        check('New document brings it back as it was, language and all', r['t'] == 'Deutsche Fassung' and r['lang'] == 'de' and 'Die Armee musste essen.' in r['h'] and r['n'] == 2, r)

        # ---- make a note, keep a copy, delete with undo
        await pg.evaluate("openSlush()"); await pg.wait_for_timeout(200)
        await pg.check('#slKeep')
        await pg.evaluate("$$('#slList li[data-sl]').find(li => li.textContent.includes('Of the stops')).querySelector('[data-sla=note]').click()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ n: P.notes[0], left: P.slush.length })")
        check('Make a note turns a piece into an idea note; Keep a copy leaves it in the pile', r['n']['kind'] == 'idea' and r['n']['body'].startswith('Of the stops Xenophon describes') and r['left'] == 2, r['n']['body'][:80])
        await pg.evaluate("$('#slList [data-sla=del]').click()"); await pg.wait_for_timeout(200)
        check('Delete removes a piece…', await pg.evaluate("P.slush.length") == 1)
        await pg.click('#toast button'); await pg.wait_for_timeout(200)
        check('…with Undo', await pg.evaluate("P.slush.length === 2 && $$('#slList li[data-sl]').length === 2"))
        await pg.evaluate("$('#slDlg').close()")

        # ---- the project file, and nothing exported
        r = await pg.evaluate("""() => { const raw = JSON.parse(JSON.stringify(P)); raw.slush.push({ html: '<p>Bad<script>alert(1)</script><img src="https://x.invalid/a.png" onerror="alert(2)"></p>', kind: 'weird', doc: { lang: 'not a language!' } }, 'junk', null);
            const o = normalize(raw).slush; return { n: o.length, last: o[o.length - 1] }; }""")
        check('kept in the project file; bad values cleaned and the HTML scrubbed', r['n'] == 3 and r['last']['kind'] == 'cut' and '<script' not in r['last']['html'] and 'onerror' not in r['last']['html'] and 'x.invalid' not in r['last']['html'] and r['last']['doc']['lang'] == '', r)
        r = await pg.evaluate("() => { const d = P.docs.find(d => /Army/.test(d.title)); openDoc(d.id); const x = buildExport(d, 'html'); return x.body.includes('Of the stops Xenophon describes'); }")
        check('the pile isn’t exported with the document', not r)
        r = await pg.evaluate("COMMANDS.map(c => c[0]).filter(c => /slush/i.test(c)).length")
        check('the command search reaches the slush pile', r == 3, r)
        check('the shortcut sheet lists ⌘/Ctrl Alt J', await pg.evaluate("KEYS.some(g => g[1].some(k => k[0] === '⌘/Ctrl Alt J'))"))
        check('no errors', not errs, errs[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
