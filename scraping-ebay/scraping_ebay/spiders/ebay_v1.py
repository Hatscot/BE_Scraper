# -*- coding: utf-8 -*-
import scrapy
import pandas as pd
import re
from scrapy.utils.project import get_project_settings

class EbayV1Spider(scrapy.Spider):
    name = "ebay_v1"

    # Browser-ähnliche Headers, um Bot-Erkennung zu vermeiden
    default_headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/84.0.4147.125 Safari/537.36 Edg/84.0.522.59'
        ),
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    custom_settings = {
        'ITEM_PIPELINES': {
            'scraping_ebay.pipelines.EbayImagesPipeline': 1,
        }
    }

    def errback_handler(self, failure):
        """
        Handhabt fehlgeschlagene Requests und loggt sie.
        """
        sw = failure.request.meta.get('sw_code', '<unknown>')
        err = failure.value.__class__.__name__
        self.logger.error(f"Error bei {sw}: {err} – {failure.request.url}")
        # Optional: yielde ein Fehler-Item für die Nachverfolgung
        yield {
            'sw_code': sw,
            'image_urls': [],
            'error': err,
        }

    def start_requests(self):
        """
        Liest SW-Codes & URLs aus der CSV und startet Requests mit errback.
        """
        settings = get_project_settings()
        csv_path = settings.get('CSV_LINKS_PATH')
        df = pd.read_csv(csv_path, dtype=str)
        for _, row in df.iterrows():
            sw_code = row.get('SW_Code') or row.get('SW_code') or row.get('sw_code')
            url = row.get('Item_Link') or row.get('item_link') or row.get('URL')
            downloaded = row.get('Downloaded') or row.get('downloaded')
            # Überspringe Einträge, die bereits als "1" markiert sind
            if downloaded and downloaded.strip() == '1':
                continue
            if not sw_code or not url:
                continue
            yield scrapy.Request(
                url=url.strip(),
                callback=self.parse_entry,
                errback=self.errback_handler,
                headers=self.default_headers,
                meta={'sw_code': sw_code.strip()}
            )

    def parse_entry(self, response):
        """
        Folgt dem "Originalangebot ansehen"-Link, falls vorhanden.
        """
        original = response.xpath("//a[contains(text(), 'Originalangebot ansehen')]/@href").get()
        if original:
            yield response.follow(
                original,
                callback=self.parse_images,
                errback=self.errback_handler,
                headers=self.default_headers,
                meta=response.meta
            )
        else:
            yield from self.parse_images(response)

    def parse_images(self, response):
        """
        Extrahiert Bild-URLs (Galeriethumbnails, OG-Meta, Hauptbild) und yielde das Item.
        """
        sw_code = response.meta['sw_code']
        image_urls = []

        # eBay UX Carousel: data-zoom-src und src
        imgs = response.xpath("//div[@data-testid='ux-image-carousel-container']//img")
        for img in imgs:
            zoom_attr = img.xpath('./@data-zoom-src').get()
            if zoom_attr:
                for part in zoom_attr.split(','):
                    url = part.strip()
                    if url and not url.startswith('data:'):
                        full = re.sub(r's-l\d+', 's-l1600', url)
                        if full not in image_urls:
                            image_urls.append(full)
                continue
            src_attr = img.xpath('./@src').get()
            if src_attr and not src_attr.startswith('data:'):
                full = re.sub(r's-l\d+', 's-l1600', src_attr)
                if full not in image_urls:
                    image_urls.append(full)

        # Fallback: Open Graph Meta Image
        if not image_urls:
            og = response.xpath("//meta[@property='og:image']/@content").get()
            if og:
                full = re.sub(r's-l\d+', 's-l1600', og)
                image_urls.append(full)

        # Fallback: klassisches Hauptbild
        if not image_urls:
            main = response.xpath("//img[@id='icImg']/@src").get()
            if main:
                full = re.sub(r's-l\d+', 's-l1600', main)
                image_urls.append(full)

        if image_urls:
            self.logger.info(f"Found {len(image_urls)} images for {sw_code}")
            yield {
                'sw_code': sw_code,
                'image_urls': image_urls
            }
        else:
            self.logger.warning(f"No images found for {sw_code} at {response.url}")
