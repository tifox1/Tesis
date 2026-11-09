from django.conf import settings
from django.db import models


class Solicitante(models.Model):
    """Ficha de identificación del prototipo; nunca es fuente automática de scoring."""

    class SituacionLaboral(models.TextChoices):
        DEPENDIENTE = 'DEPENDIENTE', 'Empleado dependiente'
        INDEPENDIENTE = 'INDEPENDIENTE', 'Trabajador independiente'
        DESEMPLEADO = 'DESEMPLEADO', 'Desempleado'
        JUBILADO = 'JUBILADO', 'Jubilado'
        OTRO = 'OTRO', 'Otro'

    cedula = models.CharField(max_length=12, unique=True, db_index=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField()
    ciudad = models.CharField(max_length=100)
    ocupacion = models.CharField(max_length=120)
    situacion_laboral = models.CharField(max_length=20, choices=SituacionLaboral.choices)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='solicitantes_registrados',
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['apellidos', 'nombres', 'id']

    def __str__(self):
        return f'{self.nombres} {self.apellidos} (CI {self.cedula})'


class EvaluacionScoring(models.Model):
    """Instantánea inmutable de los datos y el resultado de cada evaluación."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='evaluaciones_scoring',
    )
    # Null permite conservar los históricos creados antes de incorporar fichas.
    solicitante = models.ForeignKey(
        Solicitante, on_delete=models.PROTECT, null=True, blank=True,
        related_name='evaluaciones',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    entradas = models.JSONField()
    pd = models.FloatField(help_text='Probabilidad estimada del evento objetivo.')
    score = models.FloatField()
    banda = models.CharField(max_length=1, blank=True, default='')
    nivel_riesgo = models.CharField(max_length=40, blank=True, default='')
    cuota_maxima_estimada_gs = models.FloatField(default=0)
    ofertas = models.JSONField(default=list, blank=True)
    advertencias = models.JSONField(default=list, blank=True)
    modelo_version = models.CharField(max_length=50, default='credit_score_v1')

    class Meta:
        ordering = ['-fecha_hora']

    @property
    def pd_porcentaje(self):
        return self.pd * 100

    def __str__(self):
        return f'Evaluación {self.pk} - score {self.score:.1f} - banda {self.banda}'


class DecisionCredito(models.Model):
    """Decisión humana *simulada*: no concede ni desembolsa créditos reales."""

    class Estado(models.TextChoices):
        APROBADA = 'APROBADA', 'Aprobada (simulada)'
        CONDICIONAL = 'CONDICIONAL', 'Condicional (simulada)'
        RECHAZADA = 'RECHAZADA', 'Rechazada (simulada)'

    evaluacion = models.OneToOneField(
        EvaluacionScoring, on_delete=models.PROTECT, related_name='decision_crediticia',
    )
    estado = models.CharField(max_length=12, choices=Estado.choices)
    producto_codigo = models.CharField(max_length=32, blank=True, default='')
    motivo = models.TextField(max_length=1200)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='decisiones_registradas',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_hora']

    def __str__(self):
        return f'Decisión {self.estado} de evaluación {self.evaluacion_id}'


class EventoAuditoria(models.Model):
    """Rastro de operaciones académicas sin datos personales ni financieros en detalle.

    Se registra la referencia al objeto, nunca la cédula ni las variables del scoring.
    No es un almacén legalmente inalterable: es auditoría interna del prototipo.
    """

    class Accion(models.TextChoices):
        SOLICITANTE_CREADO = 'SOLICITANTE_CREADO', 'Ficha creada'
        SOLICITANTE_CONSULTADO = 'SOLICITANTE_CONSULTADO', 'Ficha consultada'
        EVALUACION_CREADA = 'EVALUACION_CREADA', 'Evaluación creada'
        EVALUACION_CONSULTADA = 'EVALUACION_CONSULTADA', 'Evaluación consultada'
        HISTORIAL_CONSULTADO = 'HISTORIAL_CONSULTADO', 'Historial consultado'
        DECISION_CREADA = 'DECISION_CREADA', 'Decisión registrada'
        SEGUIMIENTO_CREADO = 'SEGUIMIENTO_CREADO', 'Seguimiento creado'
        SEGUIMIENTO_ACTUALIZADO = 'SEGUIMIENTO_ACTUALIZADO', 'Seguimiento actualizado'
        SEGUIMIENTO_CONSULTADO = 'SEGUIMIENTO_CONSULTADO', 'Seguimiento consultado'
        USUARIO_CREADO = 'USUARIO_CREADO', 'Usuario creado'
        ROL_MODIFICADO = 'ROL_MODIFICADO', 'Rol modificado'
        ACCESO_DENEGADO = 'ACCESO_DENEGADO', 'Acceso denegado'
        AUDITORIA_CONSULTADA = 'AUDITORIA_CONSULTADA', 'Auditoría consultada'
        INDICADORES_CONSULTADOS = 'INDICADORES_CONSULTADOS', 'Indicadores consultados'

    class Resultado(models.TextChoices):
        EXITO = 'EXITO', 'Realizada'
        DENEGADO = 'DENEGADO', 'Denegada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_auditoria',
    )
    usuario_nombre = models.CharField(max_length=150, help_text='Usuario al momento del evento.')
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    accion = models.CharField(max_length=40, choices=Accion.choices, db_index=True)
    resultado = models.CharField(max_length=8, choices=Resultado.choices, default=Resultado.EXITO)
    recurso = models.CharField(max_length=35, blank=True, default='')
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True)
    detalle = models.CharField(max_length=180, blank=True, default='',
                              help_text='Resumen técnico, sin cédula ni datos sensibles.')

    class Meta:
        ordering = ['-fecha_hora', '-id']
        indexes = [models.Index(fields=['recurso', 'objeto_id'], name='audit_recurso_obj_idx')]
        verbose_name = 'Evento de auditoría'
        verbose_name_plural = 'Eventos de auditoría'

    def __str__(self):
        return f'{self.fecha_hora:%Y-%m-%d %H:%M} {self.usuario_nombre} {self.accion}'


class SeguimientoCredito(models.Model):
    """Registro académico de comportamiento de un crédito FICTICIO aprobado.

    No implica un desembolso, un contrato real ni una medición de calidad
    predictiva sobre créditos observados. Un crédito simulado por decisión.
    """

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', 'Vigente (simulado)'
        VENCIDO = 'VENCIDO', 'Vencido (simulado)'
        CANCELADO = 'CANCELADO', 'Cancelado (simulado)'

    decision = models.OneToOneField(
        DecisionCredito, on_delete=models.PROTECT, related_name='seguimiento',
    )
    fecha_otorgamiento = models.DateField(help_text='Fecha simulada de otorgamiento.')
    fecha_cierre_prevista = models.DateField(
        help_text='Vencimiento previsto; no representa un resultado observado.',
    )
    fecha_observacion = models.DateField(
        help_text='Fecha hasta la cual se declara observado el crédito ficticio.',
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.VIGENTE)
    max_dias_mora = models.PositiveIntegerField(
        default=0, help_text='Máximo de días en mora reportados hasta la observación.',
    )
    observaciones = models.TextField(max_length=500, blank=True, default='')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='seguimientos_creados',
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='seguimientos_actualizados',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_actualizacion', '-id']
        verbose_name = 'Seguimiento académico'
        verbose_name_plural = 'Seguimientos académicos'

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        errores = {}
        if self.decision_id and self.decision.estado != DecisionCredito.Estado.APROBADA:
            errores['__all__'] = 'Solo se realiza seguimiento de decisiones aprobadas.'
        if self.fecha_otorgamiento:
            if self.fecha_otorgamiento > timezone.localdate():
                errores['fecha_otorgamiento'] = 'No puede registrar un otorgamiento futuro como realizado.'
            if self.decision_id and self.fecha_otorgamiento < timezone.localdate(self.decision.fecha_hora):
                errores['fecha_otorgamiento'] = 'El otorgamiento no puede preceder a la decisión.'
        if self.fecha_cierre_prevista and self.fecha_otorgamiento:
            if self.fecha_cierre_prevista <= self.fecha_otorgamiento:
                errores['fecha_cierre_prevista'] = 'El cierre previsto debe ser posterior al otorgamiento.'
        if self.fecha_observacion and self.fecha_otorgamiento:
            if (self.max_dias_mora is not None and self.max_dias_mora >
                    max((self.fecha_observacion - self.fecha_otorgamiento).days, 0)):
                errores['max_dias_mora'] = 'La mora acumulada no puede exceder el tiempo transcurrido desde el otorgamiento.'
            if self.fecha_observacion < self.fecha_otorgamiento:
                errores['fecha_observacion'] = 'No puede observar un crédito antes de otorgarlo.'
            if self.fecha_observacion > timezone.localdate():
                errores['fecha_observacion'] = 'No se pueden declarar observaciones futuras como ocurridas.'
        if self.fecha_observacion and self.fecha_cierre_prevista:
            if self.estado == self.Estado.VENCIDO and self.fecha_observacion <= self.fecha_cierre_prevista:
                errores['estado'] = 'Vencido requiere una observación posterior al cierre previsto.'
            if self.estado == self.Estado.VIGENTE and self.fecha_observacion > self.fecha_cierre_prevista:
                errores['estado'] = 'No puede permanecer vigente después del cierre previsto.'
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f'Seguimiento simulado #{self.pk} / decisión #{self.decision_id}'
