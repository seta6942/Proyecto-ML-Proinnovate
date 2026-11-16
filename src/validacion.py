"""
Validaciones de integridad del pipeline.

Reúne las comprobaciones que detienen la ejecución cuando los datos no cumplen
el esquema esperado. Se lanzan excepciones en lugar de usar assert porque
Python omite los assert cuando se ejecuta con la opción -O.
"""

from collections.abc import Iterable

import pandas as pd


class ErrorValidacionDatos(ValueError):
    """
    Error de esquema o de integridad en los datos.

    Una excepción propia permite que el orquestador detenga el pipeline con un
    mensaje claro sin ocultar los ValueError de las librerías, que sí indican
    errores de programación.
    """


def detectar_columnas_sin_mapeo(columnas: Iterable[str], mapeo: dict[str, str]) -> list[str]:
    """
    Identifica las columnas de un corte que el diccionario de mapeo no conoce.

    Un corte nuevo con un nombre distinto (por ejemplo, RAZON_SOCIAL si no
    estuviera en el mapeo) quedaría fuera del esquema canónico sin aviso. La
    búsqueda en el diccionario es O(1), así que revisar un corte cuesta O(c)
    con c columnas.

    Args:
        columnas: Nombres de columna del corte, ya en mayúsculas.
        mapeo: Diccionario de nombres originales a nombres canónicos.

    Returns:
        Las columnas sin entrada en el mapeo, en el orden del archivo.
    """
    return [col for col in columnas if col not in mapeo]


def validar_columnas(
    df: pd.DataFrame,
    columnas: Iterable[str],
    contexto: str,
    sugerencia: str = "",
) -> None:
    """
    Comprueba que el DataFrame tenga las columnas que necesita una etapa.

    Cada fase depende de columnas creadas por las anteriores. Validarlas al
    inicio evita un KeyError a mitad del cálculo, que no indica qué etapa
    faltó ejecutar.

    Args:
        df: Dataset que recibe la etapa.
        columnas: Columnas que la etapa necesita.
        contexto: Nombre de la etapa, para el mensaje de error.
        sugerencia: Indicación opcional para corregir el problema.

    Raises:
        ErrorValidacionDatos: Si falta alguna columna.
    """
    faltantes = [col for col in columnas if col not in df.columns]
    if faltantes:
        raise ErrorValidacionDatos(f"{contexto}: faltan las columnas {faltantes}. {sugerencia}".strip())


def validar_llave_unica(df: pd.DataFrame, llave: str) -> None:
    """
    Comprueba que el dataset no esté vacío y que la llave no se repita.

    Args:
        df: Dataset deduplicado.
        llave: Columna que identifica cada registro.

    Raises:
        ErrorValidacionDatos: Si el dataset está vacío o la llave tiene
            valores repetidos.
    """
    if df.empty:
        raise ErrorValidacionDatos("El dataset quedó vacío tras la deduplicación.")

    repetidos = df[llave].duplicated().sum()
    if repetidos:
        raise ErrorValidacionDatos(f"La llave {llave} tiene {repetidos:,} valores repetidos.")


def validar_llaves(hechos: pd.DataFrame, dimension: pd.DataFrame, llave: str) -> None:
    """
    Comprueba la integridad referencial entre una tabla de hechos y una
    dimensión.

    Una llave huérfana haría que Power BI agrupe esos proyectos en "(En
    blanco)" y los totales por región o sector no cuadrarían con el total.
    La diferencia de conjuntos cuesta O(n + m), frente a O(n·m) de buscar
    cada llave de los hechos recorriendo la dimensión.

    Args:
        hechos: Tabla de hechos.
        dimension: Tabla de dimensión.
        llave: Columna que relaciona ambas tablas.

    Raises:
        ErrorValidacionDatos: Si hay valores de la llave sin fila en la
            dimensión o si la dimensión repite valores de la llave.
    """
    huerfanas = set(hechos[llave].dropna()) - set(dimension[llave])
    if huerfanas:
        raise ErrorValidacionDatos(f"Valores de {llave} sin fila en la dimensión: {sorted(huerfanas)}")

    if dimension[llave].duplicated().any():
        raise ErrorValidacionDatos(f"La dimensión tiene valores repetidos en {llave}.")
