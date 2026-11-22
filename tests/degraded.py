"""Run any test as an older or non-Chromium browser would see the page: no CSS Custom Highlight API,
no File System Access API, no ClipboardItem. Usage: python3 degraded.py t23.py"""
import runpy, sys
from playwright.async_api import Browser
INIT = ("try{Object.defineProperty(CSS,'highlights',{value:undefined,configurable:true})}catch(e){};"
        "delete window.Highlight; delete window.showSaveFilePicker; delete window.showOpenFilePicker; delete window.showDirectoryPicker; delete window.ClipboardItem;")
_nc, _np = Browser.new_context, Browser.new_page
async def nc(self, *a, **k):
    ctx = await _nc(self, *a, **k); await ctx.add_init_script(INIT); return ctx
async def np(self, *a, **k):
    pg = await _np(self, *a, **k); await pg.add_init_script(INIT); return pg
Browser.new_context, Browser.new_page = nc, np
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
