import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,jorgeajs.pythonanywhere.com').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'consulta_scoring_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'scoring.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'consulta_scoring_app.context_processors.roles_ui',
        ],
    },
}]

WSGI_APPLICATION = 'scoring.wsgi.application'

# Base transaccional del prototipo.
# SQLite guarda usuarios, autenticación, sesiones e historial de evaluaciones.
# Se elige deliberadamente para mantener el alcance de la tesis pequeño.
# Si posteriormente se exige PostgreSQL, Django permite cambiar el backend
# sin modificar el modelo de credit scoring.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Asuncion'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'consulta_scoring_app:solicitud'
LOGOUT_REDIRECT_URL = 'login'

MODEL_PATH = Path(os.getenv('MODEL_PATH', BASE_DIR / 'artifacts' / 'credit_score_modelo_final.joblib'))
FEATURE_BOUNDS_PATH = Path(os.getenv('FEATURE_BOUNDS_PATH', BASE_DIR / 'artifacts' / 'feature_bounds.json'))

# Reporte opcional, exportado de los experimentos originales. Sin archivo,
# las métricas se muestran como pendientes (nunca se inventan).
MODEL_VALIDATION_REPORT_PATH = Path(os.getenv(
    'MODEL_VALIDATION_REPORT_PATH', BASE_DIR / 'artifacts' / 'model_validation_report.json',
))
