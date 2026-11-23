# Changelog

All notable changes to Anabasis. Versions follow [semantic versioning](https://semver.org): a major version can change the project file format in ways older versions can’t read, a minor version adds features, and a patch fixes bugs.

## [Unreleased]

## [1.4.0] — 2026-11-23

### Added
- **Research journal**, a new Journal view on the research desk (and **＋ Today’s entry** in the Research tab):
  - **Research design**: purpose, research questions (shared with Plan and the Questions tab), methods, sources and data, scope and limitations, ethics and milestones.
  - **Hypotheses**: each with a status (untested, supported, mixed evidence, weakened, refuted), the question it answers, your reasoning, and the claims, notes and sources that support or challenge it. Every change of status asks what changed and is dated in the hypothesis’s history.
  - **Research log**: dated entries (did, found, decided, dead end, idea, question) with tags and links to claims, notes, sources and questions; filter by kind or tag, or search. Status changes and answered questions are recorded on their own.
  - **Search log**: where you searched, the terms and filters, results and how many you kept, with CSV download.
  - **Research memo** and **Methods appendix**: documents made from the journal, the appendix as back matter.
- The thesis and investigation examples include a filled-in journal.
- Everything about… searches the journal; journal deletions can be undone; new palette commands for each part.

## [1.3.0] — 2026-11-23

### Added
- **55 citation styles**, grouped by field in the style menu: Chicago 17th and 18th (with ibid., archives cited place first, or an annotated bibliography), MLA with notes, MHRA, New Hart's Rules, Oxford, SBL, APA 6th and annotated, APSA, AJPS, ISA, ASA, AAA, four Harvard variants, OSCOLA, Bluebook, AMA, NLM/Vancouver, CSE, Nature, Science, Cell, The Lancet, BMJ, ACS, RSC, APS, AIP, AGU, Springer, Elsevier, IEEE, ASCE and ISO 690.
- **Export references** (Sources → Export…) as BibTeX/BibLaTeX, RIS or CSL-JSON, for all sources or only those cited in the open document. Each source gets a stable, readable key (`tuchman1962guns`).
- **Pandoc / Quarto package** and **LaTeX package** exports: the document with citations as keys (`[@key, p. 12]` or `\autocite`), its bibliography, the citation style and its images, zipped with a README.
- **Suggest mode**: typing and deleting become suggestions signed with your name, to accept or reject one at a time or all at once, with undo. Word exports keep them as tracked changes; **Word import** brings tracked changes back as suggestions and Word comments as margin notes on the same words.
- **Example projects**: a thesis chapter, a long-form article, a white paper, a book proposal and an investigative piece, each with sources, notes, a plan, threads, claims, review keys and questions (New → Or open a finished example).
- **Listen**: read the draft aloud from the cursor with the system's voices, highlighting each sentence; pause, skip, speed and voice; note numbers and citations read only if you want them.
- **Your name** in Settings, used on suggestions and new margin notes.

### Changed
- The size budget is now 25 MB (the app is about 10 MB).
- Sources as CSL-JSON now use the same readable keys as the BibTeX export.

## [1.2.0] — 2026-11-23

### Added
- **Works on any screen.** The top bar, the document bar and the toolbar now adapt to the window: buttons that don't fit move into a **⋯** menu at the end of their bar, in order of how often they're needed, so every tool stays one tap away. Drafts, Record and Page setup, which were hidden on small screens before, are now always reachable.
- **Phones and tablets.** The sidebar is a drawer that a tap beside it closes, the page fills the screen, dialogs open full screen, touch targets are larger, and text fields no longer make iPhone zoom in.
- **Install on iPhone, iPad and Android.** The hosted copy on GitHub Pages can be added to the Home Screen (or installed from the browser menu). It opens full screen and works offline. The downloaded file is unchanged and still needs nothing.
- **Customize the toolbar.** Hide the buttons you don't use (they wait in the ⋯ menu, and their shortcuts keep working), or keep **Essentials only**.
- **Keyboard shortcuts sheet.** Press **?** when you're not typing, or Ctrl/⌘+/.
- **Undo for research marks.** Marking, unmarking and deleting a thread or question can be undone with Ctrl/⌘+Z, Redo with Ctrl/⌘+Shift+Z, or **Undo** in the message that appears.
- **Typewriter scrolling and paragraph dimming outside focus mode.** Turn them on from the toolbar's ⋯ menu, or choose in Settings whether they apply in focus mode only or always. Research marks can be hidden in focus mode.
- **☰ puts the sidebar away** on a wide screen too, for more room on the page.

### Changed
- **A refined map-sheet look.** One set of line icons replaces the mixed text symbols and emoji in the toolbar, document bar and sidebar; menus and popovers are framed like a map legend; the contour backdrop is quieter; empty lists and views show a small map vignette with what to do next; messages look like map labels and can carry an action.
- The document bar shows icons alone when space is short, with the names in tooltips and the ⋯ menu.
- Claim and question marks are drawn as lines under the text rather than as underlining, so the Underline and Strikethrough buttons no longer light up inside a marked claim.

## [1.1.0] — 2026-11-23

### Added
- **Research marks.** Select a passage and use **Mark** in the toolbar (or Ctrl/Cmd+Alt+G, then a letter). Marks can run across paragraphs and around citations, overlap, and travel with the text when you cut and paste. Click a marked passage to see and change its marks. They are saved with the draft and left out of every export.
  - **Threads** (T): named, colored highlights that follow a theme, argument or person through the whole piece. Step through a thread from the Research tab, read it straight through in manuscript order, or turn it into a working document.
  - **Claims** (C): a claims register. Anabasis finds the citations inside a claim or right after it and flags claims with no source, claims resting only on sources rated D–E or 4–5, and supported claims edited since they were checked. Statuses: not checked, supported, needs a source, contested, cut. Export a printable **fact-check sheet** with full citations, or a CSV.
  - **Review keys** (R): a passage to come back to, with a reason and a due date. Due keys appear in the Research tab and on Project home; mark them done or snooze them a week.
  - **Questions** (Q): link passages to open research questions (shared with Plan), and record what you've found.
- A **Research** tab in the sidebar: threads, the current document's claims, what's due for review, and open questions.
- The **research desk**: threads read through, the claims register, an **evidence grid** of claims against sources with each source's rating, review keys by due date, questions, and **Everything about…**, which gathers every paragraph, note, source and marked passage that mentions a name or term, including its other spellings from Names & spellings, and can make a dossier document from the results.
- Project home lists claims that need checking among the loose ends, and a **Due for review** card.
- File format: new top-level `threads`, `claims` and `reviewKeys`, and `span.rm` marks in document HTML (see docs/file-format.md). Older versions of Anabasis open these files and keep the marks as plain text spans.

## [1.0.4] — 2026-11-23

### Fixed
- Typing in the source form no longer freezes the page. Each pause used to rebuild the citation formatter, redraw every source and reformat the whole document (about two seconds on a large project). Now the formatter is reused, only the edited row and the preview are redrawn, and the document's notes update a moment after you stop typing, and only if it cites that source.
- Searching sources and notes, and find-in-all-documents, stay responsive on large projects (one pass to count citations, documents read once per search session, debounced lists).
- Returning to a chapter, or exporting it, reuses its formatted citations when nothing has changed.

### Added
- A typing-latency test (t28) that types in every field of a 120,000-word project and fails if the page freezes for more than a quarter of a second.

## [1.0.3] — 2026-11-23

### Added
- **Note text** in the citation window: your own words after a citation, in the same footnote or endnote. In author-date styles (APA, MLA, Chicago author-date) the parenthetical stays in the text and the note text becomes a numbered footnote. Carried through PDF, Word, ePub, HTML, Markdown and Substack exports, and the OSINT Style Guide.

## [1.0.2] — 2026-11-23

### Added
- An illustrated quick start, docs/quick-start.md, linked from the README and from Help. Its screenshots are regenerated by tools/guide/quickstart.py.

### Fixed
- The Outline checks now refresh after Anabasis itself changes the text (inserting a note or a citation), not only after typing.
- House style now checks paragraphs inside block quotes.
- Inserting a quotation that contains quotation marks no longer drops the last one; inner marks become single quotes.

## [1.0.1] — 2026-11-22

### Added
- An epigraph from Xenophon’s *Anabasis* at the top of Help.

## [1.0.0] — 2026-11-22

The first public release.

### Look
- The map-sheet design: the workspace is framed like a printed survey map, with neatlines around the desk, a legend of colored keys for Docs, Notes, Sources and Outline, and Alegreya for project names, headings and dialog titles.

### Writing and citing
- Word processor with headings, lists, tables, footnotes, figures, margin notes, focus mode, freewriting sprints and a revision lens.
- Citations in Chicago 18th (notes and bibliography, shortened notes, author-date), APA 7, MLA 9 and the OSINT Style Guide, through citeproc-js. Notes, *Ibid.* and the bibliography rebuild as you write.
- Sources by DOI, ISBN or web address, from BibTeX and RIS, or by hand, with Admiralty reliability ratings.
- Binder of documents and parts, manuscript compile, index, front and back matter templates, chronology and annotated bibliography.
- Drafts you name and compare side by side, and checkpoints of the whole project.
- Project home with goals, pace and loose ends, and a planning board for outlining before drafting.

### Research
- Notes board with piles, tags, pins and a timeline view; drag notes into a draft as quotes or paraphrases.
- PDF reader beside the draft, web clipper, Markdown import (Obsidian and similar), Word import with footnotes.
- Interview transcripts from .srt, .vtt, text or Word, turned into timed quote notes.

### Figures
- Charts: columns, bars, stacked, lines, areas, dot plots and small multiples, with event lines and shaded periods.
- Offline maps: countries, provinces for selected countries, rivers and lakes, markers, routes, arrows, hatched areas, scale bar and locator inset.
- Timelines from dated notes and relationship maps from your Names list. Every figure stays editable.

### Checks
- Acronyms, estimative language (ICD 203), corroboration, house style, accessibility, names and spellings, quotes against their notes, and paragraphs without a citation.
- Find and replace across all documents and notes, with a safety copy of each changed document.

### Publishing
- PDF with footnotes (Paged.js), Word (.docx) with real footnotes, ePub, HTML, Markdown and Substack.
- Promo kit: social threads with character counts, Substack subtitle and description, quote cards.
- Video-script mode with run time, A/V tables and a teleprompter.

### Safety and privacy
- One offline HTML file; no account, server or tracking.
- Optional password lock (AES-256-GCM, PBKDF2 600,000 iterations), checked by reading back before every locked save.
- Optional autosave to the project file (Chromium browsers) and backup to a private GitHub repository.
- Project files are versioned (format 2) and migrated on opening. Damaged files are repaired where possible, with a fallback to the browser’s copy. Files from newer versions open as a copy.
- Everything in an opened file is sanitized with DOMPurify, and a content security policy limits network access to citation lookups and GitHub.
- First-run tour and sample project.

[1.4.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.4.0
[1.3.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.3.0
[1.2.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.2.0
[1.1.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.1.0
[1.0.4]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.4
[1.0.3]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.3
[1.0.2]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.2
[1.0.1]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.1
[1.0.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.0
