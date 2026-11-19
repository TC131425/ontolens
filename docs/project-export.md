# Share a project as a ZIP

Use a project ZIP when the recipient needs to **edit or rebuild** the documentation.
To share only a finished site, distribute the generated HTML or portal bundle.
To send a printable copy, use [PDF export](pdf-export.md).

## Package and reopen the project

1. In **Project settings > Share project**, select **Include generated documentation
   and portals** if the recipient also needs the currently linked outputs (off by default).
2. Select **Export project as ZIP**, review the notices, then **Download project ZIP**.
   This snapshots the saved files without modifying the project or creating a build in it.
3. On the receiving computer, extract the ZIP and choose **Open project**.
   Select `project/ontolens.project.yaml`. For Docker, extract inside a mounted folder.

Alternatively, rebuild the extracted project from the CLI:

```sh
uv run ontolens build project/ontolens.project.yaml
```

## Package from the CLI

```sh
uv run ontolens pack my-project.yaml -o build/my-project.zip
uv run ontolens pack my-project.yaml -o build/my-project.zip --include-outputs
```

The CLI writes `build/<timestamp>_my-project/my-project.zip`. The outputs option
reads the GUI's saved `.outputs.json` links; it does **not** scan the build history.
In Docker, use e.g. `docker compose exec ontolens ontolens pack /data/project/ontolens.project.yaml -o /data/exports/project.zip`.

## What travels with the ZIP

| Inside `project/` | Contents |
| --- | --- |
| `ontolens.project.yaml` | Settings, ontology IDs and portal configuration, with portable paths and `build` as the output folder. |
| `sources/<id>/` | Each source ontology and its local images, even for externally linked sources. Rewriting local image paths may reformat the **copy** of the RDF, not the original. |
| `content/<id>/` | Linked Markdown and its local images, with adjusted relative references. |
| `EXPORT-INFO.txt` | Notices about external dependencies and what was packaged. |
| `build/export-*/` and `ontolens.project.outputs.json` | Optional linked documents and portals, both theme variants where available, plus their referenced local resources. Unlinked builds and unrelated neighboring files are excluded. |

The archive does not contain a global project list, personal app preferences or
a complete offline copy of the web. Online images, external links and
`owl:imports` remain external. Ordinary Markdown links to local documents are
reported but not bundled as images.

## If packaging fails

Missing sources, linked Markdown or local images block export, even if HTML
generation is configured to skip missing figures. Correct the paths rather than
passing on an incomplete project. Unsupported image syntax is reported. When
including generated outputs, missing dependencies, absolute file references and
references escaping an output folder can also block export. Regenerate the affected
document or exclude generated outputs. Packaging does not upgrade old HTML to use
the newer embedded graph scripts.
