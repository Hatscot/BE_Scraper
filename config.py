# PROJEKT KONFIGURATION - LEGO EBAY ARBITER

# --- Einlese- & Dateipfade ---
# Hier gibst du an, welche Tabelle als Basis für den Scrape dienen soll
INPUT_FILE = "brickeconomy_sets_2026-04-06_10-20.xlsx - LEGO Sets.csv" 
# Name der Datei, die nach dem Scrape gespeichert/hochgeladen wird
OUTPUT_FILENAME = "LEGO_Ebay_Tracker_Result.csv"

# --- Workflow Steuerung ---
# True = Startet einen komplett neuen Scrape basierend auf der INPUT_FILE
# False = Lädt eine bereits existierende Ergebnis-Tabelle und führt diese fort
NEW_SCRAPE = True 

# True = Erstellt eine komplett neue Google Tabelle in deinem Drive
# False = Versucht in eine bestehende Tabelle zu schreiben (Sheet-ID erforderlich)
CREATE_NEW_SHEET = True

# --- Scraping Einstellungen ---
# True = Nutzt die IPs aus der proxies.json für den Scrape
PROXY_MODE = True
# Zustand der Sets auf Ebay (z.B. "Brand New", "New")
CONDITION_FILTER = "New"

# --- Google Sheets API ---
# Falls CREATE_NEW_SHEET = False, hier die ID der vorhandenen Tabelle eintragen
EXISTING_SHEET_ID = "DEINE_GOOGLE_SHEET_ID_HIER"