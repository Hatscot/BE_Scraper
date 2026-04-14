import pandas as pd
import scrapy
from scrapy.crawler import CrawlerProcess
from openpyxl.styles import Font
import config
import os
import re
import json
from scrapy.exceptions import CloseSpider

# Mapping: ISO-Währungscode → Symbol (für ALLOWED_CURRENCIES in config.py)
_ISO_TO_SYMBOL = {
    'EUR': '€', 'USD': '$', 'GBP': '£', 'JPY': '¥', 'CNY': '¥',
    'CHF': 'CHF', 'AUD': 'A$', 'CAD': 'C$', 'DKK': 'DKK',
    'SEK': 'SEK', 'NOK': 'NOK', 'PLN': 'zł', 'CZK': 'Kč',
}

class EbayLegoSpider(scrapy.Spider):
    name = "ebay_lego"
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 1.5, # Moderates Timing, um nicht blockiert zu werden
        'ROBOTSTXT_OBEY': False,
        'LOG_LEVEL': 'INFO'
    }
    
    # Die Proxy-Einstellungen werden nun in run_scraper() über Environment Variables übergeben

    def __init__(self, sets_df, spider_results, max_empty=250, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sets_df = sets_df
        self.results = spider_results
        self._max_empty = int(max_empty)
        self._consecutive_empty = 0
        self._debug_saved = False
        
    def _search_url(self, query):
        """Baut die eBay-Such-URL: Sofort Kaufen, Neu, Preis aufsteigend (_sop=15)."""
        return (
            f"https://www.ebay.de/sch/i.html"
            f"?_nkw={query.replace(' ', '+')}"
            f"&LH_BIN=1&LH_ItemCondition=1000&_sop=15"
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
                meta={'row': row, 'pattern_index': 0, 'set_number': set_number, 'set_name': set_name}
            )

    def parse(self, response):
        """Phase 1: Suchergebnisseite → ersten gültigen Artikel-Link herausziehen."""
        row = response.meta['row']
        pattern_index = response.meta['pattern_index']
        set_number = response.meta['set_number']
        set_name = response.meta['set_name']

        self.logger.info(
            f"[SEARCH] Set {set_number} | HTTP {response.status} | {len(response.text)} Bytes"
        )

        # Debug: erste Suchantwort als HTML speichern
        if not self._debug_saved:
            try:
                with open('debug_live_response.html', 'w', encoding='utf-8') as dbg:
                    dbg.write(response.text)
                self.logger.info("[SEARCH] debug_live_response.html gespeichert")
            except Exception as e:
                self.logger.warning(f"[SEARCH] Konnte debug_live_response.html nicht speichern: {e}")
            self._debug_saved = True

        # Artikel-Links aus Suchergebnissen sammeln (neue + alte eBay-Struktur)
        items = response.css('li[data-listingid]') or response.css('li.s-item')
        self.logger.info(f"[SEARCH] Items auf Seite: {len(items)}")

        found_links = []
        for item in items:
            link = (item.css('.s-card__link::attr(href)').get()
                    or item.css('.s-item__link::attr(href)').get())
            # Nur echte Artikel (mind. 9-stellige ID, kein Ghost-Placeholder)
            if link and re.search(r'/itm/\d{9,}', link):
                found_links.append(link)
                if len(found_links) >= config.MAX_RESULTS_PER_SET:
                    break

        if found_links:
            self.logger.info(f"[SEARCH] {len(found_links)} Artikel-Link(s) gefunden, rufe Seiten ab")
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
                self.results.append({'row_data': row, 'ebay_price': None, 'ebay_link': None})
                if self._consecutive_empty >= self._max_empty:
                    self.logger.warning(
                        f"[SEARCH] Automatischer Abbruch: {self._max_empty} Sets in Folge ohne Ergebnis"
                    )
                    raise CloseSpider('max_empty_results_reached')

    def parse_item(self, response):
        """Phase 2: Artikelseite → Preis direkt aus JSON-LD oder itemprop extrahieren."""
        row = response.meta['row']
        set_number = response.meta['set_number']

        self.logger.info(
            f"[ITEM] Set {set_number} | HTTP {response.status} | {response.url[:80]}"
        )
        self._consecutive_empty = 0  # Artikelseite erreicht → Leerlauf-Zähler zurücksetzen

        # Titel extrahieren für Blacklist-Prüfung
        title = (
            response.css('h1[itemprop="name"] span::text').get()
            or response.css('.x-item-title__mainTitle span::text').get()
            or response.css('h1.it-ttl::text').get()
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
                    return  # Listing nicht in Ergebnisse aufnehmen

        # Setnummer-Verifikation: Titel muss die gesuchte Setnummer als eigenständige Zahl enthalten
        if config.SET_NUMBER_VERIFY and set_number and title:
            if not re.search(r'\b' + re.escape(str(set_number)) + r'\b', title):
                self.logger.info(
                    f"[ITEM] Set {set_number} → Setnummer nicht im Titel '{title[:60]}' – übersprungen"
                )
                return

        price_val = None
        currency_iso = None  # ISO-Code aus JSON-LD, z.B. "EUR"

        # Methode 1: JSON-LD Structured Data (zuverlässigste Quelle)
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    offers = entry.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price_str = offers.get('price')
                    if price_str:
                        price_val = float(price_str)
                        currency_iso = offers.get('priceCurrency', '')
                        break
            except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
                pass
            if price_val:
                break

        # Methode 2: itemprop="price" content-Attribut
        if price_val is None:
            price_content = response.css('[itemprop="price"]::attr(content)').get()
            if price_content:
                try:
                    price_val = float(price_content)
                    currency_iso = response.css('[itemprop="priceCurrency"]::attr(content)').get() or ''
                except (ValueError, TypeError):
                    pass

        # Methode 3: sichtbarer Preis-Text als letzter Fallback
        if price_val is None:
            price_text = (
                response.css('.x-price-primary span::text').get()
                or response.css('.x-bin-price span::text').get()
                or ''
            ).strip()
            if price_text:
                raw = re.sub(r'[^\d,.]', '', price_text)
                if ',' in raw:
                    raw = raw.replace('.', '').replace(',', '.')
                try:
                    price_val = float(raw) if raw else None
                except ValueError:
                    pass

        # Währungsprüfung
        if config.ALLOWED_CURRENCIES and currency_iso:
            symbol = _ISO_TO_SYMBOL.get(currency_iso.upper(), currency_iso)
            allowed = config.ALLOWED_CURRENCIES
            if symbol not in allowed and currency_iso not in allowed:
                self.logger.info(
                    f"[ITEM] Set {set_number} → Währung '{symbol}' ({currency_iso}) "
                    f"nicht in ALLOWED_CURRENCIES – übersprungen"
                )
                return

        self.logger.info(f"[ITEM] Set {set_number} → Preis: {price_val} {currency_iso or ''}")
        self.results.append({
            'row_data': row,
            'ebay_price': price_val,
            'ebay_link': response.url
        })


def run_scraper():
    print("--- LEGO EBAY ARBITER SCRAPER STARTED ---")
    
    # 0. Proxy Setup
    if config.PROXY_MODE:
        import json
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

    # 1. Daten einlesen
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

    # Polybags herausfiltern (Setnummern 30000–30999, Schema 30xxx)
    polybag_mask = input_df['Set Nummer'].astype(str).str.match(r'^30\d{3}$')
    polybag_count = int(polybag_mask.sum())
    if polybag_count > 0:
        print(f"{polybag_count} Polybag-Sets übersprungen (Setnummern 30xxx).")
    input_df = input_df[~polybag_mask]

    # 2. Merge-Logik (Bereits bearbeitete Einträge ignorieren)
    already_processed_sets = set()
    output_path = os.path.join(config.OUTPUT_FILENAME) # Speichert in Root
    
    if not config.NEW_SCRAPE and os.path.exists(output_path):
        try:
            # Wir checken die anderen Tabellenblätter, ob das Set dort existiert
            for sheet_name in ['Kauf', 'Watchlist', 'Archiv']:
                try:
                    df_sheet = pd.read_excel(output_path, sheet_name=sheet_name)
                    if 'Set Nummer' in df_sheet.columns:
                        already_processed_sets.update(df_sheet['Set Nummer'].astype(str).tolist())
                except ValueError:
                    pass # Blatt existiert nicht
            print(f"{len(already_processed_sets)} Sets übersprungen, da bereits in anderen Reitern einsortiert.")
        except Exception as e:
            print(f"Hinweis beim Lesen der existierenden Output-Datei: {e}")
            
    # Sets filtern
    to_scrape_df = input_df[~input_df['Set Nummer'].astype(str).isin(already_processed_sets)]
    print(f"Starte Scrape für {len(to_scrape_df)} Sets...")

    # 3. Crawler initialisieren & Starten
    process = CrawlerProcess()
    spider_instance = EbayLegoSpider
    
    if len(to_scrape_df) == 0:
        print("Keine neuen Sets zu scrapen.")
        return

    spider_results = []
    process.crawl(spider_instance, sets_df=to_scrape_df, spider_results=spider_results,
                  max_empty=config.MAX_EMPTY_RESULTS)
    try:
        process.start()  # Blockiert bis Spider fertig oder Ctrl+C
    except KeyboardInterrupt:
        print("\n[STOP] Scrape durch Ctrl+C unterbrochen – speichere bisherige Ergebnisse...")

    print(f"[DEBUG] spider_results: {len(spider_results)} Einträge nach Spider-Lauf")
    for r in spider_results[:3]:
        print(f"  → price={r['ebay_price']} | link={str(r['ebay_link'])[:70] if r['ebay_link'] else 'None'}")

    # 4. Resultate aggregieren
    results = spider_results
cc    for r in results:
        row = dict(r['row_data'])
        market_value_raw = str(row.get('Value (€)', '')).replace('$', '').replace(',', '')
        
        try:
            market_value = float(market_value_raw) if market_value_raw.strip() else None
        except ValueError:
            market_value = None
            
        # Alternativ Retail-Preis oder null falls KeyError
        if pd.isna(market_value) and 'Retail-Preis' in row:
            market_value = row.get('Retail-Preis')
            
        ebay_price = r['ebay_price']
        profit_eur = None
        profit_pct = None
        
        if ebay_price and market_value:
            try:
                profit_eur = float(market_value) - float(ebay_price)
                if float(ebay_price) > 0:
                    profit_pct = (profit_eur / float(ebay_price)) * 100
            except ValueError:
                pass
        
        # Überspringen wenn nichts gefunden wurde
        if not r['ebay_link'] and ebay_price is None:
            continue
            
        # Wenn gefunden aber kein Preis
        if r['ebay_link'] and ebay_price is None:
            ebay_price = 'VB'
            
        set_name = row.get('Set Name', '')

        # Layout Aufbau
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
            'eBay Preis': ebay_price,
            'Profit (€)': profit_eur,
            'Profit (%)': profit_pct,
            '_ebay_link': r['ebay_link'],  # Intern für openpyxl – wird vor DataFrame entfernt
        }
        output_data.append(new_row)
        
    # Sortierung: Set Gruppe aufsteigend, dann Set Nummer aufsteigend
    # zfill(10) sorgt für korrekte numerische Reihenfolge (z.B. 9 < 10 statt "9" > "10")
    output_data.sort(key=lambda r: (
        str(r.get('Set Gruppe', '')),
        str(r.get('Set Nummer', '')).zfill(10)
    ))

    # _ebay_link aus output_data herausziehen (internes Feld, gehört nicht in den DataFrame)
    link_data = [{'ebay_link': r.pop('_ebay_link', None)} for r in output_data]
    final_df = pd.DataFrame(output_data)

    # 5. Speichern im Multi-Sheet Excel Format
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Neu gescraptes kommt in Posteingang
        final_df.to_excel(writer, sheet_name='Posteingang', index=False)

        # Anklickbare Hyperlinks in der Set Name-Spalte setzen
        ws = writer.book['Posteingang']
        header = [cell.value for cell in ws[1]]
        set_name_col = header.index('Set Name') + 1
        for row_num, ld in enumerate(link_data, start=2):
            if ld['ebay_link']:
                cell = ws.cell(row=row_num, column=set_name_col)
                cell.hyperlink = ld['ebay_link']
                cell.font = Font(color='0563C1', underline='single')
        
        # Leere Dummy-Sheets generieren (Google Sheets Layout) falls Datei neu ist
        empty_df = pd.DataFrame(columns=final_df.columns)
        for expected_sheet in ['Kauf', 'Watchlist', 'Archiv', 'Löschen']:
            if not config.NEW_SCRAPE and os.path.exists(output_path):
                # Wenn wir updaten, alte Sheets übernehmen
                try:
                    df_old = pd.read_excel(output_path, sheet_name=expected_sheet)
                    df_old.to_excel(writer, sheet_name=expected_sheet, index=False)
                except Exception:
                    empty_df.to_excel(writer, sheet_name=expected_sheet, index=False)
            else:
                empty_df.to_excel(writer, sheet_name=expected_sheet, index=False)
                
    print(f"[DEBUG] output_data: {len(output_data)} Zeilen nach Filterung")
    print(f"✓ Erfolgreich! {len(final_df)} Ergebnisse in '{config.OUTPUT_FILENAME}' (Reiter 'Posteingang') gespeichert.")

if __name__ == "__main__":
    run_scraper()
