import os
import sys

# Ensure that the path to the utilities and other dependencies is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_db_connection, create_all_tables

if __name__ == "__main__":

    with get_db_connection() as db:

        # drop_all_tables(database)
        create_all_tables(db)
