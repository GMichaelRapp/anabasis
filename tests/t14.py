import asyncio, json, zipfile, re, sys
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
APP=sys.argv[1] if len(sys.argv)>1 else HTTP + 'anabasis.html'
CR={"DOI":"10.1080/00396338.2013.784469","type":"article-journal","title":"Why States Act through Proxies","author":[{"given":"Andrew","family":"Mumford"}],"container-title":"Survival","issued":{"date-parts":[[2013,4]]}}
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1500,'height':920}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    await ctx.route('https://doi.org/**', lambda r: r.fulfill(status=200, headers={'access-control-allow-origin':'*','content-type':'application/json'}, body=json.dumps(CR)))
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.goto(APP); await pg.wait_for_timeout(800)
    # ---- reader
    await pg.click('.tabs button[data-tab=sources]'); await pg.click('#btnReader'); await pg.wait_for_timeout(200)
    await pg.set_input_files('#filePdf','sample.pdf')
    await pg.wait_for_selector('.rd-page[data-n="2"] .textLayer span', timeout=20000)
    print('pages:', await pg.inner_text('#rdOf'), '| auto-link msg:', await pg.inner_text('#toast'), '| source:', await pg.evaluate("R.sourceId && P.sources.find(s=>s.id===R.sourceId).csl.title"))
    await pg.evaluate("goPage(3)"); await pg.wait_for_selector('.rd-page[data-n="4"] .textLayer span', timeout=20000)
    await pg.evaluate("""()=>{ const spans=[...document.querySelectorAll('.rd-page[data-n="3"] .textLayer span')].filter(s=>s.textContent.trim()); const r=document.createRange(); r.setStart(spans[0].firstChild,0); const last=spans[Math.min(1,spans.length-1)]; r.setEnd(last.firstChild,last.textContent.length); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    await pg.wait_for_timeout(400)
    print('selbar:', await pg.is_visible('#rdSelBar'), await pg.inner_text('#rdSelPage'))
    await pg.screenshot(path='r1.png')
    await pg.click('#rdSelBar [data-k=quote]'); await pg.wait_for_timeout(300)
    print('note:', await pg.evaluate("JSON.stringify((({title,body,locator,kind,sourceId})=>({title,body,locator,kind,src:P.sources.find(s=>s.id===sourceId).csl.title}))(P.notes[0]))"))
    await pg.fill('#rdOffset','1'); await pg.dispatch_event('#rdOffset','change')
    await pg.evaluate("""()=>{ const sp=[...document.querySelectorAll('.rd-page[data-n="4"] .textLayer span')].find(s=>s.textContent.trim()); const r=document.createRange(); r.selectNodeContents(sp); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }"""); await pg.wait_for_timeout(300)
    print('offset page:', await pg.inner_text('#rdSelPage'))
    await pg.fill('#rdFind','Wagner'); await pg.press('#rdFind','Enter'); await pg.wait_for_timeout(800)
    print('find:', await pg.inner_text('#rdFindN'), '| hits:', await pg.eval_on_selector_all('.rd-hit','e=>e.length'))
    print('stored pdf:', await pg.evaluate("pdfStore.get(R.sourceId).then(r=>!!(r&&r.buf&&r.buf.byteLength))"))
    await pg.click('#rdZoomIn'); await pg.wait_for_timeout(400); print('zoom:', await pg.inner_text('#rdZoom'))
    await pg.click('#rdClose')
    sid = await pg.evaluate("R.sourceId")
    await pg.evaluate(f"readSourcePdf('{sid}')"); await pg.wait_for_selector('.rd-page[data-n="1"] .textLayer span', timeout=20000); print('reopen from source ok:', await pg.inner_text('#rdName'))
    await pg.click('#rdClose')
    # ---- index
    await pg.click('#editor p >> nth=1'); await pg.keyboard.press('End')
    await pg.keyboard.press('Control+Alt+KeyX'); await pg.wait_for_timeout(200)
    await pg.fill('#ixMain','Proxy war'); await pg.fill('#ixSub','deniability'); await pg.click('#ixOk'); await pg.wait_for_timeout(300)
    print('markers:', await pg.eval_on_selector_all('#editor .ixm','e=>e.map(x=>x.dataset.ix)'))
    await pg.evaluate("""()=>{ P.indexTerms.push({id:uid('x'),term:'Tuchman',sub:'',match:[],see:'',seeAlso:'Schlieffen Plan'}); P.indexTerms.push({id:uid('x'),term:'Schlieffen Plan',sub:'',match:['mobilization'],see:'',seeAlso:''}); P.entities.push({id:uid('e'),name:'Barbara Tuchman',kind:'person',variants:[],note:''}); P.indexOpts.names=true; const d=curDoc(); d.layout.index=true; markDirty(); }""")
    await pg.click('.tabs button[data-tab=outline]'); await pg.wait_for_timeout(200); print('outline ix:', await pg.inner_text('#ixSum'))
    await pg.click('#btnIndexMgr'); await pg.click('#ixPreview'); await pg.wait_for_timeout(200); print('preview:', (await pg.inner_text('#ixPrev')).replace('\n',' | ')); await pg.screenshot(path='r2.png'); await pg.click('#ixManClose')
    # paged with index
    html=await pg.evaluate("exportPagedPDF(curDoc())"); open(OUT + '/paged2.html','w').write(html)
    p2=await ctx.new_page(); await p2.goto(HTTP + 'paged2.html'); await p2.wait_for_function("document.querySelectorAll('.pagedjs_page').length>0 && document.querySelector('.ix-refs') && !document.querySelector('.ix-refs a')", timeout=60000)
    print('paged index:', (await p2.inner_text('.ix-body')).replace('\n',' | ')); await p2.pdf(path='ix.pdf', prefer_css_page_size=True); await p2.close()
    # docx with index
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=docx]')
    f=await d.value; await f.save_as('ix.docx'); z=zipfile.ZipFile('ix.docx'); xml=z.read('word/document.xml').decode()
    print('docx XE:', len(re.findall(r'XE &quot;|XE "', xml)), '| INDEX field:', 'INDEX \\e' in xml or 'INDEX \\\\e' in xml, '| updateFields:', 'updateFields' in z.read('word/settings.xml').decode())
    # epub + html
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=epub]')
    f=await d.value; await f.save_as('ix.epub'); z=zipfile.ZipFile('ix.epub'); ixx=z.read('OEBPS/index.xhtml').decode() if 'OEBPS/index.xhtml' in z.namelist() else ''
    print('epub index links:', re.findall(r'href="(c\d\.xhtml#ix\d+)"', ixx)[:3])
    # ---- start fresh (blank)
    await pg.click('#btnSettings'); await pg.click('#btnFresh'); await pg.wait_for_timeout(200); await pg.screenshot(path='r3.png')
    async with pg.expect_download() as d: await pg.click('#frOk')
    f=await d.value; print('backup:', f.suggested_filename)
    await pg.wait_for_timeout(400)
    print('after blank:', await pg.evaluate("JSON.stringify([P.docs.length,P.notes.length,P.sources.length,editor.textContent.length])"), '| pdfs left:', await pg.evaluate("pdfStore.keys().then(k=>k.filter(x=>String(x).startsWith('pdf:')).length)"))
    # ---- erase everything
    await pg.evaluate("P.notes.push(newNote()); markDirty()"); await pg.wait_for_timeout(900)
    await pg.click('#btnSettings'); await pg.click('#btnFresh'); await pg.check('#freshDlg input[value=all]'); await pg.uncheck('#frBackup'); await pg.click('#frOk')
    await pg.wait_for_timeout(2500)
    print('after erase:', await pg.evaluate("JSON.stringify([P.docs.length,P.notes.length,P.sources.length, P.docs[0].title])"), '| prefs:', await pg.evaluate("localStorage.getItem('commonplace.prefs')"))
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
