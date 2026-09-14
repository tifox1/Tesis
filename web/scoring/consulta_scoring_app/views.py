import os
import logging

import duckdb
import joblib
import pandas as pd

from django.shortcuts import render
from django.conf import settings

from .forms import SolicitudCreditoForm
from .classes.credit_engine import MotorDecisionCredito

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
DW_PATH    = getattr(settings, "DUCKDB_PATH", r"D:\Archivos\TESIS\db\tesis.db")
MODEL_PATH = getattr(settings, "MODEL_PATH",  r"D:\Archivos\TESIS\rf_modelo.joblib")

# ── Catálogo de planes de crédito ─────────────────────────────────────────────
CATALOGO_PLANES = {
    "microcredito_express": {
        "nombre":       "Microcrédito Express",
        "score_minimo": 520,
        "tasa_anual":   0.26,
        "monto_min":    500_000,
        "monto_max":    5_000_000,
        "plazo_min":    6,
        "plazo_max":    12,
    },
    "prestamo_personal": {
        "nombre":       "Préstamo Personal Estándar",
        "score_minimo": 620,
        "tasa_anual":   0.22,
        "monto_min":    1_000_000,
        "monto_max":    50_000_000,
        "plazo_min":    6,
        "plazo_max":    36,
    },
    "credito_platino": {
        "nombre":       "Crédito Platino",
        "score_minimo": 700,
        "tasa_anual":   0.16,
        "monto_min":    5_000_000,
        "monto_max":    150_000_000,
        "plazo_min":    12,
        "plazo_max":    60,
    },
}

# ── Columnas exactas que espera el modelo ─────────────────────────────────────
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

# ── Query DuckDB ──────────────────────────────────────────────────────────────
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cargar_modelo():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Modelo no encontrado en: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def _consultar_duckdb(cedula: str) -> dict | None:
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


# ── Vista principal ───────────────────────────────────────────────────────────

def solicitud_credito(request):
    """
    GET  → muestra el formulario vacío.
    POST → valida, consulta DuckDB, predice con el modelo ML,
           corre el motor de decisión y devuelve el resultado completo.
    """
    # Pasamos el catálogo al template para construir el selector de planes
    # y los rangos de validación en JS
    catalogo_json = {
        key: {
            "nombre":    p["nombre"],
            "monto_min": p["monto_min"],
            "monto_max": p["monto_max"],
            "plazo_min": p["plazo_min"],
            "plazo_max": p["plazo_max"],
        }
        for key, p in CATALOGO_PLANES.items()
    }

    form = SolicitudCreditoForm()

    if request.method == "POST":
        form = SolicitudCreditoForm(request.POST)

        if form.is_valid():
            data   = form.cleaned_data
            cedula = data["cedula"]

            # ── 1. Consulta DuckDB ─────────────────────────────────────
            try:
                cliente_db = _consultar_duckdb(cedula)
            except Exception as exc:
                logger.exception("Error al conectar con DuckDB")
                return render(request, "solicitud.html", {
                    "form":          form,
                    "catalogo_json": catalogo_json,
                    "error":         f"Error al acceder al Data Warehouse: {exc}",
                })

            if cliente_db is None:
                return render(request, "solicitud.html", {
                    "form":          form,
                    "catalogo_json": catalogo_json,
                    "error":         f"No se encontró ningún cliente con cédula «{cedula}» en el sistema.",
                })

            # ── 2. Calcular DTI ────────────────────────────────────────
            ingreso      = data["ingreso_neto_mensual"]
            total_cuotas = cliente_db["total_cuotas_deudas_actuales"]
            relacion_deuda_ingreso = (
                round(total_cuotas / ingreso, 4) if ingreso > 0 else 0.0
            )

            # ── 3. Armar DataFrame para el modelo ──────────────────────
            fila = {
                "edad":                         data["edad"],
                "tipo_vivienda":                data["tipo_vivienda"],
                "antiguedad_vivienda":          data["antiguedad_vivienda"],
                "situacion_laboral":            data["situacion_laboral"],
                "antiguedad_laboral":           data["antiguedad_laboral"],
                "ingreso_neto_mensual":         ingreso,
                "relacion_deuda_ingreso":       relacion_deuda_ingreso,
                "total_cuotas_deudas_actuales": total_cuotas,
                "score_bruto_actual":           cliente_db["score_bruto_actual"],
                "cantidad_creditos_activos":    cliente_db["cantidad_creditos_activos"],
                "saldo_deuda":                  cliente_db["saldo_deuda"],
                "peor_atraso":                  cliente_db["peor_atraso"],
                "cantidad_cuentas_en_mora":     cliente_db["cantidad_cuentas_en_mora"],
                "perfil_riesgo":                cliente_db["perfil_riesgo"],
            }
            df = pd.DataFrame([fila], columns=MODEL_COLUMNS)

            # ── 4. Predicción del modelo ML ────────────────────────────
            try:
                modelo         = _cargar_modelo()
                probabilidades = modelo.predict_proba(df)[0]
                pd_valor       = float(probabilidades[1])   # probabilidad de default
                prob_aprobado  = round(float(probabilidades[0]) * 100, 2)
                prob_rechazado = round(pd_valor * 100, 2)
            except FileNotFoundError as exc:
                logger.error(str(exc))
                return render(request, "solicitud.html", {
                    "form":          form,
                    "catalogo_json": catalogo_json,
                    "error":         "El modelo de scoring no está disponible. Contacte al administrador.",
                })
            except Exception as exc:
                logger.exception("Error al ejecutar el modelo")
                return render(request, "solicitud.html", {
                    "form":          form,
                    "catalogo_json": catalogo_json,
                    "error":         f"Error al ejecutar el modelo: {exc}",
                })

            # ── 5. Motor de decisión crediticia ────────────────────────
            plan_key      = data["plan_solicitado"]
            plan_cat      = CATALOGO_PLANES[plan_key]
            monto_sol     = data["monto_solicitado"]
            plazo_sol     = data["plazo_meses"]

            plan_para_motor = {
                "nombre":        plan_cat["nombre"],
                "monto":         monto_sol,
                "plazo_meses":   plazo_sol,
                "tasa_anual":    plan_cat["tasa_anual"],
                "score_minimo":  plan_cat["score_minimo"],
            }

            motor     = MotorDecisionCredito()
            resultado = motor.evaluar_solicitud(
                pd              = pd_valor,
                ingreso_mensual = ingreso,
                deudas_mensuales= total_cuotas,
                plan_solicitado = plan_para_motor,
            )

            # ── 6. Determinar escenario para el template ───────────────
            # APROBADO          → califica para el plan solicitado
            # RECHAZADO_CON_ALT → no califica pero hay alternativas
            # RECHAZADO_SIN_ALT → no califica y no hay alternativas
            estado = resultado["estado"]
            if estado == "APROBADO":
                escenario = "aprobado"
            elif resultado["alternativas"]:
                escenario = "rechazado_con_alt"
            else:
                escenario = "rechazado_sin_alt"

            # ── 7. Contexto al template ────────────────────────────────
            contexto = {
                # Identificación
                "cedula":                 cedula,
                "plan_nombre":            plan_cat["nombre"],
                "monto_solicitado":       monto_sol,
                "plazo_solicitado":       plazo_sol,
                # Probabilidades del modelo
                "prob_aprobado":          prob_aprobado,
                "prob_rechazado":         prob_rechazado,
                # Motor de decisión
                "escenario":              escenario,
                "score":                  resultado["score"],
                "pd":                     round(resultado["pd"] * 100, 2),
                "cuota_calculada":        resultado["cuota_calculada"],
                "monto_preaprobado":      resultado["monto_preaprobado"],
                "motivos_rechazo":        resultado["motivos_rechazo"],
                "alternativas":           resultado["alternativas"],
                # DTI
                "relacion_deuda_ingreso": relacion_deuda_ingreso,
                # Datos originales para el resumen
                "datos_formulario":       data,
                "datos_buro":             cliente_db,
            }
            return render(request, "resultado.html", contexto)

    return render(request, "solicitud.html", {
        "form":          form,
        "catalogo_json": catalogo_json,
    })
