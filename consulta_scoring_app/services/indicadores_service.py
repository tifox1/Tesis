"""Indicadores reproducibles. Separar operaciones SIMULADAS de validación predictiva.

No importar ni ejecutar el .joblib ni entrenar modelos al abrir el panel.
"""
import json
import math
from datetime import date
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone

from ..models import DecisionCredito


def obtener_indicadores_operativos(evaluaciones):
    """Agregaciones SQL sobre TODAS las evaluaciones visibles, sin límite de 100.

    Cuentas por estado se basan en decisiones humanas simuladas, no en
    recomendaciones, productos ofrecidos ni créditos desembolsados.
    """
    totales = evaluaciones.aggregate(
        total=Count('id'), promedio_score=Avg('score'), promedio_pd=Avg('pd'),
        con_decision=Count('decision_crediticia'),
    )
    total = totales['total'] or 0
    con_decision = totales['con_decision'] or 0
    bandas_raw = dict(evaluaciones.values_list('banda').annotate(cantidad=Count('id')))
    bandas = [
        {'codigo': codigo, 'cantidad': bandas_raw.pop(codigo, 0)}
        for codigo in ('A', 'B', 'C', 'D')
    ]
    sin_banda = sum(bandas_raw.values())
    if sin_banda:
        bandas.append({'codigo': 'Sin banda', 'cantidad': sin_banda})

    decisiones_raw = dict(
        DecisionCredito.objects.filter(evaluacion__in=evaluaciones)
        .values_list('estado').annotate(cantidad=Count('id'))
    )
    decisiones = [
        {'codigo': codigo, 'nombre': nombre, 'cantidad': decisiones_raw.get(codigo, 0)}
        for codigo, nombre in DecisionCredito.Estado.choices
    ]
    # Se consideran pendientes las evaluaciones sin decisión registrada.
    decisiones.insert(0, {
        'codigo': 'PENDIENTE', 'nombre': 'Sin decisión registrada',
        'cantidad': max(0, total - con_decision),
    })
    return {
        'total': total, 'promedio_score': totales['promedio_score'],
        'promedio_pd_pct': (totales['promedio_pd'] * 100
                             if totales['promedio_pd'] is not None else None),
        'con_decision': con_decision, 'pendientes': max(0, total - con_decision),
        'bandas': bandas, 'decisiones': decisiones,
    }


class ReporteInvalido(ValueError):
    pass


def _numero_optional(doc, nombre, minimo, maximo):
    v = doc.get(nombre)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ReporteInvalido(f'{nombre}: valor numérico inválido')
    if not minimo <= v <= maximo:
        raise ReporteInvalido(f'{nombre}: fuera de rango [{minimo}, {maximo}]')
    return float(v)


def validar_reporte(doc):
    """Exigir procedencia antes de mostrar indicadores externos como evidencia.

    El reporte es un artefacto exportado por el investigador, no datos de cartera.
    """
    if not isinstance(doc, dict):
        raise ReporteInvalido('El reporte debe ser un objeto JSON')
    for nombre in ('modelo_version', 'dataset', 'particion', 'definicion_evento',
                   'fecha_validacion'):
        if not isinstance(doc.get(nombre), str) or not doc[nombre].strip():
            raise ReporteInvalido(f'Falta procedencia: {nombre}')
        if len(doc[nombre]) > 240:
            raise ReporteInvalido(f'{nombre}: texto demasiado largo')
    try:
        date.fromisoformat(doc['fecha_validacion'])
    except ValueError as e:
        raise ReporteInvalido('fecha_validacion debe usar AAAA-MM-DD') from e
    n = doc.get('muestra_n')
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ReporteInvalido('muestra_n debe ser un entero positivo')
    if n > 100_000_000:
        raise ReporteInvalido('muestra_n fuera de rango razonable')
    metricas = {
        'auc_roc': _numero_optional(doc, 'auc_roc', 0, 1),
        'gini': _numero_optional(doc, 'gini', -1, 1),
        'ks': _numero_optional(doc, 'ks', 0, 1),
        'brier': _numero_optional(doc, 'brier', 0, 1),
    }
    if all(v is None for v in metricas.values()):
        raise ReporteInvalido('Se requiere al menos una métrica verificada')
    if metricas['auc_roc'] is not None and metricas['gini'] is not None:
        if abs(metricas['gini'] - (2 * metricas['auc_roc'] - 1)) > .005:
            raise ReporteInvalido('Gini y AUC-ROC no son consistentes')
    return {
        'modelo_version': doc['modelo_version'],
        'dataset': doc['dataset'], 'particion': doc['particion'],
        'definicion_evento': doc['definicion_evento'],
        'fecha_validacion': doc['fecha_validacion'], 'muestra_n': n,
        **metricas,
    }


def leer_reporte_validacion():
    ruta = Path(settings.MODEL_VALIDATION_REPORT_PATH)
    if not ruta.exists():
        return None, None
    try:
        if not ruta.is_file() or ruta.stat().st_size > 100_000:
            raise ReporteInvalido('Tamaño o tipo de archivo no permitido')
        with ruta.open(encoding='utf-8') as f:
            datos = json.load(f)
        return validar_reporte(datos), None
    except (OSError, ValueError, TypeError) as e:
        # No mostrar valores no verificables como métricas válidas.
        return None, f'El reporte de validación no se pudo utilizar: {e}'
