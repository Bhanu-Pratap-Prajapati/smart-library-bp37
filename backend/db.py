import mysql.connector
from mysql.connector import Error

from config import config


class DatabaseManager:
    def __init__(self):
        self.connection_config = {
            "host": config.host,
            "port": config.port,
            "user": config.user,
            "password": config.password,
            "database": config.database,
            "ssl_disabled":False
        }

    def get_connection(self):
        return mysql.connector.connect(**self.connection_config)

    def test_connection(self):
        connection = None
        try:
            connection = self.get_connection()
            return connection.is_connected(), "Database connection successful."
        except Error as exc:
            return False, str(exc)
        finally:
            if connection and connection.is_connected():
                connection.close()


db = DatabaseManager()
