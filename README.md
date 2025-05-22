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
FLASK_DEBUG=1
```

### Cómo configurar el entorno
1. Copia `.env.example` y renómbralo como `.env`
2. Llena los valores reales en `.env`
3. Ejecuta la app con `python app.py`
