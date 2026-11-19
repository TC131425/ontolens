from dataclasses import asdict
from pathlib import Path
from shutil import copy2
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from .abox_model import ABoxDoc
from .abox_parser import load_abox
from .assets import inline_script, inline_style
from .render import _timestamped_output_path


def render_abox(doc: ABoxDoc, language: str = "de", max_nodes: int = 250, source_href: str = "") -> str:
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    env = Environment(loader=PackageLoader("ontolens", "templates"), autoescape=select_autoescape(("j2",)))
    records = {item.resource.id: {"instance": item, "anchor": f"record-{index}", "outgoing": [], "incoming": []}
               for index, item in enumerate(doc.instances, 1)}
    for relation in doc.relations:
        records[relation.source]["outgoing"].append(relation)
        records[relation.target]["incoming"].append(relation)
    return env.get_template("abox.html.j2").render(doc=doc, data=asdict(doc), language=language,
                                                  max_nodes=max_nodes, source_href=source_href, records=records,
                                                  inline_script=inline_script, inline_style=inline_style)


def generate_abox(input_path: Path, output_path: Path, rdf_format: str | None = None,
                  language: str = "de", max_nodes: int = 250) -> Path:
    doc = load_abox(input_path, rdf_format, language)
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    output = _timestamped_output_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    downloads = output.parent / "downloads"
    downloads.mkdir(exist_ok=True)
    copy2(input_path, downloads / input_path.name)
    output.write_text(render_abox(doc, language, max_nodes, "downloads/" + quote(input_path.name)), encoding="utf-8")
    return output
