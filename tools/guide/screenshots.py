"""Regenerate the README screenshots that show the interface itself.

    python build.py && python tools/guide/screenshots.py

Writes docs/screenshots/editor-light.png, editor-dark.png, research.png, journal.png and phone.png
from the sample project (journal.png from the thesis example). (map.png, chart.png and checks.png show figures and checks and are kept as they are.)
"""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'dist' / 'anabasis.html').as_uri()
OUT = ROOT / 'docs' / 'screenshots'
PREFS = "localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))"

MARKS = """() => {
  const ps = editor.querySelectorAll('p');
  const sel = (p, a, z) => { const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); const ns = []; let n; while ((n = w.nextNode())) if (!n.parentElement.closest('.cite,.fn')) ns.push(n);
    const at = o => { for (const x of ns) { if (o <= x.data.length) return [x, o]; o -= x.data.length; } const l = ns[ns.length - 1]; return [l, l.data.length]; };
    const [sn, so] = at(a), [en, eo] = at(z); const r = document.createRange(); r.setStart(sn, so); r.setEnd(en, eo); return r; };
  const t = newThread('Escalation', '#2A9D8F');
  rmApply(sel(ps[1], 0, 76), 'th', { ref: t.id });
  const id = uid('cl'); rmApply(sel(ps[2], 0, 78), 'cl', { pid: id }); P.claims.push({ id, status: 'open', note: '', checkedText: '', checkedAt: '', created: nowISO(), modified: nowISO() }); setClaimStatus(id, 'ok');
  const id2 = uid('cl'); rmApply(sel(ps[3], 0, 46), 'cl', { pid: id2 }); P.claims.push({ id: id2, status: 'disp', note: '', checkedText: '', checkedAt: '', created: nowISO(), modified: nowISO() });
  const rv = uid('rv'); rmApply(sel(ps[4], 0, 40), 'rv', { pid: rv }); P.reviewKeys.push({ id: rv, reason: 'Verify a fact', due: todayISO(), note: '', done: false, doneAt: '', created: nowISO() });
  switchTab('research'); rmRefresh();
}"""


async def main():
    if not (ROOT / 'dist' / 'anabasis.html').exists(): sys.exit('Build first: python build.py')
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for theme in ('light', 'dark'):
            ctx = await b.new_context(viewport={'width': 1440, 'height': 880})
            await ctx.add_init_script(PREFS); pg = await ctx.new_page()
            await pg.goto(APP); await pg.wait_for_timeout(1500)
            await pg.evaluate(f"setTheme('{theme}'); switchTab('notes')"); await pg.wait_for_timeout(500)
            await pg.screenshot(path=str(OUT / f'editor-{theme}.png'))
            if theme == 'light':
                await pg.evaluate(MARKS); await pg.wait_for_timeout(400)
                box = await pg.evaluate("() => { const r = editor.querySelector('.rm[data-k=cl]').getClientRects()[0]; return [r.left + 60, r.top + r.height / 2]; }")
                await pg.mouse.click(*box); await pg.wait_for_timeout(400)
                await pg.screenshot(path=str(OUT / 'research.png'))
                await pg.evaluate("async () => { dirtyFile = false; await openStarter('thesis'); openJournal('hyp'); }"); await pg.wait_for_timeout(900); await pg.evaluate("() => $('#toast').classList.remove('show')"); await pg.wait_for_timeout(400)
                await pg.screenshot(path=str(OUT / 'journal.png'))
                await pg.evaluate("() => { const d = newDataset('Defense spending, share of GDP', gridFromText(DEMO_CSV)); const b = newDashboard(); b.title = 'Defense spending on NATO’s eastern flank'; b.subtitle = 'Share of GDP, 2019–2024 (illustrative figures)'; b.tiles = [Object.assign(newTile('stat', d), { title: 'Poland, 2024', col: 'Poland', agg: 'latest', suffix: '% of GDP', fmt: 'd1', w: 1, h: 1 }), Object.assign(newTile('stat', d), { title: 'Estonia, 2024', col: 'Estonia', agg: 'latest', suffix: '% of GDP', fmt: 'd1', w: 1, h: 1 }), Object.assign(newTile('chart', d), { title: 'Share of GDP spent on defense', kind: 'line', labelCol: 'Year', valueCols: ['Poland', 'Estonia', 'Germany'], fmt: 'd1', ylabel: '% of GDP', w: 2, h: 2 }), Object.assign(newTile('table', d), { title: 'All figures', w: 2, h: 1 })]; dataSel = b.id; dbEdit = false; openDesk('data'); }"); await pg.wait_for_timeout(2500)
                await pg.evaluate("() => $('#toast').classList.remove('show')"); await pg.wait_for_timeout(300)
                await pg.screenshot(path=str(OUT / 'dashboard.png'))
                await pg.evaluate("() => { closeDesk(); openDoc(P.docs[0].id); splitOpen('notes'); }"); await pg.wait_for_timeout(900)
                await pg.screenshot(path=str(OUT / 'split.png'))
                await pg.evaluate("() => splitClose()")
                await pg.evaluate(r"""async () => { const d = newDoc('Measuring deterrence', '<h1>A simple model</h1><p>Let ' + eqHTML('p', false) + ' be the chance an attack succeeds and ' + eqHTML('C', false) + ' its cost. An attacker expects</p>' + eqHTML('E[U] = p\\,B - (1 - p)\\,C', true, true) + '<p>so deterrence holds when</p>' + eqHTML('p < \\frac{C}{B + C}', true, true) + '<p>Summed over ' + eqHTML('n', false) + ' independent attempts, the chance of at least one success is</p>' + eqHTML('1 - \\prod_{i=1}^{n} (1 - p_i)', true, true) + '<p><br></p>'); addDoc(d); switchTab('docs'); await mathLoad(); hydrateImages(); renumberFigures(); }"""); await pg.wait_for_timeout(1200)
                await pg.evaluate("() => $('#toast').classList.remove('show')"); await pg.wait_for_timeout(300)
                await pg.screenshot(path=str(OUT / 'equations.png'))
            await ctx.close()
        # a phone: the draft, and the toolbar's ⋯ menu
        ctx = await b.new_context(viewport={'width': 390, 'height': 760}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script(PREFS); pg = await ctx.new_page()
        await pg.goto(APP); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/tmp/phone-a.png')
        await pg.click('#btnTbMore'); await pg.wait_for_timeout(400)
        await pg.screenshot(path='/tmp/phone-b.png')
        await ctx.close(); await b.close()
    from PIL import Image
    a, c = Image.open('/tmp/phone-a.png'), Image.open('/tmp/phone-b.png')
    gap = 60; W = a.width + c.width + gap * 3
    sheet = Image.new('RGB', (W, a.height + gap * 2), (231, 235, 228))
    sheet.paste(a, (gap, gap)); sheet.paste(c, (a.width + gap * 2, gap))
    sheet = sheet.resize((W // 2, (a.height + gap * 2) // 2), Image.LANCZOS)
    sheet.save(OUT / 'phone.png', optimize=True)
    for f in ('editor-light.png', 'editor-dark.png', 'research.png', 'journal.png', 'dashboard.png', 'split.png', 'equations.png'):
        p = OUT / f; Image.open(p).convert('RGB').quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(p, optimize=True)
    print('wrote editor-light.png, editor-dark.png, research.png, journal.png, dashboard.png, split.png, equations.png, phone.png to', OUT.relative_to(ROOT))


if __name__ == '__main__':
    asyncio.run(main())
