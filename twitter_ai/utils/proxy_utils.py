from pathlib import Path
import logging
from utils.db_utils import get_db_connection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ProxyManager:
    def __init__(self):
        self._init_proxies_from_csv()

    def _init_proxies_from_csv(self):
        csv_path = Path("proxies.csv")
        if csv_path.exists():
            with open(csv_path, "r") as f:
                proxies = []
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(":")
                        if len(parts) == 4:
                            domain, port, user, password = parts
                            proxy = f"{user}:{password}@{domain}:{port}"
                            proxies.append(proxy)
                if proxies:
                    self.add_proxies(proxies, "smartproxy-residential-rotating")

    def get_next_proxy(self, source=None):
        with get_db_connection() as db:
            source_condition = "AND source = %s" if source else ""
            query = f"""
                UPDATE proxies
                SET last_used = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM proxies
                    WHERE status = 'good' 
                    --AND x_guest_token IS NOT NULL
                    {source_condition}
                    ORDER BY last_used NULLS FIRST
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING address, x_guest_token;
            """
            params = [source] if source else []
            result = db.run_query(query, params) if params else db.run_query(query)
            return result[0] if result else None

    def mark_bad(self, address, error=None):
        with get_db_connection() as db:
            query = """
                UPDATE proxies 
                SET status = 'bad', 
                    last_checked = CURRENT_TIMESTAMP, 
                    error = %s,
                    attempts = attempts + 1
                WHERE address = %s;
            """
            db.run_query(query, (error, address))

    def add_proxies(self, proxies, source):
        with get_db_connection() as db:
            query = """
                INSERT INTO proxies (address, source)
                VALUES (%s, %s)
                ON CONFLICT (address) DO NOTHING;
            """
            params = [(proxy, source) for proxy in proxies]
            db.run_insert_query(query, params)

    def update_proxy_token(self, address, token):
        with get_db_connection() as db:
            query = """
                UPDATE proxies
                SET x_guest_token = %s, 
                    status = 'good', 
                    last_checked = CURRENT_TIMESTAMP,
                    attempts = 0
                WHERE address = %s;
            """
            db.run_query(query, (token, address))


PROXY_MANAGER = ProxyManager()
