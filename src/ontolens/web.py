"""Local project API; CLI and API share the project loader."""
from __future__ import annotations

import os
import hashlib
import io
import tempfile
import subprocess
import sys
import json
import shutil
import re
from uuid import uuid4
from datetime import datetime
from typing import Literal
from threading import Lock
from collections import OrderedDict
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, ConfigDict, StrictBool, Field
from ruamel.yaml import YAML
from yaml import YAMLError
from rdflib.exceptions import ParserError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .project import load_project
from .parser import load_ontology
from .render import _is_external
from .scaffold import create_content
from .render import generate


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    quality_report: StrictBool
    recommendations: StrictBool
    custom_annotations: StrictBool
    check_content: StrictBool
    theme: Literal["light", "dark", "both"] | None = None
    skip_missing_images: StrictBool | None = None
    show_missing_endpoints: StrictBool | None = None
    include_external_classes: StrictBool | None = None
    language: str | None = Field(default=None, min_length=1, max_length=35, pattern=r"^[a-zA-Z]+(?:-[a-zA-Z0-9]+)*$")
    format: str | None = Field(default=None, min_length=1)


class PathUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    kind: Literal["input", "content", "output"]
    path: str


class TemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    profile: Literal["compact", "standard"] = "standard"


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    kind: Literal["reference", "combined", "markdown"]


class MarkdownUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    content_revision: str
    content: str


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str


class ProjectArchiveRequest(RevisionRequest):
    include_outputs: StrictBool = False


class PdfDocumentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ontology: str
    kind: Literal['reference', 'combined']


class PdfExportRequest(RevisionRequest):
    documents: list[PdfDocumentRequest] = Field(min_length=1, max_length=20)
    paper: Literal['A4', 'A3'] = 'A4'
    figures: StrictBool = True
    graph: StrictBool = False


class MarkdownCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    content: str


class HtmlAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    path: str | None = None


class NewProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    directory: str
    ontologies: list[str]
    copy_sources: StrictBool = False


class OpenProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str | None = None


class PortalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    title: str = Field(min_length=1, max_length=200)
    ontologies: list[str] = Field(min_length=1)
    theme: Literal["light", "dark", "both"] = "light"


class AddOntologiesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str
    paths: list[str] = Field(min_length=1)
    copy_sources: StrictBool = True


def choose_local_path(kind: str, initial: Path) -> str | list[str] | None:
    if os.environ.get('ONTOLENS_DATA_ROOT'):
        raise HTTPException(409, 'Bitte den Dateibrowser der Weboberfläche verwenden.')
    # A separate process gives the native dialog its own GUI main thread.
    script = '''import tkinter as tk
from tkinter import filedialog
import sys, json
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
kind, initial = sys.argv[1:]
if kind == 'ontologies':
    result = list(filedialog.askopenfilenames(parent=root, initialdir=initial, title='Ontologien hinzufügen', filetypes=[('Ontologie', '*.ttl *.rdf *.owl *.nt *.jsonld *.json-ld')]))
elif kind == 'output':
    result = filedialog.askdirectory(parent=root, initialdir=initial, title='Ausgabeordner auswählen')
else:
    types = [('Projekt', '*.yaml *.yml')] if kind == 'project' else [('HTML', '*.html *.htm')] if kind == 'html' else [('Markdown', '*.md *.markdown')] if kind == 'content' else [('Ontologie', '*.ttl *.rdf *.owl *.nt *.jsonld *.json-ld')]
    result = filedialog.askopenfilename(parent=root, initialdir=initial, title='Datei auswählen', filetypes=types)
root.destroy()
print(json.dumps(result))
'''
    try:
        result = subprocess.run([sys.executable, "-c", script, kind, str(initial)], capture_output=True, text=True, timeout=300, check=True)
        return json.loads(result.stdout) or None
    except (subprocess.SubprocessError, ValueError, OSError) as error:
        raise HTTPException(503, "Lokaler Dateidialog nicht verfügbar oder abgelaufen. Benötigt einen Desktop auf dem Backend-Rechner.") from error


def create_project_app(config_path: Path | None = None, url_prefix: str = '') -> FastAPI:
    config = (config_path or Path(os.environ.get("ONTOLENS_PROJECT", "ontolens.project.yaml"))).resolve()
    app = FastAPI(title="OntoLens Local API", version="0.1.0")
    write_lock = Lock()
    dialog_lock = Lock()
    export_lock = Lock()
    exports = {}
    image_previews = OrderedDict()
    image_lock = Lock()
    assignments_path = config.with_suffix('.outputs.json')

    def stored_path(path):
        path = Path(path).resolve()
        return path.relative_to(config.parent).as_posix() if path.is_relative_to(config.parent) else str(path)

    def assignments():
        if not assignments_path.exists():
            return {}
        try:
            return json.loads(assignments_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise HTTPException(422, 'HTML-Zuordnungen konnten nicht gelesen werden.') from error

    def store_assignment(ontology_id, kind, record):
        data = assignments()
        data.setdefault(ontology_id, {})[kind] = record
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=config.parent, suffix='.json', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
            os.replace(temporary, assignments_path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def linked_result(ontology_id, kind, record):
        if not record or not record.get('path'):
            return None
        page = (config.parent / record['path']).resolve()
        token = hashlib.sha256(f'{ontology_id}:{kind}:{page}'.encode()).hexdigest()
        archive = (config.parent / record['archive']).resolve() if record.get('archive') else page
        root = (config.parent / record['root']).resolve() if record.get('root') else page.parent
        variants = {name: (config.parent / path).resolve() for name, path in record.get('variants', {}).items()}
        exports[token] = {'root': root, 'page': page, 'pages': list(variants.values()) or [page], 'download': archive if archive.is_file() else page}
        return {'kind': kind, 'path': str(page), 'preview': f'{url_prefix}/api/exports/{token}/files/{quote(page.relative_to(root).as_posix())}',
                'variants': {name: {'path': str(path), 'preview': f'{url_prefix}/api/exports/{token}/files/{quote(path.relative_to(root).as_posix())}'} for name, path in variants.items()},
                'download': f'{url_prefix}/api/exports/{token}/download', 'notices': record.get('notices', []),
                'report_available': record.get('report_available', bool(record.get('archive') or record.get('notices'))),
                'available': page.is_file(), 'downloadLabel': 'ZIP herunterladen' if archive.is_file() and archive.suffix == '.zip' else 'HTML herunterladen'}

    def export_record(token):
        # Rebuild the registry from persistent assignments after a process restart.
        exports.clear()
        active_ids = {item.id for item in project().ontologies} | {'$portal'}
        for identity, kinds in assignments().items():
            if identity not in active_ids:
                continue
            for kind, record in kinds.items():
                linked_result(identity, kind, record)
        return exports.get(token)

    def linked_files(page, root=None):
        """Only expose the page and its local dependencies, never its whole folder."""
        from bs4 import BeautifulSoup
        root = (root or page.parent).resolve()
        allowed = {page.resolve()}
        pending = [page.resolve()]
        while pending:
            source = pending.pop()
            if not source.is_file() or source.suffix.lower() not in {'.html', '.htm', '.css', '.svg'}:
                continue
            text = source.read_text(encoding='utf-8', errors='replace')
            refs = re.findall(r'url\(\s*[\x22\x27]?([^\)\x22\x27]+)', text)
            if source.suffix.lower() == '.svg':
                from xml.etree import ElementTree
                try:
                    svg = ElementTree.fromstring(text)
                except ElementTree.ParseError:
                    continue
                refs.extend(value for node in svg.iter() for key, value in node.attrib.items()
                            if key.rsplit('}', 1)[-1] == 'href')
            elif source.suffix.lower() != '.css':
                soup = BeautifulSoup(text, 'html.parser')
                refs.extend(str(tag[attr]) for tag in soup.find_all(True) for attr in ('src', 'href', 'xlink:href', 'poster') if tag.has_attr(attr))
            for ref in refs:
                url = urlsplit(ref.strip())
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (source.parent / unquote(url.path)).resolve()
                if target.is_relative_to(root) and target not in allowed:
                    allowed.add(target)
                    pending.append(target)
        return allowed
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    def project():
        try:
            return load_project(config, require_sources=False)
        except Exception as error:
            raise HTTPException(status_code=422, detail=f"Cannot load project: {error}") from error

    def require_write(header):
        if header != "1":
            raise HTTPException(403, "Missing write header")

    def describe_images(ontology_id, source):
        from .markdown_images import inspect_images
        images = []
        for image in inspect_images(source):
            preview = None
            if not image.error:
                if image.path is None:
                    preview = image.src
                else:
                    token = uuid4().hex
                    with image_lock:
                        image_previews[token] = (ontology_id, source.path.resolve(), image.path)
                        while len(image_previews) > 1024:
                            image_previews.popitem(last=False)
                    preview = f'{url_prefix}/api/ontologies/{quote(ontology_id, safe="")}/markdown/images/{token}'
                    if urlsplit(image.src).fragment:
                        preview += '#' + urlsplit(image.src).fragment
            images.append({'src': image.src, 'alt': image.alt, 'preview': preview, 'error': image.error})
        return images

    def editable(ontology_id, revision):
        raw = config.read_bytes()
        if hashlib.sha256(raw).hexdigest() != revision:
            raise HTTPException(409, "Projekt wurde zwischenzeitlich geändert. Bitte neu laden.")
        yaml = YAML()
        yaml.preserve_quotes = True
        document = yaml.load(raw.decode("utf-8-sig"))
        entry = next((o for o in document["ontologies"] if o["id"] == ontology_id), None)
        if ontology_id is not None and entry is None:
            raise HTTPException(404, "Unknown ontology")
        return raw, yaml, document, entry

    def commit(raw, yaml, document):
        buffer = io.StringIO()
        yaml.dump(document, buffer)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=config.parent, suffix=".yaml", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(buffer.getvalue().encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            load_project(temporary, require_sources=False)
            if config.read_bytes() != raw:
                raise HTTPException(409, "Projekt wurde zwischenzeitlich geändert. Bitte neu laden.")
            os.replace(temporary, config)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    @app.post('/api/project/archive')
    def archive_project(request: ProjectArchiveRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, 'Eine Generierung läuft bereits.')
        temporary = None
        try:
            from .project_archive import create_project_archive
            with write_lock:
                editable(None, request.revision)
                temporary = Path(tempfile.mkdtemp(prefix='ontolens-project-'))
                archive, notices = create_project_archive(config, temporary,
                    include_outputs=request.include_outputs, assignments=assignments() if request.include_outputs else {})
                editable(None, request.revision)
                slug = re.sub(r'[^a-z0-9_-]+', '-', project().name.lower()).strip('-_') or 'project'
                response = FileResponse(archive, media_type='application/zip',
                    filename=f'{slug}-project.zip',
                    headers={'X-Ontolens-Notices': json.dumps([notice[:300] for notice in notices[:10]] + (['Alle Hinweise stehen in EXPORT-INFO.txt.'] if notices else []), ensure_ascii=True)},
                    background=BackgroundTask(shutil.rmtree, temporary))
                temporary = None
                return response
        except (OSError, ValueError, KeyError, SyntaxError, ParserError) as error:
            raise HTTPException(422, f'Projektpaket konnte nicht erstellt werden: {error}') from error
        finally:
            if temporary is not None:
                shutil.rmtree(temporary)
            export_lock.release()

    @app.post('/api/project/pdf')
    def export_project_pdf(request: PdfExportRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, 'Eine Generierung läuft bereits.')
        temporary = None
        try:
            from .pdf_export import PdfOptions, render_pdf
            with write_lock:
                editable(None, request.revision)
                loaded = project()
                ids = {item.id for item in loaded.ontologies}
                linked = assignments()
                selected = list(dict.fromkeys((item.ontology, item.kind) for item in request.documents))
                sources = []
                for identity, kind in selected:
                    if identity not in ids:
                        raise HTTPException(404, 'Ontologie nicht gefunden.')
                    record = linked.get(identity, {}).get(kind)
                    if not record or not record.get('path'):
                        raise HTTPException(422, f'{identity}: Zuerst eine HTML-Dokumentation generieren oder zuordnen.')
                    source = (config.parent / record.get('variants', {}).get('light', record['path'])).resolve()
                    root = (config.parent / record['root']).resolve() if record.get('root') else source.parent
                    if not source.is_file():
                        raise HTTPException(422, f'{identity}: Verknüpfte HTML-Datei fehlt.')
                    sources.append((identity, kind, source, root))
                temporary = Path(tempfile.mkdtemp(prefix='ontolens-pdf-'))
                folder = temporary / 'documents'
                options = PdfOptions(paper=request.paper, figures=request.figures, graph=request.graph)
                notices = []
                for identity, kind, source, root in sources:
                    target = folder / f'{identity}-{kind}.pdf'
                    notices.extend(f'{identity}: {notice}' for notice in render_pdf(source, target, options, root=root))
                editable(None, request.revision)
                if len(sources) == 1:
                    result = target
                    media_type = 'application/pdf'
                else:
                    slug = re.sub(r'[^a-z0-9_-]+', '-', loaded.name.lower()).strip('-_') or 'project'
                    result = Path(shutil.make_archive(str(temporary / f'{slug}-pdf'), 'zip', folder))
                    media_type = 'application/zip'
                response = FileResponse(result, media_type=media_type, filename=result.name,
                    headers={'X-Ontolens-Filename': result.name, 'X-Ontolens-Notices': json.dumps([notice[:300] for notice in notices[:10]], ensure_ascii=True)},
                    background=BackgroundTask(shutil.rmtree, temporary))
                temporary = None
                return response
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        except (OSError, ValueError, KeyError, SyntaxError) as error:
            raise HTTPException(422, f'PDF-Export fehlgeschlagen: {error}') from error
        finally:
            if temporary is not None:
                shutil.rmtree(temporary)
            export_lock.release()

    @app.post("/api/dialog/{kind}")
    def choose_path(kind: Literal["input", "content", "output", "html", "ontologies"], x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not dialog_lock.acquire(blocking=False):
            raise HTTPException(409, "Ein Dateidialog ist bereits geöffnet.")
        try:
            return {"path": choose_local_path(kind, config.parent)}
        finally:
            dialog_lock.release()

    @app.post('/api/ontologies')
    def add_ontologies(request: AddOntologiesRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            raw, yaml, document, _ = editable(None, request.revision)
            loaded = project()
            seen = {item.input for item in loaded.ontologies}
            sources = []
            for value in request.paths:
                source = Path(value)
                if not source.is_absolute() or not source.is_file():
                    raise HTTPException(422, f'Ontologiedatei nicht gefunden: {value}')
                source = source.resolve()
                if source in seen:
                    continue
                try:
                    load_ontology(source)
                except Exception as error:
                    raise HTTPException(422, f'Ontologie kann nicht gelesen werden: {source.name}: {error}') from error
                seen.add(source)
                sources.append(source)
            ids = {item.id.casefold() for item in loaded.ontologies} | {key.casefold() for key in assignments()}
            try:
                for source in sources:
                    stem = re.sub(r'[^a-z0-9_-]+', '-', source.stem.lower()).strip('-_') or 'ontology'
                    identity = f'ontology-{stem}'
                    suffix = 2
                    while identity.casefold() in ids or (config.parent / 'sources' / identity).exists():
                        identity = f'ontology-{stem}-{suffix}'
                        suffix += 1
                    ids.add(identity.casefold())
                    target = source
                    if request.copy_sources:
                        from .source_bundle import copy_ontology
                        target = copy_ontology(source, config.parent / 'sources' / identity)
                    entry = {'id': identity, 'input': stored_path(target)}
                    # A new entry has no editorial source, even if defaults enable checks.
                    if document.get('defaults', {}).get('check_content'):
                        entry['check_content'] = False
                    document['ontologies'].append(entry)
                if sources:
                    commit(raw, yaml, document)
            except (OSError, ValueError, SyntaxError, ParserError) as error:
                raise HTTPException(422, f'Hinzufügen fehlgeschlagen: {error}. Bereits kopierte Dateien bleiben unter {config.parent / "sources"} erhalten.') from error
        return get_project()

    @app.post('/api/ontologies/{ontology_id}/remove')
    def remove_ontology(ontology_id: str, request: RevisionRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            raw, yaml, document, entry = editable(ontology_id, request.revision)
            document['ontologies'].remove(entry)
            commit(raw, yaml, document)
        return get_project()

    @app.patch("/api/ontologies/{ontology_id}/path")
    def save_path(ontology_id: str, update: PathUpdate, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            raw, yaml, document, entry = editable(ontology_id, update.revision)
            path = Path(update.path)
            if not path.is_absolute():
                raise HTTPException(422, "Bitte einen absoluten Pfad auswählen.")
            path = path.resolve()
            if update.kind == "output":
                if not path.is_dir():
                    raise HTTPException(422, "Ausgabeordner existiert nicht.")
                document["output"] = stored_path(path)
            else:
                if not path.is_file():
                    raise HTTPException(422, "Datei existiert nicht.")
                try:
                    if update.kind == "content":
                        if path.suffix.lower() not in {".md", ".markdown"}:
                            raise ValueError("Bitte eine Markdown-Datei auswählen.")
                        from .content import read_editorial_source
                        read_editorial_source(path)
                    else:
                        item = next(o for o in project().ontologies if o.id == ontology_id)
                        load_ontology(path, rdf_format=item.options.get("format"))
                except Exception as error:
                    raise HTTPException(422, f"Datei konnte nicht gelesen werden: {error}") from error
                entry[update.kind] = stored_path(path)
            commit(raw, yaml, document)
        return get_project()

    @app.post("/api/ontologies/{ontology_id}/template")
    def generate_template(ontology_id: str, request: TemplateRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            raw, yaml, document, entry = editable(ontology_id, request.revision)
            item = next(o for o in project().ontologies if o.id == ontology_id)
            if item.content is not None:
                raise HTTPException(409, "Dieser Ontologie ist bereits Markdown zugeordnet.")
            language = str(item.options.get("language") or "en").lower().split("-")[0]
            if language not in {"de", "en"}:
                raise HTTPException(422, "Vorlagen sind nur auf Deutsch oder Englisch verfügbar.")
            name = f"{item.id}-documentation.{language}"
            output = project().output / item.id / f"{datetime.now():%Y-%m-%dT%H-%M-%S}_{name}-{uuid4().hex[:8]}" / f"{name}.md"
            try:
                create_content(item.input, output, language, request.profile, item.options.get("format"))
                entry["content"] = stored_path(output)
                commit(raw, yaml, document)
            except (OSError, ValueError, SyntaxError, ParserError) as error:
                raise HTTPException(422, f"Vorlage konnte nicht zugeordnet werden: {error}") from error
        return get_project()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/ontologies/{ontology_id}/markdown/detach")
    def detach_markdown(ontology_id: str, request: RevisionRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            raw, yaml, document, entry = editable(ontology_id, request.revision)
            entry.pop("content", None)
            entry["check_content"] = False
            commit(raw, yaml, document)
        return get_project()

    @app.post("/api/ontologies/{ontology_id}/markdown/check")
    def check_markdown(ontology_id: str, request: MarkdownCheckRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        editable(ontology_id, request.revision)
        item = next(o for o in project().ontologies if o.id == ontology_id)
        if item.content is None:
            raise HTTPException(422, "Keine Markdown-Datei zugeordnet.")
        from .content import parse_editorial_source
        from .content_check import check_content
        from dataclasses import asdict
        try:
            source = parse_editorial_source(request.content, item.content)
            return {"issues": [asdict(issue) for issue in check_content(source)],
                    "images": describe_images(ontology_id, source)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post('/api/ontologies/{ontology_id}/markdown/images')
    def preview_markdown_images(ontology_id: str, request: MarkdownCheckRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        editable(ontology_id, request.revision)
        item = next(o for o in project().ontologies if o.id == ontology_id)
        if item.content is None:
            raise HTTPException(422, 'Keine Markdown-Datei zugeordnet.')
        from .content import parse_editorial_source
        try:
            source = parse_editorial_source(request.content, item.content)
            return {'images': describe_images(ontology_id, source)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get('/api/ontologies/{ontology_id}/markdown/images/{token}')
    def markdown_image(ontology_id: str, token: str):
        from .markdown_images import IMAGE_TYPES
        with image_lock:
            record = image_previews.get(token)
        item = next((o for o in project().ontologies if o.id == ontology_id), None)
        if not record or record[0] != ontology_id or item is None or item.content != record[1]:
            raise HTTPException(404, 'Bildvorschau nicht mehr verfuegbar. Bitte erneut pruefen.')
        path = record[2]
        if not path.is_file() or path.suffix.lower() not in IMAGE_TYPES:
            raise HTTPException(404, 'Bilddatei nicht gefunden.')
        # Only explicitly inspected images are exposed, never their containing directory.
        return FileResponse(path, media_type=IMAGE_TYPES[path.suffix.lower()], headers={
            'Content-Security-Policy': "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:",
            'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
        })

    @app.put("/api/ontologies/{ontology_id}/markdown")
    def save_markdown(ontology_id: str, update: MarkdownUpdate, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            editable(ontology_id, update.revision)
            item = next(o for o in project().ontologies if o.id == ontology_id)
            if item.content is None:
                raise HTTPException(422, "Keine Markdown-Datei zugeordnet.")
            path = item.content
            temporary = None
            try:
                original = path.read_bytes()
                if hashlib.sha256(original).hexdigest() != update.content_revision:
                    raise HTTPException(409, "Markdown wurde zwischenzeitlich geändert. Bitte neu laden.")
                with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".md", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(update.content.encode("utf-8"))
                from .content import read_editorial_source
                read_editorial_source(temporary)
                editable(ontology_id, update.revision)
                if path.read_bytes() != original:
                    raise HTTPException(409, "Markdown wurde zwischenzeitlich geändert. Bitte neu laden.")
                os.replace(temporary, path)
            except (OSError, ValueError) as error:
                raise HTTPException(422, f"Markdown konnte nicht gespeichert werden: {error}") from error
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
        return get_markdown(ontology_id)

    @app.get("/api/ontologies/{ontology_id}/markdown/download")
    def download_markdown(ontology_id: str):
        item = next((o for o in project().ontologies if o.id == ontology_id), None)
        if item is None or item.content is None or not item.content.is_file():
            raise HTTPException(404, "Keine Markdown-Datei zugeordnet.")
        return FileResponse(item.content, filename=item.content.name, media_type="text/markdown")

    @app.post("/api/ontologies/{ontology_id}/export")
    def export_document(ontology_id: str, request: ExportRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, "Eine Generierung läuft bereits.")
        try:
            editable(ontology_id, request.revision)
            loaded = project()
            item = next(o for o in loaded.ontologies if o.id == ontology_id)
            if request.kind != 'markdown' and assignments().get(ontology_id, {}).get(request.kind):
                raise HTTPException(409, 'Bitte zuerst die vorhandene HTML-Zuordnung lösen.')
            if request.kind != "reference" and item.content is None:
                raise HTTPException(422, "Bitte zuerst Markdown zuordnen oder erzeugen.")
            options = item.options
            notices = []
            if request.kind != "reference" and options.get("check_content"):
                from .content import read_editorial_source
                from .content_check import check_content
                notices = [f"{issue.title}: {issue.kind}" for issue in check_content(read_editorial_source(item.content))]
            token = uuid4().hex
            if request.kind == "markdown":
                return {"kind": "markdown", "path": str(item.content), "preview": "",
                        "download": f"{url_prefix}/api/ontologies/{ontology_id}/markdown/download", "notices": notices}
            root = loaded.output / item.id / f"{datetime.now():%Y-%m-%dT%H-%M-%S}_{item.id}-{request.kind}-{token[:8]}"
            root.mkdir(parents=True, exist_ok=False)
            page = generate(item.input, root / f"{item.id}-{request.kind}.html",
                            content_path=item.content if request.kind == "combined" else None,
                            language=options.get("language"), rdf_format=options.get("format"),
                            recommendations=options.get("recommendations", False),
                            quality_report=options.get("quality_report", False),
                            include_custom_annotations=options.get("custom_annotations", False),
                            show_missing_endpoints=options.get("show_missing_endpoints", False),
                            include_external_classes=options.get("include_external_classes", False),
                            skip_missing_images=options.get("skip_missing_images", False), notices=notices, theme=options.get("theme", "light"))
            bundle = page.parent.parent if options.get('theme') == 'both' else page.parent
            archive = Path(shutil.make_archive(str(root / "documentation"), "zip", bundle))
            record = {'path': stored_path(page), 'archive': stored_path(archive), 'notices': notices, 'report_available': True}
            if options.get('theme') == 'both':
                record.update(root=stored_path(bundle), variants={v: stored_path(bundle / v / page.name) for v in ('light', 'dark')})
            with write_lock:
                editable(ontology_id, request.revision)
                if assignments().get(ontology_id, {}).get(request.kind):
                    raise HTTPException(409, 'Inzwischen wurde eine HTML-Datei zugeordnet. Die erzeugte Datei bleibt im Ausgabeordner erhalten.')
                store_assignment(ontology_id, request.kind, record)
            return linked_result(ontology_id, request.kind, record)
        except (OSError, ValueError, SyntaxError, ParserError) as error:
            raise HTTPException(422, f"Export fehlgeschlagen: {error}") from error
        finally:
            export_lock.release()

    @app.post("/api/portal/export")
    def export_portal(request: PortalRequest, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, "Eine Generierung läuft bereits.")
        try:
            from dataclasses import replace
            from .project import build_project
            loaded = project()
            selected = list(dict.fromkeys(request.ontologies))
            if not request.title.strip() or set(selected) - {o.id for o in loaded.ontologies}:
                raise HTTPException(422, "Bitte einen Portaltitel und gültige Ontologien auswählen.")
            with write_lock:
                editable(selected[0], request.revision)
                if (assignments().get('$portal', {}).get('portal') or {}).get('path'):
                    raise HTTPException(409, 'Bitte zuerst die vorhandene Portal-Zuordnung lösen.')
            result = build_project(replace(loaded, output=loaded.output / 'portal',
                                           portal_title=request.title.strip()), selected=selected, portal=True, overrides={'theme': request.theme})
            archive = Path(shutil.make_archive(str(result.directory) + '-bundle', 'zip', result.directory))
            record = {'path': stored_path(result.portal), 'archive': stored_path(archive),
                      'notices': list(result.notices), 'title': request.title.strip(), 'ontologies': selected, 'theme': request.theme}
            if request.theme == 'both':
                record.update(root=stored_path(result.directory), variants={v: stored_path(result.directory / v / 'index.html') for v in ('light', 'dark')})
            with write_lock:
                editable(selected[0], request.revision)
                if (assignments().get('$portal', {}).get('portal') or {}).get('path'):
                    raise HTTPException(409, 'Inzwischen wurde ein Portal zugeordnet. Die erzeugten Dateien bleiben erhalten.')
                store_assignment('$portal', 'portal', record)
            return get_project()
        except (OSError, ValueError, SyntaxError, ParserError) as error:
            raise HTTPException(422, f"Portal konnte nicht erstellt werden: {error}. Eventuelle Teilausgaben bleiben im Ausgabeordner erhalten.") from error
        finally:
            export_lock.release()

    @app.put('/api/portal/html')
    def assign_portal(update: HtmlAssignment, x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, 'Eine Generierung läuft bereits.')
        try:
            with write_lock:
                editable(None, update.revision)
                previous = assignments().get('$portal', {}).get('portal') or {}
                record = {key: previous[key] for key in ('title', 'ontologies', 'theme') if key in previous}
                record['path'] = None
                if update.path is not None:
                    page = Path(update.path)
                    if not page.is_absolute() or not page.is_file() or page.suffix.lower() not in {'.html', '.htm'}:
                        raise HTTPException(422, 'Bitte eine vorhandene Portal-HTML-Datei auswählen.')
                    record['path'] = stored_path(page)
                store_assignment('$portal', 'portal', record)
            return get_project()
        finally:
            export_lock.release()

    @app.get("/api/exports/{token}/download")
    def download_export(token: str):
        record = export_record(token)
        if record is None:
            raise HTTPException(404, "Export nicht gefunden")
        if not record['download'].is_file():
            raise HTTPException(404, 'HTML-Datei nicht gefunden')
        return FileResponse(record["download"], filename=record["download"].name)

    @app.get("/api/exports/{token}/files/{filename:path}")
    def preview_export(token: str, filename: str):
        record = export_record(token)
        if record is None:
            raise HTTPException(404, "Export nicht gefunden")
        root = record["root"].resolve()
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file() or not any(path in linked_files(page, root) for page in record['pages']):
            raise HTTPException(404, "Datei nicht gefunden")
        return FileResponse(path, headers={"Content-Security-Policy": "sandbox allow-scripts allow-downloads", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/project")
    def get_project():
        try:
            raw = config.read_bytes()
        except OSError as error:
            raise HTTPException(422, f"Cannot load project: {error}") from error
        loaded = project()
        if config.read_bytes() != raw:
            raise HTTPException(409, "Project changed while reading; reload")
        notices = []
        for item in loaded.ontologies:
            if item.content is not None and not item.content.is_file():
                notices.append({"ontology": item.id, "message": f"Markdown-Datei fehlt: {item.content}"})
            try:
                doc = load_ontology(item.input, rdf_format=item.options.get("format"), language=item.options.get("language") or "en")
                for figure in doc.hero_figures:
                    if not _is_external(figure.src) and not (item.input.parent / figure.src).is_file():
                        notices.append({"ontology": item.id, "message": f"Abbildung fehlt: {figure.src}"})
            except Exception:
                notices.append({"ontology": item.id, "message": "Ontologie konnte für die Übersicht nicht gelesen werden."})
        linked = assignments()
        portal_record = linked.get('$portal', {}).get('portal')
        return {"name": loaded.name, "config": str(config), "output": str(loaded.output),
                "revision": hashlib.sha256(raw).hexdigest(),
                "notices": notices,
                "portal": {"enabled": loaded.portal_enabled, "title": loaded.portal_title,
                           "last_title": portal_record.get('title') if portal_record else None,
                           "selection": portal_record.get('ontologies') if portal_record else None,
                           "theme": portal_record.get('theme', 'light') if portal_record else 'light',
                           "result": linked_result('$portal', 'portal', portal_record)},
                "ontologies": [{"id": item.id, "input": str(item.input),
                                "content": str(item.content) if item.content else None,
                                "html": {kind: linked_result(item.id, kind, linked.get(item.id, {}).get(kind)) for kind in ('reference', 'combined')},
                                "options": item.options} for item in loaded.ontologies]}

    @app.put('/api/ontologies/{ontology_id}/html/{kind}')
    def assign_html(ontology_id: str, kind: Literal['reference', 'combined'], update: HtmlAssignment,
                    x_ontolens_write: str | None = Header(default=None)):
        require_write(x_ontolens_write)
        with write_lock:
            editable(ontology_id, update.revision)
            record = None
            if update.path is not None:
                page = Path(update.path)
                if not page.is_absolute() or page.suffix.lower() not in {'.html', '.htm'} or not page.is_file():
                    raise HTTPException(422, 'Bitte eine vorhandene HTML-Datei auswählen.')
                record = {'path': stored_path(page), 'notices': [], 'report_available': False}
            store_assignment(ontology_id, kind, record)
        return get_project()

    @app.patch("/api/ontologies/{ontology_id}/settings")
    def save_settings(ontology_id: str, update: SettingsUpdate,
                      x_ontolens_write: str | None = Header(default=None)):
        if x_ontolens_write != "1":
            raise HTTPException(403, "Missing write header")
        with write_lock:
            loaded = project()
            raw = config.read_bytes()
            if hashlib.sha256(raw).hexdigest() != update.revision:
                raise HTTPException(409, "Projekt wurde zwischenzeitlich geändert. Bitte neu laden.")
            item = next((o for o in loaded.ontologies if o.id == ontology_id), None)
            if item is None:
                raise HTTPException(404, "Unknown ontology")
            if update.check_content and item.content is None:
                raise HTTPException(422, "Markdown-Prüfung benötigt eine zugeordnete Markdown-Datei.")
            yaml = YAML()
            yaml.preserve_quotes = True
            document = yaml.load(raw.decode("utf-8-sig"))
            entry = next(o for o in document["ontologies"] if o["id"] == ontology_id)
            changes = update.model_dump(exclude={"revision"}, exclude_none=True)
            for key in ("language", "format"):
                if key in update.model_fields_set:
                    changes[key] = getattr(update, key)
            if changes.get("format"):
                from rdflib.plugin import get, PluginException
                from rdflib.parser import Parser
                try:
                    get(changes["format"], Parser)
                except PluginException as error:
                    raise HTTPException(422, "Unbekanntes RDF-Parserformat.") from error
            for key, value in changes.items():
                if item.options.get(key, False) != value:
                    entry[key] = value
            buffer = io.StringIO()
            yaml.dump(document, buffer)
            content = buffer.getvalue().encode("utf-8")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=config.parent, suffix=".yaml", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                load_project(temporary, require_sources=False)
                if config.read_bytes() != raw:
                    raise HTTPException(409, "Projekt wurde zwischenzeitlich geändert. Bitte neu laden.")
                os.replace(temporary, config)
            except OSError as error:
                raise HTTPException(500, "Konfiguration konnte nicht gespeichert werden.") from error
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            return {"revision": hashlib.sha256(content).hexdigest(), "options": item.options | changes}

    @app.get("/api/ontologies/{ontology_id}/markdown")
    def get_markdown(ontology_id: str):
        item = next((item for item in project().ontologies if item.id == ontology_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Unknown ontology")
        if item.content is None:
            return {"content": None}
        try:
            raw = item.content.read_bytes()
            return {"content": raw.decode("utf-8-sig"), "content_revision": hashlib.sha256(raw).hexdigest()}
        except OSError as error:
            raise HTTPException(status_code=422, detail="Cannot read Markdown file") from error

    return app


def create_app(config_path: Path | None = None) -> FastAPI:
    """Each opened project gets an isolated API, not a shared active-project pointer."""
    config = (config_path or Path(os.environ.get('ONTOLENS_PROJECT', 'ontolens.project.yaml'))).resolve()
    app = create_project_app(config)
    registry_path = config.with_suffix('.projects.json')
    registry_lock = Lock()
    projects = {}

    def save_registry():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=config.parent, suffix='.json', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps([p['path'] for p in projects.values()], indent=2).encode())
            os.replace(temporary, registry_path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def register(path):
        path = Path(path).resolve()
        identity = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:20]
        if identity not in projects:
            base = '' if path == config else f'/workspaces/{identity}'
            if base:
                app.mount(base, create_project_app(path, base))
                # New workspaces must precede the production frontend catch-all.
                frontend = next((i for i, route in enumerate(app.routes) if route.name == 'frontend'), None)
                if frontend is not None:
                    app.router.routes.insert(frontend, app.router.routes.pop())
            projects[identity] = {'id': identity, 'path': str(path), 'base': base}
        return projects[identity]

    if registry_path.exists():
        for path in json.loads(registry_path.read_text(encoding='utf-8')):
            register(path)
    else:
        register(config)

    @app.get('/api/projects')
    def list_projects():
        result = []
        with registry_lock:
            entries = list(projects.values())
        for entry in entries:
            try:
                project = load_project(Path(entry['path']), require_sources=False)
                result.append(entry | {'name': project.name, 'count': len(project.ontologies), 'available': True})
            except (OSError, ValueError, YAMLError):
                result.append(entry | {'name': Path(entry['path']).stem, 'count': 0, 'available': False})
        return {'projects': result, 'default': entries[0]['id'] if entries else None}

    @app.delete('/api/projects/{project_id}')
    def remove_project(project_id: str, x_ontolens_write: str | None = Header(default=None)):
        if x_ontolens_write != '1':
            raise HTTPException(403, 'Missing write header')
        with registry_lock:
            if project_id not in projects:
                raise HTTPException(404, 'Projekt nicht gefunden.')
            previous = projects.copy()
            entry = projects.pop(project_id)
            try:
                save_registry()
            except OSError as error:
                projects.clear()
                projects.update(previous)
                raise HTTPException(500, 'Projektliste konnte nicht gespeichert werden.') from error
            if entry['base']:
                app.router.routes[:] = [route for route in app.routes if getattr(route, 'path', None) != entry['base']]
            return {'removed': project_id, 'files_preserved': True}

    @app.post('/api/projects/open')
    def open_project(x_ontolens_write: str | None = Header(default=None), request: OpenProjectRequest | None = None):
        if x_ontolens_write != '1':
            raise HTTPException(403, 'Missing write header')
        with registry_lock:
            if request is not None and request.path is not None:
                from .deployment import selected_path
                selected = str(selected_path(request.path))
            else:
                selected = choose_local_path('project', config.parent)
            if not selected:
                return {'project': None}
            try:
                load_project(Path(selected), require_sources=False)
                entry = register(selected)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=config.parent, suffix='.json', delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(json.dumps([p['path'] for p in projects.values()], indent=2).encode())
                    os.replace(temporary, registry_path)
                finally:
                    if temporary and temporary.exists():
                        temporary.unlink()
                return {'project': entry}
            except (OSError, ValueError, YAMLError) as error:
                raise HTTPException(422, f'Projekt konnte nicht geöffnet werden: {error}') from error

    @app.post('/api/projects/dialog/{kind}')
    def project_dialog(kind: Literal['directory', 'ontologies'], x_ontolens_write: str | None = Header(default=None)):
        if x_ontolens_write != '1':
            raise HTTPException(403, 'Missing write header')
        with registry_lock:
            value = choose_local_path('output' if kind == 'directory' else 'ontologies', config.parent)
            return {'path': value} if kind == 'directory' else {'paths': value or []}

    @app.post('/api/projects')
    def new_project(request: NewProject, x_ontolens_write: str | None = Header(default=None)):
        if x_ontolens_write != '1':
            raise HTTPException(403, 'Missing write header')
        with registry_lock:
            name = request.name.strip()
            parent = Path(request.directory)
            if not name or len(name) > 120:
                raise HTTPException(422, 'Bitte einen Projektnamen mit 1 bis 120 Zeichen angeben.')
            if not parent.is_absolute() or not parent.is_dir():
                raise HTTPException(422, 'Bitte einen vorhandenen Speicherordner auswählen.')
            if not request.ontologies:
                raise HTTPException(422, 'Bitte mindestens eine Ontologie hinzufügen.')
            inputs = []
            seen = set()
            for value in request.ontologies:
                source = Path(value)
                if not source.is_absolute() or not source.is_file():
                    raise HTTPException(422, f'Ontologiedatei nicht gefunden: {value}')
                source = source.resolve()
                if source in seen:
                    continue
                try:
                    load_ontology(source)
                except Exception as error:
                    raise HTTPException(422, f'Ontologie kann nicht gelesen werden: {source.name}: {error}') from error
                seen.add(source)
                inputs.append(source)
            slug = re.sub(r'[^a-z0-9_-]+', '-', name.lower()).strip('-_') or 'ontology'
            directory = parent.resolve() / f'{slug}-project'
            entries = []
            ids = set()
            for source in inputs:
                stem = re.sub(r'[^a-z0-9_-]+', '-', source.stem.lower()).strip('-_') or 'ontology'
                identity = f'ontology-{stem}'
                suffix = 2
                while identity in ids:
                    identity = f'ontology-{stem}-{suffix}'
                    suffix += 1
                ids.add(identity)
                entries.append({'id': identity, 'input': str(source)})
            document = {'name': name, 'output': 'build', 'ontologies': entries, 'portal': {'enabled': False, 'title': name}}
            try:
                directory.mkdir(exist_ok=False)
            except FileExistsError as error:
                raise HTTPException(409, 'Der Projektordner existiert bereits. Bitte einen anderen Namen oder Speicherort wählen.') from error
            except OSError as error:
                raise HTTPException(422, f'Projektordner konnte nicht erstellt werden: {error}') from error
            try:
                path = directory / 'ontolens.project.yaml'
                if request.copy_sources:
                    from .source_bundle import copy_ontology
                    for entry, source in zip(entries, inputs):
                        copied = copy_ontology(source, directory / 'sources' / entry['id'])
                        entry['input'] = copied.relative_to(directory).as_posix()
                with path.open('x', encoding='utf-8') as stream:
                    YAML().dump(document, stream)
                load_project(path)
                entry = register(path)
                save_registry()
                return {'project': entry}
            except (OSError, ValueError, YAMLError) as error:
                raise HTTPException(422, f'Projekt konnte nicht fertiggestellt werden. Dateien bleiben unter {directory} erhalten: {error}') from error

    from .deployment import configure_runtime
    configure_runtime(app)
    return app
