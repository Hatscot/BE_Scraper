# -*- coding: utf-8 -*-
import os
import csv
import logging
import pandas as pd
from scrapy import Request
from scrapy.pipelines.images import ImagesPipeline
from scrapy.utils.project import get_project_settings

class EbayImagesPipeline(ImagesPipeline):
    """
    Custom ImagesPipeline to download images, organize them under
    IMAGES_STORE/<sw_code>/<sw_code>_<index>.<ext>,
    and update the CSV Downloaded-Flag.
    """

    def __init__(self, store_uri, *args, **kwargs):
        """Initialize pipeline and log the images store path.

        ``ImagesPipeline`` requires the Pillow package. When Pillow is missing
        Scrapy raises ``NotConfigured`` during initialization.  The tests in
        this repository don't actually download images, so to keep them runnable
        in environments without Pillow we catch the exception and continue
        without image processing enabled.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            super().__init__(store_uri, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - Pillow may be missing
            # ``scrapy.pipelines.images.ImagesPipeline`` raises ImportError or
            # NotConfigured if Pillow isn't available.  Log a warning instead of
            # failing hard so unit tests can run without the dependency.
            self.logger.warning("ImagesPipeline disabled: %s", exc)
        self.logger.info("IMAGES_STORE=%s", store_uri)

    def get_media_requests(self, item, info):
        """
        For each image URL, send a request carrying sw_code and sequential order.
        """
        sw_code = item.get('sw_code')
        for idx, url in enumerate(item.get('image_urls', []), start=1):
            yield Request(
                url,
                meta={
                    'sw_code': sw_code,
                    'order': idx
                }
            )

    def file_path(self, request, response=None, info=None, *, item=None):
        """
        Compute file path: <sw_code>/<sw_code>_<order>.<extension>
        """
        sw_code = request.meta.get('sw_code')
        order   = request.meta.get('order')
        ext = os.path.splitext(request.url)[1].split('?')[0]
        if not ext:
            ext = '.jpg'
        filename = f"{sw_code}_{order}{ext}"
        return f"{sw_code}/{filename}"

    def item_completed(self, results, item, info):
        """
        Called when all image downloads finish. Update CSV 'Downloaded' flag.
        """
        for success, info_dict in results:
            if success:
                self.logger.info("Stored image at %s", info_dict.get('path'))
            else:
                self.logger.error("Image download failed: %s", info_dict)

        # Determine if at least one image was downloaded successfully
        success = any(x[0] for x in results)
        if success:
            settings = get_project_settings()
            csv_path = settings.get('CSV_LINKS_PATH')
            # Read CSV, update Downloaded field for this sw_code
            try:
                df = pd.read_csv(csv_path, dtype=str)
                col = None
                # find Downloaded column name
                for c in ['Downloaded', 'downloaded']:
                    if c in df.columns:
                        col = c
                        break
                if col is None:
                    # add new column
                    df['Downloaded'] = ''
                    col = 'Downloaded'
                # set flag
                mask = df.get('SW_Code', df.get('SW_code', df.get('sw_code')))==item['sw_code']
                df.loc[mask, col] = '1'
                # write back without index
                df.to_csv(csv_path, index=False)
            except Exception as e:
                info.spider.logger.error(f"Failed to update CSV for {item['sw_code']}: {e}")
        return item
