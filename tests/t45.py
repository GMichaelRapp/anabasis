"""The wiki (docs/wiki/): every link between pages goes to a page that exists, every picture is there and
used, the sidebar lists every page, and every section of Help has a wiki page or is on the list still to write.
No browser needed."""
import html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WIKI = ROOT / 'docs' / 'wiki'

# Help section -> the wiki page that covers it in depth
COVER = {
    'Your privacy': 'Projects-and-Saving', 'Where things are': 'Getting-Started', 'Your screen & your toolbar': 'Getting-Started',
    'Getting sources in': 'Sources', 'Writing': 'Citations-and-Styles', 'Citation styles, Zotero, Pandoc & LaTeX': 'Citations-and-Styles',
    'OSINT Style Guide citations': 'Citations-and-Styles', 'Sources': 'Sources', 'Checking links': 'Sources', 'Credits & permissions': 'Sources',
    'Notecards & the board': 'Notes-and-the-Board', 'Notes': 'Notes-and-the-Board', 'PDF reader': 'Reading-PDFs',
    'The research journal': 'Research-Journal', 'Checking the draft': 'Checking-the-Draft', 'Acronyms, estimative language & scripts': 'Checking-the-Draft',
    'Listening to the draft': 'Checking-the-Draft', 'Saving': 'Projects-and-Saving', 'Saving & exporting': 'Exporting',
    'Copies for reviewers and submission': 'Exporting', 'Substack, imports, autosave & locking': 'Exporting', 'Project home': 'Getting-Started',
    'Example projects': 'Getting-Started', 'Checkpoints, transcripts & promotion': 'Projects-and-Saving',
}
# Help sections whose wiki pages are still to be written
PENDING = {
    'Drafting', 'Nonfiction tools', 'Cross-references', 'Equations', 'Charts, maps, timelines & relationships', 'Data & dashboards',
    'Data in the writing', 'Beside the writing & in other windows', 'Research: threads, claims, review keys & questions',
    'Settings for the screen', 'Getting-started tips', 'Co-writing and review', 'Suggest mode & working with editors', 'Drafts',
    'Figures, tables & the margin', 'Planning', 'Index', 'Binder & manuscripts', 'Keyboard', 'Open-source components',
}

ok = True
def check(name, cond, extra=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)

pages = {p.stem: p.read_text(encoding='utf-8') for p in WIKI.glob('*.md')}
content = {k: v for k, v in pages.items() if not k.startswith('_')}
check('the wiki has a home page, a sidebar and a footer', {'Home', '_Sidebar', '_Footer'} <= pages.keys(), sorted(pages))

# links between pages: [text](Page-Name) or [text](Page-Name#anchor), no .md, no spaces
bad, used_imgs = [], set()
for name, text in pages.items():
    for target in re.findall(r'\]\(([^)\s]+)\)', text):
        if re.match(r'(https?:|mailto:|#)', target): continue
        if target.startswith('images/'):
            used_imgs.add(target[len('images/'):])
            if not (WIKI / target).exists(): bad.append(f'{name}: missing picture {target}')
            continue
        page = target.split('#')[0]
        if page not in content: bad.append(f'{name}: link to {target}')
check('every link between wiki pages goes to a page that exists, and every picture is there', not bad, bad)
on_disk = {p.name for p in (WIKI / 'images').glob('*')}
check('every picture in docs/wiki/images is used on a page', on_disk <= used_imgs, sorted(on_disk - used_imgs))

# alt text on every picture
no_alt = [f'{n}: {m}' for n, t in pages.items() for m in re.findall(r'!\[\]\([^)]*\)', t)]
check('every picture has alt text', not no_alt, no_alt)

# the sidebar and the home page reach every page
side = set(re.findall(r'\]\(([A-Za-z-]+)\)', pages['_Sidebar']))
home = set(re.findall(r'\]\(([A-Za-z-]+)\)', pages['Home']))
missing = sorted(set(content) - {'Home'} - side)
check('the sidebar lists every page', not missing, missing)
check('the home page links to every page', not sorted(set(content) - {'Home'} - home), sorted(set(content) - {'Home'} - home))

# each content page ends with related pages
no_rel = [n for n, t in content.items() if n != 'Home' and '## Related pages' not in t]
check('every page ends with related pages', not no_rel, no_rel)

# Help coverage
shell = (ROOT / 'src' / 'shell.html').read_text(encoding='utf-8')
i = shell.index('id="helpDlg"')
heads = [html.unescape(re.sub(r'<[^>]+>', '', h)).strip() for h in re.findall(r'<h4>(.*?)</h4>', shell[i:shell.index('</dialog>', i)])]
check('Help still has its sections', len(heads) > 30, len(heads))
loose = [h for h in heads if h not in COVER and h not in PENDING]
check('every Help section has a wiki page, or is on the list still to write', not loose, loose)
gone = [h for h in list(COVER) + list(PENDING) if h not in heads]
check('the coverage list names only sections Help still has', not gone, gone)
wrong = [f'{h} -> {p}' for h, p in COVER.items() if p not in content]
check('every covering page exists', not wrong, wrong)
print(f'{len(content)} pages, {sum(len(t.split()) for t in content.values()):,} words, {len(on_disk)} pictures; '
      f'{sum(h in COVER for h in heads)} of {len(heads)} Help sections covered')

sys.exit(0 if ok else 1)
