from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from .model import Agent, HeroFigure, MetadataItem, OntologyDoc, QualityIssue, QualityReport, QualitySection, RestrictionDoc, TermDoc, UsedOntology, Value

DC = DCTERMS
SCHEMA = Namespace("https://schema.org/")
SCHEMA_HTTP = Namespace("http://schema.org/")
VANN = Namespace("http://purl.org/vocab/vann/")
BIBO = Namespace("http://purl.org/ontology/bibo/")
FOAF = Namespace("http://xmlns.com/foaf/0.1#")
VS = Namespace("http://www.w3.org/2003/06/sw-vocab-status/ns#")

BUILTIN_NAMESPACES = (
    str(RDF),
    str(RDFS),
    str(OWL),
    str(XSD),
    str(SKOS),
    str(DC),
    str(SCHEMA),
    str(SCHEMA_HTTP),
    str(BIBO),
    str(FOAF),
    str(VS),
)

CORE_PREFIXES = {"", "owl", "rdf", "rdfs", "xml", "xsd"}
OWL_BACKWARD_COMPATIBILITY = URIRef("http://www.w3.org/2002/07/owl#backwardCompatibility")
OWL_INCOMPATIBLE_WITH = URIRef("http://www.w3.org/2002/07/owl#incompatibleWith")

FORMAT_BY_SUFFIX = {
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".xml": "xml",
    ".nt": "nt",
    ".jsonld": "json-ld",
    ".json": "json-ld",
}

TERM_ANNOTATIONS = (
    (DC.description, "Description"),
    (SKOS.definition, "Definition"),
    (SKOS.scopeNote, "Scope note"),
    (SKOS.example, "Example"),
    (SKOS.historyNote, "History note"),
)

ONTOLOGY_METADATA = (
    (DC.title, "Title"),
    (RDFS.label, "Label"),
    (DC.description, "Description"),
    (RDFS.comment, "Description"),
    (DC.abstract, "Abstract"),
    (VANN.preferredNamespaceUri, "Namespace URI"),
    (VANN.preferredNamespacePrefix, "Prefix"),
    (OWL.versionInfo, "Version info"),
    (OWL.versionIRI, "Version IRI"),
    (VS.status, "Status"),
    (OWL.priorVersion, "Previous version"),
    (OWL_BACKWARD_COMPATIBILITY, "Backward compatibility"),
    (OWL_INCOMPATIBLE_WITH, "Incompatibility"),
    (SKOS.historyNote, "History note"),
    (DC.created, "Creation date"),
    (DC.issued, "Issued date"),
    (DC.modified, "Modification Date"),
    (DC.license, "License"),
    (DC.bibliographicCitation, "Citation"),
    (BIBO.doi, "DOI"),
    (DC.publisher, "Publisher"),
    (DC.source, "Source"),
    (OWL.imports, "Imports"),
    (RDFS.seeAlso, "See also"),
    (SCHEMA.codeRepository, "Code repository"),
    (FOAF.logo, "Logo"),
    (FOAF.depiction, "Diagram"),
)

MANDATORY_METADATA = {
    "License": "To be defined",
    "Creation date": "To be defined",
    "Previous version": "To be defined",
    "Namespace URI": "To be defined",
    "Version IRI": "To be defined",
    "Prefix": "To be defined",
    "Title": "To be defined",
    "Description": "To be defined",
    "Citation": "To be defined",
}

OPTIONAL_METADATA = {
    "Abstract": "To be defined",
    "See also": "To be defined",
    "Status": "To be defined",
    "Backward compatibility": "To be defined",
    "Incompatibility": "To be defined",
    "Modification Date": "To be defined",
    "Issued date": "To be defined",
    "Source": "To be defined",
    "Publisher": "To be defined",
    "DOI": "To be defined",
    "Logo": "To be defined",
    "Diagram": "To be defined",
}


def load_ontology(
    path: Path,
    rdf_format: str | None = None,
    language: str = "en",
    recommendations: bool = False,
    quality_report: bool = False,
    include_custom_annotations: bool = False,
) -> OntologyDoc:
    graph = Graph()
    parse_format = rdf_format or FORMAT_BY_SUFFIX.get(path.suffix.lower())
    if parse_format is None:
        raise ValueError(f"Cannot infer RDF format from suffix: {path.suffix}")
    declared_prefixes = _declared_turtle_prefixes(path) if parse_format == "turtle" else ()
    graph.parse(path, format=parse_format)

    ontology = _first(graph.subjects(RDF.type, OWL.Ontology))
    preferred_namespace = _literal_text(_first(graph.objects(ontology, VANN.preferredNamespaceUri))) if ontology else None
    preferred_prefix = _literal_text(_first(graph.objects(ontology, VANN.preferredNamespacePrefix))) if ontology else None
    namespace = _local_namespace(graph, ontology, preferred_namespace, preferred_prefix, declared_prefixes)

    title = _best_literal(graph, ontology, (RDFS.label, DC.title), language) if ontology else None
    uri = str(ontology) if isinstance(ontology, URIRef) else None
    description = _best_literal(graph, ontology, (RDFS.comment, DC.description), language) if ontology else None
    summary, hero_figures = _split_description(description)
    if ontology and not hero_figures:
        hero_figures = _figures_from_descriptions(graph, ontology)
    version = _best_literal(graph, ontology, (OWL.versionInfo,), language) if ontology else None
    metadata = _metadata(graph, ontology, ONTOLOGY_METADATA, language) if ontology else ()
    creators = _agents(graph, ontology, DC.creator) if ontology else ()
    contributors = _agents(graph, ontology, DC.contributor) if ontology else ()
    if recommendations:
        metadata = _metadata_with_recommendations(metadata)
        creators = creators or (Agent("To be defined", status="mandatory-missing"),)
        contributors = contributors or (Agent("Max Mustermann (to be defined)", status="optional-missing"),)
    prefixes = declared_prefixes or _prefixes(graph)
    classes = _terms(graph, namespace, language, "Class", (OWL.Class, RDFS.Class), include_custom_annotations)
    external_classes = _terms(graph, namespace, language, "Class", (OWL.Class, RDFS.Class), external=True)
    object_properties = _terms(graph, namespace, language, "Object Property", (OWL.ObjectProperty,), include_custom_annotations)
    datatype_properties = _terms(graph, namespace, language, "Datatype Property", (OWL.DatatypeProperty,), include_custom_annotations)
    annotation_properties = _terms(graph, namespace, language, "Annotation Property", (OWL.AnnotationProperty,), include_custom_annotations)
    rdf_properties = _terms(graph, namespace, language, "RDF Property", (RDF.Property,), include_custom_annotations)
    quality = (
        _quality_report(
            metadata,
            creators,
            contributors,
            classes,
            object_properties,
            datatype_properties,
            annotation_properties,
            rdf_properties,
        )
        if quality_report
        else QualityReport()
    )

    return OntologyDoc(
        title=title or uri or path.stem,
        uri=uri,
        description=summary,
        hero_figures=hero_figures,
        version=version,
        preferred_prefix=preferred_prefix,
        preferred_namespace=preferred_namespace,
        metadata=metadata,
        creators=creators,
        contributors=contributors,
        classes=classes,
        external_classes=external_classes,
        object_properties=object_properties,
        datatype_properties=datatype_properties,
        annotation_properties=annotation_properties,
        rdf_properties=rdf_properties,
        prefixes=prefixes,
        used_ontologies=_used_ontologies(graph, ontology, namespace, prefixes, language),
        quality=quality,
    )


def _terms(
    graph: Graph,
    namespace: str | None,
    language: str,
    kind: str,
    rdf_types: tuple[URIRef, ...],
    include_custom_annotations: bool = False,
    *,
    external: bool = False,
) -> tuple[TermDoc, ...]:
    subjects: set[URIRef] = set()
    for rdf_type in rdf_types:
        subjects.update(s for s in graph.subjects(RDF.type, rdf_type) if isinstance(s, URIRef))

    terms = []
    for subject in sorted(subjects, key=str):
        if _is_local_term(subject, namespace) == external:
            continue
        terms.append(
            TermDoc(
                uri=str(subject),
                curie=_curie(graph, subject),
                anchor=_anchor(subject),
                title=_best_literal(graph, subject, (RDFS.label,), language) or _curie(graph, subject),
                kind=kind,
                labels=_values(graph, subject, RDFS.label, language),
                comments=_values(graph, subject, RDFS.comment, language),
                types=tuple(sorted(_curie(graph, t) for t in graph.objects(subject, RDF.type) if isinstance(t, URIRef))),
                parents=_object_values(graph, subject, RDFS.subClassOf, language, include_blank=False),
                domains=_object_values(graph, subject, RDFS.domain, language),
                ranges=_object_values(graph, subject, RDFS.range, language),
                subproperties=_object_values(graph, subject, RDFS.subPropertyOf, language),
                equivalents=_object_values(graph, subject, OWL.equivalentClass, language)
                + _object_values(graph, subject, OWL.equivalentProperty, language),
                inverses=_object_values(graph, subject, OWL.inverseOf, language),
                restrictions=_restrictions(graph, subject, language),
                instances=_instances(graph, subject, language) if kind == "Class" else (),
                other_annotations=_term_annotations(graph, subject, language, include_custom_annotations),
            )
        )
    return tuple(terms)


def _term_annotations(graph: Graph, subject: URIRef, language: str, include_custom_annotations: bool) -> tuple[MetadataItem, ...]:
    annotations = list(_metadata(graph, subject, TERM_ANNOTATIONS, language))
    if include_custom_annotations:
        seen = {item.label for item in annotations}
        for item in _custom_annotations(graph, subject, language):
            if item.label not in seen:
                annotations.append(item)
                seen.add(item.label)
    return tuple(annotations)


def _custom_annotations(graph: Graph, subject: URIRef, language: str) -> tuple[MetadataItem, ...]:
    handled_predicates = {
        RDF.type,
        RDFS.label,
        RDFS.comment,
        RDFS.subClassOf,
        RDFS.domain,
        RDFS.range,
        RDFS.subPropertyOf,
        OWL.equivalentClass,
        OWL.equivalentProperty,
        OWL.inverseOf,
    } | {predicate for predicate, _ in TERM_ANNOTATIONS}
    items = []
    for predicate in sorted({p for p in graph.predicates(subject) if isinstance(p, URIRef)}, key=str):
        if predicate in handled_predicates or not _is_annotation_property(graph, predicate):
            continue
        values = _values(graph, subject, predicate, language)
        if values:
            items.append(MetadataItem(_annotation_label(graph, predicate, language), values))
    return tuple(items)


def _is_annotation_property(graph: Graph, predicate: URIRef) -> bool:
    return (predicate, RDF.type, OWL.AnnotationProperty) in graph


def _annotation_label(graph: Graph, predicate: URIRef, language: str) -> str:
    return _best_literal(graph, predicate, (RDFS.label, SKOS.prefLabel), language) or _curie(graph, predicate)


def _instances(graph: Graph, class_uri: URIRef, language: str) -> tuple[Value, ...]:
    values = []
    for subject in graph.subjects(RDF.type, class_uri):
        if subject == class_uri or not isinstance(subject, (URIRef, BNode)) or _is_schema_term(graph, subject):
            continue
        values.append(_value(graph, subject, language))
    return tuple(sorted((value for value in values if value.text), key=lambda value: value.text.lower()))


def _is_schema_term(graph: Graph, subject: URIRef | BNode) -> bool:
    schema_types = (OWL.Ontology, OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, RDF.Property)
    return any((subject, RDF.type, rdf_type) in graph for rdf_type in schema_types)

def _metadata(
    graph: Graph,
    subject: URIRef | BNode,
    predicates: tuple[tuple[URIRef, str], ...],
    language: str,
) -> tuple[MetadataItem, ...]:
    by_label: dict[str, list[Value]] = {}
    for predicate, label in predicates:
        values = _values(graph, subject, predicate, language)
        if values:
            by_label.setdefault(label, []).extend(values)
    return tuple(MetadataItem(label, tuple(sorted(dict.fromkeys(values), key=lambda v: _value_sort_key(v, language))))
                 for label, values in by_label.items())


def _metadata_with_recommendations(items: tuple[MetadataItem, ...]) -> tuple[MetadataItem, ...]:
    existing = {item.label for item in items}
    enriched = list(items)
    for label, placeholder in MANDATORY_METADATA.items():
        if label not in existing:
            enriched.append(MetadataItem(label, (Value(placeholder),), status="mandatory-missing"))
    for label, placeholder in OPTIONAL_METADATA.items():
        if label not in existing:
            enriched.append(MetadataItem(label, (Value(placeholder),), status="optional-missing"))
    # Missing values belong beside their populated neighbours, not at the end.
    order = {label: index for index, (_, label) in enumerate(ONTOLOGY_METADATA)}
    return tuple(sorted(enriched, key=lambda item: order.get(item.label, len(order))))


def _quality_report(
    metadata: tuple[MetadataItem, ...],
    creators: tuple[Agent, ...],
    contributors: tuple[Agent, ...],
    classes: tuple[TermDoc, ...],
    object_properties: tuple[TermDoc, ...],
    datatype_properties: tuple[TermDoc, ...],
    annotation_properties: tuple[TermDoc, ...],
    rdf_properties: tuple[TermDoc, ...],
) -> QualityReport:
    terms = classes + object_properties + datatype_properties + annotation_properties + rdf_properties
    sections = (
        QualitySection("Metadata", _metadata_issues(metadata, creators, contributors)),
        QualitySection("Missing labels", _missing_term_values(terms, "Labels", "label")),
        QualitySection("Missing comments", _missing_term_values(terms, "Comments", "comment")),
        QualitySection("Missing property domain/range", _property_shape_issues(object_properties + datatype_properties)),
    )
    return QualityReport(tuple(section for section in sections if section.issues))


def _metadata_issues(metadata: tuple[MetadataItem, ...], creators: tuple[Agent, ...], contributors: tuple[Agent, ...]) -> tuple[QualityIssue, ...]:
    existing = {item.label for item in metadata if item.status is None}
    issues = []
    for label in MANDATORY_METADATA:
        if label not in existing:
            issues.append(QualityIssue("Metadata", f"Missing recommended metadata: {label}", "error", "#metadata"))
    for label in OPTIONAL_METADATA:
        if label not in existing:
            issues.append(QualityIssue("Metadata", f"Missing optional metadata: {label}", "warning", "#metadata"))
    if not creators or all(agent.status for agent in creators):
        issues.append(QualityIssue("Metadata", "Missing recommended metadata: Creator", "error", "#agents"))
    if not contributors or all(agent.status for agent in contributors):
        issues.append(QualityIssue("Metadata", "Missing recommended metadata: Contributor", "error", "#agents"))
    return tuple(issues)


def _missing_term_values(terms: tuple[TermDoc, ...], category: str, field_name: str) -> tuple[QualityIssue, ...]:
    issues = []
    for term in terms:
        if not getattr(term, field_name + "s"):
            issues.append(QualityIssue(category, f"{term.curie} has no {field_name}", "warning", f"#{term.anchor}"))
    return tuple(issues)


def _property_shape_issues(properties: tuple[TermDoc, ...]) -> tuple[QualityIssue, ...]:
    issues = []
    for term in properties:
        if not term.domains:
            issues.append(QualityIssue("Property shape", f"{term.curie} has no domain", "warning", f"#{term.anchor}"))
        if not term.ranges:
            issues.append(QualityIssue("Property shape", f"{term.curie} has no range", "warning", f"#{term.anchor}"))
    return tuple(issues)


def _values(graph: Graph, subject: URIRef | BNode, predicate: URIRef, language: str) -> tuple[Value, ...]:
    values = [_value(graph, obj, language) for obj in graph.objects(subject, predicate)]
    return tuple(sorted((value for value in values if value.text), key=lambda v: _value_sort_key(v, language)))


def _object_values(
    graph: Graph,
    subject: URIRef | BNode,
    predicate: URIRef,
    language: str,
    include_blank: bool = True,
) -> tuple[Value, ...]:
    values = []
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, BNode) and not include_blank:
            continue
        values.append(_value(graph, obj, language))
    return tuple(sorted((value for value in values if value.text), key=lambda v: v.text))


def _value_sort_key(value: Value, language: str) -> tuple[int, str, str]:
    if value.lang == language:
        rank = 0
    elif value.lang is None:
        rank = 1
    else:
        rank = 2
    return rank, value.lang or "", value.text.lower()


def _value(graph: Graph, obj: URIRef | BNode | Literal, language: str, seen: frozenset = frozenset()) -> Value:
    if isinstance(obj, Literal):
        return Value(str(obj), obj.language)
    if isinstance(obj, URIRef):
        label = _best_literal(graph, obj, (RDFS.label, SKOS.prefLabel), language)
        return Value(label or _curie(graph, obj), href=str(obj))
    if isinstance(obj, BNode):
        if obj in seen:
            return Value("Cyclic expression")
        seen = seen | {obj}
        union = graph.value(obj, OWL.unionOf)
        if union is not None:
            members = tuple(_value(graph, item, language, seen) for item in Collection(graph, union))
            if members:
                return Value(f"unionOf ({', '.join(member.text for member in members)})", union_members=members)
        expression = _blank_node_expression(graph, obj, language, seen)
        if expression:
            return Value(expression)
        name = _node_name(graph, obj, language)
        return Value(name or "Anonymous node")
    return Value(str(obj))


def _blank_node_expression(graph: Graph, node: BNode, language: str, seen: frozenset = frozenset()) -> str | None:
    for predicate, label in (
        (OWL.unionOf, "unionOf"),
        (OWL.intersectionOf, "intersectionOf"),
        (OWL.oneOf, "oneOf"),
    ):
        list_node = _first(graph.objects(node, predicate))
        if list_node is not None:
            values = [_value(graph, item, language, seen).text for item in Collection(graph, list_node)]
            values = [value for value in values if value]
            if values:
                return f"{label} ({', '.join(values)})"

    complement = _first(graph.objects(node, OWL.complementOf))
    if complement is not None:
        return f"complementOf ({_value(graph, complement, language, seen).text})"

    if (node, RDF.type, RDFS.Datatype) in graph:
        return "rdfs:Datatype"

    return None
def _agents(graph: Graph, ontology: URIRef | BNode, predicate: URIRef) -> tuple[Agent, ...]:
    agents = []
    for node in graph.objects(ontology, predicate):
        name = _node_name(graph, node, "en") or _literal_text(node) or str(node)
        email = _first_text(graph, node, (SCHEMA.email, SCHEMA_HTTP.email))
        identifier = _first_text(graph, node, (SCHEMA.identifier, SCHEMA_HTTP.identifier))
        affiliation_node = _first(graph.objects(node, SCHEMA.memberOf)) or _first(graph.objects(node, SCHEMA_HTTP.memberOf))
        affiliation = _node_name(graph, affiliation_node, "en") if affiliation_node else None
        agents.append(Agent(name=name, email=email, identifier=identifier, affiliation=affiliation))
    return tuple(agents)


def _restrictions(graph: Graph, subject: URIRef, language: str) -> tuple[RestrictionDoc, ...]:
    restrictions = []
    for node in graph.objects(subject, RDFS.subClassOf):
        if not isinstance(node, BNode) or (node, RDF.type, OWL.Restriction) not in graph:
            continue
        on_property = _first(graph.objects(node, OWL.onProperty))
        if not on_property:
            continue
        property_value = _value(graph, on_property, language)
        filler = _restriction_filler(graph, node, language)
        added = False

        for predicate, label in (
            (OWL.cardinality, "exactly"),
            (OWL.minCardinality, "at least"),
            (OWL.maxCardinality, "at most"),
            (OWL.qualifiedCardinality, "exactly"),
            (OWL.minQualifiedCardinality, "at least"),
            (OWL.maxQualifiedCardinality, "at most"),
        ):
            value = _first(graph.objects(node, predicate))
            if value is not None:
                restrictions.append(RestrictionDoc(property=property_value, constraint=label, value=str(value), filler=filler))
                added = True

        for predicate, label in (
            (OWL.someValuesFrom, "some values from"),
            (OWL.allValuesFrom, "all values from"),
            (OWL.hasValue, "has value"),
        ):
            value = _first(graph.objects(node, predicate))
            if value is not None:
                restrictions.append(RestrictionDoc(property=property_value, constraint=label, filler=_value(graph, value, language)))
                added = True

        if filler and not added:
            restrictions.append(RestrictionDoc(property=property_value, constraint="value restriction", filler=filler))
    return tuple(sorted(restrictions, key=lambda item: (item.property.text, item.constraint, item.value or "", item.filler.text if item.filler else "")))


def _restriction_filler(graph: Graph, node: BNode, language: str) -> Value | None:
    filler = _first(graph.objects(node, OWL.onClass)) or _first(graph.objects(node, OWL.onDataRange))
    if filler is None:
        return None
    return _value(graph, filler, language)


def _best_literal(
    graph: Graph,
    subject: URIRef | BNode | None,
    predicates: tuple[URIRef, ...],
    language: str,
) -> str | None:
    if subject is None:
        return None
    literals = []
    for predicate in predicates:
        literals.extend(obj for obj in graph.objects(subject, predicate) if isinstance(obj, Literal))
    return _pick_literal(literals, language)


def _pick_literal(literals: Iterable[Literal], language: str) -> str | None:
    literal_list = list(literals)
    for literal in literal_list:
        if literal.language == language:
            return str(literal)
    for literal in literal_list:
        if literal.language is None:
            return str(literal)
    return str(literal_list[0]) if literal_list else None


def _node_name(graph: Graph, node: URIRef | BNode | Literal | None, language: str) -> str | None:
    if node is None:
        return None
    if isinstance(node, Literal):
        return str(node)
    name = _best_literal(graph, node, (SCHEMA.name, SCHEMA_HTTP.name, RDFS.label), language)
    return name or (_curie(graph, node) if isinstance(node, URIRef) else None)


def _first_text(graph: Graph, subject: URIRef | BNode | Literal, predicates: tuple[URIRef, ...]) -> str | None:
    for predicate in predicates:
        value = _first(graph.objects(subject, predicate))
        if value is not None:
            return _literal_text(value)
    return None


def _literal_text(value: URIRef | BNode | Literal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _first(values: Iterable[object]) -> object | None:
    return next(iter(values), None)


def _local_namespace(
    graph: Graph,
    ontology: URIRef | BNode | None,
    preferred_namespace: str | None,
    preferred_prefix: str | None,
    declared_prefixes: tuple[tuple[str, str], ...],
) -> str | None:
    candidates = []
    if preferred_namespace:
        candidates.append(_ensure_namespace_suffix(preferred_namespace))
    if preferred_prefix:
        candidates.extend(namespace for prefix, namespace in declared_prefixes if prefix == preferred_prefix)
    candidates.append(_namespace_from_ontology(ontology))
    candidates.extend(str(namespace) for prefix, namespace in graph.namespaces() if preferred_prefix and prefix == preferred_prefix)

    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    if not unique_candidates:
        return None

    return max(unique_candidates, key=lambda namespace: _local_term_count(graph, namespace))


def _local_term_count(graph: Graph, namespace: str) -> int:
    rdf_types = (OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, RDF.Property)
    subjects = set()
    for rdf_type in rdf_types:
        subjects.update(subject for subject in graph.subjects(RDF.type, rdf_type) if isinstance(subject, URIRef) and str(subject).startswith(namespace))
    return len(subjects)


def _ensure_namespace_suffix(uri: str) -> str:
    return uri if uri.endswith(("#", "/")) else f"{uri}#"


def _namespace_from_ontology(ontology: URIRef | BNode | None) -> str | None:
    if not isinstance(ontology, URIRef):
        return None
    uri = str(ontology)
    return _ensure_namespace_suffix(uri)


def _is_local_term(subject: URIRef, namespace: str | None) -> bool:
    uri = str(subject)
    if namespace:
        return uri.startswith(namespace)
    return not uri.startswith(BUILTIN_NAMESPACES)


def _curie(graph: Graph, uri: URIRef | BNode | Literal) -> str:
    if not isinstance(uri, URIRef):
        return str(uri)
    try:
        curie = graph.namespace_manager.curie(uri)
        prefix = curie.split(":", 1)[0]
        if re.fullmatch(r"ns\d+", prefix):
            return str(uri)
        return curie
    except Exception:
        return str(uri)


def _anchor(uri: URIRef) -> str:
    text = str(uri)
    if "#" in text:
        candidate = text.rsplit("#", 1)[1]
    else:
        candidate = text.rstrip("/").rsplit("/", 1)[-1]
    candidate = candidate or text
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", candidate).strip("-")


def _prefixes(graph: Graph) -> tuple[tuple[str, str], ...]:
    used_uris = tuple(_used_uri_strings(graph))
    prefixes = []
    for prefix, namespace in graph.namespaces():
        namespace_text = str(namespace)
        if any(uri.startswith(namespace_text) for uri in used_uris):
            prefixes.append((prefix, namespace_text))
    return tuple(sorted(prefixes, key=lambda item: (item[0] != "", item[0])))


def _used_uri_strings(graph: Graph) -> set[str]:
    uris = set()
    for subject, predicate, obj in graph:
        for term in (subject, predicate, obj):
            if isinstance(term, URIRef):
                uris.add(str(term))
    return uris


def _declared_turtle_prefixes(path: Path) -> tuple[tuple[str, str], ...]:
    prefix_pattern = re.compile(r"^\s*@prefix\s+([^:\s]*)\s*:\s*<([^>]+)>", re.IGNORECASE)
    sparql_prefix_pattern = re.compile(r"^\s*prefix\s+([^:\s]*)\s*:\s*<([^>]+)>", re.IGNORECASE)
    prefixes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = prefix_pattern.match(line) or sparql_prefix_pattern.match(line)
        if match:
            prefixes.append((match.group(1), match.group(2)))
    return tuple(prefixes)


def _used_ontologies(
    graph: Graph,
    ontology: URIRef | BNode | None,
    local_namespace: str | None,
    prefixes: tuple[tuple[str, str], ...],
    language: str,
) -> tuple[UsedOntology, ...]:
    used = []
    seen = set()

    if ontology is not None:
        for imported in graph.objects(ontology, OWL.imports):
            if isinstance(imported, URIRef):
                uri = str(imported)
                seen.add(uri)
                used.append(UsedOntology(_best_literal(graph, imported, (RDFS.label, SKOS.prefLabel), language) or _compact_label(uri), uri, "Imported ontology"))

    for prefix, namespace in prefixes:
        if prefix in CORE_PREFIXES:
            continue
        if local_namespace and namespace == local_namespace:
            continue
        if namespace in seen:
            continue
        if _namespace_is_used(graph, namespace):
            seen.add(namespace)
            used.append(UsedOntology(prefix or _compact_label(namespace), namespace, "Referenced namespace"))
    return tuple(used)


def _namespace_is_used(graph: Graph, namespace: str) -> bool:
    for uri in _used_uri_strings(graph):
        if uri.startswith(namespace):
            return True
    return False


def _compact_label(uri: str) -> str:
    return uri.rstrip("#/").rsplit("/", 1)[-1] or uri


def _split_description(description: str | None) -> tuple[str | None, tuple[HeroFigure, ...]]:
    if not description:
        return None, ()

    figures = []
    summary_lines = []
    current_heading: str | None = None
    image_pattern = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>\S+)(?:\s+\"[^\"]*\")?\)")

    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line:
            if summary_lines and summary_lines[-1] != "":
                summary_lines.append("")
            continue

        if line.startswith("## "):
            current_heading = line[3:].strip()
            continue

        image_match = image_pattern.search(line)
        if image_match:
            alt = image_match.group("alt").strip()
            src = image_match.group("src").strip()
            figures.append(HeroFigure(title=current_heading or alt or "Ontology figure", src=src, alt=alt or current_heading or "Ontology figure"))
            current_heading = None
            continue

        if current_heading:
            summary_lines.append(current_heading)
            current_heading = None
        summary_lines.append(_plain_markdown(line))

    summary = "\n".join(summary_lines).strip()
    summary = re.sub(r"\n{3,}", "\n\n", summary)
    return summary or None, tuple(figures)


def _figures_from_descriptions(graph: Graph, ontology: URIRef | BNode) -> tuple[HeroFigure, ...]:
    for predicate in (RDFS.comment, DC.description):
        for value in graph.objects(ontology, predicate):
            if isinstance(value, Literal):
                _, figures = _split_description(str(value))
                if figures:
                    return figures
    return ()


def _plain_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "")
    return text








