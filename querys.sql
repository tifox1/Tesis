
-- Conectar a la DB
-- .open 'D:\Archivos\TESIS\db\tesis.db'

-- query para la alimentacion del modelo
SELECT 
    A.edad,
    A.tipo_vivienda,
    A.antiguedad_vivienda,
    A.situacion_laboral,
    A.antiguedad_laboral,
    A.ingreso_neto_mensual,
    A.total_cuotas_deudas_actuales,
    A.relacion_deuda_ingreso,
    B.score_bruto_actual,
    B.cantidad_creditos_activos,
    B.saldo_deuda,
    B.peor_atraso,
    B.cantidad_cuentas_en_mora,
    B.perfil_riesgo,
FROM datos_personales A
    LEFT JOIN datos_buro B ON A.numero_ci = B.numero_ci


-- CI PRUEBAS 
--     │ 1419610   │
-- │ 1533224

--                    numero_ci = 1419610
--                         edad = 41
--                tipo_vivienda = propia
--          antiguedad_vivienda = 9
--            situacion_laboral = empleado_informal
--           antiguedad_laboral = 4
--         ingreso_neto_mensual = 2918.15
-- total_cuotas_deudas_actuales = 1051.6
--       relacion_deuda_ingreso = 0.3604

--                    numero_ci = 1533224
--                         edad = 40
--                tipo_vivienda = propia
--          antiguedad_vivienda = 3
--            situacion_laboral = empleado_formal
--           antiguedad_laboral = 7
--         ingreso_neto_mensual = 1935.3
-- total_cuotas_deudas_actuales = 613.96
--       relacion_deuda_ingreso = 0.3172





