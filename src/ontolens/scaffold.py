from __future__ import annotations

from pathlib import Path

import yaml

from .parser import load_ontology


# Stable keys are shared by both languages; prose stays editable by the author.
CHAPTERS = (
    ("introduction", "Einleitung", "Introduction",
     "Zweck, Motivation und Zielgruppe beschreiben.", "Describe purpose, motivation and target audience."),
    ("scope", "Umfang und Anforderungen", "Scope and requirements",
     "Abdeckung und Grenzen beschreiben. Anwendungsfälle und Competency Questions mit erwarteten Antworten ergänzen.",
     "Describe coverage and boundaries. Add use cases and competency questions with expected answers."),
    ("conceptual-model", "Konzeptionelles Modell", "Conceptual model",
     "Zentrale Konzepte und Beziehungen erklären. Unterkapitel und eigene Diagramme nach Bedarf ergänzen.",
     "Explain core concepts and relationships. Add subsections and diagrams as needed."),
    ("design-decisions", "Modellierungsentscheidungen", "Modeling decisions",
     "Patterns, Alternativen und Begründungen dokumentieren; Wissensquellen und Entwicklungsmethode benennen.",
     "Document patterns, alternatives and rationale; identify knowledge sources and development methods."),
    ("usage", "Anwendung und Beispiele", "Usage and examples",
     "Ein fachlich geprüftes Turtle-Beispiel, typische Abläufe und gegebenenfalls SPARQL-Abfragen ergänzen.",
     "Add a reviewed Turtle example, typical workflows and SPARQL queries where useful."),
    ("interoperability", "Wiederverwendung und Interoperabilität", "Reuse and interoperability",
     "Imports, Wiederverwendung, Mappings und Erweiterungsmöglichkeiten erklären.",
     "Explain imports, reuse, mappings and extension points."),
    ("validation", "Validierung und Grenzen", "Validation and limitations",
     "Prüfverfahren, Ergebnisse und bekannte Grenzen dokumentieren. Der Qualitätsbericht ersetzt keine logische Validierung.",
     "Document testing, results and known limitations. The quality report does not replace logical validation."),
    ("maintenance", "Versionierung und Pflege", "Versioning and maintenance",
     "Versionsregeln, Kompatibilität, Änderungen, Deprecation, Zuständigkeiten und Mitarbeit beschreiben.",
     "Describe versioning, compatibility, changes, deprecation, responsibilities and contributions."),
    ("references", "Literatur und Quellen", "References and sources",
     "Normen, Publikationen und weitere Quellen nennen. Bei Bedarf Danksagung und Förderung ergänzen.",
     "List standards, publications and other sources. Add acknowledgements and funding where relevant."),
)
COMPACT = {"introduction", "scope", "conceptual-model", "usage"}


def create_content(
    ontology: Path, output: Path, language: str = "en", profile: str = "standard",
    rdf_format: str | None = None,
) -> Path:
    if language not in {"de", "en"} or profile not in {"compact", "standard"}:
        raise ValueError("Supported languages: de, en; profiles: compact, standard")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {output}")
    doc = load_ontology(ontology, rdf_format=rdf_format, language=language)
    metadata = {"language": language, "title": doc.title, "profile": profile}
    # Descriptions may contain relative image paths. Keep those in the ontology
    # metadata slot, where the asset bundler resolves their original location.
    parts = ["---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---",
             "<!-- ontolens:metadata -->"]
    for key, de, en, de_hint, en_hint in CHAPTERS:
        if profile == "compact" and key not in COMPACT:
            continue
        if key == "references":
            continue
        parts.append(f"<!-- ontolens:chapter {key} -->\n# {de if language == 'de' else en}\n\n<!-- {de_hint if language == 'de' else en_hint} -->")
        if key == "conceptual-model":
            parts.extend(["<!-- ontolens:visualization -->", "<!-- ontolens:figures -->"])
        if key == "interoperability":
            parts.append("<!-- ontolens:used-ontologies -->")
        if key == "validation":
            parts.append("<!-- ontolens:quality-report -->")
    if profile == "compact":
        parts.extend(["<!-- ontolens:used-ontologies -->", "<!-- ontolens:quality-report -->"])
    parts.extend(["<!-- ontolens:downloads -->", "<!-- ontolens:prefixes -->",
                  "<!-- ontolens:overview -->", "<!-- ontolens:cross-reference -->"])
    if profile == "standard":
        key, de, en, de_hint, en_hint = CHAPTERS[-1]
        parts.append(f"<!-- ontolens:chapter {key} -->\n# {de if language == 'de' else en}\n\n<!-- {de_hint if language == 'de' else en_hint} -->")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n\n".join(parts) + "\n")
    return output
