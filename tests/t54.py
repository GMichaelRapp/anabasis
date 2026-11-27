"""2.9.0: Socrates reads the draft, walks you through four more methods, asks new kinds of question, and remembers."""
import asyncio
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

PARA = ('<h1>The Retreat</h1><p>The march always followed the rivers, and the generals clearly knew the country. Hunger led to the mutiny at Trapezus. '
        'Some historians say the army numbered 10,000 men. It could be argued that the Persians let them go.</p>'
        '<p>The army reached the sea in 400 BCE and it was the largest Greek force ever to cross Anatolia.</p>'
        '<p>Xenophon describes the halt in detail.<span class="cite" data-items="[]">(Xenophon)</span> It was the first winter in the mountains.</p>')


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
        await pg.evaluate("(h) => { const d = newDoc('The Retreat', h); addDoc(d); renderDocList(); openDoc(d.id); }", PARA); await pg.wait_for_timeout(400)

        # ---- the deck: new kinds
        r = await pg.evaluate("(() => { const G = socData(); return { n: G.reduce((a, g) => a + g.stems.length, 0), kinds: G.length, ids: G.map(g => g.id) }; })()")
        check('Socrates has 475 questions in 24 kinds', r['n'] == 475 and r['kinds'] == 24, r)
        check('…with ethics, method, policy, the scholarly conversation, and scene and character', all(k in r['ids'] for k in ['ethics', 'method', 'policy', 'scholarship', 'scene']), r['ids'])
        r = await pg.evaluate("(() => { PREFS.tipsFor = { [P.id]: 'whitepaper' }; const p = socPool('claim').map(g => g.id); PREFS.tipsFor = { [P.id]: 'narrative' }; const q = socPool('person').map(g => g.id); PREFS.tipsFor = {}; return { wp: p.includes('policy'), nar: q.includes('scene') }; })()")
        check('…a white paper leans toward policy questions, a narrative toward scene and character', r == {'wp': True, 'nar': True}, r)

        # ---- question the draft
        await pg.evaluate("openSocScan()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ vis: !$('#socScan').hidden && $('#socDeck').hidden, list: SCAN.list.map(x => [x.k, x.hit]), head: $('#socScanHead').innerText, hl: CSS.highlights.has('soc-scan') })")
        kinds = [x[0] for x in r['list']]
        check('Question the draft finds places worth a question', r['vis'] and len(r['list']) >= 5 and 'worth a question' in r['head'], r)
        check('…sweeping words, certainty, claims of cause, unnamed authorities, hedges and facts without a source', all(k in kinds for k in ['sweep', 'cause', 'vague', 'hedge', 'nosource']), r['list'])
        check('…and shades them in the page', r['hl'])
        r = await pg.evaluate("SCAN.list.find(x => x.k === 'sweep')")
        check('…one finding a sentence, with the others noted', r['hit'] == 'always' and 'sure' in r['also'], r)
        check('…a cited paragraph has no “fact without a source”', not any(x[0] == 'nosource' and 'first winter' in str(x) for x in await pg.evaluate("SCAN.list.map(x => [x.k, x.s])")))
        await pg.evaluate("() => { $$('#socScanChips [data-sk]').find(b => b.dataset.sk === 'cause').click(); }"); await pg.wait_for_timeout(100)
        check('…filtered by kind', await pg.evaluate("$$('#socScanList [data-scq]').length") == 1)
        await pg.evaluate("$('#socScanList [data-scq]').click()"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ about: $('#socAbout').value, kind: $('#socKind').value, deck: !$('#socDeck').hidden, n: $$('#socCards li').length, range: !!socRange && socRange.toString().includes('Hunger led to') })")
        check('…“Questions about it” deals causation questions on that sentence', r['kind'] == 'causation' and 'hunger led to the mutiny' in r['about'].lower() and r['deck'] and r['n'] == 3 and r['range'], r)
        await pg.evaluate("openSocScan()"); await pg.select_option('#socScanScope', 'all'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("new Set(SCAN.list.map(x => x.docId)).size")
        check('…and can read every chapter', r >= 1)
        await pg.select_option('#socScanScope', 'doc')
        await pg.evaluate("$$('#socScanList [data-scg]')[0].click()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ open: $('#socDlg').open, sel: getSelection().toString(), hl: CSS.highlights.has('soc-scan') })")
        check('…“Go to it” selects the sentence', not r['open'] and len(r['sel']) > 20 and not r['hl'], r)

        # ---- walks
        await pg.evaluate("openSocrates({ fresh: true })"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("$$('#socWalks [data-walk]').map(b => b.textContent)")
        check('Four more walks under the questions', r == ['Steelman the other side', 'Pre-mortem', 'Competing explanations', 'Define your terms'], r)
        async def answer(*ts):
            for t in ts: await pg.evaluate("(t) => socTalkAnswer(t)", t); await pg.wait_for_timeout(60)
        await pg.evaluate("$('#socAbout').value = 'The army was shaped by hunger more than by its generals'; $$('#socWalks [data-walk]')[0].click()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ talk: !$('#socTalk').hidden, first: htmlToText(SX.log[1].html) })")
        check('Steelman starts from the selection, and asks who disagrees', r['talk'] and 'Who' in r['first'] and 'shaped by hunger' in r['first'], r)
        await answer('A historian of command', 'Leaders made the choices; hunger only limited them', 'It helps their case a little', 'The generals mattered at the crisis', 'Hunger set the options', 'Hunger set the options; the generals chose among them')
        r = await pg.evaluate("({ done: !$('#socDone').hidden, sum: $('#socDone dl').innerText, btn: $$('#socDone button').map(b => b.textContent) })")
        check('…and ends with the position before and after, what you concede, and their case', r['done'] and 'Your position now' in r['sum'] and 'Hunger set the options; the generals chose' in r['sum'] and 'What you concede' in r['sum'], r)
        n0 = await pg.evaluate("P.notes.length")
        await pg.evaluate("$$('#socDone [data-wkx]')[0].click(); $('#wkSave').click()"); await pg.wait_for_timeout(100)
        r = await pg.evaluate("(n0) => ({ note: P.notes.length === n0 + 1 && P.notes[0].tags.includes('counterargument'), j: jr().log.slice(-1)[0] })", n0)
        check('…their case can be kept as a note, and the walk saved to the journal', r['note'] and r['j']['text'].startswith('Steelman the other side with Socrates.') and 'steelman' in r['j']['tags'], r)

        await pg.evaluate("wkOpen('premortem', '')"); await pg.wait_for_timeout(100)
        await answer('this one', 'The argument about hunger is not proven', 'I never checked the numbers', 'The archive visit falls through')
        r = await pg.evaluate("htmlToText(SX.log[SX.log.length - 1].html)")
        check('Pre-mortem: three reasons it failed, then what the project itself shows', 'project' in r and ('source' in r or 'TK' in r or 'warnings' in r), r)
        await answer('Yes, the grain figure', 'Source the grain figure from Engels', 'Read Engels chapter 2 by Friday')
        r = await pg.evaluate("({ sum: $('#socDone dl').innerText })")
        check('…and ends with what to do first', '“The Retreat”' in r['sum'] and 'Read Engels chapter 2 by Friday' in r['sum'], r)
        await pg.evaluate("$$('#socDone [data-wkx]')[0].click()"); await pg.wait_for_timeout(80)
        check('…which can go on your next steps', await pg.evaluate("jr().log.some(e => e.kind === 'next' && e.text === 'Read Engels chapter 2 by Friday')"))

        await pg.evaluate("wkOpen('ach', 'Why did the army turn north?')"); await pg.wait_for_timeout(100)
        await answer('Food in the north')
        check('Competing explanations wants at least two', 'at least one more' in await pg.evaluate("htmlToText(SX.log[SX.log.length - 1].html)"))
        await answer('Food in the north\nOrders from Persia\nFear of the king', 'Villages had grain\nSatraps pursued them\nThe generals were seized')
        r = await pg.evaluate("({ cells: $$('#socLog [data-wkc]').length, form: $('#socForm').hidden })")
        check('…then a grid of evidence against each explanation', r == {'cells': 9, 'form': True}, r)
        await pg.evaluate("() => { const S = $$('#socLog [data-wkc]'); ['C','I','C', 'I','C','C', 'C','C','C'].forEach((v, i) => S[i].value = v); $('#socLog [data-wk=weigh]').click(); }"); await pg.wait_for_timeout(100)
        r = await pg.evaluate("htmlToText(SX.log[SX.log.length - 1].html)")
        check('…weighed by Heuer’s rule: least evidence against survives', 'Heuer' in r and r.index('Fear of the king: 0') < r.index('Food in the north: 1') and 'One piece of evidence fits every explanation' in r, r)
        await answer('Letters between the satraps')
        h0 = await pg.evaluate("jr().hypotheses.length")
        await pg.evaluate("$$('#socDone [data-wkx]')[0].click()"); await pg.wait_for_timeout(80)
        check('…and the explanations can become hypotheses in the journal', await pg.evaluate("jr().hypotheses.length") == h0 + 3)

        await pg.evaluate("wkOpen('define', 'army')"); await pg.wait_for_timeout(100)
        await answer('the soldiers under arms', 'the hoplites at Cunaxa', 'the camp followers')
        r = await pg.evaluate("htmlToText(SX.log[SX.log.length - 1].html)")
        check('Define your terms: finds how you already use the word', 'You use “army”' in r and 'Do they all mean what you just said?' in r, r)
        await answer('mostly, but not in chapter 3', 'the soldiers under arms, not their followers')
        check('…and keeps the definition', 'Definition' in await pg.evaluate("$('#socDone dl').innerText"))

        # ---- memory
        await pg.evaluate("$('#socDlg').close(); openSocrates({ fresh: true })"); await pg.wait_for_timeout(150)
        q = await pg.evaluate("(() => { const st = socDeal[0].s; socUse(0); return st; })()"); await pg.wait_for_timeout(150)
        await pg.evaluate("$('#qText').value = $('#qText').value.replace(/___/g, 'the march'); $('#qNew').click()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ n: (P.socq || []).length, qid: P.socq && P.socq[0].qid, has: P.socq && qItems().some(i => i.id === P.socq[0].qid) })")
        check('A question taken from Socrates is remembered with the project', r['n'] == 1 and r['has'], r)
        r = await pg.evaluate("(() => { const st = P.socq[0].st; let seen = 0; for (let i = 0; i < 30; i++) { socShuffle(); if (socDeal.some(d => (SOC_RAW.get(d.s) || d.s) === st)) seen++; } return seen; })()")
        check('…and not dealt again', r == 0, r)
        await pg.evaluate("() => { P.socq[0].at = new Date(Date.now() - 5 * 864e5).toISOString(); $('#socDlg').close(); openSocrates({ fresh: true }); }"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ vis: !$('#socMem').hidden, t: $('#socMem').innerText, foot: $('#socFoot').innerText })")
        check('…an old one still open comes back when you open Socrates', r['vis'] and 'still open' in r['t'] and '5 days ago' in r['t'] and '1 open, 0 answered' in r['foot'], r)
        await pg.evaluate("$('#socMem [data-sm=later]').click()"); await pg.wait_for_timeout(80)
        check('…“Not now” puts it off three days', await pg.evaluate("$('#socMem').hidden && !!P.socq[0].snooze"))
        r = await pg.evaluate("(() => { const n = normalize(JSON.parse(JSON.stringify(P))); return n.socq.length === 1 && n.socq[0].qid === P.socq[0].qid && n.socq[0].snooze === P.socq[0].snooze; })()")
        check('…all of it kept in the project file', r)

        bad = [e for e in errs if 'favicon' not in e]
        check('no page errors', not bad, bad[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
