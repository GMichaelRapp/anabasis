"""2.10.2: a hostile project file, fuzzed. Every piece of text in a full sample project (titles, notes, sources and
their citation data, tags, comments, ids, colors) carries markup meant to run a script, in every context it could
land in: element content, attributes, URLs, SVG, styles, templates. The project is opened, every part of the
interface is visited, and every web page Anabasis saves is opened too. Nothing may run, and the app keeps working."""
import asyncio, json, re
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

PWN = 'window.PWN=(window.PWN||[]).concat(1)'
PAYLOADS = [
    f'"><img src=x onerror="{PWN}">',
    f"'><svg onload='{PWN}'><script>{PWN}</script>",
    f'javascript:{PWN}',
    f'</textarea></title></style><script>{PWN}</script>',
    f'<a href="javascript:{PWN}">link</a><iframe srcdoc="<script>parent.{PWN}</script>"></iframe>',
    f'<math><mi xlink:href="javascript:{PWN}">x</mi></math><details open ontoggle="{PWN}">',
    '${' + PWN + '}{{constructor.constructor("' + PWN + '")()}}',
    f'<style>@import "https://evil.example/x.css";</style><link rel=stylesheet href="https://evil.example/y.css">',
]
SKIP = {'app', 'format', 'appVersion', 'saved', 'created', 'modified', 'at', 'date', 'type', 'issued', 'accessed'}


def poison(o, k='', n=[0]):
    if isinstance(o, dict): return {kk: (vv if kk in SKIP else poison(vv, kk)) for kk, vv in o.items()}
    if isinstance(o, list): return [poison(v, k) for v in o]
    if isinstance(o, str):
        n[0] += 1; return o + PAYLOADS[n[0] % len(PAYLOADS)]
    return o


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs, reqs, dialogs = [], [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; try { localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'})) } catch (e) { /* the sandboxed sketch frame has no storage */ }")
        ctx.on('request', lambda r: reqs.append(r.url) if re.match(r'https?://', r.url) and '127.0.0.1' not in r.url and 'localhost' not in r.url else None)
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.dismiss())))
        await pg.goto(URL); await pg.wait_for_timeout(1200)
        base = await pg.evaluate("""(() => { const p = sampleProject(); p.docs[0].comments = [{ id: 'c1', text: 'A comment', author: 'Ann', at: nowISO() }]; p.notes[0].comments = [];
          // 2.12: drafting colors and their key, a code snippet, a section with a task list, a sketch
          p.docs[0].html += '<h2 data-task="ts1">A section</h2><p><span class="ink ink-b">colored</span></p>' + codeHTML('Python', 'print(1)') + '<figure class="fig" data-sketch="sk1" contenteditable="false"><img data-asset="i1" alt=""><figcaption>Sketch</figcaption></figure>';
          p.inkKey = { b: 'rewrite', g: 'keep' }; p.inkKeep = true;
          p.tasks = [{ id: 'tk1', docId: p.docs[0].id, anchor: 'ts1', title: 'A section', items: [{ id: 'ti1', t: 'Check it', done: false, due: '2020-01-01', at: nowISO() }] }, { id: 'tk2', docId: p.docs[0].id, anchor: '', title: '', items: [{ id: 'ti2', t: 'Read aloud', done: false, due: '', at: nowISO() }] }];
          p.sketches = { sk1: { elements: [{ id: 'e1', type: 'text', text: 'Label', x: 0, y: 0, width: 50, height: 20, version: 1, versionNonce: 1, isDeleted: false, link: 'https://x.test', customData: { generationData: { html: '<script>parent.PWN=1</script>' } } }, { id: 'e2', type: 'embeddable', link: 'https://evil.example' }], files: {}, appState: { viewBackgroundColor: '#ffffff' } } };
          p.assets = { i1: { name: 'x', type: 'image/png', data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', w: 1, h: 1 } };
          return JSON.parse(JSON.stringify(p)); })()""")
        proj = poison(base)
        # documents get a payload in their markup as well as their text
        for d in proj['docs']: d['html'] = d['html'] + ''.join(f'<p>{p}</p>' for p in PAYLOADS)
        await pg.evaluate("p => loadProjectText(JSON.stringify(p), null)", proj); await pg.wait_for_timeout(1000)
        check('the poisoned project opens', await pg.evaluate("P.notes.length === 3 && P.sources.length === 2 && P.docs.length >= 1"))

        steps = [f"switchTab('{t}')" for t in ['docs', 'notes', 'sources', 'research', 'outline']]
        steps += ["openBoard()", "closeBoard()", "openHome()", "closeHome()", "openPlan()", "closePlan()", "openDrafts()", "closeDrafts()"]
        steps += [f"openDesk('{v}')" for v in ['threads', 'about', 'claims', 'codes', 'data', 'grid', 'journal', 'lit', 'questions', 'review', 'revision', 'translate']]
        steps += ["closeDesk(); openDoc(P.docs[0].id)", "renderOutline && renderOutline()", "openRel(); closeRel()"]
        # 2.12: every new view, with the poisoned task text, color key and sketch
        steps += ["openTasks({ anchor: (P.tasks.find(l => l.anchor) || {}).anchor || '' })", "$('#taskDlg').close(); openTaskAll()", "$('#taskAllDlg').close(); openHome()", "$('#hmCustomize') && $('#hmCustomize').click()", "closeHome(); openInk()", "closePop(); openThemes()", "$('#thmDlg').close(); openNotecards(); $('[data-ncm=typed]').click(); $('#ncTyped').value = P.notes.map(n => n.title + '\\n' + n.body).join('\\n---\\n'); $('#ncTyped').dispatchEvent(new Event('input'))",
                  "$('#ncDlg').close(); const pre = editor.querySelector('pre.code'); if (pre) openCode(pre)", "$('#codeDlg').close(); wsEnter({ main: 'notes', side: 'sources', size: 'small', place: 'right', full: false })", "wsLeave(true)",
                  "const f = editor.querySelector('figure[data-sketch]'); if (f) openSketch(f)"]
        for js in steps:
            try: await pg.evaluate(f"(() => {{ {js}; }})()"); await pg.wait_for_timeout(300)
            except Exception as e: errs.append('step ' + js + ': ' + str(e)[:120])
        # hover and click about, as a reader would
        for sel in ['#notesList li', '#srcList li', '.cite', '.fn', '.chip']:
            els = await pg.query_selector_all(sel)
            for el in els[:3]:
                try: await el.hover(timeout=800); await pg.wait_for_timeout(80)
                except Exception: pass
        await pg.wait_for_timeout(4000)  # the sketch frame loads its drawing
        check('a poisoned drawing reached the sketch frame cleaned', await pg.evaluate("(() => { const s = Object.values(P.sketches || {})[0]; return !s || s.elements.every(e => !e.customData && !e.link && e.type !== 'embeddable'); })()"))
        await pg.evaluate("$('#skDlg').open && skClose()")
        check('nothing in the project ran in the app', await pg.evaluate("window.PWN || null") is None, await pg.evaluate("window.PWN || null"))
        # …and not just because the page's policy stopped it: no handler or script link made it into the page at all
        bad = await pg.evaluate("""(() => { const out = []; const scan = root => root.querySelectorAll('*').forEach(el => {
            for (const a of el.attributes) if (/^on/i.test(a.name) || (/^(href|src|xlink:href|action|formaction)$/i.test(a.name) && /^\\s*javascript:/i.test(a.value))) out.push(el.tagName + ' ' + a.name);
            if (el.tagName === 'SCRIPT' && !el.closest('head') && el.textContent.includes('window.PWN')) out.push('SCRIPT in ' + (el.parentElement ? el.parentElement.tagName + '#' + el.parentElement.id + '.' + el.parentElement.className : '?') + ': ' + el.outerHTML.slice(0, 80));
            if (el.shadowRoot) scan(el.shadowRoot); }); scan(document); return out.slice(0, 10); })()""")
        check('no event handler, javascript: link or script from the file reached the page', not bad, bad)

        # every web page Anabasis saves, opened as the reader would open it
        pages = await pg.evaluate("""(() => { const d = P.docs[0], out = {};
          const grab = (k, f) => { try { out[k] = f(); } catch (e) { out[k] = 'ERR ' + e.message; } };
          grab('web page', () => pageCSP(exportStandaloneHTML(d)));
          grab('review page', () => pageCSP(reviewPageHTML(d, 'Please read this')));
          return out; })()""")
        for name, html in pages.items():
            check(f'the {name} builds', isinstance(html, str) and not html.startswith('ERR'), str(html)[:200])
            check(f'the {name} carries its own Content Security Policy', 'http-equiv="Content-Security-Policy"' in html and "default-src 'none'" in html)
            p2 = await ctx.new_page(); p2.on('pageerror', lambda e: errs.append('page: ' + str(e)[:200]))
            await p2.set_content(html); await p2.wait_for_timeout(600)
            for el in (await p2.query_selector_all('a, button, details, summary'))[:20]:
                try: await el.hover(timeout=500)
                except Exception: pass
            check(f'nothing runs in the {name}', await p2.evaluate("window.PWN || null") is None)
            await p2.close()
        md = await pg.evaluate("(() => { try { return buildExport(P.docs[0], 'md').body.length > 0; } catch (e) { return 'ERR ' + e.message; } })()")
        check('Markdown export still builds', md is True, md)
        dx = await pg.evaluate("exportDocx(P.docs[0], { returnBlob: true }).then(b => b && b.size > 1000).catch(e => 'ERR ' + e.message)")
        check('Word export still builds', dx is True, dx)
        check('nothing was fetched from the internet', not reqs, reqs[:5])
        check('no dialog opened by itself', not dialogs, dialogs)
        check('and still nothing ran', await pg.evaluate("window.PWN || null") is None)
        # the app still works: type, save, reopen
        r = await pg.evaluate("(() => { editor.focus(); document.execCommand('insertText', false, ' Still fine.'); syncEditor(); const t = projectJSON(); return JSON.parse(t).docs[0].html.includes('Still fine.'); })()")
        check('the app keeps working', r)
        await b.close()
    print('ERRS', json.dumps(errs))
    _sys.exit(0 if ok and not errs else 1)

asyncio.run(main())
