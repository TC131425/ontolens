"""Independent document model for asserted A-Box data."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceRef:
    id: str
    label: str
    curie: str


@dataclass(frozen=True)
class LiteralValue:
    predicate: ResourceRef
    value: str
    language: str | None = None
    datatype: str | None = None


@dataclass(frozen=True)
class Instance:
    resource: ResourceRef
    types: tuple[ResourceRef, ...]
    values: tuple[LiteralValue, ...]
    external: bool = False
    blank: bool = False


@dataclass(frozen=True)
class Relation:
    source: str
    predicate: ResourceRef
    target: str


@dataclass(frozen=True)
class ABoxDoc:
    title: str
    instances: tuple[Instance, ...]
    relations: tuple[Relation, ...]
    triple_count: int
    schema_subject_count: int
