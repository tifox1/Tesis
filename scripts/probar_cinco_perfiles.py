"""Ejecuta cinco casos contra el MISMO motor que utiliza la aplicación.

No consulta ni modifica la base de datos; los casos son inventados y no son
observaciones de morosidad ni validación estadística del modelo.

Ejecución desde la raíz del proyecto:
    python scripts/probar_cinco_perfiles.py
    python scripts/probar_cinco_perfiles.py --salida resultados_perfiles.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scoring.settings')

# Las funciones ya existentes requieren django.conf.settings para las rutas.
import django
django.setup()

from consulta_scoring_app.services.scoring_service import evaluar
from consulta_scoring_app.services.credit_rules import evaluar_productos


def ejecutar():
    casos = json.loads((ROOT / 'scripts' / 'perfiles_ficticios.json').read_text(encoding='utf-8'))
    resultados = []
    for caso in casos:
        datos = caso['datos']
        calculo = evaluar(datos)
        reglas = evaluar_productos(
            score=calculo['score'], edad=datos['edad'],
            ingreso_gs=datos['ingreso_mensual_bruto_gs'],
            dti=datos['relacion_deuda_ingreso'],
        )
        resultados.append({
            'perfil': caso['nombre'],
            'descripcion': caso['descripcion'],
            'entradas': datos,
            'pd_estimada': round(calculo['pd'], 6),
            'score': round(calculo['score'], 2),
            'banda': reglas['banda'],
            'cuota_maxima_estimada_gs': round(reglas['capacidad']['cuota_nueva_maxima_gs'], 2),
            'ofertas': [o['codigo'] for o in reglas['ofertas']],
            'advertencias': calculo['advertencias'],
        })
    return resultados


def main():
    parser = argparse.ArgumentParser(description='Demostración de cinco perfiles ficticios')
    parser.add_argument('--salida', type=Path, help='Generar JSON con las entradas y salidas calculadas')
    args = parser.parse_args()
    resultados = ejecutar()
    print('DEMOSTRACIÓN FICTICIA: predicciones, no créditos reales ni validación del modelo')
    print(f'{"Perfil":37} {"PD":>8} {"Score":>8} {"Banda":>6} {"Ofertas":>7}')
    for r in resultados:
        print(f'{r["perfil"]:37} {r["pd_estimada"]:8.4f} {r["score"]:8.2f} '
              f'{r["banda"]:>6} {len(r["ofertas"]):7}')
    if args.salida:
        args.salida.parent.mkdir(parents=True,exist_ok=True)
        args.salida.write_text(json.dumps(resultados,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(f'Resultados guardados en: {args.salida}')

if __name__ == '__main__':
    main()
