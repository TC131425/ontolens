# Export documentation as PDF

PDF export prints a **saved HTML document**, not the live ontology or Markdown draft.
Regenerate the HTML first if it must reflect recent edits. Printing never changes
the source, linked HTML or project history.

## Print from the web app

1. Open **Project settings > Share project > Export documentation as PDF**.
2. Select the linked HTML documents to print. You can choose the technical or
   combined version of each ontology, up to 20 documents per export.
3. Choose **Paper size** (A4 by default or A3). **Include figures** is on by
   default; **Include ontology graph in PDF** is off. They are independent.
4. Select **Export PDF** and download the result. One document produces a PDF;
   multiple documents produce a ZIP with one PDF per document, not a merged PDF.

## What the reader sees

Text is portrait and always uses a light print style, even for a dark HTML source.
Restrictions and instance lists are expanded. Chapter links, bookmarks, internal
term links, the document title and page numbers are preserved. Figures are scaled
proportionally. The optional graph and its legend occupy a separate landscape
page of the selected paper size. The graph uses the saved graph data, not the
zoom, filters or dragged positions in your browser.

Choose A3 for a dense graph. If labels still look too small, omit the graph and
share the interactive HTML alongside the PDF. Missing graph data in an old or
manually linked HTML file produces a notice. Graphs larger than 1,000 nodes or
3,000 edges cannot be exported as a figure; export without the graph instead.

## Print from the CLI

Docker includes the renderer. For a local installation, install the optional
dependencies and Chromium first:

```sh
uv sync --extra web --extra pdf
uv run --extra web --extra pdf python -m playwright install --only-shell chromium
```

On Linux, add `--with-deps` to the Playwright install command if system libraries
are missing. When starting the local web API for PDF export, pass both extras to
`uv run`. Other CLI commands do not require the PDF extra.

```sh
uv run --extra pdf ontolens pdf documentation.html -o build/ontology.pdf
uv run --extra pdf ontolens pdf documentation.html --paper A3 --graph -o build/ontology-graph.pdf
uv run --extra pdf ontolens pdf first.html second.html --no-figures -o build/documents.zip
```

The CLI writes `build/<timestamp>_<output-stem>/<filename>`, choosing `.pdf` or
`.zip` based on the number of inputs. In Docker use e.g.
`docker compose exec ontolens ontolens pdf /data/project/documentation.html -o /data/exports/documentation.pdf`.
Web downloads go to the browser's download folder; temporary server files are removed.

## Resources and privacy

The renderer does not execute scripts from the source HTML or fetch network
resources. Only the bundled graph code runs. Local images must be inside the
document folder or its registered export bundle. If figures are included, a
missing local image blocks export. Online images become text notices; external
stylesheets and web fonts are not fetched.

## API and testing

`POST /api/project/pdf` requires `X-Ontolens-Write: 1`, the project `revision`,
and `documents` entries such as `{"ontology":"library","kind":"reference"}`.
Use `reference` or `combined`; optional fields are `paper` (`A4` or `A3`),
`figures` (default true) and `graph` (default false). The response contains the
PDF or ZIP; see `X-Ontolens-Filename` and `X-Ontolens-Notices` for details.

For the optional real-renderer tests in PowerShell:

```powershell
$env:ONTOLENS_TEST_PDF = '1'
uv run --extra web --extra pdf pytest tests/test_pdf_export.py -q
```

For a container-level check, see [Verify a deployment](docker.md#verify-a-deployment).
