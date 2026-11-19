# OntoLens

OntoLens generates static HTML documentation for RDF/OWL ontologies. It is inspired by pyLODE and WIDOCO, but keeps the generated page focused on ontology documentation: metadata, creators and contributors, figures, used ontologies, downloads, namespace prefixes, a graph visualization, overview counts, and cross-references for classes and properties.

The default output is intentionally clean. Additional checks and verbose term annotations are opt-in through CLI flags.

Both standalone and combined HTML have an offline search above the table of
contents. Under **Search in**, readers can independently select names and labels
(all languages), IRIs and prefixed names, descriptions and comments, and, in
combined pages, Markdown chapters. All available areas are enabled initially.
Text matches show their source and a short highlighted passage. Select a result
to jump to its term, metadata or chapter. Clear the query with the reset button
or Escape to restore the tree. Only the navigation is filtered, never the page.

Ontology metadata follows a fixed reading order: URI, title and descriptions,
namespace, version/status and compatibility, dates, license/citation and provenance,
then related resources and images. Missing-value recommendations use the same
positions as populated fields rather than being appended at the bottom.

## Installation

### Projekt weitergeben

In den **Projekteinstellungen → Projekt weitergeben** lässt sich ein portables
Projekt-ZIP erstellen. Konfiguration, Ontologien, lokale Bilder und zugeordnetes
Markdown sind enthalten; aktuell verknüpfte HTML-Dokumentationen und Portale
können optional mitgenommen werden. Das Arbeitsprojekt bleibt unverändert.
Details und Grenzen: [Projekt-ZIP](docs/project-export.md).

Im selben Bereich bietet **Dokumentation als PDF** den Export vorhandener
HTML-Dokumentationen an: A4/A3, optionale Abbildungen und Graph, immer mit hellem
Drucklayout. Mehrere Dokumente werden als ZIP mit einzelnen PDFs heruntergeladen.
Docker enthält den Renderer; lokal ist das Extra `pdf` samt Chromium erforderlich.
Siehe [PDF-Export](docs/pdf-export.md).

```console
uv run ontolens pack projects/mein-projekt.yaml -o build/mein-projekt.zip
uv run ontolens pack projects/mein-projekt.yaml -o build/mein-projekt.zip --include-outputs
```

### Docker (lokale Anwendung)

Vor dem ersten Start das lokale Laufwerk in `.env` einstellen, beispielsweise
`ONTOLENS_HOST_DIR=D:/`. Ohne Einstellung verwendet Compose `C:/`.
Der Dateibrowser funktioniert auch in Firefox und schreibt direkt auf das
eingebundene Laufwerk. Details: [Docker und lokale Laufwerke](docs/docker.md#lokales-laufwerk-einstellen).

Docker Desktop mit Linux-Engine starten, dann im Projektordner:

```console
docker compose up --build -d
```

Oberfläche: **http://localhost:8080**. Projekte/Quellen/Exporte bleiben unter
`docker-data/` auf dem Host. Die Dateiauswahl erfolgt im Containerbetrieb über
einen Browser für diesen eingebundenen Ordner. Daten zuerst dorthin kopieren,
einschließlich referenzierter Bilder. Port und Datenordner sind über `.env`
konfigurierbar; Vorlage: `.env.example`.

Die vollständige [Docker-Anleitung](docs/docker.md) beschreibt Projektübernahme,
Dateiauswahl, Updates, Backups, CLI-Nutzung, Linux-Rechte und Grenzen. Image-Build,
Containerstart und Exportworkflow wurden mit Docker Desktop geprüft; ein
wiederholbarer Smoke-Test ist dort beschrieben. Diese lokale Anwendung hat keine Anmeldung und darf nicht ungeschützt
öffentlich bereitgestellt werden.

### Lokale Python-/React-Installation

The initial React/FastAPI application is available alongside the CLI. See
[Local web development](docs/web-development.md) for setup and current scope.
The interface supports separate technical HTML, Markdown, and combined HTML
exports with previews and downloads. Both HTML variants share their options;
combined documentation requires an assigned Markdown file.
Markdown is edited and saved in its assigned working file. Direct downloads do
not create build folders; unlinking an assignment preserves the file and enables
template generation again.
In the Markdown editor, **Abschnitt einfügen** inserts generated-section placeholders;
the image, table and link buttons add editable Markdown snippets at the cursor.
The link button inserts inline and uses selected text as the initial link label.
Already used placeholders are disabled. See the
[editor insertion guide](docs/markdown-content.md#inserting-content-in-the-editor).
The **Projekte** start page lists registered projects. **Neues Projekt** creates a
named YAML project from a chosen folder and one or more ontology files selected via
the native file chooser. By default, the optional copy mode includes ontology sources
and referenced local images with relative paths so the project folder can be moved.
Original files are never modified; disabling copy mode keeps external file links.
Language, parser, HTML theme and optional checks can be configured in the GUI.
The project counter, ontology table and HTML detail panel share the same known
notices: current project-file checks plus saved reports from linked HTML outputs.
Duplicate notices are counted once per ontology. These are saved build results,
not a fresh quality check of changed sources. Unlinking an output removes its
report; manually assigning HTML does not imply that it passed validation.
Without a saved report the table shows **Noch nicht geprüft** instead of a clean
result. Existing saved reports are also included after reopening a project.
See the [workflow audit and CLI/GUI comparison](docs/workflow-audit.md) for tested
workflows and remaining interface features.
Under **Portal** in the workspace navigation, select ontologies and a title on the left, then use **Portal
generieren** to build a shared documentation portal with preview and ZIP download.
The last successful portal remains available after reopening the project.
Before generating, choose **Hell**, **Dunkel**, or **Beide** for HTML, combined
documentation and portals. CLI: `--theme light`, `--theme dark`, `--theme both`.
With `both`, the timestamped folder contains `light/` and `dark/` variants; the
GUI preview switches variants and the ZIP includes both. Generated pages have
fixed themes, no theme toggle, and no stored visitor theme preference.
Portal theme selection applies to the index and all included documents.
Use the folder/unlink controls to attach an existing `index.html` or detach the
current portal before regenerating. Detaching preserves all files.
Existing projects support adding ontologies through a multi-file chooser in
**Projekteinstellungen**, optionally copying sources and images into the project.
Removing an ontology only unlinks it; files and generated outputs are preserved.

```bash
uv sync
```

## Basic usage

### A-Box knowledge graphs

Generate a separate instance-focused HTML document from your own RDF file:

```console
uv run ontolens abox path/to/instances.ttl --language de -o build/abox/instances.html
```

The A-Box mode has its own model, parser, and renderer. It includes a searchable
instance catalog, class filters, a Cytoscape graph with labeled relationships,
one-to-three-hop neighborhood views, optional literal nodes, three layouts,
PNG export, and incoming/outgoing relationship details. RDF language tags and
datatypes are preserved. `--language` selects preferred RDF labels; the current
viewer controls are German. Untyped subjects and blank nodes are included;
schema definitions are excluded, and object-only references are marked external.
No OWL reasoning or remote ontology imports are performed.

`--max-nodes 250` limits visible nodes, including optional literal nodes. All
resources remain in the searchable catalog and full HTML directory. A status
message identifies truncated views. This is a static in-memory viewer, not a
streaming interface for very large datasets. Formats: Turtle, RDF/XML,
N-Triples, and JSON-LD (`--format` can override detection).

JavaScript, styles, and library licenses are embedded directly in the HTML;
no `assets/` folder, server, or internet connection is needed for the viewer.
Each timestamped output bundle also includes the source download. Share the
entire output folder to keep that download available. Instance selections can
be linked with `#instance=<URL-encoded IRI>`.

Local delivery-note datasets are not distributed with the repository.

Build the configured LOIN, TempO and ISOProps collection and its static portal
after providing the example inputs locally or adapting the YAML to your own files:

```console
uv run ontolens build ontolens.example.yaml
```

Use `--ontology isoprops` to select one entry, or `--no-portal` to generate only
the documents. Settings can be overridden from the CLI, including negative
flags such as `--no-quality-report`. See [Projects and portals](docs/projects.md)
for configuration, precedence, output layout and publication instructions.

The existing single-file commands remain available:

```bash
uv run ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html
```

You can also run the package module directly:

```bash
uv run python -m ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html
```

If `-o/--output` is omitted, OntoLens uses `build/<input-stem>/<input-stem>.html`, relative to the current working directory. Every build is written to a timestamped directory inside that location. An explicit `--output` still controls the destination.

## Project layout

```text
examples/<ontology>/             Ontology source and optional Markdown
examples/<ontology>/figures/     Original local images
build/<ontology>/<timestamp>_<output-stem>/   Generated HTML or Markdown templates
build/legacy/                   Preserved earlier HTML builds and their assets
archive/example/                Unclassified old inputs, ZIPs and editor files
docs/                           OntoLens user documentation
```

For example, ISOProps sources live in `examples/isoprops/isoprops.ttl` and
`examples/isoprops/documentation.de.md`. Keep new ontologies in their own folders
with their original filenames. `build/` is ignored by Git; maintained inputs and
documentation stay outside it. Run the commands below from the project root.

**What belongs in Git:** source code (including bundled offline libraries and
licenses), tests, scripts, documentation, build configuration and both dependency
lockfiles. The entire `examples/` directory is currently local only, including
its Markdown and figures. The example paths in this guide refer to local inputs,
not files supplied by a fresh checkout. Keep personal projects in
`ontologies/` or outside the checkout. Local settings, exports, temporary files,
the contents of the legacy archive and Docker data are not versioned.
Commit `.env.example` and `ontolens.example.yaml`, not `.env` or the local
`ontolens.project.yaml`. For local GUI development, copy the example YAML to
`ontolens.project.yaml` in the repository root if no working project exists yet.

The legacy archive preserves the previous shared figures. LOIN and TempO have
local copies of those same images to preserve existing references; check that
they depict the intended ontology. TempO's referenced `LibraryOverview.svg` was
already absent from the original inputs and must be supplied separately.

## Output bundles

OntoLens never writes the HTML file directly to the requested output path. It creates a self-contained build directory with the local generation time and output stem:

```text
build/isoprops/
└── 2026-08-26T14-30-05_isoprops-combined-full/
    ├── isoprops-combined-full.html
    ├── downloads/
    │   └── isoprops.ttl
    └── img/
        ├── DataCatalogOverview.svg
        ├── OntologyOverview.svg
        └── PropertyAssignment.svg
```

For example, `-o build/isoprops/isoprops-combined-full.html` produces:

```text
build/isoprops/2026-08-26T14-30-05_isoprops-combined-full/isoprops-combined-full.html
```

The timestamp format is `YYYY-MM-DDThh-mm-ss`. All local images used by ontology metadata or Markdown content are copied into `img/`, including linked SVG image/use dependencies, and the generated HTML references those copies. External image URLs remain unchanged. The `img/` directory is created even when the documentation contains no images. The source ontology is copied into `downloads/` for single-file, project and GUI builds alike; input and output can be on different drives.

Generated HTML embeds all built-in JavaScript, including Cytoscape, its layout
libraries and their license notices. Graphs work offline when the HTML is opened
directly, without a server or an `assets/` folder. This applies to standalone and
combined documentation, light/dark variants, portal documents and A-Box viewers.
Keep `img/` and `downloads/` next to the HTML for figures and source downloads.
External image URLs and outbound links still require internet access; this is
not a complete archive of external resources. Older builds are not rewritten:
regenerate them to obtain the embedded scripts. Their existing asset folders
are not automatically deleted.

The CLI prints the actual generated HTML path after a successful build.

## Combined Markdown documentation

### Optional graph placeholders

Use `--show-missing-endpoints` to visualize object properties that declare only
domain or only range. The absent endpoint becomes a separate, unlabelled square
per property, using the same fill and border as class nodes, including in SVG
and PDF exports. Direction remains domain to range.
These are visual placeholders, not ontology classes or inferred axioms.
Properties with neither declaration stay hidden; datatype-property behavior is
unchanged. The quality report still reports the missing declarations when enabled.

```console
uv run ontolens examples/isoprops/isoprops.ttl --show-missing-endpoints --quality-report
uv run ontolens build ontolens.example.yaml --show-missing-endpoints
```

The default is off. Project YAML supports `show_missing_endpoints: true` in
`defaults` or an ontology entry; project builds also accept
`--no-show-missing-endpoints`. The GUI offers **Platzhalter für fehlende Domain/Range
im Graphen** in the HTML options. Regenerate existing HTML to apply the change.

Object-property connections also include named domain/range classes referenced
from external ontologies, even without a class declaration in the input file.
Datatype properties likewise include external domain classes, including union
members and ontologies with no locally defined classes. Properties with the same
domain and datatype remain grouped into one connection. External references do
not become local entries in the documentation's class catalog.
Enable **Alle deklarierten externen Klassen im Graphen** in the HTML generation
options, or pass `--include-external-classes`, to include every named `owl:Class`
or `rdfs:Class` declared in the input file, even external classes without any
connection to local terms. This option is off by default. Their
declared subclass and equivalence relationships are included where supported.
This does not fetch imported ontologies or add their undeclared classes, and does
not add external classes to local class counts or quality checks.
Project YAML accepts `include_external_classes: true` in defaults or individual
entries; `--no-include-external-classes` disables it for a project build. It applies
to technical HTML, combined HTML, both color variants, and documents in portals.
When disabled, external endpoints used by properties remain included as before.
Regenerate the HTML after changing this setting; existing files are unchanged.

All included external classes are visible initially. Uncheck **External references** in the graph toolbar
to hide external class nodes, their edges, and any literal nodes left without a
connection, and recalculate the layout. Both
graph filters use checked = visible and unchecked = hidden. This
can be combined with the datatype-property filter and affects graph image exports,
not the ontology or quality report.

`owl:unionOf` domains are expanded into their individual named class endpoints
in the graph, including nested unions. Object-property range unions are expanded
the same way; external members remain subject to the external-reference filter.
These edges show the alternatives of the union, not separate domain/range axioms.
The reference tables retain the complete `unionOf (...)` expression. Datatype
properties also support union domains; datatype range expressions remain grouped
literal nodes. Intersections are not expanded as unions.

Graph class colors identify namespaces: the main ontology uses petrol, while
other namespaces receive distinct muted colors. The ontology legend maps each
color to a prefix (or namespace URI); hover shows the full namespace. Empty
endpoint nodes use their property's namespace color, and literals remain white.
The legend follows the external-reference filter. PNG/JPG/SVG exports and PDF
graphs retain the colors and ontology legend.

Subclass connections use an unlabelled solid arrow pointing to the superclass.
The graph legend identifies this line style as `rdfs:subClassOf`, including in
PNG/JPG/SVG and PDF exports. Property names remain on their respective edges.

Double-click a class node to focus on its direct incoming and outgoing neighbors.
This view uses a compact network layout, larger wrapped labels and an automatic
fit to the available graph area. External IRIs use short namespace labels in this
view; their document links retain the complete IRI. Resizing the graph refits the
neighborhood. Connected overview graphs keep their hierarchical layout;
disconnected graphs use a network layout with larger labels and wrapped
namespace/class names. A spacing pass spreads dense centers across the available
width and height while preserving the relative ordering of nodes. Filters and resizing recalculate
that layout for the currently visible nodes. Full IRIs remain in the node links.
Exceptionally long property labels use the linked property identifier in this
view; hovering over the edge reveals the complete label. The fCoSE layout
libraries are embedded in each generated HTML document together with Cytoscape.
**Entire graph** restores the overview; visibility filters stay active in either
view. A single click selects a node without leaving the graph. The small arrow
inside each class node jumps to its reference entry (external class links open
their IRI in a new tab). These controls follow node dragging, pan, zoom and
fullscreen, but are not printed into graph exports. Image exports use the current
visible neighborhood; PDF exports continue to render the complete saved graph.

Edge labels search for free space close to their connection. Displacements are
bounded: crowded labels never stack above the entire graph or force long detours
that shrink the rest of the view. If the local area is full, the least-overlapping
nearby position is used; the neighborhood view provides more room for dense areas.
Connections bend through their labels so the relationship stays identifiable.
After automatic layouts, overlapping node rectangles are separated with a minimum gap.
On wide screens, the graph uses extra page width while prose retains its usual
reading width. The initial zoom prioritizes readable labels: large graphs can
extend beyond the viewport and can be explored by panning. Use **Zoom in** and
**Zoom out** for details, or **Fit entire graph** to see all currently visible
elements at once (with smaller labels). **Reset layout** restores the readable view.
Label positions are recalculated after layout changes, filtering and node dragging,
and are retained in PNG/JPG/SVG exports. Disconnected PDF graphs share the balanced
network layout and wrapped class labels; their complete graph is fitted to the
landscape page without viewport cropping. Connected PDF graphs retain their print
grid. The PDF graph remains a static snapshot on its own landscape page.

The graph toolbar separates visibility filters from layout and fullscreen tools.
Use the download icon to export PNG, JPG or SVG. The neighborhood and its return
button appear in a separate row. The collapsible **Legend** groups element styles
and ontology colors; hover over an ontology name to see its full namespace URI.

### Editorial content

Add `--check-content` to a build with `--content` to report missing or empty
Markdown chapters. Notices do not block HTML generation or appear on the page.
The check uses `profile: compact` or `profile: standard` in Markdown frontmatter
(default: `standard`), independently of the ontology quality report.

```bash
uv run ontolens examples/isoprops/isoprops.ttl --content examples/isoprops/documentation.de.md --check-content
```

Create a Markdown starting template with `init-content`:

```bash
uv run ontolens init-content examples/isoprops/isoprops.ttl --language de --profile standard
```

The template is created under `build/isoprops/<timestamp>_isoprops-documentation.de/`.
The command prints its path. Move it into `examples/isoprops/` when adopting it as
maintained input. An explicit `-o` still writes to that exact Markdown file path.

Choose `standard` (default) for the full chapter structure or `compact` for a shorter
guide. German and English templates are available. Existing Markdown files are
never overwritten. Optional chapter markers keep links stable when headings are
translated or renamed. Templates can be freely edited, reordered and shortened.

Use `--content` to combine a narrative Markdown document with the generated ontology reference:

```bash
uv run ontolens examples/isoprops/isoprops.ttl \
  --content examples/isoprops/documentation.de.md \
  -o build/isoprops/isoprops-combined.html
```

The Markdown can provide the page title, description, and language in YAML frontmatter. OntoLens slot comments place generated sections such as metadata, visualization, downloads, and the technical reference inside the narrative. Markdown headings and generated sections share one table of contents. The technical reference contains collapsible groups for every class and property category.

Ontology terms can be linked without hard-coding generated anchors:

```markdown
The class [[isoprops:Property|Property]] describes a reusable property definition.
```

See [Markdown content pages](docs/markdown-content.md) for all slots, defaults, link syntax, bundled image handling, and a complete example.

## Optional features

All documentation enhancement flags are opt-in. If a flag is not provided, the corresponding section or extra data is not rendered.

Show missing recommended ontology metadata as colored placeholders:

```bash
uv run ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html --recommendations
```

Include the ontology quality report:

```bash
uv run ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html --quality-report
```

Show custom `owl:AnnotationProperty` values in class and property tables:

```bash
uv run ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html --custom-annotations
```

Combine flags when you want the richer review-oriented output:

```bash
uv run ontolens examples/isoprops/isoprops.ttl -o build/isoprops/isoprops.html --recommendations --quality-report --custom-annotations
```

## Input formats

Supported input formats are inferred from the file extension:

- `.ttl` as Turtle
- `.rdf`, `.owl`, `.xml` as RDF/XML
- `.nt` as N-Triples
- `.jsonld`, `.json` as JSON-LD

Use `--format` to pass an explicit RDFLib parser format.

## Generated page

The generated HTML can include:

- ontology metadata, creators, contributors, and figures
- a timestamped output bundle with copied local images
- JSON-LD metadata annotations for crawlers
- used ontology and download sections
- namespace prefixes and overview counts
- a cross-reference for classes and properties
- optional narrative Markdown chapters with one shared table of contents
- collapsible OWL restriction summaries
- detected class instances, shown discreetly in class tables
- an interactive Cytoscape.js graph with fullscreen view, bundled datatype-property edges, a clickable property inspector, datatype filtering, and PNG/JPG/SVG export with a datatype legend

The quality report, recommendation placeholders, and custom annotation-property rows are only included when their flags are set.

## Roadmap

- Improve rendering of OWL restrictions and SHACL shapes.
- Add multi-page output for larger ontologies.
- [ ] When a reader selects a full-text search result, scroll to the exact occurrence shown in its excerpt and briefly highlight the matched text, including in long Markdown chapters.
