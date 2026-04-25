# Architektur-Dokumentation: KA Operator System
## Ziel, Dateistruktur, Implementierungsdetails

---

## 1. Überblick & Ziel

Bisher startet `KA_scrape_per_link.py` eine einzige Spider die die komplette
Input-Liste sequenziell abarbeitet. Das neue System führt einen **Operator** ein
der die Liste aufteilt und mehrere Spider-Prozesse parallel startet, überwacht
und bei Absturz automatisch neu startet.

**Kernprinzipien:**
- `KA_scrape_per_link.py` bleibt das eigentliche Scraping-Skript — es wird nur
  minimal erweitert damit es sowohl standalone als auch vom Operator gestartet
  werden kann
- `ka_operator.py` ist ein komplett neues Skript das ausschließlich für
  Aufteilung, Prozess-Management und Merge zuständig ist
- Kein `True/False`-Schalter nötig: das Hauptskript erkennt automatisch ob es
  standalone oder vom Operator gestartet wurde (über ein Kommandozeilenargument)
- Jeder Spider-Prozess schreibt in eine eigene Cache-Excel und pflegt einen
  Checkpoint — stürzt er ab, startet der Operator ihn neu und er macht genau
  dort weiter wo er aufgehört hat

---

## 2. Neue Dateistruktur

```
projekt/
├── KA_scrape_per_link.py     ← Hauptskript (minimal angepasst)
├── ka_operator.py            ← NEU: Operator-Skript
├── config.py                 ← bekommt eine neue Variable: KA_NUM_SPIDERS
├── Proxy_Login.json          ← unverändert
├── table/
│   └── brickeconomy_sets_...xlsx   ← Input-Liste (unverändert)
└── ka_cache/                 ← NEU: wird vom Operator angelegt
    ├── spider_0_input.xlsx         ← Teilliste für Spider 0
    ├── spider_1_input.xlsx         ← Teilliste für Spider 1
    ├── spider_2_input.xlsx         ← Teilliste für Spider 2
    ├── spider_3_input.xlsx         ← Teilliste für Spider 3
    ├── spider_0_results.xlsx       ← Zwischen-Ergebnisse Spider 0
    ├── spider_1_results.xlsx       ← Zwischen-Ergebnisse Spider 1
    ├── spider_2_results.xlsx       ← Zwischen-Ergebnisse Spider 2
    ├── spider_3_results.xlsx       ← Zwischen-Ergebnisse Spider 3
    ├── spider_0_checkpoint.json    ← Checkpoint Spider 0
    ├── spider_1_checkpoint.json    ← Checkpoint Spider 1
    ├── spider_2_checkpoint.json    ← Checkpoint Spider 2
    └── spider_3_checkpoint.json    ← Checkpoint Spider 3
```

Der `ka_cache/`-Ordner wird vom Operator beim Start automatisch erstellt falls
er nicht existiert. Er wird **nicht** nach dem Lauf gelöscht — bei einem
Neustart des Operators können die Checkpoints wiederverwendet werden.

---

## 3. Änderung 1: `config.py`

Eine einzige neue Variable hinzufügen, direkt unter den bestehenden
`KA_CONCURRENT_REQUESTS`-Variablen:

```python
# --- Operator Einstellungen ---
# Anzahl der parallelen Spider-Prozesse die der Operator startet
# Empfehlung: 2–4 für Datacenter-IPs; maximal 6–8 testen
# Hat keine Wirkung wenn KA_scrape_per_link.py direkt (standalone) gestartet wird
KA_NUM_SPIDERS = 4
```

---

## 4. Änderung 2: `KA_scrape_per_link.py`

### 4.1 Was sich NICHT ändert

- Die Spider-Klasse `KleinanzeigenLegoSpider` bleibt **vollständig unverändert**
- Die komplette `run_scraper()`-Funktion bleibt **vollständig unverändert**
- Alle Imports bleiben unverändert

### 4.2 Was sich ändert: `run_scraper()` bekommt optionale Parameter

Die Signatur von `run_scraper()` wird erweitert damit der Operator eine
Teilliste und eine Spider-ID übergeben kann:

```python
# ALT:
def run_scraper():

# NEU:
def run_scraper(spider_id=None, input_override=None, output_override=None):
```

**Bedeutung der Parameter:**
- `spider_id`: Integer (0, 1, 2, 3 ...) — Identifikation des Prozesses.
  `None` = standalone-Modus
- `input_override`: Pfad zu einer Teillisten-Excel die der Operator vorbereitet
  hat. `None` = wie bisher `config.INPUT_FILE` aus dem `table/`-Ordner lesen
- `output_override`: Pfad zur Cache-Ergebnis-Excel dieses Spiders.
  `None` = wie bisher `config.KA_OUTPUT_FILENAME` als Ausgabedatei

### 4.3 Änderungen innerhalb von `run_scraper()`

**Block 1: Input-Datei einlesen (Zeile ~"input_path = ...")**

```python
# ALT:
input_path = os.path.join('table', config.INPUT_FILE)

# NEU:
if input_override:
    input_path = input_override
else:
    input_path = os.path.join('table', config.INPUT_FILE)
```

**Block 2: Output-Datei bestimmen (Zeile ~"output_path = config.KA_OUTPUT_FILENAME")**

```python
# ALT:
output_path = config.KA_OUTPUT_FILENAME

# NEU:
if output_override:
    output_path = output_override
else:
    output_path = config.KA_OUTPUT_FILENAME
```

**Block 3: Checkpoint-Logik einfügen — NUR wenn spider_id gesetzt ist**

Dieser Block kommt direkt NACH dem Einlesen und Filtern von `input_df`,
aber VOR dem Merge-Block (`already_processed_sets`-Logik).

Der Block liest den Checkpoint und filtert bereits verarbeitete URLs aus
der Teilliste heraus:

```python
# Checkpoint-Logik (nur im Operator-Modus)
if spider_id is not None:
    checkpoint_path = os.path.join('ka_cache', f'spider_{spider_id}_checkpoint.json')
    processed_urls = set()

    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
                processed_urls = set(checkpoint_data.get('processed_urls', []))
            print(f"[Spider {spider_id}] Checkpoint geladen: {len(processed_urls)} URLs bereits verarbeitet")
        except Exception as e:
            print(f"[Spider {spider_id}] Checkpoint konnte nicht geladen werden: {e} – starte von vorne")
            processed_urls = set()
    else:
        print(f"[Spider {spider_id}] Kein Checkpoint gefunden – starte von vorne")
```

**Block 4: Checkpoint-URL-Filterung auf `to_scrape_df` anwenden**

Direkt nach der bestehenden `already_processed_sets`-Filterung:

```python
# Checkpoint-URLs aus to_scrape_df entfernen (Operator-Modus)
# WICHTIG: Filterung läuft über Set Nummer, nicht über URL —
# die URL wird erst beim Scrapen bekannt. Der Checkpoint speichert
# Set-Nummern die bereits vollständig abgearbeitet wurden.
if spider_id is not None and processed_urls:
    before = len(to_scrape_df)
    to_scrape_df = to_scrape_df[
        ~to_scrape_df['Set Nummer'].astype(str).isin(processed_urls)
    ]
    print(f"[Spider {spider_id}] {before - len(to_scrape_df)} Sets aus Checkpoint übersprungen, {len(to_scrape_df)} verbleiben")
```

**WICHTIGE ANMERKUNG ZUM CHECKPOINT-FORMAT:**
Der Checkpoint speichert **Set-Nummern** (nicht URLs) als "bereits erledigt".
Eine Set-Nummer gilt als erledigt sobald alle ihre Anzeigen in die Cache-Excel
geschrieben wurden. Das ist robuster als URL-Tracking weil Set-Nummern aus
der Input-Liste direkt bekannt sind.

**Block 5: Nach dem Spider-Lauf — Checkpoint schreiben**

Direkt nach `process.start()` und dem Debug-Print-Block,
VOR der Aggregations-Schleife (`for r in spider_results`):

```python
# Checkpoint nach erfolgreichem Lauf speichern (Operator-Modus)
if spider_id is not None:
    checkpoint_path = os.path.join('ka_cache', f'spider_{spider_id}_checkpoint.json')
    try:
        # Alle Set-Nummern die in spider_results vorhanden sind als erledigt markieren
        done_sets = set(str(r['row_data']['Set Nummer']) for r in spider_results)
        # Bereits bekannte erledigte Sets dazuaddieren
        all_done = processed_urls | done_sets
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({'processed_urls': list(all_done)}, f, ensure_ascii=False, indent=2)
        print(f"[Spider {spider_id}] Checkpoint gespeichert: {len(all_done)} Sets als erledigt markiert")
    except Exception as e:
        print(f"[Spider {spider_id}] Checkpoint konnte nicht gespeichert werden: {e}")
```

### 4.4 Änderung am `if __name__ == "__main__"` Block

```python
# ALT:
if __name__ == "__main__":
    run_scraper()

# NEU:
if __name__ == "__main__":
    import sys
    # Standalone-Modus: python KA_scrape_per_link.py
    # Operator-Modus:   python KA_scrape_per_link.py --spider-id 0
    #                          --input ka_cache/spider_0_input.xlsx
    #                          --output ka_cache/spider_0_results.xlsx
    spider_id = None
    input_override = None
    output_override = None

    args = sys.argv[1:]
    if '--spider-id' in args:
        idx = args.index('--spider-id')
        spider_id = int(args[idx + 1])
    if '--input' in args:
        idx = args.index('--input')
        input_override = args[idx + 1]
    if '--output' in args:
        idx = args.index('--output')
        output_override = args[idx + 1]

    run_scraper(spider_id=spider_id, input_override=input_override, output_override=output_override)
```

**Wie die automatische Erkennung funktioniert:**
- `python KA_scrape_per_link.py` → keine Argumente → `spider_id = None` →
  verhält sich exakt wie bisher, kein Unterschied zum alten Verhalten
- `python KA_scrape_per_link.py --spider-id 0 --input ... --output ...` →
  Operator-Modus mit Checkpoint-Logik und Teilliste

---

## 5. Neues Skript: `ka_operator.py`

Das ist das Herzstück des neuen Systems. Es wird komplett neu erstellt.

### 5.1 Imports

```python
import os
import sys
import time
import json
import subprocess
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font
import config
```

### 5.2 Konstanten

```python
CACHE_DIR = 'ka_cache'
POLL_INTERVAL_SEC = 10        # Wie oft der Operator den Status prüft (Sekunden)
MAX_RESTARTS_PER_SPIDER = 5   # Maximale Neustarts pro Spider bevor aufgegeben wird
```

### 5.3 Funktion: `prepare_cache_dir()`

Erstellt den `ka_cache/`-Ordner falls er nicht existiert:

```python
def prepare_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"[Operator] Cache-Verzeichnis: {os.path.abspath(CACHE_DIR)}")
```

### 5.4 Funktion: `load_and_split_input()` — Round-Robin über Gruppen

Das ist die wichtigste Funktion. Sie lädt die Input-Excel, identifiziert alle
Set-Gruppen und verteilt sie per Round-Robin auf `KA_NUM_SPIDERS` Teillisten.

**Warum Round-Robin über Gruppen (nicht einfaches Aufteilen):**
Die Input-Liste hat Gruppen unterschiedlicher Größe (z.B. "Creator Expert" mit
80 Sets vs. "4 Juniors" mit 24 Sets). Würde man die Liste einfach halbieren,
könnte ein Spider nur kleine Gruppen bekommen und viel früher fertig sein.
Round-Robin über Gruppen garantiert dass jeder Spider einen Mix aus großen
und kleinen Gruppen bekommt → Laufzeiten gleichen sich an.

```python
def load_and_split_input():
    input_path = os.path.join('table', config.INPUT_FILE)
    if not os.path.exists(input_path):
        print(f"[Operator] FEHLER: Input-Datei nicht gefunden: {input_path}")
        sys.exit(1)

    df = pd.read_excel(input_path)
    print(f"[Operator] {len(df)} Sets geladen aus {input_path}")

    # Polybags herausfiltern (wie im Hauptskript)
    polybag_mask = df['Set Nummer'].astype(str).str.match(r'^30\d{3}$')
    polybag_count = int(polybag_mask.sum())
    if polybag_count > 0:
        print(f"[Operator] {polybag_count} Polybag-Sets herausgefiltert")
    df = df[~polybag_mask].reset_index(drop=True)

    # Gruppen identifizieren (Reihenfolge aus der Excel beibehalten)
    groups = []
    seen = []
    for g in df['Set Gruppe'].astype(str):
        if g not in seen:
            seen.append(g)
    groups = seen
    print(f"[Operator] {len(groups)} Set-Gruppen gefunden")

    n = config.KA_NUM_SPIDERS
    # Round-Robin: Gruppe 0 → Spider 0, Gruppe 1 → Spider 1, ...
    # Gruppe N → Spider 0, Gruppe N+1 → Spider 1, ...
    spider_group_assignments = {i: [] for i in range(n)}
    for idx, group_name in enumerate(groups):
        spider_idx = idx % n
        spider_group_assignments[spider_idx].append(group_name)

    # DataFrames für jeden Spider zusammenstellen
    spider_dfs = {}
    for spider_idx, assigned_groups in spider_group_assignments.items():
        mask = df['Set Gruppe'].astype(str).isin(assigned_groups)
        spider_df = df[mask].reset_index(drop=True)
        spider_dfs[spider_idx] = spider_df
        print(f"[Operator] Spider {spider_idx}: {len(spider_df)} Sets "
              f"aus {len(assigned_groups)} Gruppen: {assigned_groups[:3]}{'...' if len(assigned_groups) > 3 else ''}")

    return spider_dfs
```

### 5.5 Funktion: `write_spider_inputs(spider_dfs)`

Schreibt die Teillisten als Excel-Dateien in den Cache-Ordner:

```python
def write_spider_inputs(spider_dfs):
    paths = {}
    for spider_idx, df in spider_dfs.items():
        path = os.path.join(CACHE_DIR, f'spider_{spider_idx}_input.xlsx')
        df.to_excel(path, index=False)
        paths[spider_idx] = path
        print(f"[Operator] Teilliste geschrieben: {path} ({len(df)} Sets)")
    return paths
```

### 5.6 Funktion: `start_spider_process(spider_id)`

Startet einen einzelnen Spider als separaten Python-Prozess:

```python
def start_spider_process(spider_id):
    input_path = os.path.join(CACHE_DIR, f'spider_{spider_id}_input.xlsx')
    output_path = os.path.join(CACHE_DIR, f'spider_{spider_id}_results.xlsx')
    log_path = os.path.join(CACHE_DIR, f'spider_{spider_id}.log')

    cmd = [
        sys.executable,                    # Gleicher Python-Interpreter wie Operator
        'KA_scrape_per_link.py',
        '--spider-id', str(spider_id),
        '--input', input_path,
        '--output', output_path,
    ]

    # Stdout und Stderr in Log-Datei schreiben
    log_file = open(log_path, 'a', encoding='utf-8')
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        cwd=os.path.dirname(os.path.abspath(__file__))  # Arbeitsverzeichnis = Projektordner
    )
    print(f"[Operator] Spider {spider_id} gestartet (PID {process.pid}), Log: {log_path}")
    return process, log_file
```

### 5.7 Hauptfunktion: `run_operator()`

Das ist der Kern-Loop des Operators. Er startet alle Spider, überwacht sie
und startet abgestürzte Spider neu.

```python
def run_operator():
    print("=" * 60)
    print("[Operator] KA OPERATOR GESTARTET")
    print(f"[Operator] Anzahl Spider: {config.KA_NUM_SPIDERS}")
    print("=" * 60)

    prepare_cache_dir()

    # Teillisten vorbereiten und schreiben
    spider_dfs = load_and_split_input()
    write_spider_inputs(spider_dfs)

    # Spider starten
    processes = {}      # spider_id → subprocess.Popen
    log_files = {}      # spider_id → geöffnete Log-Datei
    restart_counts = {} # spider_id → Anzahl bisheriger Neustarts
    finished = set()    # spider_ids die erfolgreich abgeschlossen haben

    for spider_id in range(config.KA_NUM_SPIDERS):
        proc, log_f = start_spider_process(spider_id)
        processes[spider_id] = proc
        log_files[spider_id] = log_f
        restart_counts[spider_id] = 0

    # Überwachungs-Loop
    print(f"\n[Operator] Überwachung läuft (Prüfintervall: {POLL_INTERVAL_SEC}s) ...\n")
    while True:
        time.sleep(POLL_INTERVAL_SEC)

        for spider_id, proc in list(processes.items()):
            if spider_id in finished:
                continue

            return_code = proc.poll()  # None = läuft noch

            if return_code is None:
                # Spider läuft noch — kein Handlungsbedarf
                continue

            # Spider ist beendet
            log_files[spider_id].close()

            if return_code == 0:
                # Sauber beendet
                print(f"[Operator] ✓ Spider {spider_id} erfolgreich abgeschlossen")
                finished.add(spider_id)
            else:
                # Abgestürzt
                restarts = restart_counts[spider_id]
                if restarts < MAX_RESTARTS_PER_SPIDER:
                    restart_counts[spider_id] += 1
                    print(f"[Operator] ✗ Spider {spider_id} abgestürzt (Code {return_code}), "
                          f"Neustart {restarts + 1}/{MAX_RESTARTS_PER_SPIDER} ...")
                    proc, log_f = start_spider_process(spider_id)
                    processes[spider_id] = proc
                    log_files[spider_id] = log_f
                else:
                    print(f"[Operator] ✗ Spider {spider_id} hat maximale Neustarts "
                          f"({MAX_RESTARTS_PER_SPIDER}) erreicht – wird aufgegeben")
                    finished.add(spider_id)

        # Alle Spider fertig?
        if len(finished) == config.KA_NUM_SPIDERS:
            print("\n[Operator] Alle Spider abgeschlossen. Starte Merge ...")
            break

    # Merge
    merge_results()
```

### 5.8 Funktion: `merge_results()`

Liest alle Cache-Ergebnis-Excels und führt sie zu einer finalen Datei zusammen.
Die Sortierung stellt sicher dass die ursprüngliche Gruppen-Reihenfolge aus der
Input-Excel erhalten bleibt.

```python
def merge_results():
    print("[Operator] Lese Teilergebnisse ...")

    # Gruppen-Reihenfolge aus der Input-Excel lesen (für spätere Sortierung)
    input_path = os.path.join('table', config.INPUT_FILE)
    df_input = pd.read_excel(input_path)
    group_order = list(dict.fromkeys(df_input['Set Gruppe'].astype(str).tolist()))

    all_frames = []
    for spider_id in range(config.KA_NUM_SPIDERS):
        results_path = os.path.join(CACHE_DIR, f'spider_{spider_id}_results.xlsx')
        if not os.path.exists(results_path):
            print(f"[Operator] Warnung: Keine Ergebnisdatei für Spider {spider_id} gefunden")
            continue
        try:
            # Nur den 'Posteingang'-Sheet lesen
            df_part = pd.read_excel(results_path, sheet_name='Posteingang')
            all_frames.append(df_part)
            print(f"[Operator] Spider {spider_id}: {len(df_part)} Einträge geladen")
        except Exception as e:
            print(f"[Operator] Fehler beim Lesen von Spider {spider_id}: {e}")

    if not all_frames:
        print("[Operator] FEHLER: Keine Ergebnisse zum Zusammenführen gefunden!")
        return

    merged_df = pd.concat(all_frames, ignore_index=True)
    print(f"[Operator] Gesamt vor Sortierung: {len(merged_df)} Einträge")

    # Duplikate entfernen (gleiche Set Nummer + KA Preis + Artikel Name)
    before_dedup = len(merged_df)
    merged_df = merged_df.drop_duplicates(
        subset=['Set Nummer', 'KA Preis', 'Artikel Name'],
        keep='first'
    )
    if before_dedup > len(merged_df):
        print(f"[Operator] {before_dedup - len(merged_df)} Duplikate entfernt")

    # Sortierung: ursprüngliche Gruppen-Reihenfolge beibehalten, dann Set Nummer
    group_rank = {g: i for i, g in enumerate(group_order)}
    merged_df['_group_rank'] = merged_df['Set Gruppe'].astype(str).map(
        lambda g: group_rank.get(g, 9999)
    )
    merged_df = merged_df.sort_values(
        by=['_group_rank', 'Set Nummer'],
        key=lambda col: col.astype(str).str.zfill(10) if col.name == 'Set Nummer' else col
    ).drop(columns=['_group_rank'])
    merged_df = merged_df.reset_index(drop=True)

    # Finale Excel schreiben
    output_path = config.KA_OUTPUT_FILENAME
    print(f"[Operator] Schreibe finale Ausgabe nach: {output_path}")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        merged_df.to_excel(writer, sheet_name='Posteingang', index=False)

        # Leere Dummy-Sheets
        empty_df = pd.DataFrame(columns=merged_df.columns)
        for sheet_name in ['Kauf', 'Watchlist', 'Archiv', 'Löschen']:
            empty_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Hyperlinks wiederherstellen — Set Name-Spalte
        # HINWEIS: Die Cache-Excels enthalten keinen separaten Link-Spalte mehr
        # da der Operator nur den Posteingang-Sheet merged. Hyperlinks aus den
        # Einzel-Excels gehen beim Merge verloren (openpyxl-Limitation beim
        # DataFrame-Roundtrip). Workaround: Eine '_ka_link'-Hilfsspalte in die
        # Cache-Excels schreiben (siehe Abschnitt 6).

    print(f"\n{'=' * 60}")
    print(f"[Operator] ✓ FERTIG! {len(merged_df)} Einträge in '{output_path}' gespeichert")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_operator()
```

---

## 6. Hyperlink-Problem im Merge — Lösung

Das aktuelle Hauptskript schreibt Hyperlinks direkt in die Excel-Zellen via
`openpyxl` und speichert die URL in einer temporären `_ka_link`-Spalte die
vor dem DataFrame-Export entfernt wird. Beim Merge über `pd.concat` gehen
diese Zell-Hyperlinks verloren.

**Lösung:** Die `_ka_link`-Spalte darf in den Cache-Excels NICHT entfernt
werden — sie muss erhalten bleiben damit der Operator beim Merge die Links
wiederherstellen kann.

### Änderung in `run_scraper()` (KA_scrape_per_link.py)

Den Block der `_ka_link` aus `output_data` entfernt anpassen:

```python
# ALT — entfernt _ka_link vor dem DataFrame:
link_data = [{'ka_link': r.pop('_ka_link', None)} for r in output_data]
final_df = pd.DataFrame(output_data)

# NEU — im Operator-Modus _ka_link in der Spalte behalten:
if spider_id is not None:
    # Operator-Modus: _ka_link als echte Spalte behalten für Merge
    final_df = pd.DataFrame(output_data)
    # _ka_link umbenennen in 'KA Link' damit es lesbar ist
    final_df = final_df.rename(columns={'_ka_link': 'KA Link'})
    link_data = [{'ka_link': row} for row in final_df['KA Link'].tolist()]
else:
    # Standalone-Modus: wie bisher
    link_data = [{'ka_link': r.pop('_ka_link', None)} for r in output_data]
    final_df = pd.DataFrame(output_data)
```

### Änderung in `merge_results()` (ka_operator.py)

Nach dem Schreiben von `merged_df` in die finale Excel, Hyperlinks
aus der `KA Link`-Spalte in die `Set Name`-Spalte eintragen:

```python
# Hyperlinks in Set Name-Spalte eintragen (nach ExcelWriter-Block)
if 'KA Link' in merged_df.columns:
    wb = load_workbook(output_path)
    ws = wb['Posteingang']
    header = [cell.value for cell in ws[1]]

    if 'Set Name' in header and 'KA Link' in header:
        set_name_col = header.index('Set Name') + 1
        ka_link_col = header.index('KA Link') + 1

        for row_num in range(2, ws.max_row + 1):
            link_cell = ws.cell(row=row_num, column=ka_link_col)
            if link_cell.value:
                name_cell = ws.cell(row=row_num, column=set_name_col)
                name_cell.hyperlink = str(link_cell.value)
                name_cell.font = Font(color='0563C1', underline='single')

        # KA Link-Spalte aus dem Sheet entfernen
        ka_link_col_letter = ws.cell(row=1, column=ka_link_col).column_letter
        ws.delete_cols(ka_link_col)

    wb.save(output_path)
    print("[Operator] Hyperlinks in finale Excel eingetragen")
```

---

## 7. Verwendung (Anleitung)

### Standalone starten (wie bisher):
```bash
python KA_scrape_per_link.py
```
→ Verhält sich exakt wie vor diesem Umbau. Keine Teillisten, kein Checkpoint,
  kein Operator. `config.KA_NUM_SPIDERS` wird ignoriert.

### Operator starten (neues paralleles System):
```bash
python ka_operator.py
```
→ Operator liest `config.KA_NUM_SPIDERS`, teilt die Liste auf, startet
  N Spider-Prozesse, überwacht, startet Abstürze neu, merged am Ende.

### Operator-Lauf nach Absturz FORTSETZEN:
```bash
python ka_operator.py
```
→ Gleicher Befehl. Der Operator erkennt vorhandene Checkpoints im `ka_cache/`-
  Ordner automatisch. Bereits erledigte Sets werden übersprungen.
  Die Teillisten (`spider_X_input.xlsx`) werden neu geschrieben — das ist
  korrekt und gewollt, da die Filterung über den Checkpoint läuft.

---

## 8. Zusammenfassung aller Änderungen

| # | Datei                       | Art       | Was                                                                 |
|---|-----------------------------|-----------|---------------------------------------------------------------------|
| 1 | `config.py`                 | Ergänzung | `KA_NUM_SPIDERS = 4` unter KA-Einstellungen hinzufügen             |
| 2 | `KA_scrape_per_link.py`     | Ergänzung | `run_scraper()` bekommt 3 optionale Parameter                       |
| 3 | `KA_scrape_per_link.py`     | Ergänzung | Input-Pfad-Block: `input_override` auswerten                        |
| 4 | `KA_scrape_per_link.py`     | Ergänzung | Output-Pfad-Block: `output_override` auswerten                      |
| 5 | `KA_scrape_per_link.py`     | Ergänzung | Checkpoint laden (nach Input-Einlesen, vor Merge-Logik)             |
| 6 | `KA_scrape_per_link.py`     | Ergänzung | Checkpoint schreiben (nach `process.start()`)                       |
| 7 | `KA_scrape_per_link.py`     | Ergänzung | `_ka_link`-Behandlung im Operator-Modus anpassen                    |
| 8 | `KA_scrape_per_link.py`     | Ergänzung | `if __name__ == "__main__"` Block: CLI-Argumente parsen             |
| 9 | `ka_operator.py`            | NEU       | Komplette neue Datei (Aufteilung, Prozess-Management, Merge)        |

**Was sich NICHT ändert:**
- `KleinanzeigenLegoSpider`-Klasse: kein einziger Buchstabe
- Proxy-Setup-Block: unverändert
- Merge-Logik für `KA_INPUT_FILE` (Fortsetzung bestehender Excels): unverändert
- Aggregations- und Berechnungslogik: unverändert
- Excel-Export-Format und Sheet-Struktur: unverändert
