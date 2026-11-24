"""1.6: what's new after an update, send feedback, the opt-in update check (mocked GitHub), screen-only
text size, typeface and spacing, the refreshed tour, and the lighter sidebar."""
import asyncio, json, sys, urllib.parse
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    latest = {'tag': 'v1.7.0'}; calls = []
    async def gh(r):
        calls.append(r.request.url)
        await r.fulfill(status=200, content_type='application/json', body=json.dumps({'tag_name': latest['tag']}))
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        async def page(prefs, raw=False):
            ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
            if raw is False: await ctx.add_init_script(f"localStorage.setItem('commonplace.prefs', {json.dumps(json.dumps(prefs))})")
            await ctx.route('https://api.github.com/repos/gmichaelrapp/anabasis/releases/latest', gh)
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
            await pg.goto(URL); await pg.wait_for_timeout(1600); return ctx, pg

        # ---- what's new
        ctx, pg = await page({'startHome': False, 'toured': True, 'seenVersion': '1.5.0'})
        await pg.wait_for_function("() => $('#wnDlg').open", timeout=8000)
        r = await pg.evaluate("() => ({ open: $('#wnDlg').open, t: $('#wnTitle').textContent, items: $$('#wnBody li').length, h: $$('#wnBody h4').map(h => h.textContent), seen: PREFS.seenVersion })")
        check('after an update, What’s new opens once with this version’s changes', r['open'] and r['t'] == 'What’s new in Anabasis 1.7.0' and r['items'] == 10 and r['seen'] == '1.7.0', r)
        await pg.click('#wnOk'); await pg.evaluate("() => wnCheck()"); await pg.wait_for_timeout(1200)
        check('…and not again', not await pg.evaluate("() => $('#wnDlg').open"))
        await pg.evaluate("() => { fillHelpTips(); $('#helpDlg').showModal(); }"); await pg.click('#helpNew'); await pg.wait_for_timeout(150)
        check('Help shows it any time', await pg.evaluate("() => $('#wnDlg').open && $$('#wnBody li').length >= 5"))
        await pg.click('#wnOk'); await ctx.close()
        ctx, pg = await page({'startHome': False, 'toured': True})
        try: await pg.wait_for_function("() => $('#wnDlg').open", timeout=8000)
        except Exception: pass
        check('someone updating from before 1.6 (no record) sees it too', await pg.evaluate("() => $('#wnDlg').open && $$('#wnBody li').length === 10"))
        await ctx.close()
        ctx, pg = await page(None, raw=True)
        r = await pg.evaluate("() => ({ wn: $('#wnDlg').open, tour: !$('#tour').classList.contains('hidden'), seen: PREFS.seenVersion })")
        check('a first visit gets the tour, not What’s new', r == {'wn': False, 'tour': True, 'seen': '1.7.0'}, r)

        # ---- the tour
        steps = []
        for _ in range(14):
            if await pg.evaluate("() => $('#tour').classList.contains('hidden')"): break
            steps.append(await pg.inner_text('#tourTitle')); await pg.click('#tourNext'); await pg.wait_for_timeout(260)
        # a step whose button has moved into the ⋯ menu (narrower fonts or window) is skipped, so allow for one
        check('the tour covers the research desk, marks and citation styles, and finishes', 9 <= len(steps) <= 10 and steps[0] == 'Welcome to Anabasis' and steps[-1] == 'Save the project file' and 'The research desk' in steps and 'Mark what matters' in steps and '55 citation styles' in steps, steps)
        await ctx.close()

        ctx, pg = await page({'startHome': False, 'toured': True, 'seenVersion': '1.7.0'})
        # ---- send feedback
        await pg.evaluate("() => { fillHelpTips(); $('#helpDlg').showModal(); }"); await pg.click('#helpFeedback'); await pg.wait_for_timeout(150)
        env = await pg.inner_text('#fbEnv')
        check('feedback fills in the version, browser and device', env.startswith('Anabasis 1.7.0') and 'Chrome' in env and 'window 1440×900' in env, env)
        await pg.select_option('#fbKind', 'idea'); await pg.fill('#fbMsg', 'A word-count widget for each part\nwould help.')
        await pg.evaluate("() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); }; }")
        await pg.evaluate("() => { window.__clip = ''; navigator.clipboard.writeText = async t => { window.__clip = t; }; }")
        await pg.click('#fbCopy'); await pg.wait_for_timeout(100)
        clip = await pg.evaluate("() => window.__clip")
        check('Copy gives a report to paste into an email', clip.startswith('Idea: A word-count widget for each part') and '- Anabasis 1.7.0' in clip, clip[:120])
        await pg.click('#fbGitHub'); await pg.wait_for_timeout(100)
        u = (await pg.evaluate("() => window.__opened"))[0]
        q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        check('Open on GitHub pre-fills an issue with a label', u.startswith('https://github.com/gmichaelrapp/anabasis/issues/new?') and q['title'][0] == 'Idea: A word-count widget for each part' and q['labels'][0] == 'enhancement' and 'would help.' in q['body'][0], u[:160])
        title = await pg.evaluate("() => P.title")
        check('…and carries nothing from the project', title not in u and 'Welcome' not in u)

        # ---- update check: never unless asked
        await pg.wait_for_timeout(300)
        check('no update check unless it’s switched on', not calls)
        latest['tag'] = 'v1.7.0'
        await pg.evaluate("() => updCheck(true)"); await pg.wait_for_timeout(300)
        check('Check for a newer version says when you’re current', 'newest version' in await pg.inner_text('#toast') and await pg.evaluate("() => $('#updBar').classList.contains('hidden')"))
        latest['tag'] = 'v1.7.2'
        await pg.evaluate("() => { PREFS.updCheck = true; PREFS.updAt = Date.now() - 8 * 864e5; updMaybe(); }"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ bar: !$('#updBar').classList.contains('hidden'), msg: $('#updMsg').textContent })")
        check('switched on, a weekly check announces a newer release', r['bar'] and '1.7.2 is out' in r['msg'], r)
        n = len(calls)
        await pg.evaluate("() => updMaybe()"); await pg.wait_for_timeout(200)
        check('…and asks at most once a week', len(calls) == n)
        await pg.click('#updBar [data-ub=no]')
        await pg.evaluate("() => $('#btnSettings').click()"); await pg.wait_for_timeout(200)
        check('the setting is in Settings for a downloaded copy', await pg.evaluate("() => !$('#stUpdRow').classList.contains('hidden') && $('#stUpd').checked"))
        await pg.click('#stCancel') if await pg.locator('#stCancel').count() else await pg.evaluate("() => $('#settingsDlg').close()")

        # ---- screen text: size, typeface, spacing; exports and print untouched
        base = await pg.evaluate("() => ({ fs: parseFloat(getComputedStyle($('#page')).fontSize), lh: getComputedStyle($('#page')).lineHeight, sp: curDoc().layout.spacing })")
        check('comfortable spacing on screen by default, whatever Page setup says', base['sp'] == '2' and abs(float(base['lh'].replace('px', '')) / base['fs'] - 1.7) < 0.02, base)
        await pg.evaluate("() => $('#btnSettings').click()"); await pg.wait_for_timeout(200)
        await pg.select_option('#stScrSize', '130'); await pg.select_option('#stScrFont', 'sans'); await pg.select_option('#stScrLh', 'page')
        await pg.click('#stOk'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => { const cs = getComputedStyle($('#page')); return { fs: parseFloat(cs.fontSize), lh: parseFloat(cs.lineHeight), ff: cs.fontFamily, layout: JSON.stringify(curDoc().layout), prefs: [PREFS.scrSize, PREFS.scrFont, PREFS.scrLh] }; }")
        check('Settings changes the size, typeface and spacing of the page on screen', abs(r['fs'] / base['fs'] - 1.3) < 0.02 and 'Atkinson' in r['ff'] and abs(r['lh'] / r['fs'] - 2) < 0.02 and r['prefs'] == [130, 'sans', 'page'], r)
        check('…without touching the document’s Page setup', json.loads(r['layout'])['size'] == '12' and json.loads(r['layout'])['font'] == 'book')
        await pg.emulate_media(media='print')
        r = await pg.evaluate("() => { const cs = getComputedStyle($('#page')); return { fs: parseFloat(cs.fontSize), ff: cs.fontFamily }; }")
        check('…or what prints', abs(r['fs'] - 16) < 0.1 and 'Atkinson' not in r['ff'], r)
        await pg.emulate_media(media='screen')
        html = await pg.evaluate("() => { const d = curDoc(); const x = buildExport(d, 'html'); return x.body + x.out; }")
        check('…or what exports', 'scr-' not in html and 'Atkinson' not in html)
        await pg.evaluate("() => { PREFS.scrSize = 100; PREFS.scrFont = ''; PREFS.scrLh = ''; applyScreen(); }")

        # ---- the lighter sidebar keeps every tool one click away
        r = await pg.evaluate("() => ['btnPlan', 'btnManuscript', 'btnTemplates', 'btnImportDocx', 'btnRel'].map(id => { const e = $('#' + id), b = e.getBoundingClientRect(); return b.width > 0 && b.height >= 24 && !!e.title; })")
        check('sidebar tools: Plan, Compile, Templates, Import Word, Relationships', all(r), r)
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
