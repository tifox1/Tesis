# Sistema de apoyo a decisiones crediticias — V2.9 (módulos 1–4 y captura financiera)

## 1. Alcance

El prototipo es un **sistema de apoyo a decisiones crediticias** para personas físicas. Un usuario interno carga datos previamente comprobados, el modelo calcula **PD y score**, y una capa separada de reglas de negocio determina una **banda de riesgo** y alternativas de crédito preaprobadas.

No es un core bancario, no desembolsa créditos y no reemplaza la decisión del analista.

## 2. Flujo general

1. El usuario interno inicia sesión.
2. El analista busca por cédula una ficha ficticia o registra un nuevo solicitante.
3. En una ficha, el analista elige captura automática de DTI/utilización desde el desglose financiero, o carga directa de ambos indicadores con fuente declarada. La edad se deriva del nacimiento. Se mantiene el vector de diez variables del modelo.
4. El ingreso se carga en **guaraníes** y se transforma internamente a la escala monetaria asumida por el modelo.
5. `scoring_service.py` ejecuta el `.joblib` y obtiene PD + score.
6. `credit_rules.py` asigna banda, estima capacidad de pago, aplica edad al vencimiento y evalúa tres productos simulados.
7. Django muestra el resultado y registra la evaluación en SQLite.

La inferencia del modelo y las reglas comerciales permanecen separadas.

## 3. Una sola base de datos: SQLite

Se eliminó DuckDB y no se utiliza PostgreSQL en esta versión.

SQLite almacena información operativa del prototipo:

- usuarios, grupos, autenticación y sesiones de Django;
- evaluaciones realizadas;
- usuario que ejecutó cada evaluación;
- ficha ficticia de solicitante (cédula, nombres, apellidos, nacimiento, ciudad, ocupación y situación laboral);
- vínculo entre solicitantes, evaluaciones y decisiones humanas simuladas;
- PD, score, banda, capacidad estimada y ofertas resultantes.

`data/cs-training.csv` **no es una base operativa**. Se conserva únicamente como fuente original utilizada durante el desarrollo/entrenamiento del modelo.

## 4. Usuarios

Se mantienen tres roles:

- `ANALISTA`: registra solicitantes y evaluaciones propias, decisiones y seguimientos simulados autorizados.
- `ADMINISTRADOR`: administra usuarios y roles; consulta expedientes e indicadores globales.
- `AUDITOR`: consulta expedientes e indicadores y revisa eventos de auditoría, sin modificar decisiones.

El primer administrador se crea con:

```bash
python manage.py createsuperuser
```

## 5. Modelo de credit scoring

Artefacto:

`artifacts/credit_score_modelo_final.joblib`

Fue serializado con scikit-learn 1.9.0; `requirements.txt` fija esa versión.

El modelo produce:

- PD estimada del evento objetivo;
- score en escala 300–850.

El `.joblib` no conoce productos, tasas, montos, capacidad de pago ni decisiones comerciales.

### Variables del modelo

- edad
- ingreso_neto_mensual (nombre técnico heredado del artefacto)
- relacion_deuda_ingreso
- utilizacion_lineas
- atraso_30_59
- atraso_60_89
- atraso_90_plus
- cantidad_creditos_activos
- creditos_inmobiliarios
- dependientes

En la aplicación el analista introduce **ingreso mensual bruto en guaraníes**. Internamente se convierte al valor `ingreso_neto_mensual` requerido por el artefacto.

## 6. Normalización monetaria

La documentación original de `MonthlyIncome` no especifica explícitamente la moneda. Para adaptar el prototipo al contexto paraguayo se adopta un **supuesto operacional fijo**:

```text
TIPO_CAMBIO_REFERENCIA_GS = 7.500
```

La aplicación calcula:

```text
ingreso_modelo = ingreso_bruto_gs / 7.500
```

Este valor es un supuesto académico de normalización, no una cotización oficial ni un mecanismo de actualización cambiaria. No se utiliza API de cotizaciones.

## 7. Bandas de riesgo

Las bandas se definieron a partir del comportamiento observado del conjunto de test:

| Banda | Score | Interpretación |
|---|---:|---|
| A | >= 638 | Riesgo bajo |
| B | 615–637,99 | Riesgo moderado |
| C | 577–614,99 | Riesgo elevado |
| D | < 577 | Riesgo muy elevado |

La banda no equivale por sí sola a aprobación o rechazo.

## 8. Capacidad de pago

Política simulada del prototipo:

```text
Carga financiera total máxima = 40 % del ingreso mensual bruto
```

El DTI se utiliza como aproximación de la carga financiera existente:

```text
carga_existente ~= ingreso * DTI
cuota_nueva_maxima = max(0, ingreso * 0,40 - carga_existente)
```

El 40 % es una regla interna simulada; no se presenta como una obligación general del BCP.

## 9. Edad al vencimiento

Política simulada:

```text
Edad máxima al vencimiento = 75 años
```

La edad no modifica el `.joblib`. Se aplica luego del scoring como regla de elegibilidad. Si un plazo largo no es posible, se intenta un plazo estándar menor (48, 36, 24 o 12 meses según el producto).

## 10. Productos simulados

| Producto | Bandas | TEA simulada | Plazo máx. | Monto máx. |
|---|---|---:|---:|---:|
| Crédito Preferencial | A | 16 % | 48 meses | Gs. 80.000.000 |
| Crédito Estándar | A, B | 19 % | 36 meses | Gs. 40.000.000 |
| Crédito Básico | A, B, C | 23 % | 24 meses | Gs. 15.000.000 |
| Sin oferta | D | — | — | — |

Son productos académicos simulados, no productos de una entidad real.

El monto preaprobado es el menor entre:

1. el monto financiable según cuota, tasa y plazo;
2. el monto máximo del producto.

## 11. Referencia regulatoria mínima

El prototipo se plantea como si fuera utilizado por una entidad bancaria o financiera supervisada por la Superintendencia de Bancos del BCP.

Durante el diseño se verificó el límite de tasa usuraria para **moneda nacional de octubre de 2026: 27,26 % efectiva anual**. Las tres tasas simuladas están por debajo de esa referencia. La aplicación no consulta al BCP ni actualiza este valor automáticamente; antes de un uso real la normativa y los límites vigentes deberían revisarse.

Fuente de referencia: Banco Central del Paraguay, Límites para Tasas Usurarias, octubre 2026.

También se mantiene una presentación básica de monto, tasa, plazo, cuota y total estimado de cuotas para favorecer la transparencia del resultado. El prototipo asume comisiones y gastos adicionales iguales a cero; no pretende calcular todos los componentes contractuales de un crédito real.

## 12. Restricciones de entrada

- las diez variables son obligatorias;
- edad: 18–100;
- ingreso bruto en Gs.: mayor que cero;
- DTI: 0–2;
- utilización: >= 0;
- atrasos, créditos y dependientes: enteros >= 0;
- no se admiten NaN ni infinitos.

Los límites P01–P99 se utilizan como **advertencia estadística**, no como rechazo automático.

## 13. Separación de responsabilidades

### `scoring_service.py`

- normaliza el ingreso;
- ejecuta el modelo;
- calcula PD y score;
- audita valores atípicos.

### `credit_rules.py`

- asigna banda;
- calcula capacidad estimada;
- aplica edad máxima al vencimiento;
- evalúa productos, plazo y monto preaprobado.

### SQLite

- usuarios y seguridad de Django;
- fichas ficticias de solicitantes y búsqueda por cédula;
- trazabilidad de evaluaciones, resultados y decisiones simuladas.

## 14. Fuera de alcance deliberadamente

No se implementa en esta versión:

- desembolso o administración del préstamo;
- cobranzas o gestión real de mora (sí existe un seguimiento limitado con datos ficticios);
- garantías;
- provisiones;
- contabilidad;
- prevención de lavado de dinero;
- integración con centrales de riesgo;
- cálculo de LGD/EAD;
- reentrenamiento automático;
- actualización automática de tasas o moneda;
- un motor regulatorio completo.

## 15. Estado funcional actual (V2.9)

Ya están incorporados: fichas por cédula, evaluaciones, decisiones simuladas,
seguimiento académico ficticio, roles y auditoría, indicadores operativos y pantalla
para mostrar métricas predictivas cuando se disponga de resultados documentados.

La V2.9 amplía la captura de datos financieros con modalidades automática y directa;
las pruebas integrales todavía deben realizarse en el entorno Django de la tesis.

## 16. Ejecución

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Si se parte de una instalación V2.1 existente, basta con reemplazar el proyecto y ejecutar nuevamente:

```bash
python manage.py migrate
```


## 17. Novedades V2.3: módulo 1 (solicitantes y decisiones)

**Ficha:** los campos solicitados son cédula de identidad, nombres, apellidos, fecha de nacimiento, ciudad, ocupación y situación laboral. No se solicita teléfono, correo electrónico ni antigüedad laboral al solicitante. La ficha es solo de gestión: **no modifica el modelo de ML ni le añade nuevas variables**.

**Cédula:** campo único normalizado a dígitos, buscable en `/solicitantes/`. En la tesis utilizar únicamente valores y nombres ficticios. Para relacionar tablas se usa `solicitante_id` interno, nunca cédula como clave foránea.

**Edad:** se deriva de la fecha de nacimiento cuando se ejecuta una nueva evaluación. La entrada oculta está validada en servidor para evitar discrepancias. La edad usada se congela en el JSON histórico de cada evaluación.

**Relaciones:** `Solicitante` 1:N `EvaluacionScoring`; `EvaluacionScoring` 0:1 `DecisionCredito`. La decisión humana es simulada, se registra una vez con motivo, usuario y fecha. Una aprobación requiere elegir un producto de los efectivamente ofrecidos; el analista puede registrar condicional o rechazo sin producto.

**Histórico existente:** la migración `0003_solicitantes_y_decisiones` conserva las evaluaciones anteriores, con `solicitante=NULL` cuando fueron creadas sin ficha. No inventa datos personales ni enlaza evaluaciones retrospectivamente.

**Autorización:** los analistas pueden acceder a los expedientes propios y las fichas creadas o evaluadas por ellos; los administradores tienen consulta global. No se conceden derechos sobre expedientes de otros analistas por conocer la cédula. El módulo de auditoría se encuentra incorporado desde V2.4.

**Flujo de demostración:** login → Solicitantes → Registrar ficha ficticia → Nueva evaluación → Resultado → Detalle → Registrar decisión → Historial.

**Comandos para actualizar la base desde V2.2:**

```bash
python manage.py migrate
python manage.py test consulta_scoring_app
python manage.py runserver
```

La versión entregada como ZIP **no incluye un `db.sqlite3` con datos personales**. Antes de migrar una instalación con información importante se recomienda respaldar la base existente.

## 18. Limitaciones y alcance académico

- Las fichas, decisiones y futuras observaciones de seguimiento se demuestran con información ficticia.
- La interfaz de scoring y el modelo no son sustituto de informes crediticios externos ni prueban validez predictiva local.
- Las consultas de solicitantes están acotadas a los registros accesibles al usuario.
- No existe todavía una pantalla para editar datos personales; se evita incrementar el alcance y alterar el historial.
- Seguimiento, dashboard y eventos de auditoría **no forman parte del módulo 1**.


## V2.4 — Roles, autorización y auditoría de operaciones

Esta versión **conserva** la V2.3, el modelo ML entrenado, el motor de ofertas y el
registro de decisiones simuladas; agrega controles operativos específicos:

- `ANALISTA`: consulta sus expedientes, crea fichas/evaluaciones y registra decisiones
  simuladas sobre sus evaluaciones.
- `ADMINISTRADOR`: consulta todos los expedientes, crea usuarios, asigna roles y
  consulta auditoría. Puede ejecutar evaluaciones, pero la decisión ordinaria
  permanece en manos del analista.
- `AUDITOR`: consulta expedientes de forma transversal y lee la auditoría, **sin**
  crear fichas, evaluar clientes, decidir ni modificar usuarios.
- `EventoAuditoria`: usuario, acción, fecha, resultado, referencia interna y
  detalle técnico limitado. No guarda cédula, nombres, ni variables de scoring.
- Acceso denegado a expediente ajeno devuelve 404; falta de rol requerido 403.
- En `usuarios/` se puede cambiar el rol de otros usuarios mediante POST con CSRF;
  no se permite cambiar el rol propio ni el de un superusuario.
- `auditoria/` muestra los últimos 200 eventos y permite filtrar por acción y resultado.
- Alta, consultas de expediente, evaluación, decisión, cambios de rol y accesos
  denegados generan registros. Las mutaciones relevantes guardan el evento
  dentro de la misma transacción de base de datos.

### Puesta en marcha

Se recomienda respaldar el archivo `db.sqlite3` existente antes de migrar.
El ZIP no lo incluye para evitar transportar expedientes privados.

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test consulta_scoring_app
python manage.py runserver
```

Ejemplo de demo: iniciar sesión como un analista y consultar una evaluación creada
por otro analista (404); luego iniciar sesión como auditor y comprobar que puede
consultarla, pero no decidir sobre ella (403). En la pestaña Auditoría se visualizan
ambos tipos de evento. La aplicación no concede créditos reales.

### Límites explícitos del prototipo

La auditoría almacenada en SQLite **no** es un registro inalterable ante un usuario
con acceso directo al servidor/BD. La solución no incluye SIEM, despliegue bancario,
certificación de seguridad, seguimiento crediticio real ni fuentes reales de PII.
Deben utilizarse fichas ficticias y proteger el archivo de base de datos durante la
demostración. Para producción, la configuración segura de Django y la protección
del servidor son requisitos adicionales, fuera del nuevo módulo.


---

## Versión 2.5 — Módulo 3: seguimiento crediticio académico

Se agrega `SeguimientoCredito` con relación **uno a uno** a `DecisionCredito`,
que a su vez pertenece a `EvaluacionScoring` y `Solicitante`. La cédula está
únicamente en la ficha de solicitante; la consulta de seguimientos permite
buscarla mediante una relación Django, sin duplicarla en la tabla.

Un seguimiento **solo** se crea para una decisión `APROBADA` simulada. Incluye
fecha de otorgamiento ficticio, cierre previsto, fecha hasta la cual se observa
el estado, mora máxima, estado (vigente/vencido/cancelado) y notas opcionales.
Los vencimientos futuros (p. ej. en 2029) representan planes, **no pagos
ocurridos ni observaciones futuras**. Se rechazan fechas de observación futuras
y combinaciones temporalmente incompatibles.

Los analistas solo crean y actualizan seguimientos de sus propias evaluaciones;
administradores y auditores pueden consultarlos sin alterar datos. Cada
creación, actualización y consulta se registra en `EventoAuditoria`, sin almacenar
la cédula en el evento. Los cambios preservan el score original.

Endpoints añadidos:
- `/seguimientos/` — lista y filtros de cédula y estado.
- `/evaluaciones/<pk>/seguimiento/nuevo/` — alta de seguimiento (analista con aprobación).
- `/seguimientos/<pk>/` — detalle (según permisos).
- `/seguimientos/<pk>/actualizar/` — actualizaciones (analista autorizado).

Para instalar sobre V2.4, hacer respaldo del SQLite y ejecutar
`python manage.py migrate`. Para probar: `python manage.py test consulta_scoring_app`.

La investigación no afirma desempeño predictivo real de cartera: los datos de
esta pantalla son exclusivamente *simulados*. La aplicación no gestiona cuotas,
desembolsos ni cobranzas, ni agrega métricas automáticas a partir de resultados ficticios.
El dashboard de métricas y operaciones será el siguiente módulo independiente.


## V2.6 — Panel de indicadores

- `/indicadores/` distingue estadísticas operativas del prototipo y desempeño
  predictivo del modelo. Respeta la visibilidad por rol: analista = propias;
  administrador/auditor = todas.
- Estadísticas operativas basadas en los registros de SQLite (conteos y media).
  Las decisiones son *simuladas*, no créditos realmente desembolsados.
- Métricas predictivas (AUC-ROC, Gini, KS y Brier) solo aparecen al incorporar
  reporte verificado con procedencia en `artifacts/model_validation_report.json`.
  No se inventan métricas y el dashboard no reutiliza los seguimientos ficticios
  como resultados de cartera.
- Consulta `CAMBIOS_V2_6.md` para el formato, condiciones y pruebas.


## V2.9 — Captura financiera

Ver `CAMBIOS_V2_9.md` para las dos modalidades y su validación. El registro `EvaluacionScoring.entradas` conserva las diez variables de inferencia y, separadamente, el origen/desglose. No se añadió una migración de base de datos.
