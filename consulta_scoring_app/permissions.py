"""Roles internos y alcance de lectura; aplicar siempre desde el servidor."""
from django.db.models import Q

from .models import EvaluacionScoring, Solicitante

ROLES = ('ANALISTA', 'ADMINISTRADOR', 'AUDITOR')


def tiene_rol(user, *roles):
    return (user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=roles).exists()
    ))


def es_administrador(user):
    return tiene_rol(user, 'ADMINISTRADOR')


def es_analista(user):
    return tiene_rol(user, 'ANALISTA')


def puede_evaluar(user):
    # La administración puede realizar evaluaciones, no aprobar créditos.
    return tiene_rol(user, 'ANALISTA', 'ADMINISTRADOR')


def puede_decidir(user):
    return es_analista(user)


def es_auditor(user):
    return tiene_rol(user, 'AUDITOR')


def puede_consultar_todos(user):
    return tiene_rol(user, 'ADMINISTRADOR', 'AUDITOR')


def puede_consultar(user):
    return tiene_rol(user, *ROLES)


def puede_ver_auditoria(user):
    return tiene_rol(user, 'ADMINISTRADOR', 'AUDITOR')


def evaluaciones_visibles(user):
    qs = EvaluacionScoring.objects.select_related('usuario', 'solicitante')
    if not puede_consultar(user):
        return qs.none()
    return qs if puede_consultar_todos(user) else qs.filter(usuario=user)


def solicitantes_visibles(user):
    qs = Solicitante.objects.select_related('creado_por')
    if not puede_consultar(user):
        return qs.none()
    if puede_consultar_todos(user):
        return qs
    return qs.filter(Q(creado_por=user) | Q(evaluaciones__usuario=user)).distinct()
