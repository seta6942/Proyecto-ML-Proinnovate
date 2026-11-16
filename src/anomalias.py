"""
Fase 3: detección de presupuestos atípicos con Isolation Forest.

Marca los proyectos cuya combinación de montos, apalancamiento y duración se
aleja del patrón general, y explica qué variable pesa más en cada caso.
"""

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.ensemble import IsolationForest

from src.configuracion import (
    CONTAMINACION_ANOMALIAS,
    MIN_PROYECTOS_CONCURSO,
    SEMILLA,
)
from src.graficos import (
    COLOR_FONDO,
    COLOR_SERIE_1,
    COLOR_SERIE_2,
    COLOR_TEXTO_SUAVE,
    crear_figura,
    titular,
)
from src.validacion import validar_columnas

COLUMNAS_ENTRADA = [
    "Concurso", "Monto_Estado", "Aporte_Privado_Total", "Monto_Total_Proyecto",
    "Porcentaje_Aporte_Estado", "Duracion_Meses",
]

# Variables del modelo y la explicación que se muestra cuando una de ellas es
# la que más se aleja de lo normal en un proyecto atípico
VARIABLES_ANOMALIA = {
    "Log_Monto_Estado"          : "MONTO DEL ESTADO ATIPICO",
    "Log_Aporte_Privado"        : "APORTE PRIVADO ATIPICO",
    "Porcentaje_Aporte_Estado"  : "PROPORCION ESTADO/PRIVADO ATIPICA",
    "Duracion_Meses"            : "DURACION ATIPICA",
    "Desviacion_Monto_Concurso" : "MONTO ATIPICO PARA SU CONCURSO",
}

# Tope de los z-scores robustos
LIMITE_ZSCORE = 10.0


def calcular_zscore_robusto(serie: pd.Series, escala_minima: float = 1e-6) -> pd.Series:
    """
    Calcula cuántas desviaciones se aleja cada valor de la mediana.

    Usa la mediana y la desviación absoluta mediana (MAD) en lugar de la media
    y la desviación estándar, porque estas últimas se inflan justo con los
    valores extremos que se quieren detectar.

    Args:
        serie: Valores numéricos.
        escala_minima: Dispersión por debajo de la cual la MAD no se usa.

    Returns:
        El z-score robusto de cada valor, acotado a ±LIMITE_ZSCORE. Si la
        serie no tiene dispersión, devuelve ceros.
    """
    mediana = serie.median()
    desviaciones = (serie - mediana).abs()

    # 1.4826 hace que la MAD sea comparable a la desviación estándar en datos normales
    escala = 1.4826 * desviaciones.median()

    if not escala > escala_minima:
        # Si más de la mitad de valores son iguales (concursos con subsidio fijo)
        # la MAD vale casi cero y cualquier diferencia daría z-scores enormes.
        # Se usa la desviación absoluta media, escalada para ser comparable.
        escala = 1.2533 * desviaciones.mean()

    if not escala > escala_minima:
        return pd.Series(0.0, index=serie.index)

    # El tope evita que un solo valor extremo domine la variable en el modelo
    return ((serie - mediana) / escala).clip(-LIMITE_ZSCORE, LIMITE_ZSCORE)


def calcular_desviacion_por_concurso(df: pd.DataFrame) -> pd.Series:
    """
    Mide cuánto se aleja el monto total de cada proyecto del típico de su
    concurso.

    Un proyecto de S/ 2 millones es normal en un concurso de innovación
    empresarial y atípico en uno de becas. Comparar contra el propio concurso
    detecta esos casos, que un modelo global pasaría por alto.

    Args:
        df: Dataset con Concurso y Monto_Total_Proyecto.

    Returns:
        El z-score robusto del log del monto dentro de su concurso. Los
        concursos con menos de MIN_PROYECTOS_CONCURSO proyectos quedan en 0
        porque no tienen una referencia confiable.
    """
    log_monto = np.log1p(df["Monto_Total_Proyecto"])
    concurso = df["Concurso"].fillna("SIN CONCURSO")

    # En escala logarítmica, 0.05 equivale a una variación de 5% en el monto:
    # diferencias menores entre proyectos de un concurso no son dispersión real
    desviacion = log_monto.groupby(concurso).transform(
        lambda montos: calcular_zscore_robusto(montos, escala_minima=0.05)
    )
    tamanio_concurso = concurso.map(concurso.value_counts())
    desviacion[tamanio_concurso < MIN_PROYECTOS_CONCURSO] = 0.0

    return desviacion.fillna(0.0)


def preparar_variables(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la matriz de variables del Isolation Forest.

    Los montos se pasan a logaritmo porque van de miles a millones de soles:
    en escala lineal, los proyectos grandes serían "atípicos" solo por su
    tamaño. No se estandariza porque los árboles del Isolation Forest eligen
    cortes entre el mínimo y el máximo de cada variable, y un cambio de
    escala lineal no altera esos cortes.

    Args:
        df: Dataset con las métricas financieras.

    Returns:
        Una columna por variable de VARIABLES_ANOMALIA, sin valores faltantes.
    """
    variables = pd.DataFrame(index=df.index)
    variables["Log_Monto_Estado"]          = np.log1p(df["Monto_Estado"])
    variables["Log_Aporte_Privado"]        = np.log1p(df["Aporte_Privado_Total"])
    variables["Porcentaje_Aporte_Estado"]  = df["Porcentaje_Aporte_Estado"]
    variables["Duracion_Meses"]            = df["Duracion_Meses"]
    variables["Desviacion_Monto_Concurso"] = calcular_desviacion_por_concurso(df)

    # Los faltantes (proyectos sin fechas o sin monto total) toman la mediana
    # para que no se marquen como atípicos solo por no tener el dato
    return variables.fillna(variables.median())


def explicar_anomalias(variables: pd.DataFrame, es_anomalia: pd.Series) -> pd.Series:
    """
    Indica, para cada proyecto atípico, la variable que más se aleja de lo
    normal.

    Args:
        variables: Matriz de variables del modelo.
        es_anomalia: Máscara de los proyectos marcados como atípicos.

    Returns:
        El motivo de cada proyecto atípico; vacío en los proyectos normales.
    """
    zscores = variables.apply(calcular_zscore_robusto).abs()
    variable_dominante = zscores.idxmax(axis=1)

    motivo = variable_dominante.map(VARIABLES_ANOMALIA)
    return motivo.where(es_anomalia, "")


def graficar_anomalias(df: pd.DataFrame) -> Figure:
    """
    Dibuja la dispersión entre el monto del Estado y el aporte privado, con
    los proyectos atípicos resaltados.

    Args:
        df: Dataset con la columna Es_Anomalia.

    Returns:
        La figura lista para guardar.
    """
    figura, ejes = crear_figura()
    normales = df[df["Es_Anomalia"] == 0]
    atipicos = df[df["Es_Anomalia"] == 1]

    ejes.scatter(
        normales["Monto_Estado"], normales["Aporte_Privado_Total"],
        s=10, alpha=0.35, color=COLOR_SERIE_1, linewidths=0,
        label=f"Normal ({len(normales):,})",
    )
    ejes.scatter(
        atipicos["Monto_Estado"], atipicos["Aporte_Privado_Total"],
        s=22, alpha=0.9, color=COLOR_SERIE_2, edgecolors=COLOR_FONDO, linewidths=0.6,
        label=f"Atípico ({len(atipicos):,})",
    )

    # symlog muestra los aportes en cero (escala lineal cerca del origen) y los
    # montos grandes en escala logarítmica
    ejes.set_xscale("symlog", linthresh=1e4)
    ejes.set_yscale("symlog", linthresh=1e4)
    ejes.set_xlabel("Monto del Estado (S/, escala logarítmica)", color=COLOR_TEXTO_SUAVE)
    ejes.set_ylabel("Aporte privado total (S/, escala logarítmica)", color=COLOR_TEXTO_SUAVE)
    ejes.legend(frameon=False, loc="upper left", labelcolor=COLOR_TEXTO_SUAVE)

    titular(
        ejes,
        "Presupuestos atípicos detectados con Isolation Forest",
        "Cada punto es un proyecto. Los atípicos combinan montos, apalancamiento o duración poco habituales.",
    )
    return figura


def ejecutar_deteccion_anomalias(df: pd.DataFrame) -> tuple[pd.DataFrame, Figure]:
    """
    Ejecuta la Fase 3 y marca los presupuestos atípicos.

    Args:
        df: Dataset con las métricas financieras.

    Returns:
        El dataset con Es_Anomalia (1 = atípico), Puntaje_Anomalia (mayor =
        más atípico), Desviacion_Monto_Concurso y Motivo_Anomalia, y la
        figura de dispersión.

    Raises:
        ErrorValidacionDatos: Si el dataset no trae las métricas financieras.
    """
    print("\nFASE 3: detección de presupuestos atípicos (Isolation Forest)")
    validar_columnas(df, COLUMNAS_ENTRADA, "Anomalías")

    variables = preparar_variables(df)

    modelo = IsolationForest(
        n_estimators=300,
        contamination=CONTAMINACION_ANOMALIAS,
        random_state=SEMILLA,
        n_jobs=-1,
    )
    prediccion = modelo.fit_predict(variables)   # -1 = atípico, 1 = normal

    df["Es_Anomalia"] = (prediccion == -1).astype(int)
    # decision_function es negativo en los atípicos; se invierte el signo para
    # que en el dashboard un puntaje mayor signifique "más atípico"
    df["Puntaje_Anomalia"] = (-modelo.decision_function(variables)).round(4)
    df["Desviacion_Monto_Concurso"] = variables["Desviacion_Monto_Concurso"].round(3)
    df["Motivo_Anomalia"] = explicar_anomalias(variables, df["Es_Anomalia"] == 1)

    n_anomalias = df["Es_Anomalia"].sum()
    print(f"   Proyectos atípicos: {n_anomalias:,} ({n_anomalias / len(df):.1%})")
    print("   Motivos principales:")
    for motivo, cantidad in df.loc[df["Es_Anomalia"] == 1, "Motivo_Anomalia"].value_counts().items():
        print(f"      {motivo:<36} {cantidad:>4}")

    return df, graficar_anomalias(df)
