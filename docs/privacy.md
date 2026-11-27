# Privacy

Anabasis has no account, no server, no analytics and no advertising. Nobody, including the author, can see what you write in it.

## Where your work is kept

- **Your project file.** Save writes the whole project (documents, notes, sources, images and settings) to one `.json` file wherever you choose. This is the real copy. Back it up the way you back up anything else.
- **Your browser.** As you type, Anabasis keeps a working copy in your browser’s own storage (IndexedDB, with localStorage as a fallback), so a closed tab or a crash doesn’t lose anything. It stays on your computer. Clearing your browser’s site data removes it. **Start fresh** in the app erases it too.
- **Checkpoints** of the whole project are kept in the same browser storage. Download a checkpoint to keep it anywhere else.
- **PDFs and archive photos** you open are kept in the same browser storage, not in the project file. Photos are resized to 2,400 pixels. The project file keeps their transcriptions, the notes made from them, and a SHA-256 fingerprint of each original file.
- **Evidence fingerprints** are worked out in the browser from the file you choose. The file itself is never stored or sent anywhere.
- **Preferences**, such as theme and check settings, are kept in localStorage, as are note templates you save and where you put the scratch pad. So are the name and contact details you give for Word’s manuscript format, which never go into the project file.
- **Search inside sources** reads the text of your PDFs in the browser and keeps it in the same browser storage, so later searches are quick. It never goes into the project file. Clearing your browser’s site data removes it.
- **Reading the text of a scan** (Read the text on an archive photo, Read text in the PDF reader) runs Tesseract, an open-source text reader built into the file, inside the page. The image never leaves your computer, and the reader downloads nothing: its English model is in the file too. Running it needs WebAssembly, so the page’s security policy allows `'wasm-unsafe-eval'`; that lets the page run compiled code it already contains, and opens no new connections.
- **My library** is kept in the same browser storage, shared by the projects you open in this browser. A source goes into a project file only when you add it to that project. **Export** writes the library to a file you choose.
- **Submissions** (outlets, editors, dates, fees and notes) are kept in the project file.
- **The slush pile** (passages you cut and documents you delete) is kept in the project file, like the documents themselves, and is never included in an export.
- **A followed Zotero library** is a file on your computer that Zotero (with Better BibTeX) keeps up to date. Anabasis reads it in the page; it never talks to Zotero or to zotero.org. The project file keeps the file's name and when it was read. In Chrome and Edge, the browser's permission to re-read that one file is kept in the same browser storage, and removing the link (or clearing site data) forgets it.
- **Book for print** and **submission packages** are made in the page: the book goes to your browser's print dialog, and the package is a .zip saved to your computer. Anonymizing for blind review happens before the file is written; the original document is not changed.
- **Socrates and the Oracle** read only your project, in the page. The questions you take from Socrates are kept in the project file so it can bring back old ones; the Oracle's manner is kept in this browser's settings. Neither has any AI or goes online.
- **Editing marks** carry the name you give in Settings, so an author can see who made each mark. Exports leave the marks out.
- **The calendar** is kept in the project file. **Export .ics** writes a file to your computer for you to import into a calendar app; Anabasis doesn’t connect to Google, Apple or Microsoft calendars.

- **The installed app's own files.** If you add the hosted copy to your Home Screen or install it, a small service worker keeps a copy of Anabasis itself (the page and its icons) so it opens offline. It stores nothing you write and makes no connections of its own. The downloaded file doesn't use one.

If you open the hosted copy on GitHub Pages, the same rules apply. GitHub serves the file, but your work stays in your browser. GitHub’s own [privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) covers serving the page.

## When Anabasis goes online

Only when you ask it to, and only to these addresses:

| You choose | Anabasis contacts | What it sends |
|---|---|---|
| Add a source by DOI | doi.org (which may hand off to Crossref or DataCite) | the DOI |
| Add a source by ISBN | openlibrary.org | the ISBN |
| Add a source by web address | en.wikipedia.org (its citation service) | the address |
| Check links (Sources tab) | archive.org (the Wayback Machine’s availability service) | the web addresses of your sources, one at a time |
| Check for retractions (Sources tab → Tools) | api.crossref.org | the DOIs of your sources, one at a time |
| Back up to GitHub, or open a backup | api.github.com | your project file and your access token, sent to a repository you choose |
| Check for a newer version (Help, or the weekly check you can switch on in Settings) | api.github.com | nothing but the request for the latest release number |

The page’s content security policy blocks every other connection. Images in your documents are stored inside the project, never loaded from the web. Proofread, Close to your notes, Socrates, the Oracle, the research guide and coding all run inside the page.

## Dashboards you export

An exported dashboard page is self-contained, except for video tiles: when someone opens the page, a YouTube or Vimeo tile loads that video from YouTube (through its privacy-enhanced youtube-nocookie.com address) or Vimeo, and a video-file link loads from wherever it points. Inside Anabasis, video tiles are shown as links and load nothing.

## Feedback

**Send feedback** (Help) opens a GitHub issue in your browser, or copies the report for you to paste elsewhere. It holds what you type plus the Anabasis version, browser, device type, window size and theme. Nothing from your project goes in it, and nothing is sent until you submit it yourself.

## GitHub backup

If you turn on GitHub backup, you give Anabasis a personal access token. It is kept in memory for the session. If you tick **Remember**, it is stored in this browser’s localStorage, unencrypted. Anyone who can use your browser profile could read it, so use a fine-grained token limited to one private repository. A locked project is backed up locked.

## Password lock

A locked project is encrypted with AES-256-GCM, using a key derived from your password with PBKDF2 (SHA-256, 600,000 iterations). The password is never stored. Nobody can recover a locked project without the password, including the author.

## Files from other people

A project file is data, but a crafted one could try to smuggle in code. Anabasis cleans every document, draft and note when it opens a file. Scripts, event handlers, `javascript:` links, frames, forms and remote images are removed before anything reaches the page.

## Co-writing

Send a copy and Take changes back work entirely through files you pass along yourself, by email, a shared drive or a USB stick. Nothing goes through a server. The project keeps a record of the last five copies you sent (the text as it was when you sent it, the collaborator's name and your note) so it can tell their changes from yours; the copy you send carries only who it's from, who it's for and the note. A returned file is cleaned like any other file from someone else before anything in it reaches the page.

## Reviews

**Export → For a reviewer** writes one web page with the open document’s text and footnotes (your margin comments and research marks are left out), the title, your name as you’ve set it in Settings, and the note you add. Send it however you like. The page makes no connections: the reviewer’s comments are kept in their own browser until they press **Save my review**, which downloads a small file with their name, their comments and suggested changes, and the words around each one. **Import a review** cleans that file like any other before anything in it reaches the page.

## Socrates, the Oracle and the archive

The Oracle is a script of keywords and sentence patterns built into the file, not AI. It reads what you type and searches your project in the browser, and nothing you say to it leaves your computer. Conversations are kept only if you press Save to journal, and then only in your project file.

Socrates is a list of question stems built into the file. It reads only what you've selected and suggests questions on the spot, without AI and without going online. All it keeps is a count, in this browser's settings, of which kinds of question you've used, so those come up a little more often; it keeps nothing about what you selected or asked. Proofread runs in the page from a word list built into Anabasis; the only thing it keeps is the list of words you tell it to ignore, saved in the project file. When Socrates or the Oracle searches your project for related notes, the index is built in your browser and thrown away; it is never saved or sent anywhere. The Oracle remembers earlier conversations only if you saved them to your journal, and then only by reading that journal entry. The archive export is put together in your browser and saved straight to your computer.
