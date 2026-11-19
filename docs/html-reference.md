# Generate and read an HTML reference

Use a reference page when you want to document what an ontology declares. Use a
[combined page](markdown-content.md) to add editorial text, or the [instance viewer](#explore-instances-instead)
to explore individuals and their relationships rather than the schema.

## Build and share the page

```sh
uv run ontolens demo.ttl -o build/library.html
```

The [quick start](../README.md#generate-html-from-the-command-line) supplies `demo.ttl`.
The CLI recognizes Turtle (`.ttl`), RDF/XML (`.rdf`, `.owl`, `.xml`), N-Triples
(`.nt`) and JSON-LD (`.jsonld`, `.json`). Use `--format` to override parser detection
and `--language` to prefer a language for RDF labels and comments.

The command prints the actual HTML path. An output argument is a *filename*, not
the final folder: `-o build/library.html` creates this layout:

```text
build/<YYYY-MM-DDThh-mm-ss>_library/
  library.html
  img/                 # copies of local figures, including SVG image/use dependencies
  downloads/demo.ttl   # the original ontology
```

Without `-o` the bundle is created under `build/<input-stem>/`. Select `--theme light`
(default), `dark` or `both` before building. With `both` the bundle has separate
`light/` and `dark/` directories; the pages have no theme switch. Copy the whole
bundle for publication. Styles and graph scripts (including Cytoscape and its layout
libraries) are embedded; no server, CDN or `assets/` folder is required. Remote
images and outbound links stay external. Regenerate older documents to embed scripts.

## Find a term

The table of contents links to metadata, contributors, figures, namespaces,
used ontologies, downloads and the cross-reference. Class and property entries
show labels, comments and OWL relationships; expand restrictions or instance
lists to inspect them. Metadata is also embedded as JSON-LD for crawlers.

Search above the contents to filter **only the navigation**. Under **Search in**,
choose among multilingual names and labels, IRIs and prefixed names, descriptions
and comments, and (in combined pages) Markdown chapters. A body-text match shows a
highlighted excerpt; selecting it opens the associated entry or chapter. Escape
clears the search without changing the document.

## Choose what to check

All of these options are off by default and can be combined:

| Option | Effect |
| --- | --- |
| `--quality-report` | Report missing labels, comments, property domains/ranges and ontology metadata. |
| `--recommendations` | Show missing metadata in its usual table position, distinguishing recommended and optional fields. |
| `--custom-annotations` | Show custom annotation-property values in the class and property tables. |
| `--check-content` (with `--content FILE`) | Report empty or missing Markdown chapters at build time, not in the HTML. |

For repeatable builds, put these settings in the [project YAML](projects.md#configuration).

## Read the graph

Classes are rectangles colored by namespace. The **Legend** maps colors to prefixes
or namespace IRIs and shows the line styles. An unlabelled solid arrow points to a
superclass; a double line denotes equivalence. Object properties are labelled edges.
Datatype properties sharing a domain and datatype are grouped on one connection;
inspect it for the individual properties.

Double-click a class for its direct incoming and outgoing neighbors. Use the small
arrow inside a node to open its reference entry (or its external IRI). **Entire graph**
restores the overview. **Datatype properties** and **External references** are
checked when visible; unchecking either filters the graph and recalculates the layout.
Pan, zoom, enter fullscreen or use **Fit entire graph** for the current selection.
PNG, JPG and SVG exports reflect the visible graph; [PDF export](pdf-export.md)
renders a fresh snapshot of the full graph on a landscape page.

| What the ontology declares | What the graph shows |
| --- | --- |
| Named domain and range, including external classes | A connection between the endpoints. External classes need not be declared locally. |
| A domain or object range using `owl:unionOf` | Named alternatives, including nested unions, get separate connections. The reference table keeps the complete expression. Intersections are not treated as unions. |
| An object property with exactly one missing endpoint | Hidden by default. `--show-missing-endpoints` draws an unlabelled square for the missing endpoint; it does not infer a class or suppress quality findings. |
| An object property with neither endpoint | Hidden, even with placeholders enabled. |
| Explicitly declared but otherwise unrelated external classes | `--include-external-classes` adds them. It does not fetch imports or change local class counts. |

Both graph options are available in the web app and in project YAML.
A generation option changes **new exports**; filters in an already generated graph
only affect the view. Datatype properties are not affected by the placeholder option.

## Explore instances instead

For an A-Box (instance-focused RDF file), use the separate CLI command:

```sh
uv run ontolens abox instances.ttl --language en --max-nodes 250 -o build/instances.html
```

The result has a searchable instance catalog, class filters, one- to three-hop
neighborhoods, optional literal nodes, incoming/outgoing relationships and PNG export.
The node limit applies to the visible graph, not the catalog. Untyped subjects
and blank nodes are included, schema definitions are excluded and object-only
references are marked external. No OWL reasoning or remote imports are performed.
`--language` selects preferred RDF labels; the standalone instance viewer's controls
are German, independently of the web app's language. Share the whole timestamped
folder to include the RDF download. Link to an individual with `#instance=<URL-encoded IRI>`.
