# 📦 Sistema de Requisiciones - Granja Los Molinos

Este sistema permite la gestión digital de requisiciones internas, aprobaciones por área y automatización de notificaciones por correo.

## 📧 Configuración SMTP (Brevo / Sendinblue)

El sistema utiliza un archivo `.env` para conectar con el servidor SMTP de Brevo y enviar notificaciones automáticas.

### Variables requeridas

```env
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=tu_usuario_brevo@example.com
SMTP_PASSWORD=tu_clave_smtp_de_brevo
MAIL_FROM=notificaciones@granjalosmolinos.com
SECRET_KEY=tu_clave_secreta_de_flask
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

### Instalación rápida

Para instalar todas las dependencias y ejecutar el servidor utiliza:

```bash
./setup.sh
```

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

1. Elimina el archivo `requisiciones.db`.
2. Ejecuta el siguiente código para recrear las tablas y los datos iniciales:

```python
from app import db, crear_datos_iniciales, app
with app.app_context():
    db.create_all()
    crear_datos_iniciales()
```
