# Security policy

Anabasis runs entirely in your browser and has no server, so most security problems are about the page itself. Examples:

- a project file, pasted text, imported document or clipped page that can run code;
- a weakness in how locked projects are encrypted or unlocked;
- a way to get Anabasis to contact an address you didn’t ask it to;
- leaking a GitHub token.

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please **don’t open a public issue**. Report it privately through [GitHub’s private vulnerability reporting](https://github.com/gmichaelrapp/anabasis/security/advisories/new). Include:

- the version and browser;
- steps or a file that shows the problem;
- what an attacker could do with it.

You’ll get an acknowledgement within a week. Once the problem is confirmed, a fix will be released as soon as practical, and you’ll be credited in the release notes unless you’d rather not be.

## Design notes

- Everything from a file passes through DOMPurify on opening. Pasted HTML goes through a stricter allowlist of its own.
- A content security policy allows no plug-ins, no `eval`, no form submission, and network access only to the citation services and GitHub listed in [docs/privacy.md](docs/privacy.md).
- Locked projects use AES-256-GCM with a PBKDF2-SHA-256 key (600,000 iterations, random 16-byte salt, random 12-byte IV per save).
- A remembered GitHub token sits in localStorage in plain text, and the app says so when you tick **Remember**. Use a fine-grained token limited to one private repository.
