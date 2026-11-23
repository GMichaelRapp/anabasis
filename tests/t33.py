"""1.5: picking up on another device from a GitHub backup (with a mocked GitHub), the weekly review and
next steps, research design templates, the fact-check sheet's checker and page numbers, and the
getting-started tips."""
import asyncio, base64, json, re, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

PREFS = "delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true}))"


class Hub:
    """A pretend GitHub: one private repository with per-path commit histories."""
    def __init__(self):
        self.files = {}   # path -> [ {sha, at, text, msg} ] newest first
        self.n = 0
        self.pending = {}
    def add(self, path, text, at, msg='Back up'):
        self.n += 1; sha = f'c{self.n}'
        self.files.setdefault(path, []).insert(0, {'sha': sha, 'at': at, 'text': text, 'msg': msg}); return sha
    def head_all(self):
        best = None
        for h in self.files.values():
            if h and (not best or h[0]['at'] > best['at']): best = h[0]
        return best
    async def route(self, r):
        u = r.request.url; m = r.request.method; body = r.request.post_data
        j = lambda o, s=200: r.fulfill(status=s, content_type='application/json', body=json.dumps(o))
        path_of = lambda: re.sub(r'\?.*$', '', u.split('/contents/', 1)[1]).replace('%2F', '/')
        if re.search(r'/repos/me/backups$', u): return await j({'full_name': 'me/backups', 'private': True, 'permissions': {'push': True}})
        if '/commits?' in u:
            p = re.search(r'path=([^&]+)', u).group(1).replace('%2F', '/')
            return await j([{'sha': c['sha'], 'commit': {'message': c['msg'], 'author': {'date': c['at']}}} for c in self.files.get(p, [])])
        if '/git/ref/heads/' in u:
            h = self.head_all(); return await (j({'object': {'sha': h['sha']}}) if h else j({'message': 'Git Repository is empty.'}, 409))
        if '/git/commits/' in u and m == 'GET': return await j({'tree': {'sha': 't'}})
        if u.endswith('/git/blobs'): self.pending['text'] = base64.b64decode(json.loads(body)['content']).decode(); return await j({'sha': 'b'}, 201)
        if u.endswith('/git/trees'): self.pending['path'] = json.loads(body)['tree'][0]['path']; return await j({'sha': 't2'}, 201)
        if u.endswith('/git/commits') and m == 'POST':
            from datetime import datetime, timezone
            sha = self.add(self.pending['path'], self.pending['text'], datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), json.loads(body)['message']); return await j({'sha': sha}, 201)
        if '/git/refs/heads/' in u and m == 'PATCH': return await j({})
        if '/contents/' in u and m == 'GET':
            p = path_of()
            if p in self.files:
                ref = re.search(r'ref=([^&]+)', u); ref = ref.group(1) if ref else 'main'
                h = self.files[p]; c = next((c for c in h if c['sha'] == ref), h[0])
                return await r.fulfill(status=200, content_type='text/plain', body=c['text'])
            items = [{'type': 'file', 'name': k.split('/')[-1], 'path': k, 'size': len(v[0]['text'])} for k, v in self.files.items() if k.startswith(p + '/')]
            return await (j(items) if items else j({'message': 'Not Found'}, 404))
        return await j({'message': 'nope'}, 404)


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    hub = Hub()
    async with async_playwright() as pw:
        b = await pw.chromium.launch()

        async def device():
            ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
            await ctx.add_init_script(PREFS); await ctx.route('https://api.github.com/**', hub.route)
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
            await pg.goto(URL); await pg.wait_for_timeout(1300); return ctx, pg

        # ---- device A makes a project and its text goes on GitHub as two older backups, plus one unrelated project
        ctxA, A = await device()
        await A.evaluate("() => { P.title = 'Field notes'; P.docs[0].title = 'First pass'; }")
        textA = await A.evaluate("() => projectFileText()")
        pid = json.loads(textA)['id']
        path = f'anabasis/Field-notes-{pid[-6:]}.json'
        hub.add(path, textA.replace('First pass', 'Older pass'), '2026-11-18T09:00:00Z')
        hub.add(path, textA, '2026-11-20T10:00:00Z')
        hub.add('anabasis/Other-abc123.json', json.dumps({'app': 'Anabasis', 'format': 2, 'id': 'p_other', 'title': 'Other', 'docs': [{'id': 'd1', 'title': 'X', 'html': '<p>x</p>'}]}), '2026-11-01T09:00:00Z')

        # ---- device B: open it from GitHub
        ctxB, B = await device()
        await B.evaluate("() => openFromGitHub()")
        await B.fill('#ghRepo', 'me/backups'); await B.fill('#ghToken', 'github_pat_x'); await B.click('#ghProjects'); await B.wait_for_timeout(500)
        rows = await B.evaluate("() => $$('#ghHist li').map(l => l.textContent)")
        check('lists every backed-up project, newest first, with when it was last backed up', len(rows) == 2 and rows[0].startswith('Field notes') and 'Nov 20' in rows[0], rows)
        await B.evaluate("() => { dirtyFile = false; }")
        await B.click(f'#ghHist [data-ghopen="{path}"]'); await B.wait_for_timeout(900)
        r = await B.evaluate("() => ({ t: P.title, d: P.docs[0].title, path: ghCfg().paths[P.id], seen: ghSeen()[P.id], open: $('#ghDlg').open })")
        check('opens the newest backup and remembers where it lives', r == {'t': 'Field notes', 'd': 'First pass', 'path': path, 'seen': 'c2', 'open': False}, r)
        check('no notice when nothing is newer', await B.evaluate("async () => { await ghCheckNewer(true); return $('#ghBar').classList.contains('hidden'); }"))

        # ---- device A backs up again: device B is told when it comes back
        hub.add(path, textA.replace('First pass', 'Second pass'), '2099-01-01T08:00:00Z')
        await B.evaluate("async () => { await ghCheckNewer(true); }"); await B.wait_for_timeout(150)
        check('a newer backup from another device is announced', await B.evaluate("() => !$('#ghBar').classList.contains('hidden') && $('#ghBarMsg').textContent.includes('Field notes')"))
        await B.click('#ghBar [data-gb=open]'); await B.wait_for_timeout(900)
        r = await B.evaluate("() => ({ d: P.docs[0].title, seen: ghSeen()[P.id], bar: $('#ghBar').classList.contains('hidden') })")
        check('…and opening it brings the newer work in', r == {'d': 'Second pass', 'seen': 'c4', 'bar': True}, r)

        # ---- backing up over someone else's newer backup asks first; automatic backups don't do it at all
        hub.add(path, textA.replace('First pass', 'Third pass'), '2099-01-02T08:00:00Z')
        n0 = len(hub.files[path])
        await B.evaluate("() => { P.docs[0].title = 'Mine'; openGitHub(); }"); await B.click('#ghNow'); await B.wait_for_timeout(500)
        asked = await B.evaluate("() => $('#askDlg').open && $('#askTitle').textContent")
        await B.click('#askCancel'); await B.wait_for_timeout(300)
        check('a manual backup over a newer one asks first, and Cancel backs nothing up', asked == 'GitHub has a newer backup' and len(hub.files[path]) == n0 and 'Not backed up' in await B.inner_text('#ghStatus'), asked)
        await B.evaluate("() => $('#ghDlg').close()")
        await B.evaluate("async () => { try { await ghBackup(false); } catch (e) {} }"); await B.wait_for_timeout(300)
        check('an automatic backup never buries a newer one: it shows the notice instead', len(hub.files[path]) == n0 and await B.evaluate("() => !$('#ghBar').classList.contains('hidden')"))
        await B.click('#ghBar [data-gb=no]'); await B.wait_for_timeout(100)
        check('“Not now” puts the notice away until there’s another backup', await B.evaluate("async () => { await ghCheckNewer(true); return $('#ghBar').classList.contains('hidden'); }"))
        await B.evaluate("() => openGitHub()"); await B.click('#ghNow'); await B.wait_for_timeout(400); await B.click('#askOk'); await B.wait_for_timeout(700)
        r = await B.evaluate("() => ghSeen()[P.id]")
        check('“Back up anyway” puts this copy on top and both stay in the history', len(hub.files[path]) == n0 + 1 and '"Mine"' in hub.files[path][0]['text'] and r == hub.files[path][0]['sha'], r)
        await B.evaluate("() => $('#ghDlg').open && $('#ghDlg').close()")

        # ---- an older browser (no record of what it has seen) goes by the clock
        r = await B.evaluate("""() => { const s = ghSeen(); delete s[P.id]; ghCfg().last = null;
            const old = { sha: 'x', at: '2001-01-01T00:00:00Z' }, nu = { sha: 'y', at: new Date(Date.now() + 3600e3).toISOString() };
            return [ghIsNewer(old), ghIsNewer(nu)]; }""")
        check('without a record, only a backup clearly newer than the last edit counts as newer', r == [False, True], r)
        await ctxA.close()

        # ---- weekly review and next steps
        pg = B
        await pg.evaluate("async () => { dirtyFile = false; await openStarter('thesis'); }"); await pg.wait_for_timeout(700)
        await pg.evaluate("() => openJournal('log', true)"); await pg.wait_for_timeout(200)
        await pg.click('.j-kind:has-text("Next step")'); await pg.fill('#jText', 'Order the 1916 war diary'); await pg.press('#jText', 'Control+Enter'); await pg.wait_for_timeout(200)
        check('“Next step” is a kind of log entry, with a box to tick', await pg.locator('.j-entry.k-next input.j-next').count() == 2)
        await pg.evaluate("() => openJournal('week')"); await pg.wait_for_timeout(200)
        body = await pg.inner_text('#deskBody')
        check('This week lists open next steps', 'Order the 1916 war diary' in body and 'Check the Book V halts' in body, body[:300])
        await pg.click('.wk-next input[aria-label^="Done: Order the 1916"]'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => { const e = jr().log.find(x => x.text.startsWith('Order')); return [e.done, !!e.doneAt]; }")
        check('ticking a next step marks it done, with the date', r == [True, True], r)
        check('…and it shows as done this week', 'Done this week: Order the 1916 war diary' in await pg.inner_text('#deskBody'))
        r = await pg.evaluate("() => { const w = weekData(0); return { log: w.log.length, checked: w.checked, nav: $('.j-side li.on').textContent }; }")
        check('the week counts the log and checked claims', r['log'] >= 2 and r['checked'] >= 1 and r['nav'].startswith('This week'), r)
        await pg.click('[aria-label="Previous week"]'); await pg.wait_for_timeout(150)
        check('step back a week', (await pg.inner_text('.j-head h5')).startswith('Week of'))
        await pg.click('[aria-label="Next week"]'); await pg.wait_for_timeout(150)
        await pg.click('#deskBody button:has-text("Week summary")'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ t: curDoc().title, h: [...editor.querySelectorAll('h2')].map(h => h.textContent) })")
        check('a week summary document', r['t'].startswith('Week of ') and 'Next' in r['h'], r)
        check('the research memo lists open next steps', await pg.evaluate("() => { journalDoc('memo'); const h = [...editor.querySelectorAll('h2')].find(h => h.textContent === 'Next steps'), ul = h && h.nextElementSibling; return !!ul && ul.textContent.includes('Check the Book V halts') && !ul.textContent.includes('Order the 1916'); }"))
        check('the Research tab counts open next steps', 'next step to do' in await pg.inner_text('#rsJournal') or 'next steps to do' in await pg.inner_text('#rsJournal'))

        # ---- research design templates
        await pg.evaluate("() => { jr().design = { purpose: 'Why', methods: '', data: '', scope: 'Only 401 BC.', ethics: '', timeline: '' }; openJournal('design'); }"); await pg.wait_for_timeout(200)
        await pg.select_option('#jTpl', 'archival'); await pg.click('#jTplGo'); await pg.wait_for_timeout(300)
        await pg.click('#askCancel'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => jr().design")
        check('a template fills only the empty fields when you say so', r['methods'].startswith('Archival research') and r['data'].startswith('Collections') and r['scope'] == 'Only 401 BC.' and r['purpose'] == 'Why', r)
        await pg.select_option('#jTpl', 'interviews'); await pg.click('#jTplGo'); await pg.wait_for_timeout(300); await pg.click('#askOk'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => jr().design")
        check('a second method adds below what’s there', r['methods'].startswith('Archival research') and 'semi-structured interviews' in r['methods'] and r['scope'].startswith('Only 401 BC.\n\n'), r['methods'][:80])
        check('templates are noted in the log', await pg.evaluate("() => jr().log.filter(e => e.kind === 'auto' && e.text.startsWith('Research design: added prompts')).length === 2"))

        # ---- fact-check sheet: who checked, page numbers, and as a document
        await pg.evaluate("() => { PREFS.myName = 'G. Rapp'; closeDesk(); openDoc(P.docs[0].id); const ids = rmAll('cl').map(p => p.pid); ids.forEach(id => setClaimStatus(id, 'ok')); }"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => P.claims.map(c => c.checkedBy)")
        check('checking a claim records who checked it', r and all(x == 'G. Rapp' for x in r), r)
        async with pg.expect_download() as d: await pg.evaluate("() => factSheet()")
        sheet = open(await (await d.value).path(), encoding='utf-8').read()
        check('the sheet fills in who checked and when, and the page of each citation', 'G. Rapp, ' in sheet and re.search(r'<b>pp?\. [\d–-]+</b>', sheet), re.findall(r'<b>[^<]*</b>', sheet)[:6])
        await pg.evaluate("() => factSheet(true)"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ t: curDoc().title, rows: editor.querySelectorAll('figure.tbl tbody tr').length, txt: editor.innerText })")
        check('…and as a document in the project', r['t'].startswith('Fact-check sheet') and r['rows'] >= 3 and 'G. Rapp' in r['txt'], {k: r[k] for k in ('t', 'rows')})
        csv = await pg.evaluate("() => { let out = ''; const d = window.download; window.download = (n, t) => { out = t; }; claimsCSV(); window.download = d; return out; }")
        check('the claims CSV has the checker too', 'G. Rapp, ' in csv)

        # ---- getting-started tips
        await pg.evaluate("() => { P.goal.kind = 'brief'; delete PREFS.tipsFor[P.id]; addDoc(newDoc('Empty brief')); }"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ on: !$('#tipCard').classList.contains('hidden'), k: $('#tipFor').value, n: $$('#tipCard li').length, first: $('#tipCard li').textContent })")
        check('an empty document shows tips for the kind of project', r['on'] and r['k'] == 'brief' and r['n'] == 6 and r['first'].startswith('Lead with key judgments'), r)
        await pg.select_option('#tipFor', 'script'); await pg.wait_for_timeout(100)
        check('pick another kind of writing, remembered for the project', await pg.evaluate("() => PREFS.tipsFor[P.id] === 'script' && $('#tipCard li').textContent.startsWith('Hook')"))
        await pg.evaluate("() => editor.focus()"); await pg.keyboard.type('Key judgments'); await pg.wait_for_timeout(100)
        check('tips go away when you start typing', await pg.evaluate("() => $('#tipCard').classList.contains('hidden')"))
        check('…and never appear in the document itself', await pg.evaluate("() => { syncEditor(); return !curDoc().html.includes('Getting started'); }"))
        await pg.evaluate("() => addDoc(newDoc('Another'))"); await pg.wait_for_timeout(200)
        await pg.click('#tipClose'); await pg.wait_for_timeout(100)
        check('close the tips for one document', await pg.evaluate("() => $('#tipCard').classList.contains('hidden') && !PREFS.tipsOff"))
        await pg.evaluate("() => addDoc(newDoc('Third'))"); await pg.wait_for_timeout(200)
        await pg.click('#tipOff'); await pg.wait_for_timeout(100)
        await pg.evaluate("() => addDoc(newDoc('Fourth'))"); await pg.wait_for_timeout(200)
        check('turn tips off everywhere', await pg.evaluate("() => PREFS.tipsOff === true && $('#tipCard').classList.contains('hidden')"))
        await pg.evaluate("() => $('#btnSettings').click()"); await pg.wait_for_timeout(200)
        check('…and back on in Settings', await pg.evaluate("() => $('#stTips').checked === false"))
        await pg.evaluate("() => { $('#stTips').checked = true; $('#stTips').dispatchEvent(new Event('change', { bubbles: true })); }")
        await pg.evaluate("() => { $('#stOk').click(); }"); await pg.wait_for_timeout(200)
        check('Settings turns them back on', await pg.evaluate("() => !PREFS.tipsOff && !$('#tipCard').classList.contains('hidden')"))
        await pg.evaluate("() => $('#btnHelp').click()"); await pg.wait_for_timeout(200)
        check('Help lists the tips for every kind of writing', await pg.evaluate("() => $$('#helpTips details').length === Object.keys(TIPS).length"))
        await pg.evaluate("() => $('#helpDlg').close()")

        # ---- hostile values in the new fields
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p>x</p>'}],
                          'claims': [{'id': 'c1', 'status': 'ok', 'checkedBy': {'x': 1}}],
                          'journal': {'log': [{'id': 'a', 'kind': 'next', 'text': 'go', 'done': 'yes', 'doneAt': 5}, {'id': 'b', 'kind': 'did', 'text': 'x', 'done': True}]}})
        await pg.evaluate("t => { dirtyFile = false; return loadProjectText(t, null, 'bad.json'); }", bad); await pg.wait_for_timeout(600)
        r = await pg.evaluate("() => ({ c: P.claims[0].checkedBy, l: P.journal.log.map(e => [e.kind, e.done, e.doneAt]) })")
        check('hostile values in the new fields are tidied', r == {'c': '', 'l': [['next', True, '5'], ['did', False, '']]}, r)
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
