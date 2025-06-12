# database_setup.py
import psycopg2
from psycopg2 import sql            # Para construir consultas de forma segura
from urllib.parse import urlparse   # Para parsear la DATABASE_URL
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db_url = os.getenv("DATABASE_URL")
load_dotenv()


def get_db_connection(db_url):
    if not db_url:
        logger.error("DATABASE_URL no está configurada en las variables de entorno.")
        raise ValueError("DATABASE_URL no está configurada.")

    # urlparse ayuda a descomponer la DATABASE_URL en sus componentes
    result = urlparse(db_url)
    username = result.username
    password = result.password
    database = result.path[1:] # Elimina el '/' inicial
    hostname = result.hostname
    port = result.port

    try:
        conn = psycopg2.connect(
            host=hostname,
            database=database,
            user=username,
            password=password,
            port=port,
            # Opcional: timeout para conexiones
            connect_timeout=5
        )
        # Por defecto, psycopg2 no hace commit automáticamente
        conn.autocommit = False # Generalmente querrás commits manuales
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error al conectar a la base de datos PostgreSQL: {e}")
        raise # Re-lanza la excepción para que el bot se detenga si la conexión falla



def initialize_db(db_url):
    conn = None
    try:
        conn = get_db_connection(db_url)
        cursor = conn.cursor()

        # --- Tabla para registros de telecom ---
        # Cambios: SERIAL PRIMARY KEY (en lugar de INTEGER PRIMARY KEY AUTOINCREMENT)
        # DOUBLE PRECISION (en lugar de REAL)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros_telecom (
                id SERIAL PRIMARY KEY,
                fecha_hora TIMESTAMP NOT NULL,
                numeroa VARCHAR(50),
                sentido VARCHAR(10),
                numerob VARCHAR(50),
                direccion VARCHAR(255),
                localidad VARCHAR(100),
                provincia VARCHAR(100),
                latitud DOUBLE PRECISION,
                longitud DOUBLE PRECISION,
                radiocobertura DOUBLE PRECISION,
                azimut DOUBLE PRECISION,
                aperhorizontal DOUBLE PRECISION,
                apervertical DOUBLE PRECISION
            );
        """)

        # --- Tabla para usuarios autorizados ---
        # Asegúrate de que 'role' tenga un valor DEFAULT o sea NOT NULL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authorized_users (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                role VARCHAR(50) DEFAULT 'viewer' NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        logger.info("Base de datos PostgreSQL inicializada o ya existente.")
    except psycopg2.Error as e:
        logger.error(f"Error al inicializar la base de datos PostgreSQL: {e}")
        raise # Es crítico que la DB se inicialice correctamente
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("La variable de entorno DATABASE_URL no está definida.")
    initialize_db(db_url)
