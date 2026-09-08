"""Small MySQL connection helper for the CRFOS application."""

import mysql.connector
from mysql.connector import Error

from config import Config


class DatabaseConnectionError(RuntimeError):
    """Raised when a database connection cannot be created."""


def get_db_connection():
    """Return a new MySQL connection using the configured environment values.

    Connections are opened only when a service requests one, so Flask pages that
    do not need database data remain available while MySQL is offline.
    """

    required_settings = {
        "DB_HOST": Config.DB_HOST,
        "DB_PORT": Config.DB_PORT,
        "DB_USER": Config.DB_USER,
        "DB_NAME": Config.DB_NAME,
    }
    missing_settings = [name for name, value in required_settings.items() if not value]
    if missing_settings:
        missing = ", ".join(missing_settings)
        raise DatabaseConnectionError(f"Database configuration is incomplete: {missing}.")

    try:
        return mysql.connector.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
    except (Error, ValueError) as error:
        raise DatabaseConnectionError("Unable to connect to the CRFOS database.") from error


def create_database():
    """Create the configured database when the MySQL server is available.

    This does not create tables; run ``schema.sql`` afterwards for that.
    """

    if not Config.DB_NAME:
        raise DatabaseConnectionError("Database configuration is incomplete: DB_NAME.")

    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME.replace('`', '``')}`")
        connection.commit()
        cursor.close()
        connection.close()
    except (Error, ValueError) as error:
        raise DatabaseConnectionError("Unable to create the CRFOS database.") from error


def test_connection():
    """Return True when the configured CRFOS database can be reached."""

    connection = get_db_connection()
    try:
        return connection.is_connected()
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        print("Database connection successful." if test_connection() else "Database connection failed.")
    except DatabaseConnectionError as error:
        print(f"Database connection failed: {error}")
