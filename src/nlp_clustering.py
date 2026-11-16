"""
Fase 2: NLP y clustering de los títulos de proyecto.

Vectoriza los títulos con TF-IDF, reduce la dimensión con SVD y agrupa los
proyectos con K-Means. Cada clúster recibe un sector tecnológico según los
términos que más pesan en su centroide.
"""

import re
import unicodedata

import nltk
import numpy as np
import pandas as pd
from nltk.corpus import stopwords
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

from src.configuracion import (
    MAX_CARACTERISTICAS,
    MAX_PROPORCION_DOCS,
    MIN_DOCUMENTOS,
    MUESTRA_SILHOUETTE,
    N_CLUSTERS,
    N_COMPONENTES,
    N_TERMINOS_CLUSTER,
    PALABRAS_VACIAS_EXTRA,
    RANGO_K_EVALUACION,
    SECTOR_MULTISECTORIAL,
    SECTOR_SIN_CLASIFICAR,
    SECTORES_TECNOLOGICOS,
    SEMILLA,
    SIN_CLUSTER,
    UMBRAL_DOMINANCIA_SECTOR,
)
from src.validacion import validar_columnas

COLUMNAS_ENTRADA = ["Contrato", "Titulo_Proyecto", "Monto_Estado", "Aporte_Privado_Total"]


# ==============================================================================
# Preprocesamiento
# ==============================================================================

def cargar_palabras_vacias() -> set[str]:
    """
    Construye el conjunto de stopwords en español más los términos propios
    de los títulos de ProInnóvate.

    Las stopwords de NLTK traen tildes ('está', 'más') y los títulos ya no las
    tienen después del ETL, así que se normalizan igual para que coincidan.

    Returns:
        Conjunto de palabras a descartar, en minúsculas y sin tildes.
    """
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)

    try:
        palabras_nltk = stopwords.words("spanish")
    except LookupError:
        # Sin conexión no se puede descargar el corpus; el pipeline sigue con
        # la lista propia, que cubre los conectores más frecuentes
        print("   Aviso: no se encontraron las stopwords de NLTK. Se usa solo la lista propia.")
        palabras_nltk = []

    palabras_sin_tilde = {
        "".join(c for c in unicodedata.normalize("NFKD", palabra) if not unicodedata.combining(c))
        for palabra in palabras_nltk
    }
    return palabras_sin_tilde | PALABRAS_VACIAS_EXTRA


def preprocesar_titulo(texto: object, palabras_vacias: set[str]) -> str:
    """
    Tokeniza un título y descarta las palabras vacías.

    Args:
        texto: Título del proyecto, ya en mayúsculas y sin tildes.
        palabras_vacias: Palabras que no aportan significado.

    Returns:
        Los tokens útiles en minúsculas separados por espacios.
    """
    # Los títulos vacíos llegan como NaN (float) desde el ETL
    if not isinstance(texto, str):
        return ""

    # Solo palabras de 3 letras o más: las más cortas son siglas o conectores.
    # palabras_vacias es un conjunto, así cada token se descarta en O(1) y el
    # título completo cuesta O(t) con t tokens.
    tokens = re.findall(r"[A-Z]{3,}", texto.upper())
    tokens_limpios = [t.lower() for t in tokens if t.lower() not in palabras_vacias]
    return " ".join(tokens_limpios)


def vectorizar_titulos(corpus: list[str]) -> tuple[TfidfVectorizer, TruncatedSVD, np.ndarray]:
    """
    Convierte los títulos en vectores TF-IDF y reduce su dimensión con SVD.

    Args:
        corpus: Títulos preprocesados.

    Returns:
        El vectorizador, el modelo SVD y la matriz reducida y normalizada.
    """
    vectorizador = TfidfVectorizer(
        max_features=MAX_CARACTERISTICAS,
        ngram_range=(1, 2),          # los bigramas capturan frases como "norma iso"
        min_df=MIN_DOCUMENTOS,
        max_df=MAX_PROPORCION_DOCS,
        sublinear_tf=True,
    )
    matriz_tfidf = vectorizador.fit_transform(corpus)

    n_comp_real = min(N_COMPONENTES, matriz_tfidf.shape[1] - 1, matriz_tfidf.shape[0] - 1)
    svd = TruncatedSVD(n_components=n_comp_real, random_state=SEMILLA)
    matriz_svd = svd.fit_transform(matriz_tfidf)
    print(
        f"   Matriz TF-IDF: {matriz_tfidf.shape[0]:,} x {matriz_tfidf.shape[1]:,} | "
        f"SVD {n_comp_real} componentes, varianza explicada {svd.explained_variance_ratio_.sum():.1%}"
    )

    # Con vectores de norma 1, la distancia euclidiana de K-Means equivale a
    # la similitud coseno, que es la adecuada para textos
    matriz_norm = normalize(matriz_svd)
    return vectorizador, svd, matriz_norm


# ==============================================================================
# Clustering
# ==============================================================================

def entrenar_kmeans(matriz: np.ndarray, n_clusters: int) -> KMeans:
    """
    Entrena K-Means sobre la matriz de títulos.

    Args:
        matriz: Títulos vectorizados y normalizados.
        n_clusters: Número de clústeres.

    Returns:
        El modelo entrenado.
    """
    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=15,
        max_iter=300,
        random_state=SEMILLA,
    )
    return kmeans.fit(matriz)


def evaluar_numero_clusters(matriz: np.ndarray, valores_k: list[int]) -> pd.DataFrame:
    """
    Calcula el silhouette y la inercia para varios valores de k.

    Args:
        matriz: Títulos vectorizados y normalizados.
        valores_k: Números de clústeres a comparar.

    Returns:
        Una fila por k con su silhouette (coseno) e inercia.
    """
    generador = np.random.default_rng(SEMILLA)
    tamanio_muestra = min(MUESTRA_SILHOUETTE, len(matriz))
    indices_muestra = generador.choice(len(matriz), tamanio_muestra, replace=False)

    resultados = []
    for k in valores_k:
        modelo = entrenar_kmeans(matriz, k)
        silhouette = silhouette_score(
            matriz[indices_muestra], modelo.labels_[indices_muestra], metric="cosine"
        )
        resultados.append({"K": k, "Silhouette": round(silhouette, 4), "Inercia": round(modelo.inertia_, 1)})

    return pd.DataFrame(resultados)


def asignar_sector(pesos_terminos: pd.Series) -> str:
    """
    Elige el sector tecnológico cuyos términos pesan más en un centroide.

    Args:
        pesos_terminos: Peso de cada término del vocabulario en el centroide.

    Returns:
        El nombre del sector, o MULTISECTORIAL si ninguno domina.
    """
    puntajes = {
        sector: pesos_terminos.reindex(terminos).clip(lower=0).sum()
        for sector, terminos in SECTORES_TECNOLOGICOS.items()
    }
    puntaje_total = sum(puntajes.values())

    if puntaje_total == 0:
        return SECTOR_MULTISECTORIAL

    sector_ganador = max(puntajes, key=puntajes.get)
    dominancia = puntajes[sector_ganador] / puntaje_total

    if dominancia < UMBRAL_DOMINANCIA_SECTOR:
        return SECTOR_MULTISECTORIAL
    return sector_ganador


def describir_clusters(
    kmeans: KMeans,
    svd: TruncatedSVD,
    vectorizador: TfidfVectorizer,
) -> pd.DataFrame:
    """
    Obtiene los términos principales y el sector de cada clúster.

    Args:
        kmeans: Modelo entrenado.
        svd: Modelo SVD usado para reducir la matriz.
        vectorizador: Vectorizador TF-IDF con el vocabulario.

    Returns:
        Una fila por clúster con sus términos principales y su sector.
    """
    vocabulario = vectorizador.get_feature_names_out()

    # Los centroides viven en el espacio SVD; inverse_transform los devuelve al
    # espacio de términos (n_clusters x n_terminos) para poder leerlos
    centroides = svd.inverse_transform(kmeans.cluster_centers_)

    filas = []
    for id_cluster, centroide in enumerate(centroides):
        pesos = pd.Series(centroide, index=vocabulario)
        terminos_top = pesos.nlargest(N_TERMINOS_CLUSTER).index.tolist()

        filas.append({
            "Cluster_Innovacion": id_cluster,
            "Sector_Tecnologico": asignar_sector(pesos),
            "Cluster_Terminos": " / ".join(terminos_top[:3]),
            "Terminos_Principales": ", ".join(terminos_top),
        })

    return pd.DataFrame(filas)


def resumir_clusters(df: pd.DataFrame, descripcion: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega a la descripción de cada clúster su tamaño y su peso financiero.

    Args:
        df: Dataset con la columna Cluster_Innovacion.
        descripcion: Términos y sector de cada clúster.

    Returns:
        La descripción con proyectos, montos y apalancamiento por clúster.
    """
    agregados = (
        df[df["Cluster_Innovacion"] != SIN_CLUSTER]
        .groupby("Cluster_Innovacion", as_index=False)
        .agg(
            N_Proyectos=("Contrato", "count"),
            Monto_Estado=("Monto_Estado", "sum"),
            Aporte_Privado=("Aporte_Privado_Total", "sum"),
        )
    )
    agregados["Ratio_Apalancamiento_Privado"] = (
        agregados["Aporte_Privado"] / agregados["Monto_Estado"].replace(0, np.nan)
    ).round(4)

    return descripcion.merge(agregados, on="Cluster_Innovacion", how="left")


# ==============================================================================
# Ejecución de la fase
# ==============================================================================

def ejecutar_clustering(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Ejecuta la Fase 2 y asigna un clúster y un sector tecnológico a cada
    proyecto.

    Args:
        df: Dataset con las métricas financieras.

    Returns:
        El dataset con Titulo_Procesado, Cluster_Innovacion, Cluster_Terminos
        y Sector_Tecnologico; la evaluación de k (silhouette e inercia) y el
        resumen de clústeres.

    Raises:
        ErrorValidacionDatos: Si el dataset no trae los títulos o las métricas.
    """
    print("\nFASE 2: NLP y clustering de títulos")
    validar_columnas(df, COLUMNAS_ENTRADA, "Clustering")

    palabras_vacias = cargar_palabras_vacias()
    df["Titulo_Procesado"] = df["Titulo_Proyecto"].apply(preprocesar_titulo, args=(palabras_vacias,))

    # Un título con 5 caracteres útiles o menos (por ejemplo, solo el nombre de
    # la empresa) no permite inferir la tecnología del proyecto
    mascara_valida = df["Titulo_Procesado"].str.len() > 5
    corpus = df.loc[mascara_valida, "Titulo_Procesado"].tolist()
    print(f"   Títulos válidos para NLP: {len(corpus):,} de {len(df):,}")

    vectorizador, svd, matriz_norm = vectorizar_titulos(corpus)

    evaluacion = evaluar_numero_clusters(matriz_norm, RANGO_K_EVALUACION)
    print("   Evaluación de k (silhouette coseno):")
    for fila in evaluacion.itertuples():
        print(f"      k={fila.K:<3} silhouette={fila.Silhouette:.4f}  inercia={fila.Inercia:,.1f}")

    kmeans = entrenar_kmeans(matriz_norm, N_CLUSTERS)

    df["Cluster_Innovacion"] = SIN_CLUSTER
    df.loc[mascara_valida, "Cluster_Innovacion"] = kmeans.labels_

    descripcion = describir_clusters(kmeans, svd, vectorizador)
    df = df.merge(
        descripcion[["Cluster_Innovacion", "Cluster_Terminos", "Sector_Tecnologico"]],
        on="Cluster_Innovacion",
        how="left",
    )
    df["Sector_Tecnologico"] = df["Sector_Tecnologico"].fillna(SECTOR_SIN_CLASIFICAR)
    df["Cluster_Terminos"] = df["Cluster_Terminos"].fillna(SECTOR_SIN_CLASIFICAR)

    resumen = resumir_clusters(df, descripcion)

    print(f"   Clústeres con k={N_CLUSTERS}:")
    for fila in resumen.itertuples():
        print(f"      {fila.Cluster_Innovacion}: {fila.Sector_Tecnologico:<30} {fila.N_Proyectos:>5,}  [{fila.Cluster_Terminos}]")

    return df, evaluacion, resumen
