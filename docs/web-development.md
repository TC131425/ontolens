# Develop the local web app

For using the app, see the [workspace guide](workspace.md). For deployment with
the frontend already built, see [Docker](docker.md). The instructions here run
the API and frontend separately so that you can change the code.

## Start development

You need Python 3.10 or newer, uv, Node.js and npm (the Docker build uses Node 22).
In the repository root, create `ontolens.project.yaml` **if you do not already
have one**. An empty workspace is sufficient for GUI development:

```yaml
name: Workspace
output: build
ontologies: []
```

Alternatively, set `ONTOLENS_PROJECT` to the path of an existing [project YAML](projects.md).
Paths in it resolve relative to that YAML. Start the API from the repository root:

```sh
uv sync --extra web
uv run --extra web uvicorn ontolens.web:create_app --factory --host 127.0.0.1 --port 8000
```

For PDF work, install Chromium and start the API with **both** extras as described
in [PDF export](pdf-export.md#print-from-the-cli). In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [the development app](http://127.0.0.1:5173) or
[the interactive API docs](http://127.0.0.1:8000/docs). Vite proxies `/api` and
`/workspaces` to the API. If you change the API port, update the target in
[the Vite config](../frontend/vite.config.ts). Native file dialogs run on the
backend machine and require a desktop with Tk; Docker uses the mounted-folder picker.

## Build and test

From `frontend/` run `npm run build` for TypeScript checks and a production bundle
in `frontend/dist/`. From the repository root run:

```sh
uv run --extra web pytest -q
```

The base CLI does not require Node.js or a running API. See the
[workflow audit](workflow-audit.md) for CLI/GUI coverage and
[Docker verification](docker.md#verify-a-deployment) for the end-to-end smoke test.

## Code and local state

| Location | Purpose |
| --- | --- |
| [src/ontolens/](../src/ontolens/) | Python CLI, RDF parsing, rendering and project management. |
| [web.py](../src/ontolens/web.py) | FastAPI app factory and per-project routes. |
| [frontend/src/](../frontend/src/) | React workspace, typed API client and interface translations. |
| [tests/](../tests/) | Generator, CLI, API and deployment checks. |
| [ontolens.example.yaml](../ontolens.example.yaml) | Versioned configuration example; replace its example paths with your inputs. |
| `ontolens.project.yaml`, `*.outputs.json`, `*.projects.json` | Local startup project, HTML assignments and registry; not versioned. |
| `examples/`, `build/`, `docker-data/` | Private example inputs, generated artifacts and persistent Docker data; not required in a checkout. |

Keep real project inputs and maintained Markdown outside build folders. Do not
commit local configuration, examples, generated data or `.env`. The dependency
lockfiles, [.env.example](../.env.example) and bundled graph libraries and their
licenses are versioned.

## API conventions

The default project uses `/api`; additional projects have isolated
`/workspaces/<id>/api` routes. Writes require `X-Ontolens-Write: 1`.
Project-dependent changes and exports check the current revision; saving Markdown
also checks the file hash. Reload before retrying a conflict. HTML previews are
sandboxed; the server serves registered outputs and their referenced local resources.

The portal and individual exports share a generation lock. CLI builds do not
change GUI assignments. Project archives and PDFs are generated on demand; their
temporary server files are removed after download. See [project ZIP export](project-export.md)
and [PDF export](pdf-export.md) for the formats and options.
