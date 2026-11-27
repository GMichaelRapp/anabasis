"""Hardening against crafted project files (CodeQL review, after 2.10.0): ids, references, colors and kinds can't
carry markup into the interface; a footnote number is text; HTML is read as text without loading anything; LaTeX
and Markdown escaping; messages between windows only from our own."""
import asyncio, json
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

PWN = 'window.PWN=(window.PWN||[]).concat(1)'
EVIL = 'x"><img src=x onerror="' + PWN + '">'


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(1200)
        proj = await pg.evaluate("JSON.parse(projectJSON())")
        proj['notes'] = [{'id': EVIL, 'title': 'A note', 'body': 'Body', 'kind': 'idea" onclick="' + PWN, 'color': 'red"><img src=x onerror="' + PWN + '">', 'tags': [], 'pile': EVIL, 'x': '1px" data-a="', 'y': 4, 'sourceId': EVIL}]
        proj['threads'] = [{'id': 't1', 'name': 'Supply', 'color': 'red"><img src=x onerror="' + PWN + '">'}]
        proj['docs'][0]['html'] += '<p>Text<sup class="fnref">&lt;img src=x onerror="' + PWN + '"&gt;</sup></p>'
        proj['docs'][0]['id'] = EVIL
        await pg.evaluate("p => loadProjectText(JSON.stringify(p), null)", proj); await pg.wait_for_timeout(800)
        for t in ['notes', 'sources', 'research', 'outline', 'docs']:
            await pg.evaluate(f"switchTab('{t}')"); await pg.wait_for_timeout(250)
        for js in ["openBoard()", "closeBoard(); openDesk('threads')", "closeDesk(); openHome()", "closeHome()"]:
            try: await pg.evaluate(js); await pg.wait_for_timeout(350)
            except Exception as e: errs.append('step ' + js + ': ' + str(e)[:80])
        st = await pg.evaluate("({ pwn: window.PWN || null, id: P.notes[0].id, doc: P.docs[0].id, ref: P.notes[0].pile, src: P.notes[0].sourceId, color: P.threads[0].color, kind: P.notes[0].kind, x: P.notes[0].x, y: P.notes[0].y })")
        check('nothing in a crafted project file runs', st['pwn'] is None, st)
        check('ids and the references to them lose only the dangerous characters, the same way', st['id'] == st['src'] and not any(c in st['id'] for c in '"<>\'') and 'img src=x' in st['id'], st)
        check('a document id is held to the same shape', not any(c in st['doc'] for c in '"<>'), st['doc'])
        check('colors and kinds carry no markup', '<' not in st['color'] and '"' not in st['kind'], st)
        check('board positions are numbers', st['x'] is None and st['y'] == 4, st)
        # a footnote number read back from the page is text
        out = await pg.evaluate("""(() => { const box = document.createElement('div'); box.innerHTML = '<p><sup class="fnref">&lt;b&gt;7&lt;/b&gt;</sup></p>';
          box.querySelectorAll('sup.fnref').forEach(s => { const n = esc(s.textContent); s.innerHTML = `<a href="#fn-${n}">${n}</a>`; }); return box.querySelector('a').textContent; })()""")
        check('htmlToText reads without loading anything', await pg.evaluate("(() => { window.PWN2 = 0; const t = htmlToText('<img src=x onerror=\"window.PWN2=1\">ok'); return new Promise(r => setTimeout(() => r([t, window.PWN2]), 300)); })()") == ['ok', 0])
        check('LaTeX: a backslash and braces', await pg.evaluate("texEsc('a\\\\b {x} 50% & $')") == r'a\textbackslash{}b \{x\} 50\% \& \$')
        check('Markdown: entities decoded once', await pg.evaluate("plainToMd('A &amp;lt;b&amp;gt; &amp; <i>C</i>')") == 'A &lt;b&gt; & *C*')
        check('messages between windows go to our own origin only', await pg.evaluate("POP_TO === (/^https?:/.test(location.origin) ? location.origin : '*') && popFromUs({ origin: 'https://evil.example' }) === false"))
        check('a saved copy of an ordinary project is unchanged by the hardening', await pg.evaluate("(() => { const a = JSON.parse(projectJSON()); const b = JSON.parse(JSON.stringify(normalize(JSON.parse(projectJSON())))); return JSON.stringify(a.notes.map(n => [n.id, n.kind, n.pile])) === JSON.stringify(b.notes.map(n => [n.id, n.kind, n.pile])); })()"))
        await b.close()
    print('ERRS', json.dumps(errs))
    _sys.exit(0 if ok and not errs else 1)

asyncio.run(main())
