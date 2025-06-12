import psycopg2
from psycopg2 import sql      # Para construir consultas de forma segura
from database_setup import get_db_connection
from urllib.parse import urlparse
from sqlalchemy import create_engine
import numpy as np 
import pandas as pd
import random
import folium
import os          # Para manejar archivos temporales
import uuid        # Para generar nombres de archivos únicos

import re
import datetime
import logging
from dotenv import load_dotenv
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

from io import BytesIO              # Para manejar archivos en memoria
from urllib.parse import urlparse   # Para parsear la DATABASE_URL

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Import the database initialization script
from database_setup import initialize_db

# Variable global para almacenar la URL de la base de datos
load_dotenv()
import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv("DATABASE_URL"))

DATABASE_URL = os.getenv("DATABASE_URL")


# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
#DB_NAME = os.getenv("DB_NAME")
MAP_FILE_NAME = os.getenv("MAP_FILE_NAME") # Nombre del archivo HTML del mapa


# Configura el logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Obtener IDs autorizados
#AUTHORIZED_CHAT_IDS_STR = os.getenv("AUTHORIZED_CHAT_IDS")
# Convertir la cadena de IDs a una lista de enteros
#AUTHORIZED_CHAT_IDS = [int(id_str.strip()) for id_str in AUTHORIZED_CHAT_IDS_STR.split(',') if id_str.strip()] if AUTHORIZED_CHAT_IDS_STR else []
#logger.info(f"IDs de chat autorizados cargados: {AUTHORIZED_CHAT_IDS}")

user_roles = {} 

def load_authorized_chat_ids_from_db():
    """Carga los IDs autorizados y roles desde la base de datos."""
    global user_roles, current_authorized_chat_ids
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Selecciona chat_id y role
        cursor.execute("SELECT chat_id, role FROM authorized_users")
        rows = cursor.fetchall()
        
        # Actualizar roles
        new_user_roles = {row[0]: row[1] for row in rows}
        if new_user_roles != user_roles:
            logger.info(f"Roles de usuario actualizados. Antiguos: {user_roles}. Nuevos: {new_user_roles}")
        user_roles = new_user_roles

        # Actualizar IDs autorizados
        new_ids = {row[0] for row in rows}
        added_ids = new_ids - current_authorized_chat_ids
        removed_ids = current_authorized_chat_ids - new_ids
        if added_ids:
            logger.info(f"IDs autorizados añadidos: {added_ids}")
        if removed_ids:
            logger.info(f"IDs autorizados eliminados: {removed_ids}")
        current_authorized_chat_ids = new_ids

        logger.info(f"IDs de chat autorizados cargados/refrescados desde DB. Total: {len(current_authorized_chat_ids)}")
    except psycopg2.Error as e:
        logger.error(f"Error cargando roles de usuario desde la DB: {e}")
    finally:
        if conn:
            conn.close()

# Modifica is_authorized para obtener el rol, y crea has_role
def get_user_role(user_id: int) -> str:
    """Devuelve el rol de un usuario o 'unauthorized' si no está en la lista."""
    # Para la primera vez que el bot corre y no hay usuarios en la DB,
    # puedes permitir un "super-admin" inicial vía variable de entorno.
    SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0")) 
    
    if not user_roles and user_id == SUPER_ADMIN_ID:
        logger.warning(f"Super-admin {user_id} autorizado con rol 'admin' (lista vacía).")
        return 'admin' # Rol de administrador para el super-admin inicial
        
    return user_roles.get(user_id, 'unauthorized')

def has_role(user_id: int, required_role: str) -> bool:
    """Verifica si un usuario tiene el rol requerido o superior."""
    user_role = get_user_role(user_id)
    
    # Define la jerarquía de roles
    role_hierarchy = {'unauthorized': 0, 'viewer': 1, 'editor': 2, 'admin': 3}
    
    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)

# La función unauthorized_access_message puede seguir siendo la misma

# Función para obtener la conexión a la base de datos
def get_db_connection():
    if not DATABASE_URL:
        logger.error("DATABASE_URL no está configurada en las variables de entorno.")
        raise ValueError("DATABASE_URL no está configurada.")

    # urlparse ayuda a descomponer la DATABASE_URL en sus componentes
    result = urlparse(DATABASE_URL)
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


# Función para cargar los IDs autorizados desde la base de datos
def load_authorized_chat_ids_from_db():
    """Carga los IDs autorizados y roles desde la base de datos."""
    global user_roles, current_authorized_chat_ids
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Selecciona chat_id y role
        cursor.execute("SELECT chat_id, role FROM authorized_users")
        rows = cursor.fetchall()
        
        # Actualizar roles
        new_user_roles = {row[0]: row[1] for row in rows}
        if new_user_roles != user_roles:
            logger.info(f"Roles de usuario actualizados. Antiguos: {user_roles}. Nuevos: {new_user_roles}")
        user_roles = new_user_roles

        # Actualizar IDs autorizados
        new_ids = {row[0] for row in rows}
        added_ids = new_ids - current_authorized_chat_ids
        removed_ids = current_authorized_chat_ids - new_ids
        if added_ids:
            logger.info(f"IDs autorizados añadidos: {added_ids}")
        if removed_ids:
            logger.info(f"IDs autorizados eliminados: {removed_ids}")
        current_authorized_chat_ids = new_ids

        logger.info(f"IDs de chat autorizados cargados/refrescados desde DB. Total: {len(current_authorized_chat_ids)}")
    except psycopg2.Error as e:
        logger.error(f"Error cargando roles de usuario desde la DB: {e}")
    finally:
        if conn:
            conn.close()


async def add_authorized_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Añade un nuevo chat_id a la tabla de usuarios autorizados."""
    requester_id = update.effective_user.id
    if not is_authorized(requester_id):
        await unauthorized_access_message(update, context)
        return

    if not context.args:
        await update.message.reply_text("Uso: /add_authorized <ID_de_usuario_telegram> [nombre_de_usuario_telegram]")
        return

    try:
        new_auth_id = int(context.args[0])
        new_username = context.args[1] if len(context.args) > 1 else None
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # ON CONFLICT DO NOTHING evita errores si el ID ya existe
            cursor.execute(
                "INSERT INTO authorized_users (chat_id, username) VALUES (%s, %s) ON CONFLICT (chat_id) DO NOTHING",
                (new_auth_id, new_username)
            )
            conn.commit()
            if cursor.rowcount > 0: # Si se insertó una fila
                load_authorized_chat_ids_from_db() # Refresca la lista en memoria
                await update.message.reply_text(f"Usuario `{new_auth_id}` (`{new_username or 'N/A'}`) agregado a la lista de autorizados.", parse_mode='MarkdownV2')
                logger.info(f"User {requester_id} added new authorized user: {new_auth_id} ({new_username}).")
            else:
                await update.message.reply_text(f"El usuario `{new_auth_id}` ya está en la lista de autorizados.", parse_mode='MarkdownV2')
        except psycopg2.Error as e:
            logger.error(f"Error adding authorized user {new_auth_id}: {e}", exc_info=True)
            await update.message.reply_text(f"Error al agregar usuario: {e}")
        finally:
            if conn:
                conn.close()

    except ValueError:
        await update.message.reply_text("Por favor, introduce un ID de usuario válido (número).")
    except Exception as e:
        logger.error(f"Unexpected error in add_authorized_user: {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error inesperado.")


async def remove_authorized_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina un chat_id de la tabla de usuarios autorizados."""
    requester_id = update.effective_user.id
    if not is_authorized(requester_id):
        await unauthorized_access_message(update, context)
        return

    if not context.args:
        await update.message.reply_text("Uso: /remove_authorized <ID_de_usuario_telegram>")
        return

    try:
        auth_id_to_remove = int(context.args[0])
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM authorized_users WHERE chat_id = %s",
                (auth_id_to_remove,)
            )
            conn.commit()
            if cursor.rowcount > 0: # Si se eliminó una fila
                load_authorized_chat_ids_from_db() # Refresca la lista en memoria
                await update.message.reply_text(f"Usuario `{auth_id_to_remove}` eliminado de la lista de autorizados.", parse_mode='MarkdownV2')
                logger.info(f"User {requester_id} removed authorized user: {auth_id_to_remove}.")
            else:
                await update.message.reply_text(f"El usuario `{auth_id_to_remove}` no se encontró en la lista de autorizados.", parse_mode='MarkdownV2')
        except psycopg2.Error as e:
            logger.error(f"Error removing authorized user {auth_id_to_remove}: {e}", exc_info=True)
            await update.message.reply_text(f"Error al eliminar usuario: {e}")
        finally:
            if conn:
                conn.close()

    except ValueError:
        await update.message.reply_text("Por favor, introduce un ID de usuario válido (número).")
    except Exception as e:
        logger.error(f"Unexpected error in remove_authorized_user: {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error inesperado.")


async def list_authorized_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todos los usuarios autorizados."""
    requester_id = update.effective_user.id
    if not is_authorized(requester_id):
        await unauthorized_access_message(update, context)
        return
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, username FROM authorized_users ORDER BY chat_id")
        rows = cursor.fetchall()
        
        if rows:
            message = "*Usuarios autorizados:*\n"
            for chat_id, username in rows:
                message += f"- `{chat_id}` (`{username or 'N/A'}`)\n"
            await update.message.reply_text(message, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("No hay usuarios autorizados registrados.")
    except psycopg2.Error as e:
        logger.error(f"Error listing authorized users: {e}", exc_info=True)
        await update.message.reply_text(f"Error al listar usuarios: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in list_authorized_users: {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error inesperado.")
    finally:
        if conn:
            conn.close()

# Nuevo comando para cambiar roles (solo admins)
async def set_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    requester_id = update.effective_user.id
    if not has_role(requester_id, 'admin'):
        await unauthorized_access_message(update, context)
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso: /set_user_role <ID_de_usuario> <rol> (ej: viewer, editor, admin)")
        return

    try:
        target_id = int(context.args[0])
        new_role = context.args[1].lower()
        
        valid_roles = {'viewer', 'editor', 'admin'}
        if new_role not in valid_roles:
            await update.message.reply_text(f"Rol inválido. Roles permitidos: {', '.join(valid_roles)}")
            return

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE authorized_users SET role = %s WHERE chat_id = %s",
                (new_role, target_id)
            )
            conn.commit()
            if cursor.rowcount > 0:
                load_authorized_chat_ids_from_db() # Refresca roles en memoria
                await update.message.reply_text(f"Rol de usuario `{target_id}` actualizado a `{new_role}`.", parse_mode='MarkdownV2')
                logger.info(f"Admin {requester_id} set role of {target_id} to {new_role}.")
            else:
                await update.message.reply_text(f"Usuario `{target_id}` no encontrado en la lista de autorizados.", parse_mode='MarkdownV2')
        except psycopg2.Error as e:
            logger.error(f"Error setting user role for {target_id}: {e}", exc_info=True)
            await update.message.reply_text(f"Error al establecer el rol: {e}")
        finally:
            if conn:
                conn.close()

    except ValueError:
        await update.message.reply_text("Por favor, introduce un ID de usuario válido (número).")
    except Exception as e:
        logger.error(f"Unexpected error in set_user_role: {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error inesperado.")


# --- NUEVAS FUNCIONES PARA LA AUTENTICACIÓN ---
#def is_authorized(user_id: int) -> bool:
#    """Verifica si el user_id está en la lista de IDs autorizados."""
#    return user_id in AUTHORIZED_CHAT_IDS

current_authorized_chat_ids = set()


# Modifica la función is_authorized para usar la variable global
def is_authorized(user_id: int) -> bool:
    # Para la primera vez que el bot corre y no hay usuarios en la DB,
    # puedes permitir un "super-admin" inicial vía variable de entorno.
    # Después de que el primer admin sea agregado a la DB, puedes quitar esta línea o el SUPER_ADMIN_ID.
    SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0")) # Lee desde .env, por seguridad (0 es un ID inválido)
    if not current_authorized_chat_ids and user_id == SUPER_ADMIN_ID:
        logger.warning(f"Super-admin {user_id} autorizado porque la lista de IDs está vacía.")
        return True
        
    return user_id in current_authorized_chat_ids


async def unauthorized_access_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respuesta para usuarios no autorizados."""
    logger.warning(f"Intento de acceso no autorizado de user_id: {update.effective_user.id}")
    await update.message.reply_text(
        "¡Acceso denegado! No estás autorizado para usar este bot. "
        "Por favor, contacta al administrador si crees que es un error."
    )
    # Considera también ocultar el teclado si lo hubiera
    await update.message.reply_text(
        "Para iniciar un nuevo intento o si eres el administrador, puedes usar /start nuevamente.",
        reply_markup=ReplyKeyboardRemove() # Asegúrate de importar ReplyKeyboardRemove
    )


# --- FUNCIÓN calcular_punto_final ---
def calcular_punto_final(lat, lon, azimut, radio_km):
    """
    Calcula el punto final de una línea dado un punto de origen, azimut y radio.
    Args:
        lat (float): Latitud del punto de origen.
        lon (float): Longitud del punto de origen.
        azimut (float): Azimut en grados (0-360, Norte es 0).
        radio_km (float): Radio de distancia en kilómetros.
    Returns:
        tuple: (new_lat, new_lon) del punto final.
    """
    # Convertir radio a la misma unidad de R_earth si es necesario
    # Aquí, radio_km se usa con R_earth en km (6371.0)
    
    azimut_rad = np.deg2rad(azimut)
    
    # Delta de latitud y longitud usando las fórmulas aproximadas
    delta_lat = (radio_km / 6371.0) * np.cos(azimut_rad) # radio de la Tierra en km
    delta_lon = (radio_km / (6371.0 * np.cos(np.deg2rad(lat)))) * np.sin(azimut_rad)
    
    new_lat = lat + np.rad2deg(delta_lat)
    new_lon = lon + np.rad2deg(delta_lon)
    return new_lat, new_lon

# --- FUNCIÓN para generar color aleatorio (basada en tu guía) ---
def color_aleatorio():
    """Genera un color hexadecimal aleatorio."""
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

# --- Conversation States ---
# Añadimos estados para la selección inicial y la consulta
(SELECCION_INICIAL, FECHA_HORA, NUMERO_A, SENTIDO, NUMERO_B, # Nuevos primeros campos
 DIRECCION, LOCALIDAD, PROVINCIA, LATITUD, LONGITUD,
 RADIO_COBERTURA, AZIMUT, APER_HORIZONTAL, APER_VERTICAL, # Campos de antena reordenados
 CONSULTA_FECHA_INICIO, CONSULTA_FECHA_FIN) = range(16) # El número total de estados no cambia, solo su orden lógico

CONFIRMACION = 17  # Si tienes 17 estados anteriores (0-16), este sería 17



# --- Static Data for Normalization ---
PROVINCIAS_ARGENTINAS = [
    "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes",
    "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza",
    "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis",
    "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego",
    "Tucumán"
]


# --- Database Helper Functions ---
def create_connection():
    """
    Devuelve una conexión activa a PostgreSQL utilizando la DATABASE_URL del entorno.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("La variable de entorno DATABASE_URL no está definida.")
    return get_db_connection(db_url)

def add_record_to_db(record_data):
    """
    Add a new record to the `registros_telecom` table, including all antenna and communication fields.
    `record_data` is a dictionary containing all necessary fields.
    """
    sql = '''
    INSERT INTO registros_telecom(fecha_hora, direccion, localidad, provincia,
                                  latitud, longitud, radiocobertura, azimut,
                                  apervertical, aperhorizontal,
                                  numeroa, sentido, numerob)
    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    '''
    db_url = os.getenv("DATABASE_URL")
    conn = get_db_connection(db_url)

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (
                record_data.get('fecha_hora'),
                record_data.get('direccion'),
                record_data.get('localidad'),
                record_data.get('provincia'),
                record_data.get('latitud'),
                record_data.get('longitud'),
                record_data.get('radiocobertura'),
                record_data.get('azimut'),
                record_data.get('apervertical'),
                record_data.get('aperhorizontal'),
                record_data.get('numeroa'),
                record_data.get('sentido'),
                record_data.get('numerob')
            ))
            new_id = cur.fetchone()[0]
            conn.commit()
            return new_id
    except psycopg2.Error as e:
        logger.error(f"Error inserting record into PostgreSQL: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_records_by_date_range(start_date_str: str, end_date_str: str):
    """
    Recupera registros de la tabla 'registros_telecom' dentro del rango de fechas especificado.
    Las fechas deben estar en formato 'YYYY-MM-DD'.
    """
    db_url = os.getenv("DATABASE_URL")
    conn = get_db_connection(db_url)
    records = []

    if conn:
        try:
            # Aseguramos la hora inicial y final para cubrir todo el rango del día
            start_datetime = start_date_str + " 00:00:00"
            end_datetime = end_date_str + " 23:59:59"

            sql = """
            SELECT fecha_hora, direccion, localidad, provincia, latitud, longitud,
                   radiocobertura, azimut, apervertical, aperhorizontal,
                   numeroa, sentido, numerob
            FROM registros_telecom
            WHERE fecha_hora BETWEEN %s AND %s
            ORDER BY fecha_hora DESC
            """

            cur = conn.cursor()
            cur.execute(sql, (start_datetime, end_datetime))
            records = cur.fetchall()
            logger.info(f"Registros obtenidos entre {start_datetime} y {end_datetime}: {len(records)}")
        except Exception as e:
            logger.error(f"Error al recuperar registros: {e}")
        finally:
            conn.close()
    else:
        logger.error("No se pudo establecer conexión con la base de datos.")

    return records


def generate_map_html(records):
    """
    Generates an HTML map using Folium with markers for each record,
    displaying both antenna and communication details.
    """
    if not records:
        logger.info("No records to generate map.")
        return None

    m = folium.Map(location=[-34.6037, -58.3816], zoom_start=6)

    for record in records:
        try:
            # Desempaquetar los datos del registro (¡ATENCIÓN AL ORDEN Y NÚMERO!)
            fecha_hora, direccion, localidad, provincia, latitud, longitud, \
                radio_cobertura, azimut, aper_vertical, aper_horizontal, \
                numeroa, sentido, numerob = record

            # Formatear campos opcionales para visualización
            radio_display = f"{radio_cobertura} m" if radio_cobertura is not None else "N/A"
            azimut_display = f"{azimut}°" if azimut is not None else "N/A"
            aper_v_display = f"{aper_vertical}°" if aper_vertical is not None else "N/A"
            aper_h_display = f"{aper_horizontal}°" if aper_horizontal is not None else "N/A"

            # Crear el popup para cada marcador con todos los datos
            popup_html = f"""
            <b>Fecha y Hora:</b> {fecha_hora}<br>
            <b>Dirección:</b> {direccion}, {localidad}, {provincia}<br>
            <hr>
            <b>Radio Cobertura:</b> {radio_display}<br>
            <b>Azimut:</b> {azimut_display}<br>
            <b>Apertura Vertical:</b> {aper_v_display}<br>
            <b>Apertura Horizontal:</b> {aper_h_display}<br>
            <hr>
            <b>Número Origen (A):</b> {numeroa}<br>
            <b>Sentido:</b> {sentido}<br>
            <b>Número Destino (B):</b> {numerob}
            """
            
            folium.Marker(
                location=[latitud, longitud],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Registro en: {localidad}, {provincia}" # Tooltip más general
            ).add_to(m)

            # Dibujar el sector de cobertura si tenemos los datos necesarios
            if all(x is not None for x in [latitud, longitud, radio_cobertura, azimut, aper_horizontal]):
                radio_km = radio_cobertura / 1000.0  # Convertir metros a kilómetros
                
                # Crear el círculo de cobertura (sin relleno)
                folium.Circle(
                    location=[latitud, longitud],
                    radius=radio_cobertura,
                    color='blue',
                    fill=False,
                    tooltip=f"Radio: {radio_cobertura} m"
                ).add_to(m)

                # Calcular los puntos del sector
                sector_points = [[latitud, longitud]]
                num_arc_points = 20
                start_angle = azimut - (aper_horizontal / 2)
                end_angle = azimut + (aper_horizontal / 2)

                # Convertir ángulos a radianes y ajustar para el sistema de coordenadas
                start_rad = np.deg2rad(90 - start_angle)
                end_rad = np.deg2rad(90 - end_angle)
                if end_rad < start_rad:
                    end_rad += 2 * np.pi

                # Generar puntos del arco
                for i in range(num_arc_points + 1):
                    interp_rad = start_rad + (end_rad - start_rad) * i / num_arc_points
                    delta_lat = (radio_km / 6371.0) * np.sin(interp_rad)
                    delta_lon = (radio_km / (6371.0 * np.cos(np.deg2rad(latitud)))) * np.cos(interp_rad)
                    arc_lat = latitud + np.rad2deg(delta_lat)
                    arc_lon = longitud + np.rad2deg(delta_lon)
                    sector_points.append([arc_lat, arc_lon])

                # Dibujar el sector con color aleatorio
                color = color_aleatorio()
                folium.Polygon(
                    locations=sector_points,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.3,
                    tooltip=f"Azimut: {azimut}°, Apertura H: {aper_horizontal}°"
                ).add_to(m)

        except Exception as e:
            logger.error(f"Error adding marker for record {record}: {e}")
            continue

    map_html_stream = BytesIO()
    m.save(map_html_stream, close_file=False)
    map_html_stream.seek(0)
    logger.info("Mapa HTML generado en memoria.")
    return map_html_stream


# --- Bot Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Envía un mensaje de bienvenida y las opciones iniciales."""
    user = update.effective_user
    user_id = user.id

    if not has_role(user_id, 'viewer'): # Cualquier rol por encima de 'unauthorized'
        await unauthorized_access_message(update, context)
        return ConversationHandler.END

    logger.info(f"User {user_id} ({user.full_name}) started the bot.")

    reply_keyboard = [["Cargar nuevo registro", "Consultar registros en el mapa"]]
    
    # --- AÑADE TU FIRMA AQUÍ ---
    #signature = "\n\n_Desarrollado por [FrijolitoRaza](https://github.com/FrijolitoRaza) con ❤️_"
    
    await update.message.reply_html(
        f"¡Hola, {user.mention_html()}! Soy tu bot de gestión de registros de telecomunicaciones."
        "\n¿Qué te gustaría hacer hoy?",
        #f"{signature}", # Agrega la firma al mensaje
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    # --- FIN DE LA FIRMA ---
    
    return SELECCION_INICIAL

async def handle_initial_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la elección inicial del usuario."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END

    choice = update.message.text
    context.user_data['initial_choice'] = choice # Guarda la elección por si la necesitas más tarde

    if choice == "Cargar nuevo registro":
        if not has_role(user_id, 'editor'): # Protege la opción de carga
            await unauthorized_access_message(update, context)
            return ConversationHandler.END

        # Llama a start_new_record (que ya tiene la verificación de autorización)
        return await start_new_record(update, context) # Pasa el control a start_new_record
    elif choice == "Consultar registros en el mapa":
        if not has_role(user_id, 'viewer'): # Protege la opción de consulta
            await unauthorized_access_message(update, context)
            return ConversationHandler.END
        await update.message.reply_text(
            "Entendido. Por favor, ingresa la **fecha de inicio** para la consulta (YYYY-MM-DD), o envía `/saltar` para ver todos los registros.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return CONSULTA_FECHA_INICIO # Pasa al estado de pedir fecha de inicio
    else:
        # Esto debería ser manejado por un fallback, pero por seguridad
        await update.message.reply_text("Opción no reconocida. Por favor, selecciona una de las opciones.")
        return SELECCION_INICIAL

async def nuevoregistro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to add a new record."""
    logger.info(f"Usuario {update.effective_user.first_name} ha iniciado un nuevo registro.")
    context.user_data['current_record'] = {} # Initialize record storage
    await update.message.reply_text(
        "¡Vamos a añadir un nuevo registro! Si deseas cancelar en cualquier momento, usa /cancelar.\n\n"
        "Primero, por favor, introduce la **Fecha y Hora del evento** (ej: `02/06/2025 14:30`).",
        reply_markup=ReplyKeyboardRemove() # Remove keyboard after selection
    )
    return FECHA_HORA

async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Shows a help message with all available commands and their descriptions.
    """
    logger.info(f"Comando /ayuda recibido de {update.effective_user.first_name}.")

    help_message = (
        "¡Claro, aquí estoy para ayudarte! ✨\n\n"
        "Estos son los comandos que puedes usar:\n\n"
        "  * **/start**: Inicia el bot y te permite elegir entre cargar o consultar registros en el mapa.\n\n"
        "  * **/nuevoregistro**: Inicia el proceso paso a paso para añadir una nueva antena con "
        "todos sus datos (dirección, coordenadas, cobertura, etc.).\n\n"
        "  * **/cancelar**: Detiene cualquier proceso (registro o consulta) que estés realizando en ese momento. "
        "¡Puedes usarlo en cualquier punto!\n\n"
        "  * **/resumen**: Muestra estadísticas rápidas del total de antenas registradas en el mapa.\n\n"
        "  * **/ayuda**: Muestra esta lista de comandos y su breve descripción.\n\n"
        "¡Espero que esto te sea útil! Si tienes alguna otra pregunta, no dudes en consultarme."
    )
    await update.message.reply_text(help_message, parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.effective_user
    logger.info(f"Usuario {user.first_name} canceló la conversación.")
    # Clear user data for the current record or query
    if 'current_record' in context.user_data:
        del context.user_data['current_record']
    if 'query_dates' in context.user_data:
        del context.user_data['query_dates']
    await update.message.reply_text(
        "Operación cancelada. Puedes usar /start para comenzar de nuevo.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def resumen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra estadísticas rápidas sobre las antenas registradas."""
    db_url = os.getenv("DATABASE_URL")
    conn = get_db_connection(db_url)
    total_records = 0
    records_24h = 0
    top_province_str = "N/A"

    if conn:
        try:
            cur = conn.cursor()

            # Total de registros
            cur.execute("SELECT COUNT(*) FROM registros_telecom")
            total_records = cur.fetchone()[0]

            # Registros en las últimas 24 horas
            now = datetime.datetime.now(datetime.timezone.utc)
            time_24h_ago = now - datetime.timedelta(hours=24)

            cur.execute(
                "SELECT COUNT(*) FROM registros_telecom WHERE fecha_hora >= %s",
                (time_24h_ago,)
            )
            records_24h = cur.fetchone()[0]

            # Provincia con más registros
            cur.execute("""
                SELECT provincia, COUNT(*) 
                FROM registros_telecom 
                GROUP BY provincia 
                ORDER BY COUNT(*) DESC 
                LIMIT 1
            """)
            top_province_data = cur.fetchone()

            if top_province_data and top_province_data[0]:
                top_province_str = f"{top_province_data[0]} ({top_province_data[1]} antenas)"

        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            await update.message.reply_text(
                "Hubo un error al obtener el resumen. Intenta de nuevo más tarde."
            )
            return
        finally:
            conn.close()
    else:
        await update.message.reply_text("No se pudo conectar a la base de datos.")
        return

    summary_message = (
        "📡 *Resumen rápido del Mapa de Comunicaciones*\n\n"
        f"• **Antenas registradas en total:** `{total_records}`\n"
        f"• **Nuevas antenas en las últimas 24hs:** `{records_24h}`\n"
        f"• **Provincia con más registros:** `{top_province_str}`\n\n"
        "¡Gracias por ayudarnos a crecer! 🌐 Continúa registrando antenas con /nuevoregistro"
    )
    await update.message.reply_text(summary_message, parse_mode='Markdown')

# --- Conversation Handler Functions (Data Input and Normalization) ---

async def start_new_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia el proceso de carga de un nuevo registro de telecomunicaciones,
    después de verificar la autorización.
    """
    user_id = update.effective_user.id
    if not has_role(user_id, 'editor'): # Solo editores y admins pueden cargar
        await unauthorized_access_message(update, context)
        return ConversationHandler.END
        
    # Inicializa el diccionario para almacenar los datos del registro actual
    context.user_data['current_record'] = {}

    await update.message.reply_text(
        "Iniciando la carga de un nuevo registro. Por favor, ingresa la fecha y hora de la comunicación (DD/MM/YYYY HH:MM):",
        reply_markup=ReplyKeyboardRemove()
    )
    return FECHA_HORA
 # Esto le dice al ConversationHandler que el siguiente estado es FECHA_HORA


async def get_fecha_hora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and validates the date and time input for the communication."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados
    user_input = update.message.text.strip()
    try:
        argentina_tz = datetime.timezone(datetime.timedelta(hours=-3))
        current_time_for_validation = datetime.datetime.now(datetime.timezone.utc).astimezone(argentina_tz)

        fecha_hora_obj = datetime.datetime.strptime(user_input, '%d/%m/%Y %H:%M')
        fecha_hora_obj = fecha_hora_obj.replace(tzinfo=argentina_tz)

        if fecha_hora_obj > current_time_for_validation + datetime.timedelta(days=7):
            await update.message.reply_text(
                "La fecha y hora no pueden ser más de 7 días en el futuro. "
                "Por favor, ingresa una fecha y hora válidas (ej: `02/06/2025 14:30`)."
            )
            return FECHA_HORA

        context.user_data['current_record']['fecha_hora'] = fecha_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Fecha y hora de comunicación: {fecha_hora_obj}")

        await update.message.reply_text("¡Fecha y hora registradas! Ahora, por favor, introduce el **NÚMERO DE TELÉFONO EMISOR (A)**:")
        return NUMERO_A

    except ValueError:
        await update.message.reply_text(
            "Formato de fecha y hora inválido. Por favor, usa `DD/MM/AAAA HH:MM` (ej: `02/06/2025 14:30`)."
        )
        return FECHA_HORA



async def get_numeroA(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets and validates the sender phone number."""
    numero_a = update.message.text.strip()
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados
    # Una validación más robusta podría incluir expresiones regulares para formatos de teléfono
    if not numero_a.isdigit() or len(numero_a) < 7:
        await update.message.reply_text(
            "Número de teléfono inválido. Por favor, introduce un número válido (solo dígitos y al menos 7)."
        )
        return NUMERO_A
    
    context.user_data['current_record']['numeroa'] = numero_a
    logger.info(f"Número A: {numero_a}")
    
    reply_keyboard = [["Entrante", "Saliente"]]
    # ¡CAMBIO AQUÍ! Después de NUMERO_A, pedimos SENTIDO
    await update.message.reply_text(
        "¡Número de emisor guardado! Ahora, indica el **SENTIDO** de la comunicación (Entrante/Saliente):",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SENTIDO


async def get_sentido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets and validates the communication direction."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados
    sentido = update.message.text.strip().capitalize()
    if sentido not in ["Entrante", "Saliente"]:
        await update.message.reply_text(
            "Sentido inválido. Por favor, elige 'Entrante' o 'Saliente'."
        )
        return SENTIDO
    
    context.user_data['current_record']['sentido'] = sentido
    logger.info(f"Sentido: {sentido}")
    
    # ¡CAMBIO AQUÍ! Después de SENTIDO, pedimos NUMERO_B
    await update.message.reply_text(
        "¡Sentido guardado! Finalmente, introduce el **NÚMERO DE TELÉFONO RECEPTOR (B)**:",
        reply_markup=ReplyKeyboardRemove()
    )
    return NUMERO_B


async def get_numeroB(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets and validates the receiver phone number and proceeds to location details."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    numero_b = update.message.text.strip()
    # Una validación más robusta podría incluir expresiones regulares para formatos de teléfono
    if not numero_b.isdigit() or len(numero_b) < 7:
        await update.message.reply_text(
            "Número de teléfono inválido. Por favor, introduce un número válido (solo dígitos y al menos 7)."
        )
        return NUMERO_B
    
    context.user_data['current_record']['numerob'] = numero_b
    logger.info(f"Número B: {numero_b}")
    
    # ¡CAMBIO AQUÍ! Después de NUMERO_B, pedimos DIRECCION
    await update.message.reply_text(
        "¡Datos de comunicación registrados! Ahora, introduce la **DIRECCIÓN** donde ocurrió la comunicación (calle y número, intersección, etc.):"
    )
    return DIRECCION


# Las siguientes funciones (get_direccion, get_localidad, get_provincia,
# get_latitud, get_longitud) no necesitan cambios en su lógica interna
# pero asegúrate de que el 'return' apunte al estado siguiente según tu nuevo flujo.

async def get_direccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and normalizes the address input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    direccion = update.message.text.strip()
    direccion_normalizada = ' '.join(word.capitalize() for word in direccion.split())
    
    context.user_data['current_record']['direccion'] = direccion_normalizada
    logger.info(f"Dirección: {direccion_normalizada}")
    await update.message.reply_text(
        f"¡Dirección guardada como: `{direccion_normalizada}`!\n"
        "Ahora, introduce la **LOCALIDAD**:",
        parse_mode='Markdown'
    )
    return LOCALIDAD # Sin cambios, sigue a LOCALIDAD

async def get_localidad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and normalizes the locality input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    localidad = update.message.text.strip()
    localidad_normalizada = ' '.join(word.capitalize() for word in localidad.split())
    
    context.user_data['current_record']['localidad'] = localidad_normalizada
    logger.info(f"Localidad: {localidad_normalizada}")
    await update.message.reply_text(
        f"¡Localidad guardada como: `{localidad_normalizada}`!\n"
        "Ahora la **PROVINCIA**:",
        parse_mode='Markdown'
    )
    return PROVINCIA # Sin cambios, sigue a PROVINCIA

async def get_provincia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and normalizes the province input, validating against a predefined list."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    provincia = update.message.text.strip()
    provincia_normalizada = ' '.join(word.capitalize() for word in provincia.split())

    if provincia_normalizada not in PROVINCIAS_ARGENTINAS:
        reply_keyboard = [[p] for p in PROVINCIAS_ARGENTINAS[0:4]] # Show first 4 as suggestions
        await update.message.reply_text(
            f"'{provincia_normalizada}' no parece ser una provincia válida de Argentina. "
            "Por favor, selecciona una de la lista o escribe correctamente (ej: `Buenos Aires`, `Córdoba`).",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return PROVINCIA
    else:
        context.user_data['current_record']['provincia'] = provincia_normalizada
        logger.info(f"Provincia: {provincia_normalizada}")
        await update.message.reply_text(
            f"¡Provincia guardada como: `{provincia_normalizada}`!\n"
            "Introduce la **LATITUD** (ej: `-34.6037`).",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return LATITUD # Sin cambios, sigue a LATITUD

async def get_latitud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and validates the latitude input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    try:
        lat = float(update.message.text.strip())
        if not (-55.0 <= lat <= -21.0): # Approximate range for Argentina
            await update.message.reply_text(
                "La latitud ingresada está fuera del rango geográfico de Argentina. "
                "Por favor, introduce un valor entre -55.0 y -21.0 (ej: `-34.6037`)."
            )
            return LATITUD
        context.user_data['current_record']['latitud'] = lat
        logger.info(f"Latitud: {lat}")

        # ¡CAMBIO AQUÍ! Después de LATITUD, pedimos LONGITUD
        await update.message.reply_text("Introduce la **LONGITUD** (ej: `-58.3816`):")
        return LONGITUD # Sin cambios, sigue a LONGITUD

    # ADD THIS 'except' BLOCK for get_latitud
    except ValueError:
        await update.message.reply_text("Latitud inválida. Por favor, introduce un número decimal (ej: `-34.6037`).")
        return LATITUD


async def get_longitud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and validates the longitude input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    try:
        lon = float(update.message.text.strip())
        if not (-74.0 <= lon <= -53.0): # Approximate range for Argentina
            await update.message.reply_text(
                "La longitud ingresada está fuera del rango geográfico de Argentina. "
                "Por favor, introduce un valor entre -74.0 y -53.0 (ej: `-58.3816`)."
            )
            return LONGITUD
        context.user_data['current_record']['longitud'] = lon
        logger.info(f"Longitud: {lon}")
        
        # ¡CAMBIO AQUÍ! Después de LONGITUD, pedimos RADIO_COBERTURA
        await update.message.reply_text("¡Ubicación registrada! Ahora, introduce el **RADIO DE COBERTURA** (en metros, ej: `1500`):")
        return RADIO_COBERTURA

    except ValueError:
        await update.message.reply_text("Longitud inválida. Por favor, introduce un número decimal (ej: `-58.3816`).")
        return LONGITUD


async def get_radio_cobertura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and validates the coverage radius input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    try:
        radio = float(update.message.text.strip())
        if not (radio > 0):
            await update.message.reply_text("El radio debe ser un número positivo. Inténtalo de nuevo:")
            return RADIO_COBERTURA
        context.user_data['current_record']['radiocobertura'] = radio
        logger.info(f"Radio Cobertura: {radio}")
        
        # ¡CAMBIO AQUÍ! Después de RADIO_COBERTURA, pedimos AZIMUT
        await update.message.reply_text("Introduce el **AZIMUT** (dirección de la antena en grados, `0-360`):")
        return AZIMUT

    except ValueError:
        await update.message.reply_text("Radio de cobertura inválido. Por favor, introduce un número (ej: `1500`).")
        return RADIO_COBERTURA


async def get_azimut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and validates the azimuth input."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    text = update.message.text.strip()
    try:
        azimut = float(text)
        if not (0 <= azimut <= 360):
            await update.message.reply_text("Azimut inválido. Debe estar entre 0 y 360 grados. Inténtalo de nuevo:")
            return AZIMUT
        context.user_data['current_record']['Azimut'] = azimut
        logger.info(f"Azimut: {azimut}")
        
        # ¡CAMBIO AQUÍ! Después de AZIMUT, pedimos APER_HORIZONTAL
        await update.message.reply_text(
            "¡Azimut registrado! Ahora, introduce la **APERTURA HORIZONTAL** del haz (en grados).\n"
            "*(Puedes omitirla presionando Enter si no deseas proporcionarla.)*"
        )
        return APER_HORIZONTAL # CAMBIO: Siguiente estado es APER_HORIZONTAL

    except ValueError:
        await update.message.reply_text("Azimut inválido. Por favor, introduce un número (ej: `90`).")
        return AZIMUT


async def get_aper_horizontal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes and validates the horizontal aperture input, then asks for APER_VERTICAL.
    Now optional.
    """
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    user_input = update.message.text.strip()

    if not user_input:
        context.user_data['current_record']['aperhorizontal'] = None
        logger.info("Apertura Horizontal: Opcional, no proporcionada.")
    else:
        try:
            aper_h = float(user_input)
            if not (aper_h > 0 and aper_h <= 360):
                await update.message.reply_text(
                    "La apertura horizontal debe ser un número positivo y no mayor a 360 grados. "
                    "Por favor, reintenta o presiona Enter para omitir:"
                )
                return APER_HORIZONTAL
            context.user_data['current_record']['aperhorizontal'] = aper_h
            logger.info(f"Apertura Horizontal: {aper_h}")
        except ValueError:
            await update.message.reply_text(
                "Apertura horizontal inválida. Introduce un número (ej: `60`) o presiona Enter para omitir."
            )
            return APER_HORIZONTAL

    # ¡CAMBIO AQUÍ! Después de APER_HORIZONTAL, pedimos APER_VERTICAL
    await update.message.reply_text(
        "¡Apertura horizontal guardada! Ahora introduce la **APERTURA VERTICAL** del haz (en grados).\n"
        "*(Puedes omitirla también presionando Enter si no deseas proporcionarla.)*"
    )
    return APER_VERTICAL # CAMBIO: Siguiente estado es APER_VERTICAL


async def get_aper_vertical(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes and validates the vertical aperture input, then summarizes for confirmation.
    Now optional.
    """
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    user_input = update.message.text.strip()

    if not user_input:
        context.user_data['current_record']['apervertical'] = None
        logger.info("Apertura Vertical: Opcional, no proporcionada.")
    else:
        try:
            aper_v = float(user_input)
            if not (aper_v > 0 and aper_v <= 180):
                await update.message.reply_text(
                    "La apertura vertical debe ser un número positivo y no mayor a 180 grados. "
                    "Por favor, reintenta o presiona Enter para omitir:"
                )
                return APER_VERTICAL
            context.user_data['current_record']['apervertical'] = aper_v
            logger.info(f"Apertura Vertical: {aper_v}")
        except ValueError:
            await update.message.reply_text(
                "Apertura vertical inválida. Introduce un número (ej: `15`) o presiona Enter para omitir."
            )
            return APER_VERTICAL

    # ¡CAMBIO AQUÍ! Después de APER_VERTICAL, procedemos a la confirmación
    return await confirm_and_save_record_display_message(update, context)

def escape_markdown_v2(text: str) -> str:
    """Helper function to escape special characters in MarkdownV2 to prevent parsing errors."""
    if not isinstance(text, str):
        text = str(text) # Ensure it's a string, then process

    # These characters must be escaped in MarkdownV2
    # Reference: https://core.telegram.org/bots/api#markdownv2-style
    # List of characters to escape: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    # The order matters for some: [ should be escaped before ]
    # The regex needs to escape the characters correctly before passing to re.sub
    escape_chars_pattern = r'([_*[\]()~`>#+\-|=!.])' # Added - for good measure, and removed { } for now (less common)
    return re.sub(escape_chars_pattern, r'\\\1', text)



# La función confirm_and_save_record_display_message y confirm_and_save_record
# ya deberían estar bien porque acceden a los datos por clave ('fecha_hora', 'numeroA', etc.)
# y la visualización de todos los campos ya está implementada.
# Solo asegúrate de que el orden de visualización en confirm_and_save_record_display_message
# sea el que prefieras, pero la recolección de datos ya está alineada.

# Renombrada para claridad: esta función solo construye el mensaje y muestra el teclado
# La lógica de guardar estará en confirm_and_save_record, que es llamada por esta
async def confirm_and_save_record_display_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Constructs and displays the confirmation message with all collected data, escaping Markdown characters."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END # Termina la conversación para usuarios no autorizados

    record = context.user_data['current_record']
    
    # Pre-process display values, ensuring they are strings before escaping
    # And handle "N/A" cases directly
    fecha_hora_display = escape_markdown_v2(record.get('fecha_hora', 'N/A'))
    direccion_display = escape_markdown_v2(record.get('direccion', 'N/A'))
    localidad_display = escape_markdown_v2(record.get('localidad', 'N/A'))
    provincia_display = escape_markdown_v2(record.get('provincia', 'N/A'))
    latitud_display = escape_markdown_v2(f"{record.get('latitud', 'N/A')}")
    longitud_display = escape_markdown_v2(f"{record.get('longitud', 'N/A')}")

    # For numerical fields, format them first, then escape the entire formatted string
    radio_cobertura_val = record.get('radiocobertura')
    radio_display = escape_markdown_v2(f"{radio_cobertura_val} m") if radio_cobertura_val is not None else escape_markdown_v2("N/A metros")

    azimut_val = record.get('Azimut')
    azimut_display = escape_markdown_v2(f"{azimut_val}°") if azimut_val is not None else escape_markdown_v2("N/A grados")

    aper_vertical_val = record.get('apervertical')
    aper_v_display = escape_markdown_v2(f"{aper_vertical_val}°") if aper_vertical_val is not None else escape_markdown_v2("N/A grados")

    aper_horizontal_val = record.get('aperhorizontal')
    aper_h_display = escape_markdown_v2(f"{aper_horizontal_val}°") if aper_horizontal_val is not None else escape_markdown_v2("N/A grados")

    numero_a_display = escape_markdown_v2(record.get('numeroa', 'N/A'))
    sentido_display = escape_markdown_v2(record.get('sentido', 'N/A'))
    numero_b_display = escape_markdown_v2(record.get('numerob', 'N/A'))


    confirmation_message = (
        "\\*\\*Por favor, confirma los datos del registro:\\*\\*\n" # Escapamos los asteriscos literales del título
        f"\\* **Fecha y Hora:** `{fecha_hora_display}`\n"
        f"\\* **Número Emisor \\(A\\):** `{numero_a_display}`\n"
        f"\\* **Sentido:** `{sentido_display}`\n"
        f"\\* **Número Receptor \\(B\\):** `{numero_b_display}`\n"
        f"\\* **Dirección:** `{direccion_display}`\n"
        f"\\* **Localidad:** `{localidad_display}`\n"
        f"\\* **Provincia:** `{provincia_display}`\n"
        f"\\* **Latitud:** `{latitud_display}`\n"
        f"\\* **Longitud:** `{longitud_display}`\n"
        f"\\* **Radio Cobertura:** `{radio_display}`\n"
        f"\\* **Azimut:** `{azimut_display}`\n"
        f"\\* **Apertura Vertical:** `{aper_v_display}`\n"
        f"\\* **Apertura Horizontal:** `{aper_h_display}`\n\n"
        "\\*\\*¿Son estos datos correctos y deseas guardarlos\\? \\(Sí/No\\)\\*\\*" # Escapamos el signo de interrogación y los asteriscos del final
    )
    
    reply_keyboard = [['Sí', 'No']]
    await update.message.reply_text(
        confirmation_message,
        parse_mode='MarkdownV2',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CONFIRMACION


async def handle_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END

    record = context.user_data.get('current_record')

    if record:
        try:
            # --- CAMBIO AQUÍ: ELIMINA 'await' ---
            save_success = save_record_to_db(record) # ¡QUITADO el 'await'!
            # --- FIN DEL CAMBIO ---

            if save_success:
                await update.message.reply_text("¡Datos guardados exitosamente!",
                                                reply_markup=ReplyKeyboardRemove())
                logger.info(f"Record for user {user_id} saved to DB.")
                context.user_data.pop('current_record', None) # Limpia los datos temporales

                reply_keyboard = [["Cargar nuevo registro", "Consultar registros en el mapa"]]
                await update.message.reply_text(
                    "¿Qué te gustaría hacer hoy?",
                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
                )
                return SELECCION_INICIAL
            else:
                await update.message.reply_text(
                    "Ocurrió un error al guardar los datos. Por favor, inténtalo de nuevo más tarde.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"Failed to save record for user {user_id}.")
                return ConversationHandler.END

        except Exception as e:
            await update.message.reply_text(f"Ocurrió un error inesperado al guardar los datos: {e}",
                                            reply_markup=ReplyKeyboardRemove())
            logger.error(f"Unexpected error saving data for user {user_id}: {e}", exc_info=True)
            return ConversationHandler.END
    else:
        await update.message.reply_text("No hay datos para guardar. Inicia un nuevo registro con /cargar_registro.",
                                        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


# Corrected handle_confirm_no
async def handle_confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END

    context.user_data.pop('current_record', None) # Clear temporary data
    await update.message.reply_text("¡Registro cancelado! Los datos no han sido guardados.",
                                    reply_markup=ReplyKeyboardRemove())
    
    # Return to main menu
    reply_keyboard = [["Cargar nuevo registro", "Consultar registros en el mapa"]]
    await update.message.reply_text(
        "¿Qué te gustaría hacer hoy?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return SELECCION_INICIAL # <-- Transition to main menu

# Your invalid_confirmation_input is already correct:
async def invalid_confirmation_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja respuestas inválidas en la fase de confirmación."""
    await update.message.reply_text("Por favor, responde 'Sí' para guardar o 'No' para cancelar.",
                                    reply_markup=ReplyKeyboardMarkup([['Sí', 'No']], one_time_keyboard=True, resize_keyboard=True))
    return CONFIRMACION


# La función confirm_and_save_record (la que realmente guarda) no necesita cambios en su lógica interna
# aparte de que los datos en context.user_data ya no tienen los campos de antena.
# Asegúrate de que esta función siga siendo la misma que la última versión que te proporcioné.

# --- Lógica de Consulta ---
async def get_consulta_fecha_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captura la fecha de inicio para la consulta del mapa."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END
    
    fecha_inicio_str = update.message.text

    if fecha_inicio_str.lower() == "/saltar":
        context.user_data['consulta_fecha_desde'] = None
        logger.info(f"Usuario {user_id} saltó la fecha de inicio.")
    else:
        try:
            # Validación simple del formato de fecha
            datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            context.user_data['consulta_fecha_desde'] = fecha_inicio_str
            logger.info(f"Fecha de inicio de consulta registrada: {fecha_inicio_str}")
        except ValueError:
            await update.message.reply_text(
                "Formato de fecha incorrecto. Por favor, usa YYYY-MM-DD, o envía `/saltar`.",
                parse_mode='Markdown'
            )
            return CONSULTA_FECHA_INICIO # Quédate en este estado si es inválido

    await update.message.reply_text(
        "Ahora, ingresa la **fecha de fin** (YYYY-MM-DD), o envía `/saltar` para ver hasta la fecha actual.",
        parse_mode='Markdown'
    )
    return CONSULTA_FECHA_FIN


async def get_consulta_fecha_fin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captura la fecha de fin para la consulta del mapa y genera el mapa."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await unauthorized_access_message(update, context)
        return ConversationHandler.END

    fecha_fin_str = update.message.text

    if fecha_fin_str.lower() == "/saltar":
        context.user_data['consulta_fecha_hasta'] = None
        logger.info(f"Usuario {user_id} saltó la fecha de fin.")
    else:
        try:
            datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')
            context.user_data['consulta_fecha_hasta'] = fecha_fin_str
            logger.info(f"Fecha de fin de consulta registrada: {fecha_fin_str}")
        except ValueError:
            await update.message.reply_text(
                "Formato de fecha incorrecto. Por favor, usa YYYY-MM-DD, o envía `/saltar`.",
                parse_mode='Markdown'
            )
            return CONSULTA_FECHA_FIN # Quédate en este estado si es inválido
            
    # Llama a la función que generará y enviará el mapa
    await generate_and_send_map(update, context)

    # Limpia los datos de la consulta de fechas
    context.user_data.pop('consulta_fecha_desde', None)
    context.user_data.pop('consulta_fecha_hasta', None)

    await update.message.reply_text("¡Operación completada! Puedes usar /start para volver al menú principal.")
    return ConversationHandler.END # Termina la conversación

# Función auxiliar para guardar en la DB
# Ejemplo de cómo debería ser tu save_record_to_db (si ya la tienes)
def save_record_to_db(record: dict) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO registros_telecom (
            fecha_hora, numeroa, sentido, numerob,
            direccion, localidad, provincia, latitud, longitud,
            radiocobertura, Azimut, aperhorizontal, apervertical
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            record.get('fecha_hora'),
            record.get('numeroa'),
            record.get('sentido'),
            record.get('numerob'),
            record.get('direccion'),
            record.get('localidad'),
            record.get('provincia'),
            record.get('latitud'),
            record.get('longitud'),
            record.get('radiocobertura'),
            record.get('Azimut'),
            record.get('aperhorizontal'),
            record.get('apervertical')
        )
        cursor.execute(sql, values) # Sin 'await' aquí
        conn.commit() # Sin 'await' aquí

        logger.info("Record saved to DB.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error during save: {e}")
        return False
    except Exception as e:
        logger.error(f"General error in save_record_to_db: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close() # Sin 'await' aquí


async def generate_and_send_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Generando el mapa, por favor espera un momento...")

    fecha_desde = context.user_data.get('consulta_fecha_desde')
    fecha_hasta = context.user_data.get('consulta_fecha_hasta')

    map_file_path = None
    conn = None
    try:
        conn = get_db_connection()  # Debe devolver conexión PostgreSQL
        query = "SELECT * FROM registros_telecom"
        params = []

        if fecha_desde and fecha_hasta:
            query += " WHERE DATE(fecha_hora) BETWEEN %s AND %s"
            params.extend([fecha_desde, fecha_hasta])
        elif fecha_desde:
            query += " WHERE DATE(fecha_hora) >= %s"
            params.append(fecha_desde)
        elif fecha_hasta:
            query += " WHERE DATE(fecha_hora) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY fecha_hora DESC"

        records_df = pd.read_sql_query(query, conn, params=params)
        records_df.columns = [col.lower() for col in records_df.columns]


        if not records_df.empty:
            numeric_cols = ['latitud', 'longitud', 'radiocobertura', 'azimut', 'aperhorizontal', 'apervertical']
            for col in numeric_cols:
                records_df[col] = pd.to_numeric(records_df[col], errors='coerce')
            records_df.dropna(subset=['latitud', 'longitud'], inplace=True)

            if records_df.empty:
                await update.message.reply_text("No hay registros válidos con coordenadas para mostrar en el rango de fechas seleccionado.")
                return

            map_center = [records_df['latitud'].mean(), records_df['longitud'].mean()]
            m = folium.Map(location=map_center, zoom_start=12)

            for index, row in records_df.iterrows():
                lat, lon = row['latitud'], row['longitud']
                radio, azimut = row['radiocobertura'], row['azimut']
                apertura_h, apertura_v = row['aperhorizontal'], row['apervertical']
                radio_km = radio / 1000.0 if radio is not None else 0

                popup_html = f"""<b>ID Registro:</b> {row['id']}<br><b>Fecha y Hora:</b> {row['fecha_hora']}<br>
                <b>Número Emisor (A):</b> {row['numeroa']}<br><b>Sentido:</b> {row['sentido']}<br>
                <b>Número Receptor (B):</b> {row['numerob']}<br><b>Dirección:</b> {row['direccion']}<br>
                <b>Localidad:</b> {row['localidad']}<br><b>Provincia:</b> {row['provincia']}<br><hr>
                <b>Latitud:</b> {lat}<br><b>Longitud:</b> {lon}<br><b>Radio Cobertura:</b> {radio} m<br>
                <b>Azimut:</b> {azimut}°<br><b>Apertura Horizontal:</b> {apertura_h}°<br><b>Apertura Vertical:</b> {apertura_v}°"""

                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)

                if lat and lon and radio and azimut and apertura_h and radio_km > 0:
                    folium.Circle(
                        location=[lat, lon],
                        radius=radio,
                        color='blue',
                        fill=True,
                        fill_opacity=0.02,
                        tooltip=f"Radio: {radio} m"
                    ).add_to(m)

                    sector_points = [[lat, lon]]
                    num_arc_points = 20
                    start_angle = azimut - (apertura_h / 2)
                    end_angle = azimut + (apertura_h / 2)

                    start_rad = np.deg2rad(90 - start_angle)
                    end_rad = np.deg2rad(90 - end_angle)
                    if end_rad < start_rad:
                        end_rad += 2 * np.pi

                    for i in range(num_arc_points + 1):
                        interp_rad = start_rad + (end_rad - start_rad) * i / num_arc_points
                        delta_lat = (radio_km / 6371.0) * np.sin(interp_rad)
                        delta_lon = (radio_km / (6371.0 * np.cos(np.deg2rad(lat)))) * np.cos(interp_rad)
                        arc_lat = lat + np.rad2deg(delta_lat)
                        arc_lon = lon + np.rad2deg(delta_lon)
                        sector_points.append([arc_lat, arc_lon])

                    folium.Polygon(
                        locations=sector_points,
                        color=color_aleatorio(),
                        fill=True,
                        fill_opacity=0.3,
                        tooltip=f"Azimut: {azimut}°, Apertura H: {apertura_h}°"
                    ).add_to(m)

            map_filename = f"mapa_registros_{uuid.uuid4().hex}.html"
            map_file_path = os.path.join("temp_maps", map_filename)
            os.makedirs("temp_maps", exist_ok=True)
            m.save(map_file_path)

            with open(map_file_path, 'rb') as map_file:
                await update.message.reply_document(
                    document=map_file,
                    filename="registros_telecom_mapa.html",
                    caption="Aquí está el mapa de tus registros. Abre el archivo en tu navegador para visualizarlo."
                )

        else:
            await update.message.reply_text("No se encontraron registros en el rango de fechas especificado.")

    except Exception as e:
        logger.error(f"Error al generar o enviar el mapa: {e}", exc_info=True)
        await update.message.reply_text(f"Ocurrió un error al generar el mapa: {e}")
    finally:
        if conn:
            conn.close()
        if map_file_path and os.path.exists(map_file_path):
            os.remove(map_file_path)



# --- Main Bot Execution Logic ---
def main() -> None:
    """Run the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Error: TELEGRAM_BOT_TOKEN no encontrado. Asegúrate de configurar tu .env file.")
        print("Error: TELEGRAM_BOT_TOKEN no encontrado. Asegúrate de configurar tu .env file.")
        return

    initialize_db(DATABASE_URL)
    
    # Cargar los IDs autorizados al inicio
    load_authorized_chat_ids_from_db()
    logger.info("IDs autorizados cargados al inicio del bot.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- INICIO DE LA MODIFICACIÓN EN main_conv_handler ---
    main_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CommandHandler("cargar_registro", start_new_record)
        ],
        states={
            SELECCION_INICIAL: [
                MessageHandler(filters.Regex("^(Cargar nuevo registro|Consultar registros en el mapa)$"), handle_initial_choice)
            ],
            
            # Flujo de carga de nuevo registro
            FECHA_HORA:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fecha_hora)],
            NUMERO_A:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_numeroA)],
            SENTIDO:             [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sentido)],
            NUMERO_B:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_numeroB)],
            DIRECCION:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_direccion)],
            LOCALIDAD:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_localidad)],
            PROVINCIA:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_provincia)],
            LATITUD:             [MessageHandler(filters.TEXT & ~filters.COMMAND, get_latitud)],
            LONGITUD:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_longitud)],
            RADIO_COBERTURA:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_radio_cobertura)],
            AZIMUT:              [MessageHandler(filters.TEXT & ~filters.COMMAND, get_azimut)],
            APER_HORIZONTAL:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_aper_horizontal)],
            APER_VERTICAL:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_aper_vertical)],
            CONFIRMACION: [ # <--- Esta es la lista de manejadores para CONFIRMACION
                MessageHandler(filters.Regex('^(?i)(Sí|Si)$'), handle_confirm_yes),
                MessageHandler(filters.Regex('^(?i)(No)$'), handle_confirm_no),
                # Este manejador estaba fuera de la lista, ahora está dentro y correctamente indentado
                MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_confirmation_input), 
            ], # <--- Cierre de la lista de manejadores para CONFIRMACION
            
            # --- ESTADOS PARA CONSULTAR REGISTROS EN EL MAPA ---
            CONSULTA_FECHA_INICIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_consulta_fecha_inicio)],
            CONSULTA_FECHA_FIN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_consulta_fecha_fin)],
            # --- FIN ESTADOS CONSULTAR REGISTROS EN EL MAPA ---
        },
        fallbacks=[CommandHandler("cancelar", cancel_command)],
    )
    # --- FIN DE LA MODIFICACIÓN EN main_conv_handler ---

    application.add_handler(main_conv_handler)
    application.add_handler(CommandHandler("ayuda", ayuda_command))
    application.add_handler(CommandHandler("resumen", resumen_command))
    application.add_handler(CommandHandler("add_authorized", add_authorized_user))
    application.add_handler(CommandHandler("remove_authorized", remove_authorized_user))
    application.add_handler(CommandHandler("list_authorized", list_authorized_users))
    application.add_handler(CommandHandler("set_user_role", set_user_role)) # Nuevo handler

    logger.info("Bot iniciado. Presiona Ctrl-C para detener.")
    print("Bot iniciado. Presiona Ctrl-C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()