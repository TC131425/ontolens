# Use the web workspace

Start with the [Docker quick start](../README.md#use-the-web-app-with-docker).
This guide uses the English interface labels. Use the language selector in the
header to switch without leaving your project or editor. The app remembers your
choice in this browser. On first use, it picks the first supported browser
language (English or German), falling back to German. **Document language**
is a separate setting for the generated document.

## Create or open a project

On **Projects**, choose **New project**, enter a name, choose a parent folder and
use **Add files** to select one or more ontologies. **Create project** writes
`<name>-project/ontolens.project.yaml` and opens the workspace. Existing folders
are not overwritten. To work with an existing project, use **Open project** and
select its YAML file. The project selector switches among registered projects.

Leave **Copy ontologies and local images into the project** checked for a portable
project. OntoLens copies sources into `sources/<ontology-id>/`, copies referenced
local images and adjusts paths in the copies; originals remain untouched. Missing
local images block copying. With copying off, the project links to the original
files instead. Moving them can break those links. In Docker, the picker browses
[mounted folders](docker.md#choose-storage); outside Docker it uses the backend computer's native dialog.

## Choose an output

Select an ontology under **Ontologies**. The middle column controls the export;
the right column previews the selected tab. The navigation stays in place.

| Tab | Input | Result |
| --- | --- | --- |
| **HTML documentation** | Ontology only | A read-only reference with metadata, classes, properties and a graph. |
| **Markdown** | An existing `.md` file or a generated compact/standard template | An editable working file. Saving updates that file, not a new timestamped copy. |
| **Combined documentation** | Ontology and linked, saved Markdown | An HTML page with chapters and the generated reference. You do **not** need to generate standalone HTML first. |

In either HTML tab, choose **Color scheme** (Light, Dark or Both) and any checks,
then generate. Pending export options are saved before the build. Look **below the
generate button** for grouped findings from that run. Quality findings appear
only when the quality report is enabled. Changing an option does not change a
previous export. With Both, the preview can switch variants and the ZIP contains both.

The project overview counts known notices from current file checks and the saved
reports of linked exports. It does not rerun quality checks on edited sources.
**Not checked yet** means there is no saved report, not that the ontology passed.
Unlinking a document removes its report; linking an arbitrary HTML file does
not supply a new one.

On the Markdown tab, link an existing file or select a template profile and
**Generate and link Markdown**. Switch between **Read** and **Edit**, use **Save**
(or Ctrl+S / Cmd+S) to write changes, and **Check** to inspect an unsaved draft.
Results appear below the document; missing or empty chapters do not block saving.
The reader displays local images relative to the Markdown file. Generated section
slots expand only in combined HTML. See [Markdown authoring](markdown-content.md)
for insertion tools, image checks and supported syntax.

## Reuse or unlink a file

Generating HTML automatically links the result. Use the folder icon beside
**Linked HTML file** to link an existing HTML file instead. The two HTML tabs have
independent links. Unlink before generating a replacement; the previous file
remains on disk. The same rule applies to a linked portal. Unlinking Markdown
makes template generation available again and disables new combined builds until
another Markdown file is assigned. Already generated combined HTML remains readable.

Links to HTML and portals live beside the project YAML in `<config-stem>.outputs.json`
and survive restarts. The CLI does not set these links. Generated outputs offer
a bundle download; manually linked HTML offers the original file. Keep its
referenced resources alongside it for preview. To hand off a whole editable
project, use [project ZIP export](project-export.md), not just the HTML download.

## Build a shared portal

1. Open **Portal** in the workspace. Enter a title and select the ontologies to include.
2. Choose a color scheme and select **Generate portal**. Each selected ontology is built
   from its saved options and linked Markdown, if any. No existing HTML export is required.
3. Preview the index on the right or download the ZIP. The bundle includes the
   documents and links back to the index. Both themes produce two complete portals.

Changing the selection does not rewrite the current portal or the YAML defaults
used by the CLI. Unlink the previous portal before generating a new snapshot.
To link an existing one, select its `index.html` and keep its subfolders in place.

## Manage projects and members

Use **Project settings > Project ontologies > Add ontologies** to add files with
the same copy-or-link choice as during project creation. Removing an ontology
updates the project, not the source files or historical exports. Rebuild a portal
to reflect the new membership. An existing project can have no members; it must
have at least one to build a portal.

Removing a project from the **Projects** list only unregisters it. Its files and
builds remain on disk; use **Open project** to register the YAML again.
Under **Project settings > Share project** you can [package the project](project-export.md)
or [print linked documents to PDF](pdf-export.md).
