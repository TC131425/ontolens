from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
CCTS_NS = "{urn:un:unece:uncefact:documentation:2}"
BASE_IRI = "https://w3id.org/delivery-note-xsd"
BASE = BASE_IRI + "#"
PREFIX_FILES = {
    "cbc": "UBL-CommonBasicComponents-2.5.xsd",
    "cac": "UBL-CommonAggregateComponents-2.5.xsd",
    "ext": "UBL-CommonExtensionComponents-2.5.xsd",
}


@dataclass(frozen=True)
class ComponentDoc:
    component_type: str = ""
    dictionary_entry_name: str = ""
    definition: str = ""
    object_class: str = ""
    property_term: str = ""
    representation_term: str = ""
    data_type: str = ""


@dataclass
class ElementDecl:
    prefix: str
    name: str
    type_name: str
    doc: ComponentDoc = field(default_factory=ComponentDoc)


@dataclass
class TypeDecl:
    name: str
    prefix: str
    doc: ComponentDoc
    element: ET.Element


@dataclass
class PropertyDecl:
    name: str
    kind: str
    domain: str
    range_name: str
    label: str
    comment: str
    source_ref: str
    min_occurs: str
    max_occurs: str
    component_type: str
    xsd_type: str


def main() -> int:
    global BASE_IRI, BASE
    parser = argparse.ArgumentParser(description="Generate an OWL ontology from the UBL DeliveryNote XSD.")
    parser.add_argument("xsd", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-depth", type=int, default=None, help="Optional recursion depth for aggregate component types.")
    parser.add_argument("--exclude-ext", action="store_true", help="Skip ext:* elements and do not load the UBL extension schema.")
    parser.add_argument("--base-iri", default=BASE_IRI, help="Ontology base IRI for this generated variant.")
    args = parser.parse_args()

    BASE_IRI = args.base_iri.rstrip("#/")
    BASE = BASE_IRI + "#"

    model = XsdModel(args.xsd, include_ext=not args.exclude_ext)
    classes, properties = model.extract_delivery_note_model(args.max_depth)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_turtle(args.xsd, classes, properties), encoding="utf-8")
    print(f"Generated {args.output} with {len(classes)} classes and {len(properties)} properties")
    return 0


class XsdModel:
    def __init__(self, main_xsd: Path, include_ext: bool = True) -> None:
        self.main_xsd = main_xsd
        self.include_ext = include_ext
        self.base_dir = main_xsd.parent
        self.roots: dict[str, ET.Element] = {}
        self.elements: dict[tuple[str, str], ElementDecl] = {}
        self.types: dict[str, TypeDecl] = {}
        self.missing_imports: set[str] = set()
        self.load_schema("main", main_xsd)
        for prefix, filename in PREFIX_FILES.items():
            if prefix == "ext" and not self.include_ext:
                continue
            candidate = self.base_dir / filename
            if candidate.exists():
                self.load_schema(prefix, candidate)
            else:
                self.missing_imports.add(prefix)

    def load_schema(self, prefix: str, path: Path) -> None:
        root = ET.parse(path).getroot()
        self.roots[prefix] = root
        for element in root.findall(XSD_NS + "element"):
            name = element.get("name")
            type_name = strip_prefix(element.get("type", ""))
            if name and type_name:
                self.elements[(prefix, name)] = ElementDecl(prefix, name, type_name, component_doc(element))
        for complex_type in root.findall(XSD_NS + "complexType"):
            name = complex_type.get("name")
            if name:
                self.types[name] = TypeDecl(name, prefix, component_doc(complex_type), complex_type)

    def extract_delivery_note_model(self, max_depth: int | None) -> tuple[dict[str, TypeDecl], list[PropertyDecl]]:
        delivery_note_type = "DeliveryNoteType"
        selected_types: dict[str, TypeDecl] = {}
        properties: list[PropertyDecl] = []
        queue: deque[tuple[str, int]] = deque([(delivery_note_type, 0)])
        queued = {delivery_note_type}

        while queue:
            type_name, depth = queue.popleft()
            type_decl = self.types.get(type_name)
            if not type_decl:
                continue
            selected_types[type_name] = type_decl
            for child in sequence_elements(type_decl.element):
                prop = self.property_for(type_decl, child)
                if prop:
                    properties.append(prop)
                ref_prefix, ref_name = split_ref(child.get("ref", ""))
                if ref_prefix != "cac":
                    continue
                target_type = self.elements.get((ref_prefix, ref_name), ElementDecl(ref_prefix, ref_name, "")).type_name
                if target_type and target_type not in queued and (max_depth is None or depth < max_depth):
                    queued.add(target_type)
                    queue.append((target_type, depth + 1))

        return selected_types, properties

    def property_for(self, type_decl: TypeDecl, child: ET.Element) -> PropertyDecl | None:
        ref_prefix, ref_name = split_ref(child.get("ref", ""))
        if not ref_prefix or not ref_name:
            return None
        if ref_prefix == "ext" and not self.include_ext:
            return None
        domain = class_name(type_decl.name)
        occurrence_doc = component_doc(child)
        global_decl = self.elements.get((ref_prefix, ref_name), ElementDecl(ref_prefix, ref_name, ""))
        doc = occurrence_doc if any(vars(occurrence_doc).values()) else global_decl.doc
        label = doc.property_term or split_label(ref_name)
        comment = doc.definition or global_decl.doc.definition or f"UBL element {ref_prefix}:{ref_name}."
        min_occurs = child.get("minOccurs", "1")
        max_occurs = child.get("maxOccurs", "1")
        xsd_type = global_decl.type_name

        if ref_prefix == "cac":
            target = class_name(global_decl.type_name or ref_name)
            prop_name = property_name("has" + domain + ref_name)
            kind = "object"
        elif ref_prefix == "ext":
            target = class_name(global_decl.type_name or ref_name)
            prop_name = property_name("has" + domain + ref_name)
            kind = "object"
        else:
            target = datatype_for(ref_name, doc, global_decl.type_name)
            prop_name = property_name(domain + ref_name)
            kind = "data"

        return PropertyDecl(
            name=prop_name,
            kind=kind,
            domain=domain,
            range_name=target,
            label=label,
            comment=comment,
            source_ref=f"{class_name(type_decl.name)}/{ref_prefix}:{ref_name}",
            min_occurs=min_occurs,
            max_occurs=max_occurs,
            component_type=doc.component_type,
            xsd_type=xsd_type,
        )


def render_turtle(source: Path, classes: dict[str, TypeDecl], properties: list[PropertyDecl]) -> str:
    lines = [
        f"@prefix : <{BASE}> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix vann: <http://purl.org/vocab/vann/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"<{BASE_IRI}>",
        "  a owl:Ontology ;",
        '  dcterms:title "Delivery Note Ontology from UBL XSD"@en, "Lieferschein-Ontologie aus UBL-XSD"@de ;',
        f'  dcterms:created "{date.today().isoformat()}"^^xsd:date ;',
        f"  dcterms:source {ttl_string(source.name)} ;",
        '  vann:preferredNamespacePrefix "dnxsd" ;',
        f"  vann:preferredNamespaceUri <{BASE}> ;",
        f"  owl:versionIRI <{BASE_IRI}/0.1.0> ;",
        '  owl:versionInfo "0.1.0" ;',
        '  rdfs:comment "Generated from the UBL DeliveryNote 2.5 XSD. Classes correspond to reachable UBL aggregate component types; properties correspond to XSD element references and carry occurrence restrictions from minOccurs/maxOccurs."@en .',
        "",
    ]
    add_annotation_property(lines, "xsdPath", "XSD path", "Source XSD component path for the generated term.")
    add_annotation_property(lines, "xsdMinOccurs", "XSD minOccurs", "Minimum occurrence from the source XSD.")
    add_annotation_property(lines, "xsdMaxOccurs", "XSD maxOccurs", "Maximum occurrence from the source XSD.")
    add_annotation_property(lines, "xsdType", "XSD type", "Source XSD type name.")
    add_annotation_property(lines, "xsdComponentType", "XSD CCTS component type", "CCTS component type from the source XSD documentation.")

    by_domain: dict[str, list[PropertyDecl]] = {}
    for prop in properties:
        by_domain.setdefault(prop.domain, []).append(prop)

    declared_class_names = {class_name(type_name) for type_name in classes}
    external_class_names = sorted({prop.range_name for prop in properties if prop.kind == "object" and prop.range_name not in declared_class_names})
    for external_class_name in external_class_names:
        lines.append(f":{external_class_name}")
        add_statements(lines, [
            "a owl:Class",
            f"rdfs:isDefinedBy <{BASE_IRI}>",
            f"rdfs:label {ttl_string(split_label(external_class_name), 'en')}",
            f"rdfs:comment {ttl_string('External XSD aggregate referenced by the DeliveryNote schema but not expanded from an available local import.', 'en')}",
        ])
        lines.append("")

    for type_name in sorted(classes, key=lambda item: class_name(item)):
        type_decl = classes[type_name]
        cls = class_name(type_name)
        label = type_decl.doc.object_class or split_label(cls)
        comment = type_decl.doc.definition or f"UBL aggregate component type {type_name}."
        statements = [
            "a owl:Class",
            f"rdfs:isDefinedBy <{BASE_IRI}>",
            f"rdfs:label {ttl_string(label, 'en')}",
            f"rdfs:comment {ttl_string(comment, 'en')}",
            f":xsdType {ttl_string(type_name)}",
        ]
        if type_decl.doc.component_type:
            statements.append(f":xsdComponentType {ttl_string(type_decl.doc.component_type)}")
        statements.extend(restrictions_for(by_domain.get(cls, [])))
        lines.append(f":{cls}")
        add_statements(lines, statements)
        lines.append("")

    for prop in sorted(properties, key=lambda item: item.name):
        add_property(lines, prop)

    return "\n".join(lines) + "\n"


def restrictions_for(properties: list[PropertyDecl]) -> list[str]:
    restrictions: list[str] = []
    for prop in properties:
        target = prop.range_name if prop.range_name.startswith("xsd:") else f":{prop.range_name}"
        restrictions.append(f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{prop.name} ; owl:allValuesFrom {target} ]")
        min_occurs = int(prop.min_occurs or "1")
        max_occurs = prop.max_occurs or "1"
        if max_occurs != "unbounded" and min_occurs == int(max_occurs):
            restrictions.append(f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{prop.name} ; owl:cardinality {typed_non_negative(max_occurs)} ]")
        else:
            if min_occurs > 0:
                restrictions.append(f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{prop.name} ; owl:minCardinality {typed_non_negative(str(min_occurs))} ]")
            if max_occurs != "unbounded":
                restrictions.append(f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{prop.name} ; owl:maxCardinality {typed_non_negative(max_occurs)} ]")
    return restrictions


def add_property(lines: list[str], prop: PropertyDecl) -> None:
    property_type = "owl:ObjectProperty" if prop.kind == "object" else "owl:DatatypeProperty"
    top_property = "owl:topObjectProperty" if prop.kind == "object" else "owl:topDataProperty"
    range_value = f":{prop.range_name}" if prop.kind == "object" else prop.range_name
    statements = [
        f"a {property_type}",
        f"rdfs:subPropertyOf {top_property}",
        f"rdfs:isDefinedBy <{BASE_IRI}>",
        f"rdfs:domain :{prop.domain}",
        f"rdfs:range {range_value}",
        f"rdfs:label {ttl_string(prop.label, 'en')}",
        f"rdfs:comment {ttl_string(prop.comment, 'en')}",
        f":xsdPath {ttl_string(prop.source_ref)}",
        f":xsdMinOccurs {ttl_string(prop.min_occurs)}",
        f":xsdMaxOccurs {ttl_string(prop.max_occurs)}",
    ]
    if prop.xsd_type:
        statements.append(f":xsdType {ttl_string(prop.xsd_type)}")
    if prop.component_type:
        statements.append(f":xsdComponentType {ttl_string(prop.component_type)}")
    lines.append(f":{prop.name}")
    add_statements(lines, statements)
    lines.append("")


def add_annotation_property(lines: list[str], name: str, label: str, comment: str) -> None:
    lines.append(f":{name}")
    add_statements(lines, ["a owl:AnnotationProperty", f"rdfs:label {ttl_string(label, 'en')}", f"rdfs:comment {ttl_string(comment, 'en')}"])
    lines.append("")


def add_statements(lines: list[str], statements: list[str]) -> None:
    statements = [statement for statement in statements if statement]
    for index, statement in enumerate(statements):
        end = " ." if index == len(statements) - 1 else " ;"
        lines.append(f"  {statement}{end}")


def component_doc(element: ET.Element) -> ComponentDoc:
    component = element.find(".//" + CCTS_NS + "Component")
    if component is None:
        documentation = element.find(".//" + XSD_NS + "documentation")
        text = normalize(" ".join(documentation.itertext())) if documentation is not None else ""
        return ComponentDoc(definition=text)
    return ComponentDoc(
        component_type=text_of(component, "ComponentType"),
        dictionary_entry_name=text_of(component, "DictionaryEntryName"),
        definition=text_of(component, "Definition"),
        object_class=text_of(component, "ObjectClass"),
        property_term=text_of(component, "PropertyTerm"),
        representation_term=text_of(component, "RepresentationTerm"),
        data_type=text_of(component, "DataType"),
    )


def text_of(component: ET.Element, local_name: str) -> str:
    child = component.find(CCTS_NS + local_name)
    return normalize(" ".join(child.itertext())) if child is not None else ""


def sequence_elements(element: ET.Element) -> list[ET.Element]:
    return element.findall(".//" + XSD_NS + "sequence/" + XSD_NS + "element")


def datatype_for(element_name: str, doc: ComponentDoc, type_name: str) -> str:
    haystack = " ".join([element_name, doc.representation_term, doc.data_type, type_name]).lower()
    if "date" in haystack:
        return "xsd:date"
    if "time" in haystack:
        return "xsd:time"
    if "indicator" in haystack:
        return "xsd:boolean"
    if "uri" in haystack:
        return "xsd:anyURI"
    if "binary" in haystack:
        return "xsd:base64Binary"
    if any(token in haystack for token in ["amount", "measure", "numeric", "quantity", "percent", "rate", "value"]):
        return "xsd:decimal"
    return "xsd:string"


def class_name(type_or_element: str) -> str:
    value = strip_prefix(type_or_element)
    if value.endswith("Type") and len(value) > 4:
        value = value[:-4]
    return local_name(value)


def local_name(value: str) -> str:
    value = strip_prefix(value)
    parts = re.findall(r"[A-Za-z0-9]+", value)
    result = "".join(part[:1].upper() + part[1:] for part in parts) or "GeneratedTerm"
    if result[0].isdigit():
        result = "Term" + result
    return result


def property_name(value: str) -> str:
    name = local_name(value)
    return name[:1].lower() + name[1:]


def split_ref(ref: str) -> tuple[str, str]:
    if ":" not in ref:
        return "", ref
    prefix, name = ref.split(":", 1)
    return prefix, name


def strip_prefix(value: str) -> str:
    return value.split(":", 1)[-1]


def split_label(value: str) -> str:
    value = strip_prefix(value)
    value = re.sub(r"Type$", "", value)
    value = re.sub(r"(?<!^)(?=[A-Z])", " ", value)
    return normalize(value)


def normalize(value: str) -> str:
    return " ".join(value.split())


def typed_non_negative(value: str) -> str:
    return f'{ttl_string(value)}^^xsd:nonNegativeInteger'


def ttl_string(value: str, lang: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    literal = f'"{escaped}"'
    if lang:
        return f"{literal}@{lang}"
    return literal


if __name__ == "__main__":
    raise SystemExit(main())






