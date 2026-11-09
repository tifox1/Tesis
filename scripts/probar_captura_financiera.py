"""Comprobación rápida de las fórmulas; no reemplaza los tests de Django."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from consulta_scoring_app.services.captura_financiera import calcular_indicadores


def main():
    resultado = calcular_indicadores(
        ingreso_gs=10_000_000,
        cuota_hipotecaria_gs=1_600_000,
        cuota_prestamos_personales_gs=700_000,
        pago_mensual_tarjetas_gs=200_000,
        saldo_lineas_utilizado_gs=4_000_000,
        limite_lineas_total_gs=10_000_000,
    )
    assert resultado['relacion_deuda_ingreso'] == 0.25, resultado
    assert resultado['utilizacion_lineas'] == 0.4, resultado
    assert resultado['total_cuotas_mensuales_gs'] == 2_500_000, resultado
    print('OK - DTI=0.25, utilización=0.40, pagos mensuales=2.500.000 Gs.')


if __name__ == '__main__':
    main()
