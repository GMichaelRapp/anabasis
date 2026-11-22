"""Accessibility audit of the app itself with axe-core (WCAG 2.1 A/AA), light and dark themes."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL = os.environ.get('ANABASIS_URL', URL)
AXE = os.environ.get('AXE_PATH', AXE)
VIEWS = [
    ('editor', "switchTab('docs')"),
    ('notes tab', "switchTab('notes')"),
    ('sources tab', "switchTab('sources')"),
    ('outline tab', "switchTab('outline')"),
    ('home', "openHome()"),
    ('help', "closeHome(); $('#helpDlg').showModal()"),
    ('chart dialog', "$('#helpDlg').close(); openChart()"),
    ('map dialog', "$('#chDlg').close(); openMap()"),
    ('checkpoints', "$('#mpDlg').close(); openCheckpoints()"),
    ('find all', "$('#cpDlg').close(); openFindAll()"),
    ('promo', "$('#frDlg').close(); openPromo()"),
    ('tour', "$('#pkDlg').close(); startTour()"),
]
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={'width': 1440, 'height': 900})
        await pg.add_init_script("localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true}))")
        await pg.goto(URL); await pg.wait_for_timeout(1200)
        await pg.add_script_tag(content=open(AXE).read())
        total = {}
        for theme in ('light', 'dark'):
            await pg.evaluate(f"document.documentElement.dataset.theme='{theme}'")
            for name, js in VIEWS:
                await pg.evaluate(f"(()=>{{ try {{ {js} }} catch(e) {{ console.warn(e) }} }})()"); await pg.wait_for_timeout(350)
                ctx = "document.querySelector('dialog[open]') || document" if 'dialog' in name or name in ('help', 'checkpoints', 'find all', 'promo') else "document"
                res = await pg.evaluate(f"""axe.run({ctx}, {{ runOnly: {{ type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] }}, resultTypes: ['violations'] }})
                    .then(r => r.violations.map(v => ({{ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, eg: v.nodes.slice(0,3).map(n => n.target.join(' ') + ' :: ' + (n.failureSummary||'').split('\\n').slice(1,2).join('')) }})))""")
                for v in res:
                    k = (v['id'], v['help'])
                    total.setdefault(k, []).append(f"{theme}/{name}: {v['n']} e.g. {v['eg'][:2]}")
            await pg.evaluate("endTour && endTour()")
        for (rid, hlp), where in sorted(total.items()):
            print(f'== {rid}: {hlp}')
            for w in where[:6]: print('   ', w[:400])
        print('RULES FAILING', len(total))
        await b.close()
        sys.exit(1 if total else 0)
asyncio.run(main())
