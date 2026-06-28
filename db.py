import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="syttpz",
        password="Eiei1447",
        database="airline_db"
    )