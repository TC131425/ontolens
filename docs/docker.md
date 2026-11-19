# Run OntoLens with Docker

One container serves the web app and API. It also contains the CLI and Chromium
for PDF export. Use it on a **trusted, single-user machine**: there is no login,
and the file picker can write to the folders you share. Compose binds the app
to `127.0.0.1`; do not expose it through a public proxy.

## Choose storage

From the repository root, use [.env.example](../.env.example) as a template for
`.env`. Do not overwrite an existing configuration. Set the host folder **before**
starting Compose:

```dotenv
ONTOLENS_HOST_DIR=D:/Ontologies
ONTOLENS_DATA_DIR=./docker-data
ONTOLENS_PORT=8080
```

| Setting | What it controls |
| --- | --- |
| `ONTOLENS_HOST_DIR` | An **existing**, writable host folder shown as **Local drive** (`/data/host-drive`). Use an absolute path. Prefer one project parent folder over sharing an entire drive. |
| `ONTOLENS_DATA_DIR` | Persistent app data at `/data`, including the startup project and project registry. Defaults to `./docker-data`. |
| `ONTOLENS_PORT` | Port on localhost. Defaults to `8080`. |

On Windows, use forward slashes in `.env`. Without a host setting, Compose mounts
`C:/`; the example environment file specifies `D:/`. An explicitly configured
missing drive **does not** fall back to C:. Choose an existing path. On Linux
or macOS set an existing native path, e.g. `/home/me/ontologies` or
`/Users/me/ontologies`. Changing a mount does not move existing files.

## Start and stop

You need a running Docker engine, Compose v2 and internet for the first build.
Use Linux containers on Docker Desktop for Windows.

```sh
docker compose up --build -d
docker compose ps
```

Open [the web app](http://localhost:8080) (adjust the port if configured).
A fresh data directory gets an empty **Workspace** project. Follow the
[workspace guide](workspace.md) to add your own project. Existing projects are
not overwritten.

| Operation | Command |
| --- | --- |
| Start again, or apply changes to `.env` | `docker compose up -d` |
| Rebuild after updating OntoLens | `docker compose up --build -d` |
| Follow recent logs | `docker compose logs --tail=100 -f ontolens` |
| Stop the app | `docker compose stop` |
| Remove the container and network | `docker compose down` |

Both `stop` and `down` leave the bound host folders and their contents in place.

## Find files or move a project

The Docker picker opens at **Local drive**. It browses mounted folders, not
every drive on your computer, and does not upload files through the browser.
Paste a path inside the mount or browse to a folder. You can filter the current
folder by name, revisit recent folders, create a subfolder or select several
ontology files. In the example above, `D:/Ontologies/library` corresponds to
`/data/host-drive/library`. An alternative is to put sources and their figures
under `docker-data/` and browse there via **Saved projects**.

To reopen an existing project, copy or mount its **whole folder**, including
YAML, Markdown, source ontologies, figures, builds and `*.outputs.json`. Choose
**Open project** and select the YAML. Project-relative paths travel with the
folder; Windows absolute paths stored in YAML do not resolve in a Linux
container. Relink them, use relative paths, or transfer the project as a
[portable ZIP](project-export.md). Never mount the repository over `/app`.

For a backup, stop the app and back up **both** the data folder and any project
folders or linked files elsewhere on the host. Keep `*.projects.json` for the
registry and `*.outputs.json` for linked HTML and portals. Restore the folders to
the same mounts before restarting. Removing a project from the list does not
delete files.

## Run the CLI in Docker

Use container paths, not host paths. With `demo.ttl` in the shared host folder:

```sh
docker compose run --rm --no-deps ontolens ontolens --help
docker compose run --rm --no-deps ontolens ontolens /data/host-drive/demo.ttl --theme both --quality-report -o /data/cli-builds/library.html
```

The CLI does not register exports in the GUI. Link them manually if needed.
Avoid writing the same project concurrently from the CLI and GUI.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Docker cannot start the container | Start the engine; check `docker version`, the configured host path and Docker Desktop file sharing. |
| Port already in use | Change `ONTOLENS_PORT` in `.env` and run `docker compose up -d`. |
| File is missing in the picker | Check the mount, file extension and folder; the search filter is not recursive. |
| Permission denied when writing | The container runs as UID/GID 1000 by default. Grant access to the chosen folders; on Linux, a local Compose override can set `services.ontolens.user` to your UID:GID. |
| Generate button is disabled | Unlink the existing HTML or portal; for a combined build, also link and save Markdown. |
| Graph fails in an older HTML export | Regenerate it or restore the assets that accompanied the old file. New HTML embeds its graph libraries. |

The runtime uses a single worker, a read-only root filesystem and writable data
mounts and temporary storage. Do not share the Docker socket or run concurrent
workers against the same project registry. Build timestamps use container time
(normally UTC).

## Verify a deployment

`docker compose config --quiet` checks the configuration. When the app is running,
[the health endpoint](http://localhost:8080/api/health) checks availability. The
optional [workflow smoke test](../scripts/docker_smoke.py) creates **new projects**
under `/data/docker-smoke-<ID>` and leaves them registered for inspection.

```powershell
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python -
```

On Linux or macOS, use `docker compose exec -T ontolens python - < scripts/docker_smoke.py`.
To check persistence, restart the container and rerun the script with
`--verify /data/docker-smoke-<ID>/manifest.json`, using the path printed on the
first run. The same manifest can be used with `--archive` or `--pdf` to check
those exports without creating another project.
