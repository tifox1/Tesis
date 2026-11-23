import math
import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.utils import timezone

from .models import DecisionCredito, SeguimientoCredito, Solicitante
from .services.captura_financiera import calcular_indicadores


def normalizar_cedula(texto):
    """Acepta puntos/guiones/espacios visuales; almacena solo dígitos."""
    texto = (texto or '').strip()
    if not re.fullmatch(r'[0-9.\-\s]+', texto):
        raise forms.ValidationError('La cédula debe contener únicamente números, puntos o guiones.')
    cedula = re.sub(r'[^0-9]', '', texto)
    if not 4 <= len(cedula) <= 12:
        raise forms.ValidationError('Ingrese una cédula de entre 4 y 12 dígitos.')
    return cedula


def edad_en_fecha(nacimiento, fecha):
    return fecha.year - nacimiento.year - ((fecha.month, fecha.day) < (nacimiento.month, nacimiento.day))


class SolicitanteForm(forms.ModelForm):
    cedula = forms.CharField(label='Número de cédula de identidad', max_length=30)
    fecha_nacimiento = forms.DateField(
        label='Fecha de nacimiento', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    class Meta:
        model = Solicitante
        fields = ('cedula', 'nombres', 'apellidos', 'fecha_nacimiento', 'ciudad',
                  'ocupacion', 'situacion_laboral')

    def clean_cedula(self):
        valor = normalizar_cedula(self.cleaned_data['cedula'])
        if Solicitante.objects.filter(cedula=valor).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('La cédula ya se encuentra registrada en el sistema.')
        return valor

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data['fecha_nacimiento']
        edad = edad_en_fecha(fecha, timezone.localdate())
        if not 18 <= edad <= 100:
            raise forms.ValidationError('La persona debe tener entre 18 y 100 años.')
        return fecha


class EvaluacionScoringForm(forms.Form):
    """Admite captura directa o derivada, con reglas independientes del navegador.

    Los diez valores finales consumidos por el modelo se mantienen sin cambios.
    La información complementaria de captura se persiste aparte del vector ML.
    """

    class Modo:
        AUTOMATICO = 'AUTOMATICO'
        DIRECTO = 'DIRECTO'

    CAMPOS_DESGLOSE = (
        'cuota_hipotecaria_gs', 'cuota_prestamos_personales_gs',
        'pago_mensual_tarjetas_gs', 'saldo_lineas_utilizado_gs',
        'limite_lineas_total_gs',
    )
    CAMPOS_DIRECTOS = ('relacion_deuda_ingreso', 'utilizacion_lineas', 'fuente_indicadores')
    VARIABLES_MODELO = (
        'edad', 'ingreso_mensual_bruto_gs', 'relacion_deuda_ingreso',
        'utilizacion_lineas', 'atraso_30_59', 'atraso_60_89',
        'atraso_90_plus', 'cantidad_creditos_activos',
        'creditos_inmobiliarios', 'dependientes',
    )

    modo_captura = forms.ChoiceField(
        label='Modalidad de captura',
        choices=[(Modo.AUTOMATICO, 'Calcular indicadores con desglose'),
                 (Modo.DIRECTO, 'Ingresar indicadores existentes')],
        initial=Modo.AUTOMATICO, widget=forms.RadioSelect,
    )
    edad = forms.IntegerField(label='Edad', min_value=18, max_value=100)
    ingreso_mensual_bruto_gs = forms.IntegerField(
        label='Ingreso mensual bruto (Gs.)', min_value=1,
        help_text='En guaraníes, sin puntos ni separadores; dato declarado o documentado.',
    )
    relacion_deuda_ingreso = forms.FloatField(
        label='DTI obtenido de otra fuente', min_value=0, max_value=2, required=False,
        help_text='Proporción decimal: 0.25 significa 25 %. Solo modalidad directa.',
    )
    utilizacion_lineas = forms.FloatField(
        label='Utilización de líneas obtenida de otra fuente', min_value=0, required=False,
        help_text='Proporción decimal: 0.40 significa 40 %. Solo modalidad directa.',
    )
    fuente_indicadores = forms.CharField(
        label='Origen declarado de los indicadores', max_length=180, required=False,
        help_text='Ej.: reporte crediticio consultado, planilla del analista. No implica verificación automática.',
    )
    cuota_hipotecaria_gs = forms.IntegerField(
        label='Cuota mensual hipotecaria (Gs.)', min_value=0, required=False,
    )
    cuota_prestamos_personales_gs = forms.IntegerField(
        label='Cuotas mensuales de otros préstamos (Gs.)', min_value=0, required=False,
    )
    pago_mensual_tarjetas_gs = forms.IntegerField(
        label='Pagos mensuales exigibles por tarjetas (Gs.)', min_value=0, required=False,
    )
    saldo_lineas_utilizado_gs = forms.IntegerField(
        label='Saldo utilizado de tarjetas y líneas revolventes (Gs.)', min_value=0, required=False,
    )
    limite_lineas_total_gs = forms.IntegerField(
        label='Límite total de esas líneas revolventes (Gs.)', min_value=0, required=False,
    )
    atraso_30_59 = forms.IntegerField(label='Atrasos de 30–59 días', min_value=0)
    atraso_60_89 = forms.IntegerField(label='Atrasos de 60–89 días', min_value=0)
    atraso_90_plus = forms.IntegerField(label='Atrasos de 90 días o más', min_value=0)
    cantidad_creditos_activos = forms.IntegerField(label='Créditos/líneas activas', min_value=0)
    creditos_inmobiliarios = forms.IntegerField(label='Créditos inmobiliarios', min_value=0)
    dependientes = forms.IntegerField(label='Dependientes', min_value=0)

    def __init__(self, *args, edad_solicitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edad_solicitante = edad_solicitante
        self.detalle_captura = None
        if edad_solicitante is not None:
            self.fields['edad'].widget = forms.HiddenInput()
            self.fields['edad'].initial = edad_solicitante
        # Los campos inactivos quedan deshabilitados también en el servidor:
        # ni se requieren ni se toman sus valores manipulados por el navegador.
        modo = (self.data.get('modo_captura') if self.is_bound
                else self.initial.get('modo_captura', self.Modo.AUTOMATICO))
        if modo == self.Modo.AUTOMATICO:
            inactivos = self.CAMPOS_DIRECTOS
        elif modo == self.Modo.DIRECTO:
            inactivos = self.CAMPOS_DESGLOSE
        else:
            inactivos = self.CAMPOS_DESGLOSE + self.CAMPOS_DIRECTOS
        for name in inactivos:
            self.fields[name].disabled = True

    def clean(self):
        cleaned = super().clean()
        if (self.edad_solicitante is not None and cleaned.get('edad') is not None
                and cleaned['edad'] != self.edad_solicitante):
            self.add_error('edad', 'La edad no coincide con la fecha de nacimiento registrada.')

        modo = cleaned.get('modo_captura')
        if not modo:
            return cleaned
        creditos = cleaned.get('cantidad_creditos_activos')
        inmobiliarios = cleaned.get('creditos_inmobiliarios')
        if creditos is not None and inmobiliarios is not None and inmobiliarios > creditos:
            self.add_error('creditos_inmobiliarios',
                           'No puede superar el total de créditos y líneas activas.')

        ingreso = cleaned.get('ingreso_mensual_bruto_gs')
        if modo == self.Modo.AUTOMATICO:
            for name in self.CAMPOS_DESGLOSE:
                if cleaned.get(name) is None and name not in self.errors:
                    self.add_error(name, 'Complete este importe (ingrese 0 si no corresponde).')
            if all(cleaned.get(n) is not None for n in self.CAMPOS_DESGLOSE) and ingreso is not None:
                # add_error() elimina de cleaned_data el campo señalado. Guardamos
                # los importes validados ANTES de añadir errores cruzados.
                desglose_validado = {n: cleaned[n] for n in self.CAMPOS_DESGLOSE}
                try:
                    derivados = calcular_indicadores(
                        ingreso_gs=ingreso,
                        **desglose_validado,
                    )
                except ValueError as exc:
                    self.add_error('limite_lineas_total_gs', str(exc))
                else:
                    cleaned['relacion_deuda_ingreso'] = derivados['relacion_deuda_ingreso']
                    cleaned['utilizacion_lineas'] = derivados['utilizacion_lineas']
                    if derivados['relacion_deuda_ingreso'] > 2:
                        self.add_error('cuota_prestamos_personales_gs',
                                       'El DTI resultante supera 2.00, límite del modelo.')
                    if (creditos == 0 and
                            (derivados['total_cuotas_mensuales_gs'] > 0 or
                             cleaned['saldo_lineas_utilizado_gs'] > 0 or
                             cleaned['limite_lineas_total_gs'] > 0)):
                        self.add_error('cantidad_creditos_activos',
                                       'Hay pagos o líneas declarados, pero cero créditos/líneas activos.')
                    self.detalle_captura = {
                        'modalidad': 'CALCULO_AUTOMATICO',
                        'origen': 'Desglose ingresado por analista (sin verificación externa automática)',
                        'desglose_gs': desglose_validado,
                        'total_cuotas_mensuales_gs': derivados['total_cuotas_mensuales_gs'],
                        'indicadores_calculados': {
                            'relacion_deuda_ingreso': derivados['relacion_deuda_ingreso'],
                            'utilizacion_lineas': derivados['utilizacion_lineas'],
                        },
                    }
        elif modo == self.Modo.DIRECTO:
            for name in ('relacion_deuda_ingreso', 'utilizacion_lineas', 'fuente_indicadores'):
                if cleaned.get(name) is None or (isinstance(cleaned.get(name), str)
                                                and not cleaned[name].strip()):
                    if name not in self.errors:
                        self.add_error(name, 'Campo obligatorio en modalidad directa.')
            if cleaned.get('fuente_indicadores'):
                fuente = cleaned['fuente_indicadores'].strip()
                if len(fuente) < 5:
                    self.add_error('fuente_indicadores', 'Identifique el origen (mínimo 5 caracteres).')
            for name in ('relacion_deuda_ingreso', 'utilizacion_lineas'):
                valor = cleaned.get(name)
                if valor is not None and not math.isfinite(valor):
                    self.add_error(name, 'Ingrese un valor finito.')
            if creditos == 0 and (cleaned.get('utilizacion_lineas') or 0) > 0:
                self.add_error('cantidad_creditos_activos',
                               'Hay utilización positiva, pero ninguna línea de crédito activa.')
            self.detalle_captura = {
                'modalidad': 'INGRESO_DIRECTO',
                'origen': (cleaned.get('fuente_indicadores') or '').strip(),
                'desglose_gs': None,
                'indicadores_informados': {
                    'relacion_deuda_ingreso': cleaned.get('relacion_deuda_ingreso'),
                    'utilizacion_lineas': cleaned.get('utilizacion_lineas'),
                },
            }
        return cleaned

    def datos_para_modelo(self):
        """Retorna exactamente las diez variables usadas históricamente."""
        if not self.is_valid():
            raise ValueError('No se pueden obtener variables de un formulario inválido.')
        return {name: self.cleaned_data[name] for name in self.VARIABLES_MODELO}


class DecisionCreditoForm(forms.ModelForm):
    producto_codigo = forms.ChoiceField(label='Producto seleccionado', required=False, choices=[('', 'Sin producto')])

    class Meta:
        model = DecisionCredito
        fields = ('estado', 'producto_codigo', 'motivo')
        widgets = {'motivo': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, evaluacion, **kwargs):
        super().__init__(*args, **kwargs)
        self.evaluacion = evaluacion
        self.fields['producto_codigo'].choices = [('', 'Sin producto')] + [
            (oferta['codigo'], oferta.get('producto', oferta['codigo']))
            for oferta in evaluacion.ofertas if oferta.get('codigo')
        ]

    def clean(self):
        cleaned = super().clean()
        estado = cleaned.get('estado')
        producto = cleaned.get('producto_codigo', '')
        motivo = (cleaned.get('motivo') or '').strip()
        if estado == DecisionCredito.Estado.APROBADA and not producto:
            self.add_error('producto_codigo', 'Una aprobación requiere seleccionar una oferta disponible.')
        if estado != DecisionCredito.Estado.APROBADA and producto:
            self.add_error('producto_codigo', 'Solo una aprobación puede seleccionar un producto.')
        if len(motivo) < 10:
            self.add_error('motivo', 'Describa la justificación (mínimo 10 caracteres).')
        cleaned['motivo'] = motivo
        return cleaned


class SeguimientoCreditoForm(forms.ModelForm):
    """Crea/actualiza seguimiento simulado con validación cronológica estricta."""

    class Meta:
        model = SeguimientoCredito
        fields = ('fecha_otorgamiento', 'fecha_cierre_prevista', 'fecha_observacion',
                  'estado', 'max_dias_mora', 'observaciones')
        widgets = {
            'fecha_otorgamiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_cierre_prevista': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_observacion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'fecha_otorgamiento': 'Fecha de otorgamiento',
            'fecha_cierre_prevista': 'Fecha prevista de cierre',
            'fecha_observacion': 'Fecha de observación',
            'estado': 'Estado del crédito',
            'max_dias_mora': 'Máximo de días de mora observados',
            'observaciones': 'Observaciones (opcionales)',
        }

    def __init__(self, *args, decision, **kwargs):
        super().__init__(*args, **kwargs)
        self.decision = decision
        self.instance.decision = decision
        if self.instance.pk:
            # Las fechas contractuales son fijas; las correcciones requieren revisión.
            self.fields['fecha_otorgamiento'].disabled = True
            self.fields['fecha_cierre_prevista'].disabled = True
        else:
            self.fields['fecha_otorgamiento'].initial = timezone.localdate()
            self.fields['fecha_observacion'].initial = timezone.localdate()

    def clean(self):
        datos = super().clean()
        # Preservar la fecha de observación y el máximo histórico ya asentados.
        if self.instance.pk:
            original = SeguimientoCredito.objects.get(pk=self.instance.pk)
            nueva_fecha = datos.get('fecha_observacion')
            nuevo_maximo = datos.get('max_dias_mora')
            if nueva_fecha is not None and nueva_fecha < original.fecha_observacion:
                self.add_error('fecha_observacion', 'La fecha de observación no puede retroceder.')
            if nuevo_maximo is not None and nuevo_maximo < original.max_dias_mora:
                self.add_error('max_dias_mora', 'El máximo histórico de mora no puede disminuir.')
            if original.estado == SeguimientoCredito.Estado.CANCELADO:
                if datos.get('estado') != original.estado:
                    self.add_error('estado', 'El estado cancelado es final en este prototipo.')
            elif original.estado == SeguimientoCredito.Estado.VENCIDO and datos.get('estado') == SeguimientoCredito.Estado.VIGENTE:
                self.add_error('estado', 'Un crédito vencido no puede volver al estado vigente.')
        return datos


class AltaUsuarioForm(UserCreationForm):
    ROL_CHOICES = [('ANALISTA', 'Analista'), ('ADMINISTRADOR', 'Administrador'), ('AUDITOR', 'Auditor (solo consulta)')]
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    email = forms.EmailField(label='Correo electrónico', required=False)
    rol = forms.ChoiceField(label='Rol', choices=ROL_CHOICES)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'rol')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
            rol = self.cleaned_data['rol']
            group, _ = Group.objects.get_or_create(name=rol)
            user.groups.set([group])
            if rol == 'ADMINISTRADOR':
                user.is_staff = True
                user.save(update_fields=['is_staff'])
        return user


class CambiarRolForm(forms.Form):
    rol = forms.ChoiceField(label='Nuevo rol', choices=AltaUsuarioForm.ROL_CHOICES)
