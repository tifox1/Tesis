import math

class MotorDecisionCredito:
    def __init__(self, target_score=600, target_odds=50, pdo=50):
        """
        Inicializa la escala del Scorecard.
        Factor y Offset permiten calibrar la escala logarítmica.
        """
        self.factor = pdo / math.log(2)
        self.offset = target_score - (self.factor * math.log(target_odds))

    def calcular_score(self, pd: float) -> int:
        """ Convierte la Probabilidad de Default (PD) en un Score (300 a 850) """
        pd_clamped = max(0.0001, min(0.9999, pd))
        odds = (1.0 - pd_clamped) / pd_clamped
        score = self.offset + (self.factor * math.log(odds))
        return int(max(300, min(850, round(score))))

    def calcular_cuota_frances(self, monto: float, tasa_anual: float, plazo_meses: int) -> float:
        """ Calcula la cuota fija mensual usando el Sistema Francés """
        if tasa_anual == 0:
            return monto / plazo_meses
        r = tasa_anual / 12.0
        return monto * (r * (1 + r)**plazo_meses) / ((1 + r)**plazo_meses - 1)
 
    def calcular_monto_maximo(self, cuota_disponible: float, tasa_anual: float, plazo_meses: int) -> float:
        """ Calcula el monto de préstamo máximo dada una cuota límite """
        if cuota_disponible <= 0:
            return 0.0
        r = tasa_anual / 12.0
        return cuota_disponible * ((1 + r)**plazo_meses - 1) / (r * (1 + r)**plazo_meses)

    def evaluar_solicitud(self, pd: float, ingreso_mensual: float, deudas_mensuales: float, plan_solicitado: dict) -> dict:
        """
        Evalúa el perfil del cliente, calcula el preaprobado y genera alternativas si aplica.
        """
        score = self.calcular_score(pd)

        # 1. Definir política de DTI según Score
        if score >= 650:
            dti_max = 0.40
        elif score >= 550:
            dti_max = 0.30
        else:
            dti_max = 0.20

        # 2. Capacidad de pago del cliente
        cuota_disponible = max(0.0, (ingreso_mensual * dti_max) - deudas_mensuales)

        # Datos del plan solicitado
        monto_sol = plan_solicitado["monto"]
        plazo_sol = plan_solicitado["plazo_meses"]
        tasa_sol = plan_solicitado["tasa_anual"]
        score_min_plan = plan_solicitado.get("score_minimo", 600)

        # 3. Cálculos financieros
        cuota_solicitada = self.calcular_cuota_frances(monto_sol, tasa_sol, plazo_sol)
        monto_preaprobado_plan = self.calcular_monto_maximo(cuota_disponible, tasa_sol, plazo_sol)

        # Verificación de condiciones
        cumple_score = score >= score_min_plan
        cumple_cuota = cuota_solicitada <= cuota_disponible

        # 4. Escenario APROBADO
        if cumple_score and cumple_cuota:
            return {
                "estado": "APROBADO",
                "score": score,
                "pd": round(pd, 4),
                "cuota_calculada": round(cuota_solicitada),
                "monto_preaprobado": round(monto_preaprobado_plan),
                "motivos_rechazo": [],
                "alternativas": []
            }

        # 5. Escenario RECHAZADO: Identificar motivos
        motivos = []
        if not cumple_score:
            motivos.append(f"Score obtenido ({score}) menor al requerido ({score_min_plan}).")
        if not cumple_cuota:
            motivos.append(f"Cuota calculada ({round(cuota_solicitada):,}) supera la capacidad disponible ({round(cuota_disponible):,}).")

        # 6. Generación de Alternativas Commerciales
        alternativas = []

        # Alternativa A: Ajustar el plan solicitado (Monto o Plazo)
        if cumple_score and not cumple_cuota and monto_preaprobado_plan > 0:
            alternativas.append({
                "nombre_plan": f"{plan_solicitado['nombre']} (Monto Ajustado)",
                "monto_sugerido": round(monto_preaprobado_plan),
                "plazo_meses": plazo_sol,
                "tasa_anual": tasa_sol,
                "cuota_estimada": round(cuota_disponible),
                "descripcion": "Monto reducido para adaptarse a tu capacidad de pago actual."
            })
            
            plazo_ext = min(60, plazo_sol + 12)
            cuota_ext = self.calcular_cuota_frances(monto_sol, tasa_sol, plazo_ext)
            if cuota_ext <= cuota_disponible:
                alternativas.append({
                    "nombre_plan": f"{plan_solicitado['nombre']} (Plazo Extendido)",
                    "monto_sugerido": monto_sol,
                    "plazo_meses": plazo_ext,
                    "tasa_anual": tasa_sol,
                    "cuota_estimada": round(cuota_ext),
                    "descripcion": f"Mismo monto a {plazo_ext} meses para lograr una cuota accesible."
                })

        # Alternativa B: Microcrédito Express (si el score es menor pero viable)
        if score >= 500 and not cumple_score:
            tasa_express = 0.30
            monto_preap_express = self.calcular_monto_maximo(cuota_disponible, tasa_express, 12)
            monto_express = min(5000000.0, monto_preap_express)
            
            if monto_express > 0:
                cuota_express = self.calcular_cuota_frances(monto_express, tasa_express, 12)
                alternativas.append({
                    "nombre_plan": "Microcrédito Express / Escala",
                    "monto_sugerido": round(monto_express),
                    "plazo_meses": 12,
                    "tasa_anual": tasa_express,
                    "cuota_estimada": round(cuota_express),
                    "descripcion": "Línea de crédito inicial para construir historial de pago positivo."
                })

        # Alternativa C: Plan de Consolidación de Deudas
        if deudas_mensuales > (ingreso_mensual * 0.20):
            tasa_cons = 0.22
            cuota_cons = self.calcular_cuota_frances(monto_sol, tasa_cons, 48)
            alternativas.append({
                "nombre_plan": "Plan Consolidación de Deudas",
                "monto_sugerido": monto_sol,
                "plazo_meses": 48,
                "tasa_anual": tasa_cons,
                "cuota_estimada": round(cuota_cons),
                "descripcion": "Unifica tus compromisos en una cuota mensual reducida a mayor plazo."
            })

        return {
            "estado": "RECHAZADO",
            "score": score,
            "pd": round(pd, 4),
            "cuota_calculada": round(cuota_solicitada),
            "monto_preaprobado": round(monto_preaprobado_plan),
            "motivos_rechazo": motivos,
            "alternativas": alternativas
        }