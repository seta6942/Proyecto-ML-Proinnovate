"""
PORTAFOLIO PROINNOVATE - PIPELINE COMPLETO
Autor: Sandro Estanislao Tapia Acosta
Última actualización: 16/11/2026

Datasets: cortes históricos del programa ProInnóvate (Perú)

Este script solo orquesta las fases: cada módulo de src/ calcula y devuelve
sus tablas o figuras, y aquí se decide en qué archivo se guardan.
"""

import os
import sys
import time

# joblib intenta contar los núcleos físicos con un comando del sistema que en
# Windows falla y llena la consola de advertencias. Solo respeta un límite menor
# a los núcleos lógicos, por eso se usa la mitad (los núcleos físicos cuando el
# procesador tiene hyperthreading).
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, (os.cpu_count() or 2) // 2)))

from src.almacenamiento import guardar_csv, guardar_figura
from src.anomalias import ejecutar_deteccion_anomalias
from src.configuracion import (
    CSV_CONSOLIDADO,
    CSV_ENRIQUECIDO,
    CSV_EVALUACION_CLUSTERS,
    CSV_METRICAS_MODELO,
    CSV_REGISTRO_LECTURA,
    CSV_RESUMEN_CLUSTERS,
    CSV_RESUMEN_REGIONAL,
    DIR_DATOS,
    DIR_POWERBI,
    PNG_ANOMALIAS,
    PNG_IMPORTANCIA,
)
from src.extraccion import extraer_cortes
from src.metricas import ejecutar_metricas
from src.modelo_inversion import ejecutar_modelo_inversion
from src.nlp_clustering import ejecutar_clustering
from src.powerbi import construir_modelo_estrella
from src.transformacion import transformar_datos
from src.validacion import ErrorValidacionDatos


def main() -> None:
    """Ejecuta las fases del pipeline en orden y guarda sus salidas."""
    inicio = time.perf_counter()

    df_cortes, registro_lectura = extraer_cortes(DIR_DATOS)
    guardar_csv(registro_lectura, CSV_REGISTRO_LECTURA)
    df = transformar_datos(df_cortes)
    guardar_csv(df, CSV_CONSOLIDADO)

    df, resumen_regional = ejecutar_metricas(df)
    guardar_csv(resumen_regional, CSV_RESUMEN_REGIONAL)

    df, evaluacion_k, resumen_clusters = ejecutar_clustering(df)
    guardar_csv(evaluacion_k, CSV_EVALUACION_CLUSTERS)
    guardar_csv(resumen_clusters, CSV_RESUMEN_CLUSTERS)

    df, figura_anomalias = ejecutar_deteccion_anomalias(df)
    guardar_figura(figura_anomalias, PNG_ANOMALIAS)

    df, metricas_modelo, figura_importancia = ejecutar_modelo_inversion(df)
    guardar_csv(metricas_modelo, CSV_METRICAS_MODELO)
    guardar_figura(figura_importancia, PNG_IMPORTANCIA)

    print("\nDATASET FINAL")
    guardar_csv(df, CSV_ENRIQUECIDO)

    for nombre_archivo, tabla in construir_modelo_estrella(df, resumen_clusters).items():
        guardar_csv(tabla, DIR_POWERBI / nombre_archivo)

    print(f"\nPipeline completado en {time.perf_counter() - inicio:.1f} s")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ErrorValidacionDatos) as error:
        # Los errores de datos o de esquema se muestran como un mensaje claro.
        # Cualquier otra excepción conserva su traza porque indica un error de
        # programación.
        print(f"\nPipeline detenido: {error}")
        sys.exit(1)
