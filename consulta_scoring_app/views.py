from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AltaUsuarioForm, CambiarRolForm, DecisionCreditoForm, SeguimientoCreditoForm, EvaluacionScoringForm,
    SolicitanteForm, edad_en_fecha, normalizar_cedula,
)
from .models import DecisionCredito, EvaluacionScoring, EventoAuditoria, SeguimientoCredito, Solicitante
from .services.credit_rules import (
    CARGA_FINANCIERA_MAXIMA,
    EDAD_MAXIMA_VENCIMIENTO,
    TASA_USURARIA_REFERENCIA,
    TASA_USURARIA_REFERENCIA_PERIODO,
    evaluar_productos,
)
from .services.scoring_service import evaluar


from .permissions import (
    es_administrador, evaluaciones_visibles, solicitantes_visibles,
    puede_consultar, puede_decidir, puede_evaluar, puede_ver_auditoria, puede_consultar_todos,
)
from .services.auditoria_service import registrar_evento
from .services.indicadores_service import obtener_indicadores_operativos, leer_reporte_validacion


def exigir_permiso(request, permitido, recurso='', objeto_id=None):
    if not permitido:
        registrar_evento(
            request.user, EventoAuditoria.Accion.ACCESO_DENEGADO, recurso=recurso,
            objeto_id=objeto_id, detalle='Acción no autorizada', denegado=True,
        )
        raise PermissionDenied('No tiene permiso para realizar esta operación.')


def obtener_visible_o_404(request, queryset, recurso, pk):
    # No informar a otros analistas de la existencia de un expediente ajeno.
    objeto = queryset.filter(pk=pk).first()
    if objeto is None:
        registrar_evento(
            request.user, EventoAuditoria.Accion.ACCESO_DENEGADO,
            recurso=recurso, objeto_id=pk, detalle='Registro no accesible', denegado=True,
        )
        from django.http import Http404
        raise Http404('Registro no disponible.')
    return objeto


@login_required
def solicitud_credito(request):
    """El scoring requiere vincularse a una ficha; conserva la URL previa."""
    exigir_permiso(request, puede_consultar(request.user), recurso='solicitante')
    return redirect('consulta_scoring_app:solicitantes_lista')


@login_required
def solicitantes_lista(request):
    exigir_permiso(request, puede_consultar(request.user), recurso='solicitante')
    solicitantes = solicitantes_visibles(request.user)
    consulta = request.GET.get('ci', '').strip()
    if consulta:
        try:
            ci = normalizar_cedula(consulta)
        except ValidationError:
            messages.error(request, 'Ingrese una cédula válida para buscar.')
            solicitantes = solicitantes.none()
        else:
            solicitantes = solicitantes.filter(cedula=ci)
    return render(request, 'solicitantes/lista.html', {
        'solicitantes': solicitantes[:100], 'consulta': consulta,
    })


@login_required
def solicitante_nuevo(request):
    exigir_permiso(request, puede_evaluar(request.user), recurso='solicitante')
    form = SolicitanteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            solicitante = form.save(commit=False)
            solicitante.creado_por = request.user
            solicitante.save()
            registrar_evento(request.user, EventoAuditoria.Accion.SOLICITANTE_CREADO,
                            recurso='solicitante', objeto_id=solicitante.pk)
        messages.success(request, 'Ficha del solicitante registrada.')
        return redirect('consulta_scoring_app:solicitante_detalle', pk=solicitante.pk)
    return render(request, 'solicitantes/nuevo.html', {'form': form})


@login_required
def solicitante_detalle(request, pk):
    exigir_permiso(request, puede_consultar(request.user), recurso='solicitante', objeto_id=pk)
    solicitante = obtener_visible_o_404(request, solicitantes_visibles(request.user), 'solicitante', pk)
    registrar_evento(request.user, EventoAuditoria.Accion.SOLICITANTE_CONSULTADO,
                    recurso='solicitante', objeto_id=solicitante.pk)
    evaluaciones = evaluaciones_visibles(request.user).filter(solicitante=solicitante)[:100]
    return render(request, 'solicitantes/detalle.html', {
        'solicitante': solicitante, 'evaluaciones': evaluaciones,
        'puede_evaluar': puede_evaluar(request.user),
    })


@login_required
def evaluar_solicitante(request, pk):
    exigir_permiso(request, puede_evaluar(request.user), recurso='evaluacion')
    solicitante = obtener_visible_o_404(request, solicitantes_visibles(request.user), 'solicitante', pk)
    edad = edad_en_fecha(solicitante.fecha_nacimiento, timezone.localdate())
    if not 18 <= edad <= 100:
        messages.error(request, 'La edad del solicitante ya no está dentro del rango aceptado.')
        return redirect('consulta_scoring_app:solicitante_detalle', pk=pk)

    form = EvaluacionScoringForm(request.POST or None, edad_solicitante=edad)
    if request.method == 'POST' and form.is_valid():
        datos = form.datos_para_modelo()
        # La edad se deriva de la ficha: nunca de valores arbitrarios del navegador.
        datos['edad'] = edad
        resultado_modelo = evaluar(datos)
        simulacion = evaluar_productos(
            score=resultado_modelo['score'],
            edad=edad,
            ingreso_gs=datos['ingreso_mensual_bruto_gs'],
            dti=datos['relacion_deuda_ingreso'],
        )
        entradas_registro = {
            'datos_ingresados': datos,
            'captura_financiera': form.detalle_captura,
            'datos_modelo': resultado_modelo['features_modelo'],
            'tipo_cambio_referencia_gs': resultado_modelo['tipo_cambio_referencia_gs'],
        }
        with transaction.atomic():
            evaluacion = EvaluacionScoring.objects.create(
                solicitante=solicitante,
                usuario=request.user,
                entradas=entradas_registro,
                pd=resultado_modelo['pd'],
                score=resultado_modelo['score'],
                banda=simulacion['banda'],
                nivel_riesgo=simulacion['nivel_riesgo'],
                cuota_maxima_estimada_gs=simulacion['capacidad']['cuota_nueva_maxima_gs'],
                ofertas=simulacion['ofertas'],
                advertencias=resultado_modelo['advertencias'],
            )
            registrar_evento(request.user, EventoAuditoria.Accion.EVALUACION_CREADA,
                            recurso='evaluacion', objeto_id=evaluacion.pk)
        return render(request, 'resultado.html', {
            'evaluacion': evaluacion,
            'solicitante': solicitante,
            'pd_porcentaje': resultado_modelo['pd'] * 100,
            'score': resultado_modelo['score'],
            'banda': simulacion['banda'],
            'nivel_riesgo': simulacion['nivel_riesgo'],
            'advertencias': resultado_modelo['advertencias'],
            'datos': datos,
            'captura_financiera': form.detalle_captura,
            'ingreso_modelo': resultado_modelo['ingreso_modelo'],
            'tipo_cambio_referencia_gs': resultado_modelo['tipo_cambio_referencia_gs'],
            'capacidad': simulacion['capacidad'],
            'ofertas': simulacion['ofertas'],
            'motivo_sin_oferta': simulacion['motivo_sin_oferta'],
            'carga_financiera_maxima_pct': CARGA_FINANCIERA_MAXIMA * 100,
            'edad_maxima_vencimiento': EDAD_MAXIMA_VENCIMIENTO,
            'tasa_usuraria_pct': TASA_USURARIA_REFERENCIA * 100,
            'tasa_usuraria_periodo': TASA_USURARIA_REFERENCIA_PERIODO,
        })
    return render(request, 'solicitud.html', {
        'form': form, 'solicitante': solicitante, 'edad_solicitante': edad,
    })


@login_required
def historial(request):
    exigir_permiso(request, puede_consultar(request.user), recurso='evaluacion')
    evaluaciones = evaluaciones_visibles(request.user)[:100]
    registrar_evento(request.user, EventoAuditoria.Accion.HISTORIAL_CONSULTADO,
                    recurso='evaluacion')
    return render(request, 'historial.html', {'evaluaciones': evaluaciones})


@login_required
def evaluacion_detalle(request, pk):
    exigir_permiso(request, puede_consultar(request.user), recurso='evaluacion', objeto_id=pk)
    evaluacion = obtener_visible_o_404(request, evaluaciones_visibles(request.user), 'evaluacion', pk)
    registrar_evento(request.user, EventoAuditoria.Accion.EVALUACION_CONSULTADA,
                    recurso='evaluacion', objeto_id=pk)
    decision = DecisionCredito.objects.filter(evaluacion=evaluacion).select_related('usuario').first()
    seguimiento = (SeguimientoCredito.objects.filter(decision=decision).first()
                   if decision else None)
    return render(request, 'evaluaciones/detalle.html', {
        'evaluacion': evaluacion, 'decision': decision,
        'seguimiento': seguimiento,
        'puede_crear_seguimiento': (puede_decidir(request.user) and decision is not None
                                   and decision.estado == DecisionCredito.Estado.APROBADA
                                   and seguimiento is None),
        'puede_decidir': puede_decidir(request.user) and decision is None,
    })


@login_required
def registrar_decision(request, pk):
    exigir_permiso(request, puede_decidir(request.user), recurso='decision', objeto_id=pk)
    evaluacion = obtener_visible_o_404(request, evaluaciones_visibles(request.user), 'evaluacion', pk)
    if DecisionCredito.objects.filter(evaluacion=evaluacion).exists():
        messages.error(request, 'La evaluación ya tiene una decisión registrada.')
        return redirect('consulta_scoring_app:evaluacion_detalle', pk=pk)

    form = DecisionCreditoForm(request.POST or None, evaluacion=evaluacion)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            decision = form.save(commit=False)
            decision.evaluacion = evaluacion
            decision.usuario = request.user
            decision.save()
            registrar_evento(request.user, EventoAuditoria.Accion.DECISION_CREADA,
                            recurso='decision', objeto_id=decision.pk)
        messages.success(request, 'Decisión académica registrada correctamente.')
        return redirect('consulta_scoring_app:evaluacion_detalle', pk=pk)
    return render(request, 'evaluaciones/decision.html', {
        'form': form, 'evaluacion': evaluacion,
    })


@login_required
def usuarios_lista(request):
    exigir_permiso(request, es_administrador(request.user), recurso='usuario')
    usuarios = list(User.objects.prefetch_related('groups').order_by('username'))
    for u in usuarios:
        u.rol_actual = next((g.name for g in u.groups.all() if g.name in ('ANALISTA', 'ADMINISTRADOR', 'AUDITOR')), '')
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios})


@login_required
def usuario_alta(request):
    exigir_permiso(request, es_administrador(request.user), recurso='usuario')
    form = AltaUsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            registrar_evento(request.user, EventoAuditoria.Accion.USUARIO_CREADO,
                            recurso='usuario', objeto_id=user.pk, detalle='Rol inicial asignado')
        messages.success(request, f'Usuario {user.username} creado correctamente.')
        return redirect('consulta_scoring_app:usuarios_lista')
    return render(request, 'usuarios/alta.html', {'form': form})


@login_required
def usuario_cambiar_rol(request, pk):
    exigir_permiso(request, es_administrador(request.user), recurso='usuario', objeto_id=pk)
    objetivo = get_object_or_404(User, pk=pk)
    # Un administrador no superusuario no puede modificar cuentas de superusuario.
    if objetivo.is_superuser:
        exigir_permiso(request, False, recurso='usuario', objeto_id=pk)
    if objetivo.pk == request.user.pk:
        messages.error(request, 'No puede cambiar su propio rol desde esta pantalla.')
        return redirect('consulta_scoring_app:usuarios_lista')
    if request.method != 'POST':
        exigir_permiso(request, False, recurso='usuario', objeto_id=pk)
    form = CambiarRolForm(request.POST)
    if form.is_valid():
        nuevo_rol = form.cleaned_data['rol']
        with transaction.atomic():
            grupo, _ = Group.objects.get_or_create(name=nuevo_rol)
            rol_anterior = ','.join(objetivo.groups.filter(name__in=('ANALISTA', 'ADMINISTRADOR', 'AUDITOR')).values_list('name', flat=True)) or 'SIN_ROL'
            objetivo.groups.set([grupo])
            objetivo.is_staff = nuevo_rol == 'ADMINISTRADOR' or objetivo.is_superuser
            objetivo.save(update_fields=['is_staff'])
            registrar_evento(request.user, EventoAuditoria.Accion.ROL_MODIFICADO,
                            recurso='usuario', objeto_id=objetivo.pk,
                            detalle=f'Rol: {rol_anterior} -> {nuevo_rol}')
        messages.success(request, 'Rol actualizado correctamente.')
    else:
        messages.error(request, 'No se pudo cambiar el rol: opción inválida.')
    return redirect('consulta_scoring_app:usuarios_lista')


@login_required
def auditoria_lista(request):
    exigir_permiso(request, puede_ver_auditoria(request.user), recurso='auditoria')
    registrar_evento(request.user, EventoAuditoria.Accion.AUDITORIA_CONSULTADA, recurso='auditoria')
    eventos = EventoAuditoria.objects.select_related('usuario')
    accion = request.GET.get('accion', '')
    resultado = request.GET.get('resultado', '')
    if accion in EventoAuditoria.Accion.values:
        eventos = eventos.filter(accion=accion)
    else:
        accion = ''
    if resultado in EventoAuditoria.Resultado.values:
        eventos = eventos.filter(resultado=resultado)
    else:
        resultado = ''
    return render(request, 'auditoria/lista.html', {
        'eventos': eventos[:200],
        'acciones': EventoAuditoria.Accion.choices,
        'resultados': EventoAuditoria.Resultado.choices,
        'accion_actual': accion, 'resultado_actual': resultado,
    })


# ---- Módulo 3: seguimiento académico de créditos simulados ----


def seguimientos_visibles(user):
    """Limitar los seguimientos a evaluaciones que el usuario puede consultar."""
    return SeguimientoCredito.objects.filter(
        decision__evaluacion__in=evaluaciones_visibles(user)
    ).select_related(
        'decision', 'decision__evaluacion', 'decision__evaluacion__solicitante',
        'creado_por', 'actualizado_por',
    )


@login_required
def seguimientos_lista(request):
    exigir_permiso(request, puede_consultar(request.user), recurso='seguimiento')
    seguimientos = seguimientos_visibles(request.user)
    consulta = request.GET.get('ci', '').strip()
    estado = request.GET.get('estado', '').strip()
    if consulta:
        try:
            ci = normalizar_cedula(consulta)
        except ValidationError:
            messages.error(request, 'Ingrese una cédula válida para buscar.')
            seguimientos = seguimientos.none()
        else:
            seguimientos = seguimientos.filter(decision__evaluacion__solicitante__cedula=ci)
    if estado in SeguimientoCredito.Estado.values:
        seguimientos = seguimientos.filter(estado=estado)
    else:
        estado = ''
    return render(request, 'seguimientos/lista.html', {
        'seguimientos': seguimientos[:100], 'consulta': consulta,
        'estado_actual': estado, 'estados': SeguimientoCredito.Estado.choices,
    })


@login_required
def seguimiento_nuevo(request, pk):
    """Solo el analista autorizado, y solo después de aprobar una oferta."""
    exigir_permiso(request, puede_decidir(request.user), recurso='seguimiento', objeto_id=pk)
    evaluacion = obtener_visible_o_404(request, evaluaciones_visibles(request.user),
                                       'evaluacion', pk)
    decision = DecisionCredito.objects.filter(evaluacion=evaluacion).first()
    if not decision or decision.estado != DecisionCredito.Estado.APROBADA:
        messages.error(request, 'El seguimiento requiere una decisión aprobada (simulada).')
        return redirect('consulta_scoring_app:evaluacion_detalle', pk=pk)
    existente = SeguimientoCredito.objects.filter(decision=decision).first()
    if existente:
        return redirect('consulta_scoring_app:seguimiento_detalle', pk=existente.pk)

    form = SeguimientoCreditoForm(request.POST or None, decision=decision)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Bloqueo lógico del registro de decisión y comprobación de unicidad.
            decision_bloqueada = DecisionCredito.objects.select_for_update().get(pk=decision.pk)
            if SeguimientoCredito.objects.filter(decision=decision_bloqueada).exists():
                messages.error(request, 'La decisión ya cuenta con un seguimiento.')
                return redirect('consulta_scoring_app:evaluacion_detalle', pk=pk)
            seguimiento = form.save(commit=False)
            seguimiento.decision = decision_bloqueada
            seguimiento.creado_por = request.user
            seguimiento.actualizado_por = request.user
            seguimiento.full_clean()
            seguimiento.save()
            registrar_evento(
                request.user, EventoAuditoria.Accion.SEGUIMIENTO_CREADO,
                recurso='seguimiento', objeto_id=seguimiento.pk,
                detalle=f'Simulado; estado={seguimiento.estado}',
            )
        messages.success(request, 'Seguimiento ficticio registrado correctamente.')
        return redirect('consulta_scoring_app:seguimiento_detalle', pk=seguimiento.pk)
    return render(request, 'seguimientos/formulario.html', {
        'form': form, 'evaluacion': evaluacion, 'decision': decision,
        'modo': 'crear',
    })


@login_required
def seguimiento_detalle(request, pk):
    exigir_permiso(request, puede_consultar(request.user), recurso='seguimiento', objeto_id=pk)
    seguimiento = obtener_visible_o_404(
        request, seguimientos_visibles(request.user), 'seguimiento', pk,
    )
    registrar_evento(
        request.user, EventoAuditoria.Accion.SEGUIMIENTO_CONSULTADO,
        recurso='seguimiento', objeto_id=seguimiento.pk,
    )
    return render(request, 'seguimientos/detalle.html', {
        'seguimiento': seguimiento,
        'puede_actualizar': puede_decidir(request.user),
    })


@login_required
def seguimiento_actualizar(request, pk):
    exigir_permiso(request, puede_decidir(request.user), recurso='seguimiento', objeto_id=pk)
    seguimiento = obtener_visible_o_404(
        request, seguimientos_visibles(request.user), 'seguimiento', pk,
    )
    if request.method == 'POST':
        with transaction.atomic():
            actual = SeguimientoCredito.objects.select_for_update().get(pk=seguimiento.pk)
            anterior = {
                'estado': actual.estado,
                'fecha_observacion': actual.fecha_observacion,
                'max_dias_mora': actual.max_dias_mora,
                'observaciones': actual.observaciones,
            }
            form = SeguimientoCreditoForm(
                request.POST, instance=actual, decision=actual.decision,
            )
            if form.is_valid():
                modificado = form.save(commit=False)
                campos = ['estado', 'fecha_observacion', 'max_dias_mora', 'observaciones']
                cambiados = [campo for campo in campos
                             if getattr(modificado, campo) != anterior[campo]]
                if cambiados:
                    modificado.actualizado_por = request.user
                    modificado.full_clean()
                    modificado.save()
                    registrar_evento(
                        request.user, EventoAuditoria.Accion.SEGUIMIENTO_ACTUALIZADO,
                        recurso='seguimiento', objeto_id=modificado.pk,
                        detalle=(
                            f'Campos: {",".join(cambiados)}; '
                            f'estado {anterior["estado"]}->{modificado.estado}; '
                            f'mora_max {anterior["max_dias_mora"]}->{modificado.max_dias_mora}'
                        ),
                    )
                    messages.success(request, 'Seguimiento actualizado y auditado.')
                else:
                    messages.info(request, 'No se registraron cambios.')
                return redirect('consulta_scoring_app:seguimiento_detalle', pk=pk)
    else:
        form = SeguimientoCreditoForm(instance=seguimiento, decision=seguimiento.decision)
    return render(request, 'seguimientos/formulario.html', {
        'form': form, 'evaluacion': seguimiento.decision.evaluacion,
        'decision': seguimiento.decision, 'modo': 'actualizar',
        'seguimiento': seguimiento,
    })


# ---- Módulo 4: indicadores operativos y ficha de validación ----

@login_required
def indicadores(request):
    """Operación histórica del prototipo y evidencia verificable del modelo.

    Las cifras operativas usan siempre el queryset autorizado del usuario;
    los seguimientos ficticios NO alimentan la evaluación del modelo.
    """
    exigir_permiso(request, puede_consultar(request.user), recurso='indicadores')
    operaciones = obtener_indicadores_operativos(evaluaciones_visibles(request.user))
    reporte, reporte_error = leer_reporte_validacion()
    registrar_evento(
        request.user, EventoAuditoria.Accion.INDICADORES_CONSULTADOS, recurso='indicadores',
    )
    return render(request, 'indicadores/panel.html', {
        'operaciones': operaciones,
        'reporte': reporte, 'reporte_error': reporte_error,
        'vista_global': request.user.is_superuser or puede_consultar_todos(request.user),
    })
