# Working baseline before ML foundation

Baseline audit: local main and freshly fetched origin/main were both 3e6a043,
with zero ahead/behind commits. The advanced backend, frontend, species model,
context engine and tests were uncommitted locally.

Validation before implementation (2026-10-16):
- System Python 3.14: `python -m pytest -q`: 107 passed, 4 subtests passed,
  5 deprecation warnings, 26.87 seconds.
- Repository .venv lacks pytest; the system interpreter ran the suite.
- Frontend: `npm run build`: passed; Vite warns about a bundle over 500 kB.

Security review: no credential-pattern matches in candidate source files.
Model weights, datasets, evidence, generated evaluation images, dependencies,
build outputs, local environments, runtime databases and caches remain local.
The user explicitly confirmed all data in config/patrols.json is synthetic.
Camera and boundary simulation provenance is documented in ml/context/README.md.

No ML implementation changes were made for this baseline.
