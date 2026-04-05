"""
Test-Skript: Scrapt nur das Theme "City" (erste Seite) und schreibt das Excel.
Damit kann man schnell prüfen ob Value-Preis, Growth, Hyperlinks und Gruppen korrekt sind.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Lade Konfiguration aus scraper.py
from scraper import (
    make_scraper, get_soup, parse_set_rows, get_total_pages,
    write_excel, LegoSet, BASE_URL, log
)

OUTPUT_TEST = r"D:\Entwicklung\GitHub\BE_Scraper_list\test_output.xlsx"

session = make_scraper()

# Nur eine Seite von City
url = "https://www.brickeconomy.com/sets/theme/city?CTY=1&O=0&page=1"
log.info("Lade Testseite: %s", url)
soup = get_soup(url, session)
sets = parse_set_rows(soup, "City")

log.info("Gefundene Sets: %d", len(sets))
for s in sets[:5]:
    log.info(
        "  %-12s | %-40s | Preis: %-10s | Growth: %s | URL: %s",
        s.nummer, s.name[:40], s.preis, s.growth, s.url
    )

if sets:
    # Auch noch ein zweites Theme simulieren damit Gruppenzeilen getestet werden
    fake_second = [
        LegoSet(
            gruppe="Star Wars (Test)",
            nummer="75xxx",
            name="Test Set",
            url="https://www.brickeconomy.com",
            jahr="2024",
            preis="€99.99",
            growth="-5.00%",
        )
    ]
    write_excel(sets + fake_second, OUTPUT_TEST)
    log.info("✅ Test-Excel geschrieben: %s", OUTPUT_TEST)
else:
    log.warning("Keine Sets gefunden!")
