from pathlib import Path

import pytest

from ontolens.cli import main
from ontolens.content import EditorialSource, read_editorial_source
from ontolens.content_check import check_content
from ontolens.scaffold import create_content
from test_content import _write_fixture


def check(body, profile="compact"):
    return {issue.chapter: issue.kind for issue in check_content(EditorialSource(Path("test.md"), body, profile=profile))}


def test_empty_comments_slots_and_subheadings():
    issues = check('# Introduction\n<!-- hint -->\n\n## Motivation\n\n<!-- ontolens:metadata -->\n\n# Scope and requirements\nSome scope.')
    assert issues == {"introduction": "empty", "conceptual-model": "missing", "usage": "missing"}


def test_translated_and_custom_titles_and_nested_content():
    body = '''<!-- ontolens:chapter introduction -->
# Freely named
## Audience
Users.
# Umfang und Anforderungen
Scope.
# Conceptual model
![Model](model.svg)
# Usage and examples
```turtle
ex:a a ex:B .
```
'''
    assert check(body) == {}


def test_fenced_markers_do_not_create_chapters():
    assert check('```markdown\n<!-- ontolens:chapter introduction -->\n# Introduction\n```')["introduction"] == "missing"


@pytest.mark.parametrize("profile,count", [("compact", 4), ("standard", 9)])
def test_generated_templates_are_empty(tmp_path, profile, count):
    ontology, _, _ = _write_fixture(tmp_path)
    output = tmp_path / "template.md"
    create_content(ontology, output, profile=profile)
    source = read_editorial_source(output)
    assert source.profile == profile
    issues = check_content(source)
    assert len(issues) == count
    assert all(issue.kind == "empty" for issue in issues)


def test_cli_opt_in_and_nonblocking(tmp_path, capsys):
    ontology, content, output = _write_fixture(tmp_path, '# Introduction\n<!-- TODO -->')
    args = [str(ontology), "--content", str(content), "-o", str(output)]
    assert main(args) == 0
    assert "Markdown" not in capsys.readouterr().err
    assert main([*args, "--check-content"]) == 0
    assert "Introduction: empty" in capsys.readouterr().err
    assert list(output.parent.glob("*/index.html"))


def test_cli_requires_content(tmp_path):
    with pytest.raises(SystemExit) as error:
        main([str(tmp_path / "unused.ttl"), "--check-content"])
    assert error.value.code == 2


def test_invalid_profile():
    with pytest.raises(ValueError, match="profile"):
        check("# Introduction", "typo")
