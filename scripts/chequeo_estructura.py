"""Control estructural sin Django: sintaxis, migraciones, rutas y archivos.

No sustituye `manage.py check`, `migrate --check` o el test funcional Django.
"""
import ast
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'consulta_scoring_app'
ERRORES = []


def verificar(condicion, descripcion):
    print(('OK' if condicion else 'ERROR') + ' | ' + descripcion)
    if not condicion:
        ERRORES.append(descripcion)


def ejecutar():
    python_files = list(ROOT.rglob('*.py'))
    for ruta in python_files:
        try:
            ast.parse(ruta.read_text(encoding='utf-8'), filename=str(ruta))
        except Exception as exc:
            ERRORES.append(f'Sintaxis: {ruta.relative_to(ROOT)}: {exc}')
    verificar(not any(e.startswith('Sintaxis:') for e in ERRORES),
              f'Sintaxis Python ({len(python_files)} archivos)')

    migrations = APP / 'migrations'
    for i in range(1,7):
        verificar(bool(list(migrations.glob(f'{i:04d}_*.py'))), f'Migración {i:04d}')

    urls_file = (APP / 'urls.py').read_text(encoding='utf-8')
    nombres = set(re.findall(r"name=['\"]([^'\"]+)['\"]", urls_file))
    nombres.update(('login', 'logout'))
    refs = set()
    for t in (APP / 'templates').rglob('*.html'):
        refs.update(re.findall(r"\{%\s*url\s+['\"](?:consulta_scoring_app:)?([^'\"]+)['\"]",t.read_text(encoding='utf-8')))
    verificar(not (refs - nombres),f'Referencias URL en plantillas ({len(refs)} nombres; faltantes={sorted(refs-nombres)})')

    for archivo in ('artifacts/credit_score_modelo_final.joblib',
                    'artifacts/feature_bounds.json','scripts/perfiles_ficticios.json',
                    'requirements.txt'):
        verificar((ROOT/archivo).is_file(), f'Archivo requerido: {archivo}')
    verificar(importlib.util.find_spec('django') is not None, 'Django instalado (necesario para pruebas integrales)')
    print(f'\nTotal de incidencias: {len(ERRORES)}')
    return 1 if ERRORES else 0

if __name__ == '__main__':
    sys.exit(ejecutar())
