# Changelog

All notable changes to Anabasis. Versions follow [semantic versioning](https://semver.org): a major version can change the project file format in ways older versions can’t read, a minor version adds features, and a patch fixes bugs.

## [Unreleased]

## [2.3.0] — 2026-11-25

### Changed
- **The Oracle talks more like a person and less like a form.** Still no AI and nothing online: the additions are about 9 KB of patterns and replies.
  - It remembers what it just asked, so a short answer (“yes”, “no”, “maybe”, “hmm”, “fair enough”) is answered against that question, and an either-or question answered “yes” gets “Yes to which?”.
  - It answers when you talk about the talk: thanks, praise, “what do you think?” (it reads back what you’ve said and asks which you’d put your name to), “why do you keep asking questions?”, “are you an AI?”, and “you’re useless” (with a way out to the check-in, open questions or Socrates).
  - It acknowledges how you say you feel (tired, frustrated, worried, overwhelmed, discouraged, excited, bored) before asking anything, and knows when it’s late.
  - It notices when you repeat yourself, and asks what won’t let go.
  - It knows your sources’ authors by name: “Lee says the army was a moving city” gets “Does Lee say that in so many words? If so, note the page,” with a button to open the source; “I agree with Lee” asks who would push back.
  - Once in a long talk, or when you say “recap”, it reads back the claims you’ve made; after a long session it offers to save the conversation to the journal.
  - New script groups for advisers, editors and reviewers, things you found, distrust, sources that contradict each other, and what you’re working on; “maybe” no longer gets a lecture on probability (that’s kept for “reportedly”, “allegedly” and the like).
  - It no longer drops a passing word into a question (“Could don’t be deliberately misleading?”): a topic has to be a quotation, a name, or something your project treats as a subject. It no longer repeats a reply it gave in the last few turns.
- **Socrates fits the question to the selection and the project.**
  - It tells a person from a place or an event by how you write about the name (“Xenophon says…”, “at Cunaxa”) and by your sources’ authors, and 42 stems that suit only a person, only a non-person or only a claim are now tagged, so a battle no longer gets “What did ___ want?” and a person no longer gets “What if ___ had not happened?”.
  - 22 new stems name parts of your project: one of your sources’ authors (one who writes about the selection, when one does), the document you’re in, or a thread (“How would Lee explain ___? Where would we part ways?”). 364 stems in all.
  - A long claim is quoted by its opening words, so the question still reads as one. With nothing selected, it deals questions that stand on their own instead of ones with empty blanks.
  - The kinds of question you use come up a little more often.
- Names & spellings: an entry marked as an organization now counts as a person or group for Socrates, and a place as a place.

## [2.2.0] — 2026-11-24

### Added
- **The Oracle**: a conversation partner beside the writing, in the manner of Joseph Weizenbaum’s ELIZA (MIT, 1964–66). No AI and nothing online: a script of ranked keywords and sentence patterns (`data/oracle.txt`, 9 KB) turns what you say into questions, with contractions rewritten, your words turned around (*my* → *your*), replies used in turn so it doesn’t repeat itself, and a short memory of what you said to raise later. Plain words with a Delphic touch. It opens from the Research tab, the split view’s new **The Oracle** tab, or the command palette.
  - **Answers from your project**: “what have I written about…” counts and quotes your paragraphs, notes and sources, with buttons to open them and **Everything about**; when you mention something you have notes on, it says so.
  - **Counts and status**: claims that need a source, contested claims, sources rated D–F, the word goal and pace, open questions, review keys due, TKs and flags, next steps, and plain counts.
  - **Acts on the conversation**: “note: …”, “question: …”, “hypothesis: …”, “log: …”, “next step: …”, “note that …”, or “save that as a question”, each with **Undo**.
  - **Argues the other side** of a claim, with Socrates’ counter-questions and any notes, contested claims and evidence you filed against it, until you say “stop”.
  - **Daily check-in**: the first visit each day (or “check in”) lists review keys due, next steps, open questions, TKs and the word pace; “done for today” asks what you did, logs it, and signs off with one of the maxims carved at Delphi, chosen to fit the conversation.
  - **Consult on a passage**: select text and choose **Mark → Consult the Oracle** (Ctrl/Cmd+Alt+G, then O). It reads the passage back with questions about missing citations, numbers, hedges, absolutes, causal claims, unexplained acronyms and claims you marked.
  - **Nudges**: after three “not sure”s it points to something concrete (a TK, a review key, a next step, an unused note); when you keep circling a subject it offers everything you have on it.
  - Conversations are forgotten unless you press **Save to journal**, which files the exchange as a dated entry.

## [2.1.0] — 2026-11-24

### Added
- **Socrates**, beside **+ Question** in the Research tab (and **Mark → Ask Socrates**, Ctrl/Cmd+Alt+G then S, the question dialog, the research desk and the command palette): questions to start from when you’re working alone and not sure what to ask. It deals three at a time from 342 question stems in 19 kinds: meaning, evidence, assumptions, alternatives, implications, perspectives, sources and provenance, causation, time, numbers, comparison, counterfactuals, intelligence analysis, journalism, the argument, the reader, your own blind spots, questions about the question, and being stuck. Select a word, a claim, a name, a number or a citation first and the questions are about it, with a claim set in quotation marks; the kind of writing chosen for the project leans the deal (an intelligence brief toward analysis, an investigation toward journalism). **Shuffle**, **Another like this** and a picker for one kind; **Use this question** opens it in the question dialog, linked to the passage, with any remaining blank selected to type over. No AI and nothing online: the stems are 23 KB of text in the file.
- **Export → Archive**: the whole project as plain files in one zip, readable decades from now without Anabasis. Every document as Markdown in its own folder with its figures, Pandoc-style citations and footnotes; every note as its own Markdown file with its title, kind, tags and source key at the top; the sources as BibTeX and CSL-JSON with the same keys; the research memo; the project file; and a README saying what is where and how to turn a document into Word with Pandoc.

### Changed
- The README and quick start point to the hosted copy at zerohistory.net/anabasis. The old address keeps working.

## [2.0.0] — 2026-11-24

The release to hand to people who have never heard of Anabasis: co-writing without a server, an interface organized around what it has become, and a promise that the file format holds.

### Added
- **Co-writing and review without a server.** Export → **Send a copy** saves a copy of the project for a collaborator, with a note they see when they open it, and keeps a record of what was sent. Export → **Take changes back** compares their returned file with what you sent and with what you’ve written since (a three-way merge). Their edits arrive as suggestions under their name, word by word inside paragraphs, with paragraphs they added or cut marked whole; their margin notes, notes, sources, images and new documents are added; where you both changed the same paragraph you see the two side by side and choose to keep yours, take theirs as suggestions, or keep both. A safety copy of each changed document goes into Drafts first, and the next exchange compares from what came back. A file that wasn’t sent from the project can still be compared, every difference shown as a suggestion.
- **Help → Where things are**: a map of the interface at the top of Help, and a section on co-writing.

### Changed
- **One Insert menu** (the plus in the toolbar) for everything that goes into the page: image, chart, map, timeline, relationship map, table, equation, cross-reference, index entry, list of figures and tables, list of abbreviations. The toolbar keeps what you do while writing.
- **Export is grouped** by purpose: share and print; review, co-write and submit; other formats; the project file.
- **Sources → Tools** holds the source audit, link check and permissions log.
- **Sidebar tabs have icons**, each in its tab’s colour, as signposts.
- The tour and the sample document point to the new places.
- Comparing two versions of a collection ignores the order of fields, so pop-out windows and co-writing only see real changes.

### File format
- Format 2 is frozen for 2.x, with a written compatibility promise (docs/file-format.md). New optional fields: `collab` and `copyOf`, and the `sgb` class on wholly added or removed paragraphs.

## [1.9.0] — 2026-11-24

### Added
- **Cross-references.** A toolbar button (and Ctrl+Alt+R) inserts a reference to a figure, table, numbered equation, heading or another document, as “Figure 3”, “figure 3” or “3” (“Chapter 4” or its title for a document). References renumber as you write, turn red if their target is deleted, and show where they point when clicked, with Go there. Every export numbers for itself, so references in a compiled manuscript follow the book’s numbering. Word gets links to bookmarks on the caption, equation number or heading; PDF, web pages and EPUB get links (across EPUB sections too); LaTeX gets `\ref`/`\eqref` with `\label`s; Markdown and Pandoc get the words.
- **Credits and permissions.** Figures (Credit & permission… when you click one) and tables (Credit… on the table toolbar) take a credit line, a permission status, whom to ask and private notes. The credit line ends the caption in every export and shows after it on screen; status and notes never leave the project. The **Permissions log** (Sources tab) lists every figure and table with what’s still to clear, plus quotations by source, as a spreadsheet (CSV) or a document.
- **Check links** (Sources tab) asks the Internet Archive’s Wayback Machine about each web source: its latest saved copy and whether the page was there, moved or gone at that visit. Keep the saved copies with their sources, cite the archived address for pages that are gone, ask the Wayback Machine to save a page now, and fill in missing accessed dates from the day each source was added. Only the addresses are sent, and only when asked (archive.org is added to the allowed connections).
- **PDF for reviewers**: every line numbered, restarting on each page; a wide outer margin; “Review copy” and the date at the top.
- **Word in manuscript format**: Times New Roman 12, double-spaced, one-inch margins, indented paragraphs, # section breaks, “Surname / Short title / page” on every page after the first, and a first page with name, contact details, rounded word count, title and byline. Your details are kept in this browser, not the project. Also a Compile manuscript output.

### Fixed
- LaTeX and Pandoc packages no longer make the browser try to load their renamed image files while building.

## [1.8.0] — 2026-11-24

### Added
- **Equations.** Σ in the toolbar (also Ctrl+Alt+E, or Alt+= as in Word) opens an equation box: type TeX, add common pieces with a click, and see a live preview that points out a missing brace or an unknown command. An equation goes in the sentence or on its own line, centred, and numbered (1), (2)… at the right margin if you like; numbers follow the order as you edit. Click an equation to change it, switch it between the two, or remove it. Selected TeX, with or without its dollars, fills the box, and **Turn TeX in $…$ and $$…$$ into equations** converts a whole document (amounts like “$5 and $10” are left alone).
- **Word equations, both ways.** Word export writes real Office Math (fractions, roots, sums and integrals with limits, brackets, matrices, aligned rows, accents, functions and limits), editable in Word’s equation editor, with numbered equations numbered at the right margin. Word import turns Word equations back into TeX, so a document can make the round trip; a paragraph holding just an equation (and its number) comes back as a display equation.
- **Every other export.** PDF, web page and EPUB draw equations as SVG, labelled for screen readers; LaTeX gets `\( \)`, `equation` and `\[ \]` with amsmath; Markdown and Pandoc get `$…$` and `$$…$$`; Substack gets the TeX in dollars for its own equation block.
- MathJax 3.2.2 (Apache-2.0) is built in and loads only when a document has an equation; nothing is fetched. Its link and file-loading commands are turned off.

### Changed
- Display equations don’t count toward the word count, and Listen says “equation” rather than reading TeX aloud.

## [1.7.1] — 2026-11-24

### Added
- **Data in the writing.** On a dashboard, **Insert** on a table tile puts it in the document as a real table (sorted and with the columns the tile shows), titled and with a source line, numbered with the other tables and exported to Word and PDF like any table. **Insert as table** in the Data view does the same for a whole dataset (up to 300 rows). **Insert** on a number tile drops its value into the sentence at the caret, as one piece, with **Cite the source** a click away.
- **Kept in step with the data.** Figures, tables and numbers taken from a dataset remember it. **Update from data** (command palette; **Update the writing** in the Data view; the table toolbar for one table) redraws them in every document, open or not, and updates their source lines; a caption you rewrote is left alone. Replacing a dataset's data offers to update the writing straight away, and deleting one says how much of the writing will keep its last values.
- Linked tables and figures are marked on screen (never in print or exports). Click a linked number to see where it comes from; **Unlink** on a number or table keeps it as it is and stops it following the data. Editing a linked figure by hand unlinks it, and says so.

### Changed
- Inserting a chart, map or timeline tile now puts it at the caret rather than at the end of the document.


### Added
- **Beside the writing**: notes, sources, the research desk or another document (read only) in a panel next to the page. ⌘/Ctrl \ opens and closes it; drag to resize, swap sides (⌘/Ctrl Shift \), widen it for a while, and F6 moves between it and the writing. On phones it fills the screen with a switch back to the writing.
- **Pop-out windows**: any of those panels in a window of its own, for a second screen. Edits in either window reach the other within a moment, including changes made in both at once; actions that change the draft are done by the main window, which is the one that saves.
- **Data and dashboards** (research desk → Data): datasets from CSV or TSV files, pasted tables or document tables, each with a source; dashboards of number, chart, map, timeline, table, text, image and video tiles, with a tile editor and live preview, sizes, drag to reorder, preview mode, insert as figure, and export as one standalone web page with sources and CSV downloads.
- **Charts**: scatter and bubble, histogram (with the median marked), heatmap, and shaded maps of countries (world or a region), US states (names or postal codes) and the regions of about 25 countries. Diverging colors when values cross zero.
- **Source types**: primary, secondary or tertiary on each source, inherited by its notes (which can override it), with badges and filters, a bibliography grouped by type (Page setup), and a claims-register flag for claims cited only to tertiary sources.

## [1.6.0] — 2026-11-23

### Added
- **What’s new**: a short list of changes after each update, shown once, and any time from Help.
- **Send feedback** (Help and the command palette): a report with the version, browser, device and window size filled in, never anything from the project. Open it as a GitHub issue, or copy it into an email.
- **Check for a newer version**: from Help any time, or once a week if you switch it on in Settings (downloaded copies; off by default). It asks GitHub for the latest release number and nothing else.
- **The writing page on this screen** (Settings): text size, typeface (book serif, easy-reading sans, typewriter) and line spacing. Screen only: PDF, Word and print follow Page setup.

### Changed
- A lighter look: hairlines in place of heavy rules and frames, soft shadows, rounder cards and dialogs, plain-text New, Open and Export in the top bar, and a quiet row of sidebar tools (Plan, Compile, Templates, Import Word, Relationships) in place of six boxed buttons.
- Line spacing on screen is comfortable (at most 1.7) unless you choose As in Page setup; a double-spaced manuscript still exports double-spaced.
- The tour is up to date: 55 citation styles, marks, the research desk and journal, and working with editors.

## [1.5.0] — 2026-11-23

### Added
- **Pick up on another device.** The GitHub dialog's **Open a project…** (and **From GitHub…** on Project home) lists every project backed up to the repository and opens the newest backup. When a newer backup of the open project turns up from another device, a notice offers to open it, checked when the app starts, when a project opens and when you come back to the tab.
- **This week**, a weekly review in the Journal: words written each day, log entries, searches, sources, notes and checked claims, hypothesis changes, questions answered, review keys coming due. Step back through earlier weeks; **Week summary** makes a document.
- **Next steps**: a new kind of log entry with a box to tick. Open ones show in This week, the Research tab and the research memo.
- **Research design templates**: prompts for eight methods (archival, interviews, open-source investigation, document analysis, case studies, data analysis, literature review, investigative reporting), filled into empty fields or added below.
- **Getting-started tips**: a short card on an empty document for the kind of writing, eleven kinds in all, also listed in Help. Off in Settings.

### Changed
- The fact-check sheet records who checked each claim and when, lists the page or other location of each citation, and can be made as a document in the project. The claims CSV includes the checker.
- Backing up to GitHub over a newer backup from another device now asks first; automatic backups skip it and show the notice instead.
- The thesis and investigation examples include a next step.
- Build and publishing workflows moved to current GitHub Actions (Node 24), and publishing to GitHub Pages retries once if GitHub can't find the upload.

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

[2.2.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v2.2.0
[2.1.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v2.1.0
[2.0.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v2.0.0
[1.9.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.9.0
[1.8.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.8.0
[1.7.1]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.7.1
[1.7.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.7.0
[1.6.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.6.0
[1.5.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.5.0
[1.4.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.4.0
[1.3.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.3.0
[1.2.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.2.0
[1.1.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.1.0
[1.0.4]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.4
[1.0.3]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.3
[1.0.2]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.2
[1.0.1]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.1
[1.0.0]: https://github.com/gmichaelrapp/anabasis/releases/tag/v1.0.0
