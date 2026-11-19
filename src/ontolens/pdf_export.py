"""Print existing HTML snapshots without running their scripts or network requests."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from html import escape
import json
import mimetypes
import re
from pathlib import Path
from threading import Lock
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from xml.etree import ElementTree

from bs4 import BeautifulSoup

STATIC = Path(__file__).parent / 'static'
PDF_LOCK = Lock()
IMAGE_TYPES = {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.bmp', '.ico'}


@dataclass(frozen=True)
class PdfOptions:
    paper: str = 'A4'
    figures: bool = True
    graph: bool = False

    def __post_init__(self):
        if self.paper not in {'A4', 'A3'}:
            raise ValueError('Papierformat muss A4 oder A3 sein.')


def _image_data(ref: str, parent: Path, root: Path, notices: list[str], seen: frozenset = frozenset()) -> str | None:
    url = urlsplit(ref)
    if ref.startswith('data:image/'):
        return ref
    if url.scheme in {'http', 'https'} or url.netloc:
        notices.append(f'Online-Bild nicht in PDF geladen: {ref}')
        return None
    if ref.startswith('#'):
        return ref
    if url.scheme == 'file':
        source = Path(url2pathname(url.path)).resolve()
    elif Path(ref).is_absolute():
        source = Path(ref).resolve()
    elif url.scheme:
        raise ValueError(f'Nicht unterstützte Bildadresse: {ref}')
    else:
        source = (parent / unquote(url.path)).resolve()
    if not source.is_relative_to(root) or source.suffix.lower() not in IMAGE_TYPES:
        raise ValueError(f'Bild liegt außerhalb des Dokumentationsordners oder hat ein nicht unterstütztes Format: {ref}')
    if source in seen or len(seen) > 20:
        raise ValueError(f'Zirkulärer oder zu tief verschachtelter Bildverweis: {source.name}')
    if not source.is_file():
        raise ValueError(f'Bilddatei fehlt: {source}')
    if source.stat().st_size > 30_000_000:
        raise ValueError(f'Bilddatei ist zu groß für den PDF-Export: {source.name}')
    data = source.read_bytes()
    if source.suffix.lower() == '.svg':
        svg = ElementTree.fromstring(data)
        for node in svg.iter():
            for child in list(node):
                if child.tag.rsplit('}', 1)[-1] in {'script', 'foreignObject'}:
                    node.remove(child)
            for attr, value in list(node.attrib.items()):
                if attr.lower().startswith('on'):
                    del node.attrib[attr]
                elif attr.rsplit('}', 1)[-1] == 'href' and not value.startswith('#'):
                    if node.tag.rsplit('}', 1)[-1] in {'image', 'use'}:
                        replacement = _image_data(value, source.parent, root, notices, seen | {source})
                        if replacement:
                            node.set(attr, replacement)
                        else:
                            del node.attrib[attr]
                    else:
                        del node.attrib[attr]
        data = ElementTree.tostring(svg, encoding='utf-8')
    mime = mimetypes.guess_type(source.name)[0] or 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')


def prepare_html(source: Path, options: PdfOptions, root: Path | None = None) -> tuple[str, str, dict | None, list[str]]:
    source = source.resolve()
    root = (root or source.parent).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError(f'HTML-Dokumentation nicht gefunden: {source}')
    if source.stat().st_size > 50_000_000:
        raise ValueError('HTML-Datei ist zu groß für den PDF-Export (maximal 50 MB).')
    text = source.read_text(encoding='utf-8-sig')
    soup = BeautifulSoup(text, 'html.parser')
    if soup.body is None or soup.html is None:
        raise ValueError('Die Datei enthält kein vollständiges HTML-Dokument.')
    title = soup.title.get_text(' ', strip=True) if soup.title else source.stem
    notices: list[str] = []
    graph = None
    if options.graph:
        for script in soup.find_all('script'):
            match = re.search(r'window\.ontolensVisualization\s*=\s*', script.get_text())
            if match:
                visualization_data = json.JSONDecoder().raw_decode(script.get_text()[match.end():])[0]
                graph = visualization_data['elements']
                if isinstance(graph, dict):
                    graph['ontologies'] = visualization_data.get('ontologies', [])
                break
        if graph is None:
            notices.append('Keine gespeicherten OntoLens-Graphdaten vorhanden; Graph ausgelassen.')
        elif not isinstance(graph, dict) or len(graph.get('nodes', [])) > 1000 or len(graph.get('edges', [])) > 3000:
            raise ValueError('Graph zu groß oder ungültig. Bitte ohne Graph exportieren.')
    for tag in soup.select('script, base, meta, link, iframe, object, embed, form, button, input, select, textarea, video, audio, canvas, aside.toc, .document-options, .figure-zoom, .visualization-actions, .datatype-inspector, #visualization-fallback, body > nav, footer'):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on') or attr.lower() in {'srcdoc', 'srcset'}:
                del tag[attr]
    if not options.figures:
        for tag in soup.select('#figures, figure, img'):
            if tag.parent is not None:
                tag.decompose()
    else:
        for image in soup.find_all('img'):
            ref = image.get('src')
            if not ref:
                image.decompose()
                continue
            data = _image_data(str(ref), source.parent, root, notices)
            if data:
                image['src'] = data
                image.attrs.pop('loading', None)
            else:
                placeholder = soup.new_tag('p')
                placeholder.string = f'[Online-Abbildung: {image.get("alt", ref)}]'
                image.replace_with(placeholder)
    visualization = soup.select_one('#visualization')
    if visualization:
        if graph is None:
            visualization.decompose()
        else:
            heading = visualization.find(['h2', 'h3'])
            heading_text = heading.get_text(' ', strip=True) if heading else 'Graph'
            ontology_legend = visualization.select_one('.ontology-legend')
            if ontology_legend:
                ontology_legend.extract()
            type_legend = visualization.select_one('.graph-type-legend')
            if type_legend:
                type_legend.extract()
            elif any(edge.get('data', {}).get('edgeKind') == 'subClassOf' for edge in graph.get('edges', [])):
                # Older HTML snapshots lack the hierarchy legend.
                type_legend = BeautifulSoup('<div class="legend graph-type-legend"><span class="legend-item subclass-legend"><svg width="32" height="14" viewBox="0 0 32 14"><path d="M1 7H25" fill="none" stroke="currentColor" stroke-width="1.55"/><path d="M24 3L31 7L24 11Z" fill="currentColor"/></svg>rdfs:subClassOf</span></div>', 'html.parser').div
            visualization.clear()
            h = soup.new_tag('h2'); h.string = heading_text
            visualization.append(h)
            if type_legend:
                visualization.append(type_legend)
            if ontology_legend:
                visualization.append(ontology_legend)
            visualization.append(soup.new_tag('div', id='ontology-graph'))
            if len(graph.get('nodes', [])) > 50:
                notices.append('Großer Graph: Beschriftungen können auf Papier sehr klein werden; gegebenenfalls A3 wählen.')
    elif graph is not None:
        graph = None
        notices.append('Kein Graphbereich in der HTML-Datei gefunden; Graph ausgelassen.')
    for details in soup.find_all('details'):
        details['open'] = ''
    # Apply the same grouping to previously generated HTML snapshots.
    for listing in soup.select('.restriction-list'):
        row = listing.find_parent('tr')
        if row:
            row['class'] = list(dict.fromkeys([*row.get('class', []), 'restriction-row']))
        for constraint in listing.select('.restriction-constraint'):
            if constraint.find_parent(class_='restriction-condition'):
                continue
            value = constraint.find_next_sibling()
            group = soup.new_tag('span', attrs={'class': 'restriction-condition'})
            constraint.wrap(group)
            if value and value.name == 'strong':
                group.append(' ')
                group.append(value.extract())
    # Convert local term IRIs into PDF-internal destinations.
    terms = {}
    for article in soup.select('article.term[id]'):
        iri = article.select_one('tr td a[href]')
        if iri:
            terms[iri['href']] = '#' + article['id']
    for link in soup.find_all('a', href=True):
        href = str(link['href'])
        if href in terms:
            link['href'] = terms[href]
        elif not href.startswith(('#', 'https://', 'http://', 'mailto:')):
            del link['href']
    soup.html['data-theme'] = 'light'
    soup.html.attrs.pop('style', None)
    toc = soup.new_tag('section', attrs={'class': 'pdf-toc'})
    heading = soup.new_tag('h2'); heading.string = 'Inhaltsverzeichnis' if soup.html.get('lang', '').startswith('de') else 'Contents'
    toc.append(heading)
    listing = soup.new_tag('ul')
    for index, heading in enumerate(soup.select('main h1, main h2, main > section > h3[id]')):
        parent = heading.parent
        anchor = heading.get('id') or (parent.get('id') if parent.name == 'section' else None) or f'pdf-heading-{index}'
        if not heading.get('id') and not parent.get('id'):
            heading['id'] = anchor
        li = soup.new_tag('li'); link = soup.new_tag('a', href='#' + anchor)
        link.string = heading.get_text(' ', strip=True); li.append(link); listing.append(li)
    toc.append(listing)
    main = soup.find('main')
    if main and listing.contents:
        main.insert(0, toc)
    style = soup.new_tag('style'); style.string = (STATIC / 'pdf.css').read_text(encoding='utf-8')
    style.string += (
        f'\n@page {{ size: {options.paper} portrait; }}'
        f'\n@page ontology-graph {{ size: {options.paper} landscape; }}'
        f'\n:root {{ --pdf-graph-page-height: {172 if options.paper == "A4" else 259}mm; }}'
    )
    if soup.head is None:
        soup.html.insert(0, soup.new_tag('head'))
    soup.head.append(style)
    return str(soup), title, graph, list(dict.fromkeys(notices))


def render_pdf(source: Path, output: Path, options: PdfOptions = PdfOptions(), *, root: Path | None = None) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError as error:
        raise RuntimeError('PDF-Komponente fehlt. Bitte uv sync --extra web --extra pdf ausführen und Chromium installieren.') from error
    html, title, graph, notices = prepare_html(source, options, root)
    with PDF_LOCK:
        try:
            with sync_playwright() as engine:
                browser = engine.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
                try:
                    context = browser.new_context(offline=True, service_workers='block', viewport={'width': 1200, 'height': 900})
                    context.route('**/*', lambda route: route.abort())
                    page = context.new_page()
                    page.set_default_timeout(60000)
                    page.set_content(html, wait_until='load')
                    if graph is not None:
                        for name in ('cytoscape.min', 'layout-base', 'cose-base', 'cytoscape-fcose',
                                     'graph-layout', 'graph-labels', 'pdf_graph'):
                            page.add_script_tag(path=str(STATIC / f'{name}.js'))
                        page.evaluate('elements => renderPdfGraph(elements)', graph)
                    page.evaluate('async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, img => img.decode().catch(() => {}))); }')
                    broken = page.evaluate('() => Array.from(document.images).filter(img => !img.naturalWidth).map(img => img.alt || "image")')
                    if broken:
                        raise ValueError('Bilder konnten nicht gerendert werden: ' + ', '.join(broken[:5]))
                    output.parent.mkdir(parents=True, exist_ok=True)
                    page.pdf(path=str(output), format=options.paper, prefer_css_page_size=True, print_background=True,
                        display_header_footer=True, tagged=True, outline=True,
                        header_template=f'<div style="font:8px Arial;color:#666;width:100%;margin:0 16mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(title[:180])}</div>',
                        footer_template='<div style="font:8px Arial;color:#666;width:100%;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                        margin={'top':'18mm', 'bottom':'18mm', 'left':'16mm', 'right':'16mm'})
                finally:
                    browser.close()
        except PlaywrightError as error:
            raise RuntimeError('PDF-Renderer konnte nicht ausgeführt werden. Chromium-Installation prüfen (python -m playwright install chromium). ' + str(error).splitlines()[0]) from error
    return notices
