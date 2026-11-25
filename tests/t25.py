"""Accessibility audit of the app itself with axe-core (WCAG 2.1 A/AA), light and dark themes."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL = os.environ.get('ANABASIS_URL', URL)
AXE = os.environ.get('AXE_PATH', AXE)
VIEWS = [
    ('editor', "if (typeof splitClose === 'function' && SPLIT.on) splitClose(); ghBarHide(); $('#updBar').classList.add('hidden'); if (curDocId !== P.docs[0].id) openDoc(P.docs[0].id); switchTab('docs')"),
    ('notes tab', "switchTab('notes')"),
    ('sources tab', "switchTab('sources')"),
    ('outline tab', "switchTab('outline')"),
    ('research tab', "(() => { if (!P.threads.length) { const p = editor.querySelector('p'); const t = [...p.childNodes].find(n => n.nodeType === 3 && n.data.length > 30); const r = document.createRange(); r.setStart(t, 0); r.setEnd(t, 25); const th = newThread('Logistics'); rmApply(r, 'th', { ref: th.id }); const r2 = document.createRange(); const t2 = [...editor.querySelectorAll('p')][2].firstChild; r2.setStart(t2, 0); r2.setEnd(t2, 20); const id = uid('cl'); rmApply(r2, 'cl', { pid: id }); P.claims.push({ id, status: 'need', note: '', checkedText: '', checkedAt: '', created: nowISO(), modified: nowISO() }); const r3 = document.createRange(); const t3 = [...editor.querySelectorAll('p')][3].firstChild; r3.setStart(t3, 0); r3.setEnd(t3, 9); const rv = uid('rv'); rmApply(r3, 'rv', { pid: rv }); P.reviewKeys.push({ id: rv, reason: 'Rewrite', due: todayISO(), note: '', done: false, doneAt: '', created: nowISO() }); plNewItem('', null, { type: 'question', title: 'Open question', status: 'open' }); } switchTab('research'); rmRefresh(); })()"),
    ('mark menu', "openMarkMenu()"),
    ('desk threads', "$('#markMenu').classList.remove('open'); openDesk('threads')"),
    ('desk claims', "openDesk('claims')"),
    ('desk grid', "openDesk('grid')"),
    ('desk review', "openDesk('review')"),
    ('desk questions', "openDesk('questions')"),
    ('journal design', "plNewItem('', null, { type: 'question', title: 'Why?', status: 'open' }); openJournal('design')"),
    ('journal hypotheses', "P.journal.hypotheses.push({ id: 'h1', text: 'A guess', rationale: '', status: 'mixed', questionId: '', links: [{ k: 'src', id: P.sources[0].id, stance: 'for' }], history: [{ at: nowISO(), from: 'untested', to: 'mixed', note: 'x' }], created: nowISO(), modified: nowISO() }); openJournal('hyp')"),
    ('journal log', "jLog('found', 'Found the diary.', { tags: ['archive'] }); jLog('auto', 'H1 mixed'); openJournal('log')"),
    ('journal this week', "jLog('next', 'Order the diary'); jLog('found', 'A thing'); openJournal('week')"),
    ('journal design templates', "openJournal('design')"),
    ('journal searches', "P.journal.searches.push({ id: 'js1', date: todayISO(), where: 'JSTOR', terms: 'x', filters: '', results: 4, kept: 1, notes: '', created: nowISO() }); openJournal('search')"),
    ('desk about', "openDesk('about'); $('#abQ').value = 'Tuchman'; $('#abForm').requestSubmit()"),
    ('thread dialog', "closeDesk(); openDoc(curDocId); const r = document.createRange(); r.selectNodeContents(editor.querySelector('p')); getSelection().removeAllRanges(); getSelection().addRange(r); openThreadPick()"),
    ('review dialog', "$('#thDlg').close(); const r = document.createRange(); r.selectNodeContents(editor.querySelector('p')); getSelection().removeAllRanges(); getSelection().addRange(r); openReviewKey()"),
    ('question dialog', "$('#rvDlg').close(); openQuestionLink(true)"),
    ('marked passage popover', "$('#qDlg').close(); const s = editor.querySelector('.rm[data-k=cl]'); showRmPop(rmMarksAt(s), s)"),
    ('toolbar more menu', "closeRmPop(); TB_PB.open()"),
    ('customize toolbar dialog', "$('#tbMore').classList.remove('open'); openTbCustom()"),
    ('shortcuts dialog', "$('#tbcDlg').close(); openKeys()"),
    ('home', "$('#keysDlg').close(); openHome()"),
    ('help', "closeHome(); $('#helpDlg').showModal()"),
    ('chart dialog', "$('#helpDlg').close(); openChart()"),
    ('map dialog', "$('#chDlg').close(); openMap()"),
    ('checkpoints', "$('#mpDlg').close(); openCheckpoints()"),
    ('find all', "$('#cpDlg').close(); openFindAll()"),
    ('promo', "$('#frDlg').close(); openPromo()"),
    ('tour', "$('#pkDlg').close(); startTour()"),
    ('getting-started tips', "closeDesk(); P.goal.kind = 'article'; addDoc(newDoc('Empty'))"),
    ('newer-backup notice', "ghBarShow({ sha: 'x', at: new Date().toISOString() })"),
    ('what’s new', "ghBarHide(); showWhatsNew('1.4.0')"),
    ('send feedback', "$('#wnDlg').close(); openFeedback()"),
    ('data: empty', "$('#updBar').classList.add('hidden'); openDesk('data')"),
    ('data: dashboard', "const ex = $$('#deskBody button').find(b => /Try an example/.test(b.textContent)); if (ex) ex.click(); else { dataSel = P.dashboards[0].id; renderDesk(); }"),
    ('data: dataset', "dataSel = P.datasets[0].id; renderDesk()"),
    ('data: tile editor', "dataSel = P.dashboards[0].id; renderDesk(); editTile(P.dashboards[0], P.dashboards[0].tiles[2])"),
    ('data: import dialog', "$('#tlCancel').click(); importDataset()"),
    ('split: notes', "$('#dsImpCancel').click(); closeDesk(); splitOpen('notes')"),
    ('split: research desk', "splitOpen('desk')"),
    ('split: a document', "splitOpen('doc')"),
    ('data in the writing', "splitClose(); closeDesk(); const d = P.datasets[0]; dataInsert(Object.assign(newTile('table', d), { title: d.name })); const st = P.dashboards[0].tiles.find(x => x.type === 'stat'); if (st) dataInsert(st); const td = editor.querySelector('figure.tbl[data-dl] td'); if (td) { const r = document.createRange(); r.selectNodeContents(td); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }"),
    ('equations in the writing', "$('#eqDlg').close(); closeDesk(); editor.insertAdjacentHTML('beforeend', '<p>Energy ' + eqHTML('E = mc^2', false) + ' here.</p>' + eqHTML('\\\\frac{a}{b}', true, true)); hydrateImages(); renumberFigures();"),
    ('equation box', "openEq(); $('#eqTex').value = '\\\\sqrt{x^2 + 1}'; eqPreview();"),
    ('cross-reference box', "$('#eqDlg').close(); openXref(); $('#xrQ').value = ''; xrPick = 1; xrRender();"),
    ('credit & permission box', "$('#xrDlg').close(); editor.insertAdjacentHTML('beforeend', figHTML(addAsset('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'x', 1, 1), 'A test figure')); hydrateImages(); renumberFigures(); openCredit(editor.querySelector('figure.fig:last-of-type') || $$('#editor figure.fig').pop());"),
    ('permissions log', "$('#crDlg').close(); openPerms();"),
    ('check links', "$('#permDlg').close(); P.sources.push({ id: 'axe1', csl: { type: 'webpage', title: 'A page', URL: 'https://example.org/a' }, lc: { at: '2026-01-01', url: 'https://web.archive.org/web/20240101000000/https://example.org/a', ts: '20240101000000', st: '404' }, created: nowISO() }); openLinks();"),
    ('manuscript format box', "$('#lkDlg').close(); openMsf(curDoc());"),
    ('insert menu', "$('#msfDlg').close(); openInsertMenu(false);"),
    ('export menu (grouped)', "closePop(); $('#exportMenu').classList.add('open');"),
    ('sources tools menu', "$('#exportMenu').classList.remove('open'); switchTab('sources'); $('#srcMoreMenu').classList.add('open');"),
    ('send a copy', "$('#srcMoreMenu').classList.remove('open'); openSendCopy();"),
    ('take changes back', "$('#scDlg').close(); TB = { T: JSON.parse(JSON.stringify(P)), send: null, name: 'x.json', who: 'Dana' }; TB.T.docs[0].html = TB.T.docs[0].html.replace(/<p>/, '<p>Changed. '); $('#tkWho').value = 'Dana'; tbPrepare(); $('#tkDlg').showModal();"),
    ('socrates', "$('#tkDlg').close(); openSocrates({ about: 'the blockade caused the famine' });"),
    ('newer-version notice', "$('#socDlg').close(); $('#tkDlg').close(); $('#msfDlg').close(); $('#eqDlg').close(); $('#fbDlg').close(); clearTimeout(toastT); $('#toast').classList.remove('show'); $('#updMsg').textContent = 'Anabasis 9.9 is out.'; $('#updBar').classList.remove('hidden')"),
]
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={'width': 1440, 'height': 900})
        await pg.add_init_script("localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg.on('console', lambda m: print('VIEW SCRIPT WARNING', m.text) if m.type == 'warning' else None)
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
        # the same audit on a phone-sized screen
        await pg.evaluate("endTour && endTour(); document.documentElement.dataset.theme='light'")
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(400)
        for name, js in [('phone editor', "closeHome && homeOn && closeHome(); openDoc(curDocId)"), ('phone toolbar menu', "TB_PB.open()"),
                         ('phone document menu', "$('#tbMore').classList.remove('open'); DOC_PB.open()"), ('phone top menu', "$('#docMore').classList.remove('open'); TOP_PB.open()"),
                         ('phone drawer', "$('#topMore').classList.remove('open'); document.body.classList.add('side-open')"), ('phone settings dialog', "document.body.classList.remove('side-open'); openSettings()")]:
            await pg.evaluate(f"(()=>{{ try {{ {js} }} catch(e) {{ console.warn(e) }} }})()"); await pg.wait_for_timeout(350)
            ctx = "document.querySelector('dialog[open]') || document" if 'dialog' in name else "document"
            res = await pg.evaluate(f"""axe.run({ctx}, {{ runOnly: {{ type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] }}, resultTypes: ['violations'] }})
                .then(r => r.violations.map(v => ({{ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, eg: v.nodes.slice(0,3).map(n => n.target.join(' ') + ' :: ' + (n.failureSummary||'').split('\\n').slice(1,2).join('')) }})))""")
            for v in res:
                total.setdefault((v['id'], v['help']), []).append(f"phone/{name}: {v['n']} e.g. {v['eg'][:2]}")
        for (rid, hlp), where in sorted(total.items()):
            print(f'== {rid}: {hlp}')
            for w in where[:6]: print('   ', w[:400])
        print('RULES FAILING', len(total))
        await b.close()
        sys.exit(1 if total else 0)
asyncio.run(main())
