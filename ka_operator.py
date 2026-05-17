import os
import sys
import time
import json
import subprocess
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font
import config


CACHE_DIR = 'ka_cache'
POLL_INTERVAL_SEC = 10
MAX_RESTARTS_PER_SPIDER = 5


def prepare_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"[Operator] Cache-Verzeichnis: {os.path.abspath(CACHE_DIR)}")


def load_and_split_input():
    """Lädt die Input-Excel und verteilt Set-Gruppen per Round-Robin auf KA_NUM_SPIDERS Teillisten."""
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

    # Gruppen-Header-Zeilen (NaN/leer in Set Nummer) entfernen –
    # sonst erzeugen sie "LEGO nan ..."-Suchen die den Spider früh abbrechen lassen
    nan_mask = df['Set Nummer'].isna() | (df['Set Nummer'].astype(str).str.strip().isin(['', 'nan', 'NaN']))
    nan_count = int(nan_mask.sum())
    if nan_count > 0:
        print(f"[Operator] {nan_count} leere/NaN-Zeilen entfernt (Gruppen-Header)")
    df = df[~nan_mask].reset_index(drop=True)

    # Gruppen in Original-Reihenfolge identifizieren
    seen = []
    for g in df['Set Gruppe'].astype(str):
        if g not in seen:
            seen.append(g)
    groups = seen
    print(f"[Operator] {len(groups)} Set-Gruppen gefunden")

    n = config.KA_NUM_SPIDERS

    # Round-Robin: Gruppe 0 → Spider 0, Gruppe 1 → Spider 1, Gruppe N → Spider 0, ...
    # Garantiert gleichmäßige Verteilung auch bei Gruppen unterschiedlicher Größe
    spider_group_assignments = {i: [] for i in range(n)}
    for idx, group_name in enumerate(groups):
        spider_idx = idx % n
        spider_group_assignments[spider_idx].append(group_name)

    spider_dfs = {}
    for spider_idx, assigned_groups in spider_group_assignments.items():
        mask = df['Set Gruppe'].astype(str).isin(assigned_groups)
        spider_df = df[mask].reset_index(drop=True)
        spider_dfs[spider_idx] = spider_df
        preview = assigned_groups[:3]
        suffix = '...' if len(assigned_groups) > 3 else ''
        print(f"[Operator] Spider {spider_idx}: {len(spider_df)} Sets "
              f"aus {len(assigned_groups)} Gruppen: {preview}{suffix}")

    return spider_dfs


def write_spider_inputs(spider_dfs):
    """Schreibt die Teillisten als Excel-Dateien in den Cache-Ordner."""
    paths = {}
    for spider_idx, df in spider_dfs.items():
        path = os.path.join(CACHE_DIR, f'spider_{spider_idx}_input.xlsx')
        df.to_excel(path, index=False)
        paths[spider_idx] = path
        print(f"[Operator] Teilliste geschrieben: {path} ({len(df)} Sets)")
    return paths


def start_spider_process(spider_id):
    """Startet einen einzelnen Spider als separaten Python-Prozess."""
    input_path = os.path.join(CACHE_DIR, f'spider_{spider_id}_input.xlsx')
    output_path = os.path.join(CACHE_DIR, f'spider_{spider_id}_results.xlsx')
    log_path = os.path.join(CACHE_DIR, f'spider_{spider_id}.log')

    cmd = [
        sys.executable,
        'KA_scrape_per_link.py',
        '--spider-id', str(spider_id),
        '--input', input_path,
        '--output', output_path,
    ]

    log_file = open(log_path, 'a', encoding='utf-8')
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print(f"[Operator] Spider {spider_id} gestartet (PID {process.pid}), Log: {log_path}")
    return process, log_file


def merge_results():
    """Liest alle Cache-Ergebnis-Excels und führt sie zur finalen Ausgabedatei zusammen."""
    print("[Operator] Lese Teilergebnisse ...")

    # Gruppen-Reihenfolge aus der Input-Excel für spätere Sortierung
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
    dedup_cols = [c for c in ['Set Nummer', 'KA Preis', 'Artikel Name'] if c in merged_df.columns]
    if dedup_cols:
        before_dedup = len(merged_df)
        merged_df = merged_df.drop_duplicates(subset=dedup_cols, keep='first')
        removed = before_dedup - len(merged_df)
        if removed > 0:
            print(f"[Operator] {removed} Duplikate entfernt")

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

    has_links = 'KA Link' in merged_df.columns

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        merged_df.to_excel(writer, sheet_name='Posteingang', index=False)

        empty_df = pd.DataFrame(columns=merged_df.columns)
        for sheet_name in ['Kauf', 'Watchlist', 'Archiv', 'Löschen']:
            empty_df.to_excel(writer, sheet_name=sheet_name, index=False)

    # Hyperlinks aus 'KA Link'-Spalte in 'Set Name'-Spalte eintragen und Hilfsspalte entfernen
    if has_links:
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

            ws.delete_cols(ka_link_col)

        wb.save(output_path)
        print("[Operator] Hyperlinks in finale Excel eingetragen")

    print(f"\n{'=' * 60}")
    print(f"[Operator] ✓ FERTIG! {len(merged_df)} Einträge in '{output_path}' gespeichert")
    print(f"{'=' * 60}")


def run_operator():
    print("=" * 60)
    print("[Operator] KA OPERATOR GESTARTET")
    print(f"[Operator] Anzahl Spider: {config.KA_NUM_SPIDERS}")
    print("=" * 60)

    prepare_cache_dir()

    spider_dfs = load_and_split_input()
    write_spider_inputs(spider_dfs)

    processes = {}       # spider_id → subprocess.Popen
    log_files = {}       # spider_id → geöffnete Log-Datei
    restart_counts = {}  # spider_id → Anzahl bisheriger Neustarts
    finished = set()     # spider_ids die abgeschlossen haben

    for spider_id in range(config.KA_NUM_SPIDERS):
        proc, log_f = start_spider_process(spider_id)
        processes[spider_id] = proc
        log_files[spider_id] = log_f
        restart_counts[spider_id] = 0

    print(f"\n[Operator] Überwachung läuft (Prüfintervall: {POLL_INTERVAL_SEC}s) ...\n")

    while True:
        time.sleep(POLL_INTERVAL_SEC)

        for spider_id, proc in list(processes.items()):
            if spider_id in finished:
                continue

            return_code = proc.poll()  # None = läuft noch

            if return_code is None:
                continue

            log_files[spider_id].close()

            if return_code == 0:
                print(f"[Operator] ✓ Spider {spider_id} erfolgreich abgeschlossen")
                finished.add(spider_id)
            else:
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

        if len(finished) == config.KA_NUM_SPIDERS:
            print("\n[Operator] Alle Spider abgeschlossen. Starte Merge ...")
            break

    merge_results()


if __name__ == "__main__":
    run_operator()
