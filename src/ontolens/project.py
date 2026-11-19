from __future__ import annotations

import re
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader

from .content import read_editorial_source
from .content_check import check_content
from .parser import load_ontology
from .render import generate


BOOLEAN_OPTIONS = {"recommendations", "quality_report", "custom_annotations", "check_content", "skip_missing_images", "show_missing_endpoints", "include_external_classes"}
OPTIONS = BOOLEAN_OPTIONS | {"language", "format", "theme"}


@dataclass(frozen=True)
class ProjectOntology:
    id: str
    input: Path
    content: Path | None
    options: dict


@dataclass(frozen=True)
class Project:
    name: str
    output: Path
    ontologies: tuple[ProjectOntology, ...]
    portal_enabled: bool
    portal_title: str


@dataclass(frozen=True)
class ProjectBuild:
    directory: Path
    pages: tuple[Path, ...]
    portal: Path | None
    notices: tuple[str, ...]


def _mapping(value, context: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown fields in {context}: {', '.join(map(str, unknown))}")
    return value


def _string(value, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a nonempty string")
    return value


def _options(values: dict, context: str) -> dict:
    for key, value in values.items():
        if key in {"language", "format"} and value is None:
            continue
        if key == "theme" and value not in ("light", "dark", "both"):
            raise ValueError(f"{context}.theme must be light, dark or both")
        if key in BOOLEAN_OPTIONS:
            if not isinstance(value, bool):
                raise ValueError(f"{context}.{key} must be true or false")
        else:
            _string(value, f"{context}.{key}")
    return values


def load_project(path: Path, *, require_sources: bool = True) -> Project:
    path = path.resolve()
    config = _mapping(yaml.safe_load(path.read_text(encoding="utf-8-sig")), "project",
                      {"name", "output", "defaults", "ontologies", "portal"})
    name = _string(config.get("name", path.stem), "name")
    output = (path.parent / _string(config.get("output", "build"), "output")).resolve()
    defaults = _options(_mapping(config.get("defaults", {}), "defaults", OPTIONS), "defaults")
    entries = config.get("ontologies")
    if not isinstance(entries, list):
        raise ValueError("ontologies must be a list")
    ontologies = []
    ids = set()
    for entry in entries:
        entry = _mapping(entry, "ontology", OPTIONS | {"id", "input", "content"})
        identity = _string(entry.get("id"), "ontology.id")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", identity) or identity.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError(f"Invalid ontology id: {identity}")
        if identity.casefold() in ids:
            raise ValueError(f"Duplicate ontology id: {identity}")
        ids.add(identity.casefold())
        input_path = (path.parent / _string(entry.get("input"), f"{identity}.input")).resolve()
        content = (path.parent / _string(entry["content"], f"{identity}.content")).resolve() if "content" in entry else None
        for source in (input_path, content):
            if require_sources and source is not None and not source.is_file():
                raise ValueError(f"Input file does not exist: {source}")
        options = defaults | _options({key: value for key, value in entry.items() if key in OPTIONS}, identity)
        ontologies.append(ProjectOntology(identity, input_path, content, options))
    portal = _mapping(config.get("portal", {}), "portal", {"enabled", "title"})
    enabled = portal.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("portal.enabled must be true or false")
    return Project(name, output, tuple(ontologies), enabled, _string(portal.get("title", name), "portal.title"))


def build_project(project: Project, selected: list[str] | None = None, overrides: dict | None = None,
                  portal: bool | None = None, _directory: Path | None = None) -> ProjectBuild:
    overrides = _options(_mapping(overrides or {}, "overrides", OPTIONS), "overrides")
    if selected and set(selected) - {item.id for item in project.ontologies}:
        raise ValueError("Unknown ontology selection: " + ", ".join(selected))
    entries = [item for item in project.ontologies if not selected or item.id in selected]
    if not entries:
        raise ValueError("No ontologies selected for building")
    notices = []
    for item in entries:
        options = item.options | overrides
        if options.get("check_content"):
            if item.content is None:
                raise ValueError(f"{item.id}: check_content requires content; set check_content: false for this entry")
            issues = check_content(read_editorial_source(item.content))
            notices.extend(f"{item.id}: [{issue.chapter}] {issue.kind}" for issue in issues)
    slug = re.sub(r"[^a-z0-9_-]+", "-", project.name.lower()).strip("-_") or "project"
    now = datetime.now()
    directory = _directory or project.output / f"{now:%Y-%m-%dT%H-%M-%S}_{slug}"
    if overrides.get('theme') == 'both' or all((item.options | overrides).get('theme') == 'both' for item in entries):
        directory.mkdir(parents=True, exist_ok=False)
        results = [build_project(project, selected, overrides | {'theme': variant}, portal,
                                 _directory=directory / variant) for variant in ('light', 'dark')]
        return ProjectBuild(directory, tuple(page for result in results for page in result.pages),
                            results[0].portal, results[0].notices)
    # A project bundle is immutable: never mix two runs in the same directory.
    directory.mkdir(parents=True, exist_ok=False)
    pages, summaries = [], []
    enabled = project.portal_enabled if portal is None else portal
    for item in entries:
        options = item.options | overrides
        page_notices = []
        page = generate(item.input, directory / item.id / f"{item.id}.html",
                        content_path=item.content, rdf_format=options.get("format"),
                        language=options.get("language"), recommendations=options.get("recommendations", False),
                        quality_report=options.get("quality_report", False),
                        include_custom_annotations=options.get("custom_annotations", False),
                        show_missing_endpoints=options.get("show_missing_endpoints", False),
                        include_external_classes=options.get("include_external_classes", False),
                        skip_missing_images=options.get("skip_missing_images", False), generated_at=now, theme=options.get("theme", "light"), notices=page_notices)
        notices.extend(f"{item.id}: {notice}" for notice in page_notices)
        pages.append(page)
        dark_page = page.parent.parent / 'dark' / page.name if options.get('theme') == 'both' else None
        if dark_page:
            pages.append(dark_page)
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        if not enabled:
            page.write_text(str(soup), encoding="utf-8")
            continue
        source = read_editorial_source(item.content) if item.content else None
        doc = load_ontology(item.input, rdf_format=options.get("format"),
                            language=options.get("language") or (source.language if source else None) or "en")
        navigation = soup.new_tag("nav", attrs={"aria-label": "Portal", "style": "padding:12px 24px;background:var(--panel,#edf4f4);border-bottom:1px solid var(--line,#cbd8da)"})
        link = soup.new_tag("a", href=os.path.relpath(directory / 'index.html', page.parent).replace(os.sep, '/'))
        link.string = project.portal_title
        navigation.append(link)
        soup.body.insert(0, navigation)
        page.write_text(str(soup), encoding="utf-8")
        if dark_page:
            dark_soup = BeautifulSoup(dark_page.read_text(encoding='utf-8'), 'html.parser')
            dark_soup.body.insert(0, deepcopy(navigation))
            dark_page.write_text(str(dark_soup), encoding='utf-8')
        description = (source.description if source else None) or doc.description or ""
        summaries.append({"id": item.id, "title": (source.title if source else None) or doc.title,
                          "description": BeautifulSoup(description, "html.parser").get_text(" ", strip=True),
                          "version": doc.version, "classes": len(doc.classes),
                          "properties": doc.term_count - len(doc.classes),
                          "href": page.relative_to(directory).as_posix()})
        if dark_page:
            summaries[-1]['title'] += ' (Light)'
            summaries.append(summaries[-1] | {'title': ((source.title if source else None) or doc.title) + ' (Dark)',
                                             'href': dark_page.relative_to(directory).as_posix()})
    index = None
    if enabled:
        env = Environment(loader=PackageLoader("ontolens", "templates"), autoescape=True)
        index = directory / "index.html"
        index.write_text(env.get_template("portal.html.j2").render(title=project.portal_title, entries=summaries, theme=overrides.get('theme', 'light')), encoding="utf-8")
    return ProjectBuild(directory, tuple(pages), index, tuple(notices))
