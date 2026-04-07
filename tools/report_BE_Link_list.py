import pandas as pd
import datetime
import os

# ================= EINSTELLUNGEN =================
# Hier den vollen Pfad zu deiner Excel-Datei angeben
EXCEL_PFAD = r'D:\Entwicklung\GitHub\BE_Scraper_list\brickeconomy_sets_2026-04-05_11-40.xlsx'

# Hier den Ordner angeben, in dem der Report gespeichert werden soll
REPORT_ORDNER = r'D:\Entwicklung\GitHub\BE_Scraper\table\Report'


# =================================================

def check_duplicates(input_path, output_folder):
    # 1. Sicherstellen, dass der Report-Ordner existiert
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Ordner '{output_folder}' wurde erstellt.")

    # 2. Dateiname und Zeitstempel vorbereiten
    file_name = os.path.basename(input_path)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_name = f"Report_{timestamp}_{file_name.split('.')[0]}.txt"
    full_report_path = os.path.join(output_folder, report_name)

    try:
        # 3. Excel einlesen
        df = pd.read_excel(input_path)

        # 4. Dubletten finden
        duplicates = df[df.duplicated(keep=False)]

        # 5. Report schreiben
        with open(full_report_path, "w", encoding="utf-8") as f:
            f.write("DUBLETTEN-REPORT\n")
            f.write(f"Quelldatei: {input_path}\n")
            f.write(f"Datum: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write("-" * 50 + "\n\n")

            if duplicates.empty:
                f.write("Keine doppelten Einträge gefunden.\n")
                print("Check abgeschlossen: Alles sauber!")
            else:
                f.write(f"Gefundene Dubletten ({len(duplicates)} Zeilen):\n\n")
                f.write(duplicates.to_string(index=False))
                print(f"Erfolg! {len(duplicates)} Dubletten im Report vermerkt.")
                print(f"Speicherort: {full_report_path}")

    except Exception as e:
        print(f"Fehler: {e}")


if __name__ == "__main__":
    if os.path.exists(EXCEL_PFAD):
        check_duplicates(EXCEL_PFAD, REPORT_ORDNER)
    else:
        print(f"Die Excel-Datei unter '{EXCEL_PFAD}' wurde nicht gefunden.")