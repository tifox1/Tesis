
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







