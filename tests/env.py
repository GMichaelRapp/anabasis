"""Shared locations for the test scripts. run_tests.py sets these through the environment."""
import os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = os.environ.get('ANABASIS_OUT', str(ROOT / 'tests' / 'out'))            # scratch folder; also served over HTTP
URL = os.environ.get('ANABASIS_URL', (ROOT / 'dist' / 'anabasis.html').as_uri())  # the built app, opened from disk
HTTP = os.environ.get('ANABASIS_HTTP', 'http://localhost:8765/')            # the same scratch folder over HTTP
FX = str(ROOT / 'tests' / 'fixtures' / 'fx')
AXE = str(ROOT / 'tests' / 'vendor' / 'axe.min.js')
