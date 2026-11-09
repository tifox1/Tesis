from django.test import SimpleTestCase

from .forms import EvaluacionScoringForm
from .services.credit_rules import (
    calcular_capacidad_pago,
    evaluar_productos,
    obtener_banda,
    obtener_plazo_permitido,
)


DATOS_VALIDOS_CON_CEROS = {
    'edad': 30,
    'ingreso_mensual_bruto_gs': 8_000_000,
    'relacion_deuda_ingreso': 0.20,
    'utilizacion_lineas': 0.10,
    'modo_captura': 'DIRECTO',
    'fuente_indicadores': 'Reporte de simulación del analista',
    'atraso_30_59': 1,
    'atraso_60_89': 0,
    'atraso_90_plus': 0,
    'cantidad_creditos_activos': 1,
    'creditos_inmobiliarios': 0,
    'dependientes': 0,
}


class EvaluacionScoringFormTests(SimpleTestCase):
    def test_cero_es_un_valor_valido(self):
        form = EvaluacionScoringForm(data=DATOS_VALIDOS_CON_CEROS)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['atraso_90_plus'], 0)
        self.assertEqual(form.cleaned_data['dependientes'], 0)

    def test_no_permite_campos_faltantes(self):
        data = DATOS_VALIDOS_CON_CEROS.copy()
        data.pop('dependientes')
        form = EvaluacionScoringForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('dependientes', form.errors)


class CapturaFinancieraTests(SimpleTestCase):
    """Regresión del nuevo cálculo; no es una validación del ML."""

    def datos_automaticos(self):
        return {
            **DATOS_VALIDOS_CON_CEROS,
            'modo_captura': 'AUTOMATICO',
            'ingreso_mensual_bruto_gs': 10_000_000,
            'cantidad_creditos_activos': 3,
            'creditos_inmobiliarios': 1,
            'cuota_hipotecaria_gs': 1_600_000,
            'cuota_prestamos_personales_gs': 700_000,
            'pago_mensual_tarjetas_gs': 200_000,
            'saldo_lineas_utilizado_gs': 4_000_000,
            'limite_lineas_total_gs': 10_000_000,
        }

    def test_calculo_automatico_y_origen_almacenable(self):
        form = EvaluacionScoringForm(data=self.datos_automaticos())
        self.assertTrue(form.is_valid(), form.errors)
        datos = form.datos_para_modelo()
        self.assertEqual(len(datos), 10)
        self.assertAlmostEqual(datos['relacion_deuda_ingreso'], 0.25)
        self.assertAlmostEqual(datos['utilizacion_lineas'], 0.4)
        self.assertEqual(form.detalle_captura['modalidad'], 'CALCULO_AUTOMATICO')
        self.assertEqual(form.detalle_captura['total_cuotas_mensuales_gs'], 2_500_000)
        self.assertEqual(form.detalle_captura['desglose_gs']['saldo_lineas_utilizado_gs'], 4_000_000)
        # El navegador no puede inyectar indicadores directos mientras está en automático.
        self.assertNotEqual(datos['relacion_deuda_ingreso'],
                            self.datos_automaticos()['relacion_deuda_ingreso'])

    def test_directo_con_fuente_declarada(self):
        datos = {**DATOS_VALIDOS_CON_CEROS, 'relacion_deuda_ingreso': 0.37}
        form = EvaluacionScoringForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.datos_para_modelo()['relacion_deuda_ingreso'], 0.37)
        self.assertEqual(form.detalle_captura['modalidad'], 'INGRESO_DIRECTO')
        self.assertIsNone(form.detalle_captura['desglose_gs'])

    def test_directo_requiere_fuente_y_ambos_indicadores(self):
        datos = {**DATOS_VALIDOS_CON_CEROS, 'fuente_indicadores': '', 'utilizacion_lineas': ''}
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('fuente_indicadores', form.errors)
        self.assertIn('utilizacion_lineas', form.errors)

    def test_automatico_requiere_importes_incluso_si_son_cero(self):
        datos = self.datos_automaticos()
        datos.pop('pago_mensual_tarjetas_gs')
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('pago_mensual_tarjetas_gs', form.errors)

    def test_saldo_sin_limite_no_valido(self):
        datos = self.datos_automaticos()
        datos['limite_lineas_total_gs'] = 0
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('limite_lineas_total_gs', form.errors)

    def test_sin_lineas_y_sin_saldo_es_utilizacion_cero(self):
        datos = self.datos_automaticos()
        datos.update({'saldo_lineas_utilizado_gs': 0, 'limite_lineas_total_gs': 0})
        form = EvaluacionScoringForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.datos_para_modelo()['utilizacion_lineas'], 0)

    def test_inmobiliarios_mayor_total_se_rechaza_en_ambos_modos(self):
        for datos in (self.datos_automaticos(), DATOS_VALIDOS_CON_CEROS):
            with self.subTest(modo=datos['modo_captura']):
                form = EvaluacionScoringForm(data={**datos, 'cantidad_creditos_activos': 1,
                                                   'creditos_inmobiliarios': 2})
                self.assertFalse(form.is_valid())
                self.assertIn('creditos_inmobiliarios', form.errors)

    def test_creditos_cero_con_utilizacion_no_se_acepta(self):
        datos = {**DATOS_VALIDOS_CON_CEROS, 'cantidad_creditos_activos': 0,
                 'utilizacion_lineas': 0.25}
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad_creditos_activos', form.errors)

    def test_no_acepta_dti_mayor_que_limite_del_modelo(self):
        datos = self.datos_automaticos()
        datos['cuota_hipotecaria_gs'] = 25_000_000
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('cuota_prestamos_personales_gs', form.errors)

    def test_dti_excesivo_no_produce_keyerror_y_preserva_desglose(self):
        datos = self.datos_automaticos()
        datos['cuota_prestamos_personales_gs'] = 25_000_000
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('cuota_prestamos_personales_gs', form.errors)
        self.assertEqual(form.detalle_captura['desglose_gs']['cuota_prestamos_personales_gs'], 25_000_000)
        self.assertGreater(form.detalle_captura['indicadores_calculados']['relacion_deuda_ingreso'], 2)

    def test_modalidad_ausente_no_se_acepta(self):
        datos = self.datos_automaticos()
        datos.pop('modo_captura')
        form = EvaluacionScoringForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('modo_captura', form.errors)


class ReglasCreditoTests(SimpleTestCase):
    def test_bandas_en_limites(self):
        self.assertEqual(obtener_banda(638).codigo, 'A')
        self.assertEqual(obtener_banda(637.99).codigo, 'B')
        self.assertEqual(obtener_banda(615).codigo, 'B')
        self.assertEqual(obtener_banda(577).codigo, 'C')
        self.assertEqual(obtener_banda(576.99).codigo, 'D')

    def test_capacidad_pago(self):
        capacidad = calcular_capacidad_pago(6_000_000, 0.25)
        self.assertAlmostEqual(capacidad['cuota_nueva_maxima_gs'], 900_000)

    def test_edad_reduce_plazo(self):
        self.assertEqual(obtener_plazo_permitido(73, 48), 24)
        self.assertEqual(obtener_plazo_permitido(74, 48), 12)
        self.assertIsNone(obtener_plazo_permitido(75, 48))

    def test_banda_d_no_tiene_oferta(self):
        r = evaluar_productos(score=550, edad=40, ingreso_gs=8_000_000, dti=0.10)
        self.assertEqual(r['banda'], 'D')
        self.assertEqual(r['ofertas'], [])

    def test_banda_b_tiene_estandar_y_basico(self):
        r = evaluar_productos(score=625, edad=40, ingreso_gs=6_000_000, dti=0.25)
        codigos = {o['codigo'] for o in r['ofertas']}
        self.assertEqual(codigos, {'estandar', 'basico'})


# Módulo incremental de solicitantes y decisiones.
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .forms import DecisionCreditoForm, SolicitanteForm
from .models import DecisionCredito, EvaluacionScoring, Solicitante


class SolicitanteYDecisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo, _ = Group.objects.get_or_create(name='ANALISTA')
        cls.analista = User.objects.create_user('analista1', password='DemoPassword123!')
        cls.analista.groups.add(grupo)
        cls.otro = User.objects.create_user('analista2', password='DemoPassword123!')
        cls.otro.groups.add(grupo)
        cls.admin = User.objects.create_superuser('admin', 'admin@example.invalid', 'DemoPassword123!')
        cls.solicitante = Solicitante.objects.create(
            cedula='0000001', nombres='Ana', apellidos='Ficticia',
            fecha_nacimiento=date(1990, 5, 14), ciudad='Asunción',
            ocupacion='Administrativa', situacion_laboral='DEPENDIENTE', creado_por=cls.analista,
        )
        cls.evaluacion = EvaluacionScoring.objects.create(
            usuario=cls.analista, solicitante=cls.solicitante,
            entradas={'datos_ingresados': DATOS_VALIDOS_CON_CEROS},
            pd=.04, score=710, banda='A', nivel_riesgo='Bajo',
            ofertas=[{'codigo': 'preferencial', 'producto': 'Crédito Preferencial',
                      'monto_preaprobado_gs': 10_000_000, 'plazo_meses': 24}],
        )

    def test_cedula_normalizada_y_campos_delimitados(self):
        form = SolicitanteForm(data={
            'cedula': ' 1.234-567 ', 'nombres': 'Ejemplo', 'apellidos': 'Simulado',
            'fecha_nacimiento': '1992-01-15', 'ciudad': 'Luque',
            'ocupacion': 'Comerciante', 'situacion_laboral': 'INDEPENDIENTE',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['cedula'], '1234567')
        self.assertNotIn('telefono', form.fields)
        self.assertNotIn('correo_electronico', form.fields)
        self.assertNotIn('antiguedad_laboral', form.fields)

    def test_no_permite_duplicar_cedula(self):
        form = SolicitanteForm(data={
            'cedula': '0.000.001', 'nombres': 'Otro', 'apellidos': 'Ficticio',
            'fecha_nacimiento': '1992-01-15', 'ciudad': 'Luque',
            'ocupacion': 'Comerciante', 'situacion_laboral': 'INDEPENDIENTE',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('cedula', form.errors)

    def test_no_permite_edad_incompatible(self):
        from .forms import edad_en_fecha
        from django.utils import timezone
        edad = edad_en_fecha(self.solicitante.fecha_nacimiento, timezone.localdate())
        form = EvaluacionScoringForm(data={**DATOS_VALIDOS_CON_CEROS, 'edad': edad + 1},
                                    edad_solicitante=edad)
        self.assertFalse(form.is_valid())
        self.assertIn('edad', form.errors)

    def test_permisos_de_consulta_entre_analistas(self):
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:evaluacion_detalle',
                                                 args=[self.evaluacion.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:solicitante_detalle',
                                                 args=[self.solicitante.pk])).status_code, 404)
        response = self.client.get(reverse('consulta_scoring_app:historial'))
        self.assertEqual(response.status_code, 200)
        # Comprobar la lista de registros, no texto ambiguo en CSS (p. ej. #1d4ed8).
        self.assertNotIn(self.evaluacion.pk, [e.pk for e in response.context['evaluaciones']])

    def test_superusuario_puede_consultar_todos(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('consulta_scoring_app:evaluacion_detalle',
                                               args=[self.evaluacion.pk]))
        self.assertEqual(response.status_code, 200)

    def test_decision_no_acepta_aprobacion_sin_oferta(self):
        evaluacion_sin_oferta = EvaluacionScoring.objects.create(
            usuario=self.analista, solicitante=self.solicitante,
            entradas={'datos_ingresados': {}}, pd=.7, score=500, banda='D', ofertas=[],
        )
        form = DecisionCreditoForm(data={
            'estado': 'APROBADA', 'producto_codigo': '',
            'motivo': 'Decisión simulada con fundamento.',
        }, evaluacion=evaluacion_sin_oferta)
        self.assertFalse(form.is_valid())
        self.assertIn('producto_codigo', form.errors)

    def test_decision_registrada_una_sola_vez(self):
        self.client.force_login(self.analista)
        url = reverse('consulta_scoring_app:registrar_decision', args=[self.evaluacion.pk])
        data = {
            'estado': 'APROBADA', 'producto_codigo': 'preferencial',
            'motivo': 'La evaluación cuenta con oferta elegible.',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DecisionCredito.objects.filter(evaluacion=self.evaluacion).count(), 1)
        self.client.post(url, data)
        self.assertEqual(DecisionCredito.objects.filter(evaluacion=self.evaluacion).count(), 1)
        self.evaluacion.refresh_from_db()
        self.assertEqual(self.evaluacion.score, 710)

    def test_otro_analista_no_puede_decidir(self):
        self.client.force_login(self.otro)
        response = self.client.post(
            reverse('consulta_scoring_app:registrar_decision', args=[self.evaluacion.pk]),
            {'estado': 'RECHAZADA', 'producto_codigo': '',
             'motivo': 'Motivo suficientemente detallado.'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(DecisionCredito.objects.filter(evaluacion=self.evaluacion).exists())

    @patch('consulta_scoring_app.views.evaluar_productos')
    @patch('consulta_scoring_app.views.evaluar')
    def test_evaluacion_vinculada_sin_alterar_motor(self, evaluar_mock, reglas_mock):
        from .forms import edad_en_fecha
        from django.utils import timezone
        edad = edad_en_fecha(self.solicitante.fecha_nacimiento, timezone.localdate())
        evaluar_mock.return_value = {
            'pd': .08, 'score': 680, 'features_modelo': {'edad': edad},
            'tipo_cambio_referencia_gs': 7500, 'advertencias': [], 'ingreso_modelo': 1066.67,
        }
        reglas_mock.return_value = {
            'banda': 'A', 'nivel_riesgo': 'Bajo',
            'capacidad': {'cuota_nueva_maxima_gs': 600000},
            'ofertas': [], 'motivo_sin_oferta': 'Ninguna oferta',
        }
        self.client.force_login(self.analista)
        response = self.client.post(
            reverse('consulta_scoring_app:evaluar_solicitante', args=[self.solicitante.pk]),
            {**DATOS_VALIDOS_CON_CEROS, 'edad': edad},
        )
        self.assertEqual(response.status_code, 200)
        nueva = EvaluacionScoring.objects.exclude(pk=self.evaluacion.pk).get()
        self.assertEqual(nueva.solicitante, self.solicitante)
        self.assertEqual(nueva.entradas['datos_ingresados']['edad'], edad)
        evaluar_mock.assert_called_once()
        reglas_mock.assert_called_once()


    @patch('consulta_scoring_app.views.evaluar_productos')
    @patch('consulta_scoring_app.views.evaluar')
    def test_scoring_automatico_conserva_desglose_y_vector_original(self, evaluar_mock, reglas_mock):
        from django.utils import timezone
        from .forms import edad_en_fecha
        edad = edad_en_fecha(self.solicitante.fecha_nacimiento, timezone.localdate())
        evaluar_mock.return_value = {
            'pd': .07, 'score': 689, 'features_modelo': {'edad': edad},
            'tipo_cambio_referencia_gs': 7500, 'advertencias': [], 'ingreso_modelo': 1333.33,
        }
        reglas_mock.return_value = {
            'banda': 'A', 'nivel_riesgo': 'Bajo',
            'capacidad': {'cuota_nueva_maxima_gs': 1_500_000},
            'ofertas': [], 'motivo_sin_oferta': 'Ninguna',
        }
        self.client.force_login(self.analista)
        response = self.client.post(
            reverse('consulta_scoring_app:evaluar_solicitante', args=[self.solicitante.pk]),
            {
                **DATOS_VALIDOS_CON_CEROS,
                'edad': edad, 'modo_captura': 'AUTOMATICO',
                'ingreso_mensual_bruto_gs': 10_000_000,
                'cantidad_creditos_activos': 3, 'creditos_inmobiliarios': 1,
                'cuota_hipotecaria_gs': 1_600_000, 'cuota_prestamos_personales_gs': 700_000,
                'pago_mensual_tarjetas_gs': 200_000, 'saldo_lineas_utilizado_gs': 4_000_000,
                'limite_lineas_total_gs': 10_000_000,
            },
        )
        self.assertEqual(response.status_code, 200)
        nueva = EvaluacionScoring.objects.exclude(pk=self.evaluacion.pk).get()
        self.assertAlmostEqual(nueva.entradas['datos_ingresados']['relacion_deuda_ingreso'], .25)
        self.assertAlmostEqual(nueva.entradas['datos_ingresados']['utilizacion_lineas'], .4)
        self.assertEqual(nueva.entradas['captura_financiera']['modalidad'], 'CALCULO_AUTOMATICO')
        self.assertEqual(nueva.entradas['captura_financiera']['total_cuotas_mensuales_gs'], 2_500_000)
        self.assertEqual(len(nueva.entradas['datos_ingresados']), 10)
        args, _ = evaluar_mock.call_args
        self.assertEqual(len(args[0]), 10)
        self.assertEqual(args[0]['relacion_deuda_ingreso'], .25)
        self.assertEqual(nueva.score, 689)



# Módulo incremental de roles, permisos efectivos y auditoría.
from .models import EventoAuditoria


class PermisosAuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.analista = User.objects.create_user('analista_audit', password='DemoPassword123!')
        cls.analista.groups.add(Group.objects.get_or_create(name='ANALISTA')[0])
        cls.analista2 = User.objects.create_user('analista2_audit', password='DemoPassword123!')
        cls.analista2.groups.add(Group.objects.get_or_create(name='ANALISTA')[0])
        cls.administrador = User.objects.create_user('admin_audit', password='DemoPassword123!')
        cls.administrador.groups.add(Group.objects.get_or_create(name='ADMINISTRADOR')[0])
        cls.auditor = User.objects.create_user('auditor_audit', password='DemoPassword123!')
        cls.auditor.groups.add(Group.objects.get_or_create(name='AUDITOR')[0])
        cls.sin_rol = User.objects.create_user('sin_rol_audit', password='DemoPassword123!')
        cls.solicitante = Solicitante.objects.create(
            cedula='9000090', nombres='Caso', apellidos='Ficticio',
            fecha_nacimiento=date(1992, 5, 4), ciudad='Luque',
            ocupacion='Dependiente', situacion_laboral='DEPENDIENTE', creado_por=cls.analista,
        )
        cls.evaluacion = EvaluacionScoring.objects.create(
            usuario=cls.analista, solicitante=cls.solicitante,
            entradas={'datos_ingresados': DATOS_VALIDOS_CON_CEROS}, pd=0.04, score=712,
            banda='A', ofertas=[{'codigo':'preferencial', 'producto': 'Preferencial'}],
        )

    def test_sin_rol_no_accede_ni_si_esta_autenticado(self):
        self.client.force_login(self.sin_rol)
        for url in [reverse('consulta_scoring_app:historial'),
                    reverse('consulta_scoring_app:solicitantes_lista'),
                    reverse('consulta_scoring_app:auditoria_lista')]:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(EventoAuditoria.objects.filter(
            usuario=self.sin_rol, accion=EventoAuditoria.Accion.ACCESO_DENEGADO,
            resultado=EventoAuditoria.Resultado.DENEGADO).count(), 3)

    def test_auditor_puede_leer_todos_pero_no_crear_o_decidir(self):
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:historial')).status_code, 200)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:evaluacion_detalle', args=[self.evaluacion.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:solicitante_detalle', args=[self.solicitante.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:auditoria_lista')).status_code, 200)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:solicitante_nuevo')).status_code, 403)
        self.assertEqual(self.client.post(reverse('consulta_scoring_app:registrar_decision', args=[self.evaluacion.pk]),
                                         {'estado':'RECHAZADA', 'motivo':'No autorizada'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:usuarios_lista')).status_code, 403)
        self.assertFalse(DecisionCredito.objects.filter(evaluacion=self.evaluacion).exists())

    def test_analista_no_puede_acceder_a_expedientes_ajenos_ni_auditoria(self):
        self.client.force_login(self.analista2)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:evaluacion_detalle', args=[self.evaluacion.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:solicitante_detalle', args=[self.solicitante.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:auditoria_lista')).status_code, 403)
        self.assertEqual(EventoAuditoria.objects.filter(usuario=self.analista2,
            accion=EventoAuditoria.Accion.ACCESO_DENEGADO).count(), 3)

    def test_administrador_no_decide_pero_puede_ver_auditoria(self):
        self.client.force_login(self.administrador)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:evaluacion_detalle', args=[self.evaluacion.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:auditoria_lista')).status_code, 200)
        self.assertEqual(self.client.post(reverse('consulta_scoring_app:registrar_decision', args=[self.evaluacion.pk]),
                                         {'estado':'RECHAZADA','motivo':'No corresponde'}).status_code, 403)

    def test_crear_solicitante_registra_evento_sin_cedula(self):
        self.client.force_login(self.analista)
        response = self.client.post(reverse('consulta_scoring_app:solicitante_nuevo'), {
            'cedula': '8.765.432', 'nombres': 'Ficticio', 'apellidos': 'Segundo',
            'fecha_nacimiento':'1993-06-14', 'ciudad':'Asunción',
            'ocupacion':'Comerciante', 'situacion_laboral':'INDEPENDIENTE',
        })
        self.assertEqual(response.status_code, 302)
        evento = EventoAuditoria.objects.get(accion=EventoAuditoria.Accion.SOLICITANTE_CREADO)
        self.assertEqual(evento.usuario, self.analista)
        self.assertEqual(evento.recurso, 'solicitante')
        self.assertNotIn('8765432', evento.detalle)
        self.assertEqual(evento.objeto_id, Solicitante.objects.get(cedula='8765432').pk)

    def test_decision_registra_auditoria_y_puntaje_sigue_igual(self):
        self.client.force_login(self.analista)
        r = self.client.post(reverse('consulta_scoring_app:registrar_decision', args=[self.evaluacion.pk]), {
            'estado': 'APROBADA', 'producto_codigo': 'preferencial',
            'motivo': 'La oferta simulada fue considerada adecuada.',
        })
        self.assertEqual(r.status_code, 302)
        decision = DecisionCredito.objects.get(evaluacion=self.evaluacion)
        evento = EventoAuditoria.objects.get(accion=EventoAuditoria.Accion.DECISION_CREADA)
        self.assertEqual(evento.usuario, self.analista)
        self.assertEqual(evento.objeto_id, decision.pk)
        self.evaluacion.refresh_from_db()
        self.assertEqual(self.evaluacion.score, 712)

    def test_administrador_asigna_rol_y_deja_rastro(self):
        self.client.force_login(self.administrador)
        r = self.client.post(reverse('consulta_scoring_app:usuario_cambiar_rol', args=[self.analista2.pk]),
                             {'rol':'AUDITOR'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.analista2.groups.filter(name='AUDITOR').exists())
        self.assertFalse(self.analista2.groups.filter(name='ANALISTA').exists())
        e = EventoAuditoria.objects.get(accion=EventoAuditoria.Accion.ROL_MODIFICADO)
        self.assertEqual(e.usuario, self.administrador)
        self.assertEqual(e.objeto_id, self.analista2.pk)
        self.assertIn('AUDITOR', e.detalle)

    def test_analista_no_puede_cambiar_roles(self):
        self.client.force_login(self.analista)
        response = self.client.post(reverse('consulta_scoring_app:usuario_cambiar_rol', args=[self.analista2.pk]),
                                    {'rol':'ADMINISTRADOR'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.analista2.groups.filter(name='ADMINISTRADOR').exists())

    def test_formulario_usuarios_incluye_auditor(self):
        from .forms import AltaUsuarioForm
        self.assertIn('AUDITOR', dict(AltaUsuarioForm.ROL_CHOICES))
        self.client.force_login(self.administrador)
        response = self.client.post(reverse('consulta_scoring_app:usuario_alta'), {
            'username':'tercero_auditor', 'first_name':'Persona', 'last_name':'De prueba',
            'rol':'AUDITOR', 'password1':'UnaClaveMuySegura123!!',
            'password2':'UnaClaveMuySegura123!!',
        })
        self.assertEqual(response.status_code, 302)
        auditor = User.objects.get(username='tercero_auditor')
        self.assertTrue(auditor.groups.filter(name='AUDITOR').exists())
        self.assertFalse(auditor.is_staff)
        self.assertTrue(EventoAuditoria.objects.filter(accion=EventoAuditoria.Accion.USUARIO_CREADO,
                                                       objeto_id=auditor.pk).exists())

    def test_auditoria_solo_lectura_y_filtros(self):
        EventoAuditoria.objects.create(
            usuario=self.analista, usuario_nombre=self.analista.username,
            accion=EventoAuditoria.Accion.SOLICITANTE_CREADO, recurso='solicitante',
            objeto_id=self.solicitante.pk,
        )
        self.client.force_login(self.auditor)
        response = self.client.get(reverse('consulta_scoring_app:auditoria_lista'),
                                   {'accion':'SOLICITANTE_CREADO', 'resultado':'EXITO'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ficha creada')


# Módulo 3: casos de prueba del seguimiento académico, sin créditos reales.
from datetime import timedelta
from django.utils import timezone
from .forms import SeguimientoCreditoForm
from .models import SeguimientoCredito


class SeguimientoCreditoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.analista = User.objects.create_user('analista_seguimiento', password='PruebaSegura!123')
        cls.analista.groups.add(Group.objects.get_or_create(name='ANALISTA')[0])
        cls.ajeno = User.objects.create_user('otro_seguimiento', password='PruebaSegura!123')
        cls.ajeno.groups.add(Group.objects.get_or_create(name='ANALISTA')[0])
        cls.admin = User.objects.create_user('admin_seguimiento', password='PruebaSegura!123')
        cls.admin.groups.add(Group.objects.get_or_create(name='ADMINISTRADOR')[0])
        cls.auditor = User.objects.create_user('auditor_seguimiento', password='PruebaSegura!123')
        cls.auditor.groups.add(Group.objects.get_or_create(name='AUDITOR')[0])
        cls.solicitante = Solicitante.objects.create(
            cedula='9090909', nombres='Solicitud', apellidos='Demostracion',
            fecha_nacimiento=date(1992, 3, 8), ciudad='Luque',
            ocupacion='Dependiente', situacion_laboral='DEPENDIENTE',
            creado_por=cls.analista,
        )
        cls.evaluacion = EvaluacionScoring.objects.create(
            usuario=cls.analista, solicitante=cls.solicitante,
            entradas={'datos_ingresados': DATOS_VALIDOS_CON_CEROS},
            pd=.03, score=720, banda='A', ofertas=[{'codigo': 'preferencial', 'producto': 'Preferencial'}],
        )
        cls.decision = DecisionCredito.objects.create(
            evaluacion=cls.evaluacion, estado='APROBADA', producto_codigo='preferencial',
            motivo='Se aprueba únicamente como parte del prototipo académico.',
            usuario=cls.analista,
        )
        cls.rechazada = EvaluacionScoring.objects.create(
            usuario=cls.analista, solicitante=cls.solicitante,
            entradas={'datos_ingresados': DATOS_VALIDOS_CON_CEROS},
            pd=.50, score=500, banda='D', ofertas=[],
        )
        cls.rechazo = DecisionCredito.objects.create(
            evaluacion=cls.rechazada, estado='RECHAZADA',
            motivo='Rechazo de demostración por riesgo muy elevado.', usuario=cls.analista,
        )

    def datos(self, **overrides):
        hoy = timezone.localdate()
        datos = {
            'fecha_otorgamiento': hoy.isoformat(),
            'fecha_cierre_prevista': (hoy + timedelta(days=1095)).isoformat(),
            'fecha_observacion': hoy.isoformat(),
            'estado': 'VIGENTE',
            'max_dias_mora': '0',
            'observaciones': 'Crédito ficticio de demostración.',
        }
        datos.update(overrides)
        return datos

    def crear_desde_vista(self):
        self.client.force_login(self.analista)
        r = self.client.post(
            reverse('consulta_scoring_app:seguimiento_nuevo', args=[self.evaluacion.pk]), self.datos(),
        )
        self.assertEqual(r.status_code, 302)
        return SeguimientoCredito.objects.get(decision=self.decision)

    def test_crear_aprobado_guarda_vencimiento_futuro_y_audita(self):
        seg = self.crear_desde_vista()
        self.assertEqual(seg.max_dias_mora, 0)
        self.assertGreater(seg.fecha_cierre_prevista, timezone.localdate())
        self.assertEqual(seg.creado_por, self.analista)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion=EventoAuditoria.Accion.SEGUIMIENTO_CREADO,
            objeto_id=seg.pk, usuario=self.analista,
        ).exists())
        self.evaluacion.refresh_from_db()
        self.assertEqual(self.evaluacion.score, 720)
        self.assertEqual(self.evaluacion.pd, .03)

    def test_no_permite_seguimiento_de_rechazado(self):
        self.client.force_login(self.analista)
        r = self.client.post(
            reverse('consulta_scoring_app:seguimiento_nuevo', args=[self.rechazada.pk]), self.datos(),
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SeguimientoCredito.objects.filter(decision=self.rechazo).exists())
        form = SeguimientoCreditoForm(data=self.datos(), decision=self.rechazo)
        self.assertFalse(form.is_valid())

    def test_un_seguimiento_por_decision(self):
        seg = self.crear_desde_vista()
        r = self.client.post(
            reverse('consulta_scoring_app:seguimiento_nuevo', args=[self.evaluacion.pk]), self.datos(),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SeguimientoCredito.objects.filter(decision=self.decision).count(), 1)
        self.assertEqual(seg.pk, SeguimientoCredito.objects.get(decision=self.decision).pk)

    def test_fecha_futura_y_mora_imposible_son_rechazadas(self):
        hoy = timezone.localdate()
        casos = [
            self.datos(fecha_observacion=(hoy + timedelta(days=1)).isoformat()),
            self.datos(fecha_cierre_prevista=(hoy - timedelta(days=1)).isoformat()),
            self.datos(max_dias_mora='40'),
            self.datos(estado='VENCIDO'),
        ]
        for datos in casos:
            form = SeguimientoCreditoForm(data=datos, decision=self.decision)
            self.assertFalse(form.is_valid(), datos)

    def test_auditor_solo_consulta_y_analista_ajeno_no_accede(self):
        seg = self.crear_desde_vista()
        url = reverse('consulta_scoring_app:seguimiento_detalle', args=[seg.pk])
        url_cambio = reverse('consulta_scoring_app:seguimiento_actualizar', args=[seg.pk])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url_cambio, self.datos()).status_code, 404)
        self.assertTrue(EventoAuditoria.objects.filter(
            usuario=self.ajeno, accion=EventoAuditoria.Accion.ACCESO_DENEGADO,
        ).exists())
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url_cambio, self.datos()).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url_cambio, self.datos()).status_code, 403)

    def test_busqueda_por_cedula_sin_repetir_cedula_en_seguimiento(self):
        seg = self.crear_desde_vista()
        self.client.force_login(self.analista)
        r = self.client.get(reverse('consulta_scoring_app:seguimientos_lista'),
                            {'ci': '9.090.909', 'estado': 'VIGENTE'})
        self.assertEqual(r.status_code, 200)
        # Verificar exactamente los IDs retornados, sin coincidencias con estilos CSS.
        self.assertIn(seg.pk, [item.pk for item in r.context['seguimientos']])
        r = self.client.get(reverse('consulta_scoring_app:seguimientos_lista'),
                            {'ci': '9.999.999'})
        self.assertNotIn(seg.pk, [item.pk for item in r.context['seguimientos']])

    def test_actualizacion_queda_auditada_y_no_modifica_score(self):
        self.crear_desde_vista()
        seg = SeguimientoCredito.objects.get(decision=self.decision)
        self.client.force_login(self.analista)
        datos = self.datos(estado='CANCELADO', observaciones='Crédito cancelado de ejemplo.')
        r = self.client.post(reverse('consulta_scoring_app:seguimiento_actualizar', args=[seg.pk]), datos)
        self.assertEqual(r.status_code, 302)
        seg.refresh_from_db()
        self.assertEqual(seg.estado, 'CANCELADO')
        evento = EventoAuditoria.objects.get(accion=EventoAuditoria.Accion.SEGUIMIENTO_ACTUALIZADO)
        self.assertIn('VIGENTE->CANCELADO', evento.detalle)
        self.assertNotIn('9090909', evento.detalle)
        self.evaluacion.refresh_from_db()
        self.assertEqual(self.evaluacion.score, 720)

    def test_no_se_permite_volver_de_cancelado_a_vigente(self):
        self.crear_desde_vista()
        seg = SeguimientoCredito.objects.get(decision=self.decision)
        seg.estado = 'CANCELADO'
        seg.save(update_fields=['estado'])
        form = SeguimientoCreditoForm(data=self.datos(estado='VIGENTE'), instance=seg, decision=self.decision)
        self.assertFalse(form.is_valid())
        self.assertIn('estado', form.errors)


    def test_caso_historico_ficticio_permite_vencido_y_rechaza_mora_decreciente(self):
        # Solo preparación de fixture: desplazar la decisión hacia el pasado
        # para poder demostrar un escenario histórico sin falsear fechas futuras.
        hoy = timezone.localdate()
        DecisionCredito.objects.filter(pk=self.decision.pk).update(
            fecha_hora=timezone.now() - timedelta(days=151),
        )
        self.decision.refresh_from_db()
        inicio = hoy - timedelta(days=140)
        cierre = hoy - timedelta(days=45)
        observacion = hoy - timedelta(days=3)
        datos = self.datos(
            fecha_otorgamiento=inicio.isoformat(),
            fecha_cierre_prevista=cierre.isoformat(),
            fecha_observacion=observacion.isoformat(),
            estado='VENCIDO', max_dias_mora='24',
        )
        self.client.force_login(self.analista)
        r = self.client.post(reverse('consulta_scoring_app:seguimiento_nuevo',
                                     args=[self.evaluacion.pk]), datos)
        self.assertEqual(r.status_code, 302)
        seg = SeguimientoCredito.objects.get(decision=self.decision)
        self.assertEqual(seg.estado, 'VENCIDO')
        self.assertEqual(seg.max_dias_mora, 24)
        # La fecha de otorgamiento y el cierre previsto son inmutables
        # y el máximo histórico de mora no puede retroceder.
        datos_invalidos = {
            **datos, 'fecha_otorgamiento': hoy.isoformat(),
            'fecha_cierre_prevista': (hoy + timedelta(days=10)).isoformat(),
            'fecha_observacion': hoy.isoformat(), 'estado': 'CANCELADO',
            'max_dias_mora': '5',
        }
        form = SeguimientoCreditoForm(data=datos_invalidos, instance=seg, decision=self.decision)
        self.assertFalse(form.is_valid())
        self.assertIn('max_dias_mora', form.errors)
        self.client.post(reverse('consulta_scoring_app:seguimiento_actualizar',
                                 args=[seg.pk]), datos_invalidos)
        seg.refresh_from_db()
        self.assertEqual(seg.fecha_otorgamiento, inicio)
        self.assertEqual(seg.fecha_cierre_prevista, cierre)
        self.assertEqual(seg.max_dias_mora, 24)


# ---- Módulo 4: pruebas incluidas para la verificación integral posterior ----
import json
import tempfile
from pathlib import Path

from django.test import override_settings

from .services.indicadores_service import (
    ReporteInvalido, validar_reporte, leer_reporte_validacion,
)


class IndicadoresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        analista, _ = Group.objects.get_or_create(name='ANALISTA')
        auditor, _ = Group.objects.get_or_create(name='AUDITOR')
        cls.a = User.objects.create_user('ind_analista', password='Prueba123456!')
        cls.a.groups.add(analista)
        cls.b = User.objects.create_user('ind_otro', password='Prueba123456!')
        cls.b.groups.add(analista)
        cls.auditor = User.objects.create_user('ind_auditor', password='Prueba123456!')
        cls.auditor.groups.add(auditor)
        cls.desprovisto = User.objects.create_user('ind_sinrol', password='Prueba123456!')
        cls.e1 = EvaluacionScoring.objects.create(
            usuario=cls.a, pd=.1, score=720, banda='A', entradas={},
        )
        cls.e2 = EvaluacionScoring.objects.create(
            usuario=cls.a, pd=.2, score=620, banda='B', entradas={},
        )
        cls.e3 = EvaluacionScoring.objects.create(
            usuario=cls.b, pd=.8, score=440, banda='D', entradas={},
        )
        DecisionCredito.objects.create(
            evaluacion=cls.e1, estado='APROBADA', producto_codigo='basico',
            motivo='Decisión simulada documentada', usuario=cls.a,
        )
        DecisionCredito.objects.create(
            evaluacion=cls.e3, estado='RECHAZADA',
            motivo='Decisión simulada documentada', usuario=cls.b,
        )

    def test_analista_ve_solo_sus_estadisticas(self):
        self.client.force_login(self.a)
        response = self.client.get(reverse('consulta_scoring_app:indicadores'))
        self.assertEqual(response.status_code, 200)
        data = response.context['operaciones']
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['con_decision'], 1)
        self.assertEqual(data['pendientes'], 1)
        self.assertEqual(data['promedio_score'], 670)
        self.assertEqual([r['cantidad'] for r in data['bandas'][:4]], [1, 1, 0, 0])
        self.assertEqual(sum(r['cantidad'] for r in data['decisiones']), 2)

    def test_auditor_ve_global_pero_no_modifica(self):
        self.client.force_login(self.auditor)
        response = self.client.get(reverse('consulta_scoring_app:indicadores'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['operaciones']['total'], 3)
        self.assertEqual(response.context['operaciones']['con_decision'], 2)
        self.assertTrue(response.context['vista_global'])

    def test_sin_rol_se_deniega_y_registra(self):
        self.client.force_login(self.desprovisto)
        response = self.client.get(reverse('consulta_scoring_app:indicadores'))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(EventoAuditoria.objects.filter(
            usuario=self.desprovisto, accion=EventoAuditoria.Accion.ACCESO_DENEGADO,
            recurso='indicadores',
        ).exists())

    def test_consulta_autorizada_registra_auditoria(self):
        self.client.force_login(self.a)
        self.client.get(reverse('consulta_scoring_app:indicadores'))
        self.assertEqual(EventoAuditoria.objects.filter(
            usuario=self.a, accion=EventoAuditoria.Accion.INDICADORES_CONSULTADOS,
        ).count(), 1)


class ReporteValidacionTests(SimpleTestCase):
    datos = {
        'modelo_version': 'credit_score_v1',
        'dataset': 'Conjunto de prueba de ejemplo académico',
        'particion': 'test separado',
        'definicion_evento': 'mora en horizonte definido',
        'fecha_validacion': '2026-10-11',
        'muestra_n': 200,
        'auc_roc': .80, 'gini': .60, 'ks': .45, 'brier': None,
    }

    def test_reporte_consistente(self):
        validado = validar_reporte(self.datos)
        self.assertEqual(validado['gini'], .6)
        self.assertIsNone(validado['brier'])

    def test_no_acepta_valores_inconsistentes(self):
        from copy import deepcopy
        datos = deepcopy(self.datos)
        datos['gini'] = .9
        with self.assertRaises(ReporteInvalido):
            validar_reporte(datos)

    def test_no_acepta_metrica_no_medida(self):
        datos = {**self.datos, 'auc_roc': None, 'gini': None, 'ks': None}
        with self.assertRaises(ReporteInvalido):
            validar_reporte(datos)

    def test_reporte_pendiente_sin_archivo(self):
        with tempfile.TemporaryDirectory() as temp:
            with override_settings(MODEL_VALIDATION_REPORT_PATH=Path(temp) / 'sin_reporte.json'):
                datos, error = leer_reporte_validacion()
        self.assertIsNone(datos)
        self.assertIsNone(error)

    def test_importa_reporte_solo_cuando_valido(self):
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / 'reporte.json'
            ruta.write_text(json.dumps(self.datos), encoding='utf-8')
            with override_settings(MODEL_VALIDATION_REPORT_PATH=ruta):
                datos, error = leer_reporte_validacion()
        self.assertIsNone(error)
        self.assertEqual(datos['auc_roc'], .8)


# V2.7: prueba de flujo transversal (Django, base temporal de test y ML simulado).
class FlujoIntegralAcademicoTests(TestCase):
    @patch('consulta_scoring_app.views.evaluar_productos')
    @patch('consulta_scoring_app.views.evaluar')
    def test_ficha_scoring_decision_seguimiento_dashboard_auditoria(self, evaluar_mock, reglas_mock):
        from django.utils import timezone
        from datetime import timedelta
        from .forms import edad_en_fecha
        analista = User.objects.create_user('flujo_analista', password='Clave!Seguro2026')
        analista.groups.add(Group.objects.get_or_create(name='ANALISTA')[0])
        auditor = User.objects.create_user('flujo_auditor', password='Clave!Seguro2026')
        auditor.groups.add(Group.objects.get_or_create(name='AUDITOR')[0])
        self.client.force_login(analista)
        hoy = timezone.localdate()
        nacimiento = date(hoy.year - 35, hoy.month, min(hoy.day, 28))
        r = self.client.post(reverse('consulta_scoring_app:solicitante_nuevo'), {
            'cedula':'8.800.001','nombres':'Perfil','apellidos':'Ficticio',
            'fecha_nacimiento':nacimiento.isoformat(),'ciudad':'Asunción',
            'ocupacion':'Empleado','situacion_laboral':'DEPENDIENTE',
        })
        self.assertEqual(r.status_code, 302)
        solicitante = Solicitante.objects.get(cedula='8800001')
        edad = edad_en_fecha(nacimiento, hoy)
        evaluar_mock.return_value = {
            'pd': .04, 'score': 705, 'features_modelo': {'edad':edad},
            'tipo_cambio_referencia_gs': 7500, 'advertencias': [], 'ingreso_modelo': 1000,
        }
        reglas_mock.return_value = {
            'banda':'A','nivel_riesgo':'Bajo',
            'capacidad':{'cuota_nueva_maxima_gs':900_000},
            'ofertas':[{'codigo':'preferencial','producto':'Preferencial',
                        'monto_preaprobado_gs':10_000_000,'plazo_meses':24}],
            'motivo_sin_oferta':'',
        }
        r = self.client.post(reverse('consulta_scoring_app:evaluar_solicitante',args=[solicitante.pk]),{
            **DATOS_VALIDOS_CON_CEROS,'edad':edad,
        })
        self.assertEqual(r.status_code, 200)
        evaluacion = EvaluacionScoring.objects.get(solicitante=solicitante)
        self.assertEqual(evaluacion.score,705)
        r = self.client.post(reverse('consulta_scoring_app:registrar_decision',args=[evaluacion.pk]),{
            'estado':'APROBADA','producto_codigo':'preferencial',
            'motivo':'Decisión ficticia basada en oferta disponible.',
        })
        self.assertEqual(r.status_code,302)
        decision = DecisionCredito.objects.get(evaluacion=evaluacion)
        self.assertEqual(decision.estado,'APROBADA')
        r = self.client.post(reverse('consulta_scoring_app:seguimiento_nuevo',args=[evaluacion.pk]),{
            'fecha_otorgamiento':hoy.isoformat(),
            'fecha_cierre_prevista':date(2029,10,12).isoformat(),
            'fecha_observacion':hoy.isoformat(), 'estado':'VIGENTE',
            'max_dias_mora':'0','observaciones':'Caso ficticio de seguimiento.',
        })
        self.assertEqual(r.status_code,302)
        seguimiento = SeguimientoCredito.objects.get(decision=decision)
        self.assertEqual(seguimiento.max_dias_mora,0)
        r = self.client.get(reverse('consulta_scoring_app:indicadores'))
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.context['operaciones']['con_decision'],1)
        self.assertEqual(r.context['operaciones']['total'],1)
        self.client.force_login(auditor)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:seguimiento_detalle',
                                                  args=[seguimiento.pk])).status_code,200)
        self.assertEqual(self.client.post(reverse('consulta_scoring_app:seguimiento_actualizar',
                                                   args=[seguimiento.pk]),{}).status_code,403)
        self.assertEqual(self.client.get(reverse('consulta_scoring_app:auditoria_lista')).status_code,200)
        eventos = EventoAuditoria.objects.filter(usuario=analista)
        for accion in ('SOLICITANTE_CREADO','EVALUACION_CREADA','DECISION_CREADA',
                       'SEGUIMIENTO_CREADO','INDICADORES_CONSULTADOS'):
            self.assertTrue(eventos.filter(accion=accion).exists(),accion)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.score,705)
