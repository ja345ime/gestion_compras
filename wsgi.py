from app import app

# Gunicorn buscará la variable 'app'
if __name__ == '__main__':
    app.run()
