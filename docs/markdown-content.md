# Markdown content pages

OntoLens can combine editorial Markdown with the automatically generated ontology documentation. This is useful for pages that need a conceptual introduction, examples, diagrams, and usage guidance in addition to the technical class and property reference.

Without `--content`, OntoLens continues to generate the regular standalone reference page.

Keep each ontology and its Markdown in `examples/<ontology>/`, with original
images in its `figures/` subdirectory. Relative image references such as
`figures/OntologyOverview.svg` continue to work. Run examples from the project root.
Without `--output`, HTML is written beneath `build/<input-stem>/` in the current
working directory. Explicit output paths override this destination. `build/` is
ignored by Git and contains generated results, including new Markdown templates.
Move a template into `examples/<ontology>/` when adopting it as maintained input.

## Generate a combined page

Start with an editable template (this creates Markdown, not an HTML build):

```bash
uv run ontolens init-content examples/isoprops/isoprops.ttl --language de --profile standard
```

`--profile standard` is the default. `--profile compact` provides introduction,
scope, conceptual model, usage examples and the generated reference. `standard`
adds modeling decisions, interoperability, validation, maintenance and references.
Both profiles include slots for the existing generated sections. The source
ontology supplies the title and generated metadata; authoring hints are invisible
HTML comments. Replace them with your own reviewed prose and examples.

`--language` accepts `de` or `en` (default). `--format` selects an RDFLib parser
when needed. Without `-o`, the generated template is written to
`build/<input-stem>/<timestamp>_<input-stem>-documentation.<language>/<input-stem>-documentation.<language>.md`
relative to the working directory. The command prints the actual path.
An explicit `-o` writes to that exact Markdown path, without adding a timestamp.
Existing files are never overwritten, including repeated calls in the same second.
Choose another output path or retry later if the file already exists.

For continued editing, move the template to `examples/isoprops/guide.de.md`.
Alternatively, use `-o examples/isoprops/guide.de.md` to deliberately create a
maintained input directly. The HTML build below assumes that maintained location.

Build the newly created document with:

```bash
uv run ontolens examples/isoprops/isoprops.ttl --content examples/isoprops/guide.de.md -o build/isoprops/isoprops-guide.html
```

Use `--check-content` to report missing or empty chapters while still generating
the HTML. Empty chapters are allowed; the profiles remain starting templates,
not enforced schemas.

## Optional completeness check

```bash
uv run ontolens examples/isoprops/isoprops.ttl --content examples/isoprops/documentation.de.md --check-content
```

The check prints notices to standard error and does not change the generated
page. Missing or empty chapters do not change the successful exit status.
`--check-content` requires `--content` and is independent of `--quality-report`.
Without the flag no completeness check is performed.

Set `profile: compact` or `profile: standard` in YAML frontmatter. New templates
include their profile; older files default to `standard`. Invalid profiles are
reported as configuration errors when the checker is enabled.

Chapters are identified by their optional `ontolens:chapter` key. Without a key,
the exact German or English template heading (ignoring case) or the key itself
is recognized. Use a marker for translated or freely renamed headings.
`compact` checks introduction, scope, conceptual model and usage; `standard`
also checks design decisions, interoperability, validation, maintenance and references.

A chapter is empty if it contains only comments, headings or generated section
slots. Text, lists, tables, code examples and images count as content, including
content in subsections. A heading of the same or higher level, or another marked
chapter, ends the checked section. Markers in fenced code blocks are ignored.
Technical reference and metadata slots are not required by the checker because
the HTML generator supplies these automatically.

This is a structural check: it does not judge correctness, text quality or whether
prose such as `TODO` has been meaningfully completed. No chapter changes are made.

```bash
uv run ontolens examples/isoprops/isoprops.ttl \
  --content examples/isoprops/documentation.de.md \
  -o build/isoprops/isoprops-combined.html
```

The output name determines the HTML filename and bundle name. OntoLens prefixes the bundle directory with the local generation timestamp:

```text
build/isoprops/2026-08-26T14-30-05_isoprops-combined/
├── isoprops-combined.html
└── img/
```

This timestamped bundle behavior applies to regular ontology documentation and combined Markdown documentation alike.

All existing opt-in flags can be combined with `--content`:

```bash
uv run ontolens examples/isoprops/isoprops.ttl \
  --content examples/isoprops/documentation.de.md \
  --recommendations \
  --quality-report \
  --custom-annotations \
  -o build/isoprops/isoprops-combined-full.html
```

## Frontmatter

An optional YAML block at the start of the file controls the page presentation:

```yaml
---
language: de
title: ISO 23386 Property Ontology (ISOProps)
description: Fachliche Einführung und technische Ontologiereferenz.
---
```

- `language` sets the HTML language and selects German or English generated section labels.
- `title` replaces the ontology title in the page header, but does not change the ontology data.
- `description` replaces the header subtitle, but does not change the ontology metadata table.
- `profile` selects `compact` or `standard` for `--check-content` (default: `standard`).
- An explicit CLI `--language` takes precedence when OntoLens selects ontology labels and comments.

## Generated section slots

Place a slot on its own line where a generated section should appear:

```markdown
<!-- ontolens:visualization -->
```

Supported slots:

| Slot | Generated content |
| --- | --- |
| `metadata` | Ontology metadata followed by creators and contributors |
| `figures` | Figures discovered in the ontology metadata |
| `quality-report` | Quality report when `--quality-report` is enabled |
| `prefixes` | Namespace prefix list |
| `used-ontologies` | Imported and referenced ontologies |
| `downloads` | Available ontology downloads |
| `visualization` | Interactive Cytoscape.js graph |
| `overview` | Counts for classes and property categories |
| `cross-reference` | Complete technical reference |

`namespaces` and `namespace-prefixes` are aliases for `prefixes`. `quality` is an alias for `quality-report`.

Each slot may occur at most once. An unknown or repeated slot stops the build with a descriptive error.

### Inserting content in the editor

In the GUI, switch the Markdown pane to **Bearbeiten**. The insert toolbar contains:

- **Abschnitt einfügen**: select a generated section to insert its slot comment.
  Already used slots are disabled, including their aliases (`quality`, `namespaces`
  and `namespace-prefixes`). Deleting a slot makes it available again.
- **Bild einfügen** (image icon): enter a relative image path or URL and alternative
  text. The initial values provide a quick editable example. The action inserts
  Markdown only; it does not upload or copy a file. The image must already be
  accessible relative to the assigned Markdown file or via its URL.
- **Tabelle einfügen** (table icon): choose 1-10 columns and 1-50 data rows.
  OntoLens adds a header row and editable sample cells automatically.
- **Link einfügen** (chain icon): enter a destination and link text. Selected
  editor text becomes the initial link text. An empty link text uses the destination.
  Web addresses (`https://` or `http://`), `mailto:` and relative links or fragments
  are supported. The link replaces the selection inline, without starting a new paragraph.

Sections, images and tables insert a separate Markdown block at the last cursor position,
replacing selected text if there is a selection. Without an existing cursor
position, the block is appended to the document. The editor regains focus after
insertion. Changes remain unsaved until **Speichern** or **Ctrl+S** is used.
Switch to **Lesen** to see images and formatted tables. Generated-section slots
are expanded only when the combined HTML documentation is built; selecting a
quality-report slot does not enable the quality-report option by itself.

### Default placement

Slots are optional positioning instructions. OntoLens keeps generated information available even when a marker is omitted:

- Metadata is placed before the Markdown content.
- Other available generated sections are placed before the technical reference.
- The technical reference is appended at the end.
- If all ontology figures are already embedded with Markdown image syntax, the additional grouped figures section is omitted. An explicit `figures` slot always renders it.

## Web links and internal links

Use explicit Markdown links so both the reader and generated HTML display them
as clickable links:

```markdown
[Project website](https://example.org)
[Technical reference](#cross-reference)
[Contact](mailto:person@example.org)
<https://example.org>
```

A bare URL such as `https://example.org` is automatically linked by the GUI's
GFM reader but remains plain text in the HTML export. Use one of the explicit
forms above or **Link einfügen** in the editor. The button may put angle brackets
around the destination inside parentheses; this is valid Markdown as well.
Links are references only: linked local documents are not automatically copied
into the output folder. Save the Markdown and regenerate combined HTML to apply edits.

## Links to ontology terms

Use wiki-style references to link narrative text to generated term entries:

```markdown
[[isoprops:Property]]
[[isoprops:Property|Merkmal]]
[[https://w3id.org/isoprops#Property|Merkmal]]
```

The first form uses the generated term title as link text. The second and third forms provide custom link text. CURIEs and complete term IRIs are supported.

OntoLens resolves these links from the parsed ontology and writes the correct local fragment link. Unknown terms stop the build instead of producing a silently broken link.

## Headings and table of contents

Optional chapter markers assign language-independent anchors to the next heading:

```markdown
<!-- ontolens:chapter introduction -->
# Einleitung

Describe the purpose and audience here.
```

This produces `#chapter-introduction`, also used in the table of contents.
Renaming the heading to `Introduction` preserves that link. Markers must precede
a level 1-3 heading, and keys must start with a lowercase letter and contain only
lowercase ASCII letters, digits and hyphens. Keys must be unique. Custom keys are
allowed. A missing heading, duplicate key or conflicting anchor raises an error.
Code examples containing chapter markers remain code examples.

Suggested keys are `introduction`, `scope`, `conceptual-model`, `design-decisions`,
`usage`, `interoperability`, `validation`, `maintenance` and `references`.
The technical reference already has its stable `cross-reference` anchor; use its
slot directly instead of adding a duplicate heading. Existing Markdown without
chapter markers remains supported.

The recommended chapter coverage draws on
[Garijo and Poveda-Villalon (2020)](https://dgarijo.com/papers/best_practices2020.pdf),
[W3C vocabulary management principles](https://www.w3.org/2006/07/SWD/Vocab/principles)
and [MIRO](https://pmc.ncbi.nlm.nih.gov/articles/PMC5774126/).
The template is an OntoLens editorial choice, not a prescribed W3C chapter list.

Markdown headings receive stable HTML anchors and are added to the same left-hand table of contents as the generated sections:

```markdown
# Conceptual model

## Property groups

## Property assignment
```

The technical reference appears as one entry with collapsible groups for classes, object properties, datatype properties, annotation properties, and RDF properties. Each group contains direct links to its terms and shows its term count.

The offline navigation search includes chapter headings and the text that follows
them, including lists and tables. Each matching chapter appears once, with a
highlighted excerpt for a body-text match. Text before the first heading is
listed as **Introductory text**. Inserted ontology sections are not indexed as
chapter text. Readers can turn off **Markdown chapters** under **Search in**,
or leave only that area enabled to search editorial content alone.

## Images and other Markdown

Relative image paths are resolved from the Markdown file and copied into the generated `img/` directory:

```markdown
![Overview of the ontology](figures/OntologyOverview.svg)
```

The generated HTML then uses `img/OntologyOverview.svg`. Images referenced by ontology metadata are bundled in the same way. When different source directories contain images with the same filename, OntoLens adds a numeric suffix such as `figure-2.svg`. Repeated use of the same source image reuses one copy.

External `http:`, `https:`, and data-URI images are not downloaded and remain unchanged. The `img/` directory is always present, even if it is empty.

### Images in the local editor

The **Lesen** view displays Markdown images, including local SVG, PNG and JPG
files. Relative paths are resolved from the assigned Markdown file, not from the
project configuration or the export folder. This also works in Docker when the
files are on a mounted drive. Prefer relative paths to keep projects portable.

While editing, OntoLens checks image references after a short typing pause.
Missing local files and unsupported formats appear below the editor. **Prüfen**
refreshes the image check as well as the chapter check, for example after adding
a missing file. These notices do not block saving the Markdown. A combined HTML
build still fails if a referenced local image cannot be copied.

Remote images load directly in the browser and need internet access; OntoLens
does not check remote servers. Broken or blocked images show a fallback message
in the reading view. Inline HTML remains supported by the HTML exporter, but is
not rendered as HTML in the editor's reading view.

**Ctrl+S** (or **Cmd+S** on macOS) inside the Markdown pane uses the same save
action as **Speichern**. It does not open the browser's save-page dialog. Existing
conflict checks and the disabled state of the save button still apply.

The navigation stays in place while the settings column and document preview
scroll independently. The same column behavior applies to the portal workspace.

OntoLens supports standard Markdown paragraphs, links, lists, tables, fenced code blocks, footnotes, and inline HTML. Local images in inline HTML are bundled as well. Inline HTML should only be used with trusted local Markdown files.

## Minimal complete example

````markdown
---
language: en
title: Example ontology
description: Concepts, usage, and technical reference in one page.
---

<!-- ontolens:metadata -->

# Introduction

The class [[ex:Thing|Thing]] is the central concept of this ontology.

<!-- ontolens:visualization -->

# Usage

```turtle
ex:item a ex:Thing .
```

<!-- ontolens:used-ontologies -->

<!-- ontolens:downloads -->

<!-- ontolens:prefixes -->

<!-- ontolens:overview -->

<!-- ontolens:cross-reference -->
````

The complete German ISOProps example is available at [`examples/isoprops/documentation.de.md`](../examples/isoprops/documentation.de.md).
