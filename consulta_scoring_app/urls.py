from django.urls import path
from . import views

app_name = 'consulta_scoring_app'

urlpatterns = [
    path('', views.solicitud_credito, name='solicitud'),
    path('scoring/', views.solicitud_credito, name='scoring'),
    path('solicitantes/', views.solicitantes_lista, name='solicitantes_lista'),
    path('solicitantes/nuevo/', views.solicitante_nuevo, name='solicitante_nuevo'),
    path('solicitantes/<int:pk>/', views.solicitante_detalle, name='solicitante_detalle'),
    path('solicitantes/<int:pk>/evaluar/', views.evaluar_solicitante, name='evaluar_solicitante'),
    path('historial/', views.historial, name='historial'),
    path('evaluaciones/<int:pk>/', views.evaluacion_detalle, name='evaluacion_detalle'),
    path('evaluaciones/<int:pk>/decision/', views.registrar_decision, name='registrar_decision'),
    path('usuarios/', views.usuarios_lista, name='usuarios_lista'),
    path('usuarios/alta/', views.usuario_alta, name='usuario_alta'),
    path('usuarios/<int:pk>/rol/', views.usuario_cambiar_rol, name='usuario_cambiar_rol'),
    path('auditoria/', views.auditoria_lista, name='auditoria_lista'),
    path('indicadores/', views.indicadores, name='indicadores'),
    path('seguimientos/', views.seguimientos_lista, name='seguimientos_lista'),
    path('evaluaciones/<int:pk>/seguimiento/nuevo/', views.seguimiento_nuevo, name='seguimiento_nuevo'),
    path('seguimientos/<int:pk>/', views.seguimiento_detalle, name='seguimiento_detalle'),
    path('seguimientos/<int:pk>/actualizar/', views.seguimiento_actualizar, name='seguimiento_actualizar'),
]
