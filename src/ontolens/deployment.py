"""Headless runtime support for the local, single-user Docker deployment."""
import os
import re
from pathlib import Path, PureWindowsPath

from fastapi import HTTPException, Header
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles


def data_root() -> Path | None:
    value = os.environ.get('ONTOLENS_DATA_ROOT')
    return Path(value).resolve() if value else None


def selected_path(value: str) -> Path:
    root = data_root()
    value = value.strip().strip('"')
    native_data_path = os.name == 'nt' and root is not None and Path(value).is_absolute() and Path(value).is_relative_to(root)
    if not native_data_path and (re.match(r'^[a-zA-Z]:', value) or value.startswith('\\\\')):
        source = PureWindowsPath(os.environ.get('ONTOLENS_HOST_SOURCE', ''))
        requested = PureWindowsPath(value)
        host = os.environ.get('ONTOLENS_HOST_DIRECTORY')
        if not host or not requested.is_absolute() or not source.is_absolute():
            raise HTTPException(403, 'Dieses Windows-Laufwerk ist nicht eingebunden.')
        try:
            relative = requested.relative_to(source)
        except ValueError as error:
            raise HTTPException(403, 'Der Windows-Pfad liegt ausserhalb des eingebundenen Laufwerks oder Ordners.') from error
        if '..' in relative.parts:
            raise HTTPException(403, 'Bitte einen absoluten Pfad ohne .. verwenden.')
        value = str(Path(host).joinpath(*relative.parts))
    path = Path(value).resolve()
    if root is None or not path.is_relative_to(root):
        raise HTTPException(403, 'Bitte einen Pfad im eingebundenen Datenordner auswählen.')
    return path


def display_path(path: Path) -> str:
    host = os.environ.get('ONTOLENS_HOST_DIRECTORY')
    source = os.environ.get('ONTOLENS_HOST_SOURCE', '')
    if host and PureWindowsPath(source).is_absolute() and path.is_relative_to(Path(host).resolve()):
        return str(PureWindowsPath(source).joinpath(*path.relative_to(Path(host).resolve()).parts))
    return str(path)


class NewDirectory(BaseModel):
    parent: str
    name: str = Field(min_length=1, max_length=120)


def configure_runtime(app):
    @app.get('/api/runtime')
    def runtime():
        root = data_root()
        host = os.environ.get('ONTOLENS_HOST_DIRECTORY')
        return {'file_browser': root is not None, 'root': str(root) if root else None,
                'host_directory': str(Path(host)) if host and root and Path(host).resolve().is_relative_to(root) and Path(host).is_dir() else None,
                'host_source': os.environ.get('ONTOLENS_HOST_SOURCE', '')}

    @app.get('/api/files')
    def list_files(path: str | None = None):
        root = data_root()
        if root is None:
            raise HTTPException(404, 'Dateibrowser ist nicht aktiviert.')
        directory = selected_path(path or str(root))
        if not directory.is_dir():
            raise HTTPException(422, 'Ordner nicht gefunden.')
        try:
            entries = []
            for child in directory.iterdir():
                try:
                    if child.name.startswith('.') or not child.resolve().is_relative_to(root):
                        continue
                    if child.is_dir() or child.is_file():
                        entries.append({'name': child.name, 'path': str(child), 'directory': child.is_dir()})
                except OSError:
                    continue
            entries.sort(key=lambda item: (not item['directory'], item['name'].casefold()))
            return {'path': str(directory), 'display_path': display_path(directory),
                    'parent': str(directory.parent) if directory != root else None, 'entries': entries}
        except OSError as error:
            raise HTTPException(422, f'Ordner konnte nicht gelesen werden: {error}') from error

    @app.post('/api/files/directory')
    def new_directory(request: NewDirectory, x_ontolens_write: str | None = Header(default=None)):
        if x_ontolens_write != '1':
            raise HTTPException(403, 'Missing write header')
        name = request.name
        if (name in {'.', '..'} or name.endswith((' ', '.')) or name != name.strip()
                or re.search(r'[\\/:*?"<>|\x00-\x1f]', name)
                or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
            raise HTTPException(422, 'Bitte einen gueltigen Ordnernamen ohne Pfad oder Sonderzeichen angeben.')
        parent = selected_path(request.parent)
        if not parent.is_dir():
            raise HTTPException(422, 'Der uebergeordnete Ordner existiert nicht.')
        target = selected_path(str(parent / name))
        try:
            target.mkdir(exist_ok=False)
        except FileExistsError as error:
            raise HTTPException(409, 'Ein Ordner oder eine Datei mit diesem Namen existiert bereits.') from error
        except OSError as error:
            raise HTTPException(422, f'Ordner konnte nicht angelegt werden: {error}') from error
        return {'path': str(target), 'display_path': display_path(target)}

    static = os.environ.get('ONTOLENS_STATIC_DIR')
    if static:
        app.mount('/', StaticFiles(directory=static, html=True), name='frontend')


def create_container_app():
    root = data_root()
    if root is None:
        raise RuntimeError('ONTOLENS_DATA_ROOT must be set for container startup')
    root.mkdir(parents=True, exist_ok=True)
    config = root / 'ontolens.project.yaml'
    if not config.exists():
        # Bootstrap once; never replace an existing configuration or registry.
        with config.open('x', encoding='utf-8') as stream:
            stream.write('name: Workspace\noutput: build\nontologies: []\n')
    from .web import create_app
    return create_app(config)
