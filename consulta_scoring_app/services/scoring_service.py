"""Servicio de inferencia del modelo de credit scoring.

Responsabilidad de este módulo:
- adaptar el ingreso cargado en guaraníes a la escala monetaria asumida por el modelo;
- ejecutar el artefacto .joblib;
- calcular PD y score;
- advertir valores atípicos respecto del conjunto de entrenamiento.

No decide productos, montos, plazos ni aprobación comercial.
"""

import json
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
from django.conf import settings


# Supuesto operacional fijo del prototipo. La documentación de Give Me Some
# Credit no especifica de forma explícita la moneda de MonthlyIncome; para la
# adaptación paraguaya se asume una unidad de referencia equivalente a USD.
# No es una cotización oficial ni se actualiza automáticamente.
TIPO_CAMBIO_REFERENCIA_GS = 7_500.0


@lru_cache(maxsize=1)
def cargar_artefacto():
    artifact = joblib.load(settings.MODEL_PATH)
    required = {'model', 'features', 'base_score', 'base_odds', 'pdo'}
    missing = required.difference(artifact)
    if missing:
        raise ValueError(f'Artefacto incompleto. Faltan: {sorted(missing)}')
    return artifact


@lru_cache(maxsize=1)
def cargar_limites():
    if not settings.FEATURE_BOUNDS_PATH.exists():
        return {}
    with open(settings.FEATURE_BOUNDS_PATH, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def pd_a_score(pd_value, artifact):
    pd_value = float(np.clip(pd_value, 1e-6, 1 - 1e-6))
    odds = (1 - pd_value) / pd_value
    score = artifact['base_score'] + artifact['pdo'] * np.log2(odds / artifact['base_odds'])
    return float(np.clip(score, 300, 850))


def normalizar_entrada(datos):
    """Transforma la entrada operativa del formulario a las features del .joblib."""
    ingreso_gs = float(datos['ingreso_mensual_bruto_gs'])
    ingreso_modelo = ingreso_gs / TIPO_CAMBIO_REFERENCIA_GS

    return {
        'edad': int(datos['edad']),
        # Se conserva el nombre técnico heredado del artefacto.
        'ingreso_neto_mensual': ingreso_modelo,
        'relacion_deuda_ingreso': float(datos['relacion_deuda_ingreso']),
        'utilizacion_lineas': float(datos['utilizacion_lineas']),
        'atraso_30_59': int(datos['atraso_30_59']),
        'atraso_60_89': int(datos['atraso_60_89']),
        'atraso_90_plus': int(datos['atraso_90_plus']),
        'cantidad_creditos_activos': int(datos['cantidad_creditos_activos']),
        'creditos_inmobiliarios': int(datos['creditos_inmobiliarios']),
        'dependientes': int(datos['dependientes']),
    }


def auditar_entrada(datos_modelo):
    warnings = []
    bounds = cargar_limites()
    for feature, value in datos_modelo.items():
        if value is None or feature not in bounds:
            continue
        p01 = bounds[feature].get('p01')
        p99 = bounds[feature].get('p99')
        if p01 is not None and p99 is not None and (value < p01 or value > p99):
            warnings.append(
                f'{feature}: {value:.3f} está fuera del rango P01–P99 del entrenamiento '
                f'({p01:.3f}–{p99:.3f}). Verifique el dato de origen.'
            )
    return warnings


def evaluar(datos):
    artifact = cargar_artefacto()
    features = artifact['features']
    datos_modelo = normalizar_entrada(datos)

    faltantes = [feature for feature in features if feature not in datos_modelo]
    if faltantes:
        raise ValueError(f'Faltan variables requeridas por el modelo: {faltantes}')

    row = {feature: datos_modelo[feature] for feature in features}
    frame = pd.DataFrame([row], columns=features)

    pd_value = float(artifact['model'].predict_proba(frame)[:, 1][0])
    score = pd_a_score(pd_value, artifact)

    return {
        'pd': pd_value,
        'score': score,
        'advertencias': auditar_entrada(row),
        'features_modelo': row,
        'ingreso_modelo': row['ingreso_neto_mensual'],
        'tipo_cambio_referencia_gs': TIPO_CAMBIO_REFERENCIA_GS,
    }
