"""Release hardening: hostile project files, damaged files, format versions, locked round-trip."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL = os.environ.get('ANABASIS_URL', URL)
HERE = OUT

def payload(tag):
    return (f'<img src=x onerror="window.__pwned=(window.__pwned||[]).concat(\'{tag}\')">'
            f'<svg onload="window.__pwned=(window.__pwned||[]).concat(\'{tag}-svg\')"></svg>'
            f'<script>window.__pwned=(window.__pwned||[]).concat(\'{tag}-script\')</script>')

def stuff(o, path='p'):
    if isinstance(o, dict):
        return {k: stuff(v, path + '.' + k) for k, v in o.items()}
    if isinstance(o, list):
        return [stuff(v, f'{path}[{i}]') for i, v in enumerate(o)]
    if isinstance(o, str) and not path.endswith(('.id', 'Id', '.type', '.kind', '.style', '.date', '.created', '.modified', '.format', '.app')):
        return o + payload(path)
    return o

def hostile():
    doc_html = ('<h1>Title</h1><p>Text <a href="javascript:window.__pwned=[\'href\']">link</a> '
                '<a href="https://example.org" onclick="window.__pwned=[\'onclick\']">ok</a></p>'
                '<iframe srcdoc="<script>parent.__pwned=[\'iframe\']</script>"></iframe>'
                '<form action="javascript:alert(1)"><button>go</button></form>'
                '<p style="color:red" onmouseover="x()">styled</p>')
    p = {
        'app': 'Anabasis', 'format': 1, 'id': 'p_evil', 'title': 'Project',
        'docs': [{'id': 'd1', 'title': 'Doc', 'html': doc_html, 'meta': {'author': 'A', 'subtitle': 'S'},
                  'snapshots': [{'id': 's1', 'name': 'Draft', 'html': doc_html, 'date': '2026-01-01T00:00:00Z', 'kind': 'draft', 'note': 'n'}],
                  'comments': [{'id': 'c1', 'text': 'comment', 'quote': 'q'}]}],
        'notes': [{'id': 'n1', 'title': 'Note', 'body': 'Body **bold**', 'tags': ['tag'], 'quote': 'quoted', 'page': '4', 'url': 'https://example.org', 'event': '2024-02-01'}],
        'sources': [{'id': 's1', 'csl': {'type': 'book', 'title': 'Book', 'author': [{'family': 'Fam', 'given': 'Giv'}], 'publisher': 'Pub', 'URL': 'https://example.org', 'container-title': 'Cont'},
                     'osint': {'descType': 'Report', 'location': 'Loc', 'rating': 'B2'}, 'transcript': '[0:01] Speaker: words'}],
        'entities': [{'id': 'e1', 'name': 'Kyiv', 'kind': 'place', 'variants': ['Kiev'], 'note': 'n'}],
        'parts': [{'id': 'pt1', 'name': 'Part'}], 'piles': [{'id': 'pl1', 'name': 'Pile'}],
        'plan': {'items': [{'id': 'i1', 'text': 'Plan item', 'kind': 'point'}], 'hoist': ''},
        'indexTerms': [{'id': 'x1', 'term': 'Term', 'match': ['Term']}],
        'acronyms': {'NATO': 'North Atlantic Treaty Organization'},
        'checkpoints': [{'id': 'cp1', 'name': 'Checkpoint', 'note': 'n', 'date': '2026-01-01T00:00:00Z', 'words': 1, 'docs': 1, 'notes': 1, 'sources': 1}],
        'house': {'prefer': 'Kyiv = Kiev'},
    }
    p = stuff(p)
    p['docs'][0]['html'] = doc_html + payload('docbody')
    return p

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        # the hostile files carry onerror/onclick handlers: Chrome reports the page's policy refusing them as soon as the
        # markup is parsed (even into an inert document, before it is cleaned). That report is the policy working, not a fault.
        pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' and 'Executing inline event handler' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1200)
        ok = True
        def check(name, cond, extra=''):
            nonlocal ok
            print(('PASS ' if cond else 'FAIL ') + name, extra); ok = ok and bool(cond)

        # ---------- hostile file
        path = os.path.join(HERE, 'hostile.json'); json.dump(hostile(), open(path, 'w'))
        await pg.set_input_files('#fileOpen', path); await pg.wait_for_timeout(1200)
        views = ["openHome()", "closeHome && closeHome()", "switchTab('docs')", "switchTab('notes')", "openBoard()", "closeBoard && closeBoard()",
                 "switchTab('sources')", "switchTab('outline')", "openPlan()", "closePlan && closePlan()", "openDrafts()", "closeDrafts && closeDrafts()",
                 "openRel()", "closeRel()", "openCheckpoints()", "$('#cpDlg').close()", "openFindAll()", "$('#frDlg').close()",
                 "openPromo()", "$('#pkDlg').close()", "openHouse()", "$('#hsDlg').close()", "openTranscript(P.sources[0].id)", "$('#trDlg').close()",
                 "openTimelineFig && openTimelineFig()", "document.querySelectorAll('dialog[open]').forEach(d=>d.close())"]
        for v in views:
            try: await pg.evaluate(f"(async()=>{{ try {{ {v} }} catch(e) {{ console.warn('view', e.message) }} }})()"); await pg.wait_for_timeout(250)
            except Exception as e: print('  view failed', v, str(e)[:120])
        await pg.evaluate("(async()=>{ const s=P.sources[0]; try{openSource&&openSource(s.id)}catch(e){} })()"); await pg.wait_for_timeout(300)
        await pg.mouse.move(700, 400); await pg.wait_for_timeout(200)
        pwned = await pg.evaluate("window.__pwned || []")
        check('no script from a hostile project ran', not pwned, pwned[:8])
        ed = await pg.evaluate("editor.innerHTML")
        check('javascript: links removed', 'javascript:' not in ed)
        check('event handlers removed', 'onclick' not in ed and 'onmouseover' not in ed and 'onerror' not in ed)
        check('iframes and forms removed', '<iframe' not in ed and '<form' not in ed and '<script' not in ed)
        check('ordinary formatting kept', 'color:red' in ed.replace(' ', '') and 'https://example.org' in ed)
        check('old format migrated', await pg.evaluate("P.format") == 2)
        saved = json.loads(await pg.evaluate("projectJSON()"))
        check('saves as format 2 with app version', saved['format'] == 2 and saved.get('appVersion') == await pg.evaluate("APP_VERSION"))

        # ---------- trailing comma / BOM: repaired
        good = json.loads(await pg.evaluate("projectJSON()")); good['title'] = 'Repaired project'
        t = '﻿' + json.dumps(good, indent=1)[:-1] + ',\n}\n\x00garbage'
        path = os.path.join(HERE, 'damaged-mild.json'); open(path, 'w', encoding='utf-8').write(t)
        await pg.set_input_files('#fileOpen', path); await pg.wait_for_timeout(2400)
        check('mildly damaged file repaired', await pg.evaluate("P.title") == 'Repaired project',
              await pg.evaluate("[...document.querySelectorAll('.toast')].map(t=>t.textContent).join(' / ')"))

        # ---------- truncated: offer browser copy
        await pg.evaluate("persistLocal()"); await pg.wait_for_timeout(400)
        path = os.path.join(HERE, 'damaged-cut.json'); open(path, 'w').write(json.dumps(good)[:5000])
        await pg.set_input_files('#fileOpen', path); await pg.wait_for_timeout(600)
        msg = await pg.text_content('#askMsg')
        check('cut-off file explained', 'can’t be read' in msg and 'cut off' in msg, msg[:160])
        await pg.click('#askOk'); await pg.wait_for_timeout(800)
        check('browser copy opened instead', await pg.evaluate("P.title") == 'Repaired project')

        # ---------- newer format
        newer = dict(good); newer['format'] = 99; newer['appVersion'] = '9.0.0'; newer['title'] = 'From the future'
        path = os.path.join(HERE, 'future.json'); json.dump(newer, open(path, 'w'))
        await pg.set_input_files('#fileOpen', path); await pg.wait_for_timeout(600)
        msg = await pg.text_content('#askMsg')
        check('newer format warns', '9.0.0' in msg, msg[:120])
        await pg.click('#askOk'); await pg.wait_for_timeout(800)
        check('newer file opens as a copy', await pg.evaluate("P.title") == 'From the future' and await pg.evaluate("fileHandle === null"))

        # ---------- locked save round-trip check
        await pg.evaluate("""(async()=>{ const salt=crypto.getRandomValues(new Uint8Array(16)); LOCK={ key: await deriveKey('correct horse', salt, 1000), salt, iter:1000 }; })()""")
        await pg.wait_for_timeout(300)
        sealed = await pg.evaluate("projectFileText()")
        env = json.loads(sealed)
        check('locked file is sealed and verified', env.get('encrypted') == 1 and 'From the future' not in sealed)
        bad = await pg.evaluate("""(async()=>{ const real=LOCK.key; LOCK.key = await deriveKey('other', LOCK.salt, 1000); const k2=LOCK.key; const orig=crypto.subtle.decrypt.bind(crypto.subtle);
            crypto.subtle.decrypt = (a,k,d)=> orig(a, real, d); try { await projectFileText(); return 'no error'; } catch(e) { return e.message } finally { crypto.subtle.decrypt=orig; LOCK.key=real; } })()""")
        check('a seal that does not read back refuses to save', 'nothing was written' in bad, bad[:80])
        await pg.evaluate("LOCK=null")

        # ---------- first visit: tour, then never again
        c2 = await b.new_context(viewport={'width': 1280, 'height': 800}); p2 = await c2.new_page()
        p2.on('pageerror', lambda e: errs.append(str(e)))
        await p2.goto(URL); await p2.wait_for_timeout(2500)
        check('tour starts on a first visit', await p2.evaluate("!$('#tour').classList.contains('hidden')"))
        for _ in range(10):
            if await p2.evaluate("$('#tour').classList.contains('hidden')"): break
            await p2.keyboard.press('ArrowRight'); await p2.wait_for_timeout(150)
        check('tour finishes', await p2.evaluate("$('#tour').classList.contains('hidden') && PREFS.toured === true"))
        check('sample shows privacy statement', 'Your work stays on this computer' in await p2.inner_text('#editor'))
        await p2.reload(); await p2.wait_for_timeout(1200)
        check('no tour on the next visit', await p2.evaluate("$('#tour').classList.contains('hidden')"))
        await c2.close()

        errs = [e for e in errs if 'favicon' not in e]
        print('ERRS', errs)
        await b.close()
        sys.exit(0 if ok and not errs else 1)
asyncio.run(main())
