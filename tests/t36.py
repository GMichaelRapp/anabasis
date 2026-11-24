"""1.7: datasets and the data dashboard: importing, tiles of every kind, the tile editor, layout,
inserting a tile as a figure, the exported page, saving, and hostile data."""
import asyncio, json, re, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

CSV = "Date,City,Latitude,Longitude,Incidents,Side\n2024-02-01,Kharkiv,49.99,36.23,120,North\n2024-02-08,Kherson,46.64,32.61,80,South\n2024-02-15,Zaporizhzhia,47.84,35.14,95,South\n2024-02-22,Donetsk,48.0,37.8,160,East\n2024-03-01,Kyiv,50.45,30.52,40,North\n2024-03-08,Odesa,46.48,30.72,55,South\n2024-03-15,Sumy,50.91,34.8,66,North\n2024-03-22,Dnipro,48.46,35.04,71,East\n2024-03-29,Mykolaiv,46.97,32.0,48,South"


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        await pg.evaluate("() => openDesk('data')"); await pg.wait_for_timeout(300)
        check('the Data view explains itself when empty', 'Show your data, with its sources' in await pg.inner_text('#deskBody'))
        # import by pasting
        await pg.click('#deskBody button:has-text("Import a CSV")'); await pg.wait_for_timeout(200)
        await pg.fill('#dsImpText', 'just one line'); await pg.click('#dsImpOk')
        check('a non-table is refused with a reason', 'first row should name the columns' in await pg.inner_text('#dsImpErr'))
        await pg.fill('#dsImpText', CSV); await pg.fill('#dsImpName', 'Incidents'); await pg.click('#dsImpOk'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => { const d = P.datasets[0]; return { n: d.name, cols: d.cols, rows: d.rows.length, types: d.cols.map((_, i) => colType(d, i)) }; }")
        check('pasted data becomes a dataset with typed columns', r == {'n': 'Incidents', 'cols': ['Date', 'City', 'Latitude', 'Longitude', 'Incidents', 'Side'], 'rows': 9, 'types': ['date', 'text', 'lat', 'lon', 'number', 'text']}, r)
        check('…shown as a table', await pg.locator('.d-tbl tbody tr').count() == 9)
        src = await pg.evaluate("() => P.sources[0].id")
        await pg.select_option('#dsSrc', src); await pg.wait_for_timeout(100)
        check('a dataset can name its source', await pg.evaluate(f"() => P.datasets[0].sourceId === '{src}'"))
        async with pg.expect_download() as d: await pg.click('#deskTools button:has-text("Download CSV")')
        csv = open(await (await d.value).path(), encoding='utf-8').read()
        check('download the dataset as CSV', csv.splitlines()[0] == 'Date,City,Latitude,Longitude,Incidents,Side' and len(csv.splitlines()) == 10)

        # a dashboard with every kind of tile
        await pg.click('.d-side h6:has-text("Dashboards") button'); await pg.wait_for_timeout(200)
        db = await pg.evaluate("() => P.dashboards[0].id")
        for kind in ['Number', 'Chart', 'Map of places', 'Timeline', 'Table', 'Text']:
            await pg.click(f'.db-add button:has-text("{kind}")'); await pg.wait_for_timeout(500)
            if kind == 'Number':
                await pg.fill('#tlTitle', 'Incidents, all cities'); await pg.select_option('#tlCol', 'Incidents'); await pg.select_option('#tlAgg', 'sum'); await pg.wait_for_timeout(400)
                check('the tile editor previews as you go', '735' in await pg.inner_text('#tlPrev'))
            if kind == 'Chart':
                await pg.select_option('#tlKind', 'hbar'); await pg.wait_for_timeout(200); await pg.select_option('#tlLabel', 'City'); await pg.wait_for_timeout(300)
            if kind == 'Text':
                await pg.fill('#tlBody', 'Counts from **open reporting**.'); await pg.wait_for_timeout(300)
            await pg.click('#tlOk'); await pg.wait_for_timeout(600)
        await pg.wait_for_timeout(1500)
        r = await pg.evaluate("() => [...document.querySelectorAll('#dbGrid [data-tile]')].map(t => [t.className.match(/tt-(\\w+)/)[1], !!t.querySelector('.tl-body svg, .tl-body img, .tl-stat, .tl-body table, .tl-text'), !t.querySelector('.tl-empty')])")
        check('every tile draws: number, chart, map, timeline, table, text', [x[0] for x in r] == ['stat', 'chart', 'map', 'timeline', 'table', 'text'] and all(x[1] and x[2] for x in r), r)
        check('the number tile totals the column', '735' in await pg.inner_text('#dbGrid .tt-stat'))
        check('tiles credit the dataset’s source', await pg.locator('#dbGrid .tl-src').count() >= 5)
        check('the map plots every row with coordinates', await pg.evaluate("() => $('#dbGrid .tt-map svg').querySelectorAll('[data-item]').length === 9"))
        # svg ids stay unique when several maps share the page
        await pg.evaluate("() => { const b = P.dashboards[0]; b.tiles.push(Object.assign(newTile('map'), { title: 'Second map' })); renderDesk(); }"); await pg.wait_for_timeout(1500)
        dup = await pg.evaluate("() => { const ids = [...document.querySelectorAll('#dbGrid svg [id]')].map(e => e.id); return ids.length - new Set(ids).size; }")
        check('several maps on one dashboard don’t share drawing ids', dup == 0, dup)
        # table: filter and sort
        await pg.fill('#dbGrid .tt-table .tl-q', 'south'); await pg.wait_for_timeout(100)
        check('tables filter', await pg.evaluate("() => [...$$('#dbGrid .tt-table tbody tr')].filter(r => !r.hidden).length === 4"))
        await pg.fill('#dbGrid .tt-table .tl-q', '')
        await pg.click('#dbGrid .tt-table th >> nth=4 >> button'); await pg.click('#dbGrid .tt-table th >> nth=4 >> button'); await pg.wait_for_timeout(100)
        check('tables sort by a column, numbers as numbers', await pg.evaluate("() => $('#dbGrid .tt-table tbody tr td:nth-child(5)').textContent === '160'"))
        # layout
        await pg.click('#dbGrid .tt-stat [data-tact=w]'); await pg.wait_for_timeout(300)
        check('resize a tile', await pg.evaluate("() => P.dashboards[0].tiles[0].w === 2"))
        await pg.click('#dbGrid .tt-text [data-tact=up]'); await pg.wait_for_timeout(300)
        check('move a tile', await pg.evaluate("() => P.dashboards[0].tiles.map(t => t.type).join() === 'stat,chart,map,timeline,text,table,map'"))
        await pg.click('#dbGrid .tt-text [data-tact=rm]'); await pg.wait_for_timeout(200)
        gone = await pg.evaluate("() => P.dashboards[0].tiles.length === 6")
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(300)
        check('remove a tile, and undo', gone and await pg.evaluate("() => P.dashboards[0].tiles.length === 7"))
        await pg.click('#deskTools button:has-text("Preview")'); await pg.wait_for_timeout(1200)
        check('preview hides the editing controls', await pg.locator('#dbGrid .db-tbar').count() == 0 and await pg.locator('.db-add').count() == 0)
        await pg.click('#deskTools button:has-text("Edit")'); await pg.wait_for_timeout(800)
        # video tile
        await pg.evaluate("() => { const b = P.dashboards[0]; b.tiles.push(Object.assign(newTile('video'), { title: 'Briefing', url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' })); renderDesk(); }"); await pg.wait_for_timeout(800)
        check('video shows as a link inside Anabasis (nothing loads from outside)', await pg.evaluate("() => !!$('#dbGrid .tl-vidph') && !document.querySelector('#dbGrid iframe')"))
        # insert a chart tile in the document
        n0 = await pg.evaluate("() => P.docs[0].html.split('<figure').length")
        await pg.click('#dbGrid .tt-chart [data-tact=ins]'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("() => ({ desk: deskOn, n: editor.querySelectorAll('figure').length, spec: (() => { const f = [...editor.querySelectorAll('figure img')].pop(); const a = f && P.assets[f.dataset.asset]; return a && a.spec && a.spec.kind; })() })")
        check('insert a chart tile in the document as a figure', not r['desk'] and r['spec'] == 'hbar', r)
        # export
        await pg.evaluate("() => openDesk('data')"); await pg.wait_for_timeout(1500)
        async with pg.expect_download() as d: await pg.click('#deskTools button:has-text("Export page")')
        html = open(await (await d.value).path(), encoding='utf-8').read()
        check('the exported page has every tile, the sources and the data', html.count('<section class="tile') == 8 and '<h2>Sources</h2>' in html and 'data:text/csv' in html and 'youtube-nocookie.com/embed/dQw4w9WgXcQ' in html, html.count('<section class="tile'))
        check('…as one self-contained page', '<script src' not in html and 'href="http' not in html.split('<footer>')[0].replace('https://www.youtube-nocookie', ''))
        ctx2 = await b.new_context(); p2 = await ctx2.new_page(); p2.on('pageerror', lambda e: errs.append('EXPORT ' + str(e)))
        await p2.set_content(html); await p2.wait_for_timeout(300)
        await p2.fill('.tt-table .tl-q', 'east'); await p2.wait_for_timeout(100)
        check('…whose tables filter and sort on their own', await p2.evaluate("() => [...document.querySelectorAll('.tt-table tbody tr')].filter(r => !r.hidden).length === 2"))
        await ctx2.close()
        # save and reopen; hostile data
        saved = await pg.evaluate("() => projectJSON()")
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'x.json'); }", saved); await pg.wait_for_timeout(700)
        r = await pg.evaluate("() => [P.datasets.length, P.datasets[0].rows.length, P.dashboards[0].tiles.length, P.dashboards[0].tiles[0].agg]")
        check('datasets and dashboards survive saving and reopening', r == [1, 9, 8, 'sum'], r)
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p>x</p>'}],
                          'datasets': [{'id': 'ds1', 'name': '<img src=x onerror=alert(1)>', 'cols': ['a', {'x': 1}], 'rows': [['1', 2], 'nope', [None, '<b>']]}, 'junk'],
                          'dashboards': [{'id': 'db1', 'title': 5, 'tiles': [{'type': 'evil'}, {'type': 'text', 'w': 99, 'h': -1, 'body': '<script>alert(1)</script>**hi**'}, {'type': 'video', 'url': 'javascript:alert(1)'}]}]})
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'bad.json'); }", bad); await pg.wait_for_timeout(700)
        r = await pg.evaluate("() => ({ ds: P.datasets.map(d => [d.cols, d.rows]), t: P.dashboards[0].tiles.map(t => [t.type, t.w, t.h, t.url]), title: P.dashboards[0].title })")
        check('hostile datasets and tiles are tidied', r == {'ds': [[['a', ''], [['1', '2'], ['', '<b>']]]], 't': [['text', 2, 2, ''], ['video', 2, 2, '']], 'title': '5'}, r)
        await pg.evaluate("() => { dataSel = P.dashboards[0].id; openDesk('data'); }"); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => [!document.querySelector('#deskBody script'), !document.querySelector('#deskBody img[src=x]'), ($('#dbGrid .tl-text') || {}).innerHTML]")
        check('…and shown as text, never run', r[0] and r[1] and 'hi' in (r[2] or '') and 'script' not in (r[2] or ''), r)
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
