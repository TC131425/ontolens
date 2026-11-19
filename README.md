# OntoLens

Turn an RDF/OWL ontology into a searchable HTML reference with an interactive graph.
Readers can look up a class in any of its label languages, inspect its properties and restrictions,
and download the source ontology. Share the generated folder or publish it on a static host;
readers do not need OntoLens. The graph and search work offline.

Use the local web app to edit Markdown chapters, preview documents and manage projects.
Use the CLI to build a single page or a collection from a YAML configuration.
Both use the same documentation generator. Supported inputs are Turtle, RDF/XML, N-Triples and JSON-LD.

## Quick start

Choose **one** of the following routes. Run the commands from the repository root.

### Use the web app with Docker

1. Install Docker with Compose v2 and start the engine. No local Python or Node.js installation is needed.
2. In `.env` beside `compose.yaml`, set `ONTOLENS_HOST_DIR` to an **existing folder** containing your ontologies.
   For example: `ONTOLENS_HOST_DIR=D:/Ontologies` on Windows or `ONTOLENS_HOST_DIR=/home/me/ontologies` on Linux.
   The app has write access to this folder and no sign-in; keep it on localhost. See the [Docker guide](docs/docker.md) for other settings.
3. Start the app:

   ```sh
   docker compose up --build -d
   ```

4. Open [OntoLens on localhost](http://localhost:8080). Select **New project**, choose a name and location, and use **Add files** to select an ontology from **Local drive**. Select **Create project**.
5. Under **Ontologies**, select the ontology, open **HTML documentation** and select **Generate HTML documentation**. The result appears in the preview and stays linked when you reopen the project.

The interface is available in English and German. The language selector changes the app, not your ontology labels, Markdown or exported documents.

### Generate HTML from the command line

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10 or later. Use your own ontology, or create a file named `demo.ttl` in the repository root with this content:

```turtle
@prefix ex:   <https://example.org/library#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/library> a owl:Ontology ; rdfs:label "Library"@en .
ex:Book a owl:Class ; rdfs:label "Book"@en .
ex:Author a owl:Class ; rdfs:label "Author"@en .
ex:writtenBy a owl:ObjectProperty ; rdfs:domain ex:Book ; rdfs:range ex:Author .
```

```sh
uv sync
uv run ontolens demo.ttl -o build/library.html
```

Open the path printed by the command: `build/<timestamp>_library/library.html`.
Under **Visualization**, the graph connects Book to Author; both classes also have reference entries.
When sharing the HTML, keep the adjacent `img/` and `downloads/` folders with it.

## Where to go next

| I want to… | Guide |
| --- | --- |
| Look up a term, explore its neighbors or check for missing metadata | [HTML reference, graph and quality options](docs/html-reference.md) |
| Add narrative chapters, diagrams and examples to the reference | [Write a combined page with Markdown](docs/markdown-content.md) |
| Build several ontologies together and publish a portal | [Configure a project and build a portal](docs/projects.md) |
| Preview exports, link existing documents or manage project members | [Use the web workspace](docs/workspace.md) |
| Explore instances rather than class definitions | [Generate an A-Box viewer](docs/html-reference.md#explore-instances-instead) |
| Share an editable project, including its sources and images | [Export a portable project ZIP](docs/project-export.md) |
| Print a document with figures or a landscape graph | [Export documentation as PDF](docs/pdf-export.md) |
| Change Docker storage, restore a backup or troubleshoot startup | [Run OntoLens with Docker](docs/docker.md) |

For command syntax and options, run `uv run ontolens --help` or request help for a subcommand, such as `uv run ontolens build --help`.

## Development

The CLI is Python; the optional local web app uses FastAPI and React.
See the [development guide](docs/web-development.md) to start both services, build the frontend and run tests.
[ontolens.example.yaml](ontolens.example.yaml) illustrates a multi-ontology configuration; its datasets are not shipped.

OntoLens takes inspiration from pyLODE and WIDOCO.
