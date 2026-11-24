"""2.0: co-writing without a server. Send a copy, the collaborator edits it in their own browser, take the
changes back: their edits arrive as suggestions under their name, new material is added, paragraphs you both
changed are decided side by side, a safety copy is kept, and a second round compares from what came back."""
import asyncio, json, pathlib, re, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

PARAS = ['First paragraph about supply.', 'Second paragraph has old words in it.', 'Third paragraph stays.', 'Fourth paragraph will be cut.', 'Fifth paragraph is followed by something new.', 'Sixth paragraph both of us edit.']


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        me = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await me.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Mike'}))")
        pg = await me.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("""paras => { P.docs.splice(1); const d = P.docs[0]; d.title = 'Chapter one'; editor.innerHTML = '<h1>Supply</h1>' + paras.map(t => '<p>' + t + '</p>').join('') + eqHTML('a = b', true, true) + '<p>Last.</p>'; syncEditor();
          P.notes.push(Object.assign(newNote(), { id: 'n-mine', title: 'My note', body: 'mine' })); markDirty(); }""", PARAS)
        await pg.evaluate("() => openSendCopy()"); await pg.fill('#scTo', 'Dana'); await pg.fill('#scNote', 'Chapter one, please')
        async with pg.expect_download() as d: await pg.click('#scOk')
        dl = await d.value; copy_path = await dl.path(); copy = json.loads(open(copy_path).read())
        check('Send a copy saves a file named for them, marked as a copy, without what you’ve sent others', dl.suggested_filename.endswith(' - for Dana.json') and copy['copyOf']['to'] == 'Dana' and copy['copyOf']['from'] == 'Mike' and 'collab' not in copy)
        check('…and this project remembers what was sent', await pg.evaluate("() => P.collab.sent.length === 1 && P.collab.sent[0].to === 'Dana' && P.collab.sent[0].docs[0].html.includes('Fourth paragraph') && Array.isArray(P.collab.sent[0].colls.notes)"))

        # ---- Dana, in her own browser
        her = await b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        await her.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Dana'}))")
        hp = await her.new_page(); hp.on('pageerror', lambda e: errs.append('her: ' + str(e)))
        await hp.goto(URL); await hp.wait_for_timeout(1200)
        await hp.evaluate("t => loadProjectText(t, null, 'copy.json')", open(copy_path).read()); await hp.wait_for_timeout(800)
        check('the collaborator is told whose copy it is and what to do', 'copy of “' in await hp.inner_text('#toast') and 'from Mike' in await hp.inner_text('#toast') and 'Chapter one, please' in await hp.inner_text('#toast'))
        await hp.evaluate("""() => { const ps = editor.querySelectorAll('p');
          ps[1].textContent = 'Second paragraph has new words in it.';
          ps[0].innerHTML = 'First paragraph about <b>supply</b>.';
          ps[3].remove();
          ps[4].insertAdjacentHTML('afterend', '<p>A paragraph Dana added.</p>');
          ps[5].textContent = 'Sixth paragraph, as Dana sees it.';
          const eq = editor.querySelector('p.eq'); eq.setAttribute('data-tex', 'a = b + c'); eq.textContent = 'a = b + c';
          ps[4].innerHTML = 'Fifth paragraph is followed by <span class="cmt" data-cmt="c-dana">something</span> new.';
          curDoc().comments.push({ id: 'c-dana', text: 'Is this right?', author: 'Dana', date: nowISO() });
          syncEditor();
          P.notes.push(Object.assign(newNote(), { id: 'n-dana', title: 'Dana’s note', body: 'hers' }));
          P.sources.push({ id: 's-dana', csl: { type: 'book', title: 'Dana’s book' }, created: nowISO(), modified: nowISO() });
          const nd = newDoc('Dana’s appendix', '<p>Appendix text.</p>'); P.docs.push(nd);
          // something nasty, which opening must clean
          P.docs[0].html += '<p>Ok <img src=x onerror="window.__pwn=1"></p>';
          markDirty(); }""")
        theirs1 = await hp.evaluate("() => projectJSON()")
        p1 = pathlib.Path(OUT) / 'dana-1.json'; p1.write_text(theirs1, encoding='utf-8')

        # ---- meanwhile, me
        await pg.evaluate("""() => { const ps = editor.querySelectorAll('p');
          ps[2].textContent = 'Third paragraph stays, says Mike.';
          ps[5].textContent = 'Sixth paragraph, as Mike sees it.';
          editor.querySelector('h1').insertAdjacentHTML('afterend', '<p>Mike’s new opening.</p>');
          syncEditor(); }""")
        # ---- take changes back
        await pg.set_input_files('#fileTakeBack', str(p1)); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ open: $('#tkDlg').open, who: $('#tkWho').value, sum: $('#tkSum').innerText, conf: $$('#tkConf .tb-c').length, mine: $('#tkConf .tb-c') && $('#tkConf .tb-c .tb-text').innerText, theirs: $('#tkConf .tb-c') && $$('#tkConf .tb-c .tb-text')[1].innerText })")
        check('Take changes back matches the copy and names who made the changes', r['open'] and r['who'] == 'Dana' and 'Matched to the copy you sent Dana' in r['sum'], r['sum'])
        check('…sums up what came back: suggestions, a new document, notes, sources, a margin note', all(x in r['sum'] for x in ['Chapter one', 'suggestion', 'New document: Dana’s appendix', 'notes: 1 new', 'sources: 1 new', '1 margin note']), r['sum'])
        check('…and shows the paragraph you both changed, side by side', r['conf'] == 1 and 'as Mike sees it' in r['mine'] and 'as Dana sees it' in r['theirs'], r)
        await pg.check('#tkConf input[value=theirs]')
        await pg.click('#tkOk'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""() => { const ps = [...editor.children].map(e => ({ tag: e.nodeName, cls: e.className, html: e.innerHTML, text: e.textContent }));
          return { ps, by: [...new Set($$('ins.sg,del.sg', editor).map(x => x.dataset.by))], pwn: !!window.__pwn, imgOn: editor.innerHTML.includes('onerror'), snaps: curDoc().snapshots.filter(v => v.kind === 'safety').map(v => v.name), docs: P.docs.map(d => d.title), notes: P.notes.map(n => n.id), src: P.sources.some(s => s.id === 's-dana'), cm: curDoc().comments.some(c => c.id === 'c-dana'), toast: $('#toast').textContent }; }""")
        texts = [p['text'] for p in r['ps']]
        html = '\n'.join(p['html'] for p in r['ps'])
        check('their edits are suggestions under their name', r['by'] == ['Dana'], r['by'])
        check('…a changed word is a deletion and an insertion', '<del class="sg"' in r['ps'][3]['html'] and '>old</del>' in r['ps'][3]['html'] and '>new</ins>' in r['ps'][3]['html'], r['ps'][3]['html'])
        check('…bold they added comes in around the word', '<b><ins class="sg"' in r['ps'][2]['html'] or ('<b>' in r['ps'][2]['html'] and 'supply' in r['ps'][2]['html']), r['ps'][2]['html'])
        cut = [p for p in r['ps'] if 'Fourth paragraph' in p['text']][0]
        check('…a paragraph they cut is struck through, whole', 'sgb' in cut['cls'] and cut['html'].startswith('<del class="sg"'), cut)
        new = [p for p in r['ps'] if 'Dana added' in p['text']][0]
        check('…a paragraph they added is marked as added, whole', 'sgb' in new['cls'] and new['html'].startswith('<ins class="sg"'), new)
        check('your own edits stay as they are', texts[1] == 'Mike’s new opening.' and any(t.startswith('Third paragraph stays, says Mike') or 'says Mike' in t for t in texts), texts)
        six = [p for p in r['ps'] if 'Sixth' in p['text']][0]['html']
        check('the paragraph you both changed came in as their suggestions against yours, as chosen', 'Mike' in six and 'Dana' in six and '<del class="sg"' in six and '<ins class="sg"' in six, six)
        check('their margin note is added to the document', r['cm'] and 'data-cmt="c-dana"' in html)
        check('…the equation they changed is theirs', await pg.evaluate("() => editor.querySelector('p.eq').dataset.tex === 'a = b + c'"))
        check('notes, sources and a new document are added, nothing of yours lost', 'n-mine' in r['notes'] and 'n-dana' in r['notes'] and r['src'] and 'Dana’s appendix' in r['docs'] and 'Chapter one' in r['docs'])
        check('a safety copy was kept first', any('Dana' in s for s in r['snaps']), r['snaps'])
        check('nothing from their file ran', not r['pwn'] and not r['imgOn'])
        check('the report says what came in', 'Dana’s changes' in r['toast'] and 'suggestion' in r['toast'], r['toast'])
        # accepting gives their text; rejecting a cut paragraph keeps it whole
        await pg.evaluate("() => { const g = sgAll().find(g => g[0].closest('.sgb') && /Fourth/.test(g[0].textContent)); sgResolve(g, false); }")
        check('rejecting a cut keeps the paragraph, unmarked', await pg.evaluate("() => { const p = [...editor.children].find(e => /Fourth/.test(e.textContent)); return p && !p.classList.contains('sgb') && !p.querySelector('del.sg'); }"))
        await pg.evaluate("() => { const g = sgAll().find(g => g[0].closest('.sgb') && /Dana added/.test(g[0].textContent)); sgResolve(g, false); }")
        check('rejecting an added paragraph removes it, leaving no empty line', await pg.evaluate("() => ![...editor.children].some(e => /Dana added/.test(e.textContent)) && ![...editor.children].some(e => e.nodeName === 'P' && !e.textContent.trim() && !e.querySelector('br,img'))"))
        await pg.evaluate("() => { sgAll().forEach(g => sgResolve(g, true)); syncEditor(); }")
        texts = await pg.evaluate("() => [...editor.children].map(e => e.textContent)")
        check('accepting the rest gives their wording with yours kept', 'Second paragraph has new words in it.' in texts and 'Sixth paragraph, as Dana sees it.' in texts and 'Mike’s new opening.' in texts, texts)

        # ---- round two: Dana keeps going from her copy
        await hp.evaluate("() => { editor.querySelectorAll('p')[0].insertAdjacentHTML('beforebegin', '<p>Dana, round two.</p>'); syncEditor(); markDirty(); }")
        p2 = pathlib.Path(OUT) / 'dana-2.json'; p2.write_text(await hp.evaluate("() => projectJSON()"), encoding='utf-8')
        await pg.set_input_files('#fileTakeBack', str(p2)); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ sum: $('#tkSum').innerText, conf: $$('#tkConf .tb-c').length })")
        check('the second time, only what changed since is brought in', '1 suggestion' in r['sum'] and r['conf'] == 0 and 'New document' not in r['sum'] and 'notes:' not in r['sum'], r)
        await pg.click('#tkOk'); await pg.wait_for_timeout(600)
        check('…and it lands where she put it', await pg.evaluate("() => [...editor.querySelectorAll('ins.sg')].some(i => i.textContent === 'Dana, round two.')"))

        # ---- a file with no record of sending
        other = json.loads(theirs1); other.pop('copyOf', None); other['id'] = 'another-project'
        p3 = pathlib.Path(OUT) / 'stranger.json'; p3.write_text(json.dumps(other), encoding='utf-8')
        await pg.set_input_files('#fileTakeBack', str(p3)); await pg.wait_for_timeout(500)
        check('a file that isn’t a copy asks first', 'isn’t a copy of this project' in await pg.inner_text('#askDlg') if await pg.locator('#askDlg[open]').count() else False)
        await pg.click('#askOk'); await pg.wait_for_timeout(600)
        r = await pg.evaluate("() => ({ sum: $('#tkSum').innerText, who: $('#tkWho').value })")
        check('…then shows every difference as their suggestion, and asks whose', 'no record of sending' in r['sum'] and r['who'] == '', r)
        await pg.click('#tkCancel')
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
