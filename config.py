import os
import secrets
import warnings

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secure secret key implementation
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('ENVIRONMENT') == 'production':
            raise ValueError("SECRET_KEY environment variable must be set in production")
        SECRET_KEY = secrets.token_hex(32)  # Strong random key for development
        warnings.warn("Using auto-generated SECRET_KEY. Set SECRET_KEY environment variable for production.")
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
