import logging
from utils.twitter_utils import ProxyManager
import requests
from bs4 import BeautifulSoup
import time
from utils.db_utils import get_db_connection
from twitter.util import init_session

logging.basicConfig(level=logging.INFO)


def check_proxies():
    proxy_manager = ProxyManager()

    # Get proxies needing verification
    query = """
        SELECT address FROM proxies 
        WHERE (error IS NULL OR error LIKE '%%timed out%%' or error LIKE '%%503%%')
          AND attempts < 10
          AND (status IN ('new', 'good') 
               OR last_checked < NOW() - INTERVAL '1 hour')
        ORDER BY last_checked NULLS FIRST 
        LIMIT 50
        FOR UPDATE SKIP LOCKED;
    """
    with get_db_connection() as db:
        proxies = db.run_query(query)
    if not proxies:
        return

    for (proxy,) in proxies:
        try:
            # Get fresh guest token through proxy
            session = init_session(proxy=proxy)
            guest_token = session.headers.get("x-guest-token")

            # Update proxy with valid token
            proxy_manager.update_proxy_token(proxy, guest_token)
            logging.info(f"Validated proxy {proxy}")
            session.close()

        except Exception as e:
            proxy_manager.mark_bad(proxy, str(e).split("validation:")[-1])
            logging.error(f"Proxy {proxy} failed: {str(e)}")


def scrape_proxies():
    proxy_manager = ProxyManager()

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


if __name__ == "__main__":
    while True:
        scrape_proxies()
        check_proxies()
