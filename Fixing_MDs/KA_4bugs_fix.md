# Fix-Dokumentation: KA_scrape_per_link.py & ka_operator.py – 4 Bugs + Root Cause

---

## Übersicht

| # | Problem | Datei | Schwere |
|---|---------|-------|---------|
| 1 | Operator übergibt NaN-Zeilen an Spider → Sets werden nicht gefunden | `ka_operator.py` | KRITISCH |
| 2 | Jahreszahlen (2017, 2018...) werden als Set-Nummer akzeptiert | `KA_scrape_per_link.py` | Hoch |
| 3 | Mehrere Set-Nummern im Titel → Spider nimmt falschen Artikel auf | `KA_scrape_per_link.py` | Hoch |
| 4 | Zeitschriften-Nummern (`Nr.113`) werden als Set-Nummern erkannt | `KA_scrape_per_link.py` | Mittel |

---

## Problem 1 (KRITISCH): Operator übergibt NaN-Zeilen – Sets werden nicht gefunden

### Ursache

Die Input-Excel (`brickeconomy_sets_*.xlsx`) enthält zwischen den Set-Gruppen
sogenannte **Gruppen-Header-Zeilen** wie:

```
  📦 4 Juniors  (24 Sets)	(leer)	(leer)	(leer)	(leer)
  📦 Advanced Models  (31 Sets)	(leer)	...
```

Diese Zeilen haben in der Spalte `Set Nummer` den Wert `NaN` (leer).

Der Operator liest die komplette Excel ein und verteilt sie per Round-Robin –
**ohne diese NaN-Zeilen vorher zu entfernen**. Das bedeutet:
- NaN-Zeilen landen in den `spider_X_input.xlsx`-Teillisten
- Der Spider liest sie und generiert daraus eine Suchanfrage mit `set_number = "nan"`
- Scrapy sendet eine Suche für `"LEGO nan OVP sealed misb"` ab → keine Treffer
- Der `_consecutive_empty`-Zähler steigt dadurch hoch
- Nach `MAX_EMPTY_RESULTS = 250` leeren Treffern bricht der Spider **automatisch ab**
  und verpasst viele echte Sets die danach in seiner Teilliste kämen

**Das erklärt warum Sets wie Stranger Things 75810 fehlen** – der Spider der
diese Gruppe zugeteilt bekam hat wegen NaN-Zeilen früh abgebrochen.

Außerdem: Der Operator filtert NaN-Zeilen **auch nicht** im `load_and_split_input()`
vor dem Round-Robin heraus, was die Gruppenverteilung leicht verfälscht.

### Lösung: NaN-Zeilen in `ka_operator.py` nach dem Polybag-Filter entfernen

**Änderung in `load_and_split_input()`, direkt nach dem Polybag-Filter:**

```python
# ALT – kein NaN-Filter vorhanden:
df = df[~polybag_mask].reset_index(drop=True)

# NEU – NaN-Zeilen (Gruppen-Header) entfernen:
df = df[~polybag_mask].reset_index(drop=True)
# Zeilen ohne gültige Set-Nummer entfernen (Gruppen-Header-Zeilen aus der BrickEconomy-Excel)
nan_mask = df['Set Nummer'].isna() | (df['Set Nummer'].astype(str).str.strip() == '')
nan_count = int(nan_mask.sum())
if nan_count > 0:
    print(f"[Operator] {nan_count} leere/NaN-Zeilen entfernt (Gruppen-Header)")
df = df[~nan_mask].reset_index(drop=True)
```

**Gleiche Änderung auch im Hauptskript `KA_scrape_per_link.py`** (Standalone-Modus),
direkt nach dem Polybag-Filter in `run_scraper()`:

```python
# Nach dem Polybag-Filter in run_scraper():
input_df = input_df[~polybag_mask]

# NEU – direkt darunter einfügen:
nan_mask = input_df['Set Nummer'].isna() | (input_df['Set Nummer'].astype(str).str.strip() == '')
nan_count = int(nan_mask.sum())
if nan_count > 0:
    print(f"{nan_count} leere/NaN-Zeilen entfernt (Gruppen-Header der BrickEconomy-Excel)")
input_df = input_df[~nan_mask]
```

---

## Problem 2 (HOCH): Jahreszahlen werden als Set-Nummer akzeptiert

### Ursache

Set-Nummern wie `2017`, `2018`, `2021`, `2022` sind **vierstellig**. Der
aktuelle SET_NUMBER_VERIFY-Code hat eine Sonderbehandlung nur für Nummern
mit **weniger als 4 Stellen** (`< 4`). Vierstellige Nummern werden nur darauf
geprüft ob sie **irgendwo** im Titel vorkommen:

```python
numbers_in_title = re.findall(r'\b(\d{3,})\b', title)
if str(set_number) not in numbers_in_title:
    return   # überspringen

if len(str(set_number)) < 4 and numbers_in_title:
    # Nur für 1-3 stellige Nummern: muss erste Zahl sein
    ...
# 4-stellige Nummern: keine weitere Prüfung → PROBLEM
```

Jahreszahlen wie `2017` kommen in sehr vielen Artikeltiteln vor – als
Erscheinungsjahr, Edition-Hinweis, oder im Satz `"aus dem Jahr 2017"`.
Das Muster `r'\b(\d{3,})\b'` findet sie als normale Zahlenfolge.

**Konkrete Fehler aus der Ergebnistabelle:**
```
Set 2017 "Choo Choo Train" → "Lego 40237 Ostereiersuche aus dem Jahr 2017 Neu & OVP"
Set 2017 "Choo Choo Train" → "Lego Star Wars Magazin Comics Vulture Droid Nr.23 2017 NEU & OVP"
Set 2018 "Stack n Learn"   → "Lego 60201 City Adventskalender 2018, OVP, Neu"
Set 2021 "Gift Set"        → "LEGO Star Wars Adventskalender Mini Builds 2021–2024 OVP"
```

Alle diese Artikel gehören zu völlig anderen Sets – das Jahreszahl-Match ist
ein reiner Zufallstreffer.

### Lösung: Jahreszahlen aus der Zahlen-Liste herausfiltern

Jahreszahlen folgen dem Muster `19xx` oder `20xx`. Sie müssen vor der
SET_NUMBER_VERIFY-Prüfung aus `numbers_in_title` entfernt werden – **außer**
wenn die gesuchte Set-Nummer selbst eine Jahreszahl ist (dann soll die Prüfung
versagen und der Artikel übersprungen werden).

**Vollständiger Ersatz des SET_NUMBER_VERIFY-Blocks in `parse_item`:**

```python
if config.SET_NUMBER_VERIFY and set_number and title:
    # Alle Zahlenfolgen ab 3 Stellen aus dem Titel extrahieren
    numbers_in_title_raw = re.findall(r'\b(\d{3,})\b', title)

    # Jahreszahlen (1900–2099) herausfiltern – AUSSER wenn set_number selbst
    # eine Jahreszahl ist (dann wird der Artikel korrekt übersprungen)
    year_pattern = re.compile(r'^(19|20)\d{2}$')
    set_number_is_year = bool(year_pattern.match(str(set_number)))

    if set_number_is_year:
        # Set-Nummer ist selbst eine Jahreszahl (z.B. 2017, 2018):
        # Jahreszahlen NICHT herausfiltern, damit der Match korrekt funktioniert
        # → wird aber durch die "erste-Zahl"-Prüfung unten korrekt geblockt
        numbers_in_title = numbers_in_title_raw
    else:
        # Jahreszahlen aus der Vergleichsliste entfernen – sie sollen keinen
        # false positive Match erzeugen
        numbers_in_title = [n for n in numbers_in_title_raw if not year_pattern.match(n)]

    # Schritt 1: Set-Nummer muss in der bereinigten Zahlen-Liste vorkommen
    if str(set_number) not in numbers_in_title:
        self.logger.info(
            f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
        )
        return

    # Schritt 2: Bei kurzen Set-Nummern (< 4 Stellen) UND bei Jahreszahlen
    # als Set-Nummer: muss die ERSTE Zahl im Titel sein
    if (len(str(set_number)) < 4 or set_number_is_year) and numbers_in_title_raw:
        first_number = numbers_in_title_raw[0]
        if first_number != str(set_number):
            self.logger.info(
                f"[ITEM] Set {set_number} → erste Zahl im Titel ist '{first_number}', "
                f"nicht '{set_number}' – übersprungen | Titel: '{title[:60]}'"
            )
            return
```

**Warum das funktioniert:**
- Für normale Sets (z.B. 75810, 21046): Jahreszahlen werden aus der Liste
  entfernt → kein versehentlicher Treffer auf `2017` etc.
- Für Sets deren Nummer selbst eine Jahreszahl ist (2017, 2018...): Jahreszahlen
  bleiben in der Liste, aber die `set_number_is_year`-Bedingung erzwingt dass
  die Jahreszahl die **erste** Zahl im Titel sein muss. Ein Titel wie
  `"Lego 60157 City (Jahr 2017)"` hat `60157` als erste Zahl → wird
  korrekt übersprungen.

---

## Problem 3 (HOCH): Mehrere Set-Nummern im Titel → falscher Artikel wird aufgenommen

### Ursache

Verkäufer listen manchmal mehrere Sets auf einmal:
```
"LEGO 70792 und 71314 Bionicle NEU / OVP"
"Lego Atlantis OVP 8075 8076 8078 8061 8060"
"Neu&OVP Lego 41668 41425 40466 41448 42073 41756 41726 40749"
```

Der aktuelle Code prüft nur ob die gesuchte Set-Nummer **in der Liste der
gefundenen Zahlen vorkommt**. Wenn der Artikel zum Beispiel unter Set `71314`
gesucht wird und der Titel `"70792 und 71314"` enthält, besteht der Check.
Der Artikel ist aber ein Multi-Set-Angebot – man kauft beide zusammen zu
einem Preis der nicht dem Einzelpreis entspricht.

Das führt zu verfälschten Preisdaten und falschen Profitberechnungen.

### Lösung: Bei mehreren Set-Nummern im Titel den Artikel überspringen

Direkt **nach** der Jahreszahl-Bereinigung in `numbers_in_title` prüfen ob
mehr als eine echte Set-Nummer vorkommt (Zahlen die keine Jahreszahlen sind
und mindestens 4 Stellen haben):

```python
    # Schritt 3 (NEU): Mehrere Set-Nummern im Titel → Artikel überspringen
    # "Echte" Set-Nummern = mindestens 4 Stellen, keine Jahreszahl
    candidate_set_numbers = [
        n for n in numbers_in_title_raw
        if len(n) >= 4 and not year_pattern.match(n)
    ]
    if len(candidate_set_numbers) > 1:
        self.logger.info(
            f"[ITEM] Set {set_number} → Mehrere Set-Nummern im Titel "
            f"({candidate_set_numbers}) – Multi-Set-Angebot, übersprungen | "
            f"Titel: '{title[:60]}'"
        )
        return
```

Dieser Block kommt **zwischen** Schritt 1 (Set-Nummer in Liste) und Schritt 2
(erste Zahl bei kurzen Nummern) in dem neuen SET_NUMBER_VERIFY-Block.

**Grenzfall:** 3-stellige Zahlen (wie Set-Nummern 111, 113, 114) werden bewusst
nicht in `candidate_set_numbers` gezählt weil kurze Nummern auch als Teilezahlen
oder sonstige Werte vorkommen können. Die Schwelle `>= 4` ist ein guter
Kompromiss.

---

## Problem 4 (MITTEL): Zeitschriften-Nummer wird als Set-Nummer erkannt

### Ursache

Artikel wie `"Lego Star Wars Zeitschrift Nr.113 Neu & OVP"` oder
`"2 x Lego Star Wars Comic Nr. 114 NEU & OVP"` enthalten eine
Zeitschriftennummer nach `"Nr."` oder `"Nr "`.

Der Regex `r'\b(\d{3,})\b'` findet `113` bzw. `114` als normale Zahlenfolge.
Wenn die gesuchte Set-Nummer zufällig `113` oder `114` lautet (was in der
`Universal Building Set`-Gruppe vorkommt), passiert der Set-Nummer-Check.

Diese Artikel sind Zeitschriften/Comics, keine LEGO-Sets.

### Lösung A: Zeitschriften-Keywords zur Titel-BLACKLIST hinzufügen (in `config.py`)

Das ist die einfachste und robusteste Lösung. Zeitschriften-Artikel haben
immer eines dieser Wörter im Titel:

```python
# Diese Einträge zur BLACKLIST in config.py hinzufügen:
    "Zeitschrift",
    "zeitschrift",
    "Comic",     # Vorsicht: prüfen ob "Comic" auch echte Set-Namen trifft
    "Magazin",
    "magazin",
    "Nr.",        # "Nr." taucht in "Zeitschrift Nr.113" auf
                  # ACHTUNG: auch in "LEGO Exo Force Nr. 7711" – deshalb
                  # NUR mit Punkt ("Nr.") nicht "Nr" alleine!
```

**ACHTUNG zu `"Nr."` und `"Comic"`:**
Aus der Ergebnistabelle ist erkennbar dass `"Nr."` auch in legitimen
Set-Titeln vorkommt wie `"❤ LEGO Exo Force Nr. 7711 - NEU & OVP- ❤"`. 
`"Nr."` (mit Punkt, mit Leerzeichen danach) wäre zu breit. Besser nur
`"Zeitschrift"` und `"Magazin"` zur Blacklist hinzufügen.

`"Comic"` ist sicherer als eigenständiges Wort – LEGO-Set-Namen enthalten
das Wort `Comic` typischerweise nicht.

### Lösung B (ergänzend): Im SET_NUMBER_VERIFY-Block `"Nr."` vor einer Zahl erkennen

Als zusätzliche Absicherung kann geprüft werden ob die Set-Nummer im Titel
direkt nach `"Nr."` oder `"Nr "` vorkommt – das wäre dann eine Zeitschriften-
oder Artikelnummer, keine Set-Nummer:

```python
    # Schritt 4 (optional): Set-Nummer nach "Nr." im Titel = Zeitschrift/Artikel
    nr_pattern = re.compile(
        r'\bNr\.?\s*' + re.escape(str(set_number)) + r'\b',
        re.IGNORECASE
    )
    if nr_pattern.search(title):
        self.logger.info(
            f"[ITEM] Set {set_number} → Nummer folgt auf 'Nr.' im Titel "
            f"– Zeitschrift/Artikel, übersprungen | Titel: '{title[:60]}'"
        )
        return
```

**Empfehlung:** Lösung A (Blacklist `"Zeitschrift"`, `"Magazin"`, `"Comic"`)
ist ausreichend und einfacher zu warten. Lösung B als optionale Ergänzung.

---

## Warum nur max. ~3–5 Ergebnisse pro Set erscheinen

Das ist **kein Bug im eigentlichen Sinne**, sondern eine Folge von Problem 1.
Da die Spider durch NaN-Zeilen frühzeitig abbrechen, scrapen sie nur einen
Bruchteil ihrer Teilliste. Bei 8 Spiders mit je ~125 Sets scrapt vielleicht
jeder nur 30–50 Sets vollständig durch bevor der `MAX_EMPTY_RESULTS`-Zähler
auslöst. Dadurch scheinen manche Sets weniger Ergebnisse zu haben als erwartet.

**Nach dem Fix von Problem 1 sollte sich das normalisieren.** Falls danach
immer noch zu wenige Ergebnisse pro Set kommen: `LIMIT_RESULTS_PER_SET = False`
ist bereits korrekt gesetzt, und die bestehende Suchergebnis-Logik sammelt
alle Links von der Seite. Das sollte ausreichen.

---

## Vollständige Änderungsliste

| # | Datei | Stelle | Was ändern |
|---|-------|--------|------------|
| 1a | `ka_operator.py` | `load_and_split_input()`, nach Polybag-Filter | NaN-Zeilen herausfiltern |
| 1b | `KA_scrape_per_link.py` | `run_scraper()`, nach Polybag-Filter | NaN-Zeilen herausfiltern |
| 2+3+4 | `KA_scrape_per_link.py` | `parse_item`, SET_NUMBER_VERIFY-Block | Kompletten Block ersetzen (Jahreszahl-Filter + Multi-Nummern-Check + Nr.-Check) |
| 5 | `config.py` | `BLACKLIST` | `"Zeitschrift"`, `"Magazin"`, `"Comic"` hinzufügen |

---

## Hinweise für Claude Code

- **Problem 1 zuerst lösen** – es ist die Wurzel des "Sets werden nicht gefunden"-
  Problems und des vorzeitigen Abbruchs. Beide Dateien müssen angefasst werden
  (`ka_operator.py` UND `KA_scrape_per_link.py`).

- **Der SET_NUMBER_VERIFY-Block** in `parse_item` wird **komplett ersetzt** –
  nicht ergänzt. Der neue Block aus diesem Dokument (Probleme 2+3+4) ist ein
  vollständiger Drop-in-Ersatz für die bestehenden ~15 Zeilen.

- **Reihenfolge der Checks im neuen Block:**
  1. Jahreszahl-Bereinigung der gefundenen Zahlen
  2. Set-Nummer muss in bereinigter Liste vorkommen → sonst `return`
  3. Multi-Set-Nummern-Check → bei mehr als einer echten Set-Nummer `return`
  4. Erster-Zahl-Check für kurze Nummern und Jahreszahl-Nummern → sonst `return`
  5. Nr.-Pattern-Check (optional) → bei `"Nr. 113"` im Titel `return`

- **`"Comic"` in der Blacklist** sollte nach dem ersten Lauf gegen die
  Ergebnistabelle geprüft werden ob es legitime Set-Namen trifft. Falls ja,
  einfach auskommentieren.

- **Die Spider-Klasse selbst (`KleinanzeigenLegoSpider`) wird nur im
  `parse_item`-Block geändert** – alle anderen Methoden bleiben unberührt.
