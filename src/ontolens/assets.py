from __future__ import annotations

import shutil
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from xml.etree import ElementTree

from markupsafe import Markup


@lru_cache(maxsize=None)
def inline_script(filename: str, license_filename: str | None = None) -> Markup:
    static = Path(__file__).parent / "static"
    source = (static / filename).read_text(encoding="utf-8")
    source = re.sub(r"(?m)^[ \t]*//[#@]\s*sourceMappingURL=.*$", "", source)
    if license_filename:
        license_text = (static / license_filename).read_text(encoding="utf-8")
        source = "/*!\n" + license_text.replace("*/", "* /") + "\n*/\n" + source
    # Only bundled code reaches this helper; prevent raw-text HTML end tags.
    return Markup(re.sub(r"</script", lambda match: "<\\/" + match[0][2:], source, flags=re.IGNORECASE))


@lru_cache(maxsize=None)
def inline_style(filename: str) -> Markup:
    source = (Path(__file__).parent / "static" / filename).read_text(encoding="utf-8")
    return Markup(re.sub(r"</style", lambda match: "<\\/" + match[0][2:], source, flags=re.IGNORECASE))


class AssetBundle:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.image_dir = self.output_dir / "img"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._sources: dict[Path, str] = {}
        self._targets: set[str] = set()

    def copy_image(self, source: Path) -> str:
        source = source.resolve()
        if source in self._sources:
            return self._sources[source]
        if not source.is_file():
            raise FileNotFoundError(f"Image does not exist: {source}")

        filename = self._available_filename(source.name)
        shutil.copy2(source, self.image_dir / filename)
        href = f"img/{filename}"
        self._sources[source] = href
        self._targets.add(filename.lower())
        if source.suffix.lower() == '.svg':
            try:
                tree = ElementTree.parse(source)
            except ElementTree.ParseError as error:
                raise ValueError(f'Invalid SVG image: {source}') from error
            changed = False
            for node in tree.iter():
                if node.tag.rsplit('}', 1)[-1] not in {'image', 'use'}:
                    continue
                for attribute in ('href', '{http://www.w3.org/1999/xlink}href'):
                    ref = node.get(attribute)
                    if not ref:
                        continue
                    url = urlsplit(ref)
                    if url.netloc or not url.path or url.scheme not in {'', 'file'}:
                        continue
                    dependency = Path(url2pathname(url.path)) if url.scheme == 'file' else source.parent / unquote(url.path)
                    copied = self.copy_image(dependency)
                    node.set(attribute, Path(copied).name + ('#' + url.fragment if url.fragment else ''))
                    changed = True
            if changed:
                tree.write(self.image_dir / filename, encoding='utf-8', xml_declaration=True)
        return href

    def _available_filename(self, filename: str) -> str:
        candidate = filename
        stem = Path(filename).stem or "image"
        suffix = Path(filename).suffix
        counter = 2
        while candidate.lower() in self._targets:
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1
        return candidate
