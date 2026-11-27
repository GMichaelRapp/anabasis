import xml.dom.minidom, asyncio, json, zipfile, subprocess, os, time
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
T0=time.time()
import builtins
_p=print
def print(*a,**k): _p(f'[{time.time()-T0:5.1f}s]',*a,**k, flush=True)
from playwright.async_api import async_playwright
APP=HTTP + 'anabasis.html'
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,seenVersion:'99.0.0'}))}catch(e){}")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.goto(APP); await pg.wait_for_timeout(800)
    async def shot(path):
      try: await asyncio.wait_for(pg.screenshot(path=path), 15)
      except Exception as e: print('SCREENSHOT TIMEOUT', path)
    async def dl(click, path):
      async with pg.expect_download() as d: await click()
      f=await d.value; await f.save_as(path); return path
    # ---------- quote check
    await pg.evaluate("""()=>{ const n=newNote(); Object.assign(n,{title:'Tuchman on mobilization',kind:'quote',sourceId:P.sources[0].id,locator:'71',body:'Once the mobilization timetables began to run, no government could stop them without risking defeat in the opening battles.'}); P.notes.unshift(n); renderNoteList(); }""")
    await pg.click('#editor p >> nth=2'); await pg.keyboard.press('End')
    await pg.evaluate("insertNote(P.notes[0])"); await pg.wait_for_timeout(700)
    await pg.click('.tabs button[data-tab=outline]'); await pg.wait_for_timeout(300)
    print('quote ok:', await pg.inner_text('#quoteSum'))
    await pg.evaluate("""()=>{ const q=editor.querySelector('.qlink'); q.textContent='Once the mobilization timetables began to run … no government could stop them'; editor.dispatchEvent(new Event('input')); }"""); await pg.wait_for_timeout(900)
    print('ellipsis edit:', await pg.inner_text('#quoteSum'))
    await pg.evaluate("""()=>{ const q=editor.querySelector('.qlink'); q.textContent='Once the timetables began, no government could ever stop them'; editor.dispatchEvent(new Event('input')); }"""); await pg.wait_for_timeout(900)
    print('changed:', await pg.inner_text('#quoteSum'), '| list:', await pg.inner_text('#quoteList'))
    await pg.click('#quoteList [data-qa=diff]'); await pg.wait_for_timeout(200)
    print('diff:', (await pg.inner_html('#quoteList .diffbox'))[:200])
    await pg.click('#quoteList [data-qfix=restore]'); await pg.wait_for_timeout(1000)
    print('after restore:', await pg.inner_text('#quoteSum'))
    # ---------- names
    await pg.evaluate("""()=>{ P.entities.push({id:uid('e'),name:'Kyiv',kind:'place',variants:['Kiev'],note:''}); const p=document.createElement('p'); p.textContent='Troops neared Kiev, and Kiev braced. Prigozhin spoke; later Prigozhin and Prigozin met.'; editor.appendChild(p); editor.dispatchEvent(new Event('input')); }""")
    await pg.wait_for_timeout(900)
    print('names:', await pg.inner_text('#nameList'))
    await pg.click('#nameList [data-fix]'); await pg.wait_for_timeout(800)
    print('after fix has Kiev:', await pg.evaluate("editor.textContent.includes('Kiev ')"), '| Kyiv count', await pg.evaluate("(editor.textContent.match(/Kyiv/g)||[]).length"))
    await pg.click('#btnNames'); await pg.wait_for_timeout(300); print('suggestions:', (await pg.inner_text('#namesSug'))[:150]); await shot('x1.png'); await pg.click('#namesClose')
    # ---------- comments
    await pg.evaluate("""()=>{ const p=[...editor.querySelectorAll('p')].find(x=>x.textContent.startsWith('Plans built')); const tn=p.firstChild; const r=document.createRange(); r.setStart(tn,0); r.setEnd(tn,11); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    await pg.click('#btnComment'); await pg.wait_for_timeout(300); await pg.keyboard.type('Is "plans" the right word here?'); await pg.keyboard.press('Escape'); await pg.wait_for_timeout(800)
    print('comments:', await pg.inner_text('#cmtList'))
    await pg.click('#btnExport'); await dl(lambda: pg.click('[data-x=docx]'), 'cm.docx')
    z=zipfile.ZipFile('cm.docx'); print('docx has comments.xml:', 'word/comments.xml' in z.namelist(), '| comment text in xml:', 'right word' in z.read('word/comments.xml').decode() if 'word/comments.xml' in z.namelist() else None)
    # ---------- lens
    await pg.evaluate("""()=>{ const p=document.createElement('p'); p.textContent='The decision was made by the committee in a way that was arguably quite unusual, and the committee members who had been arguing about the committee procedures for many hours were basically exhausted by the time the vote was finally taken in the late evening session of the long meeting.'; editor.appendChild(p); editor.dispatchEvent(new Event('input')); }""")
    await pg.click('#btnLens'); await pg.wait_for_timeout(500)
    print('lens:', (await pg.inner_text('#lensBar')).replace('\n',' '))
    await shot('x2.png')
    await pg.click('#btnLens')
    # ---------- versions
    await pg.evaluate("openSaveDraft()"); await pg.fill('#sdName','Before cuts'); await pg.click('#sdOk')
    await pg.evaluate("""()=>{ editor.lastElementChild.remove(); const p=document.createElement('p'); p.textContent='A brand new closing paragraph.'; editor.appendChild(p); editor.dispatchEvent(new Event('input')); }"""); await pg.wait_for_timeout(500)
    await pg.click('#btnVersions'); await pg.wait_for_timeout(300)
    print('version diff:', (await pg.inner_text('#dfSum')).replace('\n',' ')); await shot('x3.png'); await pg.click('#dfBack')
    # ---------- transcript
    await pg.evaluate("openTranscript(P.sources[0].id)"); await pg.wait_for_timeout(200)
    await pg.fill('#trText', "Jane Doe  0:05\nThe plan assumed speed above everything.\nIt left no room for talks.\n[00:12:34] Interviewer: Why did that matter?\n[00:12:40] Jane Doe: Because once trains moved, diplomacy stopped.")
    await pg.wait_for_timeout(500)
    print('tr lines:', await pg.eval_on_selector_all('#trLines li','e=>e.map(x=>x.textContent)'))
    await pg.click('#trLines li >> nth=3'); await pg.click('#trQuote'); await pg.wait_for_timeout(200)
    nn = await pg.evaluate("JSON.stringify((({title,body,locator,label,kind})=>({title,body,locator,label,kind}))(P.notes[0]))"); print('tr note:', nn)
    await shot('x4.png'); await pg.click('#trClose')
    print('tr cite:', await pg.evaluate("previewCluster('chicago-notes-bibliography',[{id:P.notes[0].sourceId,locator:P.notes[0].locator,label:P.notes[0].label}])"))
    # ---------- bib/ris import
    await pg.set_input_files('#fileCsl','refs.bib'); await pg.wait_for_timeout(300)
    await pg.set_input_files('#fileCsl','refs.ris'); await pg.wait_for_timeout(300)
    print('imported:', await pg.evaluate("JSON.stringify(P.sources.slice(-5).map(s=>[s.csl.type,s.csl.title,(s.csl.author||[]).map(a=>a.family||a.literal).join('/'),JSON.stringify(s.csl.issued)]))"))
    # ---------- audit
    await pg.click('.tabs button[data-tab=sources]'); await pg.click('#btnSrcMore'); await pg.click('#btnAudit'); await pg.wait_for_timeout(300)
    print('audit rows:', await pg.eval_on_selector_all('table.audit tbody tr','e=>e.map(x=>x.innerText.replace(/\\s+/g," ").slice(0,80))'))
    await shot('x5.png'); await pg.click('#auClose')
    # ---------- timeline
    await pg.evaluate("""()=>{ const ds=['4 August 1914','1914-06-28','c. 1905','July 1914']; P.notes.slice(0,4).forEach((n,i)=>n.date=ds[i]); }""")
    await pg.evaluate("PREFS.boardGroup='timeline'; openBoard()"); await pg.wait_for_timeout(300)
    print('timeline:', await pg.eval_on_selector_all('.tl-date','e=>e.map(x=>x.textContent)'))
    await shot('x6.png')
    await pg.evaluate("PREFS.boardGroup='pile'; closeBoard()")
    # ---------- templates + manuscript + annotated bib
    await pg.click('.tabs button[data-tab=docs]')
    await pg.click('#btnTemplates'); await pg.click('#tplList [data-t=dedication]'); await pg.wait_for_timeout(300)
    await pg.click('#btnTemplates'); await pg.click('#tplList [data-t=acknowledgments]'); await pg.wait_for_timeout(300)
    await pg.evaluate("P.sources[0].annotation='The classic narrative account of August 1914.'")
    await pg.evaluate("annotatedBibliography(); 0"); await pg.wait_for_timeout(300); await pg.click('#askOk'); await pg.wait_for_timeout(400)
    print('annot doc:', (await pg.inner_text('#editor'))[:300].replace('\n',' | '))
    await pg.click('#btnManuscript'); await pg.check('#msNumber'); await pg.select_option('#msFormat','doc'); await pg.click('#msOk'); await pg.wait_for_timeout(600)
    print('ms headings:', await pg.eval_on_selector_all('#editor h1','e=>e.map(x=>x.textContent)'))
    msdoc = await pg.evaluate("curDoc().id")
    # paged pdf of manuscript-doc
    html = await pg.evaluate("exportPagedPDF(curDoc())")
    open(OUT + '/paged.html','w').write(html)
    p2=await ctx.new_page(); p2.on('pageerror', lambda e: errs.append('paged '+str(e)))
    await p2.goto(HTTP + 'paged.html'); await p2.wait_for_function("() => (document.querySelectorAll('.pagedjs_page').length>0 && !!document.querySelector('.pagedjs_pages'))", timeout=60000); await p2.wait_for_timeout(1500)
    print('paged pages:', await p2.eval_on_selector_all('.pagedjs_page','e=>e.length'), '| footnotes:', await p2.eval_on_selector_all('.pagedjs_footnote_area .fn-note','e=>e.length'))
    await p2.pdf(path='ms-paged.pdf', prefer_css_page_size=True); await p2.close()
    # epub of manuscript
    await pg.click('#btnManuscript'); await pg.select_option('#msFormat','epub'); await dl(lambda: pg.click('#msOk'), 'ms.epub')
    z=zipfile.ZipFile('ms.epub'); names=z.namelist(); info=z.infolist()[0]
    print('epub first:', info.filename, info.compress_type, '| files:', [n for n in names if n.endswith('.xhtml')])
    bad=[]
    for n in names:
      if n.endswith(('.xhtml','.opf','.ncx','.xml')):
        try: xml.dom.minidom.parseString(z.read(n))
        except Exception as e: bad.append((n,str(e)[:200]))
    print('xml errors:', bad)
    # word import: build docx with footnote via page's docx lib
    await pg.evaluate("""async()=>{ const D=docx; const d=new D.Document({footnotes:{1:{children:[new D.Paragraph('Imported note text.')]}},sections:[{children:[new D.Paragraph({heading:D.HeadingLevel.HEADING_1,children:[new D.TextRun('Imported Chapter')]}),new D.Paragraph({children:[new D.TextRun('Body with a note.'),new D.FootnoteReferenceRun(1),new D.TextRun({text:' Italic bit.',italics:true})]})]}]}); const blob=await D.Packer.toBlob(d); window.__f=new File([blob],'draft.docx'); }""")
    await pg.evaluate("importDocx(window.__f)"); await pg.wait_for_timeout(1500)
    print('word import:', await pg.input_value('#docTitle'), '|', await pg.inner_html('#editor'))
    # record
    await pg.click('#editor p >> nth=0'); await pg.keyboard.press('End'); await pg.keyboard.type(' adding several new words to count today', delay=5); await pg.wait_for_timeout(800)
    await pg.click('#btnRecord'); await pg.wait_for_timeout(300); print('record:', (await pg.inner_text('#recStats')).replace('\n',' '))
    await pg.select_option('#recDocs tr >> nth=0 >> select','drafting'); await pg.fill('#recDocs tr >> nth=0 >> input[type=date]','2026-11-23'); await pg.dispatch_event('#recDocs tr >> nth=0 >> input[type=date]','change')
    await shot('x7.png'); await pg.click('#recClose')
    print('binder meta:', (await pg.inner_text('#docList li.doc >> nth=0')).replace('\n',' | '))
    # save roundtrip
    j=json.loads(await pg.evaluate("projectJSON()"))
    print('saved keys:', 'entities' in j, len(j['entities']), 'stats' in j, sum(len(d.get('snapshots',[])) for d in j['docs']), sum(len(d.get('comments',[])) for d in j['docs']), any(s.get('transcript') for s in j['sources']), any(s.get('annotation') for s in j['sources']))
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
