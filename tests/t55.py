"""2.9.0: the Oracle knows the project as it stands, starts and ends the day, says what to work on next, has a manner,
and holds up over a long conversation (a script lint and a ramble with no repeats or broken replies)."""
import asyncio, re
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

RAMBLE = [
    'I am working on the chapter about the retreat', 'I think the army lived off the land', 'the sources disagree about the numbers',
    'Xenophon says the generals were seized at a feast', 'I am not sure the numbers hold up', 'my editor wants the opening shorter',
    'the conclusion feels weak', 'I keep reading instead of writing', 'maybe the theory of logistics is wrong', 'I got rejected by a magazine last week',
    'the interview with the archivist went well', 'I need to cut two thousand words', 'the structure of the book is a mess', 'I want to finish by spring',
    'the deadline is in March', 'I doubt the Persian sources', 'they always exaggerate', 'because the satraps wanted them gone', 'the data on rainfall is thin',
    'my title is boring', 'I translated the passage myself', 'readers will not know who Tissaphernes was', 'the money is not great', 'I feel like nobody reads this stuff',
    'the archive in Athens might have letters', 'I found a new map of the route', 'it turned out the river was further east', 'the quote from Lee is too long',
    'my voice is too academic', 'I should probably start the next chapter', 'the paragraph about the passes is too long', 'the evidence for the mutiny is thin',
    'I am revising chapter two', 'it is important that readers see the hunger', 'perhaps the generals were never in control', 'the feedback was harsh',
    'the idea came to me in the shower', 'the hoplites were a minority of the march', 'I cannot decide where the map goes', 'that is all I have for now on that',
]


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Ada Ferro',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---- the script holds together in every manner
        r = await pg.evaluate("""(() => { const out = {}; for (const m of ['gentle', 'plain', 'blunt']) { PREFS.orcManner = m; ORS = null; const S = orcScript(); const bad = [];
            S.groups.concat([S.none]).forEach(g => g.rules.forEach(r => { const caps = r.pat.filter(x => x.t === '*' || x.syn).length; if (!r.replies.length && !r.mem.length) bad.push(r.id + ': no replies');
              r.replies.concat(r.mem).forEach(t => { (t.match(/\\{(\\d)\\.?\\}/g) || []).forEach(x => { if (+x[1] > caps) bad.push(r.id + ': ' + t); }); if (/^\\[(g|b)\\]/.test(t)) bad.push(r.id + ': tag left in ' + t); }); }));
            Object.keys(S.syn).forEach(k => { if (!S.groups.some(g => g.keys.includes('[' + k + ']') || g.rules.some(r => r.pat.some(x => x.syn === k)))) bad.push('unused set ' + k); });
            out[m] = { groups: S.groups.length, bad, none: S.none.rules[0].replies.slice(0, 2) }; } PREFS.orcManner = 'plain'; ORS = null; return out; })()""")
        check('The Oracle’s script has more to say about: 60+ groups', r['plain']['groups'] >= 60, r['plain']['groups'])
        check('…every reply fits its pattern, in every manner', not r['gentle']['bad'] and not r['plain']['bad'] and not r['blunt']['bad'], [r[m]['bad'][:4] for m in r])
        check('…and the manner changes what comes first', r['gentle']['none'] != r['plain']['none'] and r['blunt']['none'] != r['plain']['none'], [r[m]['none'] for m in r])

        # ---- a project with things going on
        await pg.evaluate("""() => {
            const d = P.docs.find(x => /Army/.test(x.title)), K = n => { const x = new Date(); x.setDate(x.getDate() + n); return todayKey(x); };
            d.deadline = K(2); d.revision = { claim: K(-1), aloud: K(-1) };
            P.subs = [{ id: 's1', docId: d.id, outlet: 'Journal of Ancient Logistics', editor: 'R. Okafor', kind: 'submission', sent: K(-30), status: 'sent', followUp: K(-1), fee: '', notes: '', closed: '', created: nowISO(), modified: nowISO() },
                      { id: 's2', docId: '', outlet: 'History Today', editor: '', kind: 'pitch', sent: K(-50), status: 'rejected', followUp: '', fee: '', notes: '', closed: K(-20), created: nowISO(), modified: nowISO() }];
            P.events = [{ id: 'e1', date: K(3), time: '10:00', title: 'Archive visit, Athens', kind: 'visit', note: '', created: nowISO(), modified: nowISO() }];
            jLog('did', 'Drafted the section on the passes'); const y = jr().log[jr().log.length - 1]; y.date = K(-1);
            jLog('next', 'Check Engels on daily rations'); const z = jr().log[jr().log.length - 1]; z.date = K(-1);
            openDoc(d.id);
            const p = [...editor.querySelectorAll('p')].find(e => e.textContent.includes('usually turn on courage')), w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let t; while ((t = w.nextNode())) if (t.data.includes('usually turn on')) break;
            const a = t.data.indexOf('usually turn on'), r = document.createRange(); r.setStart(t, a); r.setEnd(t, a + 15); edmWrap(r, { 'data-edm': 'm1', 'data-ek': 'aq', 'data-by': 'R. Okafor', 'data-t': 'Which histories?', 'data-sym': 'AQ' }); onEdit(); syncEditor();
        }""")
        await pg.evaluate("openOracle()"); await pg.wait_for_timeout(400)
        async def say(t):
            await pg.evaluate("(t) => orcTurn(t)", t); await pg.wait_for_timeout(50)
            return await pg.evaluate("ORC.log[ORC.log.length - 1].text")

        a = await say('check in')
        check('Check-in starts from where you left off', 'Yesterday you logged: Drafted the section on the passes' in a and 'meant to start with Check Engels on daily rations' in a, a[:400])
        check('…with what’s coming up and the editor’s marks', 'is due in 2 days' in a and 'Follow up with Journal of Ancient Logistics' in a and '1 editing mark is open, 1 query among them' in a, a[:600])
        check('…and an offer to say what to work on first', 'What should I work on first?' in a, a[-200:])
        a = await say('what should I work on next?')
        lines = await pg.evaluate("$$('#orcLog .orc-m.or:last-child ol li').map(l => l.textContent)")
        check('“What should I work on next?”: the project’s urgencies, most pressing first', len(lines) == 3 and lines[0].startswith('Follow up with Journal of Ancient Logistics') and 'due in 2 days' in lines[1] and 'query' in lines[2], lines)
        a = await say('which chapter is weakest?')
        check('“Which chapter is weakest?” reads the revision checklist and the lens', 'Least revised' in a and '2 of 9 on its checklist' in a, a)
        a = await say('any queries from my editor?')
        check('“Any queries from my editor?” lists the open marks', '1 editing mark is open in 1 document, from R. Okafor, 1 of them a query' in a and 'Which histories?' in a, a)
        a = await say("what's out on submission?")
        check('“What’s out on submission?”', '1 piece is out' in a and 'Journal of Ancient Logistics' in a and 'follow up 1 day overdue' in a and '1 decline' in a, a)
        a = await say("what's coming up?")
        check('“What’s coming up?” covers deadlines, follow-ups and the calendar', 'Archive visit, Athens' in a and 'at 10:00' in a and 'is due' in a and 'overdue' in a, a)
        a = await say('steelman: the army lived off the land')
        r = await pg.evaluate("({ open: $('#socDlg').open, walk: WK.id, claim: WK.D.claim })")
        check('“steelman:” hands the claim to Socrates', r == {'open': True, 'walk': 'steelman', 'claim': 'the army lived off the land'}, r)
        await pg.evaluate("$('#socDlg').close()")

        # ---- manner
        a = await say('be blunt')
        check('“Be blunt” changes the manner, and Settings shows it', 'blunt' in a and await pg.evaluate("PREFS.orcManner") == 'blunt', a)
        a = await say('I keep procrastinating on the conclusion')
        check('…blunt replies come first', a == 'What exactly are you avoiding? Name it.', a)
        await pg.evaluate("() => { openSettings(); $('#stOrcManner').value = 'gentle'; $('#stOk').click(); }")
        a = await say('I keep procrastinating on the introduction')
        check('…and Settings can make it gentle', a.startswith('That’s human.'), a)
        await pg.evaluate("orcSetManner('plain')")

        # ---- the wrap-up
        a = await say('wrap up')
        check('Wrap up asks what you got done', 'what did you get done today' in a, a)
        await say('Rewrote the opening'); await say('The rations figure'); a = await say('Find the rations figure in Engels')
        r = await pg.evaluate("jr().log.filter(e => e.date === todayISO()).map(e => [e.kind, e.text])")
        check('…then what’s left, and the first thing next time, into the journal', ['did', 'Rewrote the opening\n\nStill open: The rations figure'] in r and ['next', 'Find the rations figure in Engels'] in r, r)
        check('…and signs off', 'Until next time' in a, a)

        # ---- a long ramble: no broken or repeated replies
        await pg.evaluate("orcNew()")
        replies = []
        for t in RAMBLE:
            replies.append(await say(t))
        broken = [x for x in replies if not x.strip() or re.search(r'\{\d|undefined|null|NaN|\[object', x)]
        check('A forty-turn ramble: every reply is whole', not broken, broken[:3])
        rep = [(i, x) for i, x in enumerate(replies) if x in replies[max(0, i - 8):i]]
        check('…and none repeats within eight turns', not rep, rep[:3])
        first = [x.split('\n')[0] for x in replies]
        generic = sum(1 for x in first if re.match(r'^(Go on|Keep going|And then|Say more|Tell me more|What makes you|And what follows|So what follows|If that’s so)', x))
        check('…and most of it answers what was said, not a generic “go on”', generic <= 8, generic)
        topical = {'my editor wants the opening shorter': ['editor', 'opening'], 'I need to cut two thousand words': ['cut', 'lose', 'tenth', 'slow', 'protecting', 'slush'],
                   'I got rejected by a magazine last week': ['why', 'fit', 'next', 'rejection', 'turned down'], 'my title is boring': ['title', 'search', 'promise', 'Clever'], 'I keep reading instead of writing': ['read', 'write', 'source']}
        miss = [t for t, words in topical.items() if not any(w.lower() in replies[RAMBLE.index(t)].lower() for w in words)]
        check('…writing troubles get answers about them', not miss, [(t, replies[RAMBLE.index(t)]) for t in miss])

        # ---- installing as an app (2.9)
        r = await pg.evaluate("(() => { openSettings(); return $('#stInstall').innerText; })()")
        check('Settings says how to install: from the hosted copy, since a file can’t be installed', 'browsers install apps only from a website' in r and 'zerohistory.net/anabasis/app' in r, r)
        r = await pg.evaluate("(async () => { const e = new Event('beforeinstallprompt', { cancelable: true }); e.prompt = () => { window.__asked = 1; }; e.userChoice = Promise.resolve({ outcome: 'accepted' }); dispatchEvent(e); const b = $('#stInstallGo'); const had = !!b; b && b.click(); await new Promise(z => setTimeout(z, 50)); return { had, asked: !!window.__asked, after: $('#stInstall').innerText }; })()")
        check('…and where the browser can install it, an Install button that asks the browser', r['had'] and r['asked'] and 'Install Anabasis' not in r['after'], r)
        await pg.evaluate("$('#settingsDlg').close()")

        bad = [e for e in errs if 'favicon' not in e]
        check('no page errors', not bad, bad[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
