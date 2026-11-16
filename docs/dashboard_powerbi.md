# Dashboard de Power BI

El dashboard muestra cómo se distribuyen los fondos de ProInnóvate por región y sector tecnológico, cuánto capital privado atrae cada sol del Estado y qué proyectos tienen presupuestos atípicos. Se construye en Power BI Desktop a partir de las tablas que genera `PROINNOVATE_ML_Pipeline.py` en `Outputs/powerbi/`. El archivo `.pbix` se guarda en `dashboard/Dashboard_ProInnovate.pbix`.

## 1. Modelo de datos

El modelo es un esquema estrella: una tabla de hechos con un proyecto por fila y tres dimensiones que la filtran.

| Tabla | Origen | Filas | Llave |
| :--- | :--- | ---: | :--- |
| `Proyectos` | `Outputs/powerbi/Proyectos.csv` | 9 235 | `Contrato` |
| `Dim_Region` | `Outputs/powerbi/Dim_Region.csv` | 26 | `Region` |
| `Dim_Sector` | `Outputs/powerbi/Dim_Sector.csv` | 11 | `Cluster_Innovacion` |
| `Calendario` | Tabla calculada en DAX | variable | `Fecha` |

### Relaciones

| Desde (uno) | Hacia (muchos) | Dirección del filtro |
| :--- | :--- | :--- |
| `Dim_Region[Region]` | `Proyectos[Region]` | Única |
| `Dim_Sector[Cluster_Innovacion]` | `Proyectos[Cluster_Innovacion]` | Única |
| `Calendario[Fecha]` | `Proyectos[Fecha_Inicio]` | Única |

Los filtros van siempre de la dimensión a la tabla de hechos. La dirección bidireccional no se usa porque genera ambigüedad cuando dos dimensiones filtran la misma tabla.

### Carga en Power Query

- Origen: **Obtener datos → Texto/CSV**, codificación `65001: Unicode (UTF-8)`.
- Los CSV usan punto decimal y fechas `yyyy-mm-dd`. Si la configuración regional del equipo usa coma decimal, los tipos se cambian con **Cambiar tipo → Usar configuración regional → Inglés (Estados Unidos)**.
- Tipos en `Proyectos`: montos, ratios y puntajes como **Número decimal**; `Anio_Proyecto`, `Cluster_Innovacion` y `Es_Anomalia` como **Número entero**; `Fecha_Inicio`, `Fecha_Fin` y `Fecha_Corte` como **Fecha**; `Ubigeo` como **Texto** para conservar los ceros a la izquierda.
- En `Dim_Region`, la categoría de datos de `Latitud` y `Longitud` se fija como **Latitud** y **Longitud**. Con coordenadas, el mapa no depende del geocodificador, que ubica "AMAZONAS" en Brasil y "LA LIBERTAD" en El Salvador.

### Tabla Calendario

Las funciones de inteligencia de tiempo (`SAMEPERIODLASTYEAR`, `DATESYTD`) necesitan una tabla de fechas continua. Se crea en **Modelado → Nueva tabla** y se marca como tabla de fechas sobre la columna `Fecha`.

```dax
Calendario =
VAR FechaMinima = DATE ( YEAR ( MIN ( Proyectos[Fecha_Inicio] ) ), 1, 1 )
VAR FechaMaxima = DATE ( YEAR ( MAX ( Proyectos[Fecha_Inicio] ) ), 12, 31 )
RETURN
    ADDCOLUMNS (
        SELECTCOLUMNS ( CALENDAR ( FechaMinima, FechaMaxima ), "Fecha", [Date] ),
        "Anio", YEAR ( [Fecha] ),
        "Mes_Num", MONTH ( [Fecha] ),
        "Mes", FORMAT ( [Fecha], "mmm" ),
        "Trimestre", "T" & QUARTER ( [Fecha] ),
        "Anio_Mes", FORMAT ( [Fecha], "yyyy-mm" )
    )
```

`Calendario[Mes]` se ordena por `Calendario[Mes_Num]`. Los 42 proyectos sin `Fecha_Inicio` no quedan asociados a ninguna fecha: aparecen en los totales, pero no en los visuales que filtran por año del calendario. Para análisis por año sin esa pérdida se usa `Proyectos[Anio_Proyecto]`, el año del concurso.

## 2. Medidas DAX

Las medidas se agrupan en una tabla vacía `_Medidas` (**Especificar datos** sin columnas) para separarlas de las columnas del modelo.

### Montos base

```dax
Monto Estado = SUM ( Proyectos[Monto_Estado] )

Aporte Privado = SUM ( Proyectos[Aporte_Privado_Total] )

Aporte Monetario = SUM ( Proyectos[Aporte_Empresa] )

Monto Total = SUM ( Proyectos[Monto_Total_Proyecto] )

Proyectos = COUNTROWS ( Proyectos )

Ticket Promedio Estado = DIVIDE ( [Monto Estado], [Proyectos] )
```

### Apalancamiento privado

El ratio se calcula como cociente de sumas y no como promedio de los ratios de cada proyecto. Un promedio simple daría el mismo peso a un proyecto de S/ 15 mil que a uno de S/ 15 millones.

```dax
Ratio Apalancamiento Privado = DIVIDE ( [Aporte Privado], [Monto Estado] )

Ratio Apalancamiento Monetario = DIVIDE ( [Aporte Monetario], [Monto Estado] )

% Aporte Estado = DIVIDE ( [Monto Estado], [Monto Total] )

Texto Apalancamiento =
"Por cada S/ 1.00 del Estado, las empresas aportaron S/ "
    & FORMAT ( [Ratio Apalancamiento Privado], "0.00" )
    & " (S/ " & FORMAT ( [Ratio Apalancamiento Monetario], "0.00" ) & " en efectivo)"
```

### Descentralización

```dax
Monto Estado Regiones =
CALCULATE ( [Monto Estado], Proyectos[Ambito] = "REGIONES" )

% Fondos Fuera de Lima =
DIVIDE (
    [Monto Estado Regiones],
    CALCULATE ( [Monto Estado], Proyectos[Ambito] <> "NO DETERMINADO" )
)

Participación Región =
DIVIDE ( [Monto Estado], CALCULATE ( [Monto Estado], ALL ( Dim_Region ) ) )

Ranking Región =
IF (
    HASONEVALUE ( Dim_Region[Region] ),
    RANKX ( ALL ( Dim_Region[Region] ), [Monto Estado], , DESC, DENSE )
)
```

El índice de Herfindahl-Hirschman (HHI) resume en un número qué tan concentrados están los fondos: es la suma de los cuadrados de la participación de cada región. Vale 1 si todo el dinero va a una sola región y 1/25 = 0.04 si se reparte por igual entre las 25 regiones (24 departamentos y el Callao). Al bajar, la inversión se descentraliza.

```dax
Índice Concentración HHI =
SUMX (
    VALUES ( Dim_Region[Region] ),
    VAR Participacion =
        DIVIDE ( [Monto Estado], CALCULATE ( [Monto Estado], ALL ( Dim_Region ) ) )
    RETURN
        Participacion * Participacion
)

Sector Dominante =
VAR SectorTop =
    TOPN ( 1, VALUES ( Dim_Sector[Sector_Tecnologico] ), [Monto Estado], DESC )
RETURN
    CONCATENATEX ( SectorTop, Dim_Sector[Sector_Tecnologico], ", " )
```

### Evolución en el tiempo

```dax
Monto Estado Año Anterior =
CALCULATE ( [Monto Estado], SAMEPERIODLASTYEAR ( Calendario[Fecha] ) )

Variación Interanual Monto Estado =
VAR MontoActual = [Monto Estado]
VAR MontoAnterior = [Monto Estado Año Anterior]
RETURN
    IF ( NOT ISBLANK ( MontoAnterior ), DIVIDE ( MontoActual - MontoAnterior, MontoAnterior ) )

Monto Estado Acumulado =
CALCULATE (
    [Monto Estado],
    FILTER ( ALL ( Calendario[Fecha] ), Calendario[Fecha] <= MAX ( Calendario[Fecha] ) )
)

Ratio Apalancamiento Acumulado =
DIVIDE (
    CALCULATE ( [Aporte Privado], FILTER ( ALL ( Calendario[Fecha] ), Calendario[Fecha] <= MAX ( Calendario[Fecha] ) ) ),
    [Monto Estado Acumulado]
)
```

### Presupuestos atípicos (Isolation Forest)

```dax
Proyectos Atípicos = CALCULATE ( [Proyectos], Proyectos[Es_Anomalia] = 1 )

% Proyectos Atípicos = DIVIDE ( [Proyectos Atípicos], [Proyectos] )

Monto Estado en Atípicos = CALCULATE ( [Monto Estado], Proyectos[Es_Anomalia] = 1 )

% Monto en Atípicos = DIVIDE ( [Monto Estado en Atípicos], [Monto Estado] )
```

### Capacidad de inversión (XGBoost)

`Aporte_Privado_Estimado` es la predicción fuera de muestra de cada proyecto. El modelo estima la mediana, por lo que la suma de estimados queda por debajo de la suma real (los aportes tienen una cola larga de montos altos). La brecha se interpreta proyecto por proyecto o como proporción de proyectos sobre lo esperado, no como total.

```dax
Aporte Privado Estimado = SUM ( Proyectos[Aporte_Privado_Estimado] )

Proyectos con Estimación =
CALCULATE ( [Proyectos], NOT ISBLANK ( Proyectos[Aporte_Privado_Estimado] ) )

% Sobre lo Esperado =
DIVIDE (
    CALCULATE ( [Proyectos], Proyectos[Brecha_Aporte_Privado] > 0 ),
    [Proyectos con Estimación]
)

Brecha Mediana =
MEDIANX (
    FILTER ( Proyectos, NOT ISBLANK ( Proyectos[Brecha_Aporte_Privado] ) ),
    Proyectos[Brecha_Aporte_Privado]
)
```

### Formatos

| Medida | Formato |
| :--- | :--- |
| Montos | `"S/ "#,0` |
| Ratios | `0.00` |
| Porcentajes y variación | `0.0%` |
| `Índice Concentración HHI` | `0.000` |

## 3. Páginas del dashboard

Cada página tiene una sola fila de segmentadores arriba (`Calendario[Anio]`, `Proyectos[Fondo]`, `Dim_Region[Macrorregion]`, `Dim_Sector[Sector_Tecnologico]`) y los visuales debajo. Ningún visual usa doble eje: dos medidas con escalas distintas van en gráficos separados.

### Página 1: Resumen ejecutivo

- Tarjetas: `Monto Estado`, `Aporte Privado`, `Ratio Apalancamiento Privado`, `Proyectos`, `% Fondos Fuera de Lima`.
- Tarjeta de texto con `Texto Apalancamiento`.
- Columnas: `Monto Estado` por `Calendario[Anio]`.
- Línea: `Ratio Apalancamiento Privado` por `Calendario[Anio]`, en un visual aparte.
- Barras horizontales: `Monto Estado` por `Proyectos[Fondo]`.

### Página 2: Mapa de descentralización

- Mapa con `Dim_Region[Latitud]` y `Dim_Region[Longitud]`, tamaño de burbuja `Monto Estado` y tooltips `Proyectos`, `Ratio Apalancamiento Privado` y `Sector Dominante`.
- Tarjetas: `Índice Concentración HHI` y `% Fondos Fuera de Lima`.
- Barras horizontales: `Monto Estado` por `Dim_Region[Macrorregion]`.
- Tabla: `Dim_Region[Region]`, `Ranking Región`, `Proyectos`, `Monto Estado`, `Participación Región`, `Ratio Apalancamiento Privado`.

### Página 3: Sectores tecnológicos

- Barras horizontales: `Proyectos` por `Dim_Sector[Sector_Tecnologico]`.
- Barras horizontales: `Ratio Apalancamiento Privado` por `Dim_Sector[Sector_Tecnologico]`.
- Matriz: filas `Dim_Sector[Sector_Tecnologico]`, columnas `Dim_Region[Macrorregion]`, valores `Monto Estado`, con formato condicional de escala de un solo color.
- Tabla: `Dim_Sector[Cluster_Innovacion]`, `Dim_Sector[Cluster_Terminos]`, `Dim_Sector[Terminos_Principales]`, `Proyectos`. Muestra qué términos definen cada clúster.

### Página 4: Presupuestos atípicos

- Tarjetas: `Proyectos Atípicos`, `% Proyectos Atípicos`, `% Monto en Atípicos`.
- Dispersión: eje X `Proyectos[Monto_Estado]`, eje Y `Proyectos[Aporte_Privado_Total]`, ambos en escala logarítmica, leyenda `Proyectos[Es_Anomalia]`, detalle `Proyectos[Contrato]`.
- Barras horizontales: `Proyectos Atípicos` por `Proyectos[Motivo_Anomalia]`.
- Tabla filtrada a `Es_Anomalia = 1` y ordenada por `Puntaje_Anomalia` descendente: `Contrato`, `Empresa`, `Concurso`, `Monto_Estado`, `Aporte_Privado_Total`, `Motivo_Anomalia`.

### Página 5: Capacidad de inversión

- Tarjetas: `% Sobre lo Esperado` y `Brecha Mediana`.
- Dispersión: eje X `Proyectos[Aporte_Privado_Estimado]`, eje Y `Proyectos[Aporte_Privado_Total]`, escala logarítmica. Los puntos sobre la diagonal son empresas que aportaron más de lo que el modelo esperaba para su perfil.
- Barras horizontales: `% Sobre lo Esperado` por `Dim_Sector[Sector_Tecnologico]` y por `Dim_Region[Macrorregion]`.
- Imagen `Outputs/importancia_variables_xgboost.png` con la importancia de variables del modelo.

## 4. Valores de control

Sin filtros aplicados, las medidas deben coincidir con los resultados del pipeline. Una diferencia indica un tipo de dato o una relación mal configurada.

| Medida | Valor esperado |
| :--- | ---: |
| `Proyectos` | 9 235 |
| `Monto Estado` | S/ 1 346 420 345 |
| `Aporte Privado` | S/ 629 729 036 |
| `Ratio Apalancamiento Privado` | 0.47 |
| `Ratio Apalancamiento Monetario` | 0.18 |
| `% Fondos Fuera de Lima` | 38.1% |
| `Índice Concentración HHI` | 0.379 |
| `Proyectos Atípicos` | 462 |
| `% Sobre lo Esperado` | 46.9% |

Los valores corresponden a los cortes de `Data/` al 7 de julio de 2026 y cambian si se agregan cortes nuevos.
