
def render_correo_html(titulo: str, cuerpo: str, estado: str, logo_url: str) -> str:
    """Genera el HTML para notificaciones por correo.

    Parameters
    ----------
    titulo : str
        Título principal del mensaje.
    cuerpo : str
        Cuerpo del mensaje en texto plano. Puede incluir saltos de línea con ``\n``.
    estado : str
        Estado actual de la requisición que se mostrará de forma destacada.
    logo_url : str
        URL o cadena base64 de la imagen del logo.

    Returns
    -------
    str
        Cadena con el contenido HTML formateado.
    """
    # Reemplazar saltos de línea por etiquetas <br> para mantener el formato
    cuerpo_html = "<br>".join(cuerpo.splitlines())

    # Colores corporativos
    color_encabezado = "#1D1455"
    color_boton = "#F99C1B"
    color_fondo_pie = "#f0f0f0"

    html = f"""
    <!DOCTYPE html>
    <html lang=\"es\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>{titulo}</title>
        <link href='https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap' rel='stylesheet'>
    </head>
    <body style=\"font-family:'Poppins', Arial, Helvetica, sans-serif; margin:0; padding:0;\">
        <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"border-collapse:collapse;\">
            <tr>
                <td style=\"background-color:{color_encabezado}; padding:20px; text-align:center;\">
                    <img src=\"{logo_url}\" alt=\"Logo\" style=\"width:60px;\">
                </td>
            </tr>
            <tr>
                <td style=\"background-color:#ffffff; padding:30px;\">
                    <h2 style=\"color:{color_encabezado}; margin-top:0;\">{titulo}</h2>
                    <p>Hola,</p>
                    <p>{cuerpo_html}</p>
                    <p style=\"margin:20px 0;\">
                        <span style=\"background-color:{color_encabezado}; color:#ffffff; padding:8px 12px; border-radius:4px;\">
                            {estado}
                        </span>
                    </p>
                    <p style="text-align:center; margin:30px 0;">
                        <a href="https://sistema.granjalosmolinos.com" style="background-color:{color_boton}; color:#ffffff; text-decoration:none; padding:10px 20px; border-radius:4px;">
                            Ingresar al sistema
                        </a>
                    </p>
                </td>
            </tr>
            <tr>
                <td style=\"background-color:{color_fondo_pie}; color:#666666; font-size:12px; padding:15px; text-align:center;\">
                    Este mensaje es confidencial y está dirigido solo a su destinatario. Si lo recibió por error, por favor elimínelo.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html
