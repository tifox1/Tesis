"""Cálculo de indicadores derivados de datos declarados, sin inferencia ML.

No verifica documentalmente las cifras ni altera las políticas crediticias.
"""
from decimal import Decimal, ROUND_HALF_UP


DECIMALES = Decimal('0.000001')


def calcular_indicadores(*, ingreso_gs, cuota_hipotecaria_gs,
                         cuota_prestamos_personales_gs, pago_mensual_tarjetas_gs,
                         saldo_lineas_utilizado_gs, limite_lineas_total_gs):
    """Devuelve DTI y utilización expresados como proporciones (0.25 == 25%).

    Los pagos mensuales no son saldos de deuda. La utilización compara únicamente
    saldos/límites de las líneas revolventes declaradas, no el saldo hipotecario.
    """
    valores = {
        'ingreso_gs': ingreso_gs,
        'cuota_hipotecaria_gs': cuota_hipotecaria_gs,
        'cuota_prestamos_personales_gs': cuota_prestamos_personales_gs,
        'pago_mensual_tarjetas_gs': pago_mensual_tarjetas_gs,
        'saldo_lineas_utilizado_gs': saldo_lineas_utilizado_gs,
        'limite_lineas_total_gs': limite_lineas_total_gs,
    }
    if any(v is None for v in valores.values()):
        raise ValueError('Faltan datos para calcular los indicadores financieros.')
    if any(v < 0 for v in valores.values()):
        raise ValueError('Los importes financieros no pueden ser negativos.')
    if ingreso_gs <= 0:
        raise ValueError('El ingreso debe ser mayor a cero.')
    if limite_lineas_total_gs == 0 and saldo_lineas_utilizado_gs > 0:
        raise ValueError('No se puede declarar saldo utilizado sin límite de crédito.')

    total_cuotas = (cuota_hipotecaria_gs + cuota_prestamos_personales_gs
                    + pago_mensual_tarjetas_gs)
    dti = (Decimal(total_cuotas) / Decimal(ingreso_gs)).quantize(DECIMALES, rounding=ROUND_HALF_UP)
    if limite_lineas_total_gs:
        utilizacion = (Decimal(saldo_lineas_utilizado_gs) / Decimal(limite_lineas_total_gs)).quantize(
            DECIMALES, rounding=ROUND_HALF_UP,
        )
    else:
        utilizacion = Decimal('0')
    return {
        'relacion_deuda_ingreso': float(dti),
        'utilizacion_lineas': float(utilizacion),
        'total_cuotas_mensuales_gs': total_cuotas,
    }
