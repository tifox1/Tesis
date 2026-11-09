from django.contrib import admin

from .models import DecisionCredito, EvaluacionScoring, EventoAuditoria, SeguimientoCredito, Solicitante


@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    list_display = ('id', 'cedula', 'nombres', 'apellidos', 'situacion_laboral', 'fecha_registro')
    search_fields = ('cedula', 'nombres', 'apellidos')
    readonly_fields = ('cedula', 'nombres', 'apellidos', 'fecha_nacimiento', 'ciudad', 'ocupacion', 'situacion_laboral', 'creado_por', 'fecha_registro')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



@admin.register(EvaluacionScoring)
class EvaluacionScoringAdmin(admin.ModelAdmin):
    list_display = ('id', 'solicitante', 'usuario', 'score', 'banda', 'fecha_hora')
    readonly_fields = ('usuario', 'solicitante', 'fecha_hora', 'entradas', 'pd', 'score', 'banda',
                       'nivel_riesgo', 'cuota_maxima_estimada_gs', 'ofertas', 'advertencias', 'modelo_version')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DecisionCredito)
class DecisionCreditoAdmin(admin.ModelAdmin):
    list_display = ('id', 'evaluacion', 'estado', 'usuario', 'fecha_hora')
    readonly_fields = ('evaluacion', 'estado', 'producto_codigo', 'motivo', 'usuario', 'fecha_hora')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'usuario_nombre', 'accion', 'resultado', 'recurso', 'objeto_id')
    list_filter = ('accion', 'resultado', 'recurso')
    search_fields = ('usuario_nombre', 'recurso')
    readonly_fields = ('usuario', 'usuario_nombre', 'fecha_hora', 'accion', 'resultado',
                       'recurso', 'objeto_id', 'detalle')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SeguimientoCredito)
class SeguimientoCreditoAdmin(admin.ModelAdmin):
    list_display = ('id', 'decision', 'estado', 'fecha_cierre_prevista',
                    'fecha_observacion', 'max_dias_mora', 'fecha_actualizacion')
    readonly_fields = ('decision', 'fecha_otorgamiento', 'fecha_cierre_prevista',
                       'fecha_observacion', 'estado', 'max_dias_mora', 'observaciones',
                       'creado_por', 'actualizado_por', 'fecha_creacion', 'fecha_actualizacion')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
