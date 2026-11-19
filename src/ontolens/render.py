from __future__ import annotations

import shutil
import re
import warnings
import colorsys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from .assets import AssetBundle, inline_script
from .content import combine_documentation, read_editorial_source, render_editorial_content
from .model import DownloadLink, MetadataItem, OntologyDoc
from .parser import load_ontology


def render_html(
    doc: OntologyDoc,
    quality_report: bool = False,
    content=None,
    language: str = "en",
    theme: str = "light",
    show_missing_endpoints: bool = False,
    include_external_classes: bool = False,
) -> str:
    if theme not in {"light", "dark"}:
        raise ValueError("theme must be light or dark")
    env = Environment(
        loader=PackageLoader("ontolens", "templates"),
        autoescape=select_autoescape(("html", "xml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("documentation.html.j2")
    visualization = _visualization_data(doc, show_missing_endpoints, language, include_external_classes)
    html = template.render(
        doc=doc,
        json_ld=_json_ld(doc),
        visualization=visualization,
        quality_report=quality_report,
        has_markdown=content is not None,
        page_title=content.title if content and content.title else doc.title,
        page_description=content.description if content and content.description else doc.description,
        page_language=content.language if content and content.language else language,
        theme=theme,
        inline_script=inline_script,
    )
    if content:
        return combine_documentation(html, content, doc, language=content.language or language)
    return html


def generate(
    input_path: Path,
    output_path: Path,
    rdf_format: str | None = None,
    language: str | None = None,
    content_path: Path | None = None,
    recommendations: bool = False,
    quality_report: bool = False,
    include_custom_annotations: bool = False,
    generated_at: datetime | None = None,
    skip_missing_images: bool = False,
    notices: list[str] | None = None,
    theme: str = "light",
    show_missing_endpoints: bool = False,
    include_external_classes: bool = False,
    _final_path: bool = False,
) -> Path:
    if theme == 'both':
        bundle = _timestamped_output_path(output_path, generated_at).parent
        for variant in ('light', 'dark'):
            generate(input_path, bundle / variant / output_path.name, rdf_format=rdf_format,
                     language=language, content_path=content_path, recommendations=recommendations,
                     quality_report=quality_report, include_custom_annotations=include_custom_annotations,
                     generated_at=generated_at, skip_missing_images=skip_missing_images,
                     notices=notices if variant == 'light' else None, theme=variant,
                     show_missing_endpoints=show_missing_endpoints, include_external_classes=include_external_classes, _final_path=True)
        return bundle / 'light' / output_path.name
    editorial_source = read_editorial_source(content_path) if content_path else None
    resolved_language = language or (editorial_source.language if editorial_source else None) or "en"
    doc = load_ontology(input_path, rdf_format=rdf_format, language=resolved_language, recommendations=recommendations, quality_report=quality_report, include_custom_annotations=include_custom_annotations)
    if notices is not None:
        notices.extend(issue.message for section in doc.quality.sections for issue in section.issues)
        if skip_missing_images:
            notices.extend(f"Abbildung übersprungen: {figure.src}" for figure in doc.hero_figures
                           if not _is_external(figure.src) and not (input_path.parent / figure.src).is_file())
    if not _final_path:
        output_path = _timestamped_output_path(output_path, generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    assets = AssetBundle(output_path.parent)
    doc = _with_unique_term_anchors(doc)
    doc = _bundle_hero_assets(doc, input_path.parent, assets, skip_missing_images)
    doc = _with_default_download(doc, input_path, output_path.parent)
    content = None
    if editorial_source:
        content = render_editorial_content(
            editorial_source,
            doc,
            assets,
            quality_report=quality_report,
        )
    output_path.write_text(
        render_html(doc, quality_report=quality_report, content=content, language=resolved_language, theme=theme, show_missing_endpoints=show_missing_endpoints, include_external_classes=include_external_classes),
        encoding="utf-8",
    )
    return output_path


def _timestamped_output_path(output_path: Path, generated_at: datetime | None = None) -> Path:
    timestamp = (generated_at or datetime.now()).strftime("%Y-%m-%dT%H-%M-%S")
    bundle_name = f"{timestamp}_{output_path.stem}"
    return output_path.parent / bundle_name / output_path.name


def _with_unique_term_anchors(doc: OntologyDoc) -> OntologyDoc:
    seen: set[str] = set()
    updates = {}
    for field_name in (
        "classes",
        "object_properties",
        "datatype_properties",
        "annotation_properties",
        "rdf_properties",
    ):
        terms = []
        for term in getattr(doc, field_name):
            anchor = term.anchor or "term"
            if anchor in seen:
                suffix = _visual_kind(term.kind)
                candidate = f"{anchor}-{suffix}"
                counter = 2
                while candidate in seen:
                    candidate = f"{anchor}-{suffix}-{counter}"
                    counter += 1
                anchor = candidate
                term = replace(term, anchor=anchor)
            seen.add(anchor)
            terms.append(term)
        updates[field_name] = tuple(terms)
    return replace(doc, **updates)


def _with_default_download(doc: OntologyDoc, input_path: Path, output_dir: Path) -> OntologyDoc:
    downloads = output_dir / "downloads"
    downloads.mkdir(exist_ok=True)
    shutil.copy2(input_path, downloads / input_path.name)
    href = "downloads/" + quote(input_path.name)
    suffix = input_path.suffix.lower()
    formats = {
        ".ttl": ("Turtle source", "text/turtle"),
        ".rdf": ("RDF/XML source", "application/rdf+xml"),
        ".owl": ("RDF/XML source", "application/rdf+xml"),
        ".nt": ("N-Triples source", "application/n-triples"),
        ".jsonld": ("JSON-LD source", "application/ld+json"),
    }
    label, media_type = formats.get(suffix, ("Ontology source", None))
    return replace(doc, downloads=(DownloadLink(label, href, suffix.lstrip(".") or "source", media_type),) + doc.downloads)


def _bundle_hero_assets(doc: OntologyDoc, source_dir: Path, assets: AssetBundle, skip_missing_images: bool = False) -> OntologyDoc:
    if not doc.hero_figures:
        return doc
    figures = []
    for figure in doc.hero_figures:
        src = figure.src
        if not _is_external(src):
            source = Path(src) if Path(src).is_absolute() else source_dir / src
            if skip_missing_images and not source.is_file():
                warnings.warn(f"Skipping missing ontology image: {source}", stacklevel=2)
                continue
            src = assets.copy_image(source)
        figures.append(replace(figure, src=src))
    return replace(doc, hero_figures=tuple(figures))


def _is_external(src: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src)) and not Path(src).is_absolute()


def _json_ld(doc: OntologyDoc) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": doc.title,
        "url": doc.uri,
        "version": doc.version,
        "description": doc.description,
        "license": _first_metadata_href_or_text(doc.metadata, "License"),
        "dateCreated": _first_metadata_text(doc.metadata, "Creation date"),
        "datePublished": _first_metadata_text(doc.metadata, "Issued date"),
        "dateModified": _first_metadata_text(doc.metadata, "Modification Date"),
        "author": [_agent_json(agent) for agent in doc.creators if not agent.status],
        "contributor": [_agent_json(agent) for agent in doc.contributors if not agent.status],
        "publisher": _first_metadata_text(doc.metadata, "Publisher"),
        "citation": _first_metadata_text(doc.metadata, "Citation"),
        "codeRepository": _first_metadata_href_or_text(doc.metadata, "Code repository"),
        "about": {
            "@type": "DefinedTermSet",
            "name": doc.title,
            "url": doc.uri,
            "termSet": doc.preferred_namespace,
        },
        "isBasedOn": [_used_ontology_json(item) for item in doc.used_ontologies if item.relation == "Imported ontology"],
        "mentions": [_used_ontology_json(item) for item in doc.used_ontologies if item.relation != "Imported ontology"],
        "encoding": [_download_json(download) for download in doc.downloads],
    }
    return _drop_empty(data)


def _agent_json(agent) -> dict:
    data = {"@type": "Person", "name": agent.name, "email": agent.email, "identifier": agent.identifier, "affiliation": agent.affiliation}
    return _drop_empty(data)


def _download_json(download: DownloadLink) -> dict:
    return _drop_empty({"@type": "MediaObject", "name": download.label, "contentUrl": download.href, "encodingFormat": download.media_type or download.format})


def _used_ontology_json(item) -> dict:
    return _drop_empty({"@type": "CreativeWork", "name": item.label, "url": item.uri})


def _first_metadata_text(items: tuple[MetadataItem, ...], label: str) -> str | None:
    for item in items:
        if item.label == label and item.values and not item.status:
            return item.values[0].text.strip()
    return None


def _first_metadata_href_or_text(items: tuple[MetadataItem, ...], label: str) -> str | None:
    for item in items:
        if item.label == label and item.values and not item.status:
            return item.values[0].href or item.values[0].text.strip()
    return None


def _drop_empty(value):
    if isinstance(value, dict):
        return {key: _drop_empty(item) for key, item in value.items() if item not in (None, "", (), [])}
    if isinstance(value, list):
        return [_drop_empty(item) for item in value if item not in (None, "", (), [])]
    return value


def _visualization_data(doc: OntologyDoc, show_missing_endpoints: bool = False, language: str = "en", include_external_classes: bool = False) -> dict:
    external_classes = doc.external_classes if include_external_classes else ()
    class_terms = [*doc.classes, *external_classes]
    object_property_terms = list(doc.object_properties)
    datatype_property_terms = list(doc.datatype_properties)
    class_by_uri = {term.uri: term for term in class_terms}
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()

    for term in doc.classes:
        _append_node(nodes, seen_nodes, term.uri, term.title, term.curie, "class", f"#{term.anchor}")
    for term in external_classes:
        _append_node(nodes, seen_nodes, term.uri, term.title, term.curie, "external-class", term.uri)

    for term in class_terms:
        for parent in term.parents:
            if parent.href in class_by_uri:
                _append_edge(edges, seen_edges, term.uri, parent.href, "subClassOf")
        for equivalent in term.equivalents:
            if not equivalent.href or equivalent.href == term.uri:
                continue
            if equivalent.href not in class_by_uri:
                _append_node(nodes, seen_nodes, equivalent.href, equivalent.text, equivalent.text, "external-class")
            if equivalent.href in seen_nodes:
                _append_equivalent_class_edges(edges, seen_edges, term.uri, equivalent.href)

    for term in object_property_terms:
        _append_property_edges(nodes, edges, seen_nodes, seen_edges, class_by_uri, term, show_missing_endpoints, language)
    _append_datatype_property_edges(nodes, edges, seen_nodes, seen_edges, class_by_uri, datatype_property_terms)

    legend = _graph_ontology_colors(doc, nodes)
    return {"elements": {"nodes": nodes, "edges": edges}, "ontologies": legend, "counts": {"nodes": len(nodes), "edges": len(edges)}}


def _graph_ontology_colors(doc, nodes):
    def namespace(uri):
        if '#' in uri:
            return uri.rsplit('#', 1)[0] + '#'
        return uri.rsplit('/', 1)[0] + '/'

    primary = doc.preferred_namespace or (namespace(doc.classes[0].uri) if doc.classes else (doc.uri or ''))
    prefixes = {uri: prefix for prefix, uri in doc.prefixes}
    for node in nodes:
        data = node['data']
        if data['kind'] == 'literal':
            data.update(color='#ffffff', border='#155c63', ontology='')
            continue
        uri = data['id'].split(':', 1)[1] if data['kind'] == 'missing-endpoint' else data['id']
        data['ontology'] = namespace(uri) if uri.startswith(('https://', 'http://', 'urn:')) else primary
    namespaces = sorted({n['data']['ontology'] for n in nodes if n['data']['ontology']})
    palette = ['#3c648c', '#65763c', '#7b527e', '#956b30', '#9b515c', '#377d6c', '#645f98', '#8a5f46']
    colors = {primary: '#155c63'}
    for index, uri in enumerate(ns for ns in namespaces if ns != primary):
        rgb = colorsys.hls_to_rgb((index * .61803398875) % 1, .36, .32)
        colors[uri] = palette[index] if index < len(palette) else '#%02x%02x%02x' % tuple(round(c * 255) for c in rgb)
    legend = []
    for uri in sorted(namespaces, key=lambda ns: (ns != primary, ns)):
        color = colors[uri]
        border = '#' + ''.join(f'{int(int(color[i:i+2], 16) * .72):02x}' for i in (1, 3, 5))
        label = prefixes.get(uri) or (doc.preferred_prefix if uri == primary else None) or uri
        legend.append({'uri': uri, 'label': label, 'color': color, 'border': border})
        for node in nodes:
            if node['data']['ontology'] == uri:
                node['data'].update(color=color, border=border)
    return legend


def _visual_kind(kind: str) -> str:
    return kind.lower().replace(" ", "-")


def _edge(source: str, target: str | None, label: str) -> dict:
    return {"data": {"id": f"{label}:{source}->{target}", "source": source, "target": target, "label": label, "edgeKind": label}}


def _append_edge(
    edges: list[dict],
    seen_edges: set[str],
    source: str,
    target: str | None,
    label: str,
    edge_kind: str | None = None,
    href: str | None = None,
    offset: int | None = None,
    arrow: str | None = None,
    properties: list[dict[str, str]] | None = None,
) -> None:
    edge = _edge(source, target, label)
    if edge_kind:
        edge["data"]["edgeKind"] = edge_kind
    if edge["data"]["edgeKind"] == "subClassOf":
        edge["data"]["label"] = ""
    if href:
        edge["data"]["href"] = href
    if offset is not None:
        edge["data"]["offset"] = offset
    if arrow:
        edge["data"]["arrow"] = arrow
    if properties:
        edge["data"]["properties"] = properties
    edge_id = edge["data"]["id"]
    if edge_id in seen_edges:
        return
    seen_edges.add(edge_id)
    edges.append(edge)


def _append_equivalent_class_edges(edges: list[dict], seen_edges: set[str], source: str, target: str) -> None:
    pair_key = "equivalentClass:" + "<->".join(sorted((source, target)))
    if pair_key in seen_edges:
        return
    seen_edges.add(pair_key)
    edges.append({"data": {"id": f"{pair_key}:a", "source": source, "target": target, "label": "equivalentClass", "edgeKind": "equivalent-class", "offset": 5, "arrow": "none"}})
    edges.append({"data": {"id": f"{pair_key}:b", "source": source, "target": target, "label": "", "edgeKind": "equivalent-class-parallel", "offset": -5, "arrow": "none"}})


def _append_node(nodes: list[dict], seen_nodes: set[str], node_id: str, label: str, curie: str, kind: str, href: str | None = None) -> None:
    if node_id in seen_nodes:
        return
    seen_nodes.add(node_id)
    nodes.append({"data": {"id": node_id, "label": label, "curie": curie, "kind": kind, "href": href}})


def _union_endpoints(values):
    # Expand alternatives only; intersections and restrictions are not unions.
    for value in values:
        if value.union_members:
            yield from _union_endpoints(value.union_members)
        else:
            yield value


def _append_property_edges(
    nodes: list[dict],
    edges: list[dict],
    seen_nodes: set[str],
    seen_edges: set[str],
    class_by_uri: dict[str, object],
    term,
    show_missing_endpoints: bool = False,
    language: str = "en",
) -> bool:
    kind = _visual_kind(term.kind)
    domain_values = tuple(_union_endpoints(term.domains))
    range_values = tuple(_union_endpoints(term.ranges))
    domains = [value.href for value in domain_values if value.href in class_by_uri]
    ranges = [value.href for value in range_values if value.href in class_by_uri]

    if kind == "object-property" and term.domains and term.ranges:
        # Referenced classes need not be declared in the input ontology.
        for value in (*domain_values, *range_values):
            if value.href and value.href not in class_by_uri:
                _append_node(nodes, seen_nodes, value.href, value.text, value.text, "external-class", value.href)
        domains = [value.href for value in domain_values if value.href]
        ranges = [value.href for value in range_values if value.href]

    # Only genuinely absent declarations get placeholders, never unresolved IRIs.
    if show_missing_endpoints and kind == "object-property" and bool(term.domains) != bool(term.ranges):
        missing = "range" if term.domains else "domain"
        placeholder = f"missing-{missing}:{term.uri}"
        _append_node(nodes, seen_nodes, placeholder, "", "", "missing-endpoint", f"#{term.anchor}")
        endpoints = []
        for index, value in enumerate(domain_values or range_values):
            identity = value.href or f"expression:{term.uri}:{index}"
            if identity not in class_by_uri:
                _append_node(nodes, seen_nodes, identity, value.text, value.text, "external-class")
            endpoints.append(identity)
        domains, ranges = (endpoints, [placeholder]) if missing == "range" else ([placeholder], endpoints)

    if kind == "object-property" and domains and ranges:
        for domain in domains:
            for range_value in ranges:
                _append_edge(edges, seen_edges, domain, range_value, term.title, "object-property", f"#{term.anchor}")
        return True

    return False


def _append_datatype_property_edges(
    nodes: list[dict],
    edges: list[dict],
    seen_nodes: set[str],
    seen_edges: set[str],
    class_by_uri: dict[str, object],
    terms: list,
) -> None:
    groups: dict[tuple[str, str], dict] = {}
    for term in terms:
        domain_values = tuple(_union_endpoints(term.domains))
        for value in domain_values:
            if value.href and value.href not in class_by_uri:
                _append_node(nodes, seen_nodes, value.href, value.text, value.text, "external-class", value.href)
        domains = list(dict.fromkeys(value.href for value in domain_values if value.href))
        ranges = list(term.ranges) or []
        if not ranges:
            ranges = [None]
        for domain in domains:
            for range_value in ranges:
                literal_id, literal_label = _literal_target(term, range_value)
                key = (domain, literal_id)
                group = groups.setdefault(key, {"domain": domain, "literal_id": literal_id, "literal_label": literal_label, "terms": []})
                group["terms"].append(term)

    for group in groups.values():
        terms_for_group = sorted(group["terms"], key=lambda item: item.title.lower())
        _append_node(nodes, seen_nodes, group["literal_id"], group["literal_label"], group["literal_label"], "literal")
        property_count = len(terms_for_group)
        label = f"{property_count} datatype {'property' if property_count == 1 else 'properties'}"
        properties = [
            {"title": term.title, "curie": term.curie, "href": f"#{term.anchor}"}
            for term in terms_for_group
        ]
        _append_edge(
            edges,
            seen_edges,
            group["domain"],
            group["literal_id"],
            label,
            "datatype-property",
            properties=properties,
        )


def _literal_target(term, range_value) -> tuple[str, str]:
    if range_value is None:
        return "literal:Literal", "Literal"
    if range_value.href:
        return range_value.href, range_value.text
    return f"literal:{range_value.text}", range_value.text
