from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from .abox_model import ABoxDoc, Instance, LiteralValue, Relation, ResourceRef

SCHEMA_TYPES = {
    OWL.Class, RDFS.Class, RDF.Property, OWL.ObjectProperty,
    OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.Ontology,
    OWL.Restriction, RDFS.Datatype, OWL.AllDisjointClasses,
    OWL.AllDisjointProperties, OWL.Axiom,
    OWL.FunctionalProperty, OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty, OWL.SymmetricProperty, OWL.AsymmetricProperty,
    OWL.ReflexiveProperty, OWL.IrreflexiveProperty,
}
SCHEMA_PREDICATES = {
    RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range,
    OWL.equivalentClass, OWL.equivalentProperty, OWL.unionOf,
    OWL.intersectionOf, OWL.onProperty, OWL.imports,
}


def load_abox(path: Path, rdf_format: str | None = None, language: str = "de") -> ABoxDoc:
    formats = {".ttl": "turtle", ".rdf": "xml", ".owl": "xml", ".nt": "nt", ".jsonld": "json-ld"}
    graph = Graph(bind_namespaces="none")
    graph.parse(path, format=rdf_format or formats.get(path.suffix.lower()))
    subjects = set(graph.subjects())
    schema = {s for s, _, t in graph.triples((None, RDF.type, None)) if t in SCHEMA_TYPES}
    schema.update(s for s, p, _ in graph if p in SCHEMA_PREDICATES)
    # Preserve OWL punning: a schema resource can also have a domain instance type.
    domain_typed = {s for s, _, t in graph.triples((None, RDF.type, None))
                    if t not in SCHEMA_TYPES and t != RDFS.Resource}
    data_subjects = subjects - schema | domain_typed
    data_subjects = {s for s in data_subjects if isinstance(s, (URIRef, BNode))}

    def key(node):
        return "_:" + str(node) if isinstance(node, BNode) else str(node)

    def curie(node):
        return node.n3(graph.namespace_manager) if isinstance(node, URIRef) else key(node)

    def language_rank(value):
        lang = (value.language or "").lower()
        preferred = language.lower()
        return (0 if lang == preferred else 1 if lang.split("-")[0] == preferred.split("-")[0]
                else 2 if not lang else 3 if lang == "en" else 4, lang, str(value))

    def label(node):
        for predicate in (SKOS.prefLabel, RDFS.label, DCTERMS.title):
            values = sorted((v for v in graph.objects(node, predicate) if isinstance(v, Literal)), key=language_rank)
            if values:
                return str(values[0])
        # Domain vocabularies often name instances via org:name, fullName, etc.
        names = [v for p, v in graph.predicate_objects(node) if isinstance(v, Literal)
                 and str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1] in {"name", "fullName", "itemName", "locationName"}]
        return str(sorted(names, key=language_rank)[0]) if names else curie(node)

    def ref(node):
        return ResourceRef(key(node), label(node), curie(node))

    relations = []
    resources = set(data_subjects)
    for subject in sorted(data_subjects, key=key):
        for predicate, obj in sorted(graph.predicate_objects(subject), key=lambda pair: tuple(map(str, pair))):
            if predicate == RDF.type or predicate in SCHEMA_PREDICATES:
                continue
            if isinstance(obj, (URIRef, BNode)):
                resources.add(obj)
                relations.append(Relation(key(subject), ref(predicate), key(obj)))
    instances = []
    for node in sorted(resources, key=key):
        types = tuple(ref(t) for t in sorted(set(graph.objects(node, RDF.type)), key=key)
                      if t not in SCHEMA_TYPES and t != OWL.NamedIndividual)
        values = tuple(LiteralValue(ref(p), str(v), v.language, str(v.datatype) if v.datatype else None)
                       for p, v in sorted(graph.predicate_objects(node), key=lambda pair: (str(pair[0]), language_rank(pair[1]) if isinstance(pair[1], Literal) else (5, "", str(pair[1]))))
                       if isinstance(v, Literal))
        instances.append(Instance(ref(node), types, values, node not in data_subjects, isinstance(node, BNode)))
    return ABoxDoc(path.stem, tuple(instances), tuple(relations), len(graph), len(schema - domain_typed))
