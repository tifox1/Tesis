import duckdb

# 1. Conectar a la base de datos (creará el archivo persistente)
con = duckdb.connect(r"D:\Archivos\TESIS\db\tesis.db")

# 2. Crear las estructuras de las tablas
con.execute("""
CREATE TABLE IF NOT EXISTS datos_personales (
    numero_ci VARCHAR PRIMARY KEY,
    edad INTEGER,
    tipo_vivienda VARCHAR,
    antiguedad_vivienda INTEGER,
    situacion_laboral VARCHAR,
    antiguedad_laboral INTEGER,
    ingreso_neto_mensual DOUBLE,
    total_cuotas_deudas_actuales DOUBLE,
    relacion_deuda_ingreso DOUBLE
);
""")
# numero_ci,score_bruto_actual,cantidad_creditos_activos,saldo_deuda,peor_atraso,cantidad_cuentas_en_mora,perfil_riesgo
con.execute("""
CREATE TABLE IF NOT EXISTS datos_buro (
    numero_ci VARCHAR PRIMARY KEY,
    score_bruto_actual DOUBLE,
    cantidad_creditos_activos INTEGER,
    saldo_deuda DOUBLE,
    peor_atraso DOUBLE,
    cantidad_cuentas_en_mora INTEGER,
    perfil_riesgo VARCHAR,
    FOREIGN KEY (numero_ci) REFERENCES datos_personales(numero_ci)
);
""")

# Limpiamos las tablas en caso de que corras este script varias veces (para no duplicar datos)
con.execute("TRUNCATE TABLE datos_buro;")
con.execute("TRUNCATE TABLE datos_personales;")

# 3. INGESTA NATIVA DESDE CSV A DUCKDB
# Usamos read_csv y forzamos que 'numero_ci' sea texto para no perder ceros a la izquierda
print("⏳ Cargando datos desde los archivos CSV...")

con.execute("""
    INSERT INTO datos_personales 
    SELECT * FROM read_csv('D:/Archivos/TESIS/datasets/datos_personales.csv', header=True, types={'numero_ci': 'VARCHAR'});
""")

con.execute("""
    INSERT INTO datos_buro 
    SELECT * FROM read_csv('D:/Archivos/TESIS/datasets/buro_credito.csv', header=True, types={'numero_ci': 'VARCHAR'});
""")
print("✅ ¡Archivos CSV cargados exitosamente en la base de datos!")

# 4. Consultar y extraer los datos listos para tu modelo (como un DataFrame de Pandas)
print("\n=== MUESTRA DEL DATASET UNIFICADO ===")
resultado_unificado = con.execute("""
    SELECT 
        p.numero_ci,
        p.edad,
        p.ingreso_neto_mensual,
        b.score_bruto_actual,
        b.perfil_riesgo
    FROM datos_personales p
    LEFT JOIN datos_buro b ON p.numero_ci = b.numero_ci
""").df()

print(resultado_unificado)

# Cerrar conexión
con.close()