import asyncio
import logging
from utils.twitter_utils import ProxyManager
import aiohttp
from bs4 import BeautifulSoup
from utils.db_utils import get_db_connection
import itertools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROXY_CHECK_URL = "https://api.twitter.com/1.1/application/rate_limit_status.json"
HEADERS = {
    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}
CONCURRENCY_LIMIT = 250
REQUEST_TIMEOUT = 20
SCRAPE_SOURCES = [
    (
        "https://www.sslproxies.org/",
        "sslproxies",
        lambda soup: next(
            (
                t
                for t in soup.find_all("table")
                if "IP Address" in [th.get_text(strip=True) for th in t.find_all("th")]
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


async def check_proxy(proxy_manager, proxy):
    try:
        headers = HEADERS.copy()
        async with aiohttp.ClientSession(
            headers=headers,
            connector=aiohttp.TCPConnector(ssl=False),
        ) as session:
            # Activate guest token
            post_url = "https://api.twitter.com/1.1/guest/activate.json"
            async with session.post(
                post_url,
                proxy=f"http://{proxy}",
                timeout=REQUEST_TIMEOUT,
            ) as response:
                text = await response.text()
                if not text.strip().startswith("{"):
                    raise ValueError("Proxy returns non-JSON response")
                data = await response.json()
                guest_token = data.get("guest_token")
                if not guest_token:
                    raise ValueError("Missing guest token in response")

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, proxy_manager.update_proxy_token, proxy, guest_token
            )
            logger.info(f"Validated proxy {proxy}")

    except Exception as e:
        logger.error(f"Proxy {proxy} failed: {str(e)}")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, proxy_manager.mark_bad, proxy, str(e))


async def check_proxies_async(proxy_manager):
    query = """
        SELECT address FROM proxies 
        WHERE (
        (error IS NULL OR error LIKE '%%timed out%%' or error LIKE '%%503%%' or error = '')
          AND attempts < 10
          AND (last_checked < NOW() - INTERVAL '10 minutes' 
          or last_checked is null) )
        ORDER BY last_checked NULLS FIRST 
        LIMIT 1000
        FOR UPDATE SKIP LOCKED;
    """
    with get_db_connection() as db:
        proxies = [p[0] for p in db.run_query(query) or []]

    if not proxies:
        return

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def check(proxy):
        async with semaphore:
            await check_proxy(proxy_manager, proxy)

    tasks = [check(proxy) for proxy in proxies]
    await asyncio.gather(*tasks)


# Rest of the file remains unchanged (scrape_source, scrape_proxies_async, chunks, main_loop)
async def scrape_source(session, url, source, table_finder):
    try:
        async with session.get(url, timeout=15) as response:
            html = await response.text()
            loop = asyncio.get_running_loop()
            soup = await loop.run_in_executor(None, BeautifulSoup, html, "html.parser")
            table = await loop.run_in_executor(None, table_finder, soup)

            proxies = []
            if table:
                rows = table.tbody.find_all("tr") if table.tbody else []
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        ip = cells[0].text.strip()
                        port = cells[1].text.strip()
                        proxies.append(f"{ip}:{port}")

            return source, proxies

    except Exception as e:
        logger.error(f"Failed to scrape {source}: {str(e)}")
        return source, []


async def scrape_proxies_async(proxy_manager):
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            scrape_source(session, url, source, table_finder)
            for url, source, table_finder in SCRAPE_SOURCES
        ]
        results = await asyncio.gather(*tasks)

    for source, proxies in results:
        if proxies:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, proxy_manager.add_proxies, proxies, source)
            logger.info(f"Added {len(proxies)} proxies from {source}")


def chunks(iterable, size):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            return
        yield chunk


async def main_loop():
    proxy_manager = ProxyManager()
    while True:
        logger.info("Starting proxy scraping cycle")
        await scrape_proxies_async(proxy_manager)

        logger.info("Starting proxy validation cycle")
        await check_proxies_async(proxy_manager)

        logger.info("Cycle completed, sleeping for 10 seconds")
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main_loop())
