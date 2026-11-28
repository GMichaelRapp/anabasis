#!/usr/bin/env python3
"""Cross-browser smoke test: the everyday path in Chromium, Firefox or WebKit (Safari's engine).

    python tests/smoke.py --browser firefox
    python tests/smoke.py --browser webkit --http     serve over HTTP, as GitHub Pages does

Opens the app, writes, cites, checks, makes a chart and a map, switches theme, adds a task, draws a sketch
in the sandboxed Excalidraw frame, saves the project, reopens it and exports HTML and Word. Fails on any page error.
"""
import argparse, asyncio, functools, http.server, json, pathlib, sys, threading
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests' / 'out'


async def run(browser, url):
    errs, ok = [], True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra); ok = ok and bool(cond)
    async with async_playwright() as pw:
        b = await getattr(pw, browser).launch()
        ctx = await b.new_context(viewport={'width': 1280, 'height': 860}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; try{localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))}catch(e){}")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(url); await pg.wait_for_timeout(2000)
        check('app starts with the sample project', await pg.evaluate("P.docs.length > 0"))
        try: await pg.wait_for_function("() => document.querySelectorAll('#refs p').length > 0", timeout=20000)  # the citation engine waits for the first paint; slower on a busy runner
        except Exception: pass
        check('citations render', await pg.locator('#refs p').count() > 0)
        await pg.click('#editor h1'); await pg.keyboard.press('End'); await pg.keyboard.type(' (edited)')
        await pg.wait_for_timeout(400)
        check('typing works', '(edited)' in await pg.inner_text('#editor h1'))
        await pg.evaluate("switchTab('outline')"); await pg.wait_for_timeout(1500)
        check('checks run', await pg.evaluate("document.querySelectorAll('#acroList li').length > 0"))
        await pg.evaluate("openChart()"); await pg.fill('#chData', 'Year\tA\tB\n2020\t1\t2\n2021\t3\t4'); await pg.wait_for_timeout(1200)
        check('chart preview draws', await pg.evaluate("(()=>{const c=$('#chDlg canvas'); if(!c) return false; const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=400) if(d[i]) n++; return n>20})()"))
        await pg.evaluate("$('#chDlg').close(); openMap()"); await pg.wait_for_timeout(2000)
        check('map draws', await pg.evaluate("$$('#mpStage svg path').length > 50"))
        await pg.evaluate("$('#mpDlg').close()")
        # 2.12: a theme, a task, and a sketch drawn in the sandboxed frame
        await pg.evaluate("setPalette('parchment')"); await pg.wait_for_timeout(200)
        check('a theme applies', await pg.evaluate("document.documentElement.dataset.palette === 'parchment' && getComputedStyle(document.documentElement).getPropertyValue('--page').trim().toUpperCase() === '#FBF7EE'"))
        await pg.evaluate("openTasks({}); $('#tkAdd').value = 'Check the dates'; taskAdd(); $('#taskDlg').close()")
        check('a task list attaches to the document', await pg.evaluate("P.tasks.some(l => l.docId === curDocId && l.items.some(i => i.t === 'Check the dates'))"))
        await pg.evaluate("(() => { const r = document.createRange(); r.selectNodeContents(editor.lastElementChild); r.collapse(false); savedRange = r; openSketch(); })()")
        try:
            await pg.wait_for_function("() => !$('#skSave').disabled", timeout=60000)
            fr = pg.frame_locator('#skHost iframe'); await fr.locator('label:has([data-testid="toolbar-rectangle"])').click()
            box = await pg.locator('#skHost iframe').bounding_box()
            await pg.mouse.move(box['x'] + 300, box['y'] + 250); await pg.mouse.down(); await pg.mouse.move(box['x'] + 500, box['y'] + 360, steps=6); await pg.mouse.up()
            await pg.wait_for_timeout(300); await pg.click('#skSave'); await pg.wait_for_function("() => !$('#skDlg').open", timeout=30000)
            check('a sketch is drawn in Excalidraw and saved as a figure', await pg.evaluate("!!editor.querySelector('figure[data-sketch] img') && Object.values(P.sketches).some(s => s.elements.length === 1)"))
        except Exception as e:
            check('a sketch is drawn in Excalidraw and saved as a figure', False, str(e)[:200] + ' ' + await pg.inner_text('#skStatus'))
        await pg.evaluate("setPalette('map')")
        async with pg.expect_download() as d: await pg.click('#btnSave')
        dl = await d.value; path = OUT / f'smoke-{browser}.json'; await dl.save_as(path)
        saved = json.loads(path.read_text())
        check('project saves as a file', saved.get('format') == 2 and '(edited)' in json.dumps(saved))
        await pg.set_input_files('#fileOpen', str(path)); await pg.wait_for_timeout(1500)
        check('project reopens', '(edited)' in await pg.inner_text('#editor h1'))
        for x in ('html', 'docx'):
            await pg.click('#btnExport')
            async with pg.expect_download(timeout=60000) as d: await pg.click(f'#exportMenu [data-x={x}]')
            check(f'{x} export downloads', (await d.value).suggested_filename.endswith('.' + x))
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(500)
        await b.close()
    errs = [e for e in errs if 'favicon' not in e]
    print('ERRS', errs)
    return ok and not errs


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--browser', default='chromium', choices=['chromium', 'firefox', 'webkit']); ap.add_argument('--http', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'dist' / 'anabasis.html'
    if not dist.exists(): sys.exit('Build first: python build.py')
    url = dist.as_uri()
    if a.http:
        h = functools.partial(Quiet, directory=str(dist.parent))
        s = http.server.ThreadingHTTPServer(('127.0.0.1', 8766), h); threading.Thread(target=s.serve_forever, daemon=True).start()
        url = 'http://localhost:8766/anabasis.html'
    sys.exit(0 if asyncio.run(run(a.browser, url)) else 1)


if __name__ == '__main__':
    main()
