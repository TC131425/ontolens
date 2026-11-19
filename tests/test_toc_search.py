import os

import pytest
from bs4 import BeautifulSoup

from ontolens.render import generate
from test_content import CONTENT, _write_fixture


def search_page(tmp_path, combined):
    content = CONTENT.replace("<!-- ontolens:metadata -->", "Vorwort ohne Überschrift.\n\n<!-- ontolens:metadata -->")
    content = content.replace("## Usage", "Eine **separate** Textpassage.\n\n## Usage")
    ontology, markdown, output = _write_fixture(tmp_path, content)
    with ontology.open('a', encoding='utf-8') as source:
        source.write('\nex:Thing rdfs:label "Beispiel"@de, "Chose"@fr, "Oggetto"@it, "Objekt [x]"@sv .')
        source.write('\nex:Thing rdfs:comment "' + 'Ein langer Absatz. ' * 16 + 'Austauschformat für Modelle."@de .')
        source.write('\nex:relatedTo <http://purl.org/dc/terms/description> "Datenübergabe"@de .')
        source.write('\n<https://example.org/ontology> rdfs:comment "Projektplanung"@de ; '
                     '<http://purl.org/dc/terms/description> "Bauvorhaben"@de .')
    return generate(ontology, output, content_path=markdown if combined else None,
                    language='en', theme='dark' if combined else 'light')


@pytest.mark.parametrize('combined', [False, True])
def test_offline_search_markup(tmp_path, combined):
    path = search_page(tmp_path, combined)
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    assert len(soup.select('aside.toc input[type=search][aria-controls=toc-list]')) == 1
    assert soup.select_one('#toc-list a[href="#Thing"]')
    assert soup.select_one('#Thing .term-label[lang=sv]').string == 'Objekt [x]'
    assert soup.select_one('#Thing .term-curie').string == 'ex:Thing'
    assert soup.select_one('#Thing .term-iri')['href'] == 'https://example.org/ontology#Thing'
    assert not soup.select('script[src]')
    assert len(soup.select('.toc-scopes input[checked]')) == (4 if combined else 3)
    assert soup.select_one('#relatedTo [data-toc-text=Description]').text == 'Datenübergabe'
    assert {e.text for e in soup.select('#metadata [data-toc-text=Description]')} == {'Projektplanung', 'Bauvorhaben'}
    if combined:
        assert soup.select_one('p#editorial-intro')['data-toc-chapter'] == 'editorial-intro'
        assert not soup.select('#cross-reference[data-toc-chapter]')


@pytest.mark.skipif(os.getenv('ONTOLENS_TEST_BROWSER') != '1', reason='Requires local Chromium/Playwright')
@pytest.mark.parametrize('combined', [False, True])
def test_filter_highlight_and_reset_in_browser(tmp_path, combined):
    from playwright.sync_api import sync_playwright

    path = search_page(tmp_path, combined)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv('ONTOLENS_BROWSER_CHANNEL'))
        page = browser.new_page(offline=True)
        page.goto(path.as_uri())
        toc = page.locator('aside.toc')
        search = toc.get_by_role('searchbox')
        hit = toc.locator('a[href="#Thing"]')
        other = toc.locator('a[href="#relatedTo"]')
        groups = toc.locator('#toc-list details')
        if combined:
            groups.first.locator('summary').click()
            groups.nth(1).locator('summary').click()
        initial = groups.evaluate_all('(groups) => groups.map(g => g.open)')
        original_body = page.locator('main').inner_text()
        for query in ['chose', 'ex:Thing', 'https://example.org/ontology#Thing', '[x]']:
            search.fill(query)
            assert hit.is_visible() and not other.is_visible()
            assert hit.locator('mark').inner_text().lower() == query.lower()
            assert toc.get_by_role('status').inner_text() == ('1 Treffer' if combined else '1 match')
        assert page.locator('main').inner_text() == original_body
        hit.click()
        assert page.url.endswith('#Thing')
        assert page.locator('#Thing > .toc-jump-highlight').count() == 1
        search.fill('no such term')
        assert not toc.locator('li:visible').count()
        assert toc.get_by_role('status').inner_text() == ('Keine Treffer' if combined else 'No matches')
        search.press('Escape')
        assert groups.evaluate_all('(groups) => groups.map(g => g.open)') == initial
        assert not toc.locator('mark, li[hidden]').count()
        search.fill('Thing')
        toc.locator('.toc-search-box button').click()
        assert search.input_value() == ''
        assert hit.text_content() == 'Thing'
        toc.locator('.toc-scopes summary').click()
        def scope(name):
            return toc.locator(f'input[value="{name}"]')

        search.fill('ex:Thing')
        scope('iris').uncheck()
        assert not hit.is_visible()
        scope('iris').check()
        assert hit.is_visible()
        search.fill('Chose')
        scope('names').uncheck()
        assert not hit.is_visible()
        scope('names').check()
        assert hit.is_visible()
        search.fill('Austauschformat')
        assert hit.locator('mark').inner_text() == 'Austauschformat'
        assert len(hit.locator('.toc-match-field').inner_text()) < 140
        assert '…' in hit.inner_text() and 'de' in hit.inner_text()
        scope('prose').uncheck()
        assert not toc.locator('li:visible').count()
        scope('prose').check()
        assert hit.is_visible()
        for query, anchor in [('Datenübergabe', 'relatedTo'), ('Bauvorhaben', 'metadata'), ('Projektplanung', 'metadata')]:
            search.fill(query)
            assert toc.locator(f'a[href="#{anchor}"] mark').inner_text() == query
            assert toc.locator('a mark').count() == 1
        if combined:
            search.fill('separate Textpassage')
            result = toc.locator('a').filter(has=page.locator('mark'))
            assert 'Introduction' in result.inner_text()
            assert 'Kapiteltext' in result.inner_text()
            scope('markdown').uncheck()
            assert not toc.locator('li:visible').count()
            scope('markdown').check()
            search.fill('Vorwort')
            assert toc.locator('a[href="#editorial-intro"] mark').inner_text() == 'Vorwort'
        for box in toc.locator('.toc-scopes input').all():
            box.uncheck()
        assert toc.get_by_role('status').inner_text() == ('Bitte einen Suchbereich auswählen.' if combined else 'Select a search area.')
        assert page.locator('main').inner_text() == original_body
        browser.close()
