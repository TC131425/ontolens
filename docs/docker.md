# OntoLens lokal mit Docker betreiben

## Überblick

Ein Container stellt die React-Oberfläche und FastAPI gemeinsam bereit. Node.js,
Python, uv und ein separater Entwicklungsserver müssen auf dem Rechner nicht
installiert werden. Die CLI bleibt im Container verfügbar.

Die Konfiguration ist für eine **lokale Einzelbenutzer-Anwendung** vorgesehen:
keine Anmeldung, keine Benutzertrennung und keine Freigabe ins Internet.
Compose bindet den Port ausschließlich an `127.0.0.1`.

## Voraussetzungen

- Docker Desktop unter Windows/macOS oder Docker Engine unter Linux.
- Docker Compose v2 (`docker compose version`).
- Unter Windows: Docker Desktop starten, Linux-Container verwenden; gegebenenfalls
  WSL 2 und die Dateifreigabe für das gewählte Laufwerk aktivieren.
- Internetzugang für den ersten Image-Build (Basisimages, Python- und npm-Pakete).

Alle folgenden Befehle werden im OntoLens-Projektordner ausgeführt.

## Schnellstart

1. Docker Desktop starten und warten, bis die Engine bereit ist.
2. Vor dem ersten Start `ONTOLENS_HOST_DIR` in `.env` auf das gewuenschte,
   vorhandene Laufwerk bzw. den Projektordner setzen (siehe unten). Ohne Einstellung
   wird C:/ mit Schreibzugriff eingebunden. `.env.example` dient als Vorlage;
   eine bestehende `.env` nicht ueberschreiben. Datenordner und Port sind optional aenderbar.
3. Container bauen und starten:

```console
docker compose up --build -d
docker compose ps
```

Die Oberfläche ist unter **http://localhost:8080** erreichbar. Der Healthcheck
prüft `/api/health`. Der erste Build kann einige Minuten dauern.

Standardmäßig wird `docker-data/` aus diesem Repository als `/data` eingebunden.
Beim ersten Start entsteht dort ein leeres Projekt `ontolens.project.yaml` mit
dem Namen **Workspace**. Bestehende Konfigurationen werden nicht überschrieben.
Du kannst dieses Projekt mit Ontologien befüllen oder ein neues Projekt anlegen.

## Lokales Laufwerk einstellen

**Vor dem ersten Start** in `.env` den Hostpfad einstellen:

```dotenv
ONTOLENS_HOST_DIR=D:/
```

Auf dem aktuellen Entwicklungsrechner ist D: so konfiguriert. Ohne diese
Einstellung verwendet `compose.yaml` den Standard **C:/**. Alternativ die
`source`-Angabe des Mounts `/data/host-drive` direkt in `compose.yaml` aendern.
Ein einzelner Ordner ist ebenfalls moeglich, etwa `D:/Ontologieprojekte`.
Unter Linux/macOS unbedingt einen dort vorhandenen absoluten Pfad einstellen.

Danach genuegt `docker compose up --build -d` (spaeter `docker compose up -d`).
In der Oberflaeche auf **Lokales Laufwerk** klicken: `/data/host-drive` entspricht
dem eingestellten Windows-Laufwerk. Zum Beispiel ist
`/data/host-drive/Projekte/ISOProps` auf diesem Rechner `D:\Projekte\ISOProps`.
Projektanlage, Quellenkopien und generierte HTML-Dateien werden direkt dort
gespeichert. Browseruploads und Browser-Schreibrechte sind nicht erforderlich;
Firefox funktioniert genauso wie andere Browser.

**Kein automatischer Existenz-Fallback:** C: ist der Standard bei fehlender
Einstellung. Wenn explizit D: eingestellt ist, D: aber fehlt, verweigert Docker
den Start. Dann `.env` auf `ONTOLENS_HOST_DIR=C:/` aendern. Ein Dockerfile kann
Host-Laufwerke nicht pruefen, bevor Compose die Mounts einbindet. Der fehlende
Hostpfad wird absichtlich nicht automatisch angelegt. Ein stiller Laufwerkswechsel
koennte vorhandene Projektpfade auf falsche Dateien zeigen lassen.

**Schreibzugriff:** Die Freigabe ist les- und schreibbar. Bei einem ganzen Laufwerk
kann OntoLens entsprechend auf dessen Dateien zugreifen. Nur benoetigte Pfade
freigeben und die Anwendung weiterhin ausschliesslich lokal erreichbar lassen.
Docker Desktop muss den Zugriff auf das Laufwerk erlauben.

**Daten bleiben erhalten:** `/data` bleibt zusaetzlich an `docker-data` gebunden.
Bestehende Projekte und fruehere Browser-Arbeitskopien werden nicht geloescht.
Stoppen oder Entfernen des Containers loescht weder diesen Ordner noch Dateien
auf dem eingebundenen Laufwerk. Der Browserordner-Modus und der separate Starter
sind entfernt. Zum Zugriff auf alte Arbeitskopien den normalen Dateibrowser nutzen.

## Dateien bereitstellen und auswählen

Ein Container sieht die oben eingebundenen Hostpfade. Ontologien auf dem lokalen
Laufwerk koennen dort direkt ausgewaehlt werden. Alternativ kopiere
Ontologien **zusammen mit ihren Bildordnern** in den eingebundenen Datenordner.
Die Beziehungen zwischen Quelldateien und Bildern sollten erhalten bleiben.

Beispielstruktur auf dem Host:

```text
docker-data/
  inputs/
    loin/
      loin.ttl
      figures/...
    isoprops/
      isoprops.ttl
      documentation.de.md
      figures/...
  ontolens.project.yaml
  ontolens.project.projects.json
  mein-projekt-project/
    ontolens.project.yaml
    ontolens.project.outputs.json
    sources/...
    build/...
```

Beispieldaten unter Windows bereitstellen (PowerShell):

```powershell
New-Item -ItemType Directory -Force docker-data/inputs
Copy-Item -LiteralPath examples/loin -Destination docker-data/inputs -Recurse
Copy-Item -LiteralPath examples/tempo -Destination docker-data/inputs -Recurse
Copy-Item -LiteralPath examples/isoprops -Destination docker-data/inputs -Recurse
```

Nur einmal in einen neuen Eingabeordner kopieren, um unbeabsichtigtes Überschreiben
eigener Änderungen zu vermeiden. TempO referenziert weiterhin die nicht mitgelieferte
`LibraryOverview.svg`; diese ergänzen oder bei verknüpften Quellen die Exportoption
zum Überspringen fehlender Bilder nutzen. Die Quell-Kopieroption bricht bei fehlenden
referenzierten Bildern bewusst ab.

**Dateiauswahl in Docker:** Die vorhandenen Ordner-/Datei-Knöpfe öffnen einen
Dateibrowser in der Weboberfläche, nicht den Windows-Explorer. Er navigiert im
eingebundenen `/data`-Ordner und ueber **Lokales Laufwerk** in `/data/host-drive`.
Du kannst Unterordner öffnen, zurück navigieren,
Dateien auswählen und bei Ontologien mehrere Dateien markieren. Ein Ordner wird
über **Auswählen** als aktueller Speicher-/Ausgabeordner übernommen.

Der Dialog startet direkt auf dem eingebundenen Laufwerk (aktuell D:).
In der Adresszeile lassen sich Windows-Pfade wie `D:\Projekte\ISOProps` einfuegen
und mit Enter oder dem Pfeil oeffnen. Auch Containerpfade bleiben moeglich.
Nur der konfigurierte Hostpfad wird uebersetzt; andere Laufwerke werden abgewiesen.
Die Anzeige verwendet auf dem Host-Mount den Windows-Pfad.

Der Suchfilter durchsucht die Namen im **aktuellen Ordner**, nicht rekursiv das
gesamte Laufwerk. **Zuletzt verwendet** merkt sich bis zu acht ausgewaehlte Ordner
im Browser, getrennt nach Hostfreigabe. Geaenderte oder nicht mehr vorhandene
Pfade melden einen Fehler. Ueber das **Ordner-plus-Symbol** einen neuen Unterordner
anlegen; nach erfolgreicher Anlage wird er direkt geoeffnet. Bestehende Dateien
und Ordner werden dabei niemals ersetzt. Mit **Diesen Ordner verwenden** die
Auswahl abschliessen.

Es gibt keinen Browser-Upload und keine Ordnererstellung in diesem Dialog. Dateien
und zusätzliche Ordner werden über den Explorer/Dateimanager im Host-Datenordner
bereitgestellt. Beim nächsten Öffnen des Dialogs sind sie sichtbar. Außerhalb des
eingebundenen Ordners liegende Pfade und hinausführende Symlinks werden im Dialog
nicht angeboten. Im normalen lokalen Entwicklungsbetrieb bleiben native Dialoge
erhalten.

## Arbeitsablauf

1. **Neues Projekt:** Name, Speicherordner unter `/data` und Ontologien auswählen.
   Die Kopieroption erstellt projektinterne Quellen samt lokalen Bildern.
2. **Ontologien:** Markdown zuordnen/erzeugen, bearbeiten und speichern; HTML oder
   kombinierte HTML-Dokumentation mit den gewünschten Optionen generieren.
3. **Portal:** Ontologien auswählen, Hell/Dunkel/Beide wählen, Portal generieren.
4. Vorschau öffnen oder das ZIP herunterladen. Exporte liegen zugleich auf dem
   Host im entsprechenden Projekt-`build/`-Ordner.
5. Verknüpfungen vor dem erneuten Generieren lösen. Dateien bleiben dabei erhalten.

Weitere Bedienungsdetails: [Web-Anwendung](web-development.md).

## Bestehende Projekte übernehmen

Den **gesamten Projektordner** einschließlich Quellen, Bildern, Markdown, Builds
und `<config-stem>.outputs.json` nach `docker-data/` kopieren. In der Oberfläche
**Projekt öffnen** wählen und dessen YAML auswählen. Projektinterne relative
Pfade funktionieren auf Windows und im Linux-Container.

Absolute Windows-Pfade wie `D:\...` funktionieren im Container nicht. Solche
Dateien ebenfalls in den Datenordner übernehmen und die YAML auf relative Pfade
umstellen oder die Zuordnungen in der GUI reparieren. Das gilt auch für alte
HTML-Zuordnungen mit absoluten Pfaden. Der zuletzt verwendete Projektindex aus
einer Desktop-Installation muss nicht übernommen werden: YAML-Dateien direkt
öffnen, damit sie in der Container-Projektliste registriert werden.

**Nicht das komplette Repository nach `/app` mounten:** Das würde die installierte
Anwendung verdecken. Der Datenordner bleibt unter `/data`, das ausgewaehlte
Host-Laufwerk bzw. der Projektordner unter `/data/host-drive`. Ganze Laufwerke
nur bewusst mit Schreibzugriff freigeben; niemals den Docker-Socket einbinden.

## Port und Datenordner ändern

`.env.example` nach `.env` kopieren und beispielsweise einstellen:

```dotenv
ONTOLENS_PORT=8090
ONTOLENS_DATA_DIR=D:/OntoLensData
```

Der Datenordner muss vorhanden und für den Container beschreibbar sein. Unter
Windows vorzugsweise `/` als Trenner verwenden. Danach `docker compose up -d`
ausführen; der neue Port wäre http://localhost:8090. Das Ändern des Mount-Pfads
kopiert vorhandene Daten **nicht** automatisch.

Unter Linux läuft der Prozess standardmäßig als UID/GID 1000. Bei abweichender
Benutzer-ID kann eine lokale `compose.override.yaml` verwendet werden:

```yaml
services:
  ontolens:
    user: "1001:1001"
```

Die IDs an `id -u`/`id -g` anpassen und dem entsprechenden Benutzer Schreibrechte
am Datenordner geben. Keine pauschalen `chmod 777`-Freigaben verwenden.

## Start, Stop, Logs und Updates

```console
docker compose up -d
docker compose logs --tail=100 -f ontolens
docker compose stop
docker compose down
```

`stop` und `down` löschen den eingebundenen Host-Datenordner nicht. Den Ordner
selbst nicht löschen, solange die Projekte/Exporte noch benötigt werden.

Nach einem Update des Anwendungscodes:

```console
docker compose up --build -d
```

Keine Anwendungspakete im laufenden Container nachinstallieren. Änderungen gehören
in die Projektdateien und werden über einen neuen Image-Build übernommen. Für
aktualisierte Basisimages kann zusätzlich `docker compose build --pull` verwendet
werden; das ist ein bewusstes Update, kein notwendiger Schritt bei jedem Start.

## Backup und Wiederherstellung

Für ein konsistentes Backup zuerst `docker compose stop` ausführen. Den gesamten
Host-Datenordner sichern, einschließlich YAML, `.outputs.json`, `.projects.json`,
Quellen, Markdown, Bildern und Build-Ordnern. Danach wieder starten.

Zur Wiederherstellung bei gestopptem Container den gesicherten Datenordner als
Mount verwenden und starten. Im Container bleibt der Pfad `/data` gleich. Einzelne
portable Projektordner können auch in einer lokalen Installation geöffnet werden.

## CLI im Container

Die CLI ist weiterhin unabhängig von der Oberfläche nutzbar. Alle Pfade beziehen
sich auf den Container, nicht auf Windows-Laufwerke:

```console
docker compose run --rm --no-deps ontolens ontolens --help
docker compose run --rm --no-deps ontolens ontolens /data/inputs/loin/loin.ttl --theme both --quality-report -o /data/cli-builds/loin.html
docker compose run --rm --no-deps ontolens ontolens build /data/mein-projekt-project/ontolens.project.yaml --theme both
```

Der einmalige CLI-Container veröffentlicht keine zusätzlichen Ports. CLI-Builds
verändern wie bisher keine GUI-Verknüpfungen. Vorhandene Ergebnisse bei Bedarf
über den Dateibrowser zuordnen. Keine gleichzeitigen Schreibvorgänge an denselben
Projektdateien aus CLI und GUI durchführen.

## Technik und Grenzen

- Multi-Stage-Build: Node 22 baut React; Python 3.12 und uv installieren die
  gesperrten Python-Abhängigkeiten aus `uv.lock` mit dem `web`-Extra.
- Der Runtime-Container enthält weder Node noch uv; `ontolens` und `uvicorn` sind
  bereits installiert. `npm ci` verwendet `package-lock.json`.
- Ein Uvicorn-Worker, kein Auto-Reload. Die lokalen Sperren und Projektregistrierungen
  sind nicht für mehrere Worker/Container auf demselben Datenbestand ausgelegt.
- Read-only-Containerdateisystem, beschreibbar sind nur `/data` und das temporäre
  `/tmp`, einschliesslich des Host-Mounts `/data/host-drive` mit direktem
  Schreibzugriff auf das eingestellte Laufwerk. Der Prozess läuft ohne Root-Rechte
  und ohne zusätzliche Capabilities.
- Keine Authentifizierung: ausschließlich lokal verwenden. Nicht durch Ändern der
  Portbindung oder einen öffentlichen Proxy ungeschützt ins Netzwerk stellen.
- Der Dateibrowser begrenzt die Auswahl auf `/data`; dies ist keine Mandantentrennung
  oder umfassende Sandbox für nicht vertrauenswürdige RDF-/HTML-Eingaben.
- Graphbibliotheken einschließlich Cytoscape sind direkt in neu erzeugten HTML-Dateien
  eingebettet und funktionieren offline ohne `assets/`. Bilder bleiben in `img/`.
  Externe Bild-URLs und Links können weiterhin Internet benötigen.
- Die Containerzeit wird für Build-Zeitstempel verwendet (standardmäßig UTC).

## Fehlerbehebung und Prüfstatus

### Projekte aus der Auswahl entfernen

In der Projektübersicht entfernt der Papierkorb ein Projekt nach Bestätigung
aus der gespeicherten Projektliste, auch nach einem Containerneustart.
Dateien auf der Festplatte werden dabei **nicht gelöscht**: Quellen, Bilder,
Markdown und Exporte bleiben erhalten. Mit „Projekt öffnen“ und der zugehörigen
YAML-Datei lässt sich das Projekt wieder hinzufügen. Das gilt auch für die
Smoke-Testprojekte. Deren Ordner können bei Bedarf separat im Host-Dateimanager
entfernt werden, nachdem geprüft wurde, dass sie nicht mehr benötigt werden.

### Projekte als ZIP weitergeben

Unter **Projekteinstellungen → Projekt weitergeben** steht der ZIP-Export bereit.
Optional lassen sich die aktuell verknüpften Dokumentationen und Portale
einschließen. Nach Prüfung der Dateien wird ein Downloadlink angeboten.
Das ZIP lässt sich auf dem Zielrechner entpacken und über die enthaltene
`project/ontolens.project.yaml` öffnen. Details: [Projekt-ZIP](project-export.md).

Im selben Bereich lassen sich verknüpfte HTML-Dokumentationen auch als PDF
exportieren. Chromium und die benötigten Schriften sind im Image enthalten;
beim ersten Build werden sie heruntergeladen. A4/A3, Abbildungen und ein statischer
Graph sind wählbar. Details: [PDF-Export](pdf-export.md).

Der vorhandene Smoke-Test kann den Export prüfen, ohne weitere Projekte anzulegen:

```powershell
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python - --archive /data/docker-smoke-<ID>/manifest.json
```

| Problem | Prüfen |
| --- | --- |
| Docker-Pipe/Daemon nicht erreichbar | Docker Desktop starten, Linux-Engine abwarten; `docker version` prüfen |
| Port belegt | `ONTOLENS_PORT` ändern und Compose neu starten |
| Dateien fehlen im Dialog | Liegen sie im eingebundenen Host-Ordner? Dateiendung passt zur Auswahl? |
| Permission denied beim Start/Speichern | Mount-Freigabe unter Docker Desktop bzw. UID/GID und Linux-Dateirechte prüfen |
| Windows-Pfade im Projekt | Quellen nach `/data` übernehmen und relative Pfade/Zuordnungen verwenden |
| Generierung blockiert | Bestehende HTML-/Portal-Verknüpfung lösen; Fehlermeldungen/Logs prüfen |
| Graph lädt nicht | Ältere Dokumentation neu generieren; aktuelle Builds enthalten alle Graph-Skripte direkt in der HTML. Bei alten Builds können lokale Assets oder CDN-Zugriff fehlen. |

Automatisierte Tests prüfen Bootstrap, Datenbrowser-Grenzen, statisches Frontend,
dynamisch geöffnete Projekte, Portalexport und Neustart-Persistenz. Compose lässt
sich ohne laufende Engine mit `docker compose config --quiet` validieren.
**Mit Docker Desktop geprüft:** Image-Build, Containerstart und Healthcheck,
Projektanlage mit Quellen-/Bildkopien, Markdown erzeugen/prüfen/speichern,
HTML und kombinierte Dokumentation in beiden Farbschemata, Verknüpfen/Lösen,
Ontologien hinzufügen/entfernen, Portal, ZIP-Downloads und CLI im Container.
Nach einem echten Containerneustart waren Projekte, Markdown und Exportverknüpfungen
weiter verfügbar. Zusätzlich wurde ein Portal mit LOIN, TempO und ISOProps in
beiden Farbschemata gebaut. Bei TempO fehlt in den Beispieldaten
`figures/LibraryOverview.svg`; dieser Test überspringt fehlende Bilder ausdrücklich.

### Workflowtest wiederholen

Der Test spricht die laufende API an und legt einen eigenen Ordner
`/data/docker-smoke-<ID>` an. Vorhandene Projekte werden nicht verändert.
Die Testprojekte und Exporte bleiben zur Kontrolle erhalten und erscheinen in
der Projektauswahl. Voraussetzung: Container läuft, Befehle im Repository ausführen.

```powershell
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python -
```

Unter Linux/macOS entsprechend:

```sh
docker compose exec -T ontolens python - < scripts/docker_smoke.py
```

Die Ausgabe nennt `MANIFEST=/data/docker-smoke-<ID>/manifest.json`. Für den
Persistenztest diesen konkreten Pfad im nächsten Befehl einsetzen:

```powershell
docker compose restart ontolens
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python - --verify /data/docker-smoke-<ID>/manifest.json
```

Optional die echten Beispiele in denselben Testordner kopieren und prüfen:

```powershell
docker compose exec -T ontolens mkdir -p /data/docker-smoke-<ID>/examples
docker compose cp examples/. ontolens:/data/docker-smoke-<ID>/examples
Get-Content scripts/docker_smoke.py -Raw | docker compose exec -T ontolens python - --examples /data/docker-smoke-<ID>/examples
```

Der Beispieldurchlauf gibt einen `PORTAL`-Pfad aus. Mit
`http://localhost:8080` davor lässt sich das Ergebnis direkt öffnen.
Diese Tests prüfen HTTP-Antworten, HTML-Verweise, Bilder und ZIP-Inhalte;
sie ersetzen keinen vollständigen interaktiven Test aller Graphfunktionen.

Referenzen: [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/),
[Docker Compose](https://docs.docker.com/compose/),
[Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
