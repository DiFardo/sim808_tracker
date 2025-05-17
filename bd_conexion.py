
import psycopg2

from dotenv import load_dotenv
import os

load_dotenv() 

def obtener_conexion():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )