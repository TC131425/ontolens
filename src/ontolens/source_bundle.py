"""Copy ontology sources and their local image references into a project."""
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF

from .assets import AssetBundle
from .parser import FORMAT_BY_SUFFIX


def copy_ontology(source: Path, destination: Path, *, notices: list[str] | None = None, rdf_format: str | None = None) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    assets = AssetBundle(destination)
    copied: dict[Path, str] = {}

    def image(ref: str, base: Path) -> str:
        parsed = urlsplit(ref)
        if parsed.scheme in {'http', 'https', 'data'} or ref.startswith('//') or ref.startswith('#'):
            if notices is not None and (parsed.scheme in {'http', 'https'} or ref.startswith('//')):
                notices.append(f'Online-Bild bleibt extern: {ref}')
            return ref
        if parsed.scheme == 'file':
            path = Path(url2pathname(('//' + parsed.netloc if parsed.netloc and parsed.netloc != 'localhost' else '') + parsed.path))
        elif Path(ref).is_absolute():
            path = Path(ref)
        elif parsed.scheme:
            raise ValueError(f'Unsupported local image reference: {ref}')
        else:
            path = base / unquote(parsed.path)
        path = path.resolve()
        if path.suffix.lower() not in {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.bmp', '.tif', '.tiff', '.ico'}:
            raise ValueError(f'Unsupported image file: {path}')
        if path in copied:
            return copied[path] + (f'#{parsed.fragment}' if parsed.fragment else '')
        href = assets.copy_image(path)
        copied[path] = href
        # Keep linked raster images in SVGs portable as well.
        if path.suffix.lower() == '.svg':
            try:
                tree = ElementTree.parse(path)
            except ElementTree.ParseError as error:
                raise ValueError(f'Invalid SVG image: {path}') from error
            changed = False
            for node in tree.iter():
                for attribute in ('href', '{http://www.w3.org/1999/xlink}href'):
                    ref = node.get(attribute)
                    if ref and node.tag.rsplit('}', 1)[-1] in {'image', 'use'}:
                        replacement = image(ref, path.parent)
                        if replacement != ref:
                            node.set(attribute, Path(replacement).name)
                            changed = True
            if changed:
                tree.write(destination / href, encoding='utf-8', xml_declaration=True)
        return href + (f'#{parsed.fragment}' if parsed.fragment else '')

    graph = Graph()
    rdf_format = rdf_format or FORMAT_BY_SUFFIX[source.suffix.lower()]
    graph.parse(source, format=rdf_format)
    changed = False
    pattern = re.compile(r'(!\[[^\]]*\]\()([^\s)]+)([^)]*\))')
    for subject, predicate, value in list(graph):
        replacement = value
        if isinstance(value, Literal):
            text = str(value)
            updated = pattern.sub(lambda match: match[1] + image(match[2], source.parent) + match[3], text)
            if '<img' in updated.lower():
                soup = BeautifulSoup(updated, 'html.parser')
                for tag in soup.find_all('img', src=True):
                    tag['src'] = image(tag['src'], source.parent)
                updated = str(soup)
            if predicate in (FOAF.logo, FOAF.depiction) and updated.strip() and '<' not in updated:
                updated = image(updated, source.parent)
            if updated != text:
                replacement = Literal(updated, lang=value.language, datatype=value.datatype)
        elif isinstance(value, URIRef) and predicate in (FOAF.logo, FOAF.depiction):
            href = image(str(value), source.parent)
            if rdf_format == 'nt' and href != str(value):
                raise ValueError('Local image IRIs in N-Triples cannot be made relative. Use Turtle for a portable copy.')
            replacement = URIRef(href)
        if replacement != value:
            graph.remove((subject, predicate, value))
            graph.add((subject, predicate, replacement))
            changed = True
    target = destination / source.name
    if changed:
        graph.serialize(target, format=rdf_format)
    else:
        shutil.copy2(source, target)
    return target
