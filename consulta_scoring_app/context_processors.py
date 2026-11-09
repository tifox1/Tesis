from .permissions import (
    es_administrador, puede_consultar, puede_evaluar, puede_ver_auditoria,
)


def roles_ui(request):
    user = request.user
    return {
        'ui_puede_consultar': puede_consultar(user),
        'ui_puede_evaluar': puede_evaluar(user),
        'ui_admin': es_administrador(user),
        'ui_auditoria': puede_ver_auditoria(user),
    }
