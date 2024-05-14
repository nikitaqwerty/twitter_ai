import psycopg2
from contextlib import contextmanager


class Database:
    def __init__(self, host, database, user, password):
        self.conn_params = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
        }
        self.connection = None
        self.cursor = None

    def __enter__(self):
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            self.cursor = self.connection.cursor()
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None
            self.cursor = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            if exc_type is not None:
                self.connection.rollback()
            else:
                self.connection.commit()
            self.connection.close()

    def run_query(self, query, params=None):
        if self.cursor is None:
            raise AttributeError(
                "Cursor is not initialized. Check the database connection."
            )
        self.cursor.execute(query, params or ())
        self.connection.commit()  # Ensure that changes are committed
        try:
            return self.cursor.fetchall()
        except psycopg2.ProgrammingError:
            return None

    def run_batch_query(self, query, params_list):
        if self.cursor is None:
            raise AttributeError(
                "Cursor is not initialized. Check the database connection."
            )
        self.cursor.executemany(query, params_list)
        self.connection.commit()  # Ensure that changes are committed

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
