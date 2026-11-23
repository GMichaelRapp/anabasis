"""1.4: the research journal: research design, hypotheses tracked against evidence, the dated log,
the search log, the memo and appendix, saving, undo, search, and hostile journal data."""
import asyncio, json, os, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

MOD = 'Meta' if sys.platform == 'darwin' else 'Control'


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        # ---- reach it from the sidebar
        await pg.evaluate("() => switchTab('research')")
        await pg.click('#rsToday'); await pg.wait_for_timeout(300)
        check('Today’s entry opens the journal log with the cursor in the entry', await pg.evaluate("() => deskOn && deskView === 'journal' && PREFS.jSec === 'log' && document.activeElement && document.activeElement.id === 'jText'"))
        await pg.fill('#jText', 'Searched the regimental archive index for the 1916 war diary.')
        await pg.click('.j-kind:has-text("Did")'); await pg.fill('#jTags', 'Archive, war diary'); await pg.press('#jText', f'{MOD}+Enter'); await pg.wait_for_timeout(200)
        await pg.click('.j-kind:has-text("Dead end")'); await pg.fill('#jText', 'The diary for October is missing from the index.'); await pg.fill('#jTags', 'archive')
        sids = await pg.evaluate("() => P.sources.map(s => 'src:' + s.id)")
        await pg.select_option('#jLink', sids[0]); await pg.click('#jForm button.primary'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => P.journal.log.map(e => [e.kind, e.text.slice(0, 20), e.tags, e.links.length, e.date === todayISO()])")
        check('log entries saved with kind, tags (tidied), links and today’s date', r == [['did', 'Searched the regimen', ['archive', 'war diary'], 0, True], ['dead', 'The diary for Octobe', ['archive'], 1, True]], r)
        await pg.click('.j-filt button:has-text("Dead end")'); await pg.wait_for_timeout(150)
        check('log filters by kind', await pg.locator('.j-entry').count() == 1)
        await pg.click('.j-filt button:has-text("All")'); await pg.fill('#jQ', 'regimental'); await pg.wait_for_timeout(500)
        check('log search', await pg.locator('.j-entry').count() == 1)
        await pg.fill('#jQ', ''); await pg.wait_for_timeout(500)
        await pg.click('.j-entry:has-text("Searched") button:has-text("Edit")'); await pg.fill('.j-edit', 'Searched the regimental archive index for the 1916 and 1917 war diaries.'); await pg.click('.j-save'); await pg.wait_for_timeout(150)
        check('log entries can be edited', await pg.evaluate("() => P.journal.log[0].text.includes('1917')"))
        await pg.click('.j-entry:has-text("October") button[aria-label="Delete entry"]'); await pg.wait_for_timeout(150)
        gone = await pg.evaluate("() => P.journal.log.length === 1")
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(200)
        check('deleting an entry can be undone', gone and await pg.evaluate("() => P.journal.log.length === 2"))

        # ---- research design
        await pg.click('.j-side li:has-text("Research design")'); await pg.wait_for_timeout(150)
        await pg.fill('#jd-purpose', 'Why the offensive stalled.'); await pg.press('#jd-purpose', 'Tab')
        await pg.fill('#jd-methods', 'War diaries, compared week by week.\n\nInterviews with descendants.'); await pg.press('#jd-methods', 'Tab')
        check('design fields save', await pg.evaluate("() => P.journal.design.purpose === 'Why the offensive stalled.' && P.journal.design.methods.includes('descendants')"))
        await pg.evaluate("() => { plNewItem('', null, { type: 'question', title: 'Why did the October attack fail?', status: 'open' }); renderDesk(); }")
        await pg.check('[data-qdone]'); await pg.wait_for_timeout(150)
        check('answering a question there marks it in Plan and records it in the log', await pg.evaluate("() => qItems()[0].status === 'answered' && P.journal.log.some(e => e.kind === 'auto' && e.text.startsWith('Question answered'))"))

        # ---- hypotheses
        await pg.click('.j-side li:has-text("Hypotheses")'); await pg.click('.j-head button:has-text("Hypothesis")'); await pg.wait_for_timeout(200)
        await pg.fill('.h-card textarea[data-hf=text]', 'The attack failed for lack of artillery shells.'); await pg.press('.h-card textarea[data-hf=text]', 'Tab')
        await pg.select_option('.h-card select[data-hf=questionId]', index=1); await pg.wait_for_timeout(150)
        await pg.select_option('.h-card .h-add select:not([data-hstance])', sids[0]); await pg.select_option('.h-card [data-hstance]', 'for'); await pg.click('.h-card [data-hadd]'); await pg.wait_for_timeout(150)
        await pg.select_option('.h-card .h-add select:not([data-hstance])', sids[1]); await pg.select_option('.h-card [data-hstance]', 'against'); await pg.click('.h-card [data-hadd]'); await pg.wait_for_timeout(150)
        r = await pg.evaluate("() => { const h = P.journal.hypotheses[0]; return { t: h.text, q: !!h.questionId, l: h.links.map(l => l.k + ':' + l.stance), tally: $('.h-tally').textContent }; }")
        check('a hypothesis links to a question and to evidence for and against', r['t'].startswith('The attack') and r['q'] and r['l'] == ['src:for', 'src:against'] and r['tally'].startswith('1 for · 1 against'), r)
        await pg.click('.h-chip:has-text("Weakened")'); await pg.wait_for_timeout(200)
        await pg.fill('#askInput', 'Shell returns show stocks were adequate.'); await pg.click('#askOk'); await pg.wait_for_timeout(250)
        r = await pg.evaluate("() => { const h = P.journal.hypotheses[0]; return { st: h.status, hist: h.history.map(x => x.from + '>' + x.to + ':' + x.note), log: P.journal.log.filter(e => e.kind === 'auto').map(e => e.text).pop() }; }")
        check('changing status asks why, dates it, and logs it', r['st'] == 'weakened' and r['hist'] == ['untested>weakened:Shell returns show stocks were adequate.'] and r['log'].startswith('H1 weakened (was untested)'), r)
        await pg.click('.h-chip:has-text("Refuted")'); await pg.wait_for_timeout(200); await pg.click('#askCancel'); await pg.wait_for_timeout(200)
        check('cancelling a status change leaves the status alone', await pg.evaluate("() => P.journal.hypotheses[0].status === 'weakened' && P.journal.hypotheses[0].history.length === 1"))

        # ---- search log
        await pg.click('.j-side li:has-text("Searches")'); await pg.wait_for_timeout(150)
        await pg.fill('#jsWhere', 'National Archives catalog'); await pg.fill('#jsTerms', '"war diary" 1916'); await pg.fill('#jsRes', '41'); await pg.fill('#jsKept', '3'); await pg.click('#jsForm button'); await pg.wait_for_timeout(150)
        await pg.fill('.j-stable input[data-sf=notes]', 'Mostly duplicates'); await pg.press('.j-stable input[data-sf=notes]', 'Tab')
        r = await pg.evaluate("() => P.journal.searches[0]")
        check('searches log with counts and notes', r['where'] == 'National Archives catalog' and r['results'] == 41 and r['kept'] == 3 and r['notes'] == 'Mostly duplicates', r)
        async with pg.expect_download() as d: await pg.click('#deskTools button:has-text("CSV")')
        csv = open(await (await d.value).path(), encoding='utf-8-sig', newline='').read()
        check('search log exports as CSV', csv.startswith('"Date","Where","Terms"') and '"41","3","Mostly duplicates"' in csv, csv[:200])

        # ---- the memo and the appendix
        await pg.click('#deskTools button:has-text("Research memo")'); await pg.wait_for_timeout(500)
        memo = await pg.evaluate("() => ({ t: curDoc().title, h: [...editor.querySelectorAll('h2')].map(h => h.textContent), txt: editor.innerText })")
        check('research memo document', memo['t'].startswith('Research memo') and memo['h'][:3] == ['Purpose', 'Research questions', 'Hypotheses'] and 'Search log' in memo['h'] and 'Weakened since' in memo['txt'] and 'Against:' in memo['txt'], memo['h'])
        await pg.evaluate("() => openJournal()"); await pg.click('#deskTools button:has-text("Methods appendix")'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ t: curDoc().title, role: curDoc().role, h: [...editor.querySelectorAll('h2')].map(h => h.textContent), tbl: !!editor.querySelector('figure.tbl table') })")
        check('methods appendix as back matter with the search table', r == {'t': 'Appendix: Methods and Sources', 'role': 'back', 'h': ['Approach and methods', 'Search log'], 'tbl': True}, r)

        # ---- found by Everything about…, kept by saving
        await pg.evaluate("() => { openDesk('about'); $('#abQ').value = 'artillery'; $('#abForm').requestSubmit(); }"); await pg.wait_for_timeout(300)
        check('Everything about… searches the journal', 'Journal' in await pg.inner_text('#deskBody') and 'H1 · Weakened' in await pg.inner_text('#deskBody'))
        saved = await pg.evaluate("() => projectJSON()")
        await pg.evaluate("t => loadProjectText(t, null, 'j.json')", saved); await pg.wait_for_timeout(700)
        r = await pg.evaluate("() => ({ log: P.journal.log.length, h: P.journal.hypotheses[0].status, hist: P.journal.hypotheses[0].history.length, s: P.journal.searches.length, d: P.journal.design.purpose })")
        check('the journal survives save and reopen', r == {'log': 4, 'h': 'weakened', 'hist': 1, 's': 1, 'd': 'Why the offensive stalled.'}, r)
        check('the sidebar summarizes it', 'Journal' in await pg.inner_text('#rsJournal') and '1 hypothesis: 1 weakened' in await pg.inner_text('#rsJournal'))

        # ---- examples ship with a journal
        await pg.evaluate("() => { dirtyFile = false; openStarter('thesis'); }"); await pg.wait_for_timeout(700)
        r = await pg.evaluate("() => ({ d: !!P.journal.design.methods, h: P.journal.hypotheses.map(h => h.status + ':' + h.links.length + ':' + (h.questionId ? 'q' : '-')), l: P.journal.log.length, s: P.journal.searches.length, dangling: P.journal.hypotheses.some(h => h.links.some(l => !l.id)) })")
        check('the thesis example has a design, linked hypotheses, a log and searches', r['d'] and r['h'] == ['supported:3:q', 'mixed:2:-'] and r['l'] == 5 and r['s'] == 2 and not r['dangling'], r)

        # ---- hostile journal data is tidied, not trusted
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p>x</p>'}],
                          'journal': {'design': {'purpose': {'x': 1}, 'methods': '<img src=x onerror=alert(1)>'}, 'hypotheses': [{'id': 'h1', 'text': 5, 'status': 'proven', 'links': [{'k': 'evil', 'id': 'x'}, {'k': 'src', 'id': 's', 'stance': 'maybe'}], 'history': 'no'}],
                                      'log': [{'id': 'j1', 'date': 'yesterday', 'kind': 'hack', 'text': 'ok', 'tags': ['a', {'b': 1}]}, {'id': 'j2', 'text': ''}], 'searches': [{'id': 's1', 'results': '-5', 'kept': 'many'}]}})
        await pg.evaluate("t => loadProjectText(t, null, 'bad.json')", bad); await pg.wait_for_timeout(700)
        r = await pg.evaluate("() => P.journal")
        h = r['hypotheses'][0]; e = r['log']
        check('hostile journal data is cleaned', r['design']['purpose'] == '' and h['status'] == 'untested' and h['text'] == '5' and h['links'] == [{'k': 'src', 'id': 's', 'stance': ''}] and h['history'] == [] and len(e) == 1 and e[0]['kind'] == 'did' and len(e[0]['date']) == 10 and e[0]['tags'] == ['a'] and r['searches'][0]['results'] == 0 and r['searches'][0]['kept'] == '', r)
        await pg.evaluate("() => { openJournal('design'); }"); await pg.wait_for_timeout(200)
        check('…and shown as text, never as markup', await pg.evaluate("() => $('#jd-methods').value.startsWith('<img') && !document.querySelector('.j-main img')"))
        for sec in ['hyp', 'log', 'search']:
            await pg.evaluate(f"() => openJournal('{sec}')"); await pg.wait_for_timeout(120)
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
