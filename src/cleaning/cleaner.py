"""
Módulo de limpieza y estandarización de avisos inmobiliarios (Semana 3 y Sección 7).
Implementa las 9 reglas de limpieza documentadas en docs/metodologia.md:
1. Precios y separación de administración.
2. Área en m² con filtro de plausibilidad urbana [10, 5000].
3. Marcado (no borrado ciego) de valores atípicos por IQR según (municipio, operacion).
4. Estandarización geográfica (minúsculas, sin tildes, correspondencia DANE).
5. Deduplicación intra-fuente (fecha_captura, fuente, id_aviso_fuente).
6. Deduplicación inter-fuente conservando el registro más completo.
7. Nulos sin imputación arbitraria.
8. Cálculo de precio_m2 solo con precio y área válidos.
9. Separación estricta de venta y arriendo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

MIN_AREA_M2 = 10.0
MAX_AREA_M2 = 5000.0

MAPA_MUNICIPIOS_DANE: Dict[str, str] = {
    "pamplona": "54518",
    "cucuta": "54001",
    "san jose de cucuta": "54001",
    "los patios": "54405",
    "villa del rosario": "54874",
    "el zulia": "54261",
    "san cayetano": "54673",
    "ocana": "54498",
}


def normalize_text(value: Optional[str]) -> Optional[str]:
    """Convierte a minúsculas, elimina tildes y colapsa espacios múltiples."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_price_and_admin(raw_text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Regla 1: Convierte '$ 1.300.000' a número y separa la administración si viene
    concatenada (ej. '$ 1.300.000 + $ 150.000 admin').
    """
    if raw_text is None or pd.isna(raw_text):
        return None, None

    text = str(raw_text).lower()
    # Buscar si hay segmento explícito de administración
    parts = re.split(r"\+|admin|administraci[oó]n", text, maxsplit=1)

    def _extract_number(segment: str) -> Optional[float]:
        digits = re.sub(r"[^\d]", "", segment)
        if not digits:
            return None
        val = float(digits)
        return val if val > 0 else None

    precio = _extract_number(parts[0])
    admin = _extract_number(parts[1]) if len(parts) > 1 else None
    return precio, admin


def parse_area_m2(raw_area: Any) -> Optional[float]:
    """
    Regla 2: Extrae el número de '116 m²' y descarta áreas imposibles (< 10 m² o > 5000 m²).
    """
    if raw_area is None or pd.isna(raw_area):
        return None
    if isinstance(raw_area, (int, float)):
        val = float(raw_area)
    else:
        text = str(raw_area).lower().replace("m²", "").replace("m2", "").replace("mts2", "")
        text = text.strip()
        # Si tiene coma decimal (ej. "45,5"), reemplazar por punto; si tiene punto de miles ("1.200"), quitarlo
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        elif re.match(r"^\d{1,3}(\.\d{3})+$", text):
            text = text.replace(".", "")

        match = re.search(r"\d+(?:\.\d+)?", text)
        if not match:
            return None
        val = float(match.group(0))

    if val < MIN_AREA_M2 or val > MAX_AREA_M2:
        return None
    return val


def flag_iqr_outliers(df: pd.DataFrame, col: str = "precio_m2") -> pd.Series:
    """
    Regla 3: Marca (1 = atípico, 0 = normal) usando rango intercuartílico por
    (municipio, operacion). No borra registros automáticamente.
    """
    if df.empty or col not in df.columns:
        return pd.Series(0, index=df.index, dtype=int)

    flags = pd.Series(0, index=df.index, dtype=int)
    valid = df[col].notna()

    for (_, _), group in df[valid].groupby(["municipio", "operacion"]):
        if len(group) < 4:
            continue
        q1 = group[col].quantile(0.25)
        q3 = group[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_idx = group[(group[col] < lower) | (group[col] > upper)].index
        flags.loc[outlier_idx] = 1

    return flags


def clean_listings_dataframe(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Aplica las 9 reglas de limpieza sobre un DataFrame crudo y devuelve:
    (df_limpio, reporte_calidad).
    """
    total_inicial = len(df_raw)
    df = df_raw.copy()

    # Regla 4: Normalización geográfica y de campos categóricos
    for col in ("fuente", "operacion", "tipo_inmueble", "municipio", "barrio"):
        if col in df.columns:
            df[col] = df[col].apply(normalize_text)

    # Regla 9: Validar operación estrictamente en ('venta', 'arriendo')
    invalid_op_mask = ~df["operacion"].isin(["venta", "arriendo"])
    descartados_operacion = int(invalid_op_mask.sum())
    df = df[~invalid_op_mask].copy()

    # Validar municipio contra DANE DIVIPOLA
    df["codigo_dane"] = df["municipio"].map(MAPA_MUNICIPIOS_DANE)
    invalid_muni_mask = df["codigo_dane"].isna()
    descartados_municipio = int(invalid_muni_mask.sum())
    df = df[~invalid_muni_mask].copy()

    # Regla 1: Precios y administración
    parsed_prices = df["precio"].apply(parse_price_and_admin)
    df["precio"] = [p[0] for p in parsed_prices]
    if "administracion" in df.columns:
        admin_extra = [p[1] for p in parsed_prices]
        parsed_admin = df["administracion"].apply(lambda x: parse_price_and_admin(x)[0])
        df["administracion"] = [
            a if a is not None else e for a, e in zip(parsed_admin, admin_extra)
        ]
    else:
        df["administracion"] = [p[1] for p in parsed_prices]

    # Regla 2: Área en m²
    areas_antes = df["area_m2"].notna().sum() if "area_m2" in df.columns else 0
    df["area_m2"] = df["area_m2"].apply(parse_area_m2) if "area_m2" in df.columns else np.nan
    areas_descartadas = int(areas_antes - df["area_m2"].notna().sum())

    # Regla 5: Duplicados dentro de una misma fuente en la misma fecha
    antes_dedup_intra = len(df)
    df = df.drop_duplicates(subset=["fecha_captura", "fuente", "id_aviso_fuente"], keep="first").copy()
    duplicados_intra_fuente = int(antes_dedup_intra - len(df))

    # Regla 6: Duplicados entre fuentes (conservar el registro con más campos completos)
    df["_completitud"] = df.notna().sum(axis=1)
    df["_precio_round"] = df["precio"].apply(lambda x: round(x, -4) if pd.notna(x) else -1)
    df["_area_round"] = df["area_m2"].apply(lambda x: round(x) if pd.notna(x) else -1)

    antes_dedup_inter = len(df)
    df = df.sort_values(by="_completitud", ascending=False)
    mask_valid_key = (df["_precio_round"] > 0) & (df["_area_round"] > 0)
    df_valid_key = df[mask_valid_key].drop_duplicates(
        subset=["fecha_captura", "municipio", "operacion", "barrio", "_area_round", "_precio_round", "habitaciones"],
        keep="first",
    )
    df = pd.concat([df_valid_key, df[~mask_valid_key]], ignore_index=True)
    duplicados_inter_fuente = int(antes_dedup_inter - len(df))
    df = df.drop(columns=["_completitud", "_precio_round", "_area_round"])

    # Regla 8: Precio por m² solo cuando precio y área son válidos
    df["precio_m2"] = np.where(
        df["precio"].notna() & df["area_m2"].notna() & (df["area_m2"] > 0),
        (df["precio"] / df["area_m2"]).round(2),
        np.nan,
    )

    # Regla 3: Marcar outliers por IQR según municipio y operación
    df["is_outlier_iqr"] = flag_iqr_outliers(df, col="precio_m2")

    # Reporte de calidad (Semana 3)
    pct_vacios = (df.isna().mean() * 100).round(2).to_dict()
    reporte_calidad = {
        "total_registros_entrada": total_inicial,
        "total_registros_limpios": len(df),
        "descartados_operacion_invalida": descartados_operacion,
        "descartados_municipio_fuera_alcance": descartados_municipio,
        "areas_fuera_de_rango_10_5000_m2": areas_descartadas,
        "duplicados_intra_fuente_eliminados": duplicados_intra_fuente,
        "duplicados_inter_fuente_eliminados": duplicados_inter_fuente,
        "outliers_iqr_marcados": int(df["is_outlier_iqr"].sum()),
        "porcentaje_nulos_por_campo": pct_vacios,
    }
    return df, reporte_calidad
