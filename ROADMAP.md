# ROADMAP: LEGO eBay Arbiter & Inventory Manager

## Phase 1: Setup & Konfiguration
- [x] Projektinitialisierung: Klärung offener Fragen (Scrapy, eBay, Output-Format).
- [ ] Erstellung & Anpassung der `config.py` (Suchmuster, Input/Output Dateien).
- [ ] Implementierung der Checkbox & Tabellenstruktur in Pandas.

## Phase 2: eBay Scraper Entwicklung (Scrapy)
- [x] Spider-Logik für eBay: Suchen nach "LEGO + Set Nummer" und Preis/Link Extraktion.
- [x] Berücksichtigung von `CONDITION_FILTER` ("Neu" / "Brand New") und "Sofort-Kaufen" (Buy It Now).
- [x] Integration der Proxies für Stabilität.
- [x] Fehlerbehandlung: Was passiert, wenn kein Set gefunden wird?

## Phase 3: Datenverarbeitung & Anti-Reset Logik
- [x] Einlesen des Inputs (`brickeconomy_sets_...xlsx`).
- [x] Wenn `NEW_SCRAPE = False`: Merge-Logik mit bestehender Liste (Check über Reiter `Kauf`, `Watchlist`, `Archiv`).
- [x] Erstellung der exakten Output-Struktur für Google Sheets (Checkbox-Felder als FALSE, Spalten F-L formatiert, eingebettete Links).
- [x] Profit-Berechnung: `Marktwert - eBay Preis` sowie `Profit (%)`.

## Phase 4: Test & Verifikation
- [ ] Testlauf mit einer limitierten Anzahl an Sets.
- [ ] Prüfung der generierten `LEGO_Ebay_Tracker_Result.xlsx`.
- [ ] Abschluss-Reporting.

## Phase 5: Google Sheets & Automation (Google Apps Script)
- [ ] Manuelles Hochladen der `.xlsx` in Google Sheets.
- [ ] Einrichtung des bereitgestellten Google Apps Script für die Checkbox-Automatisierung.
