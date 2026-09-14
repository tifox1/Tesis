from django import forms


TIPO_VIVIENDA_CHOICES = [
    ("", "— Seleccione —"),
    ("propia",       "Propia"),
    ("alquilada",    "Alquilada"),
    ("familiar",     "Familiar / Cedida"),
    ("hipotecada",   "Hipotecada"),
]

SITUACION_LABORAL_CHOICES = [
    ("", "— Seleccione —"),
    ("dependiente",   "Empleado en relación de dependencia"),
    ("independiente", "Trabajador independiente / Freelance"),
    ("empresario",    "Empresario / Socio"),
    ("desempleado",   "Desempleado"),
    ("jubilado",      "Jubilado / Pensionado"),
]

PLAN_CHOICES = [
    ("",                    "— Seleccione un plan —"),
    ("microcredito_express", "Microcrédito Express"),
    ("prestamo_personal",    "Préstamo Personal Estándar"),
    ("credito_platino",      "Crédito Platino"),
]


class SolicitudCreditoForm(forms.Form):

    # ── Datos del solicitante ─────────────────────────────────────────────────

    cedula = forms.CharField(
        label="Número de Cédula",
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Ej: 4.567.890",
            "autofocus":   True,
        }),
    )

    edad = forms.IntegerField(
        label="Edad",
        min_value=18,
        max_value=100,
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 35"}),
    )

    tipo_vivienda = forms.ChoiceField(
        label="Tipo de Vivienda",
        choices=TIPO_VIVIENDA_CHOICES,
    )

    antiguedad_vivienda = forms.IntegerField(
        label="Antigüedad en la Vivienda (años)",
        min_value=0,
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 5"}),
    )

    situacion_laboral = forms.ChoiceField(
        label="Situación Laboral",
        choices=SITUACION_LABORAL_CHOICES,
    )

    antiguedad_laboral = forms.IntegerField(
        label="Antigüedad Laboral (años)",
        min_value=0,
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 3"}),
    )

    ingreso_neto_mensual = forms.FloatField(
        label="Ingreso Neto Mensual (Gs.)",
        min_value=0.01,
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 3500000", "step": "0.01"}),
    )

    # ── Solicitud del crédito ─────────────────────────────────────────────────

    plan_solicitado = forms.ChoiceField(
        label="Plan de Crédito Solicitado",
        choices=PLAN_CHOICES,
    )

    monto_solicitado = forms.FloatField(
        label="Monto Solicitado (Gs.)",
        min_value=1,
        widget=forms.NumberInput(attrs={
            "placeholder": "Seleccione un plan primero",
            "step":        "1",
        }),
    )

    plazo_meses = forms.IntegerField(
        label="Plazo (meses)",
        min_value=1,
        widget=forms.NumberInput(attrs={
            "placeholder": "Seleccione un plan primero",
        }),
    )

    # ── Limpieza y validación cruzada ─────────────────────────────────────────

    # Rangos por plan: deben coincidir exactamente con CATALOGO_PLANES en views.py
    _RANGOS = {
        "microcredito_express": {
            "monto_min":  500_000,   "monto_max":  5_000_000,
            "plazo_min":  6,          "plazo_max":  12,
        },
        "prestamo_personal": {
            "monto_min":  1_000_000, "monto_max":  50_000_000,
            "plazo_min":  6,          "plazo_max":  36,
        },
        "credito_platino": {
            "monto_min":  5_000_000, "monto_max": 150_000_000,
            "plazo_min":  12,         "plazo_max":  60,
        },
    }

    def clean_cedula(self):
        """Normaliza la cédula removiendo puntos y guiones."""
        cedula = self.cleaned_data.get("cedula", "")
        return cedula.replace(".", "").replace("-", "").strip()

    def clean_plan_solicitado(self):
        plan = self.cleaned_data.get("plan_solicitado", "")
        if not plan:
            raise forms.ValidationError("Debe seleccionar un plan de crédito.")
        return plan

    def clean(self):
        """Valida que monto y plazo estén dentro de los rangos del plan elegido."""
        cleaned = super().clean()
        plan    = cleaned.get("plan_solicitado")
        monto   = cleaned.get("monto_solicitado")
        plazo   = cleaned.get("plazo_meses")

        if not plan or plan not in self._RANGOS:
            return cleaned

        rangos = self._RANGOS[plan]

        if monto is not None:
            if monto < rangos["monto_min"]:
                self.add_error(
                    "monto_solicitado",
                    f"El monto mínimo para este plan es Gs. {rangos['monto_min']:,.0f}."
                )
            elif monto > rangos["monto_max"]:
                self.add_error(
                    "monto_solicitado",
                    f"El monto máximo para este plan es Gs. {rangos['monto_max']:,.0f}."
                )

        if plazo is not None:
            if plazo < rangos["plazo_min"]:
                self.add_error(
                    "plazo_meses",
                    f"El plazo mínimo para este plan es {rangos['plazo_min']} meses."
                )
            elif plazo > rangos["plazo_max"]:
                self.add_error(
                    "plazo_meses",
                    f"El plazo máximo para este plan es {rangos['plazo_max']} meses."
                )

        return cleaned
