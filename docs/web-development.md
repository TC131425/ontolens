# Local web application

The React application is separate from the static generated documentation.
The initial foundation supports reading the configured project, selecting its
ontologies, inspecting effective options, and reading Markdown as source or
formatted text, editing and saving Markdown, and exporting documentation. It also
supports opening and switching between existing project configurations. The ontology options can
now be changed and saved with Apply, including language, RDF parser and skipping
missing ontology images. Empty language/parser fields mean automatic selection;
`null` overrides a project default without changing other ontology entries.
Template generation also saves pending options first. Template languages are
German and English; HTML can use other RDF label language tags.
Native file pickers can assign source and
Markdown files and the project-wide output directory. Selections are saved
immediately. The native chooser runs on the backend computer and needs a local
desktop with Tk support. With `ONTOLENS_DATA_ROOT` set (Docker), the same buttons
instead open the in-app file browser for the mounted data folder; no Tk is needed.
See [Docker deployment](docker.md) for startup and data preparation.
Canceling it leaves the configuration unchanged.

When no Markdown file is assigned, select compact/standard and generate a template.
It is written into a timestamped directory under the configured output root,
then assigned to the ontology. Existing assignments cannot be overwritten by
template generation. Manually assigning Markdown disables the profile selector
as well. If assignment fails after generation, the generated file may remain for
recovery. Saving options writes ontology-specific overrides, preserves YAML comments,
and rejects stale revisions with a conflict error. Reload before retrying after
an external file change. Markdown checks require an assigned Markdown file.
Images in the Markdown reader are
currently represented by their captions; OntoLens slots are not rendered here.

## Export workflow

Source, output directory, language and parser are shared across the three tabs:

- **HTML-Dokumentation** generates the technical reference without editorial Markdown.
- **Markdown** assigns or generates a compact/standard working file. Use
  **Lesen / Bearbeiten** in the preview toolbar to switch views and **Speichern** to update that
  same file. **Markdown herunterladen** downloads the saved file directly, without
  creating another build directory. Local image references remain unchanged.
- **Kombinierte Dokumentation** generates one HTML page from the ontology and the
  assigned Markdown. It requires Markdown, but no previously exported HTML file.

HTML options are shared by both HTML variants. Pending option changes are saved
before export. **Platzhalter für fehlende Domain/Range im Graphen** enables
per-property dashed placeholder nodes for object properties with exactly one
missing endpoint declaration. It is off by default and saved as
`show_missing_endpoints`. No ontology triples are changed. Missing declarations
remain findings in an enabled quality report; datatype properties are unchanged.
Regenerate already linked HTML to apply new options. Portal builds also use this
per-ontology setting. Pending option changes are saved
before export. Markdown checks run on combined exports when enabled.
**Alle deklarierten externen Klassen im Graphen** includes all named external
class declarations, even without connections to local classes. It is off by
default and saved per ontology as `include_external_classes`. The setting is
shared by both HTML tabs and portal document builds. Turning it off keeps
external property endpoints but omits the extra declarations. The generated
graph's **External references** filter remains a separate display control.
Existing linked HTML is not modified; unlink and regenerate to apply a change.
The **Farbschema** selection offers **Hell**, **Dunkel**, or **Beide**, independently
of the application's own theme. It is saved as `theme: light`, `dark`, or `both`.
Generated pages have a fixed theme with no switch or stored visitor preference.
With **Beide**, one build folder contains `light/` and `dark/`, each with its HTML,
images and source downloads. The GUI preview can switch between these variants;
the ZIP contains both, and linking/unlinking manages the whole generated pair.
Manually assigned files remain individual, unchanged HTML files.
CLI equivalents: `ontolens input.ttl --theme dark` and
`ontolens build project.yaml --theme both`. The default is `light`.
Figures and the graph canvas retain a light background for legibility and export.
The right-hand preview follows the selected tab; HTML is shown after generation.
HTML generation notices appear below its generation button, separately for each
HTML variant. They include findings from the enabled quality report and skipped
ontology images. With quality reporting disabled, its checks are not run.
Notices are grouped into collapsed sections with counts (metadata, labels,
descriptions, domain/range, and images). Metadata distinguishes recommended and
optional fields. Long groups scroll internally; unknown messages remain visible
under additional notices.
Each HTML export gets a new timestamped directory below `<output>/<ontology-id>`.
HTML downloads are ZIP archives containing the generated page, copied images and
the ontology source download. External scripts may still require internet access.
Markdown downloads are individual `.md` files. Generated files remain on disk;
HTML assignments and their preview/download links survive API and browser restarts.
Only one generation runs at a time. The existing CLI remains independent.
Linked SVG image/use dependencies are copied into exports and available in previews.
Source and output may reside on different Windows drives.

### Linked HTML outputs

Each ontology has separate assignments for technical and combined HTML. Generation
automatically links its result; the last linked file is loaded when opening the app.
Use the folder button next to **Verknüpfte HTML-Datei** to select an existing `.html`
or `.htm` file, including older builds. The unlink button removes the assignment,
not the HTML or its assets. Unlink first to generate a new output. HTML is read-only;
editing sources or options never changes an already linked output.

Assignments are stored beside the project YAML in `<config-stem>.outputs.json`,
which is local state excluded from Git. Keep this file to retain assignments.
The CLI does not change these UI assignments. Existing builds are not scanned or
automatically linked; select them explicitly once. Missing linked files are shown
as unavailable and can still be unlinked or replaced.

Generated outputs retain their ZIP download. Manually linked outputs offer the HTML
file download without copying or modifying it. For previews, keep local assets
beside the HTML or in subfolders (such as `img/`); references outside that directory
are blocked. Only the HTML and referenced local dependencies are served, not unrelated
files in its folder. HTML previews remain sandboxed.

Newly generated documentation embeds Cytoscape, layout helpers and library
licenses directly in the HTML. No graph script is loaded from a CDN or an
`assets/` directory. This also applies to combined documents, portal pages and
A-Box viewers. Local images remain in `img/`, source downloads in `downloads/`.
Older linked HTML is left unchanged and may still need its original assets;
regenerate it to use the offline graph. External image URLs remain online.

The unlink icon next to the assigned Markdown removes only its project assignment,
never the file. It disables Markdown checks and makes
template generation available again. Combined generation requires assigned, saved
Markdown; an already linked combined HTML remains viewable without Markdown.
Unsaved edits must be saved first. Saving checks the project revision and
file hash to reject conflicting external changes. Reload before retrying a conflict.

**Prüfen** checks the current editor draft, including unsaved edits, without writing
any files. The collapsible results below the document area list missing and empty chapters
for the Markdown's compact/standard profile. This is a structural completeness check,
not a semantic review. Results are marked stale after edits. Reading and editing use
the same available document area. The UI no longer exposes a Markdown-check checkbox;
the CLI/project `check_content` option remains available for automatic build checks.

The Markdown editor includes a section dropdown and image/table/link insertion buttons.
They insert into the unsaved draft at its last cursor position, replacing selected
text. Existing section slots are disabled, including aliases. Image paths are
references to existing files or URLs, not uploads; tables include an editable
header and the requested number of data rows. Links are inserted inline and can
use selected text as their label; explicit Markdown links work in both the reader
and combined HTML (bare URLs are only auto-linked in the reader). See
[Inserting content in the editor](markdown-content.md#inserting-content-in-the-editor).

### Project selection

The application starts on **Projekte**, a searchable overview of registered projects
with their name, ontology count and configuration path. Open a project from its row,
or return to this overview using **Projekte** in the sidebar.
The header selector switches between opened project configurations. The folder
button opens an existing project YAML using the native file chooser. Files are
validated before opening; canceling leaves the selected project unchanged.
Projects retain separate ontology options, Markdown files, output folders and HTML
assignments. Pending edits require confirmation before switching; active writes
must finish first. Startup remains on the overview instead of automatically opening
the previously selected project.

The recently opened list is stored in `<startup-config-stem>.projects.json` beside
the startup YAML. It is local state excluded from Git. Each project has an isolated
API under `/workspaces/<id>/api`; the default project also remains at `/api`.
Vite proxies both paths. Existing CLI YAML projects can be opened directly.
Missing source or Markdown files do not prevent opening a project in the GUI:
the overview reports them and the file controls can repair/unlink assignments.
CLI builds continue to reject missing inputs. Existing HTML remains independently
viewable. Confirming discard when leaving the editor actually reloads the saved
Markdown on return; unsaved option changes also trigger the browser close warning.

See [Workflow audit and CLI parity](workflow-audit.md) for automated coverage and
the remaining GUI gaps (A-Box and project defaults).

### Generate a shared portal

Open a project and choose **Portal** in the workspace navigation. Enter a title
and select ontologies with checkboxes in the left column. The right column shows
the last generated portal, with open/download controls and an expandable file path.
On smaller screens, the preview follows the selection vertically. Generation
notices remain below the generate button. A changed selection is marked as not yet
generated; it does not alter the existing preview until generation succeeds.
Adding/removing project members remains under **Projekteinstellungen**.
**Alle auswählen** selects or clears the complete list. At least one ontology
and a nonempty title are required. Press **Portal generieren**.

The API uses the same `build_project` generator as the CLI. Each selected entry
uses its saved options and assigned Markdown, when present; otherwise it produces
technical HTML. Existing individually linked HTML files are not reused or changed.
The **Farbschema** selection overrides the fixed theme of the portal index and all
included documents for this build only. **Beide** creates complete `light/` and
`dark/` portals in one build folder, each with its own index and documents.
Individual ontology settings are not rewritten. Generated pages contain no theme
switches. Existing linked HTML is never restyled by changing this setting.
CLI equivalent: `ontolens build CONFIG --theme both`.
The portal contains links to all selected documents and each document links back.

Results appear under `<output>/portal/<timestamp>_<project-name>/index.html`.
The ZIP beside that directory contains the entire portal, documentation pages,
source downloads and copied local images. The UI provides an inline preview,
**Portal öffnen**, **ZIP herunterladen**, and generation notices.

The last successful portal, its title and selection are stored in the project's
`.outputs.json` under the reserved `$portal` key. They survive reopening and moving
the complete project folder. Failed builds do not replace the last successful
assignment; partial output can remain. After unlinking, new builds create new
timestamped bundles. As in the CLI, a same-second name collision is rejected.

Generating automatically links the portal. While linked, generation is disabled
until **Portal entkoppeln** is used. The folder icon by **Verknüpfte Portaldatei**
opens a native HTML chooser: select the existing portal's `index.html`, keeping
its documentation/asset subfolders alongside it. Unlinking only removes the
assignment; it never deletes files. The last build's title, selection and theme
remain available. Missing linked files can also be unlinked or replaced.
Manually assigned HTML is not parsed to infer build settings and offers an HTML
download, not a synthesized ZIP. Generated assignments retain their ZIP download.
Assignments persist after restart and use relative paths within the project.
`PUT /api/portal/html` accepts `revision` and `path` (null or omitted to unlink).

GUI title/selection are build-specific and do not rewrite YAML `portal.enabled`,
`portal.title` or CLI defaults. External scripts/images can still require internet.
The write endpoint is `POST /api/portal/export` with `revision`, `title`, a
nonempty `ontologies` array and optional `theme` (`light` by default, `dark`, or `both`).
It shares the individual-export generation lock; assigning/unlinking during a
build is rejected.

**Neues Projekt** opens a form on the overview. Enter a project name, select a parent
directory and add one or more ontologies with the native multi-file chooser. More
files can be added in successive selections; duplicate paths are ignored and entries
can be removed before creation. At least one readable ontology is required.

Creation writes `<name-slug>-project/ontolens.project.yaml` into the selected directory,
sets the output to that project's `build/` directory and opens the project immediately.
Existing directories are never overwritten. **Ontologien und lokale Bilder ins Projekt
kopieren** is enabled by default. Each ontology is copied into `sources/<ontology-id>/`
with its referenced local images in `img/`; the YAML uses relative source paths.
Markdown image references, HTML image tags and `foaf:logo` / `foaf:depiction` are
processed; linked local SVG image/use dependencies are included. Paths in copied
ontology annotations are adjusted as needed, which may reformat the copied RDF.
Original files remain unchanged. Missing images cause an explicit error rather than
silently producing a broken bundle. Partial files are retained at the reported path
if creation fails. Local image IRIs in N-Triples require conversion to Turtle first
because N-Triples does not permit relative IRIs.

With copying disabled, sources remain externally linked using absolute paths.
Identical filenames receive distinct ontology IDs. The generated YAML works with
the existing CLI. Generated Markdown and HTML assignments inside the project also
use relative paths. To transfer a project, copy its complete folder (including
`sources/`, `build/` and `.outputs.json`) and open its YAML on the other computer.
Externally assigned files/output folders are not made portable automatically.
Online image URLs, remote imports and external script dependencies remain online;
this is source portability, not a fully offline bundle of all web resources.
### Change ontology membership

Under **Projekteinstellungen > Ontologien im Projekt**, use **Ontologien
hinzufügen** to select multiple files through the native chooser. The default
**Ontologien und lokale Bilder ins Projekt kopieren** option copies files into
`sources/<ontology-id>/` with relative references, just as during project creation.
Disable it to link the selected files in place. Identical selected paths and
already assigned input paths are ignored; distinct files with the same name get
unique IDs. Re-selecting an original external file after copying it can create a
new independent copy, since the assigned input is now the project-local file.

The unlink icon removes an ontology after confirmation. It changes the YAML list,
but never deletes its sources, images, Markdown or generated outputs. Removed
individual HTML assignments are no longer served. IDs with retained outputs or
source folders are not reused, preventing accidental attachment of older outputs.
The last generated portal remains an immutable snapshot; generate it again to
reflect the new membership. Its selection excludes removed entries.

All ontologies can be removed. An empty existing project can be reopened and
populated again; generating a portal requires at least one selection. CLI builds
of empty projects report an error. New-project creation still requires an input.
Changes use revision checks. On copy failure the YAML is unchanged, but partial
copies remain under `sources/` for inspection. Source files are never deleted.
The endpoints are `POST /api/ontologies` (`revision`, `paths`, `copy_sources`)
and `POST /api/ontologies/{id}/remove` (`revision`).

The preview header shows its linked filename. Expand it to view/select the complete
path; the redundant path footer has been removed.

## Start development

From the repository root:

```console
uv sync --extra web
uv run --extra web uvicorn ontolens.web:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal:

```console
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite forwards `/api` requests to the local Python
server on port 8000. OpenAPI documentation is available at
http://127.0.0.1:8000/docs. No CORS wildcard or public network binding is needed.
If a port is occupied, select a different port and adjust `vite.config.ts`'s
proxy target to match the backend.

The backend defaults to `ontolens.project.yaml` in its working directory.
On a fresh checkout, copy `ontolens.example.yaml` to this name in the repository
root and point it at your own inputs unless the local demo files are present.
The working copy is ignored by Git; do
not overwrite an existing project.
Set `ONTOLENS_PROJECT` to select another configuration before starting it.
Project paths are resolved relative to that configuration as in the CLI.

```powershell
$env:ONTOLENS_PROJECT = 'D:\path\project.yaml'
```

## Build frontend

```console
cd frontend
npm run build
```

This runs TypeScript checks and writes static frontend assets to `frontend/dist`.
Docker serves these assets through FastAPI on the same port; see the Docker guide.
The existing CLI still works independently without the `web` extra,
Node.js, a browser or a running API server.

## Structure

- `frontend/src/api.ts`: typed API client.
- `frontend/src/main.tsx`: React application shell and read-only project views.
- `frontend/src/style.css`: responsive dark/light styles.
- `src/ontolens/web.py`: FastAPI factory using the existing project loader.
- `docs/design/gui-preview.html`: separate interactive design prototype.

API endpoints expose health, project data, settings and path updates, native file
pickers, Markdown templates, and exports by ontology ID. Export file serving is
restricted to the registered export directory. Write requests require the
`X-Ontolens-Write: 1` header; configuration-dependent exports also require the
current project revision. Raw HTML inside Markdown is not executed by the reader.

`POST /api/project/archive` accepts `revision` and optional `include_outputs`
(default false). It returns a validated ZIP with portable relative project paths.
The temporary server package is deleted after transmission. The response header
`X-Ontolens-Notices` contains a bounded JSON list of export notices; the full list
is in the archive's `EXPORT-INFO.txt`. The GUI exposes this under project settings,
and the standalone CLI equivalent is `ontolens pack`; see [Project ZIP](project-export.md).

Project settings also expose `POST /api/project/pdf` for printing linked HTML
snapshots. Local PDF support requires `uv sync --extra web --extra pdf` and
`uv run --extra web --extra pdf python -m playwright install --only-shell chromium`.
Keep both extras when starting the API with uv. Docker includes the renderer.
See [PDF export](pdf-export.md) for options, resource restrictions and CLI usage.
