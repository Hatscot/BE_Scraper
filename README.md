# BE_Scraper

Das Skript BE_Link_scraper.py soll ermöglichen alle Sets zu Scrapen und in eine Liste zu Packen die Liste soll folgender Maßen ausschauen:
| Set Gruppe | Set Nummer | Set Name mit eingebetteten Link | Set Jahr | Set preis - Value | Growth in Prozent |

**Gesteckte Ziele Stichpunktartig
Das Skript EB_scrape_per_link.py soll Ermöglichen eine Liste aller Angebote von Ebay einzuholen so soll es Funktionieren:
- Es wird die Zuvor erstellte Excel Geladen dann alle Produkte Geladen und Anschließend bei Ebay in Verschieden Kombinationen nach Sets gesucht (Mal nach Set Nummer Mal nach Set Namen)
- Wird der Preis VB aufgefasst soll er einfach in der Lieste VB verzeichnen bei der jeweiligen Anzeige
- Beim Erstellen der Datei soll der Namen der Anzeige zu dem Jeweiligen Set verbettet mit dem Dazugehörign Anzeigen Link Stehen
- Am Ende soll Geprüft werden ob es Doppelte Links Gibt und gegebenfalls diese auch Löschen
- Am Ende soll eine Spalte hinzugeügt werden die den Profit aufnimmt was die Sets Wert sind wissen wir ja bereits aus der anderen Tabelle
- Es soll eine Möglichkeit geben diese Excel weiterzuführen so das man beim Erneuten Scrapen eine Preisentwicklung sieht im Best fall


** Einweisung für den AI Agenten **
# Projekt: LEGO eBay Arbiter & Inventory Manager (Agent-Guide)

## 🎯 Zielsetzung
Dieses System automatisiert den Preisabgleich von LEGO-Sets. Ein Python-Agent liest Marktdaten ein, sucht auf eBay nach dem günstigsten "Sofort-Kaufen"-Preis und bereitet die Daten so auf, dass sie in Google Sheets als interaktives Dashboard (mit Checkbox-Logik) funktionieren.

## 🛠 1. Prozess-Sicherheit (Roadmap-Pflicht)
**ERSTE AUFGABE:** Erstelle eine Datei `ROADMAP.md`. 
- Liste alle Phasen (Setup, Scraping, Google Sheets Export, Apps Script) auf.
- Markiere erledigte Schritte sofort mit `[x]`. 
- Der Status der Roadmap muss nach jedem Teilschritt aktualisiert werden.

## ⚙️ 2. Konfiguration & Steuerung
Die Steuerung erfolgt ausschließlich über die `config.py`.
- **Einlese-Logik:** Nutze die Variable `INPUT_FILE`, um die Quell-Tabelle zu laden.
- **Modus-Prüfung:** - Wenn `NEW_SCRAPE = True`: Scrape alle Sets aus der `INPUT_FILE`.
    - Wenn `NEW_SCRAPE = False`: Lade die bestehende Tabelle und prüfe nur auf fehlende oder veraltete Preise.

## 🕵️ 3. Scraper-Spezifikationen (eBay)
- **Suche:** Suche nach `LEGO + [Set Nummer]`.
- **Hyperlink-Format:** Der Set-Name in der Tabelle darf kein reiner Text sein. Er muss als Google-Sheets-Formel gespeichert werden:
  `=HYPERLINK("EBAY_URL"; "SET_NAME")`
- **Proxy-Rotation:** Wenn `PROXY_MODE = True`, rotiere die IP-Adressen für jede Anfrage unter Verwendung der `proxies.json`.

## 📊 4. Google Sheets Struktur
Die Zieltabelle MUSS exakt diese Spalten in dieser Reihenfolge enthalten:

1. **Kauf** (Checkbox)
2. **Beobachten** (Checkbox)
3. **Löschen** (Checkbox)
4. **Archiv** (Checkbox)
5. **Set Gruppe**
6. **Set Nummer**
7. **Set Name** (Inkl. eingebettetem Link)
8. **Jahr**
9. **Marktwert (€)** (Aus der Quell-Datei)
10. **eBay Preis** (Gefundener Preis)
11. **Profit (€)** (Formel: `Marktwert - eBay Preis`)
12. **Profit (%)** (Formel: `Profit / eBay Preis`)

## ⚡ 5. Automatisierung (Google Apps Script)
Beispiel Skript für Google sheets soll angepasst werden sollte die Variante nicht
funktionieren - Stabilietät wurde noch nicht geprüft. Sollten Funktionen noch unklar sein
Soll der Agent Fragen stellen um die beste Lösung zu finden. Das Skript soll in Google Sheets
integriert werden und die Checkboxen sollen die Zeilen in die entsprechenden Tabellen verschieben. 
Bei weiterm Aktueliesiern mit einer Neuen Liste soll die Liste nicht überschrieben werden sondern
Aktualisiert werden bis auf die neuen Einträge die ins Erste Tabellenblatt sollen. Die Spalten
Kauf, Beobachten, Löschen, Archiv sollen nicht überschrieben werden. Die Spalten Marktwert und
Profit sollen aber Aktualisiert werden. Zudem ist wichtig anzumerken das die Checkbox Löschen nicht wirklich den ganzen eintrag löscht sondern ebenfalls zu dem Zugehörigen Tabellenblatt versiebt, damit
soll verhindert werden das beim Erneuten Aktueliesiern die gelöschten Sets wieder auftauchen.

```javascript
function onEdit(e) {
  const range = e.range;
  const sheet = range.getSheet();
  const row = range.getRow();
  const col = range.getColumn();
  const value = range.getValue();

  if (row < 2) return; // Header ignorieren

  if (value === true) {
    let targetName = "";
    if (col === 1) targetName = "Kauf";
    if (col === 2) targetName = "Watchlist";
    if (col === 3) { sheet.deleteRow(row); return; } // Löschen
    if (col === 4) targetName = "Archiv";

    if (targetName !== "") {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const targetSheet = ss.getSheetByName(targetName) || ss.insertSheet(targetName);
      const rowData = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getValues();
      targetSheet.appendRow(rowData[0]);
      sheet.deleteRow(row);
    }
  }
}

## 6. Technische Anforderungen
- Python (Pandas für Daten, BeautifulSoup/Playwright für Scraping).
- Google Sheets API v4.
- Fehlerbehandlung für "Set nicht gefunden" auf eBay
- Proxy-Rotation fürs Scraping ein beispiel habe ich in dem Ordner scraping-ebay gelegt das zum rotating_proxies Ordner gehört, Die Speider in scraping-ebay waren darauf ausgelegt Bilder anhand einer Liste zu scrapen dies hat auch mit rotating_proxies gut funktioniert, aufpassen es sind par mehr Spider skripte dabei, 2 Davon haben nicht funktioniert.


## 🔄 7. Intelligente Merge-Logik (Anti-Reset)
Um zu verhindern, dass bereits bearbeitete Sets erneut im "Posteingang" landen, muss der Agent folgende Prüfung durchführen:

1. **Globaler Scan:** Vor jedem Schreibvorgang müssen die Set-Nummern aus ALLEN Reitern (Kauf, Watchlist, Archiv) eingelesen werden.
2. **Abgleich:** - Wenn eine Set-Nummer bereits in "Kauf", "Watchlist" oder "Archiv" existiert -> **Nicht** erneut in das Hauptblatt (Posteingang) schreiben.
   - **Optional:** Nur den Preis im jeweiligen Reiter aktualisieren, aber die Zeile dort lassen, wo sie ist.
3. **Posteingang-Bereinigung:** Sets, die im Hauptblatt verbleiben, aber beim neuen Scrape nicht mehr gefunden wurden (oder nicht mehr profitabel sind), sollten markiert oder entfernt werden, damit der Posteingang nicht "zumüllt".