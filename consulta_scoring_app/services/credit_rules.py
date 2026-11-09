"""Reglas de negocio del prototipo crediticio.

Este módulo NO entrena ni modifica el modelo de machine learning.
Recibe score y datos económicos ya validados y devuelve una recomendación
preliminar de productos para apoyar al analista.

Los valores de tasas, montos, carga financiera y edad son supuestos fijos del
prototipo académico. No representan la política de una entidad real.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


# -------------------------
# Políticas fijas del prototipo
# -------------------------
CARGA_FINANCIERA_MAXIMA = 0.40
EDAD_MAXIMA_VENCIMIENTO = 75

# Referencia regulatoria usada durante el diseño del prototipo.
# BCP - límite para moneda nacional, octubre de 2026: 27,26 % efectiva anual.
# No se actualiza automáticamente: antes de un uso real debería revisarse.
TASA_USURARIA_REFERENCIA = 0.2726
TASA_USURARIA_REFERENCIA_PERIODO = "Octubre 2026"

PLAZOS_DISPONIBLES = (12, 24, 36, 48)

PRODUCTOS = {
    "preferencial": {
        "nombre": "Crédito Preferencial",
        "bandas": ("A",),
        "tasa_anual": 0.16,
        "plazo_maximo": 48,
        "monto_maximo": 80_000_000,
    },
    "estandar": {
        "nombre": "Crédito Estándar",
        "bandas": ("A", "B"),
        "tasa_anual": 0.19,
        "plazo_maximo": 36,
        "monto_maximo": 40_000_000,
    },
    "basico": {
        "nombre": "Crédito Básico",
        "bandas": ("A", "B", "C"),
        "tasa_anual": 0.23,
        "plazo_maximo": 24,
        "monto_maximo": 15_000_000,
    },
}


BANDAS = (
    (638, "A", "Riesgo bajo"),
    (615, "B", "Riesgo moderado"),
    (577, "C", "Riesgo elevado"),
    (float("-inf"), "D", "Riesgo muy elevado"),
)


@dataclass(frozen=True)
class BandaRiesgo:
    codigo: str
    descripcion: str


def obtener_banda(score: float) -> BandaRiesgo:
    """Convierte el score a la banda de riesgo definida para el prototipo."""
    score = float(score)
    for minimo, codigo, descripcion in BANDAS:
        if score >= minimo:
            return BandaRiesgo(codigo=codigo, descripcion=descripcion)
    raise RuntimeError("No se pudo asignar una banda de riesgo.")


def calcular_capacidad_pago(ingreso_gs: float, dti: float) -> dict:
    """Estima la capacidad para una NUEVA cuota mensual.

    DTI se utiliza como aproximación de la carga financiera existente:
        carga_existente ~= ingreso * DTI

    Política simulada del prototipo:
        carga financiera total máxima = 40 % del ingreso bruto.
    """
    ingreso_gs = float(ingreso_gs)
    dti = float(dti)

    if not isfinite(ingreso_gs) or ingreso_gs <= 0:
        raise ValueError("El ingreso debe ser mayor que cero.")
    if not isfinite(dti) or dti < 0:
        raise ValueError("El DTI no puede ser negativo.")

    carga_existente = ingreso_gs * dti
    carga_maxima = ingreso_gs * CARGA_FINANCIERA_MAXIMA
    cuota_nueva_maxima = max(0.0, carga_maxima - carga_existente)

    return {
        "ingreso_gs": ingreso_gs,
        "dti": dti,
        "carga_existente_estimada_gs": carga_existente,
        "carga_maxima_gs": carga_maxima,
        "cuota_nueva_maxima_gs": cuota_nueva_maxima,
        "carga_financiera_maxima": CARGA_FINANCIERA_MAXIMA,
    }


def tasa_mensual_efectiva(tasa_anual: float) -> float:
    tasa_anual = float(tasa_anual)
    if tasa_anual < 0:
        raise ValueError("La tasa anual no puede ser negativa.")
    return (1 + tasa_anual) ** (1 / 12) - 1


def monto_desde_cuota(cuota: float, tasa_anual: float, meses: int) -> float:
    """Valor presente de una anualidad de cuotas constantes."""
    cuota = float(cuota)
    meses = int(meses)
    if cuota <= 0 or meses <= 0:
        return 0.0

    i = tasa_mensual_efectiva(tasa_anual)
    if i == 0:
        return cuota * meses
    return cuota * ((1 - (1 + i) ** (-meses)) / i)


def cuota_desde_monto(monto: float, tasa_anual: float, meses: int) -> float:
    """Cuota mensual estimada para el monto finalmente preaprobado."""
    monto = float(monto)
    meses = int(meses)
    if monto <= 0 or meses <= 0:
        return 0.0

    i = tasa_mensual_efectiva(tasa_anual)
    if i == 0:
        return monto / meses
    return monto * i / (1 - (1 + i) ** (-meses))


def obtener_plazo_permitido(edad: int, plazo_maximo: int) -> int | None:
    """Mayor plazo estándar que no supera los 75 años al vencimiento."""
    edad = int(edad)
    plazo_maximo = int(plazo_maximo)

    posibles = [
        meses
        for meses in PLAZOS_DISPONIBLES
        if meses <= plazo_maximo
        and edad + (meses / 12) <= EDAD_MAXIMA_VENCIMIENTO
    ]
    return max(posibles) if posibles else None


def evaluar_productos(*, score: float, edad: int, ingreso_gs: float, dti: float) -> dict:
    """Aplica banda, capacidad, edad, productos y referencia regulatoria."""
    banda = obtener_banda(score)
    capacidad = calcular_capacidad_pago(ingreso_gs, dti)

    if banda.codigo == "D":
        return {
            "banda": banda.codigo,
            "nivel_riesgo": banda.descripcion,
            "capacidad": capacidad,
            "ofertas": [],
            "motivo_sin_oferta": "La banda D no tiene productos habilitados en este prototipo.",
        }

    if capacidad["cuota_nueva_maxima_gs"] <= 0:
        return {
            "banda": banda.codigo,
            "nivel_riesgo": banda.descripcion,
            "capacidad": capacidad,
            "ofertas": [],
            "motivo_sin_oferta": (
                "La carga financiera estimada ya alcanza o supera el 40 % del ingreso bruto."
            ),
        }

    ofertas = []
    excluidos_por_edad = 0

    for codigo, producto in PRODUCTOS.items():
        if banda.codigo not in producto["bandas"]:
            continue

        # Regla regulatoria mínima del prototipo: no ofrecer una tasa por encima
        # de la referencia usuraria utilizada en el diseño.
        if producto["tasa_anual"] > TASA_USURARIA_REFERENCIA:
            continue

        plazo = obtener_plazo_permitido(edad, producto["plazo_maximo"])
        if plazo is None:
            excluidos_por_edad += 1
            continue

        cuota_maxima = capacidad["cuota_nueva_maxima_gs"]
        monto_capacidad = monto_desde_cuota(
            cuota_maxima,
            producto["tasa_anual"],
            plazo,
        )
        monto_preaprobado = min(monto_capacidad, float(producto["monto_maximo"]))
        cuota_estimada = cuota_desde_monto(
            monto_preaprobado,
            producto["tasa_anual"],
            plazo,
        )
        total_estimado = cuota_estimada * plazo

        ofertas.append({
            "codigo": codigo,
            "producto": producto["nombre"],
            "tasa_anual": float(producto["tasa_anual"]),
            "tasa_anual_pct": float(producto["tasa_anual"]) * 100,
            "plazo_meses": plazo,
            "edad_al_vencimiento": edad + plazo / 12,
            "monto_maximo_producto_gs": float(producto["monto_maximo"]),
            "monto_por_capacidad_gs": monto_capacidad,
            "monto_preaprobado_gs": monto_preaprobado,
            "cuota_estimada_gs": cuota_estimada,
            "total_estimado_cuotas_gs": total_estimado,
        })

    motivo = ""
    if not ofertas:
        if excluidos_por_edad:
            motivo = (
                f"No existe un plazo estándar compatible con la edad máxima al vencimiento "
                f"de {EDAD_MAXIMA_VENCIMIENTO} años."
            )
        else:
            motivo = "No existe un producto compatible con las reglas del prototipo."

    return {
        "banda": banda.codigo,
        "nivel_riesgo": banda.descripcion,
        "capacidad": capacidad,
        "ofertas": ofertas,
        "motivo_sin_oferta": motivo,
    }
