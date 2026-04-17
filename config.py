# PROJEKT KONFIGURATION - LEGO EBAY ARBITER

# --- Einlese- & Dateipfade ---
# Hier gibst du an, welche Tabelle als Basis für den Scrape dienen soll
INPUT_FILE = "brickeconomy_sets_2026-04-06_10-20.xlsx" 
# Name der Datei, die nach dem Scrape gespeichert/hochgeladen wird
OUTPUT_FILENAME = "LEGO_Ebay_Tracker_Result.xlsx"

# --- Suchmuster ---
# Die Suchmuster, die auf eBay nacheinander ausgeführt werden, bis ein Preis gefunden wird
# Verfügbare Platzhalter: {set_number}, {set_name}
SEARCH_PATTERNS = [
    "LEGO {set_number} sealed",
    "LEGO {set_number} {set_name} sealed",
    "LEGO {set_name} sealed",
    "LEGO {set_number} OVP",
    "LEGO {set_number} {set_name} OVP",
    "LEGO {set_name} OVP",
]

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
# Maximale aufeinanderfolgende Sets ohne Ergebnis, bevor der Scrape automatisch stoppt
MAX_EMPTY_RESULTS = 250
# Maximale Anzahl eBay-Angebote pro Set in der Ausgabe (günstigste zuerst, da _sop=15)
MAX_RESULTS_PER_SET = 3
# True = eBay-Artikeltitel muss die gesuchte Setnummer enthalten, sonst wird das Listing übersprungen
SET_NUMBER_VERIFY = True

# --- Währungsfilter ---
# Nur Listings in diesen Währungen werden aufgefasst.
# Symbole eintragen: €  $  £  ¥  CHF  A$  C$  DKK  SEK  NOK  PLN  Kč
# Leer lassen [] = alle Währungen akzeptieren
ALLOWED_CURRENCIES = ["£"]

# --- Blacklist ---
# Wörter die im eBay-Artikeltitel vorkommen dürfen, damit das Listing NICHT aufgefasst wird.
# Groß-/Kleinschreibung wird ignoriert. Einfach die Kommentarzeichen (#) entfernen um ein
# Wort zu aktivieren, oder eigene Einträge hinzufügen.
BLACKLIST = [
     #"Polybag",       # Kleine Aktionsbeutel (ohne Box)
     "Minifigur",     # Einzelne Figuren, keine Sets
     "Minifig",
     "Custom",        # Inoffizielle/modifizierte Sets
     "Ersatzteile",   # Einzelne Teile, kein komplettes Set
     "Sticker",       # Nur Aufkleber
     "Instructions",  # Nur Bauanleitungen
     "Box only",      # Nur Verpackung ohne Inhalt
     "Leerkarton",    # Nur leere Box
     "MOC",           # My Own Creation (kein offizielles Set)
     "GWP",           # Gift with Purchase (Aktionsset)
    "Teilset",
    "LEGO Minifigur",
    "Schlüsselanhänger",
    "Kopfbedeckung",
    "Spielsteine"
    "mit OVP",
    "aufgebaut",


]

# --- Google Sheets API ---
# Falls CREATE_NEW_SHEET = False, hier die ID der vorhandenen Tabelle eintragen
EXISTING_SHEET_ID = "DEINE_GOOGLE_SHEET_ID_HIER"

# --- Kleinanzeigen-spezifische Einstellungen ---
KA_OUTPUT_FILENAME = "LEGO_KA_Tracker_Result_02.xlsx"
KA_ALLOWED_CURRENCIES = ["€"]

# Pfad zu einer bestehenden KA-Ergebnis-Excel, die fortgeführt werden soll.
# Leer ("") = Neue Tabelle erstellen (alle Sheets frisch anlegen)
# Pfad gesetzt = Bestehende Datei laden, neue Ergebnisse zu "Posteingang" hinzufügen,
#                Kauf/Watchlist/Archiv/Löschen bleiben erhalten;
#                bereits enthaltene Sets (aus Kauf, Watchlist, Archiv) werden nicht erneut gescrapt.
KA_INPUT_FILE = ""