"""Check the vendored libraries against published security advisories.

Reads vendor/manifest.json, asks the OSV database (osv.dev, which gathers the GitHub, npm and other
advisory feeds) about every npm package at the exact version vendored, and reports any advisory that
applies. Exits 1 if there is one (2 if the database can't be reached), so the scheduled workflow can open an issue.
An advisory listed in vendor/advisories-accepted.json (no fixed release yet, and mitigated in Anabasis, with the reason
written down) is reported but doesn't fail the check until its review date passes.

    python tools/check_advisories.py             # report
    python tools/check_advisories.py --markdown  # report as Markdown (for the issue body)
"""
import argparse, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OSV = 'https://api.osv.dev/v1/querybatch'


def packages(manifest):
    """The distinct (npm name, version, display name) triples in the manifest."""
    seen, out = set(), []
    for e in manifest:
        m = re.match(r'npm:((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)', e.get('source', ''))
        if not m or (m[1], m[2]) in seen: continue
        seen.add((m[1], m[2])); out.append((m[1], m[2], e.get('name', m[1])))
    return out


def query(pkgs, post=None):
    body = json.dumps({'queries': [{'package': {'name': n, 'ecosystem': 'npm'}, 'version': v} for n, v, _ in pkgs]}).encode()
    if post: return post(body)
    req = urllib.request.Request(OSV, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)


def details(vid):
    with urllib.request.urlopen(f'https://api.osv.dev/v1/vulns/{vid}', timeout=60) as r: return json.load(r)


def findings(pkgs, result, lookup=details):
    out = []
    for (name, version, label), res in zip(pkgs, result.get('results', [])):
        for v in res.get('vulns') or []:
            try: d = lookup(v['id'])
            except Exception: d = {}
            sev = (d.get('database_specific') or {}).get('severity') or ''
            out.append({'package': name, 'version': version, 'label': label, 'id': v['id'],
                        'aliases': d.get('aliases') or [], 'summary': d.get('summary') or '', 'severity': sev})
    return out


def report(found, md=False):
    if not found: return 'No published advisories affect the vendored versions.'
    lines = ['Published advisories affect these vendored libraries. Update each in vendor/ (and its version and '
             'sha256 in vendor/manifest.json), rebuild, and run the tests.', '']
    for f in found:
        ids = ', '.join([f['id']] + f['aliases'])
        if md: lines.append(f"- **{f['label']}** {f['version']} (`{f['package']}`): {f['summary'] or 'see the advisory'} "
                            f"{('— ' + f['severity'].lower()) if f['severity'] else ''} ([{f['id']}](https://osv.dev/vulnerability/{f['id']}); {ids})")
        else: lines.append(f"{f['label']} {f['version']} ({f['package']}): {f['summary']} [{f['severity']}] {ids}")
    return '\n'.join(lines)


def accepted_now(found, accepted, today):
    """Split findings into those still to act on and those accepted, with a reason, until their review date."""
    keep, ok = [], []
    for f in found:
        ids = {f['id'], *f['aliases']}
        a = next((x for x in accepted if (x.get('id') in ids or ids & set(x.get('aliases') or [])) and x.get('package') == f['package'] and x.get('version') == f['version']), None)
        (ok if a and str(a.get('review_by', '')) >= today else keep).append(dict(f, accepted=a) if a else f)
    return keep, ok


def main():
    import datetime
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('--markdown', action='store_true')
    a = ap.parse_args()
    pkgs = packages(json.loads((ROOT / 'vendor/manifest.json').read_text()))
    try: found = findings(pkgs, query(pkgs))
    except Exception as e: print(f'Could not reach the advisory database: {e}', file=sys.stderr); sys.exit(2)
    acc = ROOT / 'vendor/advisories-accepted.json'
    keep, ok = accepted_now(found, json.loads(acc.read_text()) if acc.exists() else [], datetime.date.today().isoformat())
    print(report(keep, a.markdown))
    for f in ok: print(f"\nAccepted until {f['accepted']['review_by']}: {f['label']} {f['version']} {f['id']}. {f['accepted']['reason']}")
    sys.exit(1 if keep else 0)


if __name__ == '__main__':
    main()
