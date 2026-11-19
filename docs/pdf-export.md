# Dokumentationen als PDF exportieren

## In der Oberfläche

Unter **Projekteinstellungen → Projekt weitergeben → Dokumentation als PDF**:

1. Gewünschte Dokumente auswählen: HTML-Dokumentation und/oder HTML + Markdown
   pro Ontologie. Nur vorhandene, verknüpfte HTML-Dateien sind auswählbar.
2. Papierformat **A4** (Standard) oder **A3** wählen. Der Text verwendet Hochformat,
   der optionale Graph erhält immer eine eigene Querformatseite desselben Formats.
3. **Abbildungen einschließen** ist standardmäßig an, **Ontologiegraph ins PDF aufnehmen** aus.
   Beide Checkboxen sind unabhängig: Der Graph kann auch ohne andere Abbildungen exportiert werden.
4. **PDF exportieren** anklicken und anschließend den Downloadlink verwenden.

Ein Dokument ergibt eine PDF. Mehrere Dokumente ergeben einen ZIP-Download mit
je einer PDF pro ausgewähltem Dokument. Maximal 20 Dokumente pro Vorgang.
Die gesamte Dokumentation wird exportiert; Kapitelauswahl und zusammengeführte
Gesamt-PDF sind nicht Bestandteil dieser ersten Version.

Die PDF basiert auf der **gespeicherten HTML-Datei**, nicht auf einer neu
eingelesenen Ontologie. Nach Änderungen an Quelle oder Markdown die
HTML-Dokumentation zuerst neu generieren. Keine Quelldatei, HTML-Datei oder
Verknüpfung wird durch den PDF-Export verändert.

## Drucklayout

- Immer helles Drucklayout, auch bei dunkel erzeugten HTML-Dateien.
- Offene Restrictions und Instanzlisten, ohne interaktive Bedienelemente.
- Klickbares Kapitel-Inhaltsverzeichnis, PDF-Lesezeichen und interne Termverweise.
- Dokumenttitel in der Kopfzeile, Seitenzahl und Gesamtseitenzahl im Fußbereich.
- Tabellen mit festen Spalten, Zeilenumbrüchen und Druck-Seitenumbrüchen.
- Abbildungen werden proportional auf die verfügbare Seitenfläche begrenzt.
- Der Graph wird aus den in der HTML-Datei gespeicherten OntoLens-Graphdaten mit
  der mitgelieferten Cytoscape-Version kompakt angeordnet, mit vergrößerten Knoten-
  und Kantenbeschriftungen versehen und als hochauflösende PNG
  eingebettet. Er ist statisch: aktuelle Zoom-/Filter-/Drag-Zustände eines offenen
  Browserfensters werden nicht übernommen. Fachliche Detailtabellen bleiben enthalten.
- Graphen mit mehreren getrennten Komponenten verwenden dieselbe kompakte
  Netzwerk-Anordnung wie die HTML-Ansicht: Zusammenhaengende Klassen bleiben
  gruppiert, isolierte Klassen werden in mehreren Reihen angeordnet. Lange
  Klassennamen werden mit Praefix umbrochen, ohne die gespeicherten IRIs zu aendern.
  Kantenbeschriftungen werden um Knoten und andere Beschriftungen herum platziert.
  Zusammenhaengende Graphen behalten das bisherige druckoptimierte Raster.
  Titel, Legende und Graph teilen sich eine Querformatseite; die Grafik nutzt den
  verbleibenden Platz proportional, statt auf eine separate Seite umzubrechen.

Bei großen Graphen A3 verwenden oder den Graph weglassen. Auch eine hohe
Bildauflösung kann sehr kleine Beschriftungen bei vielen Knoten nicht verhindern.
Fehlen Graphdaten in einer älteren/manuell zugeordneten HTML-Datei, wird das als
Hinweis gemeldet. Mehr als 1000 Knoten oder 3000 Kanten blockieren den Graphexport;
der Export ohne Graph bleibt möglich.

## Dateien und Sicherheit

Der Renderer führt keine Skripte aus der HTML-Dokumentation aus und lädt keine
Netzwerkressourcen. Nur der mit OntoLens ausgelieferte Graph-Code wird ausgeführt.
Lokale Bilder müssen im Dokumentationsordner bzw. zugeordneten Export-Bundle liegen.
Fehlende lokale Bilder verhindern den Export, sofern Abbildungen eingeschlossen sind.
Online-Bilder erscheinen als Texthinweis und werden zusätzlich in den PDF-Hinweisen
gemeldet. Externe CSS-Dateien und Webfonts werden nicht nachgeladen; das Drucklayout
verwendet lokale Schriften. Fremde HTML-Seiten mit eigenem JavaScript werden nicht
wie in einem normalen Browser ausgeführt.

In der GUI werden temporäre Serverdateien nach der Übertragung gelöscht. Der
Browser bestimmt den Downloadordner. Der PDF-Export erstellt keine zusätzliche
HTML-Verknüpfung oder Build-Historie im Arbeitsprojekt.

## Installation und Docker

Docker enthält den Renderer bereits. Der erste Image-Build dauert wegen Chromium,
Schriften und Systembibliotheken länger; das Image ist entsprechend größer.
Es werden keine zusätzlichen Ports oder Host-Verzeichnisse benötigt.

Für eine lokale Python-Installation:

```console
uv sync --extra web --extra pdf
uv run --extra web --extra pdf python -m playwright install --only-shell chromium
```

Unter Linux bei fehlenden Systembibliotheken:

```console
uv run --extra web --extra pdf python -m playwright install --with-deps --only-shell chromium
```

Die API ebenfalls mit beiden Extras starten, damit `uv` die PDF-Abhängigkeit
nicht wieder entfernt. Ohne PDF-Extra funktionieren die bisherigen CLI-Befehle
weiter; ein PDF-Aufruf meldet die fehlende Komponente.

## CLI

```console
uv run --extra pdf ontolens pdf path/to/documentation.html -o build/ontology.pdf
uv run --extra pdf ontolens pdf path/to/documentation.html --paper A3 --graph -o build/ontology.pdf
uv run --extra pdf ontolens pdf first.html second.html --no-figures -o build/documents.zip
```

Ausgaben landen in Zeitstempelordnern, etwa
`build/2026-10-29T16-30-00_ontology/ontology.pdf`.
Die Endung wird passend zur Anzahl der Eingaben auf `.pdf` bzw. `.zip` gesetzt.
CLI-Bildpfade müssen innerhalb des Ordners der jeweiligen HTML-Datei liegen.

Im Container:

```console
docker compose exec ontolens ontolens pdf /data/project/build/documentation.html --paper A4 -o /data/exports/documentation.pdf
```

## API und Tests

`POST /api/project/pdf` benötigt `X-Ontolens-Write: 1`, die aktuelle `revision`
und `documents: [{"ontology": "id", "kind": "reference"}]`.
`kind` ist `reference` oder `combined`. Weitere Felder: `paper` (`A4`/`A3`),
`figures` (Standard `true`) und `graph` (Standard `false`). Antwort: PDF oder ZIP,
Dateiname in `X-Ontolens-Filename`, Hinweise in `X-Ontolens-Notices`.

Die normalen Tests prüfen Auswahl, Validierung, Ressourcenbegrenzung und HTML-
Vorbereitung. Für echte Chromium-Tests unter PowerShell:

```powershell
$env:ONTOLENS_TEST_PDF = '1'
uv run --extra web --extra pdf pytest tests/test_pdf_export.py -q
```

Mit einem vorhandenen Docker-Smoke-Testprojekt kann der echte API-Workflow ohne
neue Projektanlage geprüft werden:

```powershell
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python - --pdf /data/docker-smoke-<ID>/manifest.json
```

Technische Grundlagen: [Playwright PDF-Ausgabe](https://playwright.dev/python/docs/api/class-page#page-pdf)
und [Playwright in Docker](https://playwright.dev/python/docs/docker).
