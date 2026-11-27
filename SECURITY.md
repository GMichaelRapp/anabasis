# Security policy

Anabasis runs entirely in your browser and has no server, so most security problems are about the page itself. Examples:

- a project file, pasted text, imported document, ePub or clipped page that can run code;
- a weakness in how locked projects are encrypted or unlocked;
- a way to get Anabasis to contact an address you didn’t ask it to;
- leaking a GitHub token, or anything else from your work, to someone you didn’t send it to.

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please **don’t open a public issue**. Report it privately through [GitHub’s private vulnerability reporting](https://github.com/gmichaelrapp/anabasis/security/advisories/new). Include:

- the version and browser;
- steps or a file that shows the problem;
- what an attacker could do with it.

You’ll get an acknowledgement within a week. Once the problem is confirmed, a fix will be released as soon as practical, and you’ll be credited in the release notes unless you’d rather not be.

## Checking a download

Every release is built and published by the [Release workflow](.github/workflows/release.yml) from a tagged commit, and nothing else. Two ways to check that the `anabasis.html` you have is that file, unaltered:

- **The checksum.** Compare `sha256sum anabasis.html` (macOS: `shasum -a 256 anabasis.html`; Windows: `certutil -hashfile anabasis.html SHA256`) with `SHA256SUMS.txt` on the release page.
- **The build provenance** (2.10.2 and later). Each release carries a signed attestation of where, from which commit and by which workflow the file was built. With the [GitHub CLI](https://cli.github.com/):

  ```
  gh attestation verify anabasis.html -R gmichaelrapp/anabasis
  ```

  It succeeds only for a file this repository’s workflow built.

## What Anabasis defends against

**Someone sends you a file.** A project, a collaborator’s returned copy, a review, a Word document, an ePub, a PDF or a web page you clip can all be crafted to attack the app. The defenses, in layers, so that a mistake in one is caught by the next:

1. **Cleaning on the way in.** Everything from a file passes through DOMPurify when it is opened; pasted HTML goes through a stricter allowlist of its own. Ids, references, colors and kinds in a project file are reduced to plain characters before they reach the page, and board positions must be numbers. ePubs are read without their scripts, styles or forms.
2. **Cleaning on the way to the screen.** In Chrome and Edge, Trusted Types make the browser refuse any HTML written into the page that hasn’t passed through the app’s policy. The policy cleans with DOMPurify anything that could carry script (an event handler, a `javascript:` address however it’s spelled or spaced, a script, frame, object, form, `<base>` or `<meta>`, or a character reference that could hide one); the interface’s own markup, with every value escaped, passes as it is. A string can’t become script at all: the policy refuses every attempt.
3. **A strict content security policy.** The page may run only its own scripts, each pinned by its SHA-256 hash when Anabasis is built, plus scripts the app itself makes from those (in blob: addresses). Inline event handlers, `javascript:` links, `eval`, plug-ins, `<base>` and form submission are all refused, and the page can connect only to the citation services and GitHub listed in [docs/privacy.md](docs/privacy.md). So even text that slipped past both cleanings could neither run nor send anything anywhere.
4. **Tested.** The test suites open crafted projects with script payloads in every field (`tests/t57.py`, `tests/t58.py`), visit every part of the interface and every saved web page, and fail if anything runs or anything is fetched. GitHub’s CodeQL scans every change.

**Someone gets your file or your computer.** A locked project, its browser copy, and a GitHub token remembered while it is open are encrypted with AES-256-GCM, with a key made from your password by PBKDF2-SHA-256 (600,000 iterations, a random 16-byte salt, a random 12-byte IV for each save). The key is kept in memory only. Passwords must be at least 10 characters and not one of the first ones an attacker would try. A locked project hides itself after a spell with no typing or clicking (15 minutes unless you choose otherwise) and asks for the password again; **Lock now** does it at once.

**What you send out says more than you meant.** Pictures you add lose their location (GPS), camera and other details before they are stored. Every web page Anabasis saves (an exported document, a reviewer’s page, a dashboard, a comparison of drafts, a fact-check sheet) carries its own content security policy: it can run only the scripts written into it and load nothing from the internet (a dashboard’s YouTube and Vimeo tiles excepted). A Word file says how many of your comments it includes.

**The network.** Anabasis contacts nothing unless you use a feature that needs it, and **Work offline** in Settings turns all of those off. GitHub backups go to a private repository: Anabasis won’t back up to a public one without asking, and never does so automatically.

**The supply chain.** Every library is vendored (copied into this repository) with its version, license and SHA-256 recorded in `vendor/manifest.json`; the build refuses to run if a file doesn’t match. A weekly workflow checks every vendored library against the OSV advisory database and opens an issue if one is affected. The workflows pin each action to an exact commit, keep their permissions to what each job needs, and don’t leave credentials on disk; Dependabot proposes action updates for review.

## What it can’t defend against

- Someone who can use your unlocked computer while a project is open, or who installs software on it (a keylogger, a malicious browser extension). Browser extensions can read any page you open, including this one.
- A forgotten password. Nobody can open a locked project without it, including the author.
- What happens to a file after you send it.

## For contributors

- Build HTML with `esc()` for every value, never by pasting text in; prefer `textContent`.
- Don’t add a network address to the content security policy without adding it to [docs/privacy.md](docs/privacy.md) and saying why.
- New inline `<script>` blocks are hashed into the policy by `build.py` automatically; nothing else may run.
- A change to how files are read needs a hostile example in the tests.
