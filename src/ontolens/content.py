from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

import markdown
import yaml
from bs4 import BeautifulSoup, Comment, Tag
from markdown.extensions import Extension
from markdown.extensions.toc import TocExtension, slugify as markdown_slugify
from markdown.inlinepatterns import InlineProcessor

from .assets import AssetBundle
from .model import OntologyDoc, TermDoc


SLOT_MARKER = re.compile(
    r"^\s*<!--\s*ontolens:([a-z0-9_-]+)\s*-->\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
SLOT_ELEMENT = re.compile(r'<div\s+data-ontolens-slot="([a-z0-9-]+)"\s*></div>')
WIKI_LINK = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"

SLOT_ALIASES = {
    "metadata": "metadata",
    "figures": "figures",
    "quality": "quality-report",
    "quality-report": "quality-report",
    "namespaces": "prefixes",
    "namespace-prefixes": "prefixes",
    "prefixes": "prefixes",
    "used-ontologies": "used-ontologies",
    "downloads": "downloads",
    "visualization": "visualization",
    "overview": "overview",
    "cross-reference": "cross-reference",
}

DEFAULT_SLOT_ORDER = (
    "figures",
    "quality-report",
    "prefixes",
    "used-ontologies",
    "downloads",
    "visualization",
    "overview",
)

UI_TEXT = {
    "en": {
        "toc": "Table of Contents",
        "editorial-intro": "Introductory text",
        "metadata": "Ontology Metadata",
        "agents": "Creators and Contributors",
        "figures": "Figures",
        "quality-report": "Quality Report",
        "prefixes": "Namespace Prefixes",
        "used-ontologies": "Used Ontologies",
        "downloads": "Downloads",
        "visualization": "Visualization",
        "overview": "Overview",
        "cross-reference": "Technical Reference",
        "classes": "Classes",
        "object-properties": "Object Properties",
        "datatype-properties": "Datatype Properties",
        "annotation-properties": "Annotation Properties",
        "rdf-properties": "RDF Properties",
        "reference-intro": "This section provides details for each class and property defined by the ontology.",
    },
    "de": {
        "toc": "Inhaltsverzeichnis",
        "editorial-intro": "Einleitungstext",
        "metadata": "Ontologie-Metadaten",
        "agents": "Erstellende und Mitwirkende",
        "figures": "Abbildungen",
        "quality-report": "Qualitätsbericht",
        "prefixes": "Namensraum-Präfixe",
        "used-ontologies": "Verwendete Ontologien",
        "downloads": "Downloads",
        "visualization": "Visualisierung",
        "overview": "Übersicht",
        "cross-reference": "Technische Referenz",
        "classes": "Klassen",
        "object-properties": "Objekt-Properties",
        "datatype-properties": "Daten-Properties",
        "annotation-properties": "Annotations-Properties",
        "rdf-properties": "RDF-Properties",
        "reference-intro": "Dieser Abschnitt enthält die technische Beschreibung aller Klassen und Properties der Ontologie.",
    },
}

COMBINED_PAGE_CSS = """
.editorial-flow > h1 {
  margin: 44px 0 14px;
  padding: 0 0 9px;
  border-bottom: 2px solid var(--brand);
  color: var(--brand-dark);
  font-size: 1.9rem;
  line-height: 1.2;
}
.editorial-flow > h1:first-of-type { margin-top: 34px; }
.editorial-flow > h2,
.editorial-flow > h3 { scroll-margin-top: 18px; }
.editorial-flow p { max-width: 76ch; }
.editorial-flow > p:has(> img) { max-width: none; margin: 18px 0 30px; }
.editorial-flow > p > img {
  display: block;
  width: 100%;
  max-height: 760px;
  padding: 18px;
  object-fit: contain;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(20, 28, 32, .08);
}
.editorial-flow pre {
  margin: 14px 0 24px;
  padding: 16px 18px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #172629;
  color: #e8f2f3;
  line-height: 1.5;
}
.editorial-flow pre code { padding: 0; background: transparent; color: inherit; }
.editorial-flow table { table-layout: fixed; }
.editorial-flow th,
.editorial-flow td,
.editorial-flow a,
.editorial-flow .pill {
  overflow-wrap: anywhere;
  word-break: break-word;
}
.editorial-flow .pill {
  display: inline-block;
  max-width: 100%;
  white-space: normal;
}
.toc-subsection { padding: 4px 0 4px 12px; font-size: .9rem; }
.toc-level-3 { padding-left: 24px; font-size: .84rem; }
.toc-subsection + .toc-group { margin-top: 6px; }
.toc-reference-groups {
  display: grid;
  gap: 3px;
  padding: 8px 0 0 10px !important;
}
.toc-reference-groups details { min-width: 0; }
.toc-reference-groups summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 0;
  color: var(--brand-dark);
  cursor: pointer;
  font-weight: 650;
  line-height: 1.25;
  list-style: none;
}
.toc-reference-groups summary::-webkit-details-marker { display: none; }
.toc-reference-groups summary::before {
  content: "+";
  flex: 0 0 15px;
  color: var(--muted);
  font-weight: 700;
}
.toc-reference-groups details[open] > summary::before { content: "−"; }
.toc-reference-groups summary > span:first-child { flex: 1 1 auto; }
.toc-count {
  flex: 0 0 auto;
  min-width: 24px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #e5edef;
  color: var(--muted);
  text-align: center;
  font-size: .75rem;
  font-weight: 700;
}
.toc-term-list {
  padding: 2px 0 7px 20px !important;
  border-left: 1px solid #cbd8da;
}
.toc-term-list li { padding: 3px 0; }
.toc-term-list a { color: #315e62; font-size: .84rem; }
@media (max-width: 700px) {
  .editorial-flow pre code { white-space: pre-wrap; overflow-wrap: anywhere; }
}
"""


@dataclass(frozen=True)
class EditorialSource:
    path: Path
    markdown: str
    language: str | None = None
    title: str | None = None
    description: str | None = None
    profile: str = "standard"


@dataclass(frozen=True)
class ContentBlock:
    kind: str
    value: str


@dataclass(frozen=True)
class EditorialContent:
    blocks: tuple[ContentBlock, ...]
    language: str | None = None
    title: str | None = None
    description: str | None = None


def read_editorial_source(path: Path) -> EditorialSource:
    path = path.resolve()
    text = path.read_text(encoding="utf-8-sig")
    return parse_editorial_source(text, path)


def parse_editorial_source(text: str, path: Path) -> EditorialSource:
    """Parse an editorial draft without writing it to disk."""
    metadata, body = _split_frontmatter(text, path)
    return EditorialSource(
        path=path,
        markdown=body,
        language=_optional_string(metadata, "language"),
        title=_optional_string(metadata, "title"),
        description=_optional_string(metadata, "description"),
        profile=_optional_string(metadata, "profile") or "standard",
    )


def render_editorial_content(
    source: EditorialSource,
    doc: OntologyDoc,
    assets: AssetBundle,
    quality_report: bool = False,
) -> EditorialContent:
    markers: list[str] = []

    def replace_marker(match: re.Match[str]) -> str:
        raw_slot = match.group(1).lower()
        if raw_slot not in SLOT_ALIASES:
            supported = ", ".join(sorted(SLOT_ALIASES))
            raise ValueError(f"Unknown OntoLens slot '{raw_slot}' in {source.path}. Supported slots: {supported}")
        slot = SLOT_ALIASES[raw_slot]
        if slot in markers:
            raise ValueError(f"OntoLens slot '{slot}' occurs more than once in {source.path}")
        markers.append(slot)
        return f'\n\n<div data-ontolens-slot="{slot}"></div>\n\n'

    marked_source = SLOT_MARKER.sub(replace_marker, source.markdown)
    terms = _term_lookup(doc)
    reserved_ids = _reserved_ids(doc)

    def slugify(value: str, separator: str) -> str:
        candidate = markdown_slugify(value, separator) or "section"
        if candidate in reserved_ids:
            return f"content-{candidate}"
        return candidate

    renderer = markdown.Markdown(
        extensions=[
            "extra",
            "sane_lists",
            TocExtension(slugify=slugify),
            _OntologyLinkExtension(terms),
        ],
        output_format="html5",
    )
    rendered = _apply_chapter_markers(renderer.convert(marked_source), reserved_ids)
    rendered, image_sources = _bundle_content_images(rendered, source.path.parent, assets)
    blocks = _split_blocks(rendered)

    explicit_slots = {block.value for block in blocks if block.kind == "slot"}
    if "metadata" not in explicit_slots:
        blocks.insert(0, ContentBlock("slot", "metadata"))

    missing_slots = [
        slot
        for slot in DEFAULT_SLOT_ORDER
        if slot not in explicit_slots and _slot_is_available(slot, doc, quality_report)
    ]
    if "figures" in missing_slots and _all_figures_embedded(doc, image_sources):
        missing_slots.remove("figures")

    cross_reference_index = next(
        (index for index, block in enumerate(blocks) if block.kind == "slot" and block.value == "cross-reference"),
        len(blocks),
    )
    blocks[cross_reference_index:cross_reference_index] = [ContentBlock("slot", slot) for slot in missing_slots]
    if "cross-reference" not in explicit_slots:
        blocks.append(ContentBlock("slot", "cross-reference"))

    return EditorialContent(
        blocks=tuple(blocks),
        language=source.language,
        title=source.title,
        description=source.description,
    )


def _apply_chapter_markers(html: str, reserved_ids: set[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    used = set(reserved_ids) | {tag["id"] for tag in soup.select("[id]")}
    chapters: set[str] = set()
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        text = str(comment).strip()
        if not text.startswith("ontolens:chapter "):
            continue
        key = text.removeprefix("ontolens:chapter ").strip()
        if not re.fullmatch(r"[a-z][a-z0-9-]*", key):
            raise ValueError(f"Invalid OntoLens chapter key '{key}'")
        if key in chapters:
            raise ValueError(f"Duplicate OntoLens chapter key '{key}'")
        heading = comment.find_next_sibling()
        if heading is None or heading.name not in ("h1", "h2", "h3"):
            raise ValueError(f"OntoLens chapter '{key}' must precede a heading (levels 1-3)")
        anchor = f"chapter-{key}"
        if anchor in used and heading.get("id") != anchor:
            raise ValueError(f"OntoLens chapter anchor '{anchor}' is already used")
        heading["id"] = anchor
        heading["data-ontolens-chapter"] = key
        used.add(anchor)
        chapters.add(key)
        comment.extract()
    return str(soup)


def combine_documentation(
    html: str,
    content: EditorialContent,
    doc: OntologyDoc,
    language: str = "en",
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    toc = soup.select_one("aside.toc")
    if not isinstance(main, Tag) or not isinstance(toc, Tag):
        raise ValueError("The OntoLens template does not contain the expected main content and table of contents")

    page_language = (content.language or language or "en").split("-", 1)[0].lower()
    ui = UI_TEXT.get(page_language, UI_TEXT["en"])
    html_tag = soup.find("html")
    if isinstance(html_tag, Tag):
        html_tag["lang"] = content.language or language

    _localize_generated_sections(main, ui)
    sections = {
        section.get("id"): section.extract()
        for section in main.find_all("section", recursive=False)
        if section.get("id")
    }
    main.clear()
    main["class"] = list(dict.fromkeys([*(main.get("class") or []), "editorial-flow"]))

    slot_sections = {
        "metadata": ("metadata", "agents"),
        "figures": ("figures",),
        "quality-report": ("quality-report",),
        "prefixes": ("prefixes",),
        "used-ontologies": ("used-ontologies",),
        "downloads": ("downloads",),
        "visualization": ("visualization",),
        "overview": ("overview",),
        "cross-reference": ("cross-reference",),
    }
    for block in content.blocks:
        if block.kind == "html":
            fragment = BeautifulSoup(block.value, "html.parser")
            for child in list(fragment.contents):
                if isinstance(child, Tag) and child.name not in ("script", "style", "template"):
                    child["data-toc-chapter"] = ""
                main.append(child)
            continue
        for section_id in slot_sections[block.value]:
            section = sections.get(section_id)
            if section is not None:
                main.append(section)

    if main.find("section", id="figures", recursive=False) is None:
        for dialog in soup.select(".figure-zoom"):
            dialog.decompose()

    _build_toc(soup, toc, main, doc, ui)
    style = soup.new_tag("style", attrs={"id": "ontolens-combined-content"})
    style.string = COMBINED_PAGE_CSS
    if soup.head:
        soup.head.append(style)
    return str(soup)


def _split_frontmatter(text: str, path: Path) -> tuple[dict, str]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    lines = text.splitlines(keepends=True)
    closing = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if closing is None:
        raise ValueError(f"Unclosed YAML frontmatter in {path}")
    data = yaml.safe_load("".join(lines[1:closing])) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML frontmatter in {path} must be a mapping")
    return data, "".join(lines[closing + 1 :])


def _optional_string(metadata: dict, key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Frontmatter field '{key}' must be a string")
    return value.strip() or None


def _split_blocks(rendered: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    position = 0
    for match in SLOT_ELEMENT.finditer(rendered):
        html = rendered[position : match.start()].strip()
        if html:
            blocks.append(ContentBlock("html", html))
        blocks.append(ContentBlock("slot", match.group(1)))
        position = match.end()
    tail = rendered[position:].strip()
    if tail:
        blocks.append(ContentBlock("html", tail))
    return blocks


def _term_lookup(doc: OntologyDoc) -> dict[str, TermDoc]:
    result = {}
    for _, terms in _term_groups(doc):
        for term in terms:
            result.setdefault(term.curie, term)
            result.setdefault(term.uri, term)
    return result


def _reserved_ids(doc: OntologyDoc) -> set[str]:
    result = {
        "metadata",
        "agents",
        "figures",
        "quality-report",
        "prefixes",
        "used-ontologies",
        "downloads",
        "visualization",
        "overview",
        "cross-reference",
        "classes",
        "object-properties",
        "datatype-properties",
        "annotation-properties",
        "rdf-properties",
    }
    for _, terms in _term_groups(doc):
        result.update(term.anchor for term in terms)
    return result


def _slot_is_available(slot: str, doc: OntologyDoc, quality_report: bool) -> bool:
    return {
        "figures": bool(doc.hero_figures),
        "quality-report": quality_report,
        "prefixes": bool(doc.prefixes),
        "used-ontologies": bool(doc.used_ontologies),
        "downloads": bool(doc.downloads),
        "visualization": bool(doc.classes or doc.external_classes),
        "overview": True,
    }[slot]


def _all_figures_embedded(doc: OntologyDoc, sources: set[str]) -> bool:
    return bool(doc.hero_figures) and all(figure.src in sources for figure in doc.hero_figures)


def _localize_generated_sections(main: Tag, ui: dict[str, str]) -> None:
    headings = {
        "metadata": "metadata",
        "agents": "agents",
        "figures": "figures",
        "quality-report": "quality-report",
        "prefixes": "prefixes",
        "used-ontologies": "used-ontologies",
        "downloads": "downloads",
        "visualization": "visualization",
        "overview": "overview",
        "cross-reference": "cross-reference",
    }
    for section_id, label_key in headings.items():
        section = main.find("section", id=section_id, recursive=False)
        if isinstance(section, Tag):
            heading = section.find("h2")
            if isinstance(heading, Tag):
                heading.string = ui[label_key]

    cross_reference = main.find("section", id="cross-reference", recursive=False)
    if isinstance(cross_reference, Tag):
        intro = cross_reference.find("p", class_="muted")
        if isinstance(intro, Tag):
            intro.string = ui["reference-intro"]
        for anchor in (
            "classes",
            "object-properties",
            "datatype-properties",
            "annotation-properties",
            "rdf-properties",
        ):
            heading = cross_reference.find("h3", id=anchor)
            if isinstance(heading, Tag):
                heading.string = ui[anchor]


def _build_toc(soup: BeautifulSoup, toc: Tag, main: Tag, doc: OntologyDoc, ui: dict[str, str]) -> None:
    title = toc.select_one(".toc-title")
    title.string = ui["toc"]
    root = toc.select_one("#toc-list")
    root.clear()

    chapter = None
    for child in main.children:
        if not isinstance(child, Tag):
            continue
        if child.name in ("h1", "h2", "h3") and child.get("id"):
            chapter = child["id"]
            child["data-toc-chapter"] = chapter
            level = int(child.name[1])
            css_class = "toc-group" if level == 1 else f"toc-subsection toc-level-{level}"
            link_class = "toc-heading" if level == 1 else None
            root.append(_toc_link_item(soup, child.get_text(" ", strip=True), child["id"], css_class, link_class))
            continue
        if child.has_attr("data-toc-chapter"):
            if not chapter and child.get_text(strip=True):
                chapter = child.get("id") or "editorial-intro"
                if not child.get("id"):
                    while soup.find(id=chapter):
                        chapter += "-intro"
                    child["id"] = chapter
                root.append(_toc_link_item(soup, ui["editorial-intro"], chapter, "toc-subsection"))
            child["data-toc-chapter"] = chapter or ""
            continue
        if child.name != "section" or not child.get("id"):
            continue
        section_id = child["id"]
        heading = child.find("h2")
        if not isinstance(heading, Tag):
            continue
        if section_id == "cross-reference":
            root.append(_reference_toc(soup, doc, ui))
        else:
            root.append(_toc_link_item(soup, heading.get_text(" ", strip=True), section_id, "toc-subsection"))


def _toc_link_item(
    soup: BeautifulSoup,
    title: str,
    anchor: str,
    css_class: str | None = None,
    link_class: str | None = None,
) -> Tag:
    item = soup.new_tag("li")
    if css_class:
        item["class"] = css_class.split()
    link = soup.new_tag("a", attrs={"href": f"#{anchor}"})
    if link_class:
        link["class"] = link_class
    link.string = title
    item.append(link)
    return item


def _reference_toc(soup: BeautifulSoup, doc: OntologyDoc, ui: dict[str, str]) -> Tag:
    item = _toc_link_item(soup, ui["cross-reference"], "cross-reference", "toc-group toc-reference", "toc-heading")
    groups = soup.new_tag("ul", attrs={"class": "toc-reference-groups"})
    opened_group = False
    for anchor, terms in _term_groups(doc):
        if not terms:
            continue
        group_item = soup.new_tag("li")
        details = soup.new_tag("details")
        if not opened_group:
            details["open"] = ""
            opened_group = True
        summary = soup.new_tag("summary")
        label = soup.new_tag("span")
        label.string = ui[anchor]
        count = soup.new_tag("span", attrs={"class": "toc-count"})
        count.string = str(len(terms))
        summary.extend((label, count))
        details.append(summary)
        term_list = soup.new_tag("ul", attrs={"class": "toc-term-list"})
        for term in terms:
            term_list.append(_toc_link_item(soup, term.title, term.anchor))
        details.append(term_list)
        group_item.append(details)
        groups.append(group_item)
    item.append(groups)
    return item


def _term_groups(doc: OntologyDoc):
    return (
        ("classes", doc.classes),
        ("object-properties", doc.object_properties),
        ("datatype-properties", doc.datatype_properties),
        ("annotation-properties", doc.annotation_properties),
        ("rdf-properties", doc.rdf_properties),
    )


class _OntologyLinkInlineProcessor(InlineProcessor):
    def __init__(self, terms: dict[str, TermDoc]):
        super().__init__(WIKI_LINK)
        self.terms = terms

    def handleMatch(self, match, data):
        reference = match.group(1).strip()
        term = self.terms.get(reference)
        if term is None:
            raise ValueError(f"Markdown references unknown ontology term '{reference}'")
        element = ElementTree.Element("a")
        element.set("href", f"#{term.anchor}")
        element.text = (match.group(2) or term.title).strip()
        return element, match.start(0), match.end(0)


class _OntologyLinkExtension(Extension):
    def __init__(self, terms: dict[str, TermDoc]):
        super().__init__()
        self.terms = terms

    def extendMarkdown(self, md):
        md.inlinePatterns.register(_OntologyLinkInlineProcessor(self.terms), "ontolens-wiki-link", 175)


def _bundle_content_images(rendered: str, content_dir: Path, assets: AssetBundle) -> tuple[str, set[str]]:
    soup = BeautifulSoup(rendered, "html.parser")
    sources: set[str] = set()
    for image in soup.find_all("img"):
        src = image.get("src")
        if not src:
            continue
        if _is_external_or_embedded(src):
            sources.add(src)
            continue
        parsed = urlsplit(src)
        source_path = Path(src) if Path(src).is_absolute() else content_dir / unquote(parsed.path)
        bundled = assets.copy_image(source_path)
        if parsed.query:
            bundled += f"?{parsed.query}"
        if parsed.fragment:
            bundled += f"#{parsed.fragment}"
        image["src"] = bundled
        sources.add(bundled)
    return str(soup), sources


def _is_external_or_embedded(src: str) -> bool:
    if Path(src).is_absolute():
        return False
    parsed = urlsplit(src)
    return bool(parsed.scheme or parsed.netloc or src.startswith(("/", "#", "data:")))
