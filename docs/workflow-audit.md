# Project workflow audit and CLI/GUI comparison

Audit: 2026-10-29. This describes the implemented application, not the design dummy.

## Automated workflow coverage

Run `uv run --extra web pytest -q` and `cd frontend; npm run build`.
`tests/test_web_workflow.py` exercises real HTTP routes with FastAPI TestClient;
native file-picker selection is covered separately using stubs in `test_web.py`.
Tests use temporary projects and do not edit the maintained example inputs.

- Create a named project, copy ontology and local images, and keep originals unchanged.
- Keep opened projects isolated, including prefixed preview/download URLs.
- Save language, parser, theme and optional checks to YAML with revision protection.
- Generate compact and standard Markdown, assign, check drafts, save, download,
  detach without deleting, and generate a new template.
- Generate technical and combined HTML, inspect HTML, serve images, download ZIP.
- Reopen the API and restore persisted HTML assignments.
- Move a complete copied project, remove the original sources, reopen it and
  retain Markdown, HTML, downloads and image links.
- Detach HTML, reject generation of combined HTML without Markdown, and link an
  existing HTML file again. Previously published HTML is independent of Markdown.
- Repair missing input/Markdown paths without making the entire GUI unusable.
- Reject stale writes, unknown parsers, malformed RDF, and unrelated preview files.
- Generate both HTML variants for ISOProps, LOIN and TempO, then reopen them.
  TempO's known missing `LibraryOverview.svg` is skipped with a warning.

The graphical browser automation connection was unavailable during this audit.
These are API/file-level integration tests plus TypeScript/production-build checks,
not an assertion that all native dialogs, layout, or click sequences were visually
tested. React navigation/discard handling was reviewed and corrected in code.

## Fixes from this audit

- Markdown export URLs now include the selected project's API prefix.
- Missing input files no longer block opening/repairing projects in the GUI.
  CLI loading remains strict by default.
- Pending language/parser settings are applied before template generation.
- Empty language/parser values can override inherited defaults explicitly.
- Discarding Markdown while navigating away reloads saved content on return.
  Selecting the current navigation item no longer clears dirty tracking.
- Browser-close warnings now include unsaved export options.
- Malformed RDF exports return an actionable error instead of an internal error.
- Linked SVG image/use dependencies survive HTML export and preview.
- Source downloads are bundled by the shared generator. Cross-drive exports on
  Windows no longer fail while computing a relative source path.
- Failure messages no longer incorrectly promise that no partial output exists.

## CLI/GUI parity

| Function | CLI | Current GUI |
| --- | --- | --- |
| Technical HTML | `INPUT -o OUTPUT` | HTML-Dokumentation tab |
| Combined HTML | `--content FILE` | Kombinierte Dokumentation tab; assigned Markdown required |
| Markdown template | `init-content --profile compact/standard` | Both profiles; generation and assignment |
| Template language | `init-content --language de/en` | Shared language field; de/en templates |
| RDF parser | `--format` | Editable parser field; automatic detection when empty |
| Preferred label language | `--language` | Editable language tag; automatic when empty |
| Recommendations | `--recommendations` | Checkbox |
| Quality report | `--quality-report` | Checkbox |
| Custom annotations | `--custom-annotations` | Checkbox |
| Missing object-property endpoints in graph | `--show-missing-endpoints` | Checkbox; off by default; no effect on quality checks |
| Missing ontology images | `--skip-missing-images` | Checkbox; Markdown images remain required |
| HTML theme | `--theme light/dark/both` | Hell / Dunkel / Beide; GUI preview switches variants, generated pages have no toggle |
| Markdown completeness | `--check-content` | Check button for editor draft; YAML `check_content` honored on combined builds |
| Output location | `--output` | Project-wide directory picker |
| Explicit output filename | `-o FILE` | Not exposed; generated names are automatic |
| Explicit template filename | `init-content -o FILE` | Not exposed; generated working file is linked automatically |
| Batch project builds | `build CONFIG` | Shared build in Portal workspace; separate batch without portal not exposed |
| Selected batch builds | `build --ontology ID` (repeatable) | Ontology checkboxes on the left in Portal workspace |
| Portal | `build --portal/--no-portal` | Title, selection, generate, preview and ZIP download |
| Project-wide defaults | YAML `defaults` / CLI overrides | Read as effective settings; GUI writes individual overrides |
| Per-run overrides without saving | CLI flags | Not exposed; GUI saves settings before generation |
| A-Box document | `abox INPUT --max-nodes N` | Not exposed |

The standalone Check button is intentional, not a missing checkbox. Automatic
checking on every combined build remains configurable in YAML. Negative project
CLI flags correspond to unchecked per-ontology GUI options.

## Remaining product work

1. Optional batch builds without a shared portal.
2. A-Box export/preview controls, including node limit.
3. Editing project defaults and project name. Ontology membership can now be
   changed in project settings, including optional copies of sources and images.
4. Optional custom export/template filenames, if the GUI needs CLI-level naming control.
5. Converting an existing externally linked project into a portable copied project.

Docker image build and startup were verified with Docker Desktop. The real HTTP
workflow test covers project creation, asset copies, Markdown, both HTML themes,
combined documents, portal, ZIP downloads, CLI and restart persistence. LOIN,
TempO and ISOProps also passed a combined portal export. See `docker.md` and
`scripts/docker_smoke.py` for reproduction.

Portability still requires keeping the whole project folder and internal assets.
External Markdown, output locations, remote image URLs/imports/scripts are not
automatically copied. SVG CSS resources and other external web dependencies are
not covered by the SVG image/use bundling. This is not a fully offline web archive.
