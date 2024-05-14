from db.database import Database, drop_all_tables, create_all_tables

if __name__ == "__main__":
    database = Database("localhost", "crypto-twitter", "myuser", "mypassword")
    database.connect()

    drop_all_tables(database)
    create_all_tables(database)

    database.close()
