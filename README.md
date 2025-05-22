# Gestión Compras

Esta aplicación es un sistema sencillo de requisiciones utilizando Flask y SQLite.

## Configuración de correo

Para que se envíen las notificaciones por correo se deben establecer las variables de entorno:

- `SMTP_SERVER`: servidor SMTP a utilizar.
- `SMTP_PORT`: puerto del servidor SMTP (por defecto `587`).
- `SMTP_USER`: usuario para autenticarse en el servidor SMTP.
- `SMTP_PASSWORD`: contraseña del usuario SMTP.
- `MAIL_FROM`: dirección de correo que se usará como remitente. Si no se especifica se usará `jaimegaya@granjalosmolinos.com` por defecto.

