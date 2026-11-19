from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path


CLASSES = {
    "DeliveryNote": {"de": "Lieferschein", "en": "Delivery note", "comment": "A business document that records the delivery of goods or materials."},
    "DeliveryNotePart": {"de": "Lieferscheinbestandteil", "en": "Delivery note part", "comment": "A structural part of a delivery note document."},
    "DeliveryNoteHeader": {"de": "Lieferscheinkopf", "en": "Delivery note header", "comment": "The part of a delivery note that contains information applying to the document as a whole.", "parent": "DeliveryNotePart"},
    "DeliveryNoteLine": {"de": "Lieferscheinposition", "en": "Delivery note line", "comment": "A repeatable line of a delivery note describing delivered goods or materials.", "parent": "DeliveryNotePart"},
    "DeliveryNoteFooter": {"de": "Lieferscheinfuss", "en": "Delivery note footer", "comment": "The closing part of a delivery note, including handover, receipt or signature information.", "parent": "DeliveryNotePart"},
    "Shipment": {"de": "Sendung", "en": "Shipment", "comment": "A transport context for goods or materials referenced by a delivery note."},
    "ShipmentStage": {"de": "Transportstufe", "en": "Shipment stage", "comment": "A stage within a shipment, such as a transport leg or handover step."},
    "Consignment": {"de": "Sendungseinheit", "en": "Consignment", "comment": "A grouping of goods or materials handled together within a shipment."},
    "Delivery": {"de": "Lieferung", "en": "Delivery", "comment": "The fulfilment context in which goods or materials are delivered."},
    "Party": {"de": "Partei", "en": "Party", "comment": "An organization or person participating in a delivery note process."},
    "Contact": {"de": "Kontakt", "en": "Contact", "comment": "Contact information for reaching a party or person."},
    "Person": {"de": "Person", "en": "Person", "comment": "A natural person associated with a party, contact or signature."},
    "PostalAddress": {"de": "Postadresse", "en": "Postal address", "comment": "A postal address associated with a party or delivery location."},
    "GeoLocation": {"de": "Geoposition", "en": "Geolocation", "comment": "Geographic location information such as coordinates."},
    "Item": {"de": "Artikel", "en": "Item", "comment": "A product, material or object described by a delivery note line."},
    "Quantity": {"de": "Menge", "en": "Quantity", "comment": "A quantity value with an associated unit."},
    "Measurement": {"de": "Messwert", "en": "Measurement", "comment": "A measured value such as weight, volume, temperature or consistency."},
    "DocumentReference": {"de": "Dokumentenreferenz", "en": "Document reference", "comment": "A reference to another document, order, certificate or external source."},
    "Attachment": {"de": "Anhang", "en": "Attachment", "comment": "A file or embedded document attached to a document reference."},
    "Signature": {"de": "Signatur", "en": "Signature", "comment": "Signature or signatory information connected to a delivery note."},
    "DeliveryNoteProfile": {"de": "Lieferscheinprofil", "en": "Delivery note profile", "comment": "A profile variant of the delivery note specification."},
}


OBJECT_PROPERTIES = {
    "hasPart": {"label": "has part", "domain": "DeliveryNote", "range": "DeliveryNotePart"},
    "hasHeader": {"label": "has header", "domain": "DeliveryNote", "range": "DeliveryNoteHeader", "xsd": "/*Advice"},
    "hasLine": {"label": "has line", "domain": "DeliveryNote", "range": "DeliveryNoteLine", "xsd": "/*Advice/*Line"},
    "hasFooter": {"label": "has footer", "domain": "DeliveryNote", "range": "DeliveryNoteFooter"},
    "hasShipment": {"label": "has shipment", "domain": "DeliveryNote", "range": "Shipment", "xsd": "/*Advice/cac:Shipment"},
    "hasConsignment": {"label": "has consignment", "domain": "Shipment", "range": "Consignment", "xsd": "/*Advice/cac:Shipment/cac:Consignment"},
    "hasShipmentStage": {"label": "has shipment stage", "domain": "Shipment", "range": "ShipmentStage", "xsd": "/*Advice/cac:Shipment/cac:ShipmentStage"},
    "hasDelivery": {"label": "has delivery", "domain": "Shipment", "range": "Delivery", "xsd": "/*Advice/cac:Shipment/cac:Delivery"},
    "hasParty": {"label": "has party", "domain": "DeliveryNote", "range": "Party"},
    "hasSeller": {"label": "has seller", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:SellerSupplierParty/cac:Party"},
    "hasShipper": {"label": "has shipper", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:DespatchSupplierParty/cac:Party"},
    "hasBuyer": {"label": "has buyer", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:BuyerCustomerParty/cac:Party"},
    "hasRecipient": {"label": "has recipient", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:DeliveryCustomerParty/cac:Party"},
    "hasCarrier": {"label": "has carrier", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:Shipment/cac:ShipmentStage/cac:CarrierParty"},
    "hasManufacturer": {"label": "has manufacturer", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:Shipment/cac:Consignment/cac:ManufacturerParty"},
    "hasIssuingParty": {"label": "has issuing party", "domain": "DeliveryNote", "range": "Party", "subproperty": "hasParty", "xsd": "/*Advice/cac:Signature/cac:SignatoryParty"},
    "hasContact": {"label": "has contact", "domain": "Party", "range": "Contact", "xsd": "cac:Contact"},
    "hasPerson": {"label": "has person", "domain": "Party", "range": "Person", "xsd": "cac:Person"},
    "hasAddress": {"label": "has address", "domain": "Party", "range": "PostalAddress", "xsd": "cac:PostalAddress"},
    "hasGeoLocation": {"label": "has geolocation", "domain": "PostalAddress", "range": "GeoLocation", "xsd": "cac:LocationCoordinate"},
    "hasItem": {"label": "has item", "domain": "DeliveryNoteLine", "range": "Item", "xsd": "cac:Item"},
    "hasQuantity": {"label": "has quantity", "domain": "DeliveryNoteLine", "range": "Quantity", "xsd": "cbc:DeliveredQuantity"},
    "hasMeasurement": {"label": "has measurement", "domain": "DeliveryNoteLine", "range": "Measurement"},
    "hasDocumentReference": {"label": "has document reference", "domain": "DeliveryNote", "range": "DocumentReference", "xsd": "cac:AdditionalDocumentReference"},
    "hasAttachment": {"label": "has attachment", "domain": "DocumentReference", "range": "Attachment", "xsd": "cac:Attachment"},
    "hasSignature": {"label": "has signature", "domain": "DeliveryNote", "range": "Signature", "xsd": "/*Advice/cac:Signature"},
}


DATA_PROPERTIES = {
    "deliveryNoteNumber": {"label": "delivery note number", "domain": "DeliveryNoteHeader", "range": "xsd:string", "xsd": "/DespatchAdvice/cbc:ID"},
    "issueDate": {"label": "issue date", "domain": "DeliveryNoteHeader", "range": "xsd:date", "xsd": "/*Advice/cbc:IssueDate"},
    "issueTime": {"label": "issue time", "domain": "DeliveryNoteHeader", "range": "xsd:time", "xsd": "/*Advice/cbc:IssueTime"},
    "note": {"label": "note", "domain": "DeliveryNoteHeader", "range": "xsd:string", "xsd": "/*Advice/cbc:Note"},
    "lineIdentifier": {"label": "line identifier", "domain": "DeliveryNoteLine", "range": "xsd:string", "xsd": "/*Advice/*Line/cbc:ID"},
    "partyName": {"label": "party name", "domain": "Party", "range": "xsd:string", "xsd": "cac:PartyLegalEntity/cbc:RegistrationName"},
    "partyIdentifier": {"label": "party identifier", "domain": "Party", "range": "xsd:string", "xsd": "cac:PartyIdentification"},
    "website": {"label": "website", "domain": "Party", "range": "xsd:anyURI", "xsd": "cbc:WebsiteURI"},
    "contactName": {"label": "contact name", "domain": "Contact", "range": "xsd:string", "xsd": "cbc:Name"},
    "telephone": {"label": "telephone", "domain": "Contact", "range": "xsd:string", "xsd": "cbc:Telephone"},
    "fax": {"label": "fax", "domain": "Contact", "range": "xsd:string", "xsd": "cbc:Telefax"},
    "email": {"label": "email", "domain": "Contact", "range": "xsd:string", "xsd": "cbc:ElectronicMail"},
    "firstName": {"label": "first name", "domain": "Person", "range": "xsd:string", "xsd": "cbc:FirstName"},
    "lastName": {"label": "last name", "domain": "Person", "range": "xsd:string", "xsd": "cbc:FamilyName"},
    "jobTitle": {"label": "job title", "domain": "Person", "range": "xsd:string", "xsd": "cbc:JobTitle"},
    "streetName": {"label": "street name", "domain": "PostalAddress", "range": "xsd:string", "xsd": "cbc:StreetName"},
    "buildingNumber": {"label": "building number", "domain": "PostalAddress", "range": "xsd:string", "xsd": "cbc:BuildingNumber"},
    "cityName": {"label": "city name", "domain": "PostalAddress", "range": "xsd:string", "xsd": "cbc:CityName"},
    "postalCode": {"label": "postal code", "domain": "PostalAddress", "range": "xsd:string", "xsd": "cbc:PostalZone"},
    "countryCode": {"label": "country code", "domain": "PostalAddress", "range": "xsd:string", "xsd": "cac:Country"},
    "latitude": {"label": "latitude", "domain": "GeoLocation", "range": "xsd:decimal", "xsd": "cbc:LatitudeDegreesMeasure"},
    "longitude": {"label": "longitude", "domain": "GeoLocation", "range": "xsd:decimal", "xsd": "cbc:LongitudeDegreesMeasure"},
    "itemName": {"label": "item name", "domain": "Item", "range": "xsd:string", "xsd": "cac:Item/cbc:Name"},
    "itemIdentifier": {"label": "item identifier", "domain": "Item", "range": "xsd:string", "xsd": "cac:Item/cac:SellersItemIdentification"},
    "quantityValue": {"label": "quantity value", "domain": "Quantity", "range": "xsd:decimal", "xsd": "cbc:DeliveredQuantity"},
    "unitCode": {"label": "unit code", "domain": "Quantity", "range": "xsd:string", "xsd": "@unitCode"},
    "measurementValue": {"label": "measurement value", "domain": "Measurement", "range": "xsd:decimal"},
    "measurementType": {"label": "measurement type", "domain": "Measurement", "range": "xsd:string"},
    "documentIdentifier": {"label": "document identifier", "domain": "DocumentReference", "range": "xsd:string", "xsd": "cac:AdditionalDocumentReference/cbc:ID"},
    "documentUri": {"label": "document URI", "domain": "DocumentReference", "range": "xsd:anyURI", "xsd": "cac:ExternalReference/cbc:URI"},
    "fileName": {"label": "file name", "domain": "Attachment", "range": "xsd:string", "xsd": "cbc:Filename"},
    "mimeType": {"label": "MIME type", "domain": "Attachment", "range": "xsd:string", "xsd": "@mimeCode"},
    "signatureIdentifier": {"label": "signature identifier", "domain": "Signature", "range": "xsd:string", "xsd": "cac:Signature/cbc:ID"},
    "profileIdentifier": {"label": "profile identifier", "domain": "DeliveryNoteProfile", "range": "xsd:string", "xsd": "cbc:ProfileID"},
}


PROFILE_INDIVIDUALS = {
    "standardProfile": ("1LS Standard", "standard profile"),
    "bulkProfile": ("1LS Bulk", "bulk profile"),
    "concreteProfile": ("1LS Concrete", "concrete profile"),
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: generate_delivery_note_ontology.py <ttl>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_turtle(), encoding="utf-8")
    print(f"Generated {target}")
    return 0


def render_turtle() -> str:
    lines = [
        "@prefix : <https://w3id.org/delivery-note#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix vann: <http://purl.org/vocab/vann/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "<https://w3id.org/delivery-note>",
        "  a owl:Ontology ;",
        '  dcterms:title "Delivery Note Ontology"@en, "Lieferschein-Ontologie"@de ;',
        '  dcterms:description "Initial class structure for modelling delivery note documents and their core business concepts."@en ;',
        '  dcterms:created "2026-07-20"^^xsd:date ;',
        '  dcterms:creator "Sven Zentgraf" ;',
        '  vann:preferredNamespacePrefix "dnote" ;',
        "  vann:preferredNamespaceUri <https://w3id.org/delivery-note#> ;",
        "  owl:versionIRI <https://w3id.org/delivery-note/0.1.0> ;",
        '  owl:versionInfo "0.1.0" ;',
        '  rdfs:comment "This version models the abstract class structure and annotates model properties with catalogue XSD paths where a stable mapping is known. Spreadsheet rows themselves are not represented."@en .',
        "",
        ":xsdPath",
        "  a owl:AnnotationProperty ;",
        '  rdfs:label "XSD path"@en ;',
        '  rdfs:comment "XML/XSD path from the delivery note catalogue for the annotated property."@en .',
        "",
    ]
    add_classes(lines)
    add_object_properties(lines)
    add_data_properties(lines)
    add_profile_individuals(lines)
    return "\n".join(lines) + "\n"


def add_classes(lines: list[str]) -> None:
    restrictions = restrictions_by_class()
    for name, values in CLASSES.items():
        statements = [
            "a owl:Class",
            f'rdfs:label {ttl_string(values["de"], "de")}, {ttl_string(values["en"], "en")}',
            f'rdfs:comment {ttl_string(values["comment"], "en")}',
        ]
        if parent := values.get("parent"):
            statements.append(f"rdfs:subClassOf :{parent}")
        statements.extend(restrictions[name])
        lines.append(f":{name}")
        add_statements(lines, statements)
        lines.append("")


def restrictions_by_class() -> dict[str, list[str]]:
    restrictions: dict[str, list[str]] = defaultdict(list)
    for name, values in OBJECT_PROPERTIES.items():
        restrictions[values["domain"]].append(restriction(name, values["range"], "owl:allValuesFrom"))
    for name, values in DATA_PROPERTIES.items():
        restrictions[values["domain"]].append(restriction(name, values["range"], "owl:allValuesFrom"))
    return restrictions


def restriction(property_name: str, filler: str, kind: str) -> str:
    target = filler if filler.startswith("xsd:") else f":{filler}"
    return f"rdfs:subClassOf [ a owl:Restriction ; owl:onProperty :{property_name} ; {kind} {target} ]"


def add_object_properties(lines: list[str]) -> None:
    for name, values in OBJECT_PROPERTIES.items():
        statements = [
            "a owl:ObjectProperty",
            f'rdfs:label {ttl_string(values["label"], "en")}',
            f'rdfs:domain :{values["domain"]}',
            f'rdfs:range :{values["range"]}',
            f'rdfs:subPropertyOf :{values["subproperty"]}' if values.get("subproperty") else "",
            f"rdfs:comment {ttl_string('Relates ' + values['domain'] + ' to ' + values['range'] + '.', 'en')}",
        ]
        if xsd_path := values.get("xsd"):
            statements.append(f":xsdPath {ttl_string(xsd_path)}")
        lines.append(f":{name}")
        add_statements(lines, statements)
        lines.append("")


def add_data_properties(lines: list[str]) -> None:
    for name, values in DATA_PROPERTIES.items():
        statements = [
            "a owl:DatatypeProperty",
            f'rdfs:label {ttl_string(values["label"], "en")}',
            f'rdfs:domain :{values["domain"]}',
            f'rdfs:range {values["range"]}',
            f"rdfs:comment {ttl_string('Data property of ' + values['domain'] + '.', 'en')}",
        ]
        if xsd_path := values.get("xsd"):
            statements.append(f":xsdPath {ttl_string(xsd_path)}")
        lines.append(f":{name}")
        add_statements(lines, statements)
        lines.append("")



def add_profile_individuals(lines: list[str]) -> None:
    for name, (label, comment) in PROFILE_INDIVIDUALS.items():
        lines.append(f":{name}")
        add_statements(lines, ["a :DeliveryNoteProfile", f'rdfs:label {ttl_string(label, "en")}', f'rdfs:comment {ttl_string(comment, "en")}'])
        lines.append("")


def add_statements(lines: list[str], statements: list[str]) -> None:
    statements = [statement for statement in statements if statement]
    for index, statement in enumerate(statements):
        end = " ." if index == len(statements) - 1 else " ;"
        lines.append(f"  {statement}{end}")


def ttl_string(value: str, lang: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    literal = f'"{escaped}"'
    if lang:
        return f"{literal}@{lang}"
    return literal


if __name__ == "__main__":
    raise SystemExit(main())

