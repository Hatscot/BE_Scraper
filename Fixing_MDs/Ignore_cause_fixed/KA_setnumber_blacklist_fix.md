# Fix-Dokumentation: KA_scrape_per_link.py – Set-Nummer-Erkennung & Blacklist-Lücken

---

## Übersicht der gefundenen Probleme

| # | Problem | Schwere | Datei |
|---|---------|---------|-------|
| 1 | Set-Nummer-Heuristik greift die falsche Zahl | Hoch | `KA_scrape_per_link.py` |
| 2 | `SET_NUMBER_VERIFY` prüft nur Wortgrenzen, nicht Position im Titel | Hoch | `KA_scrape_per_link.py` |
| 3 | Blacklist-Einträge mit Leerzeichen am Ende → kein Match | Mittel | `config.py` |
| 4 | `vollständig` nie aktiv wegen Python-String-Konkatenation | Hoch | `config.py` |
| 5 | `"wie neu"` / `"Neuwertig"` nicht in Titel-Blacklist | Mittel | `config.py` |
| 6 | `"Defekte OVP"` / `"Defekte"` fehlt in Blacklists | Mittel | `config.py` |
| 7 | `"incl OVP"` Variante fehlt in Blacklist | Niedrig | `config.py` |
| 8 | Kurzfristige Set-Nummern (2–3 Stellen) verursachen False Positives | Hoch | `KA_scrape_per_link.py` |

---

## Problem 1 & 8 (KRITISCH): Set-Nummer-Heuristik – falsche Zahl wird erkannt

### Ursache

Der aktuelle `SET_NUMBER_VERIFY`-Code:

```python
if not re.search(r'\b' + re.escape(str(set_number)) + r'\b', title):
```

Prüft nur ob die Setnummer **irgendwo** im Titel vorkommt – nicht ob sie die
**erste oder primäre** Zahl im Titel ist.

**Konkrete Fehler aus der Ergebnistabelle:**

```
Set 190 "Farm Set" → Artikel: "LEGO® DREAMZzz-Albtraum-Haischiff, 1389 T., NEU&OVP, ~190€ im PVG"
→ 190 ist hier der PREIS, nicht die Set-Nummer!

Set 194 "Family" → Artikel: "LEGO 40575 Jahr des Hasen NEU & OVP 194 Teile"
→ 194 ist hier die TEILEZAHL, nicht die Set-Nummer!

Set 195 "Airplane" → Artikel: "LEGO Technic 42163 Schwerlast-Bulldozer | NEU OVP | 195 Teile"
→ 195 ist hier die TEILEZAHL, nicht die Set-Nummer!

Set 199 "Scooter" → Artikel: "LEGO Friends 43447 Paisley's Café 199 Teile NEU OVP"
→ 199 ist hier die TEILEZAHL, nicht die Set-Nummer!

Set 254 "Family" → Artikel: "Lego Brick Headz 40728 - Fortnite Brite Bomber 254 - NEU/OVP"
→ 254 ist hier eine andere Set-Nummer (Fortnite), nicht die gesuchte!

Set 3828 "Air Temple" → Artikel: "Lego 56217 aus Set the last Airbender 3828 Air Temple"
→ 56217 ist die eigentliche Nummer des Artikels, 3828 nur eine Referenz!
```

Das Problem verschärft sich bei Set-Nummern mit 2–3 Stellen (190, 194, 195, 199, 200,
214, 254 etc.) – diese kommen häufig als Preise, Teilezahlen oder Jahreszahlen vor.

### Lösung: Erste Zahlenfolge im Titel als primäre Set-Nummer verwenden

Die Set-Nummer-Verifizierung muss prüfen ob die gesuchte Set-Nummer die **erste
nennenswerte Zahl** im Titel ist (nach "LEGO" und ähnlichen Präfixen).

**Änderung in `parse_item`, den SET_NUMBER_VERIFY-Block ersetzen:**

```python
# ALT:
if config.SET_NUMBER_VERIFY and set_number and title:
    if not re.search(r'\b' + re.escape(str(set_number)) + r'\b', title):
        self.logger.info(
            f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
        )
        return

# NEU:
if config.SET_NUMBER_VERIFY and set_number and title:
    # Schritt 1: Alle Zahlenfolgen im Titel extrahieren (mindestens 3 Stellen)
    # Zahlen unter 3 Stellen werden ignoriert (Jahreszahlen wie 2024, Preise wie 190€
    # werden über Schritt 2 abgefangen)
    numbers_in_title = re.findall(r'\b(\d{3,})\b', title)

    # Schritt 2: Prüfen ob set_number unter den gefundenen Zahlen ist
    if str(set_number) not in numbers_in_title:
        self.logger.info(
            f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
        )
        return

    # Schritt 3: Bei kurzen Set-Nummern (< 4 Stellen) zusätzlich prüfen ob
    # die Set-Nummer die ERSTE Zahl im Titel ist. Kurze Nummern sind zu häufig
    # als Teilezahl, Preis oder Jahreszahl um nur auf Vorkommen zu prüfen.
    if len(str(set_number)) < 4 and numbers_in_title:
        first_number = numbers_in_title[0]
        if first_number != str(set_number):
            self.logger.info(
                f"[ITEM] Set {set_number} (kurze Nr.) → erste Zahl im Titel ist '{first_number}', "
                f"nicht '{set_number}' – übersprungen | Titel: '{title[:60]}'"
            )
            return
```

**Warum `< 4 Stellen` als Schwelle:**
- Set-Nummern mit 4+ Stellen (z.B. 7773, 21046, 75572) sind spezifisch genug
  um ihr bloßes Vorkommen als Beweis zu werten
- Set-Nummern mit 1–3 Stellen (190, 254 etc.) sind zu kurz – sie kommen als
  Teilezahlen, Preise (`~190€`) oder andere Set-Nummern vor
- Die Grenze bei 4 Stellen ist konservativ; alternativ kann `< 5` versucht werden

---

## Problem 2 (HOCH): `vollständig` nie aktiv – Python String-Konkatenation

### Ursache

In `config.py` in der `BLACKLIST` befinden sich diese drei Zeilen direkt
hintereinander ohne Komma:

```python
    "komplett vollständig "   # ← Leerzeichen am Ende UND kein Komma danach
    "vollständig"             # ← kein Komma → Python konkateniert zu einem String!
    "BA",                     # ← erst hier ein Komma
```

Python konkateniert String-Literale die direkt nebeneinander stehen (ohne
Operator) automatisch zu einem einzigen String. Das Ergebnis ist:

```python
"komplett vollständig vollständigBA"
```

Das ist ein einzelner BLACKLIST-Eintrag der nie matchen wird. Weder
`"vollständig"` noch `"BA"` sind effektiv. Das erklärt warum viele Artikel
mit `"vollständig"` im Titel durchkommen.

**Beweis aus der Ergebnistabelle:**
```
"Lego Atlantis 8058 + 8057 Riesenhai Taucher vollständig incl OVP"  → nicht gefiltert!
"Lego 5932 OVP und vollständig"                                      → nicht gefiltert!
"LEGO 8426 Cars 2 Spy Jet Escape vollständig OVP"                    → nicht gefiltert!
"Lego Castle Gefängnis Kutsche Skelett 7092 vollständig OVP"         → nicht gefiltert!
usw. (viele weitere Treffer)
```

### Lösung: Kommas in `config.py` korrigieren

```python
# ALT (fehlerhaft – drei Einträge verschmelzen zu einem):
    "komplett vollständig "
    "vollständig"
    "BA",

# NEU (korrekt – jeder Eintrag einzeln mit Komma):
    "komplett vollständig",
    "vollständig",
    "BA",
```

**WICHTIG:** Gleichzeitig auch das Leerzeichen am Ende von
`"komplett vollständig "` entfernen (war Leerzeichen-Bug, der Match verhinderte).

**Hinweis:** Denselben Fehler gibt es auch weiter oben in der BLACKLIST:
```python
    "OBA",
    "komplett vollständig "   # ← Leerzeichen + kein Komma
    "vollständig"             # ← kein Komma
    "BA",
```
Alle drei müssen mit Komma versehen werden.

---

## Problem 3: Blacklist-Einträge mit Leerzeichen am Ende

### Ursache

Der String `"komplett vollständig "` hat ein abschließendes Leerzeichen.
Da der Code `word.lower() in title_lower` nutzt (substring-Suche), würde
`"komplett vollständig "` nur matchen wenn im Titel auch ein Leerzeichen
nach "vollständig" steht – also nicht am Satzende oder vor Satzzeichen.

### Lösung: In der Blacklist-Prüfschleife `.strip()` auf jeden Eintrag anwenden

**Änderung in `parse_item`, Blacklist-Prüfblock:**

```python
# ALT:
for word in config.BLACKLIST:
    if word.lower() in title_lower:

# NEU:
for word in config.BLACKLIST:
    if word.strip().lower() in title_lower:
```

Gleiche Änderung auch im `DES_BLACKLIST`-Block:

```python
# ALT:
for word in config.DES_BLACKLIST:
    if word.lower() in desc_lower:

# NEU:
for word in config.DES_BLACKLIST:
    if word.strip().lower() in desc_lower:
```

Das macht die Prüfung robust gegen versehentliche Leerzeichen in der Config.

---

## Problem 4: `"wie neu"` und `"Neuwertig"` in Titel-BLACKLIST fehlen

### Ursache

`"Neuwertig"` und `"wie neu"` stehen aktuell nur in der `DES_BLACKLIST`
(Beschreibungs-Blacklist), nicht in der Titel-`BLACKLIST`. Viele Verkäufer
schreiben diese Begriffe direkt in den Titel.

**Beweis aus der Ergebnistabelle:**
```
"LEGO Orient Expedition 7424 Black Cruiser Neuwertig mit Karton"  → nicht gefiltert!
"Lego Atlantis 8072 Unterwasserflitzer wie neu OVP"               → nicht gefiltert!
"Lego Architecture Empire State Building 21046 OVP (wie neu)"     → nicht gefiltert!
"Lego 6289 Piratenschiff Red Beard Runner, wie neu!"              → nicht gefiltert!
"Lego Nexo Knights 70350 Triple-Rocker wie neu OVP"               → nicht gefiltert!
```

### Lösung: Einträge zur Titel-`BLACKLIST` in `config.py` hinzufügen

```python
# Diese Einträge zur BLACKLIST hinzufügen:
    "wie neu",
    "Neuwertig",
    "neuwertig",
    "fast wie neu",
    "fast neu",
    "sehr guter Zustand",
    "sehr gutem Zustand",
    "guter Zustand",
    "gutem Zustand",
```

---

## Problem 5: `"Defekte OVP"` fehlt in beiden Blacklists

### Ursache

`"Defekte OVP"` und `"defekt"` fehlen komplett in der Titel-`BLACKLIST`.

**Beweis aus der Ergebnistabelle:**
```
"Lego 6175 Aquanauts Defekte OVP Verpackung Karton"  → nicht gefiltert!
```

### Lösung: Einträge zur `BLACKLIST` in `config.py` hinzufügen

```python
# Diese Einträge zur BLACKLIST hinzufügen:
    "Defekte OVP",
    "defekte OVP",
    "defekt",
    "Defekt",
    "beschädigt",
    "Beschädigt",
```

---

## Problem 6: `"incl OVP"` Variante fehlt

### Ursache

`"incl OVP"` (ohne Punkt) fehlt in der Titel-`BLACKLIST`. Vorhanden sind
`"incl.OVP"` und `"inkl OVP"` aber nicht `"incl OVP"` (mit Leerzeichen, ohne Punkt).

**Beweis aus der Ergebnistabelle:**
```
"Lego Atlantis 8058 + 8057 Riesenhai Taucher vollständig incl OVP"  → nicht gefiltert!
```

### Lösung: Eintrag zur `BLACKLIST` in `config.py` hinzufügen

```python
    "incl OVP",     # bereits "incl.OVP" vorhanden, diese Variante fehlt noch
```

---

## Problem 7: False Positive durch Artikel-Set-Konfusion (strukturelles Problem)

### Ursache

Einige Artikel referenzieren das gesuchte Set nur nebenbei, sind aber selbst
ein ganz anderes Set oder Produkt:

```
Set 6100 "Aquashark Dart" → "OVP zu LEGO Set 6100 Aquashark Dart"
→ Verkauft wird nur die LEERE OVP-Box, nicht das Set!

Set 4005 "Tug Boat" → "Lego 4005 Brick, 4 Stück, Schubladenbox, grau/weiß, Neu, OVP"
→ 4005 ist hier eine Schubladenbox, kein Set!
```

Der erste Fall (`"OVP zu LEGO"`) ist ein bekanntes Muster für Leerkarton-Verkäufe
die durch die Blacklist-Einträge `"Leerkarton"` und `"Box only"` nicht erfasst werden
weil der Titel diese Wörter nicht verwendet.

### Lösung: Blacklist in `config.py` um diese Muster erweitern

```python
# Diese Einträge zur BLACKLIST hinzufügen:
    "OVP zu LEGO",      # Leerkarton-Verkäufe ("OVP zu LEGO Set XXXX")
    "OVP zu Lego",
    "Karton zu",        # "Karton zu LEGO Set..."
    "Schubladenbox",    # Aufbewahrungsboxen mit LEGO-Nummer
```

---

## Vollständige Liste der Codeänderungen

| # | Datei | Stelle | Was ändern |
|---|-------|--------|------------|
| 1 | `KA_scrape_per_link.py` | `parse_item`, SET_NUMBER_VERIFY-Block | Neuen Zahlen-Prüf-Block einsetzen (siehe Problem 1 & 8) |
| 2 | `KA_scrape_per_link.py` | `parse_item`, BLACKLIST-Schleife | `.strip()` auf `word` anwenden |
| 3 | `KA_scrape_per_link.py` | `parse_item`, DES_BLACKLIST-Schleife | `.strip()` auf `word` anwenden |
| 4 | `config.py` | `BLACKLIST`, Einträge `"komplett vollständig "` / `"vollständig"` / `"BA"` | Kommas ergänzen, Leerzeichen entfernen |
| 5 | `config.py` | `BLACKLIST` | `"wie neu"`, `"Neuwertig"`, Zustandsbeschreibungen hinzufügen |
| 6 | `config.py` | `BLACKLIST` | `"Defekte OVP"`, `"defekt"`, `"beschädigt"` hinzufügen |
| 7 | `config.py` | `BLACKLIST` | `"incl OVP"`, `"OVP zu LEGO"`, `"Schubladenbox"` hinzufügen |

---

## Hinweise für Claude Code

- **Problem 2 (String-Konkatenation) zuerst angehen** – das ist der größte
  einzelne Fehler und erklärt den Großteil der `vollständig`-Durchläufer.
  Den BLACKLIST-Block in config.py sorgfältig auf fehlende Kommas prüfen –
  Python gibt hierfür keine Warnung, der Fehler ist heimtückisch still.

- **SET_NUMBER_VERIFY-Block komplett ersetzen**, nicht nur ergänzen.
  Der neue Block ist ein Drop-in-Ersatz für die zwei bestehenden Zeilen.

- **Keine Änderungen an der Spider-Klasse nötig** außer dem
  SET_NUMBER_VERIFY-Block und den zwei `.strip()`-Ergänzungen.

- **Die `< 4 Stellen`-Schwelle** kann später über eine config-Variable
  `KA_SET_NUMBER_MIN_DIGITS = 4` konfigurierbar gemacht werden falls gewünscht.
  Für den initialen Fix ist der Hardcode ausreichend.
