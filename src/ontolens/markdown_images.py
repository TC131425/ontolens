"""Inspect editorial images without fetching remote URLs or copying files."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown
from bs4 import BeautifulSoup

from .content import EditorialSource


IMAGE_TYPES = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml', '.gif': 'image/gif', '.webp': 'image/webp',
    '.avif': 'image/avif', '.bmp': 'image/bmp', '.ico': 'image/x-icon',
}


@dataclass(frozen=True)
class MarkdownImage:
    src: str
    alt: str
    path: Path | None = None
    error: str = ''


def inspect_images(source: EditorialSource) -> list[MarkdownImage]:
    rendered = markdown.markdown(source.markdown, extensions=['extra', 'sane_lists'])
    images = []
    seen = set()
    for tag in BeautifulSoup(rendered, 'html.parser').find_all('img'):
        src = str(tag.get('src', ''))
        if not src or src in seen:
            continue
        seen.add(src)
        alt = str(tag.get('alt', ''))
        try:
            parsed = urlsplit(src)
            if not Path(src).is_absolute() and (parsed.scheme or parsed.netloc):
                allowed = parsed.scheme.lower() in {'http', 'https'} or not parsed.scheme
                allowed = allowed or src.lower().startswith('data:image/')
                images.append(MarkdownImage(src, alt, error='' if allowed else 'Nicht unterstuetzte Bildadresse.'))
                continue
            path = (Path(src) if Path(src).is_absolute() else source.path.parent / unquote(parsed.path)).resolve()
            if not path.is_file():
                error = 'Bilddatei nicht gefunden. Pfad relativ zur Markdown-Datei pruefen.'
            elif path.suffix.lower() not in IMAGE_TYPES:
                error = 'Dieses Dateiformat kann nicht als Bild angezeigt werden.'
            else:
                error = ''
            images.append(MarkdownImage(src, alt, path, error))
        except (OSError, ValueError):
            images.append(MarkdownImage(src, alt, error='Bildpfad ist ungueltig oder nicht lesbar.'))
    return images
