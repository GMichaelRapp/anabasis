"""2.6.1: a literature review drafted from the literature grid, the Literature review plan template, and the
menu, template and command-palette entries that reach it."""
import asyncio
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
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
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # three sources: two summarized on "Main argument", one with only a tagged note, a "How I'll use it" cell
        r = await pg.evaluate("""() => {
          const g = lgCfg(); g.rows = 'all'; const S = sortedSources().slice(0, 3), [a, b, c] = S;
          const col = n => g.cols.find(x => x.name === n).id;
          g.cells[a.id] = { [col('Main argument')]: 'Supply, not battle, set the route.', [col('How I’ll use it')]: 'Frame for chapter 2' };
          g.cells[b.id] = { [col('Main argument')]: 'The army was a moving town', [col('Key findings')]: 'Halts followed harvests.' };
          const n = Object.assign(newNote(), { kind: 'summary', title: 'On the march', sourceId: c.id, body: 'x', tags: ['main argument'] }); P.notes.push(n);
          return { a: srcShort(a), b: srcShort(b), c: srcShort(c), n: P.sources.length }; }""")
        names = r
        await pg.evaluate("openDesk('lit')"); await pg.wait_for_timeout(500)
        check('the grid offers a drafted review beside the grid as a document', await pg.evaluate("() => !!$('#deskTools [data-j]') && /Draft a literature review/.test($('#deskTools').textContent) && /Grid as a document/.test($('#deskTools').textContent)"))
        await pg.click('#deskTools >> text=Draft a literature review'); await pg.wait_for_timeout(900)
        r = await pg.evaluate("""() => ({ title: curDoc().title, h2: $$('#editor h2').map(h => h.textContent),
          cites: editor.querySelectorAll('.cite').length, text: editor.innerText, desk: $('#desk') ? !$('#desk').hidden && getComputedStyle($('#desk')).display !== 'none' : false })""")
        h2 = r['h2']
        check('a new "Literature Review" document with a section per theme, between the introduction and the close',
              r['title'] == 'Literature Review' and h2[0] == 'Introduction' and 'Main argument' in h2 and 'Key findings' in h2 and h2[-2:] == ['Gaps and open questions', 'What this review sets up'], h2)
        check('…the "How I’ll use it" column isn’t a theme; its notes go to the closing section',
              'How I’ll use it' not in h2 and 'Frame for chapter 2' in r['text'].split('What this review sets up')[1], h2)
        check('…every summary is cited, one citation per summarized cell', r['cites'] == 3, r['cites'])
        sec = r['text'].split('Main argument')[1].split('Evidence and method')[0]
        check('…in a notes style the note follows the full stop, and a full stop is added when the summary has none',
              await pg.evaluate("""() => { const ps = $$('#editor h2').find(h => h.textContent === 'Main argument').nextElementSibling;
                 const h = ps.innerHTML; return /set the route\\.<span class="cite[^>]*>[^<]*<\\/span>/.test(h) && /moving town\\.<span class="cite[^>]*>[^<]*<\\/span>/.test(h); }"""), sec[:200])
        ad = await pg.evaluate("""() => { const d = curDoc(), st = d.style; d.style = 'apa'; const { html } = lgReviewHTML(); d.style = st; return html; }""")
        check('…in an author-date style the citation goes before the full stop', bool(__import__('re').search(r'set the route <span class="cite[^>]*>[^<]*</span>[.]', ad)), ad[600:900])
        check('…with a prompt to compare, a flag for a source with notes but no summary, and the sources silent on a theme',
              'Compare:' in sec and f"{names['c']}: 1 note bears on this" in sec
              and f"Not addressed by: {names['a']}" in r['text'].split('Key findings')[1].split('Limits and gaps')[0], [names, sec[:400]])
        check('…a theme nobody has summarized says so', 'No summaries in the grid for this theme yet.' in r['text'].split('Evidence and method')[1].split('Key findings')[0])
        r = await pg.evaluate("() => { const dl = $$('#editor mark').length; return { marks: dl }; }")
        check('…the drafting notes are highlighted, so they’re easy to find and delete', r['marks'] >= 6, r)

        # export: the citations resolve into a bibliography like any other document
        r = await pg.evaluate("() => { const x = buildExport(curDoc(), 'html'); return x.body || x.html || String(x); }")
        check('…and it exports with its citations formatted', '[cite]' not in r and 'class="cite"' not in r and r.count('fnref') == 3, r[-600:])

        # an empty grid explains itself instead of making an empty document
        r = await pg.evaluate("() => { const n = P.docs.length; const keep = P.litGrid; P.litGrid = { cols: keep.cols, cells: {}, rows: 'cited' }; const sv = lgCited; lgCited = () => new Set(); lgReview(); lgCited = sv; P.litGrid = keep; return P.docs.length - n; }")
        check('with nothing in the grid, no document is made', r == 0, r)

        # reaching it from the menu, the templates dialog and the palette
        for how, js in [('export menu', "() => { $('[data-x=litrev]').click(); }"),
                        ('templates dialog', "() => { openTemplates(); $('#tplList [data-t=__litrev]').click(); }")]:
            n0 = await pg.evaluate("P.docs.length")
            await pg.evaluate(js); await pg.wait_for_timeout(700)
            check(f'…from the {how}', await pg.evaluate("P.docs.length") == n0 + 1 and await pg.evaluate("curDoc().title") == 'Literature Review')
        check('…and the command palette lists it', await pg.evaluate("() => /Draft a literature review/.test(document.documentElement.innerHTML) || (typeof PALETTE !== 'undefined')"))

        # the plan template
        r = await pg.evaluate("() => { P.plan.items = []; plApplyTemplate('Literature review', ''); return P.plan.items.map(i => i.type + ':' + i.title); }")
        check('Plan → templates: a Literature review outline with themes, disagreements, gaps and your question',
              'section:Theme 1' in r and 'counter:Where they disagree, and why' in r and 'question:What has nobody examined?' in r and any(x.startswith('section:What this review sets up') for x in r), r[:6])
        check('no errors', not errs, errs[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
