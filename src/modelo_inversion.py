"""
Fase 4: modelo XGBoost para estimar la capacidad de inversión privada.

Predice cuánto aporta la empresa (monetario más no monetario) a partir del
subsidio, el fondo, el concurso, la región, el sector tecnológico y la
duración del proyecto. La diferencia entre lo aportado y lo estimado indica
qué empresas invierten más o menos de lo esperado para su perfil.
"""

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, TargetEncoder
from xgboost import XGBRegressor

from src.configuracion import (
    FRECUENCIA_MINIMA_CATEGORIA,
    HIPERPARAMETROS_XGB,
    N_PLIEGUES_CV,
    SEMILLA,
)
from src.graficos import (
    COLOR_SERIE_1,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    crear_figura,
    titular,
)
from src.validacion import validar_columnas

# El monto total, los ratios y las columnas de anomalías se calculan con el
# aporte privado, que es justo lo que se predice. Usarlas filtraría la
# respuesta al modelo (data leakage), por eso no están en estas listas.
VARIABLES_NUMERICAS = ["Log_Monto_Estado", "Anio_Proyecto", "Duracion_Meses"]
VARIABLE_CONCURSO = "Concurso"
VARIABLES_CATEGORICAS = [
    "Fondo", "Region", "Macrorregion", "Sector_Tecnologico", "Moneda_Original",
]

COLUMNAS_ENTRADA = (
    ["Monto_Estado", "Aporte_Privado_Total", "Anio_Proyecto", "Duracion_Meses", VARIABLE_CONCURSO]
    + VARIABLES_CATEGORICAS
)

CATEGORIA_DESCONOCIDA = "DESCONOCIDO"


# ==============================================================================
# Preparación de datos y modelo
# ==============================================================================

def preparar_datos_modelo(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Arma la matriz de variables y el objetivo del modelo.

    El aporte privado va de cero a millones de soles. El modelo no lo predice
    en soles sino como log((1 + aporte) / (1 + subsidio)), que es casi el
    logaritmo del ratio de apalancamiento. Así aprende qué proporción del
    subsidio pone la empresa (lo que cada concurso regula) y el error no lo
    dominan unos pocos proyectos grandes. Para volver a soles basta con sumar
    log(1 + subsidio) y aplicar la exponencial.

    Args:
        df: Dataset con métricas, clústeres y fechas.

    Returns:
        Las variables (X), el objetivo (y) y la máscara de las filas usadas.
        Se excluyen los proyectos sin monto del Estado, que no tienen
        subsidio del cual partir.
    """
    mascara = df["Monto_Estado"] > 0
    datos = df.loc[mascara].copy()

    datos["Log_Monto_Estado"] = np.log1p(datos["Monto_Estado"])
    datos["Anio_Proyecto"] = datos["Anio_Proyecto"].astype(float)

    for col in VARIABLES_CATEGORICAS + [VARIABLE_CONCURSO]:
        datos[col] = datos[col].fillna(CATEGORIA_DESCONOCIDA).astype(str)

    X = datos[VARIABLES_NUMERICAS + [VARIABLE_CONCURSO] + VARIABLES_CATEGORICAS]
    y = np.log1p(datos["Aporte_Privado_Total"]) - datos["Log_Monto_Estado"]
    return X, y, mascara


def estimar_aporte_en_soles(prediccion: np.ndarray, X: pd.DataFrame) -> np.ndarray:
    """
    Convierte la predicción del modelo (log del ratio) en aporte en soles.

    Args:
        prediccion: Salida del modelo.
        X: Variables usadas en la predicción, con Log_Monto_Estado.

    Returns:
        Aporte privado estimado en soles, nunca negativo.
    """
    return np.clip(np.expm1(prediccion + X["Log_Monto_Estado"].to_numpy()), 0, None)


def construir_pipeline() -> Pipeline:
    """
    Construye el pipeline de preprocesamiento y XGBoost.

    - Concurso tiene más de 150 valores y cada uno fija su propia regla de
      contrapartida. TargetEncoder lo reemplaza por el valor promedio del
      objetivo en ese concurso, calculado con validación cruzada interna para
      que cada fila no use su propio objetivo (sin data leakage).
    - Las demás categóricas van en one-hot; las que tienen menos de
      FRECUENCIA_MINIMA_CATEGORIA proyectos se agrupan en una sola columna.
    - Las variables numéricas pasan sin escalar porque los árboles no
      dependen de la escala, y XGBoost maneja de forma nativa los faltantes
      de Duracion_Meses.

    Returns:
        Pipeline sin entrenar.
    """
    preprocesador = ColumnTransformer(
        transformers=[
            ("numericas", "passthrough", VARIABLES_NUMERICAS),
            ("concurso", TargetEncoder(
                target_type="continuous",
                random_state=SEMILLA,
            ), [VARIABLE_CONCURSO]),
            ("categoricas", OneHotEncoder(
                handle_unknown="infrequent_if_exist",
                min_frequency=FRECUENCIA_MINIMA_CATEGORIA,
                sparse_output=False,
            ), VARIABLES_CATEGORICAS),
        ],
    )

    modelo = XGBRegressor(**HIPERPARAMETROS_XGB, random_state=SEMILLA, n_jobs=-1)

    return Pipeline([("preprocesador", preprocesador), ("modelo", modelo)])


# ==============================================================================
# Evaluación
# ==============================================================================

def predecir_linea_base(X: pd.DataFrame, aporte_real: np.ndarray, pliegues: KFold) -> np.ndarray:
    """
    Predice con una regla simple para tener contra qué comparar el modelo.

    La regla multiplica el subsidio por el ratio mediano de apalancamiento de
    su concurso, calculado solo con los datos de entrenamiento de cada
    pliegue. Si XGBoost no supera esta regla, no aporta valor.

    Args:
        X: Variables del modelo.
        aporte_real: Aporte privado real en soles.
        pliegues: Divisiones de validación cruzada.

    Returns:
        Predicción en soles para cada fila, fuera de muestra.
    """
    monto_estado = np.expm1(X["Log_Monto_Estado"])
    ratio = pd.Series(aporte_real, index=X.index) / monto_estado
    prediccion = np.zeros(len(X))

    for indices_train, indices_test in pliegues.split(X):
        ratio_por_concurso = ratio.iloc[indices_train].groupby(X["Concurso"].iloc[indices_train]).median()
        ratio_global = ratio.iloc[indices_train].median()

        ratio_test = X["Concurso"].iloc[indices_test].map(ratio_por_concurso).fillna(ratio_global)
        prediccion[indices_test] = ratio_test.to_numpy() * monto_estado.iloc[indices_test].to_numpy()

    return prediccion


def calcular_metricas(y_real: np.ndarray, y_estimado: np.ndarray, nombre: str) -> dict[str, str | float]:
    """
    Calcula las métricas de error en soles y el R² en escala logarítmica.

    Args:
        y_real: Aporte privado real en soles.
        y_estimado: Aporte privado estimado en soles.
        nombre: Nombre del modelo evaluado.

    Returns:
        Diccionario con MAE, mediana del error absoluto, RMSE y R² (soles y log).
    """
    return {
        "Modelo": nombre,
        "MAE_Soles": round(mean_absolute_error(y_real, y_estimado), 2),
        "MedAE_Soles": round(median_absolute_error(y_real, y_estimado), 2),
        "RMSE_Soles": round(np.sqrt(mean_squared_error(y_real, y_estimado)), 2),
        "R2_Soles": round(r2_score(y_real, y_estimado), 4),
        "R2_Log": round(r2_score(np.log1p(y_real), np.log1p(y_estimado)), 4),
    }


def calcular_importancia(pipeline: Pipeline) -> pd.Series:
    """
    Suma la importancia (ganancia) de las columnas one-hot de cada variable
    original.

    Mostrar 'Concurso' como un solo valor es más claro que repartir su
    importancia entre decenas de columnas 'Concurso_<nombre>'.

    Args:
        pipeline: Pipeline entrenado.

    Returns:
        Participación de cada variable original en la ganancia total.
    """
    nombres = pipeline.named_steps["preprocesador"].get_feature_names_out()
    ganancias = pipeline.named_steps["modelo"].get_booster().get_score(importance_type="total_gain")

    # XGBoost nombra las columnas f0, f1, ... en el orden de la matriz
    ganancia_por_columna = pd.Series(
        [ganancias.get(f"f{i}", 0.0) for i in range(len(nombres))], index=nombres
    )

    # Se prueban primero los nombres más largos para que 'Macrorregion_' no se
    # confunda con 'Region_'
    variables = sorted(
        VARIABLES_NUMERICAS + [VARIABLE_CONCURSO] + VARIABLES_CATEGORICAS, key=len, reverse=True
    )

    def variable_original(nombre_columna: str) -> str:
        sin_prefijo = nombre_columna.split("__", 1)[1]
        return next(v for v in variables if sin_prefijo == v or sin_prefijo.startswith(f"{v}_"))

    importancia = ganancia_por_columna.groupby(variable_original).sum()
    return (importancia / importancia.sum()).sort_values()


def graficar_importancia(importancia: pd.Series) -> Figure:
    """
    Dibuja las barras con la importancia de cada variable.

    Args:
        importancia: Participación de cada variable en la ganancia total.

    Returns:
        La figura lista para guardar.
    """
    figura, ejes = crear_figura(ancho=9, alto=5)
    posiciones = np.arange(len(importancia))

    ejes.barh(posiciones, importancia.values, height=0.6, color=COLOR_SERIE_1)
    ejes.set_yticks(posiciones, [nombre.replace("_", " ") for nombre in importancia.index])
    ejes.tick_params(axis="y", colors=COLOR_TEXTO, labelsize=10, length=0)
    ejes.grid(axis="y", visible=False)
    ejes.xaxis.set_major_formatter(lambda valor, _: f"{valor:.0%}")

    for posicion, valor in zip(posiciones, importancia.values):
        ejes.text(valor + 0.005, posicion, f"{valor:.1%}", va="center", fontsize=9, color=COLOR_TEXTO_SUAVE)

    ejes.set_xlim(0, importancia.max() * 1.15)
    titular(
        ejes,
        "Variables que más explican el aporte privado (XGBoost)",
        "Participación de cada variable en la ganancia total de los árboles.",
    )
    return figura


# ==============================================================================
# Ejecución de la fase
# ==============================================================================

def ejecutar_modelo_inversion(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, Figure]:
    """
    Ejecuta la Fase 4: evalúa XGBoost con validación cruzada y agrega la
    estimación de aporte privado de cada proyecto.

    Las estimaciones salen de cross_val_predict: cada proyecto se predice con
    un modelo que no lo vio al entrenar, así la brecha refleja una diferencia
    real y no un sobreajuste.

    Args:
        df: Dataset con métricas, clústeres y anomalías.

    Returns:
        El dataset con Aporte_Privado_Estimado y Brecha_Aporte_Privado
        (positiva = la empresa aportó más de lo esperado), las métricas del
        modelo y de la línea base, y la figura de importancia de variables.

    Raises:
        ErrorValidacionDatos: Si el dataset no trae las variables del modelo.
    """
    print("\nFASE 4: XGBoost para estimar la capacidad de inversión privada")
    validar_columnas(df, COLUMNAS_ENTRADA, "Modelo de inversión")

    X, y, mascara = preparar_datos_modelo(df)
    print(f"   Proyectos para el modelo: {len(X):,} | validación cruzada de {N_PLIEGUES_CV} pliegues")

    pliegues = KFold(n_splits=N_PLIEGUES_CV, shuffle=True, random_state=SEMILLA)
    pipeline = construir_pipeline()
    y_real = df.loc[mascara, "Aporte_Privado_Total"].to_numpy()

    prediccion = cross_val_predict(pipeline, X, y, cv=pliegues)
    estimado_xgb = estimar_aporte_en_soles(prediccion, X)
    estimado_base = predecir_linea_base(X, y_real, pliegues)

    metricas = pd.DataFrame([
        calcular_metricas(y_real, estimado_xgb, "XGBoost"),
        calcular_metricas(y_real, estimado_base, "Línea base (ratio mediano por concurso)"),
    ])

    for fila in metricas.itertuples():
        print(
            f"   {fila.Modelo:<40} MAE S/ {fila.MAE_Soles:>11,.0f} | "
            f"MedAE S/ {fila.MedAE_Soles:>9,.0f} | R² {fila.R2_Soles:.3f} | R² log {fila.R2_Log:.3f}"
        )

    df["Aporte_Privado_Estimado"] = np.nan
    df.loc[mascara, "Aporte_Privado_Estimado"] = estimado_xgb.round(2)
    df["Brecha_Aporte_Privado"] = (df["Aporte_Privado_Total"] - df["Aporte_Privado_Estimado"]).round(2)

    # El modelo final se entrena con todos los datos solo para medir la
    # importancia de variables; las estimaciones ya salieron de la validación
    pipeline.fit(X, y)
    importancia = calcular_importancia(pipeline)

    print("   Importancia de variables (ganancia):")
    for variable, valor in importancia.sort_values(ascending=False).items():
        print(f"      {variable:<20} {valor:.1%}")

    return df, metricas, graficar_importancia(importancia)
