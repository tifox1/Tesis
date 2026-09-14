
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








-- perfiles buenos
-- ┌───────────┬────────────────────┬───────────────┬───┬─────────────┬─────────────┬──────────────────────────┐
-- │ numero_ci │ score_bruto_actual │ perfil_riesgo │ … │ saldo_deuda │ peor_atraso │ cantidad_cuentas_en_mora │
-- │  varchar  │       int32        │    varchar    │ … │   double    │    int32    │          int32           │
-- ├───────────┼────────────────────┼───────────────┼───┼─────────────┼─────────────┼──────────────────────────┤
-- │ 5501094   │                850 │ excelente     │ … │    21653.44 │           0 │                        0 │
-- │ 3299167   │                850 │ excelente     │ … │     7122.09 │           0 │                        0 │
-- │ 6590337   │                850 │ excelente     │ … │     8692.14 │           0 │                        0 │
-- │ 6556920   │                848 │ excelente     │ … │     3996.76 │           0 │                        0 │
-- │ 5790237   │                848 │ excelente     │ … │     5146.74 │           0 │                        0 │
-- │ 2325761   │                844 │ excelente     │ … │     4522.93 │           0 │                        0 │
-- │ 6995511   │                844 │ excelente     │ … │      5468.1 │           0 │                        0 │
-- │ 6230394   │                843 │ excelente     │ … │    13594.53 │           0 │                        0 │
-- │ 4143909   │                843 │ excelente     │ … │     4665.23 │           0 │                        0 │
-- │ 9835919   │                843 │ excelente     │ … │     9322.76 │           0 │                        0 │
-- └───────────┴────────────────────┴───────────────┴───┴─────────────┴─────────────┴──────────────────────────┘
--   10 rows                        use .last to show entire result                        7 columns (6 shown)