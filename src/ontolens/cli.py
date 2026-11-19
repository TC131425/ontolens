from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .render import generate


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "abox":
        return _build_abox(argv[1:])
    if argv and argv[0] == "init-content":
        return _init_content(argv[1:])
    if argv and argv[0] == "build":
        return _build_project(argv[1:])
    if argv and argv[0] == "pack":
        return _pack_project(argv[1:])
    if argv and argv[0] == "pdf":
        return _export_pdf(argv[1:])
    parser = argparse.ArgumentParser(description="Generate static HTML documentation for RDF/OWL ontologies.")
    parser.epilog = "Create a Markdown template with: ontolens init-content INPUT --language de --profile standard"
    parser.add_argument("input", type=Path, help="Input ontology file (.ttl, .rdf, .nt, .jsonld).")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML name. Defaults to build/<input-stem>/<input-stem>.html relative to the working directory; builds use timestamped directories.",
    )
    parser.add_argument("--format", help="RDFLib parser format, e.g. turtle, xml, nt, json-ld.")
    parser.add_argument("--language", help="Preferred language for labels and comments. Defaults to the Markdown language or en.")
    parser.add_argument(
        "--content",
        type=Path,
        help="Optional Markdown file for a combined narrative and technical documentation page.",
    )
    parser.add_argument("--recommendations", action="store_true", help="Show missing recommended ontology metadata fields as placeholders.")
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="light", help="Fixed HTML color scheme; both creates light/ and dark/ variants.")
    parser.add_argument("--custom-annotations", action="store_true", help="Include custom owl:AnnotationProperty values in term tables.")
    parser.add_argument("--show-missing-endpoints", action="store_true", help="Show graph placeholders for object properties missing either domain or range (not both).")
    parser.add_argument("--include-external-classes", action=argparse.BooleanOptionalAction, default=False, help="Include every explicitly declared external class in the graph, even without a connection to local terms.")
    parser.add_argument("--quality-report", action="store_true", help="Include the ontology quality report.")
    parser.add_argument("--check-content", action="store_true", help="Report missing or empty Markdown chapters without blocking the HTML build; requires --content.")
    parser.add_argument("--skip-missing-images", action="store_true", help="Skip missing ontology figures with a warning (Markdown images remain required).")
    args = parser.parse_args(argv)
    if args.check_content and not args.content:
        parser.error("--check-content requires --content")

    if args.check_content:
        from .content import read_editorial_source
        from .content_check import check_content

        source = read_editorial_source(args.content)
        try:
            issues = check_content(source)
        except ValueError as error:
            parser.error(str(error))
        german = (source.language or args.language or "en").lower().split("-")[0] == "de"
        print(f"Markdown ({source.profile}): {len(issues)} " + ("Hinweis(e)" if german else "notice(s)"), file=sys.stderr)
        for issue in issues:
            status = ({"missing": "fehlt", "empty": "leer"} if german else {"missing": "missing", "empty": "empty"})[issue.kind]
            print(f"  [{issue.chapter}] {issue.title}: {status}", file=sys.stderr)

    output = args.output or Path("build") / args.input.stem / f"{args.input.stem}.html"
    generated = generate(
        args.input,
        output,
        rdf_format=args.format,
        language=args.language,
        content_path=args.content,
        recommendations=args.recommendations,
        quality_report=args.quality_report,
        include_custom_annotations=args.custom_annotations,
        show_missing_endpoints=args.show_missing_endpoints,
        include_external_classes=args.include_external_classes,
        skip_missing_images=args.skip_missing_images,
        theme=args.theme,
    )
    print(f"Generated {generated}")
    if args.theme == 'both':
        print(f"Generated {generated.parent.parent / 'dark' / generated.name}")
    return 0


def _export_pdf(argv: list[str]) -> int:
    import shutil
    import tempfile
    from .pdf_export import PdfOptions, render_pdf
    parser = argparse.ArgumentParser(prog='ontolens pdf', description='Print existing HTML documentation as light, paginated PDF.')
    parser.add_argument('input', type=Path, nargs='+', help='Existing HTML files. Multiple files produce a ZIP with individual PDFs.')
    parser.add_argument('-o', '--output', type=Path, help='Output name; a timestamped folder is created.')
    parser.add_argument('--paper', choices=['A4', 'A3'], default='A4')
    parser.add_argument('--figures', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--graph', action='store_true')
    args = parser.parse_args(argv)
    if len(args.input) > 20:
        parser.error('At most 20 HTML files per export.')
    suffix = '.pdf' if len(args.input) == 1 else '.zip'
    output = (args.output or Path('build') / 'pdf' / args.input[0].stem).with_suffix(suffix)
    folder = output.parent / f'{datetime.now():%Y-%m-%dT%H-%M-%S}_{output.stem}'
    try:
        with tempfile.TemporaryDirectory(prefix='ontolens-pdf-') as temporary:
            root = Path(temporary)
            for index, source in enumerate(args.input):
                page = root / 'documents' / f'{index + 1}-{source.stem}.pdf'
                notices = render_pdf(source, page, PdfOptions(args.paper, args.figures, args.graph))
                for notice in notices:
                    print(f'{source.name}: {notice}', file=sys.stderr)
            result = page if suffix == '.pdf' else Path(shutil.make_archive(str(root / 'documents'), 'zip', root / 'documents'))
            folder.mkdir(parents=True, exist_ok=False)
            shutil.copy2(result, folder / output.name)
    except (OSError, ValueError, KeyError, SyntaxError, RuntimeError) as error:
        parser.error(str(error))
    print(f'Created {folder / output.name}')
    return 0


def _pack_project(argv: list[str]) -> int:
    import json
    import shutil
    import tempfile
    import yaml
    from rdflib.exceptions import ParserError
    from .project_archive import create_project_archive

    parser = argparse.ArgumentParser(prog='ontolens pack', description='Export a portable project ZIP.')
    parser.add_argument('config', type=Path)
    parser.add_argument('-o', '--output', type=Path, help='ZIP filename; placed in a timestamped directory.')
    parser.add_argument('--include-outputs', action='store_true', help='Include currently assigned HTML documents and portals, not build history.')
    args = parser.parse_args(argv)
    output = args.output or Path('build') / args.config.stem / 'project.zip'
    output = output.with_suffix('.zip')
    folder = output.parent / f'{datetime.now():%Y-%m-%dT%H-%M-%S}_{output.stem}'
    try:
        state = args.config.with_suffix('.outputs.json')
        assignments = json.loads(state.read_text(encoding='utf-8')) if args.include_outputs and state.exists() else {}
        with tempfile.TemporaryDirectory(prefix='ontolens-project-') as temporary:
            archive, notices = create_project_archive(args.config, Path(temporary), include_outputs=args.include_outputs, assignments=assignments)
            folder.mkdir(parents=True, exist_ok=False)
            shutil.copy2(archive, folder / output.name)
        for notice in notices:
            print(notice, file=sys.stderr)
    except (OSError, ValueError, KeyError, SyntaxError, ParserError, yaml.YAMLError) as error:
        parser.error(str(error))
    print(f'Created {folder / output.name}')
    return 0


def _build_abox(argv: list[str]) -> int:
    from .abox_render import generate_abox
    from rdflib.exceptions import ParserError
    parser = argparse.ArgumentParser(prog="ontolens abox", description="Generate an interactive A-Box knowledge graph document.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--format")
    parser.add_argument("--language", default="de", help="Preferred RDF label language.")
    parser.add_argument("--max-nodes", type=int, default=250, help="Maximum visible graph nodes; all instance details remain searchable.")
    args = parser.parse_args(argv)
    if args.max_nodes < 1:
        parser.error("--max-nodes must be positive")
    output = args.output or Path("build") / args.input.stem / f"{args.input.stem}-abox.html"
    try:
        result = generate_abox(args.input, output, args.format, args.language, args.max_nodes)
    except (ValueError, OSError, SyntaxError, ParserError) as error:
        parser.error(str(error))
    print(f"Generated {result}")
    return 0


def _build_project(argv: list[str]) -> int:
    import yaml
    from .project import BOOLEAN_OPTIONS, build_project, load_project

    parser = argparse.ArgumentParser(prog="ontolens build", description="Build a configured ontology project and optional static portal.")
    parser.add_argument("config", type=Path, help="Project YAML file; relative paths are resolved beside this file.")
    parser.add_argument("--ontology", action="append", help="Build only this ontology id; repeat to select several.")
    parser.add_argument("--output", type=Path, help="Override the project output directory, relative to the working directory.")
    parser.add_argument("--language")
    parser.add_argument("--format")
    parser.add_argument("--theme", choices=("light", "dark", "both"))
    parser.add_argument("--portal", action=argparse.BooleanOptionalAction, default=None)
    for name in sorted(BOOLEAN_OPTIONS):
        parser.add_argument("--" + name.replace("_", "-"), action=argparse.BooleanOptionalAction, default=None)
    args = parser.parse_args(argv)
    try:
        from dataclasses import replace
        project = load_project(args.config)
        if args.output:
            project = replace(project, output=args.output.resolve())
        overrides = {name: getattr(args, name) for name in BOOLEAN_OPTIONS | {"language", "format", "theme"} if getattr(args, name) is not None}
        result = build_project(project, args.ontology, overrides, args.portal)
    except (ValueError, OSError, yaml.YAMLError) as error:
        parser.error(str(error))
    for notice in result.notices:
        print(f"Markdown: {notice}", file=sys.stderr)
    for page in result.pages:
        print(f"Generated {page}")
    if result.portal:
        print(f"Portal {result.portal}")
        dark_portal = result.directory / 'dark' / 'index.html'
        if dark_portal.is_file():
            print(f"Portal {dark_portal}")
    return 0


def _init_content(argv: list[str]) -> int:
    from .scaffold import create_content

    parser = argparse.ArgumentParser(prog="ontolens init-content", description="Create an editable Markdown documentation template.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Explicit Markdown file path; by default creates a timestamped template under build/<input-stem>/.")
    parser.add_argument("--format", help="RDFLib input format.")
    parser.add_argument("--language", choices=("de", "en"), default="en")
    parser.add_argument("--profile", choices=("compact", "standard"), default="standard")
    args = parser.parse_args(argv)
    filename = f"{args.input.stem}-documentation.{args.language}.md"
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    output = args.output or Path("build") / args.input.stem / f"{timestamp}_{Path(filename).stem}" / filename
    try:
        create_content(args.input, output, args.language, args.profile, args.format)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Created {output}")
    return 0
