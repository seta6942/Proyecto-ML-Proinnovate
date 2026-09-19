# Proyecto Proinnovate - Analytics

## Criterios Técnicos y Metodología

### 1. Análisis Exploratorio(EDA) y Homologación de Esquemas
Como los datos vienen de distintos cortes históricos, las columnas cambian de nombre de un año a otro (el conocido schema drift). Para armar el diccionario de mapeo (`MAPEO_COLUMNAS`) en el script, evité asumir nombres a ciegas e hice un análisis exploratorio previo. Revisé muestras de datos cruzadas usando `df.sample()` para confirmar que columnas con nombres distintos, como `NOMBRE_SOLICITANTE` en 2021 y `RAZON_SOCIAL` en 2024, guardaran exactamente la misma información de la empresa postulante. 

Esto lo complementé cruzando la información con los diccionarios oficiales de la Plataforma Nacional de Datos Abiertos, lo cual fue clave para entender las nomenclaturas internas y confirmar, por ejemplo, que `MONTO_RNR` corresponde al dinero aportado por el Estado. Finalmente, apliqué sanity checks para validar los tipos de datos (fechas, montos, texto) y asegurar que al concatenar los 6 cortes históricos no se rompiera la estructura ni se mezclaran textos con operaciones numéricas.

### 2. Feature Selection y Delimitación del Alcance
Meter toda la data cruda a los modelos de Machine Learning (NLP y XGBoost) solo iba a generar ruido y multicolinealidad. Para llegar a la lista final de variables (`COLS_REQUERIDAS`), apliqué un filtro basado en la lógica de negocio. Conservé únicamente las variables que explican el contexto y el impacto del subsidio: quién recibe los fondos, para qué, dónde y cuánto. Toda la variables administrativa, como nombres de evaluadores, teléfonos o ubigeos redundantes, fue descartada directamente. 

A nivel de calidad de datos, eliminé desde el inicio las columnas con más del 90% de nulos o aquellas con varianza cero, ya que al tener un mismo valor repetido en todas las filas no aportan ninguna capacidad predictiva al algoritmo. Por último, para evitar redundancias y no confundir a los modelos con datos financieros duplicados o dispersos, unifiqué todos esos campos financieros en una sola columna (`Monto_Total_Proyecto`).