from playwright.sync_api import sync_playwright
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz
from feedgen.feed import FeedGenerator
from dateutil.parser import parse
from urllib.parse import urljoin
import logging
logging.basicConfig(level=logging.INFO)

tz = pytz.timezone('Asia/Shanghai')


class Selector:
    def __init__(self, container, link, title, date):
        """
        Initialize a Selector object for scraping web elements.

        Args:
            container (str): CSS selector for the container element
            link (str): CSS selector for the link element relative to container
            title (str): CSS selector for the title element relative to container
            date (str): CSS selector for the date element relative to container
        """
        self.container = container
        self.link = link
        self.title = title
        self.date = date


class RSS:
    connect_max_retries = 3

    def __init__(self, url, output_file, title=None, description=None):
        """
        Initialize an RSS feed object.

        Args:
            url (str): The URL of the website providing the RSS feed
            title (str): The title of the RSS feed
            description (str): A description of the RSS feed
            output_file (str): The file path where the RSS feed will be saved
        """
        self.url = url
        self.title = title
        self.description = description
        self.entries = []
        self.output_file = output_file

    def get_response(self):
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--dns-prefetch-disable",
                    ]
                )

                for attempt in range(RSS.connect_max_retries):
                    context = None
                    page = None
                    try:
                        context = browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            viewport={'width': 1920, 'height': 1080},
                            ignore_https_errors=True
                        )
                        
                        page = context.new_page()
                        page.set_default_timeout(60000)  # 3 minutes timeout
                        
                        response = page.goto(
                            self.url,
                            wait_until="networkidle",
                            timeout=60000
                        )
                        
                        if not response.ok:
                            raise Exception(f"HTTP {response.status}: {response.status_text}")
                        
                        # Wait for content with increased timeout
                        page.wait_for_selector(
                            f"{self.selector.container} >> nth=0",
                            timeout=60000,
                            state="visible"
                        )
                        page.wait_for_timeout(5000)  # 5 second wait
                        
                        # Extract content
                        self._extract_page_content(page)
                        
                        return  # Success - exit method
                        
                    except Exception as e:
                        logging.warning(
                            f"Attempt {attempt + 1}/{RSS.connect_max_retries} failed for {self.url}: {str(e)}")
                        
                        if attempt == RSS.connect_max_retries - 1:
                            raise
                        
                        # Cleanup before retry
                        if page:
                            try:
                                page.close()
                            except:
                                pass
                        if context:
                            try:
                                context.close()
                            except:
                                pass
                                
                        # Wait with exponential backoff
                        import time
                        time.sleep(5 * (2 ** attempt))  # 5, 10, 20 seconds
                        
        except Exception as e:
            logging.error(f"Failed to process {self.url}: {str(e)}")
            raise
        finally:
            if browser:
                try:
                    browser.close()
                except:
                    pass

    def _extract_page_content(self, page):
        """Extract content from loaded page"""
        self.title = page.title()
        description_element = page.query_selector(
            'head > meta[name="description"], head > meta[name*="description"], head > meta[name*="Description"]'
        )
        self.description = description_element.get_attribute("content") if description_element else None

        container = page.query_selector_all(self.selector.container)
        if not container:
            raise Exception(f"No elements found matching selector: {self.selector.container}")
            
        logging.info(f"Found {len(container)} entries in {self.title}")
        self.clear_entries()

        for ele in container:
            try:
                self._process_single_entry(ele, page)
            except Exception as e:
                logging.warning(f"Failed to process entry: {str(e)}")
                continue

    def _process_single_entry(self, ele, page):
        try:
            link_element = ele.query_selector(self.selector.link)
            title_element = ele.query_selector(self.selector.title)
            date_element = ele.query_selector(self.selector.date)

            link = title = published_date = date_with_tz = None

            link = link_element.get_attribute("href")
            # Ensure the link is absolute
            link = urljoin(self.url, link)
            title = title_element.inner_text().strip()
            published_date = date_element.inner_text().strip()
            date_with_tz = None  # 解析失败则设为 None
            try:
                date_obj = parse(published_date)  # 自动解析多种格式
                date_with_tz = tz.localize(date_obj)
            except ValueError:
                logging.error(f"Date parsing error for entry: {published_date}")

            self.add_entry(date=date_with_tz, title=title, link=link)
        except Exception as e:
            logging.error(f"Error processing entry: {str(e)}")
            raise

    def gen_feed(self):
        # Sort entries by date
        self.entries.sort(key=lambda x: x[0])

        fg = FeedGenerator()
        fg.title(title=self.title)
        fg.link(href=self.url)
        fg.description(description=self.description)
        fg.language('zh-CN')
        fg.id(self.url)

        # Add sorted entries to feed
        for date, title, link in self.entries:
            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=link)
            fe.guid(link)
            fe.description(title)
            fe.pubDate(date)

        fg.rss_str(pretty=True)
        fg.rss_file(self.output_file, pretty=True)

    def rss_builder(self, selector):
        if not isinstance(selector, Selector):
            raise TypeError("Expected Selector object")
        self.selector = selector
        self.get_response()
        self.gen_feed()

    def add_entry(self, date, title, link):
        """
        Add an entry to the RSS feed.
        
        Args:
            date (datetime): The publication date of the entry
            title (str): The title of the entry
            link (str): The URL link to the entry
        """
        self.entries.append((date, title, link))

    def clear_entries(self):
        """Clear all entries from the RSS feed."""
        self.entries = []

    @classmethod
    def update_feeds(cls, sites):
        """Update all RSS feeds in the sites list"""
        for rss, selector in sites:
            try:
                rss.rss_builder(selector)
                logging.info(f"Successfully processed {rss.url}")
            except Exception as e:
                logging.error(f"Failed to process {rss.url}: {str(e)}")

    @classmethod
    def start_schedule(cls, sites, hours=1, minutes=0, seconds=0):
        """
        Start a scheduled task to update RSS feeds periodically.
        
        Args:
            sites: List of (RSS, Selector) tuples to process
            hours (int): Hours between updates
            minutes (int): Minutes between updates
            seconds (int): Seconds between updates
        """
        logging.basicConfig()
        scheduler = BlockingScheduler()
        scheduler.add_job(
            cls.update_feeds,
            'interval',
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            args=[sites]
        )
        logging.info(
            f"Starting scheduler - Updates every {hours}h {minutes}m {seconds}s")
        scheduler.start()


if __name__ == "__main__":
    sites = [
        (RSS(url="https://gdstc.gd.gov.cn/zwgk_n/tzgg/index.html",
             output_file='gdstc.xml'),
         Selector(container='ul.list li',
                  link='a',
                  title='a',
                  date='span.time')),
        (RSS(url="https://kjj.gz.gov.cn/xxgk/zcfg/index.html",
             output_file='gzkjj.xml'),
         Selector(container='div.news_list ul li',
                  link='a',
                  title='a',
                  date='span.time')),
        (RSS(url="https://www.hp.gov.cn/gzhpkj/gkmlpt/index",
             output_file='hp.xml'),
         Selector(container='table.table-content tbody tr:not(.header)',
                  link='td:nth-child(1) a',
                  title='td:nth-child(1) a',
                  date='td:nth-child(2)'))
    ]

    # Run once immediately
    RSS.update_feeds(sites)

    # Then start the scheduler (updates every hour by default)
    # RSS.start_schedule(sites, hours=0, minutes=5, seconds=0)
