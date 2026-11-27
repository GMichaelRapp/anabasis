"""2.11: the Quartermaster. Turning it on, what it records (typing, pastes from outside, notes, quotations, text
moved within the project), pause and resume, changes made while it wasn't watching, the hash chain and the ways it
catches tampering, saving and reopening, GitHub anchors, a hostile ledger in a crafted file, the report (its own
script runs, nothing else does, nothing is fetched, an edited script doesn't run), locked projects, and speed."""
import asyncio, json, re
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

PWN = 'window.PWN=(window.PWN||[]).concat(1)'


def paste_js(text):
    return f"""() => {{ const dt = new DataTransfer(); dt.setData('text/plain', {json.dumps(text)}); editor.focus(); editor.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }})); }}"""


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs, reqs = [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Jane Q. Writer'}))")
        ctx.on('request', lambda r: reqs.append(r.url) if re.match(r'https?://', r.url) and '127.0.0.1' not in r.url and 'localhost' not in r.url else None)
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.on('console', lambda m: errs.append('console: ' + m.text[:200]) if m.type == 'error' and 'Executing inline event handler' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1200)

        # ---- off until turned on
        check('off until the writer turns it on', await pg.evaluate("!curDoc().ledger && $('#qmBadge').classList.contains('hidden')"))
        await pg.evaluate("openQM()"); await pg.wait_for_timeout(200)
        t = await pg.inner_text('#qmBody')
        check('turning it on says what it keeps and never keeps', 'never keeps' in t and 'keystrokes' in t and 'can’t prove' in t, t[:200])
        await pg.click('#qmStart'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ ev: curDoc().ledger.events.map(e => e.k), pre: curDoc().ledger.events[1] && curDoc().ledger.events[1].d.pre, badge: !$('#qmBadge').classList.contains('hidden') && $('#qmBadge').textContent.trim() })")
        check('on: a start entry, then the text already there, and a badge', r['ev'][:2] == ['start', 'snap'] and r['pre'] == 1 and r['badge'] == 'Ledger', r)

        # ---- what it records
        await pg.click('#editor p'); await pg.keyboard.press('End'); await pg.keyboard.type(' I wrote this sentence myself, one key at a time.')
        await pg.evaluate("qmLastSnap = 0; qmFlush()")
        await pg.evaluate(paste_js('A long passage lifted from a website about the war, pasted straight into the draft without changes.'))
        await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { const n = Object.assign(newNote(), { title: 'A quotation', kind: 'quote', body: 'Plans built for speed leave no room for second thoughts once the trains begin to move.', sourceId: P.sources[0].id, locator: '12' }); P.notes.push(n); insertNote(n); }""")
        await pg.wait_for_timeout(300)
        await pg.evaluate(paste_js(await pg.evaluate("P.notes[0].body")))
        await pg.wait_for_timeout(300)
        moved = await pg.evaluate("editor.querySelectorAll('p')[4].textContent.trim().split(/\\s+/).slice(0, 8).join(' ')")
        await pg.evaluate(paste_js(moved)); await pg.wait_for_timeout(300)
        await pg.evaluate("qmLastSnap = 0; qmDirty = true; qmFlush()")
        r = await pg.evaluate("curDoc().ledger.events.filter(e => e.k === 'paste').map(e => [e.d.src, e.d.via])")
        check('pastes are told apart: outside, a quotation inserted, a note pasted, text moved within the project', r == [['outside', 'paste'], ['quote', 'insert'], ['note', 'paste'], ['moved', 'paste']], r)
        r = await pg.evaluate("(() => { const L = curDoc().ledger; return { last: qmReplay(L).join('\\n') === qmParasOf(curDoc()).join('\\n'), snaps: L.events.filter(e => e.k === 'snap').length }; })()")
        check('the snapshots rebuild the document exactly', r['last'] and r['snaps'] >= 4, r)
        check('no keystrokes or clipboard contents beyond what was pasted are kept', await pg.evaluate("!JSON.stringify(curDoc().ledger).match(/\"(key|keys|code|clipboard)\"/)"))

        # ---- pause, resume, and changes it didn't see
        await pg.evaluate("openQM()"); await pg.click('#qmPause'); await pg.wait_for_timeout(200)
        check('pause shows on the badge', await pg.evaluate("$('#qmBadge').classList.contains('paused') && $('#qmBadge').textContent.includes('paused')"))
        await pg.keyboard.press('Escape')
        await pg.evaluate("() => { editor.querySelector('p').append(' Added while paused.'); syncEditor(); qmDirty = true; qmFlush(); }")
        check('nothing is recorded while paused', await pg.evaluate("curDoc().ledger.events[curDoc().ledger.events.length - 1].k === 'pause'"))
        await pg.evaluate("openQM()"); await pg.click('#qmPause'); await pg.wait_for_timeout(200); await pg.keyboard.press('Escape')
        r = await pg.evaluate("curDoc().ledger.events.slice(-2).map(e => e.k + (e.d.out ? ':out' : ''))")
        check('resuming records what changed meanwhile, marked as such', r == ['resume', 'snap:out'], r)
        await pg.evaluate("() => { const d = curDoc(); const other = P.docs.find(x => x.id !== d.id) || (() => { const n = newDoc('Other'); P.docs.push(n); return n; })(); openDoc(other.id); d.html += '<p>Edited in another browser.</p>'; openDoc(d.id); }")
        await pg.wait_for_timeout(300)
        check('a change made elsewhere is caught when the document opens', await pg.evaluate("(() => { const e = curDoc().ledger.events; const l = e[e.length - 1]; return l.k === 'snap' && l.d.out === 1 && l.d.s.join(' ').includes('another browser'); })()"))

        # ---- the chain
        check('intact and bound to this document', await pg.evaluate("(() => { const v = qmVerify(curDoc()); return v.ok && v.bound; })()"))
        r = await pg.evaluate("""(() => { const d = curDoc(), keep = JSON.stringify(d.ledger), out = {};
          const t = f => { d.ledger = JSON.parse(keep); f(d.ledger); const v = qmVerify(d); return v.ok ? (v.bound ? 'ok' : 'unbound') : 'broken@' + v.at; };
          out.edit = t(L => { L.events[3].d.w += 50; });
          out.drop = t(L => { L.events.splice(4, 1); });
          out.swap = t(L => { const x = L.events[4]; L.events[4] = L.events[5]; L.events[5] = x; });
          out.trim = t(L => { L.events.pop(); });
          out.moved = (() => { d.ledger = JSON.parse(keep); const o = P.docs.find(x => x.id !== d.id); o.ledger = JSON.parse(keep); const v = qmVerify(o); delete o.ledger; return v.ok && !v.bound ? 'unbound' : 'missed'; })();
          d.ledger = JSON.parse(keep); return out; })()""")
        check('an edited entry breaks the chain there', r['edit'] == 'broken@4', r)
        check('a dropped, reordered or trimmed entry breaks it', r['drop'].startswith('broken') and r['swap'].startswith('broken') and r['trim'].startswith('broken'), r)
        check('a ledger moved to another document is caught', r['moved'] == 'unbound', r)

        # ---- saving and reopening
        r = await pg.evaluate("""(() => { const id = curDoc().id, n = curDoc().ledger.events.length; loadProjectText(projectJSON(), null); openDoc(id);
          const d = curDoc(), v = qmVerify(d); return { n: d.ledger.events.length, was: n, ok: v.ok && v.bound, badge: !$('#qmBadge').classList.contains('hidden') }; })()""")
        await pg.wait_for_timeout(400)
        check('saved and reopened: the ledger is intact and still on', r['ok'] and r['n'] >= r['was'] and r['badge'], r)

        # ---- GitHub anchors
        r = await pg.evaluate("(() => { const note = qmBackupNote(); qmAnchor('3f9c2ab71d0e'); qmAnchor('not a sha'); const e = curDoc().ledger.events.filter(x => x.k === 'anchor'); return { note, n: e.length, sha: e[0] && e[0].d.sha }; })()")
        check('a backup commit names each ledger and its latest link; the commit is anchored', 'Quartermaster ledger' in r['note'] and 'link ' in r['note'] and r['n'] == 1 and r['sha'] == '3f9c2ab71d0e', r)

        # ---- the report
        await pg.evaluate("openQM()"); await pg.wait_for_timeout(200)
        async with pg.expect_download() as dl: await pg.click('#qmReport')
        path = _os.path.join(OUT, 'qm-report.html'); await (await dl.value).save_as(path)
        html = open(path, encoding='utf-8').read()
        check('the report carries its own policy: one script pinned by hash, nothing from the internet', 'http-equiv="Content-Security-Policy"' in html and "default-src 'none'" in html and html.count("'sha256-") == 1 and 'connect-src' not in html)
        check('…the honest paragraph, the account and the chain check', 'doesn’t prove who wrote it' in html and 'Pasted from outside Anabasis' in html and 'Intact' in html and 'Jane Q. Writer' in html)
        check('…note titles left out unless asked', 'A quotation' not in html)
        rp = await ctx.new_page(); rerrs = []
        rp.on('pageerror', lambda e: rerrs.append(str(e))); rp.on('console', lambda m: rerrs.append(m.text) if m.type == 'error' else None)
        await rp.goto('file://' + path); await rp.wait_for_timeout(1500)
        r = await rp.evaluate("({ live: document.getElementById('qm-live').textContent, when: document.getElementById('rp-when').textContent, ps: document.querySelectorAll('#rp-view p').length, outside: document.querySelectorAll('.text .src-outside').length, quote: document.querySelectorAll('.text .src-quote').length, note: document.querySelectorAll('.text .src-note').length })")
        check('opened: its own script checks the chain and draws the replay', 'all ' in r['live'] and 'link up' in r['live'] and 'words' in r['when'] and r['ps'] > 3, r)
        check('the text is marked by where it came from', r['outside'] >= 1 and r['quote'] >= 1 and r['note'] >= 1, r)
        await rp.click('#rp-play'); await rp.wait_for_timeout(1200)
        check('the replay plays', await rp.evaluate("+document.getElementById('rp-range').value > 0"))
        check('the report runs without errors', not rerrs, rerrs)
        await rp.close()
        # an edited copy: its script no longer matches the policy, so it doesn't run
        bad = html.replace("Checked in this browser just now", "Checked here")
        bp = _os.path.join(OUT, 'qm-edited.html'); open(bp, 'w', encoding='utf-8').write(bad)
        ep = await ctx.new_page(); await ep.goto('file://' + bp); await ep.wait_for_timeout(1000)
        check('an edited report’s script doesn’t run', await ep.evaluate("document.getElementById('qm-live').textContent") == 'Checking in this browser…')
        await ep.close()

        # ---- a hostile ledger in a crafted project file
        proj = await pg.evaluate("JSON.parse(projectJSON())")
        d0 = proj['docs'][0]; evs = d0['ledger']['events']
        evil = '</script><script>' + PWN + '</script><img src=x onerror="' + PWN + '">'
        evs.append({'t': evs[-1]['t'], 'k': 'snap', 'd': {'a': 0, 'r': 0, 's': [evil, '"><svg onload="' + PWN + '">'], 'w': 9}, 'p': 'x'})
        evs.append({'t': evs[-1]['t'], 'k': 'paste', 'd': {'src': 'outside', 'via': 'paste', 'w': 3, 'x': evil}, 'p': 'y'})
        evs.append({'t': '<b>now</b>', 'k': 'snap', 'd': {'a': 0, 'r': 0, 's': [], 'w': 1}, 'p': ''})
        evs.append({'t': evs[0]['t'], 'k': 'eval', 'd': {}, 'p': ''})
        evs.append({'t': evs[0]['t'], 'k': 'snap', 'd': {'a': -1, 'r': 'x', 's': 'no', 'w': 1, 'html': evil}, 'p': ''})
        evs.append({'t': evs[0]['t'], 'k': 'paste', 'd': {'src': 'outside', 'via': 'paste', 'w': 1, 'x': 'a', 'ref': '"><b>'}, 'p': ''})
        d0['ledger']['on'] = 'yes'; d0['ledger']['head'] = '<script>'
        await pg.evaluate("p => loadProjectText(JSON.stringify(p), null)", proj); await pg.wait_for_timeout(600)
        r = await pg.evaluate("(() => { const L = P.docs[0].ledger; return { n: L.events.length, kinds: [...new Set(L.events.map(e => e.k))], on: L.on, head: L.head, v: qmVerify(P.docs[0]) }; })()")
        check('a crafted ledger: malformed entries dropped, odd values not trusted', 'eval' not in r['kinds'] and r['on'] is False and r['head'] == '' and not r['v']['ok'], r)
        await pg.evaluate(f"openDoc(P.docs[0].id); openQM()"); await pg.wait_for_timeout(300)
        check('…the dialog says it was changed', 'Changed after it was recorded' in await pg.inner_text('#qmBody'))
        async with pg.expect_download() as dl: await pg.click('#qmReport')
        hp = _os.path.join(OUT, 'qm-hostile.html'); await (await dl.value).save_as(hp)
        hh = open(hp, encoding='utf-8').read()
        check('…the report holds the payload only as escaped data', '</script><script>window.PWN' not in hh and '\\u003c/script>' in hh)
        hpg = await ctx.new_page(); await hpg.goto('file://' + hp); await hpg.wait_for_timeout(1200)
        await hpg.evaluate("document.getElementById('rp-range').value = document.getElementById('rp-range').max; document.getElementById('rp-range').dispatchEvent(new Event('input'))"); await hpg.wait_for_timeout(300)
        r = await hpg.evaluate("({ pwn: window.PWN || null, live: document.getElementById('qm-live').textContent, shown: document.getElementById('rp-view').textContent.includes('onerror') })")
        check('…nothing in it runs; the replay shows it as text; the in-page check flags it', r['pwn'] is None and 'changed' in r['live'] and r['shown'], r)
        await hpg.close()
        check('nothing ran in the app either', await pg.evaluate("window.PWN || null") is None)
        await pg.keyboard.press('Escape')
        # too big to read: set aside, the rest opens
        big = await pg.evaluate("JSON.parse(projectJSON())")
        big['docs'][0]['ledger'] = {'v': 1, 'on': True, 'events': [{'t': '2026-01-01T00:00:00Z', 'k': 'pause', 'd': {}, 'p': ''}] * 200001}
        await pg.evaluate("p => loadProjectText(JSON.stringify(p), null)", big); await pg.wait_for_timeout(2400)
        r = await pg.evaluate("({ ledger: 'ledger' in P.docs[0], docs: P.docs.length, toast: $('#toast') ? $('#toast').textContent : '' })")
        check('a ledger too large to read is set aside, and the project opens', not r['ledger'] and r['docs'] >= 1 and 'set aside' in r['toast'], r)

        # ---- locked projects
        await pg.evaluate("""async () => { const salt = crypto.getRandomValues(new Uint8Array(16)); LOCK = { key: await deriveKey('correct horse battery', salt), salt, iter: ITER };
          openQM(); $('#qmStart').click(); }"""); await pg.wait_for_timeout(300)
        await pg.evaluate("openQM()"); await pg.click('#qmReport'); await pg.wait_for_timeout(300)
        check('a report from a locked project asks first', await pg.evaluate("$('#askDlg').open && $('#askTitle').textContent") == 'The report isn’t locked')
        await pg.click('#askCancel'); await pg.evaluate("LOCK = null")

        # ---- delete
        await pg.evaluate("openQM()"); await pg.click('#qmDelete'); await pg.wait_for_timeout(200); await pg.click('#askOk'); await pg.wait_for_timeout(200)
        check('deleting removes the ledger and the badge, not the document', await pg.evaluate("!curDoc().ledger && $('#qmBadge').classList.contains('hidden') && editor.textContent.length > 100"))

        # ---- speed on a long document
        r = await pg.evaluate("""() => { const para = '<p>' + 'The plan crowded out diplomacy, and speed became the point of everything. '.repeat(6) + '</p>';
          const d = curDoc(); d.html = para.repeat(2500); editor.innerHTML = d.html; openQM(); $('#qmStart').click();
          editor.querySelector('p:nth-child(1200)').append(' A small change.'); syncEditor(); qmDirty = true; qmLastSnap = 0;
          const t = performance.now(); qmFlush(); return { ms: Math.round(performance.now() - t), w: qmWords(d.ledger.last) }; }""")
        check('a snapshot of a 180,000-word document takes a moment, not a freeze', r['ms'] < 250 and r['w'] > 150000, r)
        check('nothing was fetched from the internet', not reqs, reqs[:5])
        await b.close()
    print('ERRS', json.dumps(errs))
    _sys.exit(0 if ok and not errs else 1)

asyncio.run(main())
