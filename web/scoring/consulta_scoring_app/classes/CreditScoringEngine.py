import numpy as np
import shap
import pandas as pd


class CreditScoringEngine:
    def __init__(self, model, base_score=600, base_odds=50, pdo=20):
        self.model = model
        self.factor = pdo / np.log(2)
        self.offset = base_score - (self.factor * np.log(base_odds))
        self.explainer = shap.Explainer(model)

    def pd_a_score(self, pd_val: float) -> int:
        pd_clean = max(min(pd_val, 0.9999), 0.0001)
        odds = (1 - pd_clean) / pd_clean
        score = self.offset + (self.factor * np.log(odds))
        return int(np.clip(round(score), 300, 850))

    def evaluar(self, X_cliente: pd.DataFrame) -> dict:
        # 1. Obtener Probabilidad de Default (PD)
        pd_val = self.model.predict_proba(X_cliente)[0][1]
        score_final = self.pd_a_score(pd_val)

        # 2. Explicabilidad SHAP convertida a puntos
        shap_values = self.explainer(X_cliente)
        # Impacto a la clase 1 (Default): un valor positivo aumenta el riesgo -> resta puntos
        impactos_shap = shap_values.values[0]
        
        desglose_puntos = {}
        for col, val in zip(X_cliente.columns, impactos_shap):
            puntos = -1 * (val * self.factor)
            desglose_puntos[col] = round(float(puntos), 1)

        return {
            "score": score_final,
            "pd_porcentaje": round(pd_val * 100, 2),
            "desglose_puntos": desglose_puntos
        }