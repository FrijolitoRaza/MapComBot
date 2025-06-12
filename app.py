from flask import Flask, render_template, request
import sqlite3
import pandas as pd
import numpy as np
import folium
import math
import random
from datetime import datetime


import os # Asegúrate de que esta línea esté presente
from dotenv import load_dotenv # Asegúrate de que esta línea esté presente

# Ensure database_setup.py is in the same directory or adjust path
from database_setup import initialize_db 

app = Flask(__name__)

# Carga las variables de entorno desde .env
load_dotenv()

# Obtiene el nombre de la base de datos desde las variables de entorno
DB_NAME = os.getenv("DB_NAME")

# Verificación para depuración (puedes eliminarla después)
if not DB_NAME:
    print("Error: DB_NAME no encontrado en el archivo .env. Asegúrate de configurarlo.")
    exit()

# Helper function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

# Helper function to calculate points for a sector
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

# --- LA FUNCIÓN map_view ACTUALIZADA ---
@app.route('/', methods=['GET', 'POST'])
def map_view():
    fecha_desde = request.form.get('fecha_desde')
    fecha_hasta = request.form.get('fecha_hasta')

    map_html = None
    records_df = pd.DataFrame() # Usaremos un DataFrame para compatibilidad con tu guía

    conn = get_db_connection()
    try:
        query = "SELECT * FROM registros_telecom"
        params = []

        if fecha_desde and fecha_hasta:
            query += " WHERE substr(fecha_hora, 1, 10) BETWEEN ? AND ?"
            params.append(fecha_desde)
            params.append(fecha_hasta)
        elif fecha_desde:
            query += " WHERE substr(fecha_hora, 1, 10) >= ?"
            params.append(fecha_desde)
        elif fecha_hasta:
            query += " WHERE substr(fecha_hora, 1, 10) <= ?"
            params.append(fecha_hasta)
        
        query += " ORDER BY fecha_hora DESC"

        # Leer directamente a un DataFrame de pandas
        records_df = pd.read_sql_query(query, conn, params=params)

        if not records_df.empty:
            # Asegurarse de que las columnas numéricas sean floats
            for col in ['latitud', 'longitud', 'radioCobertura', 'Azimut', 'aperHorizontal', 'aperVertical']:
                records_df[col] = pd.to_numeric(records_df[col], errors='coerce')
            
            # Limpiar filas con NaN en latitud o longitud
            records_df.dropna(subset=['latitud', 'longitud'], inplace=True)
            
            if records_df.empty: # Si después de limpiar no quedan registros válidos
                map_html = "<p style='text-align:center;'>No hay registros válidos con coordenadas para mostrar.</p>"
                m = folium.Map(location=[-34.6037, -58.3816], zoom_start=12) # Mapa por defecto
            else:
                # Crear un mapa centrado en la media de las coordenadas del DataFrame
                map_center = [records_df['latitud'].mean(), records_df['longitud'].mean()]
                m = folium.Map(location=map_center, zoom_start=12)

                # Iterar sobre cada fila del DataFrame para agregar elementos al mapa
                for index, row in records_df.iterrows():
                    lat = row['latitud']
                    lon = row['longitud']
                    radio = row['radioCobertura'] # Este valor ya está en metros
                    azimut = row['Azimut']
                    apertura_v = row['aperVertical'] # Apertura Vertical
                    apertura_h = row['aperHorizontal'] # Apertura Horizontal

                    # Convertir radio de metros a kilómetros para calcular_punto_final
                    radio_km = radio / 1000.0 if radio is not None else 0

                    # Crear el contenido del popup (tooltip_content de tu guía, pero para popup)
                    # Asegúrate de usar los nombres de columna de tu DB
                    popup_html = f"""
                    <b>ID Registro:</b> {row['id']}<br>
                    <b>Fecha y Hora:</b> {row['fecha_hora']}<br>
                    <b>Número Emisor (A):</b> {row['numeroA']}<br>
                    <b>Sentido:</b> {row['sentido']}<br>
                    <b>Número Receptor (B):</b> {row['numeroB']}<br>
                    <b>Dirección:</b> {row['direccion']}<br>
                    <b>Localidad:</b> {row['localidad']}<br>
                    <b>Provincia:</b> {row['provincia']}<br><hr>
                    <b>Latitud:</b> {lat}<br>
                    <b>Longitud:</b> {lon}<br>
                    <b>Radio Cobertura:</b> {radio} m<br>
                    <b>Azimut:</b> {azimut}°<br>
                    <b>Apertura Horizontal:</b> {apertura_h}°<br>
                    <b>Apertura Vertical:</b> {apertura_v}°
                    """

                    # Agregar marcador
                    folium.Marker(
                        location=[lat, lon],
                        popup=folium.Popup(popup_html, max_width=300), # Usar popup_html aquí
                        icon=folium.Icon(color='blue', icon='info-sign') # icon='tower-broadcast' de font-awesome es 'info-sign' en default folium
                    ).add_to(m)

                    # Graficar el círculo y el sector solo si los datos son válidos
                    if lat is not None and lon is not None and radio is not None and azimut is not None and apertura_h is not None:
                        # Agregar círculo de cobertura (radio en metros)
                        folium.Circle(
                            location=[lat, lon],
                            radius=radio, # Folium Circle espera radio en metros
                            color='blue',
                            fill=True,
                            fill_opacity=0.02,
                            tooltip=f"Radio: {radio} m"
                        ).add_to(m)

                        # Calcular vértices del polígono de cobertura (el "triángulo" o "porción de pizza")
                        # Tu azimut en la DB es Norte=0, Este=90, etc. Esto es estándar.
                        # calcular_punto_final espera azimut normal.

                        # Calcular los dos bordes del sector
                        angle_left = azimut - (apertura_h / 2)
                        angle_right = azimut + (apertura_h / 2)

                        # Puntos del polígono: centro, punto extremo del borde izquierdo, punto extremo del borde derecho (y el centro de nuevo para cerrar)
                        point_left_border = calcular_punto_final(lat, lon, angle_left, radio_km)
                        point_right_border = calcular_punto_final(lat, lon, angle_right, radio_km)
                        
                        # Crear los puntos para el polígono: centro, punto del borde izquierdo, y luego todos los puntos del arco
                        # hasta el punto del borde derecho, y finalmente de nuevo el centro.
                        
                        # Para un "sector de pizza" más suave, podemos generar puntos intermedios en el arco
                        sector_points = [[lat, lon]] # Empieza con el centro
                        num_arc_points = 20 # Cuántos puntos para dibujar el arco

                        # Convertir ángulos a formato 0=Este, 90=Norte para numpy trig. functions
                        # Y ajustar la dirección de crecimiento del ángulo si es necesario para el arco
                        start_angle_rad_math = np.deg2rad(90 - angle_left)
                        end_angle_rad_math = np.deg2rad(90 - angle_right)

                        # Asegurarse de que el ángulo final sea mayor que el inicial si el arco cruza el 360/0
                        if start_angle_rad_math < end_angle_rad_math:
                            # Esto es si el sector envuelve 0
                            start_angle_rad_math += 2 * np.pi 

                        for i in range(num_arc_points + 1):
                            interp_angle_rad_math = start_angle_rad_math + (end_angle_rad_math - start_angle_rad_math) * i / num_arc_points
                            
                            # Convertir de nuevo a azimut para calcular_punto_final o usar la fórmula de abajo
                            # Si usamos la fórmula de calcular_punto_final, necesitamos un azimut entre 0 y 360
                            # azimut_interp = 90 - np.rad2deg(interp_angle_rad_math) # Esta conversión es tricky con negativos
                            # while azimut_interp < 0: azimut_interp += 360
                            # while azimut_interp >= 360: azimut_interp -= 360

                            # Calcular punto directo usando la fórmula de esférica con el ángulo interp_angle_rad_math
                            delta_lat_interp = (radio_km / 6371.0) * np.sin(interp_angle_rad_math) # seno para latitud
                            delta_lon_interp = (radio_km / (6371.0 * np.cos(np.deg2rad(lat)))) * np.cos(interp_angle_rad_math) # coseno para longitud

                            arc_lat = lat + np.rad2deg(delta_lat_interp)
                            arc_lon = lon + np.rad2deg(delta_lon_interp)
                            sector_points.append([arc_lat, arc_lon])

                        # Añade el último punto si no se agregó ya
                        # sector_points.append([lat, lon]) # Cierra el polígono con el centro

                        folium.Polygon(
                            locations=sector_points, # Esto ahora incluye el arco y el centro
                            color=color_aleatorio(),
                            fill=True,
                            fill_opacity=0.3,
                            tooltip=f"Azimut: {azimut}°, Apertura H: {apertura_h}°"
                        ).add_to(m)

            # (Opcional) Agregar marcadores manuales si querés (adaptados de tu guía)
#            marcadores_manuales_info = [
#                {
#                    'coords': [-34.8726993, -58.6503373],
#                    'tooltip': '<b>Lugar:</b> Casa BUSCADO<br><b>Tipo:</b> Domicilio<br><b>Dirección:</b> Mz 8, Lote 6; B° Vernazza, Virrey del Pino, PBA '
#                },
#                {
#                    'coords': [-34.57379356399747, -58.49992169303971],
#                    'tooltip': '<b>Lugar:</b> Trabajo de Wendy<br><b>Tipo:</b> Domicilio<br><b>Dirección:</b> Pje. Achega 3063, Caba'
#                },
#            ]
#
#            for i, marcador_info in enumerate(marcadores_manuales_info, start=1):
#                folium.Marker(
#                    location=marcador_info['coords'],
#                    popup=f"Marcador Manual {i}", # Puedes hacer un popup más detallado si quieres
#                    tooltip=marcador_info['tooltip'],
#                    icon=folium.Icon(color='black', icon='home', prefix='fa')
#                ).add_to(m)

            map_html = m._repr_html_()
        else:
            map_html = "<p style='text-align:center;'>No hay registros para mostrar en el rango de fechas seleccionado.</p>"

    except sqlite3.Error as e:
        print(f"Error de base de datos: {e}")
        map_html = f"<p style='text-align:center; color:red;'>Error al conectar o consultar la base de datos: {e}</p>"
    except Exception as e:
        print(f"Error general en map_view: {e}")
        map_html = f"<p style='text-align:center; color:red;'>Error general al generar el mapa: {e}</p>"
        m = folium.Map(location=[-34.6037, -58.3816], zoom_start=12)
        map_html = m._repr_html_()
    finally:
        if conn:
            conn.close()

    return render_template('map_display.html', map_html=map_html,
                           fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

if __name__ == '__main__':
    initialize_db(DB_NAME) # Ensure the DB is initialized before running the app
    app.run(debug=True)