"""Create portable project copies without modifying the working project."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from xml.etree import ElementTree
from zipfile import ZipFile, ZIP_DEFLATED

import markdown
import yaml
from bs4 import BeautifulSoup
from rdflib import Graph
from rdflib.namespace import OWL

from .assets import AssetBundle
from .content import _split_frontmatter
from .project import load_project
from .parser import FORMAT_BY_SUFFIX
from .source_bundle import copy_ontology


def local_reference(ref: str, parent: Path) -> Path | None:
    url = urlsplit(ref)
    if url.scheme == 'file':
        if url.netloc and url.netloc != 'localhost':
            raise ValueError(f'Netzwerk-Dateiverknüpfung wird nicht übernommen: {ref}')
        return Path(url2pathname(url.path)).resolve()
    if Path(ref).is_absolute():
        return Path(ref).resolve()
    if ref.startswith('#') or url.scheme or url.netloc:
        return None
    return (parent / unquote(url.path)).resolve() if url.path else None


def export_dependencies(pages: list[Path], root: Path) -> set[Path]:
    pending = list(pages)
    found: set[Path] = set()
    while pending:
        source = pending.pop().resolve()
        if source in found:
            continue
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f'Exportdatei fehlt oder liegt außerhalb des Exportordners: {source}')
        found.add(source)
        if source.suffix.lower() not in {'.html', '.htm', '.css', '.svg'}:
            continue
        text = source.read_text(encoding='utf-8')
        refs = re.findall(r'url\(\s*[\x22\x27]?([^\)\x22\x27]+)', text)
        if source.suffix.lower() == '.svg':
            svg = ElementTree.fromstring(text)
            refs.extend(value for node in svg.iter() for key, value in node.attrib.items() if key.rsplit('}', 1)[-1] == 'href')
        elif source.suffix.lower() != '.css':
            soup = BeautifulSoup(text, 'html.parser')
            refs.extend(str(tag[attr]) for tag in soup.find_all(True) for attr in ('src', 'href', 'poster') if tag.has_attr(attr))
        for ref in refs:
            target = local_reference(ref.strip(), source.parent)
            if target is not None:
                if Path(ref).is_absolute() or urlsplit(ref).scheme == 'file':
                    raise ValueError(f'Absolute Dateiverknüpfung im HTML-Export: {ref}. Bitte Dokumentation neu generieren.')
                pending.append(target)
    return found


def copy_markdown(source: Path, destination: Path, notices: list[str]) -> Path:
    text = source.read_text(encoding='utf-8-sig')
    _, body = _split_frontmatter(text, source)
    rendered = BeautifulSoup(markdown.markdown(body, extensions=['extra']), 'html.parser')
    assets = AssetBundle(destination)
    for tag in rendered.find_all('img', src=True):
        ref = str(tag['src'])
        local = local_reference(ref, source.parent)
        if local is None:
            if not ref.startswith('data:'):
                notices.append(f'Online-Bild im Markdown bleibt extern: {ref}')
            continue
        replacement = assets.copy_image(local)
        fragment = urlsplit(ref).fragment
        if fragment:
            replacement += '#' + fragment
        # Match only destinations, not prose occurrences of the same filename.
        for spelling in {ref, ref.replace('&', '&amp;')}:
            pattern = r'(\]\(\s*<?|\]:\s*<?|\bsrc\s*=\s*[\x22\x27])' + re.escape(spelling) + r'(?=[\s>)\x22\x27])'
            text = re.sub(pattern, lambda m: m[1] + replacement, text)
    target = destination / source.name
    target.write_text(text, encoding='utf-8')
    # Fail closed for unsupported image syntax instead of shipping broken paths.
    _, copied_body = _split_frontmatter(text, target)
    copied_html = BeautifulSoup(markdown.markdown(copied_body, extensions=['extra']), 'html.parser')
    for tag in copied_html.find_all('img', src=True):
        local = local_reference(str(tag['src']), destination)
        if local is not None and (not local.is_relative_to(destination.resolve()) or not local.is_file()):
            raise ValueError(f'Markdown-Bild kann nicht portabel übernommen werden: {tag["src"]}')
    for tag in copied_html.find_all('a', href=True):
        ref = str(tag['href'])
        if local_reference(ref, destination) is not None:
            notices.append(f'Lokaler Markdown-Link ist kein Bild und wird nicht gebündelt: {ref}')
    return target


def create_project_archive(config: Path, destination: Path, *, include_outputs: bool = False,
                           assignments: dict | None = None) -> tuple[Path, list[str]]:
    config = config.resolve()
    project = load_project(config)
    document = yaml.safe_load(config.read_text(encoding='utf-8-sig'))
    notices: list[str] = []
    root = destination / 'project'
    root.mkdir()
    document['output'] = 'build'
    for entry, item in zip(document['ontologies'], project.ontologies):
        copied = copy_ontology(item.input, root / 'sources' / item.id, notices=notices,
                               rdf_format=item.options.get('format'))
        entry['input'] = copied.relative_to(root).as_posix()
        if not item.input.is_relative_to(config.parent):
            notices.append(f'{item.id}: extern verknüpfte Ontologiedatei ins Paket kopiert.')
        graph = Graph().parse(item.input, format=item.options.get('format') or FORMAT_BY_SUFFIX[item.input.suffix.lower()])
        for imported in graph.objects(None, OWL.imports):
            notices.append(f'owl:imports wird nicht automatisch gebündelt: {imported}')
        if item.content:
            copied_md = copy_markdown(item.content, root / 'content' / item.id, notices)
            entry['content'] = copied_md.relative_to(root).as_posix()
    output_assignments = {}
    if include_outputs:
        for identity, kinds in (assignments or {}).items():
            if identity not in {item.id for item in project.ontologies} | {'$portal'}:
                continue
            for kind, record in kinds.items():
                if not record or not record.get('path'):
                    continue
                page = (config.parent / record['path']).resolve()
                source_root = (config.parent / record['root']).resolve() if record.get('root') else page.parent
                target_root = root / 'build' / f'export-{sum(len(kinds) for kinds in output_assignments.values()) + 1}'
                pages = [page, *((config.parent / value).resolve() for value in record.get('variants', {}).values())]
                dependencies = export_dependencies(pages, source_root)
                for source in dependencies:
                    if not source.is_relative_to(source_root) or not source.is_file():
                        raise ValueError(f'Exportdatei fehlt oder liegt außerhalb des Exportordners: {source}')
                    target = target_root / source.relative_to(source_root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                def relocated(value):
                    return (target_root / (config.parent / value).resolve().relative_to(source_root)).relative_to(root).as_posix()
                output_assignments.setdefault(identity, {})[kind] = {
                    **{key: value for key, value in record.items() if key not in {'path', 'root', 'archive', 'variants'}},
                    'path': relocated(record['path']), 'root': target_root.relative_to(root).as_posix(),
                    'variants': {name: relocated(value) for name, value in record.get('variants', {}).items()},
                }
        notices.append('Enthaltene HTML-Dokumente können weiterhin externe Web-Bibliotheken verwenden; kein Offline-Archiv.')
    portable_config = root / 'ontolens.project.yaml'
    portable_config.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding='utf-8')
    if output_assignments:
        portable_config.with_suffix('.outputs.json').write_text(json.dumps(output_assignments, ensure_ascii=False, indent=2), encoding='utf-8')
    load_project(portable_config)
    notices = list(dict.fromkeys(notices))
    (root / 'EXPORT-INFO.txt').write_text(
        'OntoLens project package\n\nOpen ontolens.project.yaml in OntoLens.\n'
        'Output directory: build (relative to this folder).\n'
        'Only assigned HTML documents/portals are included when requested, not build history.\n\n'
        + '\n'.join(notices), encoding='utf-8')
    archive = destination / 'project.zip'
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as output:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                output.write(path, path.relative_to(destination).as_posix())
    return archive, notices
