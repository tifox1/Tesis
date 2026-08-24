# import os
# import logging

# import duckdb
# import joblib
# import pandas as pd

# from django.shortcuts import render
# from django.conf import settings

# from .forms import SolicitudCreditoForm

# logger = logging.getLogger(__name__)

# # ── Paths ────────────────────────────────────────────────────────────────────
# # Define these in settings.py or adjust the defaults below.
# DW_PATH    = getattr(settings, "DUCKDB_PATH",   os.path.join(settings.BASE_DIR, "datawarehouse.duckdb"))
# MODEL_PATH = getattr(settings, "MODEL_PATH",    os.path.join(settings.BASE_DIR, "modelo_crediticio.pkl"))

# # ── Columnas exactas que espera el modelo (en el orden correcto) ─────────────
# MODEL_COLUMNS = [
#     "edad",
#     "tipo_vivienda",
#     "antiguedad_vivienda",
#     "situacion_laboral",
#     "antiguedad_laboral",
#     "ingreso_neto_mensual",
#     "total_cuotas_deudas_actuales",
#     "relacion_deuda_ingreso",
#     "score_bruto_actual",
#     "cantidad_creditos_activos",
#     "saldo_deuda",
#     "peor_atraso",
#     "cantidad_cuentas_en_mora",
#     "perfil_riesgo",
# ]

# # ── Query SQL (JOIN entre tablas A y B por cédula) ──────────────────────────
# QUERY_CLIENTE = """
#     SELECT
#         a.total_cuotas_deudas_actuales,
#         b.score_bruto_actual,
#         b.cantidad_creditos_activos,
#         b.saldo_deuda,
#         b.peor_atraso,
#         b.cantidad_cuentas_en_mora,
#         b.perfil_riesgo
#     FROM datos_personales AS a
#     INNER JOIN buro_credito AS b
#         ON a.cedula = b.cedula
#     WHERE a.cedula = ?
#     LIMIT 1
# """


# def _cargar_modelo():
#     """Carga el modelo desde disco. Lanza FileNotFoundError si no existe."""
#     if not os.path.exists(MODEL_PATH):
#         raise FileNotFoundError(f"Modelo no encontrado en: {MODEL_PATH}")
#     return joblib.load(MODEL_PATH)


# def _consultar_duckdb(cedula: str) -> dict | None:
#     """
#     Conecta a DuckDB (read-only), ejecuta el JOIN y devuelve un dict con los
#     campos del cliente, o None si la cédula no existe.
#     """
#     with duckdb.connect(DW_PATH, read_only=True) as con:
#         result = con.execute(QUERY_CLIENTE, [cedula]).fetchone()

#     if result is None:
#         return None

#     return {
#         "total_cuotas_deudas_actuales": result[0],
#         "score_bruto_actual":           result[1],
#         "cantidad_creditos_activos":    result[2],
#         "saldo_deuda":                  result[3],
#         "peor_atraso":                  result[4],
#         "cantidad_cuentas_en_mora":     result[5],
#         "perfil_riesgo":                result[6],
#     }


# def solicitud_credito(request):
#     """
#     Vista principal.
#     GET  → muestra el formulario en blanco.
#     POST → valida, consulta DuckDB, predice y redirige al template de resultado.
#     """
#     form = SolicitudCreditoForm()

#     if request.method == "POST":
#         form = SolicitudCreditoForm(request.POST)

#         if form.is_valid():
#             data = form.cleaned_data
#             cedula = data["cedula"]

#             # ── 1. Consulta DuckDB ───────────────────────────────────────
#             try:
#                 cliente_db = _consultar_duckdb(cedula)
#             except Exception as exc:
#                 logger.exception("Error al conectar con DuckDB")
#                 return render(request, "scoring_app/solicitud.html", {
#                     "form": form,
#                     "error": f"Error al acceder al Data Warehouse: {exc}",
#                 })

#             if cliente_db is None:
#                 return render(request, "scoring_app/solicitud.html", {
#                     "form": form,
#                     "error": f"No se encontró ningún cliente con cédula «{cedula}» en el sistema.",
#                 })

#             # ── 2. Calcular relación deuda / ingreso ─────────────────────
#             ingreso = data["ingreso_neto_mensual"]
#             total_cuotas = cliente_db["total_cuotas_deudas_actuales"]

#             relacion_deuda_ingreso = (
#                 round(total_cuotas / ingreso, 4) if ingreso > 0 else 0.0
#             )

#             # ── 3. Consolidar DataFrame con las 14 variables ─────────────
#             fila = {
#                 # Del formulario
#                 "edad":                       data["edad"],
#                 "tipo_vivienda":              data["tipo_vivienda"],
#                 "antiguedad_vivienda":        data["antiguedad_vivienda"],
#                 "situacion_laboral":          data["situacion_laboral"],
#                 "antiguedad_laboral":         data["antiguedad_laboral"],
#                 "ingreso_neto_mensual":       ingreso,
#                 # Calculada
#                 "relacion_deuda_ingreso":     relacion_deuda_ingreso,
#                 # De DuckDB
#                 "total_cuotas_deudas_actuales": total_cuotas,
#                 "score_bruto_actual":           cliente_db["score_bruto_actual"],
#                 "cantidad_creditos_activos":    cliente_db["cantidad_creditos_activos"],
#                 "saldo_deuda":                  cliente_db["saldo_deuda"],
#                 "peor_atraso":                  cliente_db["peor_atraso"],
#                 "cantidad_cuentas_en_mora":     cliente_db["cantidad_cuentas_en_mora"],
#                 "perfil_riesgo":                cliente_db["perfil_riesgo"],
#             }

#             df = pd.DataFrame([fila], columns=MODEL_COLUMNS)

#             # ── 4. Cargar modelo y predecir ──────────────────────────────
#             try:
#                 modelo = _cargar_modelo()
#                 prediccion      = int(modelo.predict(df)[0])
#                 probabilidades  = modelo.predict_proba(df)[0]
#                 prob_aprobado   = round(float(probabilidades[1]) * 100, 2)
#                 prob_rechazado  = round(float(probabilidades[0]) * 100, 2)
#             except FileNotFoundError as exc:
#                 logger.error(str(exc))
#                 return render(request, "scoring_app/solicitud.html", {
#                     "form": form,
#                     "error": "El modelo de scoring no está disponible. Contacte al administrador.",
#                 })
#             except Exception as exc:
#                 logger.exception("Error al ejecutar el modelo")
#                 return render(request, "scoring_app/solicitud.html", {
#                     "form": form,
#                     "error": f"Error al ejecutar el modelo: {exc}",
#                 })

#             # ── 5. Renderizar resultado ──────────────────────────────────
#             contexto = {
#                 "cedula":                   cedula,
#                 "prediccion":               prediccion,       # 1 = aprobado, 0 = rechazado
#                 "aprobado":                 prediccion == 1,
#                 "prob_aprobado":            prob_aprobado,
#                 "prob_rechazado":           prob_rechazado,
#                 "relacion_deuda_ingreso":   relacion_deuda_ingreso,
#                 "datos_formulario":         data,
#                 "datos_buro":               cliente_db,
#             }
#             return render(request, "scoring_app/resultado.html", contexto)

#     return render(request, "consulta_scoring_app/templates/solicitud.html", {"form": form})

















import os
import logging

import duckdb
import joblib
import pandas as pd

from django.shortcuts import render
from django.conf import settings

from .forms import SolicitudCreditoForm

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
# Se usa 'r' (raw string) para evitar problemas con las barras invertidas (\) en Windows
DW_PATH    = getattr(settings, "DUCKDB_PATH",   r"D:\Archivos\TESIS\db\tesis.db")
MODEL_PATH = getattr(settings, "MODEL_PATH",    r"D:\Archivos\TESIS\rf_modelo.joblib")

# ── Columnas exactas que espera el modelo (en el orden correcto) ─────────────
MODEL_COLUMNS = [
    "edad",
    "tipo_vivienda",
    "antiguedad_vivienda",
    "situacion_laboral",
    "antiguedad_laboral",
    "ingreso_neto_mensual",
    "total_cuotas_deudas_actuales",
    "relacion_deuda_ingreso",
    "score_bruto_actual",
    "cantidad_creditos_activos",
    "saldo_deuda",
    "peor_atraso",
    "cantidad_cuentas_en_mora",
    "perfil_riesgo",
]

# ── Query SQL (Ajustada con LEFT JOIN, nuevas tablas y numero_ci) ───────────
QUERY_CLIENTE = """
    SELECT
        A.total_cuotas_deudas_actuales,
        B.score_bruto_actual,
        B.cantidad_creditos_activos,
        B.saldo_deuda,
        B.peor_atraso,
        B.cantidad_cuentas_en_mora,
        B.perfil_riesgo
    FROM datos_personales A
    LEFT JOIN datos_buro B 
        ON A.numero_ci = B.numero_ci
    WHERE A.numero_ci = ?
    LIMIT 1
"""

def _cargar_modelo():
    """Carga el modelo desde disco. Lanza FileNotFoundError si no existe."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Modelo no encontrado en: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def _consultar_duckdb(cedula: str) -> dict | None:
    """
    Conecta a DuckDB (read-only), ejecuta el JOIN y devuelve un dict con los
    campos del cliente, o None si la cédula no existe.
    """
    with duckdb.connect(DW_PATH, read_only=True) as con:
        result = con.execute(QUERY_CLIENTE, [cedula]).fetchone()

    if result is None:
        return None

    return {
        "total_cuotas_deudas_actuales": result[0],
        "score_bruto_actual":           result[1],
        "cantidad_creditos_activos":    result[2],
        "saldo_deuda":                  result[3],
        "peor_atraso":                  result[4],
        "cantidad_cuentas_en_mora":     result[5],
        "perfil_riesgo":                result[6],
    }


def solicitud_credito(request):
    """
    Vista principal.
    GET  → muestra el formulario en blanco.
    POST → valida, consulta DuckDB, predice y redirige al template de resultado.
    """
    form = SolicitudCreditoForm()

    if request.method == "POST":
        form = SolicitudCreditoForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            cedula = data["cedula"]

            # ── 1. Consulta DuckDB ───────────────────────────────────────
            try:
                cliente_db = _consultar_duckdb(cedula)
            except Exception as exc:
                print(exc)
                logger.exception("Error al conectar con DuckDB")
                return render(request, "solicitud.html", {
                    "form": form,
                    "error": f"Error al acceder al Data Warehouse: {exc}",
                })

            if cliente_db is None:
                return render(request, "solicitud.html", {
                    "form": form,
                    "error": f"No se encontró ningún cliente con cédula «{cedula}» en el sistema.",
                })

            # ── 2. Calcular relación deuda / ingreso ─────────────────────
            ingreso = data["ingreso_neto_mensual"]
            total_cuotas = cliente_db["total_cuotas_deudas_actuales"]

            relacion_deuda_ingreso = (
                round(total_cuotas / ingreso, 4) if ingreso > 0 else 0.0
            )

            # ── 3. Consolidar DataFrame con las 14 variables ─────────────
            fila = {
                # Del formulario
                "edad":                       data["edad"],
                "tipo_vivienda":              data["tipo_vivienda"],
                "antiguedad_vivienda":        data["antiguedad_vivienda"],
                "situacion_laboral":          data["situacion_laboral"],
                "antiguedad_laboral":         data["antiguedad_laboral"],
                "ingreso_neto_mensual":       ingreso,
                # Calculada
                "relacion_deuda_ingreso":     relacion_deuda_ingreso,
                # De DuckDB
                "total_cuotas_deudas_actuales": total_cuotas,
                "score_bruto_actual":           cliente_db["score_bruto_actual"],
                "cantidad_creditos_activos":    cliente_db["cantidad_creditos_activos"],
                "saldo_deuda":                  cliente_db["saldo_deuda"],
                "peor_atraso":                  cliente_db["peor_atraso"],
                "cantidad_cuentas_en_mora":     cliente_db["cantidad_cuentas_en_mora"],
                "perfil_riesgo":                cliente_db["perfil_riesgo"],
            }

            df = pd.DataFrame([fila], columns=MODEL_COLUMNS)

            # ── 4. Cargar modelo y predecir ──────────────────────────────
            try:
                modelo = _cargar_modelo()
                prediccion      = int(modelo.predict(df)[0])
                probabilidades  = modelo.predict_proba(df)[0]
                prob_aprobado   = round(float(probabilidades[1]) * 100, 2)
                prob_rechazado  = round(float(probabilidades[0]) * 100, 2)
            except FileNotFoundError as exc:
                logger.error(str(exc))
                return render(request, "solicitud.html", {
                    "form": form,
                    "error": "El modelo de scoring no está disponible. Contacte al administrador.",
                })
            except Exception as exc:
                logger.exception("Error al ejecutar el modelo")
                return render(request, "solicitud.html", {
                    "form": form,
                    "error": f"Error al ejecutar el modelo: {exc}",
                })

            # ── 5. Renderizar resultado ──────────────────────────────────
            contexto = {
                "cedula":                   cedula,
                "prediccion":               prediccion,       # 1 = aprobado, 0 = rechazado
                "aprobado":                 prediccion == 1,
                "prob_aprobado":            prob_aprobado,
                "prob_rechazado":           prob_rechazado,
                "relacion_deuda_ingreso":   relacion_deuda_ingreso,
                "datos_formulario":         data,
                "datos_buro":               cliente_db,
            }
            return render(request, "resultado.html", contexto)

    # Si es GET, o si el form es inválido (aunque faltaría el else del is_valid para volver a mostrar errores), se renderiza normal
    return render(request, "solicitud.html", {"form": form})
