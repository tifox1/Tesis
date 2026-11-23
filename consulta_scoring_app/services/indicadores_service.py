"""Indicadores reproducibles. Separar operaciones SIMULADAS de validación predictiva.

No importar ni ejecutar el .joblib ni entrenar modelos al abrir el panel.
"""
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from ..models import DecisionCredito, Solicitante


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


# Gráficos descriptivos: nunca se utilizan para validar el modelo predictivo.
_GRUPOS_EDAD = (
    ('18–24', 18, 24), ('25–34', 25, 34), ('35–44', 35, 44),
    ('45–54', 45, 54), ('55–64', 55, 64), ('65 o más', 65, 120),
)
_RANGOS_SCORE = (
    ('300–399', 300, 400), ('400–499', 400, 500), ('500–599', 500, 600),
    ('600–699', 600, 700), ('700–799', 700, 800), ('800–850', 800, 851),
)
_MESES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def _barras(rows, valor='cantidad'):
    """Añadir anchuras porcentuales relativas al máximo de la misma serie."""
    maximo = max((fila[valor] for fila in rows), default=0)
    for fila in rows:
        fila['ancho'] = (fila[valor] / maximo * 100) if maximo else 0
    return rows


def _edad_en_fecha(fecha_nacimiento, fecha_evaluacion):
    return (fecha_evaluacion.year - fecha_nacimiento.year
            - ((fecha_evaluacion.month, fecha_evaluacion.day) <
               (fecha_nacimiento.month, fecha_nacimiento.day)))


def obtener_graficos_descriptivos(evaluaciones):
    """Gráficos de evaluaciones autorizadas y perfiles únicos (última evaluación).

    No consulta evaluaciones ajenas, no reentrena y no interpreta las simulaciones
    como desempeño predictivo observado. Excluye históricos sin ficha del perfil.
    """
    # Los rangos de score y el número de ofertas corresponden a EVALUACIONES.
    score_counts = Counter()
    ofertas_counts = Counter()
    perfiles = {}
    filas = (evaluaciones.order_by('-fecha_hora', '-pk')
             .values_list('solicitante_id', 'solicitante__fecha_nacimiento',
                          'solicitante__situacion_laboral', 'solicitante__ciudad',
                          'score', 'fecha_hora', 'ofertas')
             .iterator(chunk_size=2000))
    for pk_solicitante, nacimiento, empleo, ciudad, score, fecha_hora, ofertas in filas:
        for label, minimo, maximo_excl in _RANGOS_SCORE:
            if minimo <= score < maximo_excl:
                score_counts[label] += 1
                break
        else:
            score_counts['Fuera de escala'] += 1
        n_ofertas = len(ofertas) if isinstance(ofertas, list) else 0
        ofertas_counts[n_ofertas if n_ofertas <= 3 else '4 o más'] += 1
        # La ordenación garantiza que solo queda la última evaluación visible
        # de cada persona, evitando sobrecontar a quienes se evalúan varias veces.
        if pk_solicitante is not None and pk_solicitante not in perfiles:
            fecha_local = timezone.localtime(fecha_hora).date()
            perfiles[pk_solicitante] = (
                _edad_en_fecha(nacimiento, fecha_local) if nacimiento else None,
                empleo, (ciudad or '').strip(), float(score),
            )

    rangos = [dict(etiqueta=label, cantidad=score_counts[label])
              for label, _, _ in _RANGOS_SCORE]
    if score_counts['Fuera de escala']:
        rangos.append(dict(etiqueta='Fuera de escala', cantidad=score_counts['Fuera de escala']))
    _barras(rangos)

    ofertas_rows = [dict(etiqueta=str(i), cantidad=ofertas_counts[i]) for i in range(4)]
    if ofertas_counts['4 o más']:
        ofertas_rows.append(dict(etiqueta='4 o más', cantidad=ofertas_counts['4 o más']))
    _barras(ofertas_rows)

    edades_conteo = Counter()
    edades_score = defaultdict(list)
    empleo_conteo = Counter()
    ciudades_conteo = Counter()
    etiquetas_empleo = dict(Solicitante.SituacionLaboral.choices)
    for edad, empleo, ciudad, score in perfiles.values():
        ciudades_conteo[ciudad or 'No informada'] += 1
        empleo_conteo[etiquetas_empleo.get(empleo, 'No informada')] += 1
        if edad is None:
            continue
        for label, minimo, maximo in _GRUPOS_EDAD:
            if minimo <= edad <= maximo:
                edades_conteo[label] += 1
                edades_score[label].append(score)
                break

    edades = [dict(etiqueta=label, cantidad=edades_conteo[label])
             for label, _, _ in _GRUPOS_EDAD]
    _barras(edades)
    score_por_edad = []
    for label, _, _ in _GRUPOS_EDAD:
        valores = edades_score[label]
        if not valores:
            continue
        media = sum(valores) / len(valores)
        score_por_edad.append({
            'etiqueta': label, 'cantidad': len(valores), 'promedio': media,
            # La barra representa la escala declarada, 300 a 850 puntos.
            'ancho': max(0, min(100, (media - 300) / 550 * 100)),
        })

    situaciones = [dict(etiqueta=nombre, cantidad=cantidad)
                   for nombre, cantidad in empleo_conteo.most_common()]
    _barras(situaciones)
    ciudades = [dict(etiqueta=nombre, cantidad=cantidad)
                for nombre, cantidad in ciudades_conteo.most_common(6)]
    otros = sum(ciudades_conteo.values()) - sum(fila['cantidad'] for fila in ciudades)
    if otros:
        ciudades.append(dict(etiqueta='Otras ciudades', cantidad=otros))
    _barras(ciudades)

    # Evolución temporal: últimos 12 meses calendario, contando evaluaciones.
    hoy = timezone.localdate()
    mes_inicio = date(hoy.year, hoy.month, 1)
    meses = []
    for _ in range(12):
        meses.append(mes_inicio)
        mes_inicio = (mes_inicio - timedelta(days=1)).replace(day=1)
    meses.reverse()
    datos_mes = (evaluaciones.filter(fecha_hora__date__gte=meses[0])
                 .annotate(mes=TruncMonth('fecha_hora'))
                 .values('mes').annotate(total=Count('id')).order_by('mes'))
    mes_cantidad = {(item['mes'].year, item['mes'].month): item['total']
                    for item in datos_mes if item['mes'] is not None}
    evolucion = [dict(etiqueta=f'{_MESES[mes.month - 1]} {mes.year}',
                      cantidad=mes_cantidad.get((mes.year, mes.month), 0))
                 for mes in meses]
    _barras(evolucion)

    return {
        'rangos_score': rangos, 'ofertas': ofertas_rows,
        'edades': edades, 'score_por_edad': score_por_edad,
        'situaciones': situaciones, 'ciudades': ciudades, 'evolucion': evolucion,
        'personas': len(perfiles),
        'sin_ficha': evaluaciones.filter(solicitante__isnull=True).count(),
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
