import os
from urllib.parse import urlsplit

import pytest


@pytest.mark.skipif(not os.getenv("ONTOLENS_GUI_URL"), reason="Requires the local GUI server")
def test_language_switch_preserves_drafts_and_document_language():
    from playwright.sync_api import expect, sync_playwright

    entry = dict(id="demo", name="Projekte", base="", path="/demo.yaml", count=1, available=True)
    ontology = dict(id="Modell", input="/modell.ttl", content="/text.md", options={"language": "de"})
    project = dict(name="Projekte", config="/demo.yaml", output="/out", revision="1",
                   ontologies=[ontology], notices=[], portal={"title": "Portal", "enabled": True})
    writes = []

    def api(route):
        path = urlsplit(route.request.url).path
        if route.request.method != "GET":
            writes.append(path)
        payloads = {
            "/api/projects": {"projects": [entry]},
            "/api/project": project,
            "/api/ontologies/Modell/markdown": {"content": "# Mein Text", "content_revision": "a"},
            "/api/ontologies/Modell/markdown/images": {"images": []},
            "/api/runtime": {"file_browser": True, "root": "/data"},
            "/api/files": {"path": "/data", "parent": None, "entries": []},
        }
        route.fulfill(json=payloads[path])

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.getenv("ONTOLENS_BROWSER_CHANNEL"))
        page = browser.new_page(locale="en-US")
        page.route("**/api/**", api)
        page.goto(os.environ["ONTOLENS_GUI_URL"])
        language = page.locator(".ui-language select")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.get_by_role("button", name="New project", exact=True).click()
        page.get_by_label("Project name", exact=True).fill("Mein Projekt")
        language.select_option("de")
        expect(page.get_by_label("Projektname", exact=True)).to_have_value("Mein Projekt")
        page.reload()
        expect(page.locator("html")).to_have_attribute("lang", "de")
        language.select_option("en")
        page.get_by_role("button", name="New project", exact=True).click()
        page.get_by_role("button", name="Choose project folder").click()
        expect(page.get_by_role("dialog")).to_contain_text("Use this folder")
        page.get_by_role("dialog").get_by_role("button", name="Cancel").first.click()
        page.get_by_role("button", name="Open Projekte", exact=True).click()
        expect(page.get_by_label("Document language", exact=True)).to_have_value("de")
        page.get_by_role("tab", name="Markdown", exact=True).click()
        page.get_by_role("button", name="Edit", exact=True).click()
        page.get_by_role("textbox", name="Edit Markdown").fill("# Ungespeichert")
        language.select_option("de")
        expect(page.get_by_role("textbox", name="Markdown bearbeiten")).to_have_value("# Ungespeichert")
        expect(page.get_by_label("Dokumentsprache", exact=True)).to_have_value("de")
        assert set(writes) <= {"/api/ontologies/Modell/markdown/images"}
        browser.close()
