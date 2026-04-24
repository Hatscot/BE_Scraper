# PROJEKT KONFIGURATION - LEGO EBAY ARBITER

# --- Einlese- & Dateipfade ---
# Hier gibst du an, welche Tabelle als Basis für den Scrape dienen soll
INPUT_FILE = "brickeconomy_sets_2026-04-19_06-41.xlsx"
# Name der Datei, die nach dem Scrape gespeichert/hochgeladen wird
OUTPUT_FILENAME = "LEGO_Ebay_Tracker_Result.xlsx"

# --- Suchmuster ---
# Die Suchmuster, die auf eBay nacheinander ausgeführt werden, bis ein Preis gefunden wird
# Verfügbare Platzhalter: {set_number}, {set_name}
SEARCH_PATTERNS = [
    "LEGO {set_number} OVP sealed misb",
    "LEGO {set_number} {set_name} Neu sealed misb",
    "LEGO {set_number} {set_name} Neu OVP misb",
    "LEGO {set_number} {set_name} Neu sealed",
    "LEGO {set_number} {set_name} Neu OVP",
    "LEGO {set_number} {set_name} Neu",
    "LEGO {set_number} OVP", 
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
# Maximale Anzahl Angebote pro Set in der Ausgabe (günstigste zuerst, da _sop=15)
MAX_RESULTS_PER_SET = 50
# True  = Begrenzung aktiv → maximal MAX_RESULTS_PER_SET Angebote pro Set
# False = Alle gefundenen Angebote werden aufgenommen (MAX_RESULTS_PER_SET wird ignoriert)
LIMIT_RESULTS_PER_SET = False
# True = eBay-Artikeltitel muss die gesuchte Setnummer enthalten, sonst wird das Listing übersprungen
SET_NUMBER_VERIFY = True

# --- Scrapy Parallelitäts-Einstellungen (Kleinanzeigen) ---
# Empfehlung: 2 / 1 / 3.0 als Startpunkt; aggressiver: 4 / 2 / 2.0
KA_CONCURRENT_REQUESTS = 2
KA_CONCURRENT_REQUESTS_PER_DOMAIN = 1
KA_DOWNLOAD_DELAY = 3.0

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
    "Spielsteine",
    "mit OVP",
    "aufgebaut",
    "OP",
    "Anleitung",
    "ohne OVP",
    "inkl. OVP",
    "ink. OVP",
    "inkl OVP",
    "Xingbao",
    "incl.OVP",
    "OBA",
    "komplett vollständig "
    "vollständig"
    "BA",
    "Komplett",
    "komplett",
    "NEU in OVP",
    "Zb",
    "z.B",
    
]

# --- Beschreibungs-Blacklist ---
# Wörter oder Sätze die im Beschreibungstext der Anzeige vorkommen dürfen, damit
# das Listing NICHT aufgenommen wird. Groß-/Kleinschreibung wird ignoriert.
# Funktioniert identisch zur BLACKLIST, prüft aber den Beschreibungstext statt den Titel.
DES_BLACKLIST = [
     "geöffnet",        # Bereits geöffnete Pakete
     "beschädigt",      # Beschädigte Verpackung
     "Kratzer",         # Sichtbare Mängel
     "fehlt",           # Fehlende Teile
     "unvollständig",   # Set nicht komplett
     "ohne OVP",
     "ausgedruckter Anleitung",
     "KEIN Original Karton",
     "kein Original Karton",
     "alle Teile vorhanden",
     "auseinandergebaut",
     "Ohne Anleitung",
     "Gebrauchsspuren",
     "gebrauchsspuren",
     "bespielt",
     "Gebraucht",
     "gebraucht",
     "inklusive Figuren",
     "in sehr gutem Zustand",
     "fast neu",
     "fast wie neu",
     "sehr gutem Zustand",
     "sehr guten Zustand",
     "Sehr guter Zustand",
     "sehr guter Zustand",
     "Sehr gutem Zustand",
     "Sehr guten Zustand",
     "Set ist vollständig",
     "Es fehlt",
     "sind gebraucht",
     "Mit Figuren",
     "100% vollständig",
     "neuwertig",
     "kein Originalkarton",
     "gebrauchtes Set",
     "Alle Teile vollständig",
     "Set ist komplett",
     "fehlende Teile",
     "komplett",
     "abgebrochen",
     "nicht mehr ganz vollständig",
     "nicht mehr ganz vollständig.",
     "Alle Teile vorhanden.",
     "Alle Teile vorhanden",
     "Inkl. Bauanleitung und Verpackung",
     "inkl. Bauanleitung und Verpackung",
     "Inkl. Bauanleitung und Verpackung.",
     "inkl. Bauanleitung und Verpackung.",
     "Inkl. Bauanleitung",
     "inkl. Bauanleitung",
     "Inkl. Bauanleitung.",
     "inkl. Bauanleitung.",
     "inkl. Verpackung",
     "Inkl. Verpackung",
     "inkl. Verpackung.",
     "Inkl. Verpackung.",
     
        
]

# --- Kostenabzug & Margen-Schwellenwerte ---
# B2C_MARGIN und LOGISTIC_COSTS werden multiplikativ vom Marktwert abgezogen:
# Netto-Wert = Marktwert × (1 - B2C_MARGIN/100) × (1 - LOGISTIC_COSTS/100)
B2C_MARGIN = 20      # Prozentuale B2C-Marge      (20 = 20%, Faktor 0.80)
LOGISTIC_COSTS = 10  # Prozentuale Logistikkosten (10 = 10%, Faktor 0.90)

# Marge-Schwellenwerte: [[min_Preis_€, min_Profit_%], ...]
# Die höchste passende Stufe (KA-Preis >= Stufe) bestimmt den Mindest-Profit.
# Liegt der Profit darunter → Listing wird nicht aufgeführt.
# Erweiterbar: einfach weitere [Preis, Prozent]-Einträge hinzufügen.
MARGIN_THRESHOLD = [
    [0,    30],  # Unter 100€:  mind. 40% Profit nötig
    [100,  25],  # Ab 100€:     mind. 30% Profit nötig
    [1000, 8],  # Ab 1000€:    mind. 10% Profit nötig
]




# --- Google Sheets API ---
# Falls CREATE_NEW_SHEET = False, hier die ID der vorhandenen Tabelle eintragen
EXISTING_SHEET_ID = "DEINE_GOOGLE_SHEET_ID_HIER"

# --- Kleinanzeigen-spezifische Einstellungen ---
KA_OUTPUT_FILENAME = "LEGO_KA_Tracker_Result_08.xlsx"
KA_ALLOWED_CURRENCIES = ["€"]

# Pfad zu einer bestehenden KA-Ergebnis-Excel, die fortgeführt werden soll.
# Leer ("") = Neue Tabelle erstellen (alle Sheets frisch anlegen)
# Pfad gesetzt = Bestehende Datei laden, neue Ergebnisse zu "Posteingang" hinzufügen,
#                Kauf/Watchlist/Archiv/Löschen bleiben erhalten;
#                bereits enthaltene Sets (aus Kauf, Watchlist, Archiv) werden nicht erneut gescrapt.
KA_INPUT_FILE = ""