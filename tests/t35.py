"""1.7: source types (primary, secondary, tertiary) on sources and notes, the grouped bibliography,
and the new charts: scatter and bubble, histogram, heatmap, shaded maps."""
import asyncio, json, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("async () => { dirtyFile = false; await openStarter('thesis'); }"); await pg.wait_for_timeout(800)

        # ---- source types
        r = await pg.evaluate("() => P.sources.map(s => s.stype)")
        check('the example marks Xenophon primary and the historians secondary', sorted(r) == ['primary', 'secondary', 'secondary', 'secondary'], r)
        await pg.evaluate("() => switchTab('sources')")
        check('the sources list shows each type as a badge', await pg.locator('#sourceList .stype.st-primary').count() == 1 and await pg.locator('#sourceList .stype.st-secondary').count() == 3)
        await pg.click('#srcChips [data-st=primary]'); await pg.wait_for_timeout(100)
        check('filter sources by type', await pg.locator('#sourceList li').count() == 1)
        await pg.click('#srcChips [data-st=primary]')
        lee = await pg.evaluate("() => P.sources.find(s => /Greek Army/.test(s.csl.title)).id")
        await pg.evaluate(f"() => openSource('{lee}')"); await pg.wait_for_timeout(200)
        await pg.select_option('#srcStype', 'tertiary'); await pg.wait_for_timeout(300)
        check('set a source’s type in its panel', await pg.evaluate(f"() => P.sources.find(s => s.id === '{lee}').stype === 'tertiary'"))
        await pg.evaluate("() => { closePanel(); switchTab('notes'); }"); await pg.wait_for_timeout(100)
        r = await pg.evaluate(f"() => P.notes.filter(n => n.sourceId === '{lee}').map(n => noteSType(n))")
        check('notes inherit their source’s type', r == ['tertiary'], r)
        note = await pg.evaluate(f"() => P.notes.find(n => n.sourceId === '{lee}').id")
        await pg.evaluate(f"() => openNote('{note}')"); await pg.wait_for_timeout(200)
        opt0 = await pg.evaluate("() => $('#nStype').options[0].textContent")
        check('a note says where its type comes from', opt0 == 'From source: Tertiary', opt0)
        await pg.select_option('#nStype', 'primary'); await pg.wait_for_timeout(500)
        check('a note can override it', await pg.evaluate(f"() => noteSType(P.notes.find(n => n.id === '{note}')) === 'primary'"))
        await pg.select_option('#nStype', 'none'); await pg.wait_for_timeout(500)
        check('…or set none', await pg.evaluate(f"() => noteSType(P.notes.find(n => n.id === '{note}')) === ''"))
        await pg.select_option('#nStype', ''); await pg.wait_for_timeout(500); await pg.evaluate("() => closePanel()")
        await pg.click('#tagChips [data-st=tertiary]'); await pg.wait_for_timeout(100)
        check('filter notes by type', await pg.locator('#noteList li').count() == 1)
        await pg.click('#tagChips [data-st=tertiary]')
        # bibliography grouped by type
        await pg.evaluate("() => { const d = curDoc(); d.layout.bib = 'all'; d.layout.bibSplit = true; renderRefs(true); }"); await pg.wait_for_timeout(600)
        subs = await pg.evaluate("() => $$('#refs .bib-sub').map(x => x.textContent)")
        check('Page setup can group the bibliography by source type', subs == ['Primary sources', 'Secondary sources', 'Tertiary sources'], subs)
        md = await pg.evaluate("() => { const x = buildExport(curDoc(), 'md'); return JSON.stringify(x.out.bib.entries.slice(0, 2)); }")
        check('…and exports carry the groups', 'Primary sources' in md)
        await pg.evaluate("() => { const d = curDoc(); d.layout.bibSplit = false; renderRefs(true); }"); await pg.wait_for_timeout(400)
        check('…or one list', await pg.locator('#refs .bib-sub').count() == 0)
        # a claim cited only to tertiary sources is flagged
        r = await pg.evaluate(f"""() => {{ const p = rmAll('cl').find(x => x.cites.length); const fake = Object.assign({{}}, p, {{ cites: ['{lee}'] }}); return [claimIssues(fake, {{ status: 'open' }}), claimIssues(Object.assign({{}}, p, {{ cites: P.sources.filter(s => s.stype === 'secondary').map(s => s.id) }}), {{ status: 'open' }})]; }}""")
        check('a claim cited only to tertiary sources is flagged', 'Only tertiary sources' in r[0] and 'Only tertiary sources' not in r[1], r)
        # save and reopen keeps types
        saved = await pg.evaluate("() => projectJSON()")
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'x.json'); }", saved); await pg.wait_for_timeout(700)
        r = await pg.evaluate(f"() => [P.sources.find(s => s.id === '{lee}').stype, P.sources.filter(s => s.stype).length]")
        check('types survive saving and reopening', r == ['tertiary', 4], r)
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p>x</p>'}], 'sources': [{'id': 's1', 'csl': {'title': 'T'}, 'stype': '<b>'}], 'notes': [{'id': 'n1', 'body': 'x', 'stype': {'a': 1}}]})
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'bad.json'); }", bad); await pg.wait_for_timeout(600)
        r = await pg.evaluate("() => [P.sources[0].stype || '', P.notes[0].stype]")
        check('odd source types are dropped', r == ['', ''], r)

        # ---- the new charts
        specs = {
            'scatter': "Country, Spending, Troops, Population, Alliance\nUnited States, 916, 1328, 335, NATO\nChina, 296, 2035, 1410, Other\nPoland, 32, 164, 37, NATO",
            'hist': "Days\n3\n5\n8\n9\n12\n13\n40\n41\n90",
            'heat': "Month, 2022, 2023\nJan, 40, 33\nFeb, -95, 30",
            'choro': "Country, Value\nUSA, 3.4\nUK, 2.3\nCzech Republic, 2.1\nDemocratic Republic of the Congo, 1\nNarnia, 9",
        }
        for k, d in specs.items():
            r = await pg.evaluate("([k, d]) => { const s = { type: 'chart', kind: k, data: d, fmt: 'n', aspect: 'wide', region: 'world' }; const c = vizCheck(s); const v = c.err ? '' : vizSVG(s).svg; return { err: c.err || '', note: c.note || '', n: (v.match(/<(circle|rect|path)/g) || []).length, titles: (v.match(/<title>/g) || []).length }; }", [k, d])
            check(f'{k}: draws, with a tooltip on every mark', not r['err'] and r['n'] > 3 and r['titles'] >= 3, r)
        r = await pg.evaluate("() => vizCheck({ kind: 'choro', data: 'Country, Value\\nUSA, 3.4\\nUK, 2.3\\nCzech Republic, 2.1\\nDemocratic Republic of the Congo, 1\\nNarnia, 9', region: 'world' })")
        check('shaded maps match common country names and list the rest', r['note'].startswith('Not on this map: Narnia'), r)
        r = await pg.evaluate("() => { const d = choroData({ data: 'State, n\\nTX, 1\\nCalifornia, 2\\nDC, 3\\nwashington, 4', region: 'us' }); return [...d.vals.keys()].sort(); }")
        check('US states by name or postal code, and D.C.', r == ['California', 'Texas', 'Washington', 'Washington, D.C.'], r)
        r = await pg.evaluate("() => { const d = choroData({ data: 'Oblast, n\\nKharkiv, 5\\nOdessa, 2', region: 'adm:Ukraine' }); return d.err ? d.err : [...d.vals.keys()]; }")
        check('regions of other countries', isinstance(r, list) and len(r) >= 1, r)
        r = await pg.evaluate("() => { const s = heatSVG({ data: 'R, a, b\\nx, -10, 5\\ny, 10, 0', fmt: 'n' }, 800, 450); return /#7f1d1d|rgb\\(127,29,29\\)/.test(s) || /rgb\\(1[0-9]{2},\\d+,\\d+\\)/.test(s); }")
        check('values that cross zero use the diverging colors', r)
        r = await pg.evaluate("() => { const s = histSVG({ data: 'v\\n1\\n2\\n3\\n4\\n100', bins: 4, fmt: 'n' }, 800, 450); return [(s.match(/<rect x=/g) || []).length, /Median 3/.test(s)]; }")
        check('histogram bins and median', r[0] >= 4 and r[1], r)
        # through the chart dialog into the document
        await pg.evaluate("async () => { dirtyFile = false; await openStarter('thesis'); }"); await pg.wait_for_timeout(700)
        await pg.evaluate("() => { editor.focus(); const r = document.createRange(); r.selectNodeContents(editor); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); saveSelectionNow(); openChart(); }"); await pg.wait_for_timeout(200)
        await pg.select_option('#chType', 'scatter'); await pg.wait_for_timeout(100)
        check('the dialog explains each kind’s data', 'sizes the bubbles' in await pg.inner_text('#chHint') and await pg.evaluate("() => $('#chEventsRow').classList.contains('hidden')"))
        await pg.fill('#chData', specs['scatter']); await pg.wait_for_timeout(400)
        await pg.select_option('#chType', 'choro'); await pg.wait_for_timeout(100)
        check('shaded maps offer a choice of map', await pg.evaluate("() => !$('#chRegionRow').classList.contains('hidden') && $$('#chRegion option').length > 20"))
        await pg.fill('#chData', "State, n\nTX, 1\nCA, 2"); await pg.select_option('#chRegion', 'us'); await pg.wait_for_timeout(500)
        n0 = await pg.evaluate("() => editor.querySelectorAll('figure').length")
        await pg.click('#chOk'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("() => { const f = [...editor.querySelectorAll('figure')].pop(), img = f && f.querySelector('img'), a = img && P.assets[img.dataset.asset]; return { n: editor.querySelectorAll('figure').length, spec: a && a.spec && [a.spec.kind, a.spec.region] }; }")
        check('a shaded map goes into the document as an editable figure', r['n'] == n0 + 1 and r['spec'] == ['choro', 'us'], r)
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
