from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Value:
    text: str
    lang: str | None = None
    href: str | None = None
    union_members: tuple[Value, ...] = ()


@dataclass(frozen=True)
class Agent:
    name: str
    email: str | None = None
    identifier: str | None = None
    affiliation: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class MetadataItem:
    label: str
    values: tuple[Value, ...]
    status: str | None = None


@dataclass(frozen=True)
class HeroFigure:
    title: str
    src: str
    alt: str


@dataclass(frozen=True)
class UsedOntology:
    label: str
    uri: str
    relation: str


@dataclass(frozen=True)
class DownloadLink:
    label: str
    href: str
    format: str
    media_type: str | None = None


@dataclass(frozen=True)
class QualityIssue:
    category: str
    message: str
    severity: str = "warning"
    href: str | None = None


@dataclass(frozen=True)
class QualitySection:
    title: str
    issues: tuple[QualityIssue, ...] = ()

    @property
    def count(self) -> int:
        return len(self.issues)


@dataclass(frozen=True)
class QualityReport:
    sections: tuple[QualitySection, ...] = ()

    @property
    def issue_count(self) -> int:
        return sum(section.count for section in self.sections)

    @property
    def error_count(self) -> int:
        return sum(1 for section in self.sections for issue in section.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for section in self.sections for issue in section.issues if issue.severity == "warning")


@dataclass(frozen=True)
class RestrictionDoc:
    property: Value
    constraint: str
    value: str | None = None
    filler: Value | None = None


@dataclass(frozen=True)
class TermDoc:
    uri: str
    curie: str
    anchor: str
    title: str
    kind: str
    labels: tuple[Value, ...] = ()
    comments: tuple[Value, ...] = ()
    types: tuple[str, ...] = ()
    parents: tuple[Value, ...] = ()
    domains: tuple[Value, ...] = ()
    ranges: tuple[Value, ...] = ()
    subproperties: tuple[Value, ...] = ()
    equivalents: tuple[Value, ...] = ()
    inverses: tuple[Value, ...] = ()
    restrictions: tuple[RestrictionDoc, ...] = ()
    instances: tuple[Value, ...] = ()
    other_annotations: tuple[MetadataItem, ...] = ()


@dataclass(frozen=True)
class OntologyDoc:
    title: str
    uri: str | None
    description: str | None
    hero_figures: tuple[HeroFigure, ...]
    version: str | None
    preferred_prefix: str | None
    preferred_namespace: str | None
    metadata: tuple[MetadataItem, ...]
    creators: tuple[Agent, ...] = ()
    contributors: tuple[Agent, ...] = ()
    classes: tuple[TermDoc, ...] = ()
    object_properties: tuple[TermDoc, ...] = ()
    datatype_properties: tuple[TermDoc, ...] = ()
    annotation_properties: tuple[TermDoc, ...] = ()
    rdf_properties: tuple[TermDoc, ...] = ()
    prefixes: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    used_ontologies: tuple[UsedOntology, ...] = ()
    downloads: tuple[DownloadLink, ...] = ()
    quality: QualityReport = field(default_factory=QualityReport)
    external_classes: tuple[TermDoc, ...] = ()

    @property
    def term_count(self) -> int:
        return (
            len(self.classes)
            + len(self.object_properties)
            + len(self.datatype_properties)
            + len(self.annotation_properties)
            + len(self.rdf_properties)
        )



