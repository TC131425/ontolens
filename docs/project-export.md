# Projekt als ZIP weitergeben

## Oberfläche

1. Projekt öffnen und **Projekteinstellungen** auswählen.
2. Unter **Projekt weitergeben** bei Bedarf **Generierte Dokumentationen und
   Portale einschließen** aktivieren. Standardmäßig ist die Option aus.
3. **Projekt als ZIP exportieren** anklicken. OntoLens prüft und bündelt die Dateien.
4. Exporthinweise lesen und **Projekt-ZIP herunterladen** auswählen.

Der Download enthält eine Momentaufnahme der gespeicherten Dateien. Das
Arbeitsprojekt wird nicht verändert. Der Browser bestimmt den Downloadordner;
im Projekt entsteht kein zusätzlicher Build. Temporäre Serverdateien werden nach
der Übertragung entfernt.

## Paketinhalt

```text
project/
  ontolens.project.yaml
  EXPORT-INFO.txt
  sources/<ontologie-id>/<quelle.ttl>
  sources/<ontologie-id>/img/...
  content/<ontologie-id>/<dokumentation.md>
  content/<ontologie-id>/img/...
  build/export-*/...                 # optional
  ontolens.project.outputs.json     # optional
```

- Ontologien und zugeordnetes Markdown werden auch dann kopiert, wenn sie
  außerhalb des Projektordners liegen. Lokale Bildverweise werden angepasst.
- Konfiguration und Ausgabezuordnungen verwenden innerhalb des Pakets relative
  Pfade. Der Ausgabeordner der Kopie ist `build`.
- Optionen, Projektname, Ontologie-IDs und Portal-Konfiguration bleiben erhalten.
- RDF-Dateien können zur Anpassung lokaler Bildverweise neu serialisiert werden.
  Formatierung und Kommentare der kopierten RDF-Datei können sich dadurch ändern;
  die Originaldatei bleibt unverändert.
- Mit der Checkbox werden **aktuell verknüpfte** Dokumentationen und Portale samt
  lokal referenzierten Ressourcen übernommen, einschließlich Hell/Dunkel-Varianten.
  Andere Dateien im Ausgabeordner und alte, nicht mehr verknüpfte Builds werden
  nicht pauschal eingepackt. Auch fremde Dateien neben einer HTML-Datei bleiben außen vor.

## Prüfen und Grenzen

Fehlende Quellen, Markdown-Dateien oder lokale Bilder blockieren den Export mit
einer Fehlermeldung. Das gilt auch bei aktivem `skip_missing_images`: Ein
Projektpaket soll keine fehlenden Quellbilder stillschweigend übergehen.
Bei eingeschlossenen Ausgaben blockieren fehlende lokale Abhängigkeiten,
absolute Dateiverweise und Verweise außerhalb des jeweiligen Exportordners den
Export. Gegebenenfalls die Dokumentation neu generieren oder die Checkbox ausschalten.

Online-Bilder bleiben online. `owl:imports` wird nicht automatisch heruntergeladen.
Diese Abhängigkeiten werden in den Exporthinweisen und in `EXPORT-INFO.txt`
aufgeführt. Normale lokale Markdown-Links auf andere Dokumente werden nicht wie
Bilder gebündelt und erzeugen einen Hinweis. Nicht unterstützte Bildsyntax wird
abgewiesen, statt ein Paket mit gebrochenem Bildpfad auszugeben.

Neue OntoLens-Dokumentationen betten ihre Graph-Skripte einschließlich Cytoscape
direkt in die HTML ein; ein `assets/`-Ordner ist dafür nicht mehr nötig. Bilder
bleiben in `img/`. Das Paket ist trotzdem **kein vollständiges Offline-Webarchiv**:
Online-Bilder, externe Links sowie Web-Abhängigkeiten älterer oder fremder
HTML-Dateien können weiterhin Internetzugang benötigen. Vorhandene Exporte werden
beim Verpacken nicht auf das neue HTML-Format umgestellt; dafür neu generieren.
Es enthält keine globale Projektliste oder persönlichen Anwendungseinstellungen.

## Entpacken und verwenden

ZIP an einen gewünschten Ort entpacken. Danach in OntoLens über **Projekt öffnen**
die enthaltene `project/ontolens.project.yaml` auswählen. Bei Docker muss der
entpackte Ordner im eingebundenen Datenordner liegen. Ein eigener ZIP-Importdialog
ist noch nicht erforderlich bzw. nicht Bestandteil dieser Funktion.

Alternativ per CLI neu generieren:

```console
uv run ontolens build /pfad/zum/entpackten/project/ontolens.project.yaml
```

## CLI-Export

```console
uv run ontolens pack projects/mein-projekt.yaml -o build/mein-projekt.zip
uv run ontolens pack projects/mein-projekt.yaml -o build/mein-projekt.zip --include-outputs
```

Wie bei anderen CLI-Ausgaben entsteht ein Zeitstempelordner, beispielsweise
`build/2026-10-29T16-30-00_mein-projekt/mein-projekt.zip`.
`--include-outputs` verwendet die neben der Konfiguration gespeicherten
`.outputs.json`-Zuordnungen der GUI; es durchsucht keinen gesamten Build-Verlauf.

Im Container ohne `uv run`:

```console
docker compose exec ontolens ontolens pack /data/mein-projekt/ontolens.project.yaml -o /data/exports/mein-projekt.zip --include-outputs
```
