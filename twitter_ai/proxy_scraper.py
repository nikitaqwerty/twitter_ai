# twitter_ai/twitter_ai/proxy_scraper.py
import logging
from utils.twitter_utils import ProxyManager
import requests
from bs4 import BeautifulSoup
import time
from utils.db_utils import get_db_connection

logging.basicConfig(level=logging.INFO)


def scrape_proxies():
    with get_db_connection() as db:
        proxy_manager = ProxyManager(db)

        sources = [
            (
                "https://www.sslproxies.org/",
                "sslproxies",
                lambda soup: next(
                    (
                        t
                        for t in soup.find_all("table")
                        if "IP Address"
                        in [th.get_text(strip=True) for th in t.find_all("th")]
                    ),
                    None,
                ),
            ),
            (
                "https://free-proxy-list.net/",
                "freeproxylist",
                lambda soup: soup.find("div", {"class": "table-responsive"}),
            ),
        ]

        for url, source, table_finder in sources:
            try:
                resp = requests.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                table = table_finder(soup)
                proxies = []

                if table:
                    rows = table.tbody.find_all("tr") if table.tbody else []
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            ip = cells[0].text.strip()
                            port = cells[1].text.strip()
                            proxies.append(f"{ip}:{port}")

                if proxies:
                    proxy_manager.add_proxies(proxies, source)
                    logging.info(f"Added {len(proxies)} proxies from {source}")
                else:
                    logging.warning(f"No proxies found at {source}")

            except Exception as e:
                logging.error(f"Failed to scrape {source}: {str(e)}")
            time.sleep(5)


if __name__ == "__main__":
    while True:
        scrape_proxies()
        time.sleep(60)
