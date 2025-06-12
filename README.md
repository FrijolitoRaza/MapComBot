🚀 MapComBot - Asistente Inteligente para Gestión de Antenas vía Telegram



🌟 Descripción General
El MapComBot es una aplicación de Telegram diseñada para optimizar la gestión y visualización de registros de infraestructura de telecomunicaciones. Permite a los usuarios autorizados cargar nuevos registros de forma interactiva directamente desde el chat de Telegram, así como consultar y visualizar estos datos geográficamente en mapas interactivos generados dinámicamente.

Este bot transforma un proceso manual de recolección de datos en una experiencia eficiente y accesible, proporcionando una herramienta poderosa para el personal de campo y los equipos de gestión.



✨ Características Principales:
* Registro de datos guiado por conversación: Un flujo conversacional paso a paso que guía al usuario en la carga de diversos parámetros técnicos (fecha, hora, dirección, coordenadas GPS, radio de cobertura, azimut, aperturas, etc.).
* Validación de entrada robusta: Implementación de validaciones en tiempo real para asegurar la integridad y el formato correcto de los datos ingresados (fechas, números, coordenadas).
* Geocodificación integrada: Capacidad para transformar direcciones textuales en coordenadas geográficas precisas (latitud y longitud), facilitando la ubicación de la infraestructura.
* Almacenamiento persistente en Base de datos: Los registros se guardan de forma segura en una base de datos PostgreSQL, garantizando la persistencia y disponibilidad de los datos.
* Generación de Mapas Interactivos (Folium):
    ** Filtra registros por rango de fechas.
    ** Visualiza cada punto de registro en un mapa interactivo.
    ** Muestra el radio de cobertura y el azimut de cada antena, ofreciendo una representación visual clara de la dirección y el alcance de la señal.
    ** Genera mapas con información detallada de cada punto al hacer clic.
* Gestión de usuarios autorizados: Control de acceso basado en IDs de usuario, asegurando que solo el personal autorizado pueda interactuar con el bot.
* Despliegue en la nube: Preparado para producción, garantizando alta disponibilidad y escalabilidad.



🛠️ Habilidades Técnicas Destacadas
Este proyecto demuestra un conjunto de habilidades técnicas robustas y prácticas:

Desarrollo de Bots con Python: Dominio de la librería python-telegram-bot para construir interfaces conversacionales complejas, gestionar estados de conversación, y manejar diferentes tipos de entradas de usuario.
Manejo de Bases de Datos:
Diseño y gestión de esquemas de bases de datos relacionales.
Interacción programática con bases de datos PostgreSQL utilizando psycopg2 para operaciones CRUD (Crear, Leer, Actualizar, Borrar).
Preparación para despliegue de DB en la nube.
Visualización de Datos Geoespaciales (Folium & Pandas):
Utilización de Folium para generar mapas interactivos basados en datos geográficos.
Manipulación y análisis de datos tabulares con Pandas para preparar la información para la visualización en mapas.
Cálculos trigonométricos para representar azimut y radios de cobertura en el mapa.


Ingeniería de Software & Arquitectura:
Estructuración modular del código para facilitar la mantenibilidad y escalabilidad.
Gestión de estados complejos en una conversación, crucial para una experiencia de usuario fluida.
Manejo de errores y logging para una depuración y monitoreo efectivos.
Despliegue en la nube: Experiencia en la configuración y despliegue de aplicaciones Python en una plataforma PaaS (Platform as a Service), incluyendo:
Configuración de Procfile.
Gestión de variables de entorno (.env local, variables de entorno de nube).
Conexión con servicios de bases de datos externos.
Control de Versiones (Git & GitHub): Uso de Git para el control de versiones y GitHub para la colaboración y el alojamiento del código fuente.



🚀 Cómo Empezar (Desarrollo Local)
Para ejecutar el bot localmente, sigue estos pasos:

1 - Clona el repositorio:

git clone https://github.com/tu-usuario/telegram-telecom-map-bot.git
cd telegram-telecom-map-bot



2 - Crea y activa un entorno virtual:

python -m venv venv
# En Windows:
.\venv\Scripts\activate

# En macOS/Linux:
source venv/bin/activate


3 - Instala las dependencias:

pip install -r requirements.txt


4 - Configura tus variables de entorno:
Crea un archivo .env en la raíz de tu proyecto con el siguiente contenido:

TELEGRAM_BOT_TOKEN="TU_TOKEN_DE_BOT"
AUTHORIZED_CHAT_IDS="ID_USUARIO_1,ID_USUARIO_2" # IDs de Telegram separados por coma
# Para desarrollo local con SQLite (si no migras a PostgreSQL localmente)
# DB_NAME="telecom_data.db"
# Para desarrollo local con PostgreSQL
# DATABASE_URL="postgresql://usuario:contraseña@host:puerto/nombre_db"
Obtén tu TELEGRAM_BOT_TOKEN de BotFather en Telegram.
Usa @userinfobot en Telegram para obtener tu ID_USUARIO.


5 - Ejecuta el bot:

python bot.py

Tu bot debería iniciarse y responder a tus comandos en Telegram.



☁️ Despliegue en Producción
Este proyecto está configurado para un despliegue sencillo utilizando una base de datos PostgreSQL.

Crea una base de datos PostgreSQL en tu proveedor preferido y obtén la External Database URL.
Configura tu servicio en Render:
Crea un Background Worker en Render.
Conecta tu repositorio de GitHub.
Configura las variables de entorno: TELEGRAM_BOT_TOKEN, AUTHORIZED_CHAT_IDS, y DATABASE_URL (con la URL de tu DB de Render).
Asegúrate de que tu Procfile esté configurado como worker: python bot.py.
Monitorea los logs en Render para asegurar un despliegue exitoso.



🤝 Contribuciones
¡Las contribuciones son bienvenidas! Si encuentras un error o tienes una mejora, no dudes en abrir un issue o enviar un pull request.




📄 Licencia
Este proyecto está bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.

¡Gracias por revisar el proyecto!
Desarrollado con ❤️ por [FrijolitoRaza/https://github.com/FrijolitoRaza]