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
    ("dependiente",  "Empleado en relación de dependencia"),
    ("independiente","Trabajador independiente / Freelance"),
    ("empresario",   "Empresario / Socio"),
    ("desempleado",  "Desempleado"),
    ("jubilado",     "Jubilado / Pensionado"),
]


class SolicitudCreditoForm(forms.Form):
    cedula = forms.CharField(
        label="Número de Cédula",
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Ej: 4.567.890",
            "autofocus": True,
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

    def clean_cedula(self):
        """Normaliza la cédula removiendo puntos y guiones."""
        cedula = self.cleaned_data.get("cedula", "")
        return cedula.replace(".", "").replace("-", "").strip()
