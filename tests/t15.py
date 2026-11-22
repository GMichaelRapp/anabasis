import asyncio
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1500,'height':920}); errs=[]
    await pg.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.goto(URL); await pg.wait_for_timeout(700)
    await pg.click('.tabs button[data-tab=sources]'); await pg.click('#btnReader'); await pg.set_input_files('#filePdf','sample.pdf')
    try:
      await pg.wait_for_selector('.rd-page[data-n="1"] .textLayer span', timeout=20000); print('file:// reader OK')
    except Exception as e: print('file:// reader FAILED', await pg.inner_text('#rdPages'))
    await pg.screenshot(path='r4.png')
    print(errs); await b.close()
asyncio.run(main())
