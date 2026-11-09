"""Auditoría de operaciones relevantes. No registrar PII ni las entradas del modelo."""
from ..models import EventoAuditoria


def registrar_evento(usuario, accion, *, recurso='', objeto_id=None, detalle='', denegado=False):
    """Guardar solo identificadores internos y metadatos no sensibles."""
    if not usuario or not usuario.is_authenticated:
        return None
    return EventoAuditoria.objects.create(
        usuario=usuario,
        usuario_nombre=usuario.get_username()[:150],
        accion=accion,
        resultado=EventoAuditoria.Resultado.DENEGADO if denegado else EventoAuditoria.Resultado.EXITO,
        recurso=recurso,
        objeto_id=objeto_id,
        detalle=detalle[:180],
    )
