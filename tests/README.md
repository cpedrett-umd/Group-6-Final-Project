# tests/ — Python test suite

Covers the analysis pipeline and the API both front ends call.

```bash
pip install pytest
python -m pytest tests/ -q
```

Run from the repository root. `conftest.py` puts `app/` on `sys.path`, because
the app's modules import each other as top-level names the way
`python app/server.py` gives them.

## What's covered

| File | Subject |
|---|---|
| [test_tactics.py](test_tactics.py) | Trigger-phrase lexicon, panel-row construction, the low-confidence guard |
| [test_ocr.py](test_ocr.py) | Space repair, backend discovery, reading text off real images |
| [test_predict.py](test_predict.py) | The tuned classifier's output shape, determinism, truncation |
| [test_server.py](test_server.py) | Routes, validation, error codes, CORS, and the JSON contract |

## Markers

Tests that need an artifact **skip** rather than fail, so a fresh clone runs
green on the logic suites before anyone downloads weights.

| Marker | Skipped unless |
|---|---|
| `model` | the tuned weights are on disk |
| `ocr` | an OCR backend is installed |
| `slow` | — (informational; takes over a second) |

```bash
python -m pytest tests/ -q -m "not slow"      # fast logic only
python -m pytest tests/ -q -m model           # just the model-backed tests
python -m pytest tests/test_tactics.py -q     # one file
```

The weights are committed via Git LFS, so the `model` tests normally run. If
they skip, the checkpoint is probably still an LFS pointer:

```bash
git lfs install && git lfs pull
```

## Notable cases

These exist because they caught real bugs:

- **Punctuation survives space repair.** The word splitter discards
  non-alphanumeric characters, so `70%offbeforethesupplementban` was becoming
  `70 off before the supplement ban` — dropping the percent sign from text the
  panel quotes back to the user.
- **Brand names survive space repair.** The same splitter turns `MemoryMax`
  into `Memory Max`. A 2-way split is only accepted for all-caps runs.
- **Oversized uploads return 413, not 500.** Werkzeug raises
  `RequestEntityTooLarge` while parsing, inside the route's `try`, where the
  generic handler was swallowing it.
- **A clean ad reports nothing.** Between the `Neutral` class and the
  low-confidence guard, a bakery's opening-hours ad must not read as
  "This ad uses 1 pressure tactic."

## Extension tests

The browser extension has its own suite (Node, no browser needed):

```bash
cd extension/tests && npm install && npm test
```

See [extension/README.md](../extension/README.md).
