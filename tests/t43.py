"""2.2.0: the Oracle. The ELIZA-style engine (script, substitutions, reflection, ranked keywords, rotation,
memory), the pane beside the writing, answers from the project, counts and status, saving what you say,
arguing the other side, the daily check-in and log, consulting on a passage, nudges, Delphic sign-offs,
saving a conversation to the journal, and no network use at any point."""
import asyncio, json, re, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs, net = [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        # ---- the script
        sc = await pg.evaluate("""() => { const S = orcScript(); const bad = [];
            S.groups.forEach(g => g.rules.forEach(r => { const n = r.pat.filter(p => p.t === '*' || p.syn).length; [...r.replies, ...r.mem].forEach(t => { (t.match(/\\{(\\d)\\.?\\}/g) || []).forEach(m => { if (+m[1] > n) bad.push(t); }); }); if (!r.replies.length) bad.push('no replies: ' + r.id); }));
            const syn = S.groups.flatMap(g => g.keys.filter(k => /^\\[/.test(k)).concat(g.rules.flatMap(r => r.pat.filter(p => p.syn).map(p => '[' + p.syn + ']')))).filter(k => !S.syn[k.slice(1, -1)]);
            return { groups: S.groups.length, none: S.none.rules[0].replies.length, subs: Object.keys(S.subs).length, bad, syn }; }""")
        check('the script has its keyword groups, fallbacks and contractions', sc['groups'] >= 28 and sc['none'] >= 5 and sc['subs'] >= 25, sc)
        check('every reply uses only pieces its pattern captures, and every set exists', not sc['bad'] and not sc['syn'], (sc['bad'][:3], sc['syn']))

        # ---- the engine
        en = await pg.evaluate("""() => {
            const words = s => orcTok(s).filter(t => !t.p).map(t => t.w).join(' ');
            const r = s => { const x = orcReply(s); return x ? x.group : null; };
            return { tok: words("I don't know, I'm stuck"),
                     refl: orcReflect(orcTok('my chapter and I am sure you saw me')),
                     np: orcReflect(orcTok('source says the army starved'), true),
                     g: { stuck: r('I am stuck on chapter three'), belief: r('I think the blockade mattered'), hedge: r('maybe it was the harvest'),
                          because: r('the army turned north because the passes were closed'), know: r('I do not know where the figures came from'),
                          src: r('the archive has a gap in 1916'), all: r('everyone agrees on this'), none: r('purple elephants') } }; }""")
        check('contractions are rewritten before matching', en['tok'] == 'i do not know i am stuck', en['tok'])
        check('your words are turned around: my → your, I am → you are, you → me', en['refl'] == 'your chapter and you are sure I saw me' or en['refl'] == 'your chapter and you are sure me saw you', en['refl'])
        check('{n.} keeps just the noun phrase', en['np'] == 'source', en['np'])
        g = en['g']
        check('the highest-ranked keyword picks the reply', g['stuck'] == '[stuck]' and g['belief'] == '[belief]' and g['hedge'] == '[hedge]' and g['because'] == 'because' and g['know'] == 'know' and g['src'] == '[src]' and g['all'] == '[all]' and g['none'] is None, g)
        rot = await pg.evaluate("() => { const a = orcReply('maybe it was the harvest').text, b = orcReply('maybe it was the harvest').text, c = orcReply('maybe it was the harvest').text; return [a, b, c]; }")
        check('saying the same thing again gets a different reply', len(set(rot)) == 3, rot)
        fill = await pg.evaluate("() => orcReply('I think the blockade caused the famine').text")
        check('a reply carries your own words back', 'the blockade' in fill or 'blockade' in fill or 'mechanism' in fill, fill)
        mem = await pg.evaluate("() => { ORC.mem = []; orcReply('my chapter is a mess'); return ORC.mem.map(x => x.t); }")
        check('it remembers what you said about your work, to raise later', mem and 'your chapter' in mem[0], mem)

        # ---- the pane, beside the writing, on the thesis example
        await pg.evaluate("() => { dirtyFile = false; PREFS.orcDay = ''; }")
        await pg.evaluate("() => openStarter('thesis')"); await pg.wait_for_timeout(1500)
        pg.on('request', lambda r: net.append(r.url) if r.url.startswith('http') else None)
        await pg.evaluate("() => switchTab('research')")
        await pg.click('#btnOracle'); await pg.wait_for_timeout(400)
        pane = await pg.evaluate("() => ({ split: SPLIT.on && SPLIT.view === 'oracle', tab: $('#spTabs [data-sv=oracle]').classList.contains('on'), focus: document.activeElement && document.activeElement.id, first: ORC.log[0] && ORC.log[0].text, pop: $('#spPop').classList.contains('hidden') })")
        check('The Oracle opens beside the writing, ready to type', pane['split'] and pane['tab'] and pane['focus'] == 'orcIn', pane)
        check('the first visit of the day is a check-in: next steps, open questions, words', 'question' in pane['first'] and 'words of' in pane['first'] and 'What are you working on today?' in pane['first'], pane['first'])
        async def say(t):
            await pg.fill('#orcIn', t); await pg.press('#orcIn', 'Enter'); await pg.wait_for_timeout(120)
            return await pg.evaluate("() => ORC.log[ORC.log.length - 1].text")
        async def say_html(t):
            await say(t); return await pg.evaluate("() => ORC.log[ORC.log.length - 1].html")

        # answers from the project
        a = await say('what have I written about Xenophon?')
        n = await pg.evaluate("() => { const r = aboutSearch('Xenophon'); return { notes: r.notes.length, paras: r.paras.length, sources: r.sources.length }; }")
        check('“what have I written about…” counts what the project holds', 'On Xenophon you have' in a and f"{n['paras']} paragraph" in a, (a[:200], n))
        before = await pg.evaluate("() => $$('#orcLog [data-oa]').length")
        await pg.click('#orcLog .orc-m.or:last-child [data-oa].primary-soft'); await pg.wait_for_timeout(300)
        dk = await pg.evaluate("() => ({ view: deskView, sel: deskSel, on: deskOn })")
        check('…with buttons to open what it found, and everything about it on the research desk', before > 1 and dk['view'] == 'about' and dk['sel'] == 'Xenophon' and dk['on'], dk)
        await pg.evaluate("() => { if (deskOn && !deskInSplit) closeDesk(); }")
        a = await say('tell me about purple elephants')
        check('…and says plainly when there is nothing', 'You haven’t written anything about' in a, a)

        # counts and status
        need = await pg.evaluate("() => claimRows().filter(x => x.c.status === 'need').length")
        a = await say('how many claims need a source?')
        check('how many claims need a source', a.startswith(f'{need} claim') and 'need' in a, a)
        a = await say("what's open?")
        qs = await pg.evaluate("() => qItems().filter(i => i.status !== 'answered').length")
        check('what’s open lists the open questions', f'{qs} question' in a, a)
        await pg.evaluate("() => { P.sources[0].osint = Object.assign({}, P.sources[0].osint, { rating: 'D3' }); }")
        a = await say('which sources are rated D or E?')
        check('which sources are weak', a.startswith('1 source is rated D, E or F') and 'D3' in a, a)
        a = await say('how far am I from my word goal?')
        check('how far from the word goal', re.search(r'[\d,]+ words of [\d,]+', a) is not None, a)
        a = await say('next steps?')
        check('next steps come from the journal', 'Your next steps' in a or 'no next steps' in a, a)
        await pg.evaluate("() => { editor.insertAdjacentHTML('beforeend', '<p>The ration was TK pounds a day.</p>'); syncEditor(); }")
        a = await say('any TKs?')
        check('TKs and flags in the drafts', re.search(r'\d+ (gap|gaps) (is|are) flagged', a) is not None, a)
        a = await say('how many notes')
        check('plain counts', a == f"You have {await pg.evaluate('() => P.notes.length')} notes.", a)

        # saving what you say
        nb = await pg.evaluate("() => P.notes.length")
        a = await say('note: check the grain figures against the 1916 census')
        nn = await pg.evaluate("() => { const n = P.notes[P.notes.length - 1]; return { n: P.notes.length, body: n.body, tags: n.tags }; }")
        check('“note: …” saves a note, tagged', nn['n'] == nb + 1 and nn['body'] == 'check the grain figures against the 1916 census' and 'oracle' in nn['tags'] and a.startswith('Saved as a note'), (nn, a))
        await pg.click('#orcLog .orc-m.or:last-child [data-oa]:nth-of-type(2)'); await pg.wait_for_timeout(150)
        check('…and Undo takes it back', await pg.evaluate("() => P.notes.length") == nb)
        await say('I suspect the halts were set by the grain, not the generals')
        a = await say('save that as a question')
        q = await pg.evaluate("() => qItems().map(i => i.title)")
        check('“save that as a question” keeps what you just said as an open question', 'I suspect the halts were set by the grain, not the generals' in q and a.startswith('Saved as an open question'), (q, a))
        hb = await pg.evaluate("() => jr().hypotheses.length")
        await say('hypothesis: the army moved fastest where it could not forage')
        check('“hypothesis: …” adds a hypothesis to the journal', await pg.evaluate("() => jr().hypotheses.length") == hb + 1)
        await say('next step: read Lee 2007 on the Carduchian passes')
        check('“next step: …” logs a next step', await pg.evaluate("() => jr().log.some(e => e.kind === 'next' && e.text.startsWith('read Lee 2007'))"))

        # arguing the other side
        a = await say('argue the other side: the blockade caused the famine')
        st = await pg.evaluate("() => ({ mode: ORC.mode, claim: ORC.claim })")
        check('“argue the other side” takes the claim and pushes back', st == {'mode': 'devil', 'claim': 'the blockade caused the famine'} and '“the blockade caused the famine”' in a and 'Your move' in a, (st, a))
        a2 = await say('the records are clear about it')
        check('…every answer gets another objection', a2 != a and len(a2) > 30 and await pg.evaluate("() => ORC.mode") == 'devil', a2)
        a3 = await say('stop')
        check('…until you say stop', await pg.evaluate("() => ORC.mode") == '' and 'round' in a3, a3)
        voice = await pg.evaluate("() => orcStem('Am I assuming ___ knew what I know now?', '“X”')")
        check('borrowed Socrates stems are asked of you, not of itself', voice == 'Are you assuming “X” knew what you know now?', voice)

        # nudges: circling
        await say("I'm not sure the figures hold")
        await say('no idea honestly')
        h = await say_html("I don't know where to go from here")
        check('after three “not sure”s it suggests something concrete', 'orc-nudge' in h and 'not sure 3 times' in h, h[:300])

        # consult on a passage, from the Mark menu (Ctrl+Alt+G, then O)
        await pg.evaluate("""() => { editor.insertAdjacentHTML('beforeend', '<p id=\"cx\">The army probably lost 4,000 men in the passes, because the Carduchians clearly controlled every ridge.</p>'); syncEditor();
            const p = $('#cx'), r = document.createRange(); r.selectNodeContents(p); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); editor.focus(); }""")
        await pg.keyboard.press('Control+Alt+KeyG'); await pg.wait_for_timeout(150); await pg.keyboard.press('o'); await pg.wait_for_timeout(300)
        c = await pg.evaluate("() => ({ you: ORC.log[ORC.log.length - 2].text, or: ORC.log[ORC.log.length - 1].text, n: $$('#orcLog .orc-m.or:last-child ol li').length })")
        check('Consult the Oracle reads the selected passage back', 'The army probably lost 4,000 men' in c['you'], c['you'])
        check('…with questions on its sources, numbers, hedges, absolutes and causes', c['n'] >= 4 and 'Nothing here is cited' in c['or'] and '4,000' in c['or'] and '“probably”' in c['or'] and '“clearly”' in c['or'] and '“because”' in c['or'], c)

        # the day: check in, done for today, the log, a Delphic sign-off
        a = await say('check in')
        check('“check in” lists what’s waiting', 'What are you working on today?' in a, a)
        a = await say('done for today')
        check('“done for today” asks what you did', 'what did you get done today' in a, a)
        a = await say('drafted the section on the passes')
        logged = await pg.evaluate("() => jr().log.some(e => e.kind === 'did' && e.text === 'drafted the section on the passes' && e.tags.includes('oracle'))")
        sign = await pg.evaluate("() => ORC.log[ORC.log.length - 1].html")
        check('…logs it in the journal', logged)
        check('…and signs off with a maxim carved at Delphi', 'orc-max' in sign and any(g in sign for g in ['Γνῶθι σεαυτόν', 'Μηδὲν ἄγαν', 'Ἐγγύα']), sign[:300])

        # saving the conversation, starting fresh
        jb = await pg.evaluate("() => jr().log.length")
        await pg.click('#orcSave'); await pg.wait_for_timeout(150)
        tr = await pg.evaluate("() => { const e = jr().log[jr().log.length - 1]; return { n: jr().log.length, text: e.text }; }")
        check('Save to journal files the conversation as a dated entry', tr['n'] == jb + 1 and tr['text'].startswith('Talked it through with the Oracle.') and 'You: argue the other side' in tr['text'] and 'Oracle:' in tr['text'], tr['text'][:200])
        await pg.click('#orcNew'); await pg.wait_for_timeout(150)
        fresh = await pg.evaluate("() => ({ n: ORC.log.length, mem: ORC.mem.length, mode: ORC.mode, first: ORC.log[0].text })")
        check('New starts a fresh conversation, remembering nothing', fresh['n'] == 1 and fresh['mem'] == 0 and fresh['mode'] == '' and any(x in fresh['first'] for x in ['The oracle has read your notes', 'The oracle is listening', 'answer will be your own']), fresh)
        a = await say('help')
        check('help lists what it can do', 'Check in' in a and 'Argue the other side' in a and 'Consult the Oracle' in a, a[:200])
        a = await say('hello')
        check('it answers small talk', 'working on' in a or 'leave off' in a, a)

        # ---- 2.3: talking like a person, not a form
        await say('argue the other side: the army lived off the land'); await say('stop')
        await pg.evaluate("() => { ORC.asked = 'Is it the research that is stuck, or the writing?'; }")
        a = await say('yes')
        check('a bare yes to an either-or question asks which', 'which' in a.lower(), a)
        await pg.evaluate("() => { ORC.asked = 'Does the source say so?'; }")
        a = await say('hmm')
        check('a hmm gets patience, not a non sequitur', any(x in a for x in ['Take your time', 'No hurry', 'Mm.', 'Still here']), a)
        a = await say('thanks')
        check('thanks is answered as thanks', any(x in a for x in ['welcome', 'Any time', 'Glad to']), a)
        a = await say("I'm so tired of this chapter")
        check('it acknowledges a feeling before asking', any(x in a for x in ['late', 'small', 'Tired is information']) and '?' in a, a)
        a = await say('why do you keep asking me questions?')
        check('it explains itself honestly when asked why it only asks questions', 'not an AI' in a or 'can’t think' in a or 'Socrates' in a, a)
        a = await say('Lee says the army was a moving city')
        check('it knows a source’s author by name and asks whether the author says it', 'Lee is in your sources' in a and 'in so many words' in a and 'Open the source' in a, a)
        a = await say('I agree with Lee')
        check('agreeing with an author asks who would push back', 'push back' in a, a)
        await say('the generals were seized and everything changed after that')
        await say('my advisor thinks the chapter is too long')
        a = await say('the generals were seized and everything changed after that')
        check('it notices when you repeat yourself', 'before' in a or 'second time' in a or 'keep coming back' in a, a)
        a = await say('what do you think?')
        check('asked its opinion, it reads back what you said instead', 'only your words' in a and 'moving city' in a, a)
        a = await say('Could don’t be a problem with the decide word')
        check('it doesn’t drop a passing word into a question', 'decide' not in a.split('?')[0].lower() or 'decide' in a.lower().split('could')[0], a)
        reps = await pg.evaluate("() => { const o = ORC.log.filter(m => m.who === 'oracle').slice(-8).map(m => m.text); return o.length - new Set(o).size; }")
        check('it doesn’t repeat a reply within a few turns', reps == 0, reps)

        # ---- 2.4: more phrasing, the project searched, picking up, Socrates' dialogue
        st = await pg.evaluate("() => [wstem('contradiction'), wstem('contradicting'), wstem('contradicts'), wstem('frustration'), wstem('frustrated')]")
        check('word endings come off: contradiction, contradicting, contradicts are one word', len(set(st[:3])) == 1 and st[3] == st[4], st)
        a = await say("I'm so frustated with the sources")
        check('a typo in a feeling is still understood', 'maddening' in a or 'care about getting it right' in a, a)
        a = await say("I'm not tired at all, just slow")
        check('"not tired" is not tired', 'late' not in a and 'Tired is information' not in a and 'keep it small' not in a, a)
        a = await say("I don't agree with Lee")
        check('"don’t agree with" is disagreement', 'part ways' in a, a)
        a = await say('I spent the morning reading. The figures for grain do not add up. Engels and Lee contradict each other by half.')
        check('a long message is answered at its most telling sentence', 'part ways' in a or 'counting different things' in a or 'closer to the events' in a or 'both be right' in a, a)
        mem = await pg.evaluate("() => ORC.mem.map(x => x.t).join(' | ')")
        check('the rest of a long message is kept to come back to', 'figures for grain' in mem or 'morning reading' in mem, mem)
        rel = await pg.evaluate("() => { const h = zxFind('how much grain did each soldier carry on the march', { kinds: ['note', 'source'], n: 3 }); return h.map(x => x.it.k + ':' + x.it.title.slice(0, 40)); }")
        check('the project search finds notes and sources close in words', len(rel) > 0, rel)
        bare = await pg.evaluate("() => zxBuild().items.filter(i => i.k === 'para').map(i => i.cited).filter(x => !x).length > 0 && zxBuild().items.some(i => i.k === 'para' && i.cited)")
        check('the index knows which paragraphs have citations', bare)
        idx = await pg.evaluate("() => JSON.stringify(P).includes('\"tf\"') || 'ZX' in P")
        check('the search index is never saved in the project', not idx)
        await pg.evaluate("""() => { const d = new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10); jLog('did', 'Talked it through with the Oracle.\\n\\nOracle: hello\\nYou: I am working on the chapter about Cunaxa\\nYou: I can’t decide how to open the chapter\\nOracle: hm', { tags: ['oracle'], date: d }); }""")
        pick = await pg.evaluate("() => orcPickup()")
        check('it picks up from a conversation saved to the journal', 'Last time we talked' in pick and 'decide how to open' in pick and 'decided' in pick.lower(), pick)
        await pg.evaluate("() => { P.journal.log = P.journal.log.filter(e => !(e.tags || []).includes('oracle')); }")
        check('with nothing saved, there is nothing to pick up', await pg.evaluate("() => orcPickup() === ''"))
        v = await pg.evaluate("() => { const s = new Set(); for (let i = 0; i < 30; i++) s.add(vary('{a|b|c} and {d|e}')); return [...s].length; }")
        check('{a|b} in a line picks one of the choices', v >= 4, v)
        await say('examine: the army lived off the land'); await pg.wait_for_timeout(250)
        ex = await pg.evaluate("() => ({ open: $('#socDlg').open, talk: !$('#socTalk').hidden, claim: SX.claim, term: SX.term })")
        check('"examine:" hands a claim to Socrates’ dialogue', ex['open'] and ex['talk'] and ex['claim'] == 'the army lived off the land' and ex['term'] == 'lived off the land', ex)
        await pg.evaluate("() => $('#socDlg').close()")

        # the palette, the Mark menu entry, the split tab
        pal = await pg.evaluate("() => { openPalette(); $('#palQ').value = 'oracle'; $('#palQ').dispatchEvent(new Event('input')); return $$('#palList li').map(li => li.textContent).join('|'); }")
        check('the palette finds the Oracle', 'The Oracle: talk your research through' in pal and 'Consult the Oracle' in pal, pal[:200])
        await pg.keyboard.press('Escape')
        check('the Mark menu has Consult the Oracle', await pg.evaluate("() => !!$('#markMenu [data-m=orc]')"))
        check('the pop-out button is hidden for the Oracle', pane['pop'])
        check('the Oracle never touched the network', not net, net[:3])
        await b.close()
    check('no page errors', not errs, errs[:5])
    print('t43', 'OK' if ok else 'FAILED'); sys.exit(0 if ok else 1)

asyncio.run(main())
