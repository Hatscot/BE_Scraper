# Feature-Dokumentation: KA_scrape_per_link.py – Beschreibungs-Blacklist (DES_BLACKLIST)

## Ziel

Anzeigen sollen nicht nur anhand des Titels gefiltert werden, sondern auch anhand
des Beschreibungstexts. Enthält die Beschreibung eines Inserats ein Wort oder einen
Satz aus der neuen `DES_BLACKLIST`, wird die Anzeige wie bei der normalen Blacklist
übersprungen und nicht in die Ergebnisse aufgenommen.

---

## Änderung 1: `config.py` – neue Liste `DES_BLACKLIST` hinzufügen

Direkt **unterhalb** des bestehenden `BLACKLIST`-Blocks einfügen:

```python
# --- Beschreibungs-Blacklist ---
# Wörter oder Sätze die im Beschreibungstext der Anzeige vorkommen dürfen, damit
# das Listing NICHT aufgenommen wird. Groß-/Kleinschreibung wird ignoriert.
# Funktioniert identisch zur BLACKLIST, prüft aber den Beschreibungstext statt den Titel.
DES_BLACKLIST = [
    # "geöffnet",        # Bereits geöffnete Pakete
    # "beschädigt",      # Beschädigte Verpackung
    # "Kratzer",         # Sichtbare Mängel
    # "fehlt",           # Fehlende Teile
    # "unvollständig",   # Set nicht komplett
]
```

---

## Änderung 2: `KA_scrape_per_link.py` – Beschreibung extrahieren und prüfen

### Einstiegspunkt

In `parse_item`, **nach** der bestehenden Titel-Blacklist-Prüfung und **nach** der
Set-Nummer-Verifizierung, aber **vor** der Preis-Extraktion.

Aktueller Code an der Einfügestelle:

```python
        # Set-Nummer-Verifizierung: Titel muss die Setnummer als eigenständige Zahl enthalten
        if config.SET_NUMBER_VERIFY and set_number and title:
            if not re.search(r'\b' + re.escape(str(set_number)) + r'\b', title):
                self.logger.info(
                    f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
                )
                return

        price_val = None   # ← HIER einfügen (vor dieser Zeile)
```

### Einzufügender Code-Block

```python
        # Beschreibungs-Blacklist-Prüfung
        if config.DES_BLACKLIST:
            description = (
                response.css('p#viewad-description-text::text').get()
                or response.css('p#viewad-description-text *::text').getall()
            )
            # getall() liefert eine Liste → zu einem String zusammenführen
            if isinstance(description, list):
                description = ' '.join(description)
            description = (description or '').strip()

            if description:
                desc_lower = description.lower()
                for word in config.DES_BLACKLIST:
                    if word.lower() in desc_lower:
                        self.logger.info(
                            f"[ITEM] Set {set_number} → DES_BLACKLIST '{word}' "
                            f"in Beschreibung – übersprungen"
                        )
                        return
            else:
                self.logger.debug(
                    f"[ITEM] Set {set_number} → Keine Beschreibung gefunden "
                    f"(DES_BLACKLIST übersprungen)"
                )
```

### Hinweis zur CSS-Selektor-Robustheit

Kleinanzeigen verwendet aktuell `p#viewad-description-text` für den Beschreibungstext.
Sollte dieser Selektor bei einzelnen Anzeigen leer zurückkommen (z.B. weil der Text
in verschachtelten `<span>`-Tags steckt), greift der Fallback mit `*::text` +
`getall()` automatisch. Liefert auch dieser nichts, wird die DES_BLACKLIST-Prüfung
für diese Anzeige still übersprungen (kein Abbruch) — das ist das gewünschte
Verhalten, da fehlende Beschreibungen kein Ausschlussgrund sein sollen.

---

## Übersicht der Änderungen

| # | Datei                      | Stelle                                              | Was                                           |
|---|----------------------------|-----------------------------------------------------|-----------------------------------------------|
| 1 | `config.py`                | Nach `BLACKLIST`-Block                              | Neue Liste `DES_BLACKLIST = [...]` einfügen   |
| 2 | `KA_scrape_per_link.py`    | `parse_item`, vor `price_val = None`                | Beschreibung extrahieren + DES_BLACKLIST prüfen |

Keine weiteren Imports oder Abhängigkeiten nötig.
