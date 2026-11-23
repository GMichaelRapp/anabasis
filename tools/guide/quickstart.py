#!/usr/bin/env python3
"""Regenerate the screenshots in docs/quick-start.md by driving the real app.

    python build.py && python tools/guide/quickstart.py      (Pillow, if installed, shrinks the images)

Walks through the quick start (new project, write, add a source, cite, switch styles,
take a note, run the checks, save, export) and saves one screenshot per step to
docs/quick-start/. The step being described is outlined in red. Rerun it after any
interface change so the guide never goes stale.
"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = (ROOT / 'dist' / 'anabasis.html').as_uri()
OUT = ROOT / 'docs' / 'quick-start'
W, H = 1280, 800
MARK = "outline:3px solid #A3271B!important;outline-offset:3px!important;border-radius:6px"


async def main():
    if not (ROOT / 'dist' / 'anabasis.html').exists(): sys.exit('Build first: python build.py')
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': W, 'height': H}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))

        async def mark(*sels):
            await pg.evaluate("""s => { document.querySelectorAll('[data-qs-mark]').forEach(e => { e.style.cssText = e.dataset.qsMark === '-' ? '' : e.dataset.qsMark; e.removeAttribute('data-qs-mark'); });
              s.forEach(([sel, css]) => { const e = document.querySelector(sel); if (e) { e.dataset.qsMark = e.getAttribute('style') || '-'; e.style.cssText += ';' + css; } }); }""",
                              [[s, MARK] for s in sels])

        async def shot(name, clip=None, *sels):
            await mark(*sels); await pg.wait_for_timeout(250)
            await pg.screenshot(path=str(OUT / f'{name}.png'), clip=clip)
            await mark()

        # 1. First visit: the tour
        await pg.goto(APP); await pg.wait_for_timeout(2500)
        await shot('01-welcome')
        await pg.click('#tourSkip'); await pg.wait_for_timeout(300)

        # 2. New project
        await pg.click('#btnNewProj'); await pg.wait_for_timeout(500)
        if await pg.locator('#askOk').is_visible():  # "start a new project? your current one is saved in this browser"
            await pg.click('#askOk'); await pg.wait_for_timeout(500)
        await pg.fill('#npTitle', 'The March of the Ten Thousand')
        kind = pg.locator('#npKinds button, #npKinds label').filter(has_text='Article')
        if await kind.count(): await kind.first.click()
        await pg.wait_for_timeout(300)
        box = await pg.locator('#npDlg').bounding_box()
        await shot('02-new-project', {'x': box['x'] - 8, 'y': box['y'] - 8, 'width': box['width'] + 16, 'height': box['height'] + 16}, '#npTitle', '#npKinds')
        await pg.click('#npOk'); await pg.wait_for_timeout(1200)
        if await pg.evaluate("homeOn"): await pg.evaluate("closeHome()")
        if await pg.evaluate("planOn"): await pg.evaluate("closePlan()")
        await pg.wait_for_timeout(400)

        # 3. Write
        await pg.evaluate("""() => { editor.innerHTML = '<h1>The March of the Ten Thousand</h1><h2>The sea</h2><p><br></p>'; const p = editor.querySelector('p');
            const r = document.createRange(); r.setStart(p, 0); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); onEdit(); }""")
        await pg.keyboard.type('After months in the mountains of Armenia, the Greek mercenaries reached the summit of Mount Theches in 400 BCE and saw the Black Sea for the first time. The cry that went down the column has stood ever since for the end of a long march.', delay=0)
        await pg.wait_for_timeout(500)
        await shot('03-write', None, '#editor')

        # 4. Add a source
        await pg.evaluate("switchTab('sources')"); await pg.wait_for_timeout(300)
        await pg.click('#btnNewSource'); await pg.wait_for_timeout(500)
        await pg.fill('#panelBody [data-f="title"]', 'Anabasis'); await pg.locator('#panelBody [data-f="title"]').dispatch_event('input')
        await pg.fill('#people .prow [data-p="family"]', 'Xenophon'); await pg.locator('#people .prow [data-p="family"]').dispatch_event('input')
        await pg.click('#addPerson'); await pg.wait_for_timeout(200)
        await pg.select_option('#people .prow:nth-child(2) [data-p="role"]', 'translator')
        await pg.fill('#people .prow:nth-child(2) [data-p="family"]', 'Dakyns'); await pg.fill('#people .prow:nth-child(2) [data-p="given"]', 'H. G.')
        await pg.locator('#people .prow:nth-child(2) [data-p="given"]').dispatch_event('input')
        for k, v in (('publisher', 'Macmillan'), ('publisher-place', 'London'), ('issued', '1897')):
            f = pg.locator(f'#panelBody [data-f="{k}"]')
            if await f.count(): await f.fill(v); await f.dispatch_event('input'); await f.dispatch_event('change')
        await pg.wait_for_timeout(700)
        await shot('04-add-source', None, '#quickId', '#panel')

        # 5. Cite
        await pg.evaluate("""() => { const p = editor.querySelector('p'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false);
            const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); saveSelectionNow && saveSelectionNow(); }""")
        await pg.click('#btnCite'); await pg.wait_for_timeout(500)
        await pg.click('#citePick li:first-child'); await pg.wait_for_timeout(300)
        lab = pg.locator('#citeCluster select').first
        if await lab.count():
            try: await lab.select_option('book')
            except Exception: pass
        loc = pg.locator('#citeCluster input').first
        if await loc.count(): await loc.fill('IV.7'); await loc.dispatch_event('input')
        await pg.wait_for_timeout(500)
        box = await pg.locator('#citeDlg').bounding_box()
        await shot('05-cite', {'x': box['x'] - 8, 'y': box['y'] - 8, 'width': box['width'] + 16, 'height': box['height'] + 16}, '#citePick li:first-child', '#citeCluster')
        await pg.click('#citeOk'); await pg.wait_for_timeout(900)

        # 6. Notes and bibliography appear under the text
        await pg.evaluate("closePanel && closePanel()"); await pg.wait_for_timeout(300)
        await shot('06-notes-and-bibliography', None, '#refs')

        # 7. Switch style
        await pg.select_option('#docStyle', 'apa'); await pg.wait_for_timeout(900)
        await shot('07-switch-style', None, '#docStyle', '#editor p .cite', '#refs')
        await pg.select_option('#docStyle', 'chicago-notes-bibliography'); await pg.wait_for_timeout(600)

        # 8. Take a note and bring it into the draft
        await pg.evaluate("switchTab('notes')"); await pg.wait_for_timeout(300)
        await pg.click('#btnNewNote'); await pg.wait_for_timeout(500)
        await pg.evaluate("""() => { const n = P.notes.find(x => x.id === panelState.id); const s = P.sources.find(x => x.csl.title === 'Anabasis');
            Object.assign(n, { title: 'The sea! the sea!', kind: 'quote', sourceId: s.id, locator: 'IV.7', tags: ['arrival'],
              body: 'Presently they could hear the soldiers shouting and passing on the joyful word, "The sea! the sea!"' });
            renderNoteList(); openNote(n.id); markDirty(); }""")
        await pg.wait_for_timeout(500)
        await pg.evaluate("""() => { const p = editor.querySelector('p'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false);
            const s = getSelection(); s.removeAllRanges(); s.addRange(r); saveSelectionNow && saveSelectionNow(); }""")
        await shot('08-note', None, '#panelFoot [data-a="ins"]', '#noteList li:first-child')
        await pg.click('#panelFoot [data-a="ins"]'); await pg.wait_for_timeout(800)

        # 9. Checks
        await pg.evaluate("closePanel && closePanel(); switchTab('outline')"); await pg.wait_for_timeout(1800)
        await pg.evaluate("$('#corList').scrollIntoView({block: 'center'}); const d = $('#corList details'); if (d) d.open = true"); await pg.wait_for_timeout(300)
        await shot('09-checks', None, '.tabs [data-tab=outline]', '#corList')

        # 10. Save
        async with pg.expect_download() as d: await pg.click('#btnSave')
        dl = await d.value; await dl.cancel() if hasattr(dl, 'cancel') else None
        await pg.wait_for_timeout(600)
        await shot('10-save', {'x': 0, 'y': 0, 'width': W, 'height': 220}, '#btnSave', '#saveState')

        # 11. Export
        await pg.click('#btnExport'); await pg.wait_for_timeout(400)
        await shot('11-export', None, '#exportMenu [data-x=pdf]')
        await pg.keyboard.press('Escape')

        await b.close()
        if errs: sys.exit('page errors: ' + '; '.join(errs))
        try:  # shrink the files: interface screenshots need far fewer than 16 million colors
            from PIL import Image
            for f in OUT.glob('*.png'): Image.open(f).convert('RGB').quantize(colors=192, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
        except ImportError: pass
        print('wrote', len(list(OUT.glob('*.png'))), 'screenshots to', OUT.relative_to(ROOT))


if __name__ == '__main__':
    asyncio.run(main())
