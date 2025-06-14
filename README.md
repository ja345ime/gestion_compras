# 📦 Sistema de Requisiciones - Granja Los Molinos

Este sistema permite la gestión digital de requisiciones internas, aprobaciones por área y automatización de notificaciones por correo.

## 📧 Configuración de correos (Brevo / Sendinblue)

El sistema envía las notificaciones a través de la API transaccional de Brevo. Todas las credenciales deben especificarse en el archivo `.env`.

### Variables requeridas

```env
BREVO_API_KEY=tu_api_key_de_brevo
BREVO_SENDER_EMAIL=notificaciones@granjalosmolinos.com
BREVO_SENDER_NAME=Granja Los Molinos
SECRET_KEY=tu_clave_secreta_de_flask
ADMIN_PASSWORD=TuClaveFuerte123
FLASK_DEBUG=0
```

### Cómo configurar el entorno
1. Copia `.env.example` y renómbralo como `.env`.
2. Llena los valores reales en `.env`.
3. En desarrollo puedes ejecutar `flask run`.
4. Para producción levanta el servidor con:

   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
   ```

Se recomienda usar Nginx como proxy inverso.

Al iniciar por primera vez ejecuta `flask crear-admin` para
asegurar que exista el usuario `admin` con privilegios de superadministrador.
Aplica las migraciones con:

```bash
flask db init   # solo la primera vez
flask db migrate -m "init"
flask db upgrade
```

### Instalación rápida

Para instalar todas las dependencias y ejecutar el servidor utiliza:

```bash
./setup.sh
```

### Tiempo de expiración de sesión

El sistema invalida otras sesiones activas de un usuario cuando se inicia sesión
en un nuevo dispositivo. Además, las sesiones expiran después de una hora. Este
valor puede modificarse cambiando la constante `DURACION_SESION` en `app/config.py`.

Si luego de actualizar obtienes un **Internal Server Error**, asegúrate de que
la base de datos tenga la columna `session_token`. La aplicación intentará
crearla automáticamente al iniciar. Utiliza PostgreSQL especificando
`DATABASE_URL` en el archivo `.env` y gestiona el esquema con `Flask-Migrate`.



### Configuración Nginx

Ejemplo de bloque de servidor:

```nginx
server {
    listen 80;
    server_name _;

    location /static/ {
        alias /usr/share/nginx/html/static/;
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
    }
}
```

Con esta configuración el sistema será accesible a través de Nginx
utilizando un dominio o una IP interna como `http://192.168.x.x/`.

### Reiniciar base de datos en pruebas

1. Ejecuta el siguiente código para recrear las tablas y los datos iniciales
   en una base temporal de pruebas:

```python
from app import db, crear_datos_iniciales, app
with app.app_context():
    db.create_all()
   crear_datos_iniciales()
```

### Respaldos automáticos

Ejecuta `backup_daily.sh` desde cron para guardar un volcado de la base de datos
en la carpeta definida por `BACKUP_DIR` (por defecto `/backups`). El resultado de
cada respaldo se registra en `backup.log`.
