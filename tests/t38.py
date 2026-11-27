"""1.7.1: data in the writing: a table tile or a dataset as a document table, a number tile in the sentence
(with its citation), figures, tables and numbers that remember their dataset, Update from data, unlinking,
saving, exports, pasting, the pop-out window and hostile links."""
import asyncio, json, re, sys, zipfile, io
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

CSV = "Year,Poland,Estonia,Germany\n2021,2.2,2.0,1.3\n2022,2.4,2.1,1.4\n2023,3.8,2.7,1.6\n2024,4.1,3.4,2.1"
CSV2 = "Year,Poland,Estonia,Germany\n2021,2.2,2.0,1.3\n2022,2.4,2.1,1.4\n2023,3.8,2.7,1.6\n2024,4.1,3.4,2.1\n2025,4.7,3.4,2.4"


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
        # hostile markup in this test carries event handlers: the page's policy refusing them as it's parsed is expected
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Executing inline event handler' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        # a document with a sentence, a dataset with a source, a dashboard with a number, a table and a chart
        await pg.evaluate("""() => {
          editor.innerHTML = '<p>Poland now spends</p><p>Next paragraph.</p>'; syncEditor();
          const g = gridFromText(CSVDATA); const d = newDataset('Defence spending', g); d.sourceId = P.sources[0].id;
          const b = newDashboard();
          b.tiles.push(Object.assign(newTile('stat', d), { title: 'Poland, 2024', col: 'Poland', agg: 'latest', fmt: 'n', suffix: '% of GDP' }));
          b.tiles.push(Object.assign(newTile('table', d), { title: 'Spending by year', sortCol: 'Year', sortDir: 'desc' }));
          b.tiles.push(Object.assign(newTile('chart', d), { title: 'Spending', kind: 'line', labelCol: 'Year', valueCols: ['Poland', 'Estonia'] }));
          dataSel = b.id; markDirty();
        }""".replace('CSVDATA', json.dumps(CSV)))
        src = await pg.evaluate("() => { const s = sourceLabel(P.sources[0]); return [s.who, s.title].filter(Boolean).join(', '); }")
        # put the caret at the end of the first sentence, then open the dashboard
        await pg.evaluate("() => { const t = editor.querySelector('p').firstChild; const r = document.createRange(); r.setStart(t, t.length); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); }")
        await pg.evaluate("() => openDesk('data')"); await pg.wait_for_timeout(1200)
        check('number and table tiles have an Insert button', await pg.locator('#dbGrid .tt-stat [data-tact=ins]').count() == 1 and await pg.locator('#dbGrid .tt-table [data-tact=ins]').count() == 1)

        # 1. a number in the sentence, then its citation
        await pg.click('#dbGrid .tt-stat [data-tact=ins]'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ desk: deskOn, p: editor.querySelector('p').innerHTML, t: editor.querySelector('p').textContent, toast: $('#toast').textContent })")
        check('a number tile drops its value into the sentence, where the caret was', not r['desk'] and r['t'].startswith('Poland now spends 4.1% of GDP') and 'class="dnum"' in r['p'], r)
        check('…as one piece (it can’t be half-edited)', await pg.evaluate("() => editor.querySelector('.dnum').getAttribute('contenteditable') === 'false'"))
        check('…and offers to cite the dataset’s source', 'Cite the source' in r['toast'], r['toast'])
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => { const n = editor.querySelector('.dnum'), c = n.nextElementSibling; return { cite: !!(c && c.classList.contains('cite')), items: c && c.dataset.items, para: editor.querySelector('p').contains(c) }; }")
        sid = await pg.evaluate("() => P.sources[0].id")
        check('“Cite the source” puts the citation right after the number', r['cite'] and r['para'] and sid in (r['items'] or ''), r)

        # 2. a table tile as a document table
        await pg.evaluate("() => { const p = editor.querySelectorAll('p')[1]; const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); openDesk('data'); }"); await pg.wait_for_timeout(1000)
        await pg.click('#dbGrid .tt-table [data-tact=ins]'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => { const f = editor.querySelector('figure.tbl[data-dl]'); return f && { cap: f.querySelector('figcaption').textContent, head: [...f.querySelectorAll('th')].map(x => x.textContent), first: [...f.querySelectorAll('tbody tr')][0].textContent, rows: f.querySelectorAll('tbody tr').length, n: f.querySelector('figcaption').dataset.cpN, after: f.previousElementSibling && f.previousElementSibling.textContent }; }")
        check('a table tile goes in as a real table, sorted as the tile is', r and r['head'] == ['Year', 'Poland', 'Estonia', 'Germany'] and r['rows'] == 4 and r['first'].startswith('2024'), r)
        check('…with its title and source line, numbered with the other tables', r and r['cap'] == f'Spending by year. Source: {src}.' and r['n'] == 'Table 1.', r)
        check('…after the paragraph holding the caret', r and r['after'] == 'Next paragraph.', r)
        check('…marked as linked on screen', await pg.evaluate("() => getComputedStyle(editor.querySelector('figure.tbl[data-dl]'), '::after').content.includes('Linked to data')"))

        # a whole dataset, from the Data view
        await pg.evaluate("() => { dataSel = P.datasets[0].id; openDesk('data'); }"); await pg.wait_for_timeout(600)
        check('the Data view says how much of the writing uses the dataset', 'Update the writing (2)' in await pg.inner_text('#deskTools'))
        await pg.click('#deskTools button:has-text("Insert as table")'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => [...editor.querySelectorAll('figure.tbl[data-dl]')].map(f => [f.querySelector('figcaption').textContent, f.querySelector('tbody tr').textContent.slice(0, 4)])")
        check('“Insert as table” puts the whole dataset in, in its own order', len(r) == 2 and r[1][0] == f'Defence spending. Source: {src}.' and r[1][1] == '2021', r)

        # 3. a chart tile as a linked figure
        await pg.evaluate("() => openDesk('data')"); await pg.evaluate("() => { dataSel = P.dashboards[0].id; renderDesk(); }"); await pg.wait_for_timeout(1000)
        await pg.click('#dbGrid .tt-chart [data-tact=ins]'); await pg.wait_for_timeout(1800)
        r = await pg.evaluate("() => { const f = editor.querySelector('figure.fig[data-dl]'); const a = f && P.assets[f.querySelector('img').dataset.asset]; return f && { asset: f.querySelector('img').dataset.asset, kind: a.spec.kind, toast: $('#toast').textContent }; }")
        check('a chart tile goes in as a figure that keeps track of its data', r and r['kind'] == 'line' and 'keeps track' in r['toast'], r)
        fig_asset = r and r['asset']

        # nothing changed yet: up to date
        await pg.evaluate("() => refreshFromData()"); await pg.wait_for_timeout(800)
        check('Update from data with nothing new says so', 'up to date' in await pg.inner_text('#toast'), await pg.inner_text('#toast'))

        # 4. replace the data: the prompt, then everything updates
        await pg.evaluate("() => { dataSel = P.datasets[0].id; openDesk('data'); }"); await pg.wait_for_timeout(500)
        await pg.click('#deskTools button:has-text("Replace data")'); await pg.wait_for_timeout(200)
        await pg.fill('#dsImpText', CSV2); await pg.click('#dsImpOk'); await pg.wait_for_timeout(300)
        t = await pg.inner_text('#toast')
        check('replacing the data says what in the writing comes from it, and offers to update', 'in your writing come from it' in t and 'Update the writing' in t, t)
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(2500)
        t = await pg.inner_text('#toast')
        r = await pg.evaluate("() => ({ num: editor.querySelector('.dnum').textContent, rows: [...editor.querySelectorAll('figure.tbl[data-dl]')].map(f => f.querySelectorAll('tbody tr').length), top: editor.querySelector('figure.tbl[data-dl] tbody tr').textContent.slice(0, 4), asset: editor.querySelector('figure.fig[data-dl] img').dataset.asset, src: !!editor.querySelector('figure.fig[data-dl] img').getAttribute('src') })")
        check('…the number follows the new data', r['num'] == '4.7% of GDP', r)
        check('…so do both tables', r['rows'] == [5, 5] and r['top'] == '2025', r)
        check('…and the figure is redrawn', r['asset'] != fig_asset and r['src'], r)
        check('…with a report of what changed', 'Updated 1 figure, 2 tables, 1 number' in t, t)
        newspec = await pg.evaluate("() => P.assets[editor.querySelector('figure.fig[data-dl] img').dataset.asset].spec.data")
        check('…from the new rows', '2025' in newspec)

        # the source changes: captions follow, a hand-written caption is left alone
        await pg.evaluate("() => { const cs = editor.querySelectorAll('figure.tbl[data-dl] figcaption'); cs[1].textContent = 'My own words about this table'; syncEditor(); P.datasets[0].sourceId = P.sources[1].id; }")
        src2 = await pg.evaluate("() => { const s = sourceLabel(P.sources[1]); return [s.who, s.title].filter(Boolean).join(', '); }")
        await pg.evaluate("() => refreshFromData()"); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("() => [...editor.querySelectorAll('figure[data-dl] figcaption')].map(c => c.textContent)")
        check('a new source for the dataset updates the source line', r[0] == f'Spending by year. Source: {src2}.' and r[2].endswith(f'Source: {src2}.'), r)
        check('…but leaves a caption you rewrote', r[1] == 'My own words about this table', r)

        # other documents are updated too, without being open
        await pg.evaluate("""() => { syncEditor(); const d = newDoc(); d.title = 'Second'; d.html = editor.innerHTML; P.docs.push(d); markDirty();
          P.datasets[0].rows.find(r => r[0] === '2025')[1] = '5.2'; }""")
        res = await pg.evaluate("() => refreshFromData().then(r => r)")
        other = await pg.evaluate("() => { const d = P.docs.find(x => x.title === 'Second'); return { num: /class=\"dnum\"[^>]*>([^<]*)</.exec(d.html)[1], src: /data-asset=\"[^\"]+\" src=/.test(d.html) }; }")
        check('documents that aren’t open are updated as well', res['docs'] == 2 and other['num'] == '5.2% of GDP' and not other['src'], [res, other])

        # unlinking: a table from its toolbar, a number by clicking it
        await pg.evaluate("() => { closeDesk(); const td = editor.querySelector('figure.tbl[data-dl] td'); const r = document.createRange(); r.selectNodeContents(td); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }"); await pg.wait_for_timeout(300)
        check('a linked table’s toolbar has Update from data and Unlink', await pg.locator('#tblBar [data-t=dlup]:visible').count() == 1 and await pg.locator('#tblBar [data-t=dlun]:visible').count() == 1)
        await pg.click('#tblBar [data-t=dlup]'); await pg.wait_for_timeout(300)
        check('…Update from data on one table', 'up to date' in await pg.inner_text('#toast'), await pg.inner_text('#toast'))
        await pg.evaluate("() => { const td = editor.querySelector('figure.tbl[data-dl] td'); const r = document.createRange(); r.selectNodeContents(td); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }"); await pg.wait_for_timeout(300)
        await pg.click('#tblBar [data-t=dlun]'); await pg.wait_for_timeout(300)
        check('…Unlink lets it go and keeps it as it is', await pg.evaluate("() => editor.querySelectorAll('figure.tbl[data-dl]').length === 1 && editor.querySelectorAll('figure.tbl').length === 2"))
        await pg.evaluate("() => { const td = editor.querySelector('td'); const r = document.createRange(); r.selectNodeContents(td); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }"); await pg.wait_for_timeout(300)
        check('an ordinary table’s toolbar doesn’t offer them', await pg.locator('#tblBar [data-t=dlup]:visible').count() == 0)
        await pg.click('#editor .dnum'); await pg.wait_for_timeout(200)
        t = await pg.inner_text('#toast')
        check('clicking a number says where it comes from', 'From “Defence spending”: latest value, Poland.' in t, t)
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(300)
        check('…and Unlink turns it into plain text', await pg.evaluate("() => !editor.querySelector('.dnum') && editor.querySelector('p').textContent.includes('5.2% of GDP')"))

        # editing a linked figure by hand lets it go
        await pg.evaluate("() => { const f = editor.querySelector('figure.fig[data-dl]'); openSpecEditor(P.assets[f.querySelector('img').dataset.asset].spec, f); }"); await pg.wait_for_timeout(800)
        await pg.evaluate("() => $('#chOk').click()"); await pg.wait_for_timeout(1800)
        r = await pg.evaluate("() => ({ n: editor.querySelectorAll('figure.fig[data-dl]').length, t: $('#toast').textContent })")
        check('a linked figure edited by hand stops following the data, and says so', r['n'] == 0 and 'no longer follows the dataset' in r['t'], r)

        # save, reopen, export
        await pg.evaluate("() => { refreshFromData({ quiet: true }); }")
        await pg.evaluate("() => { const td = editor.querySelector('figure.tbl td'); const r = document.createRange(); r.selectNodeContents(editor.querySelector('p')); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); }")
        await pg.evaluate("() => { dataSel = P.dashboards[0].id; openDesk('data'); }"); await pg.wait_for_timeout(800)
        await pg.click('#dbGrid .tt-stat [data-tact=ins]'); await pg.wait_for_timeout(500)
        saved = await pg.evaluate("() => { syncEditor(); return projectJSON(); }")
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'x.json'); }", saved); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ links: editor.querySelectorAll('[data-dl]').length, num: editor.querySelector('.dnum') && editor.querySelector('.dnum').getAttribute('contenteditable') })")
        check('linked tables and numbers survive saving and reopening', r['links'] == 2 and r['num'] == 'false', r)
        await pg.evaluate("() => { P.datasets[0].rows.find(r => r[0] === '2025')[1] = '5.5'; }")
        await pg.evaluate("() => refreshFromData()"); await pg.wait_for_timeout(600)
        check('…and still update after reopening', '5.5% of GDP' in await pg.inner_text('#editor'))
        # docx: the linked table is a Word table; the number is plain text
        async with pg.expect_download() as d: await pg.evaluate("() => { syncEditor(); return exportDocx(curDoc()); }")
        z = zipfile.ZipFile(await (await d.value).path()); xml = z.read('word/document.xml').decode('utf-8')
        check('Word export: the linked table is a real table and the number is ordinary text', xml.count('<w:tbl>') >= 2 and '5.5% of GDP' in xml and 'data-dl' not in xml)

        # pasting keeps the link; a hostile link is harmless
        await pg.evaluate("""() => { const dt = new DataTransfer(); const dl = editor.querySelector('.dnum').getAttribute('data-dl');
          dt.setData('text/html', '<p>Copied: <span class="dnum" data-dl="' + dl.replace(/"/g, '&quot;') + '" onclick="alert(1)">5.5% of GDP</span></p>');
          const r = document.createRange(); r.selectNodeContents(editor.lastElementChild); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r);
          editor.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }"""); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => { const all = editor.querySelectorAll('.dnum'); const n = all[all.length - 1]; return { k: all.length, on: n.getAttribute('onclick'), ce: n.getAttribute('contenteditable') }; }")
        check('pasting a linked number keeps the link, and nothing else', r['k'] == 2 and r['on'] is None and r['ce'] == 'false', r)
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p>x <span class="dnum" data-dl="{&quot;type&quot;:&quot;stat&quot;,&quot;ds&quot;:&quot;ds1&quot;,&quot;col&quot;:&quot;a&quot;,&quot;prefix&quot;:&quot;<img src=x onerror=alert(1)>&quot;}">1</span> <span class="dnum" data-dl="not json">2</span></p><figure class="tbl" data-dl="{&quot;type&quot;:&quot;evil&quot;}"><table><tbody><tr><td>z</td></tr></tbody></table></figure>'}],
                          'datasets': [{'id': 'ds1', 'name': 'D', 'cols': ['a'], 'rows': [['7']]}]})
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'bad.json'); }", bad); await pg.wait_for_timeout(700)
        await pg.evaluate("() => refreshFromData()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ img: !!editor.querySelector('img'), first: editor.querySelector('.dnum').textContent, t: $('#toast').textContent, tbl: editor.querySelector('td').textContent })")
        check('hostile links are shown as text and the rest are left alone', not r['img'] and '<img' in r['first'] and r['tbl'] == 'z' and 'could not be updated' in r['t'], r)

        # the pop-out desk inserts and updates in the main window
        await pg.evaluate("() => { editor.innerHTML = '<p>Total: </p>'; syncEditor(); const d = P.datasets[0]; const b = newDashboard(); b.tiles.push(Object.assign(newTile('stat', d), { col: 'a', agg: 'sum' })); dataSel = b.id; const t = editor.querySelector('p').firstChild; const r = document.createRange(); r.setStart(t, t.length); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); markDirty(); }")
        async with ctx.expect_page() as np: await pg.evaluate("() => popOut('desk', { dv: 'data' })")
        pop = await np.value; pop.on('pageerror', lambda e: errs.append('POP ' + str(e)))
        await pop.wait_for_function("() => typeof popReady !== 'undefined' && popReady", timeout=8000); await pop.wait_for_timeout(800)
        await pop.evaluate("() => { dataSel = P.dashboards[P.dashboards.length - 1].id; renderDesk(); }"); await pop.wait_for_timeout(800)
        await pop.click('#dbGrid .tt-stat [data-tact=ins]'); await pop.wait_for_timeout(800)
        check('Insert in a pop-out desk puts the number in the main window’s draft', await pg.evaluate("() => editor.querySelector('.dnum') && editor.querySelector('p').textContent === 'Total: 7'"), await pg.inner_text('#editor'))
        await pop.evaluate("() => { P.datasets[0].rows[0][0] = '9'; P.datasets[0].modified = nowISO(); markDirty(); refreshFromData(); }"); await pop.wait_for_timeout(1200)
        check('…and an edit plus Update there reach it too, in order', await pg.evaluate("() => editor.querySelector('.dnum').textContent === '9'"), await pg.inner_text('#editor'))
        await pop.close()
        await b.close()
    print('ERRS', [e for e in errs if 'favicon' not in e])
    return ok and not [e for e in errs if 'favicon' not in e]

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
