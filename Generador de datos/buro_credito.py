"""
Simulador de Datos para Modelo de Credit Scoring
=================================================
Genera dos tablas coherentes entre sí:

  TABLA 1 — datos_personales
    numero_ci, edad, tipo_vivienda, antiguedad_vivienda,
    situacion_laboral, antiguedad_laboral, ingreso_neto_mensual,
    total_cuotas_deudas_actuales, relacion_deuda_ingreso (DTI)

  TABLA 2 — buro_credito
    numero_ci, score_bruto_actual, cantidad_creditos_activos,
    saldo_deuda, peor_atraso, cantidad_cuentas_en_mora,
    perfil_riesgo

Coherencia garantizada:
  • El perfil de riesgo es el eje central: determina rangos
    de TODOS los campos en ambas tablas.
  • ingreso_neto_mensual y deudas son consistentes con DTI.
  • score_bruto_actual se degrada según mora y atraso real.
  • edad y antigüedades son mutuamente consistentes.
  • Variables categóricas (vivienda, situación laboral) tienen
    probabilidades condicionadas al perfil de riesgo.
"""

import random
import numpy as np
import pandas as pd
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────
#  PERFILES DE RIESGO (eje central de coherencia)
# ─────────────────────────────────────────────────────────

PERFILES = {
    # nombre: (peso_población, configuración)

    "excelente": (0.12, {
        # Personales
        "edad_rango":               (28, 60),
        "ingreso_rango":            (2_500, 12_000),
        "antiguedad_laboral_rango": (3, 25),
        "antiguedad_vivienda_rango":(2, 20),
        "dti_rango":                (0.05, 0.25),     # deuda/ingreso bajo
        # Vivienda (probabilidades)
        "p_vivienda":               {"propia": 0.55, "alquilada": 0.25, "familiar": 0.20},
        # Situación laboral
        "p_laboral":                {"empleado_formal": 0.60, "independiente": 0.25,
                                     "empleado_informal": 0.10, "desempleado": 0.05},
        # Buró
        "score_rango":              (750, 850),
        "creditos_activos_rango":   (1, 3),
        "deuda_por_credito":        (500, 8_000),
        "peor_atraso_rango":        (0, 5),
        "mora_rango":               (0, 0),
    }),

    "bueno": (0.23, {
        "edad_rango":               (25, 58),
        "ingreso_rango":            (1_500, 7_000),
        "antiguedad_laboral_rango": (2, 18),
        "antiguedad_vivienda_rango":(1, 15),
        "dti_rango":                (0.10, 0.35),
        "p_vivienda":               {"propia": 0.40, "alquilada": 0.35, "familiar": 0.25},
        "p_laboral":                {"empleado_formal": 0.50, "independiente": 0.25,
                                     "empleado_informal": 0.20, "desempleado": 0.05},
        "score_rango":              (670, 749),
        "creditos_activos_rango":   (1, 4),
        "deuda_por_credito":        (1_000, 20_000),
        "peor_atraso_rango":        (0, 30),
        "mora_rango":               (0, 1),
    }),

    "regular": (0.30, {
        "edad_rango":               (22, 55),
        "ingreso_rango":            (800, 4_000),
        "antiguedad_laboral_rango": (0, 10),
        "antiguedad_vivienda_rango":(0, 10),
        "dti_rango":                (0.25, 0.50),
        "p_vivienda":               {"propia": 0.25, "alquilada": 0.40, "familiar": 0.35},
        "p_laboral":                {"empleado_formal": 0.35, "independiente": 0.25,
                                     "empleado_informal": 0.30, "desempleado": 0.10},
        "score_rango":              (550, 669),
        "creditos_activos_rango":   (2, 5),
        "deuda_por_credito":        (2_000, 35_000),
        "peor_atraso_rango":        (15, 90),
        "mora_rango":               (0, 3),
    }),

    "malo": (0.22, {
        "edad_rango":               (20, 52),
        "ingreso_rango":            (400, 2_500),
        "antiguedad_laboral_rango": (0, 6),
        "antiguedad_vivienda_rango":(0, 8),
        "dti_rango":                (0.40, 0.75),
        "p_vivienda":               {"propia": 0.15, "alquilada": 0.35, "familiar": 0.50},
        "p_laboral":                {"empleado_formal": 0.20, "independiente": 0.20,
                                     "empleado_informal": 0.40, "desempleado": 0.20},
        "score_rango":              (400, 549),
        "creditos_activos_rango":   (1, 6),
        "deuda_por_credito":        (3_000, 50_000),
        "peor_atraso_rango":        (60, 180),
        "mora_rango":               (1, 6),
    }),

    "muy_malo": (0.13, {
        "edad_rango":               (18, 50),
        "ingreso_rango":            (200, 1_500),
        "antiguedad_laboral_rango": (0, 3),
        "antiguedad_vivienda_rango":(0, 5),
        "dti_rango":                (0.60, 1.20),     # puede superar el 100%
        "p_vivienda":               {"propia": 0.08, "alquilada": 0.30, "familiar": 0.62},
        "p_laboral":                {"empleado_formal": 0.10, "independiente": 0.15,
                                     "empleado_informal": 0.40, "desempleado": 0.35},
        "score_rango":              (300, 399),
        "creditos_activos_rango":   (0, 4),
        "deuda_por_credito":        (5_000, 80_000),
        "peor_atraso_rango":        (120, 730),
        "mora_rango":               (3, 24),
    }),
}


# ─────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────

def _normal_clamp(mean, std, lo, hi) -> float:
    return float(np.clip(np.random.normal(mean, std), lo, hi))


def _categorical(opciones: dict) -> str:
    return random.choices(
        list(opciones.keys()),
        weights=list(opciones.values()),
        k=1
    )[0]


# ─────────────────────────────────────────────────────────
#  GENERADOR PRINCIPAL
# ─────────────────────────────────────────────────────────

class SimuladorScoring:

    def __init__(self, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)
        self._ci_usados: set[str] = set()

    # ── CI único ────────────────────────────

    def _generar_ci(self) -> str:
        while True:
            ci = str(random.randint(1_000_000, 9_999_999))
            if ci not in self._ci_usados:
                self._ci_usados.add(ci)
                return ci

    # ── Elegir perfil ───────────────────────

    def _elegir_perfil(self) -> tuple[str, dict]:
        nombres = list(PERFILES.keys())
        pesos   = [PERFILES[n][0] for n in nombres]
        nombre  = random.choices(nombres, weights=pesos, k=1)[0]
        return nombre, PERFILES[nombre][1]

    # ── Generar un individuo ─────────────────

    def _generar_individuo(self) -> dict:
        perfil, cfg = self._elegir_perfil()
        ci = self._generar_ci()

        # ── EDAD ──────────────────────────────────────────────
        e_lo, e_hi = cfg["edad_rango"]
        edad = int(_normal_clamp((e_lo + e_hi) / 2, (e_hi - e_lo) / 5, e_lo, e_hi))

        # ── SITUACIÓN LABORAL ─────────────────────────────────
        situacion_laboral = _categorical(cfg["p_laboral"])

        # Antigüedad laboral: si desempleado → 0
        al_lo, al_hi = cfg["antiguedad_laboral_rango"]
        if situacion_laboral == "desempleado":
            antiguedad_laboral = 0
        else:
            # No puede superar la edad activa (edad - 18)
            al_hi_real = min(al_hi, max(0, edad - 18))
            antiguedad_laboral = int(_normal_clamp(
                (al_lo + al_hi_real) / 2, (al_hi_real - al_lo + 1) / 4,
                al_lo, al_hi_real
            ))

        # ── INGRESO NETO MENSUAL ──────────────────────────────
        i_lo, i_hi = cfg["ingreso_rango"]
        # Desempleados tienen ingresos muy bajos (informales/subsidios)
        if situacion_laboral == "desempleado":
            i_hi = min(i_hi, 600)
            i_lo = min(i_lo, 200)
        ingreso_neto_mensual = round(_normal_clamp(
            (i_lo + i_hi) / 2, (i_hi - i_lo) / 4, i_lo, i_hi
        ), 2)

        # ── TIPO Y ANTIGÜEDAD DE VIVIENDA ─────────────────────
        tipo_vivienda = _categorical(cfg["p_vivienda"])
        av_lo, av_hi  = cfg["antiguedad_vivienda_rango"]
        av_hi_real    = min(av_hi, max(0, edad - 18))
        antiguedad_vivienda = int(_normal_clamp(
            (av_lo + av_hi_real) / 2, (av_hi_real - av_lo + 1) / 4,
            av_lo, av_hi_real
        ))

        # ── BURÓ DE CRÉDITO ───────────────────────────────────

        # Score base
        s_lo, s_hi = cfg["score_rango"]
        score = int(_normal_clamp((s_lo + s_hi) / 2, (s_hi - s_lo) / 6, s_lo, s_hi))

        # Créditos activos
        cant_cred = random.randint(*cfg["creditos_activos_rango"])

        # Saldo deuda total
        d_lo, d_hi = cfg["deuda_por_credito"]
        if cant_cred == 0:
            saldo_deuda = 0.0
        else:
            saldo_deuda = round(sum(
                random.uniform(d_lo, d_hi) for _ in range(cant_cred)
            ), 2)

        # Peor atraso (días)
        a_lo, a_hi = cfg["peor_atraso_rango"]
        peor_atraso = int(np.clip(
            np.random.exponential(max(1, (a_hi - a_lo) / 3)) + a_lo,
            a_lo, a_hi
        ))

        # Cuentas en mora
        m_lo, m_hi = cfg["mora_rango"]
        cantidad_cuentas_en_mora = 0 if cant_cred == 0 else random.randint(m_lo, m_hi)

        # Penalización de score según mora y atraso reales
        if cantidad_cuentas_en_mora > 0:
            score = max(300, score - random.randint(
                cantidad_cuentas_en_mora * 5,
                cantidad_cuentas_en_mora * 12
            ))
        if peor_atraso > 90:
            score = max(300, score - random.randint(10, 40))

        # ── DTI Y CUOTAS ─────────────────────────────────────
        # DTI = total_cuotas / ingreso_neto_mensual
        # Lo generamos desde el DTI objetivo del perfil
        dti_lo, dti_hi = cfg["dti_rango"]
        dti_objetivo = _normal_clamp(
            (dti_lo + dti_hi) / 2, (dti_hi - dti_lo) / 4, dti_lo, dti_hi
        )
        # Cuota mensual total consistente con saldo y DTI
        total_cuotas = round(ingreso_neto_mensual * dti_objetivo, 2)

        # Si no hay deuda, cuota = 0 y DTI = 0
        if saldo_deuda == 0:
            total_cuotas = 0.0

        # DTI real recalculado (evitar división por cero)
        dti_real = round(total_cuotas / ingreso_neto_mensual, 4) if ingreso_neto_mensual > 0 else 0.0

        return {
            # Llave de unión
            "numero_ci":                    ci,
            # Personales
            "edad":                         edad,
            "tipo_vivienda":                tipo_vivienda,
            "antiguedad_vivienda":          antiguedad_vivienda,
            "situacion_laboral":            situacion_laboral,
            "antiguedad_laboral":           antiguedad_laboral,
            "ingreso_neto_mensual":         ingreso_neto_mensual,
            "total_cuotas_deudas_actuales": total_cuotas,
            "relacion_deuda_ingreso":       dti_real,
            # Buró
            "score_bruto_actual":           score,
            "cantidad_creditos_activos":    cant_cred,
            "saldo_deuda":                  saldo_deuda,
            "peor_atraso":                  peor_atraso,
            "cantidad_cuentas_en_mora":     cantidad_cuentas_en_mora,
            "perfil_riesgo":                perfil,
        }

    # ── API pública ─────────────────────────

    def generar(self, n: int = 2000) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Genera n registros y devuelve (datos_personales, buro_credito).
        Ambas tablas comparten numero_ci como llave de unión.
        """
        filas = [self._generar_individuo() for _ in range(n)]
        df_full = pd.DataFrame(filas)

        cols_personales = [
            "numero_ci", "edad", "tipo_vivienda", "antiguedad_vivienda",
            "situacion_laboral", "antiguedad_laboral", "ingreso_neto_mensual",
            "total_cuotas_deudas_actuales", "relacion_deuda_ingreso",
        ]
        cols_buro = [
            "numero_ci", "score_bruto_actual", "cantidad_creditos_activos",
            "saldo_deuda", "peor_atraso", "cantidad_cuentas_en_mora",
            "perfil_riesgo",
        ]

        df_personales = df_full[cols_personales].copy()
        df_buro       = df_full[cols_buro].copy()

        print(f"✅ Generados {n:,} registros")
        print(f"   → datos_personales : {df_personales.shape}")
        print(f"   → buro_credito     : {df_buro.shape}")
        return df_personales, df_buro


# ─────────────────────────────────────────────────────────
#  REPORTE DE VALIDACIÓN DE COHERENCIA
# ─────────────────────────────────────────────────────────

def reporte(df_p: pd.DataFrame, df_b: pd.DataFrame):
    df = df_p.merge(df_b, on="numero_ci")

    sep = "=" * 62

    print(f"\n{sep}")
    print("  REPORTE DE VALIDACIÓN — COHERENCIA ENTRE VARIABLES")
    print(sep)

    # 1. Distribución por perfil
    print("\n  [1] Distribución por perfil de riesgo")
    dist = df["perfil_riesgo"].value_counts()
    for p, n in dist.items():
        bar = "█" * int(n / len(df) * 35)
        print(f"      {p:<12} {bar:<35} {n:>5}  ({n/len(df)*100:.1f}%)")

    # 2. Score promedio por perfil
    print("\n  [2] Score bruto promedio por perfil")
    score_p = df.groupby("perfil_riesgo")["score_bruto_actual"].mean().sort_values(ascending=False)
    for p, s in score_p.items():
        print(f"      {p:<12}  {s:>6.0f}")

    # 3. DTI por perfil (debe crecer con el riesgo)
    print("\n  [3] DTI (relacion_deuda_ingreso) promedio por perfil")
    orden = ["excelente", "bueno", "regular", "malo", "muy_malo"]
    dti_p = df.groupby("perfil_riesgo")["relacion_deuda_ingreso"].mean()
    for p in orden:
        if p in dti_p.index:
            print(f"      {p:<12}  {dti_p[p]:.3f}")

    # 4. Ingreso vs mora (negativamente correlacionados)
    print("\n  [4] Ingreso neto mensual promedio por perfil")
    ing_p = df.groupby("perfil_riesgo")["ingreso_neto_mensual"].mean()
    for p in orden:
        if p in ing_p.index:
            print(f"      {p:<12}  ${ing_p[p]:>9,.0f}")

    # 5. Correlaciones clave
    print("\n  [5] Correlaciones clave (Pearson)")
    pares = [
        ("score_bruto_actual",    "cantidad_cuentas_en_mora", "esperada: negativa"),
        ("score_bruto_actual",    "peor_atraso",              "esperada: negativa"),
        ("score_bruto_actual",    "ingreso_neto_mensual",     "esperada: positiva"),
        ("relacion_deuda_ingreso","score_bruto_actual",       "esperada: negativa"),
        ("antiguedad_laboral",    "ingreso_neto_mensual",     "esperada: positiva"),
    ]
    for c1, c2, desc in pares:
        r = df[c1].corr(df[c2])
        print(f"      {c1:<35} ↔ {c2:<30} r = {r:+.3f}  ({desc})")

    # 6. Estadísticas globales
    cols = [
        "edad", "ingreso_neto_mensual", "relacion_deuda_ingreso",
        "score_bruto_actual", "peor_atraso", "cantidad_cuentas_en_mora",
    ]
    print(f"\n  [6] Estadísticas descriptivas globales")
    print(f"      {'Campo':<35} {'Media':>9} {'Mediana':>9} {'Std':>9} {'Min':>8} {'Max':>8}")
    print("      " + "─" * 80)
    for c in cols:
        print(
            f"      {c:<35} "
            f"{df[c].mean():>9.2f} "
            f"{df[c].median():>9.2f} "
            f"{df[c].std():>9.2f} "
            f"{df[c].min():>8.2f} "
            f"{df[c].max():>8.2f}"
        )

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    sim = SimuladorScoring(seed=42)

    df_personales, df_buro = sim.generar(n=40000)

    reporte(df_personales, df_buro)

    # Muestra combinada
    df_merged = df_personales.merge(df_buro, on="numero_ci")
    print("  MUESTRA — 5 registros (vista combinada):")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(df_merged.sample(5, random_state=7).to_string(index=False))
    print()

    # Exportar
    out_p = "D:/Archivos/TESIS/datasets/datos_personales.csv"
    out_b = "D:/Archivos/TESIS/datasets/buro_credito.csv"
    df_personales.to_csv(out_p, index=False)
    df_buro.to_csv(out_b, index=False)
    print(f"📁 datos_personales  →  {out_p}")
    print(f"📁 buro_credito      →  {out_b}") 