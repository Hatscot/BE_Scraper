# Fix-Dokumentation: KA_scrape_per_link.py – 403-Blockierung & Proxy-Rotation

## Kurzzusammenfassung der Probleme

Nach 5–15 Minuten läuft der Scraper in eine Dauerschleife aus 403-Fehlern.
Drei unabhängige Fehler wirken zusammen und verstärken sich gegenseitig:

1. **`time.sleep()` im Scrapy-Reactor** blockiert den gesamten Event-Loop → neue IPs
   werden sofort nach dem Aufwachen mit maximaler Request-Rate angefragt → sofort gebannt
2. **Zu hohe Parallelität** (Scrapy-Default: 16 concurrent requests) bei zu wenig Delay
3. **Retry-Logik** nutzt denselben Mechanismus der das Problem verursacht

---

## Problem 1: `time.sleep()` zerstört den Twisted-Reactor (KRITISCH)

### Ursache

Scrapy basiert auf dem asynchronen `twisted`-Framework. Alle Callbacks (`parse`,
`parse_item`) laufen im **selben Single-Thread-Event-Loop**. Ein `time.sleep(15)`
in einem Callback **friert den kompletten Reactor ein**:

- Alle anderen parallelen Requests werden nicht abgearbeitet
- TCP-Verbindungen laufen in Timeouts
- Der Proxy-Anbieter (DataImpulse) **rotiert erst bei neuer Verbindung**, nicht nach
  einer Pause — die Pause hilft also überhaupt nicht
- Wenn der Reactor nach 15s aufwacht, feuert er alle aufgestauten Requests mit der
  **gleichen alten IP** ab → sofort neuer 403

### Lösung: Scrapy-native Retry mit `errback` und `dont_filter`

`time.sleep` komplett entfernen. Stattdessen den Request einfach direkt zurück in die
Scrapy-Queue geben — Scrapy verwaltet das Timing über `DOWNLOAD_DELAY` und
`RETRY_HTTP_CODES` selbst.

**Änderung in `parse` (403-Block):**

```python
# ALT – blockiert den Reactor:
if response.status == 403:
    retry_count = response.meta.get('_403_retries', 0)
    if retry_count < _MAX_403_RETRIES:
        self.logger.warning(...)
        time.sleep(_RETRY_WAIT_SEC)          # ← ENTFERNEN
        yield scrapy.Request(
            url=response.url,
            callback=self.parse,
            meta={**response.meta, '_403_retries': retry_count + 1, 'dont_filter': True}
        )
```

```python
# NEU – gibt Request zurück in Queue ohne zu blockieren:
if response.status == 403:
    retry_count = response.meta.get('_403_retries', 0)
    if retry_count < _MAX_403_RETRIES:
        self.logger.warning(
            f"[403] Set {set_number} – blockiert, Re-Queue "
            f"(Versuch {retry_count + 1}/{_MAX_403_RETRIES})"
        )
        yield scrapy.Request(
            url=response.url,
            callback=self.parse,
            priority=-1,           # Niedrige Priorität → andere Sets zuerst
            dont_filter=True,
            meta={**response.meta, '_403_retries': retry_count + 1}
        )
```

Gleiche Änderung analog in `parse_item`.

**`import time` kann danach komplett entfernt werden.**

---

## Problem 2: Parallelität und Delay falsch konfiguriert

### Ursache

Scrapy-Default: `CONCURRENT_REQUESTS = 16`, `DOWNLOAD_DELAY = 2.0`.
Das bedeutet in der Praxis ca. 8 Requests/Sekunde — viel zu aggressiv für
Kleinanzeigen mit Datacenter-IPs.

Außerdem fehlt `AUTOTHROTTLE`, das den Delay automatisch auf Basis der
Server-Antwortzeiten anpasst.

### Lösung Teil A: Neue Variablen in `config.py` hinzufügen

Folgende Einstellungen in `config.py` eintragen (z.B. direkt unter die
`MAX_RESULTS_PER_SET`-Zeile im Bereich `# --- Scraping Einstellungen ---`):

```python
# --- Scrapy Parallelitäts-Einstellungen ---
# Maximale Anzahl gleichzeitiger Requests (Scrapy-Default wäre 16 – hier stark reduziert)
# Zum Antasten empfohlene Werte: 1 = sehr sanft, 2 = sanft, 4 = moderat, 8 = aggressiv
KA_CONCURRENT_REQUESTS = 2

# Maximale Anzahl gleichzeitiger Requests pro Domain (sollte <= KA_CONCURRENT_REQUESTS sein)
KA_CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Wartezeit in Sekunden zwischen Requests (wird durch AutoThrottle dynamisch angepasst)
KA_DOWNLOAD_DELAY = 3.0
```

### Lösung Teil B: `custom_settings` in der Spider-Klasse anpassen

In der Spider-Klasse `custom_settings` die neuen Config-Variablen einbinden:

```python
custom_settings = {
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',

    # Parallelität aus config.py lesen
    'CONCURRENT_REQUESTS': config.KA_CONCURRENT_REQUESTS,
    'CONCURRENT_REQUESTS_PER_DOMAIN': config.KA_CONCURRENT_REQUESTS_PER_DOMAIN,

    # Delay aus config.py lesen
    'DOWNLOAD_DELAY': config.KA_DOWNLOAD_DELAY,
    'RANDOMIZE_DOWNLOAD_DELAY': True,          # Delay wird um ±50% zufällig variiert

    # AutoThrottle: passt Delay automatisch an Server-Last an
    'AUTOTHROTTLE_ENABLED': True,
    'AUTOTHROTTLE_START_DELAY': config.KA_DOWNLOAD_DELAY,
    'AUTOTHROTTLE_MAX_DELAY': 30.0,
    'AUTOTHROTTLE_TARGET_CONCURRENCY': config.KA_CONCURRENT_REQUESTS_PER_DOMAIN,

    # Scrapy-natives Retry (für Netzwerkfehler, Timeouts etc.)
    'RETRY_ENABLED': True,
    'RETRY_TIMES': 2,
    'RETRY_HTTP_CODES': [],                    # 403 wird manuell behandelt (s.o.)

    'ROBOTSTXT_OBEY': False,
    'LOG_LEVEL': 'INFO',
    'HTTPERROR_ALLOWED_CODES': [403],
    'COOKIES_ENABLED': False,                  # Kein Session-Tracking durch KA
}
```

### Orientierungswerte zum Antasten

| `KA_CONCURRENT_REQUESTS` | `KA_DOWNLOAD_DELAY` | Charakter              |
|--------------------------|---------------------|------------------------|
| 1                        | 5.0                 | Sehr sanft, kaum Bans  |
| 2                        | 3.0                 | Empfohlen als Startpunkt |
| 4                        | 2.0                 | Moderat                |
| 8                        | 1.5                 | Aggressiv, hohe Ban-Gefahr |

---

## Problem 3: Retry-Logik zu aggressiv (Folgeproblem)

### Ursache

Aktuell: `_MAX_403_RETRIES = 3` × 3 Versuche = bis zu 9 fehlgeschlagene Requests
pro Set bevor aufgegeben wird. Bei hunderten von Sets in der Queue stapeln sich
diese Retries.

### Lösung: Retries reduzieren und Backoff einbauen

Konstanten am Anfang der Datei anpassen:

```python
_MAX_403_RETRIES = 2   # War: 3 — nach 2 Versuchen aufgeben
# _RETRY_WAIT_SEC entfernen (wird nicht mehr gebraucht)
```

Optional: Exponential-Backoff über Request-Priorität simulieren. Beim zweiten
Retry die Priorität noch weiter senken (`priority=-2`), damit der Spider erst
viele andere Sets abarbeitet bevor er zurückkommt:

```python
yield scrapy.Request(
    url=response.url,
    callback=self.parse,
    priority=-(retry_count + 1) * 2,   # -2, -4 je Versuch
    dont_filter=True,
    meta={**response.meta, '_403_retries': retry_count + 1}
)
```

---

## Zur Frage: Datacenter IPs vs. Residential IPs

**Deine Einschätzung ist korrekt.** Kleinanzeigen nutzt Cloudflare mit
Bot-Detection, die u.a. ASN-Reputation (also ob die IP aus einem bekannten
Rechenzentrum stammt) bewertet. Datacenter-IPs haben grundsätzlich eine
schlechtere Reputation und werden bei auffälligem Verhalten schneller gebannt.

**Mit den obigen Fixes alleine** (geringere Parallelität, kein sleep, AutoThrottle)
lässt sich die Laufzeit deutlich verlängern — ob das für einen vollständigen
Scrape reicht, hängt von der Größe der Input-Liste ab.

**Residential IPs** würden das Problem grundsätzlicher lösen, sind aber teurer.
Als pragmatischen Mittelweg gibt es **Mobile Proxies** (z.B. über Mobilfunk-IPs),
die günstiger als Residential sind, aber deutlich bessere Reputation haben als
Datacenter.

**Empfehlung für DataImpulse-Nutzer:** DataImpulse bietet auch Residential-IPs an.
Wenn der aktuelle Plan Datacenter-IPs sind, lohnt sich der Wechsel zum Residential-
Tarif für Kleinanzeigen-Scraping.

---

## Übersicht aller Änderungen

| # | Stelle                          | Änderung                                                                    |
|---|---------------------------------|-----------------------------------------------------------------------------|
| 1 | `config.py`                     | `KA_CONCURRENT_REQUESTS`, `KA_CONCURRENT_REQUESTS_PER_DOMAIN`, `KA_DOWNLOAD_DELAY` hinzufügen |
| 2 | Konstanten (oben im Spider)     | `_RETRY_WAIT_SEC` entfernen; `_MAX_403_RETRIES = 2`                         |
| 3 | `import time`                   | Komplett entfernen                                                          |
| 4 | `custom_settings`               | Config-Variablen einbinden; AutoThrottle, Retry wie oben beschrieben        |
| 5 | `parse` – 403-Block             | `time.sleep()` entfernen; `priority=-1` zum Request hinzufügen              |
| 6 | `parse_item` – 403-Block        | Gleiche Änderung wie in `parse`                                             |

---

## Erwartetes Verhalten nach dem Fix

- Kein einfrierender Reactor mehr
- Bei 403: Request wandert ans Ende der Queue, Spider arbeitet andere Sets weiter ab
- AutoThrottle drosselt automatisch wenn der Server langsamer antwortet
- Weniger Bans weil Request-Rate auf 1–2/Sekunde limitiert
- Scraper läuft länger durch bevor IPs rotieren müssen
