"""Structural completeness checks for editorial Markdown, independent of RDF quality."""

from dataclasses import dataclass

import markdown
from bs4 import BeautifulSoup, Comment, Tag

from .content import EditorialSource, _apply_chapter_markers
from .scaffold import CHAPTERS, COMPACT


@dataclass(frozen=True)
class ContentIssue:
    chapter: str
    title: str
    kind: str


def check_content(source: EditorialSource) -> tuple[ContentIssue, ...]:
    if source.profile not in {"compact", "standard"}:
        raise ValueError("Content profile must be 'compact' or 'standard'")
    html = markdown.markdown(source.markdown, extensions=["extra"])
    soup = BeautifulSoup(_apply_chapter_markers(html, set()), "html.parser")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for element in soup.select("script, style"):
        element.decompose()

    headings = soup.find_all(["h1", "h2", "h3"])
    issues = []
    german = (source.language or "en").lower().split("-")[0] == "de"
    for key, de, en, *_ in CHAPTERS:
        if source.profile == "compact" and key not in COMPACT:
            continue
        aliases = {key.casefold(), de.casefold(), en.casefold()}
        matches = [heading for heading in headings if
                   heading.get("data-ontolens-chapter") == key or
                   (not heading.has_attr("data-ontolens-chapter") and
                    heading.get_text(" ", strip=True).casefold() in aliases)]
        title = de if german else en
        if not matches:
            issues.append(ContentIssue(key, title, "missing"))
        elif not any(_has_content(heading) for heading in matches):
            issues.append(ContentIssue(key, title, "empty"))
    return tuple(issues)


def _has_content(heading: Tag) -> bool:
    level = int(heading.name[1])
    for sibling in heading.next_siblings:
        if isinstance(sibling, Tag):
            if sibling.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                if int(sibling.name[1]) <= level or sibling.has_attr("data-ontolens-chapter"):
                    break
                continue
            if sibling.name in {"img", "svg", "video", "audio"} or sibling.find(["img", "svg", "video", "audio"]):
                return True
            if sibling.get_text(strip=True):
                return True
        elif str(sibling).strip():
            return True
    return False
