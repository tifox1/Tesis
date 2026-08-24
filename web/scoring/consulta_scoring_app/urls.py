from django.urls import path
from .views import solicitud_credito

app_name = "consulta_scoring_app"

urlpatterns = [
    path("solicitud/", solicitud_credito, name="solicitud"),
]
