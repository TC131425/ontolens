# Projects and static portals

The original single-file CLI remains available. Project builds use the same
generator, with YAML configuration and optional portal navigation.

```console
uv run ontolens build ontolens.example.yaml
uv run ontolens build ontolens.example.yaml --ontology isoprops
uv run ontolens build ontolens.example.yaml --ontology loin --ontology tempo --no-portal
uv run ontolens build ontolens.example.yaml --no-quality-report --recommendations
```

The supplied YAML refers to local inputs, not bundled datasets. Provide the
referenced files first or change the paths to your own. With the local demo
collection it builds LOIN, TempO and ISOProps. ISOProps includes the
maintained Markdown introduction. The others use standard ontology documentation.

## Configuration

```yaml
name: ontology-collection
output: build
defaults:
  language: de
  recommendations: false
  quality_report: true
  custom_annotations: false
  check_content: false
ontologies:
  - id: loin
    input: examples/loin/loin.ttl
  - id: tempo
    input: examples/tempo/tempo.ttl
    skip_missing_images: true
  - id: isoprops
    input: examples/isoprops/isoprops.ttl
    content: examples/isoprops/documentation.de.md
    check_content: true
portal:
  enabled: true
  title: LOIN, TempO & ISOProps
```

All YAML paths are relative to the configuration file, independent of the current
working directory. `name` defaults to the config filename stem, `output` to
`build`, and the portal is disabled unless requested. Ontology IDs must be unique
(case-insensitive) and contain letters, digits, underscores or hyphens, starting
with a letter or digit. Windows reserved filenames are rejected.

Existing projects may have `ontologies: []` while being
reorganized; loading is supported, but building requires at least one entry.

Settings resolve in this order: CLI overrides, ontology entry, project defaults,
generator defaults. Boolean options default to false. Supported settings are
`language`, `format` (RDFLib parser format), `recommendations`, `quality_report`,
`custom_annotations`, `check_content`, `skip_missing_images`, `show_missing_endpoints`,
`include_external_classes`, and `theme`.

`include_external_classes: true` adds all named external classes explicitly
declared in the input file to the graph, including isolated classes. It defaults
to false; external property endpoints remain visible in either case. Use
`--include-external-classes` or `--no-include-external-classes` to override the
configuration for a build. The HTML's **External references** filter independently
controls the visibility of external nodes included during generation.
`theme` accepts `light` (default), `dark`, or `both`. Use `--theme both` for a
project bundle containing complete `light/` and `dark/` portal variants. Each
variant has a fixed theme without a visitor toggle. The same applies when all
selected entries inherit/set `theme: both`. For a single-file export, `both`
places both HTML variants and their assets below the timestamped build folder.
`show_missing_endpoints` defaults to false. When true, object properties with
exactly one missing domain/range declaration get a visual placeholder for that
endpoint. Both absent stays hidden; datatype properties and quality checks are
unaffected. The setting also applies to documents generated in a portal build.
`language: null` and `format: null` explicitly restore automatic detection for an
entry even when project defaults specify a language or parser. Automatic HTML
language selection uses the Markdown language if present, otherwise English.

Use the equivalent CLI flags with hyphens. Each boolean supports both `--flag`
and `--no-flag`, allowing explicit overrides of configured true values.
`--portal` / `--no-portal` overrides portal generation. `--output DIRECTORY`
overrides the project output root relative to the working directory. Unlike the
legacy single-file command, this is a directory, not an HTML filename.

`check_content: true` requires a Markdown `content` file. Set it to false for
entries without Markdown. Missing/empty chapter notices are nonblocking.
Unknown configuration keys, invalid booleans, missing inputs and unknown selected
IDs are errors. Runtime failures stop the build; partial output may remain for
inspection. An index is only written after all selected documents succeed.

## Output and publication

```text
build/<timestamp>_ontology-collection/
  index.html
  loin/<timestamp>_loin/
    loin.html
    img/
    downloads/loin.ttl
  tempo/<timestamp>_tempo/...
  isoprops/<timestamp>_isoprops/...
```

Each run creates a new timestamped project bundle. If the same bundle name
already exists (for example two runs within one second), the build fails rather
than overwriting it. Use another output directory or retry later.

The portal contains only selected ontologies, with titles, descriptions, versions
where supplied, and class/property counts. Each documentation page links back
to the portal. Names and descriptions are escaped as text. Source ontology
downloads and local images are copied into the bundle. Copy the whole bundle to
publish it; no Python service or Docker container is required to serve it.
Graph scripts, including Cytoscape and its layout libraries, are embedded in the
HTML and work offline without an `assets/` folder. External image URLs and links
remain external, so this is not a complete offline archive. Cross-ontology term search and automatic mappings
are not included in this first portal version.

TempO references a missing `LibraryOverview.svg`. Its example configuration
explicitly enables `skip_missing_images`, which warns and omits missing ontology
figures. The default remains an error, and missing Markdown images still fail.
The single-file CLI also supports `--skip-missing-images`. Previously shared
example images are retained as-is; this does not certify their semantic accuracy.
