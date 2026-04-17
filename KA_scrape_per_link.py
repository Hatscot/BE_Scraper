import pandas as pd
import scrapy
from scrapy.crawler import CrawlerProcess
from openpyxl.styles import Font
import config
import os
import re
import json
import time
from scrapy.exceptions import CloseSpider


_MAX_403_RETRIES = 3   # Maximale Wiederholungsversuche bei HTTP 403
_RETRY_WAIT_SEC   = 15  # Wartezeit in Sekunden vor jedem Retry (DataImpulse rotiert automatisch)


class KleinanzeigenLegoSpider(scrapy.Spider):
    name = "ka_lego"
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2.0,
        'ROBOTSTXT_OBEY': False,
        'LOG_LEVEL': 'INFO',
        # 403 wird an die Callbacks weitergeleitet statt als Fehler abgebrochen
        'HTTPERROR_ALLOWED_CODES': [403],
    }

    def __init__(self, sets_df, spider_results, max_empty=250, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sets_df = sets_df
        self.results = spider_results
        self._max_empty = int(max_empty)
        self._consecutive_empty = 0
        self._debug_saved = False

    def _search_url(self, query):
        """Baut die Kleinanzeigen-Such-URL, sortiert nach Preis aufsteigend."""
        slug = re.sub(r'\s+', '-', query.strip().lower())
        # Sonderzeichen entfernen, nur Buchstaben, Ziffern und Bindestrich behalten
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return (
            f"https://www.kleinanzeigen.de/s-{slug}/k0"
            f"?sortingField=PRICE&sortingOrder=ASC"
        )

    def start_requests(self):
        for index, row in self.sets_df.iterrows():
            set_number = str(row['Set Nummer']).strip()
            set_name = str(row['Set Name']).strip()
            pattern = config.SEARCH_PATTERNS[0]
            query = pattern.format(set_number=set_number, set_name=set_name)
            yield scrapy.Request(
                url=self._search_url(query),
                callback=self.parse,
                meta={'row': row, 'pattern_index': 0,
                      'set_number': set_number, 'set_name': set_name}
            )

    def parse(self, response):
        """Phase 1: Suchergebnisseite → gültige Anzeigen-Links herausziehen."""
        row = response.meta['row']
        pattern_index = response.meta['pattern_index']
        set_number = response.meta['set_number']
        set_name = response.meta['set_name']

        # 403-Behandlung: DataImpulse rotiert automatisch bei neuer Verbindung
        if response.status == 403:
            retry_count = response.meta.get('_403_retries', 0)
            if retry_count < _MAX_403_RETRIES:
                self.logger.warning(
                    f"[403] Set {set_number} – Suchanfrage blockiert | "
                    f"warte {_RETRY_WAIT_SEC}s, neuer Proxy (Versuch {retry_count + 1}/{_MAX_403_RETRIES})"
                )
                time.sleep(_RETRY_WAIT_SEC)
                yield scrapy.Request(
                    url=response.url,
                    callback=self.parse,
                    meta={**response.meta, '_403_retries': retry_count + 1, 'dont_filter': True}
                )
            else:
                self.logger.warning(
                    f"[403] Set {set_number} – Suchanfrage nach {_MAX_403_RETRIES} Versuchen aufgegeben"
                )
                self._consecutive_empty += 1
                self.results.append({'row_data': row, 'ka_price': None, 'ka_link': None})
                if self._consecutive_empty >= self._max_empty:
                    raise CloseSpider('max_empty_results_reached')
            return

        self.logger.info(
            f"[SEARCH] Set {set_number} | HTTP {response.status} | {len(response.text)} Bytes"
        )

        # Debug: erste Suchantwort als HTML speichern
        if not self._debug_saved:
            try:
                with open('debug_ka_response.html', 'w', encoding='utf-8') as dbg:
                    dbg.write(response.text)
                self.logger.info("[SEARCH] debug_ka_response.html gespeichert")
            except Exception as e:
                self.logger.warning(f"[SEARCH] Konnte debug_ka_response.html nicht speichern: {e}")
            self._debug_saved = True

        # Anzeigen-Links aus Suchergebnissen sammeln
        found_links = []
        for article in response.css('article.aditem'):
            href = article.css('a[href*="/s-anzeige/"]::attr(href)').get()
            if not href:
                continue
            # Relative URL vervollständigen
            if href.startswith('/'):
                href = 'https://www.kleinanzeigen.de' + href
            # Nur echte Anzeigen-Links (ID-Muster am Ende: XXXXXX-XX-XXXXX)
            if re.search(r'/s-anzeige/.+/\d+-\d+-\d+', href):
                found_links.append(href)
                if len(found_links) >= config.MAX_RESULTS_PER_SET:
                    break

        self.logger.info(f"[SEARCH] Items auf Seite: {len(response.css('article.aditem'))} | Valide Links: {len(found_links)}")

        if found_links:
            self.logger.info(f"[SEARCH] {len(found_links)} Anzeigen-Link(s) gefunden")
            for link in found_links:
                yield scrapy.Request(
                    url=link,
                    callback=self.parse_item,
                    meta={'row': row, 'set_number': set_number, 'set_name': set_name,
                          'pattern_index': pattern_index}
                )
        else:
            # Kein Treffer → nächstes Suchmuster probieren
            if pattern_index + 1 < len(config.SEARCH_PATTERNS):
                next_pattern = config.SEARCH_PATTERNS[pattern_index + 1]
                query = next_pattern.format(set_number=set_number, set_name=set_name)
                self.logger.info(f"[SEARCH] Kein Treffer, versuche Pattern {pattern_index + 2}")
                yield scrapy.Request(
                    url=self._search_url(query),
                    callback=self.parse,
                    meta={'row': row, 'pattern_index': pattern_index + 1,
                          'set_number': set_number, 'set_name': set_name}
                )
            else:
                self._consecutive_empty += 1
                self.logger.info(
                    f"[SEARCH] Kein Treffer für Set {set_number} "
                    f"(Leerläufe: {self._consecutive_empty}/{self._max_empty})"
                )
                self.results.append({'row_data': row, 'ka_price': None, 'ka_link': None})
                if self._consecutive_empty >= self._max_empty:
                    self.logger.warning(
                        f"[SEARCH] Automatischer Abbruch: {self._max_empty} Sets in Folge ohne Ergebnis"
                    )
                    raise CloseSpider('max_empty_results_reached')

    def parse_item(self, response):
        """Phase 2: Anzeigenseite → Preis aus eingebettetem JavaScript (adPrice) extrahieren."""
        row = response.meta['row']
        set_number = response.meta['set_number']

        # 403-Behandlung: DataImpulse rotiert automatisch bei neuer Verbindung
        if response.status == 403:
            retry_count = response.meta.get('_403_retries', 0)
            if retry_count < _MAX_403_RETRIES:
                self.logger.warning(
                    f"[403] Set {set_number} – Anzeigenseite blockiert | "
                    f"warte {_RETRY_WAIT_SEC}s, neuer Proxy (Versuch {retry_count + 1}/{_MAX_403_RETRIES})"
                )
                time.sleep(_RETRY_WAIT_SEC)
                yield scrapy.Request(
                    url=response.url,
                    callback=self.parse_item,
                    meta={**response.meta, '_403_retries': retry_count + 1, 'dont_filter': True}
                )
            else:
                self.logger.warning(
                    f"[403] Set {set_number} – Anzeige nach {_MAX_403_RETRIES} Versuchen aufgegeben"
                )
            return

        self.logger.info(
            f"[ITEM] Set {set_number} | HTTP {response.status} | {response.url[:80]}"
        )
        self._consecutive_empty = 0  # Anzeigenseite erreicht → Leerlauf-Zähler zurücksetzen

        # Titel extrahieren für Blacklist-Prüfung und Set-Nummer-Verifizierung
        title = (
            response.css('h1#viewad-title::text').get()
            or response.css('h1.boxedbig::text').get()
            or response.css('h1::text').get()
            or ''
        ).strip()

        # Blacklist-Prüfung (Groß-/Kleinschreibung ignorieren)
        if config.BLACKLIST:
            title_lower = title.lower()
            for word in config.BLACKLIST:
                if word.lower() in title_lower:
                    self.logger.info(
                        f"[ITEM] Set {set_number} → Blacklist '{word}' in Titel '{title[:60]}' – übersprungen"
                    )
                    return

        # Set-Nummer-Verifizierung: Titel muss die Setnummer als eigenständige Zahl enthalten
        if config.SET_NUMBER_VERIFY and set_number and title:
            if not re.search(r'\b' + re.escape(str(set_number)) + r'\b', title):
                self.logger.info(
                    f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
                )
                return

        price_val = None

        # Preis-Extraktion: adPrice-Variable aus eingebettetem JavaScript
        # Mögliche Formate: adPrice: 15  |  "adPrice": "15"  |  adPrice: "15,00"
        match = re.search(r'adPrice["\']?\s*:\s*["\']?(\d+(?:[.,]\d+)?)', response.text)
        if match:
            try:
                raw = match.group(1).replace(',', '.')
                price_val = float(raw)
            except (ValueError, TypeError):
                pass

        # Währungsprüfung (Kleinanzeigen zeigt immer €)
        if config.KA_ALLOWED_CURRENCIES and price_val is not None:
            if '€' not in config.KA_ALLOWED_CURRENCIES:
                self.logger.info(
                    f"[ITEM] Set {set_number} → Währung '€' nicht in KA_ALLOWED_CURRENCIES – übersprungen"
                )
                return

        self.logger.info(f"[ITEM] Set {set_number} → Preis: {price_val} € | Titel: {title[:60]}")
        self.results.append({
            'row_data': row,
            'ka_price': price_val,
            'ka_link': response.url
        })


def run_scraper():
    print("--- LEGO KLEINANZEIGEN ARBITER SCRAPER STARTED ---")

    # 0. Proxy Setup
    if config.PROXY_MODE:
        proxy_path = 'Proxy_Login.json'
        if os.path.exists(proxy_path):
            try:
                with open(proxy_path, 'r') as f:
                    p_data = json.load(f)
                    user = p_data.get("Login_ID", "")
                    pw = p_data.get("Password", "")
                    host = p_data.get("Proxy_Host", "")
                    port = p_data.get("Proxy_Port", "")
                    if user and pw and host and port:
                        proxy_url = f"http://{user}:{pw}@{host}:{port}"
                        os.environ['http_proxy'] = proxy_url
                        os.environ['https_proxy'] = proxy_url
                        print(f"Proxy erfolgreich geladen: http://{host}:{port}")
                    else:
                        print("Proxy_Login.json enthält leere Felder! Bitte ausfüllen.")
                        return
            except Exception as e:
                print(f"Fehler beim Laden von Proxy_Login.json: {e}")
                return
        else:
            print("Proxy_Login.json nicht gefunden! Bitte erstellen.")
            return

    # 1. Eingabe-Datei einlesen (dieselbe Liste wie EB-Scraper)
    input_path = os.path.join('table', config.INPUT_FILE)
    if not os.path.exists(input_path):
        print(f"Fehler: Datei {input_path} nicht gefunden!")
        return

    try:
        input_df = pd.read_excel(input_path)
        print(f"{len(input_df)} Sets in der Eingabeliste gefunden.")
    except Exception as e:
        print(f"Fehler beim Lesen der Excel: {e}")
        return

    # Polybags herausfiltern (Setnummern 30000–30999)
    polybag_mask = input_df['Set Nummer'].astype(str).str.match(r'^30\d{3}$')
    polybag_count = int(polybag_mask.sum())
    if polybag_count > 0:
        print(f"{polybag_count} Polybag-Sets übersprungen (Setnummern 30xxx).")
    input_df = input_df[~polybag_mask]

    # 2. Merge-Logik (KA_INPUT_FILE steuert, ob bestehende Datei fortgeführt wird)
    already_processed_sets = set()
    output_path = config.KA_OUTPUT_FILENAME

    is_continuation = bool(config.KA_INPUT_FILE and config.KA_INPUT_FILE.strip())
    existing_file_path = config.KA_INPUT_FILE.strip() if is_continuation else None

    if is_continuation:
        if not os.path.exists(existing_file_path):
            print(f"Warnung: KA_INPUT_FILE '{existing_file_path}' nicht gefunden – starte neuen Scrape.")
            is_continuation = False
        else:
            try:
                for sheet_name in ['Kauf', 'Watchlist', 'Archiv']:
                    try:
                        df_sheet = pd.read_excel(existing_file_path, sheet_name=sheet_name)
                        if 'Set Nummer' in df_sheet.columns:
                            already_processed_sets.update(df_sheet['Set Nummer'].astype(str).tolist())
                    except ValueError:
                        pass  # Sheet existiert nicht
                print(f"{len(already_processed_sets)} Sets übersprungen (bereits in Kauf/Watchlist/Archiv).")
            except Exception as e:
                print(f"Hinweis beim Lesen der bestehenden KA-Datei: {e}")

    # Sets filtern
    to_scrape_df = input_df[~input_df['Set Nummer'].astype(str).isin(already_processed_sets)]
    print(f"Starte Scrape für {len(to_scrape_df)} Sets...")

    if len(to_scrape_df) == 0:
        print("Keine neuen Sets zu scrapen.")
        return

    # 3. Crawler initialisieren & starten
    spider_results = []
    process = CrawlerProcess()
    process.crawl(KleinanzeigenLegoSpider, sets_df=to_scrape_df,
                  spider_results=spider_results, max_empty=config.MAX_EMPTY_RESULTS)
    try:
        process.start()  # Blockiert bis Spider fertig oder Ctrl+C
    except KeyboardInterrupt:
        print("\n[STOP] Scrape durch Ctrl+C unterbrochen – speichere bisherige Ergebnisse...")

    print(f"[DEBUG] spider_results: {len(spider_results)} Einträge nach Spider-Lauf")
    for r in spider_results[:3]:
        print(f"  → price={r['ka_price']} | link={str(r['ka_link'])[:70] if r['ka_link'] else 'None'}")

    # 4. Resultate aggregieren
    output_data = []
    for r in spider_results:
        row = dict(r['row_data'])
        market_value_raw = str(row.get('Value (€)', '')).replace('$', '').replace(',', '')

        try:
            market_value = float(market_value_raw) if market_value_raw.strip() else None
        except ValueError:
            market_value = None

        if market_value is None or (isinstance(market_value, float) and pd.isna(market_value)):
            if 'Retail-Preis' in row:
                market_value = row.get('Retail-Preis')

        ka_price = r['ka_price']
        profit_eur = None
        profit_pct = None

        if ka_price and market_value:
            try:
                profit_eur = float(market_value) - float(ka_price)
                if float(ka_price) > 0:
                    profit_pct = (profit_eur / float(ka_price)) * 100
            except ValueError:
                pass

        # Überspringen wenn nichts gefunden wurde
        if not r['ka_link'] and ka_price is None:
            continue

        # Gefunden aber kein Preis (z.B. "VB" / Preis auf Anfrage)
        if r['ka_link'] and ka_price is None:
            ka_price = 'VB'

        set_name = row.get('Set Name', '')

        new_row = {
            'Kauf': 'FALSE',
            'Beobachten': 'FALSE',
            'Löschen': 'FALSE',
            'Archiv': 'FALSE',
            'Set Gruppe': row.get('Set Gruppe', ''),
            'Set Nummer': row.get('Set Nummer', ''),
            'Set Name': str(set_name),
            'Jahr': row.get('Jahr', ''),
            'Marktwert (€)': market_value,
            'KA Preis': ka_price,
            'Profit (€)': profit_eur,
            'Profit (%)': profit_pct,
            '_ka_link': r['ka_link'],  # Intern für openpyxl – wird vor DataFrame entfernt
        }
        output_data.append(new_row)

    # Sortierung: Set Gruppe aufsteigend, dann Set Nummer aufsteigend
    output_data.sort(key=lambda r: (
        str(r.get('Set Gruppe', '')),
        str(r.get('Set Nummer', '')).zfill(10)
    ))

    # _ka_link aus output_data herausziehen
    link_data = [{'ka_link': r.pop('_ka_link', None)} for r in output_data]
    final_df = pd.DataFrame(output_data)

    # 5. Speichern im Multi-Sheet Excel Format
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='Posteingang', index=False)

        # Anklickbare Hyperlinks in der Set Name-Spalte
        ws = writer.book['Posteingang']
        header = [cell.value for cell in ws[1]]
        set_name_col = header.index('Set Name') + 1
        for row_num, ld in enumerate(link_data, start=2):
            if ld['ka_link']:
                cell = ws.cell(row=row_num, column=set_name_col)
                cell.hyperlink = ld['ka_link']
                cell.font = Font(color='0563C1', underline='single')

        # Leere Dummy-Sheets oder bestehende Sheets übernehmen
        empty_df = pd.DataFrame(columns=final_df.columns)
        for expected_sheet in ['Kauf', 'Watchlist', 'Archiv', 'Löschen']:
            if is_continuation and existing_file_path and os.path.exists(existing_file_path):
                try:
                    df_old = pd.read_excel(existing_file_path, sheet_name=expected_sheet)
                    df_old.to_excel(writer, sheet_name=expected_sheet, index=False)
                except Exception:
                    empty_df.to_excel(writer, sheet_name=expected_sheet, index=False)
            else:
                empty_df.to_excel(writer, sheet_name=expected_sheet, index=False)

    print(f"[DEBUG] output_data: {len(output_data)} Zeilen nach Filterung")
    print(f"✓ Erfolgreich! {len(final_df)} Ergebnisse in '{config.KA_OUTPUT_FILENAME}' (Reiter 'Posteingang') gespeichert.")


if __name__ == "__main__":
    run_scraper()
