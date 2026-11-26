"""2.7: writing in other languages (a document's language, a passage's language, quotation marks, citation terms,
right-to-left, counts by character, exports), translation notes and the translation journal with its glossary
check, transliteration, and the special-characters palette."""
import asyncio, json, re, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

TL_CASES = [
    ['ru-ala', 'Щербаков', 'Shcherbakov'], ['ru-ala', 'Юрий Гагарин', 'I͡uriĭ Gagarin'], ['ru-ala', 'Объединённые', 'Obʺedinënnye'], ['ru-ala', 'Эрмитаж', 'Ėrmitazh'], ['ru-ala', 'Царь', 'T͡sarʹ'],
    ['ru-bgn', 'Юрий', 'Yuriy'], ['ru-bgn', 'Елена', 'Yelena'], ['ru-bgn', 'Хрущёв', 'Khrushchëv'], ['ru-simple', 'Хрущёв', 'Khrushchyov'], ['ru-simple', 'Достоевский', 'Dostoyevskiy'],
    ['uk-nat', 'Згурський', 'Zghurskyi'], ['uk-nat', 'Київ', 'Kyiv'], ['uk-nat', 'Їжакевич', 'Yizhakevych'], ['uk-nat', 'Юрій', 'Yurii'], ['uk-nat', "Знам'янка", 'Znamianka'], ['uk-nat', 'Запоріжжя', 'Zaporizhzhia'],
    ['uk-ala', 'Київ', 'Kyïv'], ['bg', 'София', 'Sofia'], ['bg', 'Пловдив', 'Plovdiv'], ['sr', 'Љубљана', 'Ljubljana'], ['sr', 'Ђоковић', 'Đoković'],
    ['el', 'Αθήνα', 'Athina'], ['el', 'ευχαριστώ', 'efcharisto'], ['el', 'Μπακογιάννης', 'Bakogiannis'], ['el', 'Αύγουστος', 'Avgoustos'], ['el', 'Άγγελος', 'Angelos'],
    ['grc', 'Ξενοφῶν', 'Xenophōn'], ['grc', 'Ἀνάβασις', 'Anabasis'], ['grc', 'ἡμέρα', 'hēmera'], ['grc', 'ῥήτωρ', 'rhētōr'], ['grc', 'Εὐριπίδης', 'Euripidēs'], ['grc', 'αἷμα', 'haima'],
    ['grc', 'ἄγγελος', 'angelos'], ['grc', 'Ἡρόδοτος', 'Hērodotos'], ['grc', 'εὑρίσκω', 'heuriskō'], ['grc', 'τῷ', 'tōi'], ['grc', 'Πύρρος', 'Pyrrhos'],
    ['ar', 'مُحَمَّد', 'muḥammad'], ['ar', 'كِتَاب', 'kitāb'], ['ar', 'سُورَة', 'sūrah'], ['ar', 'أَحْمَد', 'aḥmad'], ['ar', 'بَيْت', 'bayt'],
]


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
        await ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---------- a document's language ----------
        await pg.evaluate("$('#btnPageSetup').click()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ v: $('#suLang').value, n: $$('#suLang option').length })")
        check('Page setup has a Language, English (US) by default, with two dozen others', r['v'] == 'en-US' and r['n'] >= 25, r)
        await pg.select_option('#suLang', 'de'); await pg.click('#suOk'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ lang: curDoc().lang, el: editor.getAttribute('lang'), dir: editor.dir })")
        check('…choosing German sets the document’s language and the editor’s, for the spell-checker', r == {'lang': 'de', 'el': 'de', 'dir': 'ltr'}, r)
        r = await pg.evaluate("""() => { const d = curDoc(); d.style = 'apa'; lastSig = ''; renderRefs(true);
            return new Promise(res => setTimeout(() => { const de = $('#refs').innerText; d.lang = ''; lastSig = ''; renderRefs(true);
              setTimeout(() => { const en = $('#refs').innerText; d.lang = 'de'; lastSig = ''; renderRefs(true); res({ de, en }); }, 400); }, 400)); }""")
        check('…citations use the language’s terms: “Übers.” in German where English has “Trans.”', '(R. Warner, Übers.)' in r['de'] and '(R. Warner, Trans.)' in r['en'], [r['de'][-300:], r['en'][-200:]])
        r = await pg.evaluate("() => { const d = curDoc(); d.lang = 'ar'; applyLayout($('#page'), d); return [editor.lang, editor.dir, $('#page').classList.contains('rtl')]; }")
        check('…Arabic, Hebrew, Persian and Urdu documents run right to left', r == ['ar', 'rtl', True], r)
        r = await pg.evaluate("() => { const d = curDoc(); d.lang = 'de'; applyLayout($('#page'), d); return [editor.dir, $('#page').classList.contains('rtl')]; }")
        check('…and back again', r == ['ltr', False], r)
        r = await pg.evaluate("[docQuotes().open, docQuotes().close, (curDoc().lang = 'fr', docQuotes().open), (curDoc().lang = 'ja', docQuotes().open + docQuotes().close), (curDoc().lang = 'de', 1)]")
        check('…quotation marks follow it: „…“ in German, « … » with no-break spaces in French, 「…」 in Japanese', r[0] == '„' and r[1] == '“' and r[2] == '« ' and r[3] == '「」', r)
        r = await pg.evaluate("""() => { const R = hsRules.call ? (P.house = Object.assign(HS_DEFAULT(), { quotes: true }), hsRules()) : []; const q = R.find(x => x.id === 'quotes'); const t = 'Er sagte "nein" dazu.';
            const out = t.replace(q.re, (...a) => { const m = a; m.index = a[a.length - 2]; return q.fix(m, t); }); return [q.label, out]; }""")
        check('…and Proofread’s straight-quote rule uses them', r[1] == 'Er sagte „nein“ dazu.' and '„' in r[0], r)
        r = await pg.evaluate("[wc('这是一个测试 and two'), wc('日本語のテスト'), wc('plain english words here')]")
        check('Chinese and Japanese are counted by character, as their publishers count', r == [8, 7, 4], r)
        r = await pg.evaluate("pxQuoted('Er sagte „das Heer zog weiter“ und mehr; il dit « encore » ici')")
        check('“Close to your notes” knows German and French quotation marks', len(r) == 2, r)

        # ---------- a passage's language ----------
        await pg.evaluate("""() => { const p = editor.querySelector('p'); p.insertAdjacentHTML('beforeend', ' Москва и Киев.'); const t = p.lastChild, i = t.data.indexOf('Москва');
            const r = document.createRange(); r.setStart(t, i); r.setEnd(t, i + 6); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
        await pg.evaluate("$('#markMenu [data-m=lang]').click()"); await pg.wait_for_timeout(150)
        check('Mark → Language of this passage…', await pg.evaluate("$('#lmDlg').open"))
        await pg.select_option('#lmLang', 'ru'); await pg.click('#lmOk'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ html: editor.querySelector('span[lang]')?.outerHTML, kept: sanitize(editor.innerHTML).includes('<span lang=\"ru\">Москва</span>') })")
        check('…wraps it in its language, which survives saving', r['html'] == '<span lang="ru">Москва</span>' and r['kept'], r)
        r = await pg.evaluate("sanitize('<p>x <span lang=\"he\">שלום</span> <span lang=\"bad lang\" style=\"font-weight:bold\">b</span></p>')")
        check('…a right-to-left passage gets its direction; nothing else on a span gets through', '<span lang="he" dir="rtl">שלום</span>' in r and 'bad lang' not in r, r)
        # exports carry the languages
        syncd = await pg.evaluate("() => { syncEditor(); return exportStandaloneHTML(curDoc()).slice(0, 80); }")
        check('Web export: <html lang="de">', '<html lang="de">' in syncd, syncd)
        async with pg.expect_download() as dl:
            await pg.evaluate("() => { syncEditor(); return exportDocx(curDoc()); }")
        d = await dl.value; path = OUT + '/lang.docx'; await d.save_as(path)
        z = zipfile.ZipFile(path); styles = z.read('word/styles.xml').decode(); body = z.read('word/document.xml').decode()
        check('Word export: German is the document’s language, Russian the passage’s', 'w:lang w:val="de"' in styles and re.search(r'<w:lang w:val="ru"/>.*?Москва', body, re.S), styles[styles.find('docDefaults'):][:300])

        # ---------- transliteration ----------
        bad = await pg.evaluate("cases => cases.filter(([s, i, w]) => transliterate(i, s) !== w.normalize('NFC')).map(([s, i, w]) => [s, i, transliterate(i, s), w])", TL_CASES)
        check(f'Transliteration: {len(TL_CASES)} names in Russian, Ukrainian, Bulgarian, Serbian, Greek and Arabic', not bad, bad)
        r = await pg.evaluate("[tlGuess('Ἀνάβασις'), tlGuess('Київ'), tlGuess('Москва'), tlGuess('Αθήνα'), tlGuess('القاهرة'), tlGuess('Beograd')]")
        check('…it recognizes the script (and Ukrainian by its letters)', r == ['grc', 'uk-nat', 'ru-ala', 'el', 'ar', ''], r)
        await pg.evaluate("""() => { const sp = editor.querySelector('span[lang=ru]'), r = document.createRange(); r.selectNodeContents(sp); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
        await pg.evaluate("$('#markMenu [data-m=tl]').click()"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ open: $('#trlDlg').open, sys: $('#trlSys').value, out: $('#trlOut').value, rep: !$('#trlReplace').disabled })")
        check('Mark → Transliterate… takes the selection and picks the system', r == {'open': True, 'sys': 'ru-ala', 'out': 'Moskva', 'rep': True}, r)
        await pg.select_option('#trlForm', 'both'); await pg.click('#trlReplace'); await pg.wait_for_timeout(200)
        check('…Replace puts “Moskva (Москва)” in the draft', 'Moskva (Москва)' in await pg.evaluate("editor.innerText"))
        await pg.evaluate("openTranslit('Ξενοφῶν')"); await pg.wait_for_timeout(150)
        await pg.click('#trlCopy'); await pg.wait_for_timeout(200)
        clip = await pg.evaluate("navigator.clipboard.readText()")
        check('…or Copy, from anything you paste (accents and breathings mark ancient Greek)', clip == 'Xenophōn (Ξενοφῶν)', clip)
        await pg.evaluate("$('#trlDlg').close(); $('#trlForm').value = 'only'; PREFS.tlForm = 'only'")
        r = await pg.evaluate("transliterate('محمد', 'ar')")
        check('…unvowelled Arabic gives only the letters on the page, and says so', r == 'mḥmd' and 'short vowels' in await pg.evaluate("TL.ar.note"), r)

        # ---------- special characters ----------
        await pg.evaluate("""() => { const p = editor.querySelector('p'), t = document.createTextNode(' Caf'); p.append(t); const r = document.createRange(); r.setStart(t, 4); r.collapse(true); editor.focus(); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
        await pg.keyboard.press('Control+Alt+KeyO'); await pg.wait_for_timeout(200)
        check('⌘/Ctrl Alt O opens the special characters beside the writing (not blocking it)', await pg.evaluate("$('#spcDlg').open && !$('#spcDlg').matches(':modal')"))
        await pg.evaluate("[...$$('#spcTabs [data-chset]')].find(b => b.dataset.chset === 'latin').click()"); await pg.wait_for_timeout(80)
        await pg.click('#spcGrid .chb[data-ch="é"]'); await pg.wait_for_timeout(150)
        r = await pg.evaluate("[editor.innerText.includes('Café'), document.activeElement === editor]")
        check('…a character goes in at the caret, and the caret stays in the draft', r == [True, True], r)
        await pg.keyboard.type(' crème')
        await pg.evaluate("[...$$('#spcTabs [data-chset]')].find(b => b.dataset.chset === 'poly').click()"); await pg.wait_for_timeout(80)
        for js in ["[...$$('#spcGrid [data-poly=v]')].find(b => b.dataset.v === 'ω').click()", "[...$$('#spcGrid [data-poly=br]')].find(b => b.dataset.v === '\\u0314').click()",
                   "[...$$('#spcGrid [data-poly=ac]')].find(b => b.dataset.v === '\\u0342').click()", "$('#spcGrid [data-poly=io]').click()"]:
            await pg.evaluate(js); await pg.wait_for_timeout(50)
        check('…polytonic Greek: ω + rough breathing + circumflex + iota subscript = ᾧ', await pg.evaluate("$('#spcGrid .chb.big').dataset.ch") == 'ᾧ')
        await pg.click('#spcGrid .chb.big'); await pg.wait_for_timeout(100)
        check('…inserted as one composed letter', 'crème ᾧ' in await pg.evaluate("editor.innerText.normalize('NFC')") or 'crèmeᾧ' in await pg.evaluate("editor.innerText.normalize('NFC')"))
        await pg.evaluate("[...$$('#spcTabs [data-chset]')].find(b => b.dataset.chset === 'recent').click()"); await pg.wait_for_timeout(80)
        check('…and Recent keeps what you used', await pg.evaluate("$$('#spcGrid .chb').map(b => b.dataset.ch).slice(0, 2).join('')") == 'ᾧé')
        await pg.evaluate("$('#spcDlg').close()")

        # ---------- translation notes ----------
        await pg.evaluate("""() => { const T = trj(); T.from = 'grc'; T.insert = 'note'; T.mine = true; const n = Object.assign(newNote(), { title: 'The halt', body: 'There they stayed three days.', sourceId: sortedSources()[0].id, locator: '4.5' });
            P.notes.unshift(n); renderNoteList(); openNote(n.id); }""")
        await pg.wait_for_timeout(200)
        await pg.select_option('#panelBody [data-n=kind]', 'translation'); await pg.wait_for_timeout(600)
        r = await pg.evaluate("({ orig: !!$('#nOrig'), lang: $('#nOrigLang')?.value, label: [...$$('#panelBody label')].some(l => l.textContent.startsWith('Translation')) })")
        check('A Translation note: original and its language beside your translation', r == {'orig': True, 'lang': 'grc', 'label': True}, r)
        await pg.fill('#nOrig', 'ἐνταῦθα ἔμειναν ἡμέρας τρεῖς'); await pg.wait_for_timeout(350)
        check('…the original takes its language, for the spell-checker and the screen reader', await pg.evaluate("$('#nOrig').lang") == 'grc')
        await pg.click('#panelBody [data-a=translit]'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ t: $('#nTranslit').value, saved: P.notes[0].translit, orig: P.notes[0].orig, ol: P.notes[0].origLang })")
        check('…Transliterate the original fills in the transliteration', r == {'t': 'entautha emeinan hēmeras treis', 'saved': 'entautha emeinan hēmeras treis', 'orig': 'ἐνταῦθα ἔμειναν ἡμέρας τρεῖς', 'ol': 'grc'}, r)
        await pg.evaluate("curDoc().lang = ''; applyLayout($('#page'), curDoc())")
        def ins_js(mode):
            return f"""() => {{ trj().insert = '{mode}'; const h = noteToHTML(P.notes[0]); const d = document.createElement('div'); d.innerHTML = h; const c = d.querySelector('.cite'); return {{ text: d.innerText, cnote: c ? c.dataset.cnote : null, span: !!d.querySelector('span[lang=grc]') }}; }}"""
        r = await pg.evaluate(ins_js('note'))
        check('…inserted: your translation in quotation marks; the original and “My translation.” in the citation’s note',
              r['text'].startswith('“There they stayed three days.”') and r['cnote'] == 'My translation. Original: “ἐνταῦθα ἔμειναν ἡμέρας τρεῖς”', r)
        r = await pg.evaluate(ins_js('brackets'))
        check('…or the original after it in brackets, marked as Greek', '[ἐνταῦθα ἔμειναν ἡμέρας τρεῖς]' in r['text'] and r['span'] and r['cnote'] == 'My translation.', r)
        r = await pg.evaluate(ins_js('orig'))
        check('…or the original in the text and your translation in the note', r['text'].startswith('“ἐνταῦθα') and 'Translation: “There they stayed three days.”' in r['cnote'], r)
        r = await pg.evaluate("() => { trj().insert = 'note'; const n = P.notes[0]; n.transBy = 'other'; n.translator = 'Rex Warner'; const d = document.createElement('div'); d.innerHTML = noteToHTML(n); n.transBy = 'me'; return d.querySelector('.cite').dataset.cnote; }")
        check('…someone else’s translation is credited: “Trans. Rex Warner.”', r.startswith('Trans. Rex Warner.'), r)
        r = await pg.evaluate("() => { const n = P.notes[0], s = n.sourceId; n.sourceId = ''; const d = document.createElement('div'); d.innerHTML = noteToHTML(n); n.sourceId = s; return d.querySelector('.fn')?.dataset.text; }")
        check('…with no source, the original goes in a footnote', r and 'Original:' in r, r)

        # ---------- translation journal and the glossary ----------
        await pg.evaluate("openJournal('trans')"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ on: $('.j-side li.on')?.innerText, from: $('#trFrom').value, sys: $('#trSys').value, btns: $('#deskTools').innerText })")
        check('Journal → Translation: languages, the transliteration system, how notes are inserted', r['on'].startswith('Translation') and r['from'] == 'grc' and r['sys'] == 'grc' and 'Note on translation' in r['btns'], r)
        await pg.fill('#tgTerm', 'ἐπιμελητής'); await pg.fill('#tgRender', 'quartermaster'); await pg.fill('#tgAvoid', 'supervisor, steward'); await pg.fill('#tgNote', 'the army office')
        await pg.click('#trAdd button[type=submit]'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ g: trj().glossary.map(g => [g.term, g.render, g.avoid]), row: $('.tr-gl tbody tr')?.innerText })")
        check('…add a term: original, rendering, renderings to avoid; the transliteration is shown', r['g'] == [['ἐπιμελητής', 'quartermaster', ['supervisor', 'steward']]] and 'epimelētēs' in r['row'], r)
        await pg.evaluate("() => { closeDesk(); const p = editor.querySelector('p'); p.append(' The steward counted the grain, and a supervisor checked it.'); editor.dispatchEvent(new Event('input')); }"); await pg.wait_for_timeout(1800)
        r = await pg.evaluate("({ n: $('#tgCount').textContent, items: $$('#tgList li').map(l => l.innerText), shown: !$('#tgHead').classList.contains('hidden') })")
        check('Outline → Translation glossary lists each avoided rendering in the draft', r['shown'] and r['n'] == '2' and '“steward” → quartermaster' in r['items'][0], r)
        await pg.evaluate("$('#tgList [data-tgfix=\"0\"]').click()"); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("[editor.innerText.includes('The quartermaster counted'), $('#tgCount').textContent]")
        check('…Replace swaps in your rendering', r == [True, '1'], r)
        P_note = await pg.evaluate("() => { const n = P.notes[0]; n.orig = 'ὁ ἐπιμελητὴς ἦλθεν'; n.body = 'The steward came.'; const T = trj(); T.glossary[0].term = 'ἐπιμελητὴς'; return trCounts()[T.glossary[0].id]; }")
        check('…and the journal counts uses, avoided forms and translation notes that differ', P_note['use'] >= 1 and P_note['avoid'] >= 1 and P_note['notes'] == 1, P_note)
        await pg.evaluate("openJournal('trans')"); await pg.wait_for_timeout(300)
        await pg.fill('#tdText', 'Kept “satrap” untranslated.'); await pg.click('#trDec button'); await pg.wait_for_timeout(300)
        check('…decisions go in the log, tagged translation', await pg.evaluate("jr().log.some(e => e.text === 'Kept “satrap” untranslated.' && e.tags.includes('translation') && e.kind === 'decided') && $('.tr-decs').innerText.includes('satrap')"))
        n0 = await pg.evaluate("P.docs.length")
        await pg.evaluate("$$('#deskTools [data-j]').find(b => b.textContent === 'Note on translation').click()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ n: P.docs.length, t: curDoc().title, role: curDoc().role, text: editor.innerText })")
        check('Note on translation: front matter saying whose translations, which transliteration, and the key renderings',
              r['n'] == n0 + 1 and r['t'] == 'A Note on Translation' and r['role'] == 'front' and 'Translations from the Greek (ancient) are my own' in r['text'] and 'Library of Congress' in r['text'] and '“quartermaster”' in r['text'], r['text'][:400])
        await pg.evaluate("openJournal('trans')"); await pg.wait_for_timeout(300)
        async with pg.expect_download() as dl:
            await pg.evaluate("$$('#deskTools [data-j]').find(b => b.textContent === 'CSV').click()")
        d = await dl.value; await d.save_as(OUT + '/gl.csv'); csv = open(OUT + '/gl.csv', encoding='utf-8-sig').read()
        check('…the glossary as a CSV', csv.startswith('"term","language","transliteration","rendering","avoid","why"') and 'quartermaster' in csv, csv[:200])
        await pg.evaluate("$$('#deskTools [data-j]').find(b => b.textContent === 'Glossary').click()"); await pg.wait_for_timeout(400)
        check('…and as back matter', await pg.evaluate("curDoc().title === 'Glossary' && curDoc().role === 'back' && editor.innerText.includes('quartermaster')"))

        # ---------- the project file ----------
        r = await pg.evaluate("""() => { const raw = JSON.parse(JSON.stringify(P)); raw.journal.trans.from = 'not a language!'; raw.journal.trans.insert = 'sideways'; raw.journal.trans.glossary.push({ term: '', render: 'x' }, 'junk'); raw.docs[0].lang = 'uk'; raw.docs[1].lang = '<script>';
            const x = normalize(raw), n = x.notes.find(n => n.kind === 'translation'); return { from: x.journal.trans.from, ins: x.journal.trans.insert, g: x.journal.trans.glossary.length, note: n && [n.orig, n.origLang, n.translit], lang: [x.docs[0].lang, x.docs[1].lang] }; }""")
        check('The project file keeps the languages, the glossary and translation notes; bad values are cleaned',
              r['from'] == '' and r['ins'] == 'note' and r['g'] == 1 and r['note'][1] == 'grc' and r['note'][2] and r['lang'] == ['uk', ''], r)
        r = await pg.evaluate("COMMANDS.map(c => c[0]).join('|')")
        check('The command search reaches all of it', all(x in r for x in ['Special characters', 'Transliterate', 'Language of this passage', 'Translation journal']), r[-500:])
        check('no errors', not errs, errs[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
