from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path

XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
CCTS_NS = "{urn:un:unece:uncefact:documentation:2}"
BASE_IRI = "https://w3id.org/delivery-note-xsd-single-file"
BASE = BASE_IRI + "#"


@dataclass(frozen=True)
class ComponentDoc:
    component_type: str = ""
    definition: str = ""
    object_class: str = ""
    property_term: str = ""
    representation_term: str = ""
    data_type: str = ""


@dataclass(frozen=True)
class PropertyDecl:
    name: str
    kind: str
    range_name: str
    label: str
    comment: str
    source_ref: str
    min_occurs: str
    max_occurs: str
    component_type: str
    datatype: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a single-file OWL view from UBL-DeliveryNote-2.5.xsd only.")
    parser.add_argument("xsd", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    root = ET.parse(args.xsd).getroot()
    delivery_note_type = next(
        complex_type for complex_type in root.findall(XSD_NS + "complexType") if complex_type.get("name") == "DeliveryNoteType"
    )
    root_element = next(element for element in root.findall(XSD_NS + "element") if element.get("name") == "DeliveryNote")
    properties = [property_from_element(element) for element in delivery_note_type.findall(XSD_NS + "sequence/" + XSD_NS + "element")]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_turtle(args.xsd, root_element, delivery_note_type, properties), encoding="utf-8")
    print(f"Generated {args.output} with 1 root class, {len(external_classes(properties))} external stub classes and {len(properties)} properties")
    return 0


def property_from_element(element: ET.Element) -> PropertyDecl:
    ref = element.get("ref", "")
    prefix, local = split_ref(ref)
    doc = component_doc(element)
    label = doc.property_term or split_label(local)
    comment = doc.definition or f"UBL DeliveryNote element {ref}."
    min_occurs = element.get("minOccurs", "1")
    max_occurs = element.get("maxOccurs", "1")

    if prefix in {"cac", "ext"}:
        return PropertyDecl(
            name=property_name("hasDeliveryNote" + local),
            kind="object",
            range_name=class_name(local),
            label=label,
            comment=comment,
            source_ref=f"DeliveryNote/{ref}",
            min_occurs=min_occurs,
            max_occurs=max_occurs,
            component_type=doc.component_type,
            datatype="",
        )
    datatype = datatype_for(local, doc)
    return PropertyDecl(
        name=property_name("deliveryNote" + local),
        kind="data",
        range_name=datatype,
        label=label,
        comment=comment,
        source_ref=f"DeliveryNote/{ref}",
        min_occurs=min_occurs,
        max_occurs=max_occurs,
        component_type=doc.component_type,
        datatype=doc.data_type,
    )


def render_turtle(source: Path, root_element: ET.Element, delivery_note_type: ET.Element, properties: list[PropertyDecl]) -> str:
    root_doc = component_doc(delivery_note_type)
    element_doc = component_doc(root_element)
    comment = root_doc.definition or element_doc.definition or "UBL DeliveryNote document."
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
        '  dcterms:title "Delivery Note Ontology from UBL DeliveryNote XSD only"@en ;',
        f'  dcterms:created "{date.today().isoformat()}"^^xsd:date ;',
        f"  dcterms:source {ttl_string(source.name)} ;",
        '  vann:preferredNamespacePrefix "dnxsd1" ;',
        f"  vann:preferredNamespaceUri <{BASE}> ;",
        f"  owl:versionIRI <{BASE_IRI}/0.1.0> ;",
        '  owl:versionInfo "0.1.0" ;',
        '  rdfs:comment "Generated only from UBL-DeliveryNote-2.5.xsd. Imported Common Component schemas are not read; external references are represented as local stub classes."@en .',
        "",
    ]
    for name, label, description in [
        ("xsdPath", "XSD path", "Source XSD component path for the generated term."),
        ("xsdMinOccurs", "XSD minOccurs", "Minimum occurrence from the source XSD."),
        ("xsdMaxOccurs", "XSD maxOccurs", "Maximum occurrence from the source XSD."),
        ("xsdComponentType", "XSD CCTS component type", "CCTS component type from the source XSD documentation."),
    ]:
        add_statements(lines, f":{name}", ["a owl:AnnotationProperty", f"rdfs:label {ttl_string(label, 'en')}", f"rdfs:comment {ttl_string(description, 'en')}"])
        lines.append("")

    for stub in sorted(external_classes(properties)):
        add_statements(lines, f":{stub}", [
            "a owl:Class",
            f"rdfs:isDefinedBy <{BASE_IRI}>",
            f"rdfs:label {ttl_string(split_label(stub), 'en')}",
            f"rdfs:comment {ttl_string('Stub class for an external aggregate referenced by UBL-DeliveryNote-2.5.xsd.', 'en')}",
        ])
        lines.append("")

    class_statements = [
        "a owl:Class",
        f"rdfs:isDefinedBy <{BASE_IRI}>",
        'rdfs:label "Delivery Note"@en',
        f"rdfs:comment {ttl_string(comment, 'en')}",
        ':xsdPath "DeliveryNoteType"',
    ]
    if root_doc.component_type:
        class_statements.append(f":xsdComponentType {ttl_string(root_doc.component_type)}")
    for prop in properties:
        target = prop.range_name if prop.kind == "data" else f":{prop.range_name}"
        class_statements.append(f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{prop.name} ; owl:allValuesFrom {target} ]")
        class_statements.extend(cardinality_restrictions(prop))
    add_statements(lines, ":DeliveryNote", class_statements)
    lines.append("")

    for prop in sorted(properties, key=lambda item: item.name):
        add_property(lines, prop)

    return "\n".join(lines) + "\n"


def add_property(lines: list[str], prop: PropertyDecl) -> None:
    property_type = "owl:ObjectProperty" if prop.kind == "object" else "owl:DatatypeProperty"
    top_property = "owl:topObjectProperty" if prop.kind == "object" else "owl:topDataProperty"
    range_value = f":{prop.range_name}" if prop.kind == "object" else prop.range_name
    statements = [
        f"a {property_type}",
        f"rdfs:subPropertyOf {top_property}",
        f"rdfs:isDefinedBy <{BASE_IRI}>",
        "rdfs:domain :DeliveryNote",
        f"rdfs:range {range_value}",
        f"rdfs:label {ttl_string(prop.label, 'en')}",
        f"rdfs:comment {ttl_string(prop.comment, 'en')}",
        f":xsdPath {ttl_string(prop.source_ref)}",
        f":xsdMinOccurs {ttl_string(prop.min_occurs)}",
        f":xsdMaxOccurs {ttl_string(prop.max_occurs)}",
    ]
    if prop.component_type:
        statements.append(f":xsdComponentType {ttl_string(prop.component_type)}")
    add_statements(lines, f":{prop.name}", statements)
    lines.append("")


def cardinality_restrictions(prop: PropertyDecl) -> list[str]:
    restrictions: list[str] = []
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


def component_doc(element: ET.Element) -> ComponentDoc:
    component = element.find(".//" + CCTS_NS + "Component")
    if component is None:
        documentation = element.find(".//" + XSD_NS + "documentation")
        return ComponentDoc(definition=normalize(" ".join(documentation.itertext())) if documentation is not None else "")
    return ComponentDoc(
        component_type=text_of(component, "ComponentType"),
        definition=text_of(component, "Definition"),
        object_class=text_of(component, "ObjectClass"),
        property_term=text_of(component, "PropertyTerm"),
        representation_term=text_of(component, "RepresentationTerm"),
        data_type=text_of(component, "DataType"),
    )


def text_of(component: ET.Element, local_name: str) -> str:
    child = component.find(CCTS_NS + local_name)
    return normalize(" ".join(child.itertext())) if child is not None else ""


def datatype_for(name: str, doc: ComponentDoc) -> str:
    haystack = " ".join([name, doc.representation_term, doc.data_type]).lower()
    if "date" in haystack:
        return "xsd:date"
    if "time" in haystack:
        return "xsd:time"
    if "indicator" in haystack:
        return "xsd:boolean"
    if "uri" in haystack:
        return "xsd:anyURI"
    if any(token in haystack for token in ["amount", "measure", "numeric", "quantity", "percent", "rate", "value"]):
        return "xsd:decimal"
    return "xsd:string"


def external_classes(properties: list[PropertyDecl]) -> set[str]:
    return {prop.range_name for prop in properties if prop.kind == "object"}


def add_statements(lines: list[str], subject: str, statements: list[str]) -> None:
    lines.append(subject)
    for index, statement in enumerate(statements):
        end = " ." if index == len(statements) - 1 else " ;"
        lines.append(f"  {statement}{end}")


def split_ref(ref: str) -> tuple[str, str]:
    return ref.split(":", 1) if ":" in ref else ("", ref)


def class_name(value: str) -> str:
    return local_name(value)


def property_name(value: str) -> str:
    name = local_name(value)
    return name[:1].lower() + name[1:]


def local_name(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    result = "".join(part[:1].upper() + part[1:] for part in parts) or "GeneratedTerm"
    return "Term" + result if result[0].isdigit() else result


def split_label(value: str) -> str:
    return normalize(re.sub(r"(?<!^)(?=[A-Z])", " ", value))


def normalize(value: str) -> str:
    return " ".join(value.split())


def typed_non_negative(value: str) -> str:
    return f'{ttl_string(value)}^^xsd:nonNegativeInteger'


def ttl_string(value: str, lang: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    literal = f'"{escaped}"'
    return f"{literal}@{lang}" if lang else literal


if __name__ == "__main__":
    raise SystemExit(main())
