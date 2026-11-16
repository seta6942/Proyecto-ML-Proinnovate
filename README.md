# Proyecto Proinnovate - Analytics

Evaluación de impacto y mapeo del ecosistema de innovación financiado por ProInnóvate (Perú). El pipeline unifica los cortes históricos publicados en la Plataforma Nacional de Datos Abiertos, mide cuánto capital privado atrae cada sol del Estado, clasifica los proyectos por sector tecnológico a partir de sus títulos, detecta presupuestos atípicos y estima la capacidad de inversión de las empresas. Los resultados alimentan un dashboard de Power BI.

## Resultados

Cortes de `Data/` al 7 de julio de 2026.

| Indicador | Valor |
| :--- | ---: |
| Proyectos únicos | 9 235 |
| Inversión del Estado | S/ 1 346 millones |
| Aporte privado (monetario y no monetario) | S/ 630 millones |
| Ratio de Apalancamiento Privado | 0.47 |
| Ratio de apalancamiento solo en efectivo | 0.18 |
| Fondos fuera de Lima Metropolitana y Callao | 38.1% |
| Índice de concentración regional (HHI) | 0.379 |
| Proyectos con presupuesto atípico | 462 (5.0%) |

Por cada sol que pone el Estado, las empresas aportan 47 céntimos, de los cuales 18 son dinero en efectivo y el resto aportes valorizados (horas, equipos, infraestructura). El departamento de Lima concentra el 60.6% de los fondos; la macrorregión sur (12.7%) y la norte (11.3%) le siguen.

| Sector tecnológico | Proyectos | Monto Estado (S/ millones) | Ratio de apalancamiento |
| :--- | ---: | ---: | ---: |
| Multisectorial | 2 826 | 529.0 | 0.45 |
| Certificación y calidad | 1 993 | 90.2 | 0.54 |
| Manufactura y procesos | 1 736 | 406.9 | 0.47 |
| Transformación digital | 1 416 | 139.4 | 0.42 |
| Marketing y gestión comercial | 585 | 44.8 | 0.47 |
| Prototipado y validación | 331 | 106.3 | 0.56 |
| Transferencia y formación | 272 | 24.7 | 0.54 |
| Sin clasificar | 76 | 5.2 | 0.45 |

## Estructura del repositorio

```text
Proyecto ML Proinnovate/
├── Data/                          Cortes históricos en CSV (también admite .xlsx)
├── Outputs/                       Salidas que genera el pipeline
│   └── powerbi/                   Tablas del modelo estrella para el dashboard
├── docs/
│   └── dashboard_powerbi.md       Modelo de datos, medidas DAX y páginas del dashboard
├── src/
│   ├── configuracion.py           Rutas, mapeos y parámetros de todas las fases
│   ├── extraccion.py              Fase 1a: lectura de CSV y Excel, homologación y registro de lectura
│   ├── transformacion.py          Fase 1b: fechas, montos en soles, textos y deduplicación por contrato
│   ├── limpieza.py                Funciones de limpieza de textos, montos y fechas
│   ├── validacion.py              Validaciones de esquema, llaves e integridad referencial
│   ├── metricas.py                Apalancamiento privado y descentralización
│   ├── nlp_clustering.py          Fase 2: TF-IDF, SVD y K-Means sobre los títulos
│   ├── anomalias.py               Fase 3: Isolation Forest
│   ├── modelo_inversion.py        Fase 4: XGBoost
│   ├── powerbi.py                 Fase 5: tablas del modelo estrella
│   ├── graficos.py                Estilo común de los gráficos
│   └── almacenamiento.py          Escritura de tablas y figuras
├── PROINNOVATE_ML_Pipeline.py     Orquesta las fases y guarda sus salidas
└── requirements.txt
```

Las responsabilidades siguen el flujo de un pipeline de datos: extracción, transformación, validación, modelado y almacenamiento. Cada fase recibe un DataFrame, valida al inicio las columnas que necesita y devuelve sus resultados sin escribir en disco; el orquestador decide dónde se guarda cada salida. Así una fase se puede reutilizar o probar por separado y todas las tablas comparten la misma codificación.

## Ejecución

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python PROINNOVATE_ML_Pipeline.py
```

Las rutas se resuelven desde la raíz del repositorio, así que el script funciona desde cualquier carpeta. La primera ejecución descarga las stopwords de NLTK; sin conexión, el clustering usa solo la lista propia de `configuracion.py`. Dos ejecuciones sobre los mismos datos producen salidas idénticas porque todos los modelos usan la semilla fija `SEMILLA = 42`. La ejecución completa toma unos 12 segundos.

Un archivo que no se puede leer no detiene el proceso: el error queda en `registro_lectura.csv` y se continúa con los demás cortes. Un error de esquema (una columna obligatoria que falta o una llave repetida) sí detiene el pipeline, con un mensaje que indica la etapa afectada.

| Salida | Contenido |
| :--- | :--- |
| `registro_lectura.csv` | Estado de cada archivo: filas leídas y esperadas, columnas sin mapeo y errores |
| `dataset_consolidado_limpio.csv` | Resultado del ETL: un registro por contrato |
| `dataset_final_enriquecido.csv` | Dataset con métricas, clústeres, anomalías y estimaciones |
| `resumen_regional.csv` | Proyectos, montos y apalancamiento por región |
| `evaluacion_clusters.csv` | Silhouette e inercia para cada k evaluado |
| `resumen_clusters.csv` | Términos, sector y montos de cada clúster |
| `anomalias_scatter.png` | Dispersión de montos con los proyectos atípicos resaltados |
| `metricas_modelo_inversion.csv` | Error del modelo XGBoost y de la línea base |
| `importancia_variables_xgboost.png` | Variables que más explican el aporte privado |
| `powerbi/` | `Proyectos.csv`, `Dim_Region.csv` y `Dim_Sector.csv` |

## Fases del pipeline

### Fase 1: ETL multi-archivo

`Data/` contiene siete archivos: el consolidado `Dataset 06` (corte del 5 de enero de 2026) y seis cortes de proyectos en ejecución entre julio de 2023 y julio de 2026. Juntos suman 16 501 filas, que se reducen a 9 235 contratos únicos.

| Problema detectado | Tratamiento |
| :--- | :--- |
| Títulos con comillas escapadas (`\"`) que el lector descartaba sin aviso (5 contratos de 2008 a 2010) | Lectura con el motor C de pandas y `escapechar`, con un conteo independiente de registros que avisa si se pierde alguna fila |
| 1 509 filas de FINCYT y BID 4 registradas en dólares | Conversión a soles con el tipo de cambio bancario venta promedio del año del concurso (BCRP, serie PM05242PA). La moneda original y el tipo de cambio quedan en el dataset |
| Un mismo contrato aparece en hasta seis cortes | Se conserva la fila completa del corte más reciente con `drop_duplicates`; `groupby().first()` podía mezclar columnas de cortes distintos |
| Una empresa puede tener varios contratos (1 109 empresas tienen más de uno) y 37 contratos cambian el nombre de la empresa entre cortes (abreviaturas, orden de nombres, cambio de razón social) | La llave de deduplicación es el contrato y no la empresa: deduplicar por empresa borraría proyectos distintos |
| `FONDO` se interpretaba como sector económico | Se renombra a `Fondo` (programa que financia: FINCYT, FIDECOM, BID 4...). El sector tecnológico sale de la Fase 2 |
| Región vacía o marcada como `N/D` en 743 filas | Se agrupan en `NO DETERMINADO` para que el dashboard las muestre juntas |
| Fechas numéricas en formatos `YYYYMMDD` y `DDMMYYYY` | `convertir_fecha` las lleva a `datetime` y se calcula la duración de cada proyecto en meses |
| Montos con separadores de miles o coma decimal | `limpiar_monto` interpreta `1,234.56`, `1.234,56` y `1.234.567` |

### Métricas financieras y territoriales

- **Ratio de Apalancamiento Privado**: aporte privado total (monetario más no monetario) entre el monto del Estado. Un ratio de 0.5 indica que la empresa pone S/ 0.50 por cada S/ 1.00 del subsidio. Los ratios de grupos (región, sector, total) se calculan como cociente de sumas, no como promedio de los ratios de cada proyecto.
- **Ratio de apalancamiento monetario**: igual, pero solo con el aporte en efectivo, porque el no monetario lo valoriza la propia empresa.
- **Ámbito**: la provincia de Lima y el Callao forman Lima Metropolitana; el resto del país, incluidas las demás provincias del departamento de Lima, cuenta como regiones.
- **Macrorregión**: Lima y Callao, norte, centro, sur y oriente.

### Fase 2: NLP y clustering

Los títulos se normalizan, se filtran stopwords (las de NLTK sin tildes más términos genéricos como "proyecto" o "fortalecimiento") y se vectorizan con TF-IDF de unigramas y bigramas. TruncatedSVD reduce la matriz a 100 componentes y K-Means agrupa los vectores normalizados, lo que equivale a usar similitud coseno.

Se evaluaron k = 6, 8, 10, 12 y 14. Los títulos son textos cortos y el silhouette es bajo en todos los casos (0.07 a 0.14). k = 10 es un máximo local (0.109, frente a 0.090 con k = 8 y 0.102 con k = 12) y separa temas que con menos clústeres quedaban mezclados, como la certificación ISO, la certificación HACCP y las misiones tecnológicas.

Cada clúster recibe el sector cuyos términos de referencia (`SECTORES_TECNOLOGICOS`) pesan más en su centroide. El nombre depende del contenido del clúster y no de su número, que K-Means puede cambiar al agregar cortes. Si ningún sector reúne el 35% del puntaje, el clúster se marca como multisectorial.

### Fase 3: presupuestos atípicos

Isolation Forest (300 árboles, 5% de contaminación) evalúa cinco variables por proyecto: monto del Estado y aporte privado en logaritmo, proporción que cubre el Estado, duración y desviación del monto respecto a la mediana de su concurso. Esta última detecta, por ejemplo, un proyecto de S/ 2 millones en un concurso donde lo habitual son S/ 50 mil. Cada atípico lleva un motivo: la variable con mayor z-score robusto (mediana y MAD).

### Fase 4: capacidad de inversión con XGBoost

El modelo estima el aporte privado de cada proyecto a partir del subsidio, el concurso, el fondo, la región, el sector tecnológico, el año y la duración. El objetivo es el logaritmo del ratio de apalancamiento y la pérdida es el error absoluto. El concurso (173 valores) entra con `TargetEncoder`, que usa validación cruzada interna para no filtrar el objetivo. El monto total, los ratios y las columnas de anomalías quedan fuera porque se calculan con el aporte privado.

La evaluación usa validación cruzada de 5 pliegues y se compara con una línea base que multiplica el subsidio por el ratio mediano de su concurso.

| Modelo | MAE (S/) | Mediana del error (S/) | RMSE (S/) | R² | R² (log) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| XGBoost | 22 036 | 435 | 123 103 | 0.496 | 0.936 |
| Línea base por concurso | 22 483 | 268 | 135 986 | 0.385 | 0.848 |

XGBoost mejora el MAE, el RMSE y ambos R². La línea base tiene menor mediana del error porque muchos concursos fijan un porcentaje de contrapartida y la regla acierta exactamente en esos casos; el modelo gana en los proyectos que se apartan de la regla. La columna `Brecha_Aporte_Privado` (aporte real menos estimado, fuera de muestra) indica qué empresas invierten más o menos de lo esperado para su perfil.

### Fase 5: dashboard de Power BI

El pipeline exporta un modelo estrella a `Outputs/powerbi/`. El diseño del dashboard, las relaciones, las medidas DAX y los valores de control están en [docs/dashboard_powerbi.md](docs/dashboard_powerbi.md).

## Criterios técnicos y metodología

### Análisis exploratorio y homologación de esquemas

Los cortes históricos provienen de distintas publicaciones y el nombre de una misma columna puede cambiar de un año a otro (schema drift). El diccionario `MAPEO_COLUMNAS` lleva cada variante al nombre canónico del pipeline, por ejemplo `NOMBRE_SOLICITANTE`, `RAZON_SOCIAL` o `EMPRESA` a `Empresa`, y `CONTRATO` o `CODIGO` a `Contrato`. Las equivalencias se definieron con un análisis exploratorio previo, revisando muestras cruzadas con `df.sample()` y los diccionarios oficiales de la Plataforma Nacional de Datos Abiertos, que confirman, por ejemplo, que `MONTO_RNR` (recursos no reembolsables) es el aporte del Estado.

En los siete archivos que hoy contiene `Data/` la cabecera coincide (17 columnas). El diccionario conserva las variantes para integrar sin cambios de código los cortes publicados con otra nomenclatura. Cada columna que el mapeo no reconoce se reporta en `registro_lectura.csv`, y `validar_columnas` detiene el proceso si falta una columna obligatoria.

Todas las columnas se leen como texto y se convierten después de forma explícita (montos, fechas, año). Así pandas no infiere tipos distintos en cada archivo y el UBIGEO conserva sus ceros a la izquierda.

### Selección de variables y alcance

Los modelos solo reciben variables que explican el contexto y el impacto del subsidio: quién recibe los fondos, para qué, dónde, cuánto y cuándo. El ETL descarta las columnas con más de 90% de nulos o con un único valor, porque no aportan capacidad predictiva; en los cortes actuales ninguna cumple esa condición. Los tres campos de montos se suman en `Monto_Total_Proyecto` para analizar el costo completo del proyecto sin repetir información, y se conservan por separado porque cada uno responde una pregunta distinta (aporte público, aporte en efectivo y aporte valorizado).

### Eficiencia computacional

| Operación | Decisión | Costo |
| :--- | :--- | :--- |
| Deduplicación | Orden por fecha de corte y `drop_duplicates` (tabla hash) | O(n log n) por el ordenamiento |
| Conteo de registros de cada CSV | Lector de la librería estándar, línea por línea | O(n) adicional en tiempo, O(1) en memoria |
| Silhouette para elegir k | Muestra de 5 000 títulos | O(m²) con m = 5 000, en lugar de O(n²) con n = 9 159 |
| Integridad referencial del modelo estrella | Diferencia de conjuntos entre llaves | O(n + m), frente a O(n·m) de comparar cada llave con toda la dimensión |

## Limitaciones

- El silhouette bajo refleja que los títulos son textos cortos. El clúster multisectorial (31% de los proyectos) agrupa títulos genéricos o que solo contienen el nombre de la empresa.
- La conversión de dólares usa el promedio anual del año del concurso, no el tipo de cambio de cada desembolso. Los concursos de 2026 usan el promedio de 2025, el último publicado.
- XGBoost estima la mediana del aporte esperado, así que la suma de estimados queda por debajo de la suma real. La brecha se interpreta por proyecto.
- Las coordenadas del mapa corresponden a la capital de cada departamento.
