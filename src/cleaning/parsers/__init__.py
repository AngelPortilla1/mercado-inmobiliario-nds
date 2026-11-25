"""
Registro y orquestación de parsers de fuentes crudas (`data/raw/<fuente>/<fecha>/`).

Cada fuente aprobada en docs/legal.md se registra en `PARSER_REGISTRY` mediante una
función con firma:
    parser_fn(source_date_dir: Path, capture_date: str) -> List[RawListing]

En el Paso 2 se conectarán `fincaraiz` y `rentabien`, y en el Paso 3 `bermudez`,
`casaclick` e `inmobiliariapamplona`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

from src.cleaning.parsers.bermudez import parse_bermudez_dir
from src.cleaning.parsers.casaclick import parse_casaclick_dir
from src.cleaning.parsers.fincaraiz import parse_fincaraiz_dir
from src.cleaning.parsers.inmobiliariapamplona import parse_inmopamplona_dir
from src.cleaning.parsers.rentabien import parse_rentabien_dir
from src.cleaning.parsers.schema import (
    AUDIT_COLUMNS,
    DERIVED_COLUMNS,
    INTERIM_COLUMNS,
    PARSER_COLUMNS,
    STANDARD_COLUMNS,
    RawListing,
    listings_to_dataframe,
    validate_raw_dataframe,
)

logger = logging.getLogger(__name__)

SourceParser = Callable[[Path, str], List[RawListing]]

# Mapa completo de las 5 fuentes aprobadas en docs/legal.md
PARSER_REGISTRY: Dict[str, SourceParser] = {
    "fincaraiz": parse_fincaraiz_dir,
    "rentabien": parse_rentabien_dir,
    "bermudez": parse_bermudez_dir,
    "casaclick": parse_casaclick_dir,
    "inmobiliariapamplona": parse_inmopamplona_dir,
}


def register_parser(source_name: str, parser_fn: SourceParser) -> None:
    """Registra una función parser para una fuente normalizada en minúsculas."""
    key = source_name.strip().lower()
    if not key:
        raise ValueError("El nombre de la fuente no puede estar vacío.")
    PARSER_REGISTRY[key] = parser_fn


def list_available_capture_dates(raw_base_dir: Path = Path("data/raw")) -> List[str]:
    """
    Descubre todas las fechas de captura (`YYYY-MM-DD`) existentes en `data/raw/*/`.
    """
    if not raw_base_dir.exists():
        return []
    dates = set()
    for source_dir in raw_base_dir.iterdir():
        if not source_dir.is_dir():
            continue
        for date_dir in source_dir.iterdir():
            if date_dir.is_dir():
                dates.add(date_dir.name)
    return sorted(dates)


def parse_source_raw(
    source: str,
    capture_date: str,
    raw_base_dir: Path = Path("data/raw"),
    registry: Optional[Dict[str, SourceParser]] = None,
) -> pd.DataFrame:
    """
    Parsea todos los archivos crudos de una fuente específica para una fecha dada
    y retorna un DataFrame con el esquema exacto `PARSER_COLUMNS`.
    """
    source_key = source.strip().lower()
    active_registry = registry if registry is not None else PARSER_REGISTRY

    if source_key not in active_registry:
        raise KeyError(
            f"No existe un parser registrado para la fuente {source_key!r}. "
            f"Fuentes registradas: {sorted(active_registry.keys())}"
        )

    source_date_dir = raw_base_dir / source_key / capture_date
    if not source_date_dir.exists():
        logger.warning(
            "[Parsers] Directorio crudo no encontrado para %s (%s): %s",
            source_key,
            capture_date,
            source_date_dir,
        )
        return listings_to_dataframe([])

    records = active_registry[source_key](source_date_dir, capture_date)
    df = listings_to_dataframe(records)
    logger.info(
        "[Parsers] %s (%s) -> %d avisos parseados al formato estándar.",
        source_key,
        capture_date,
        len(df),
    )
    return df


def parse_all_raw(
    capture_date: str,
    raw_base_dir: Path = Path("data/raw"),
    sources: Optional[Sequence[str]] = None,
    registry: Optional[Dict[str, SourceParser]] = None,
) -> pd.DataFrame:
    """
    Ejecuta todos los parsers registrados (o el subconjunto indicado en `sources`)
    para `capture_date` y concatena el resultado en un único DataFrame uniforme.
    """
    active_registry = registry if registry is not None else PARSER_REGISTRY
    target_sources = list(sources) if sources is not None else list(active_registry.keys())

    if not target_sources:
        logger.warning("[Parsers] No hay fuentes registradas para parsear en %s.", capture_date)
        return listings_to_dataframe([])

    frames: List[pd.DataFrame] = []
    for src in target_sources:
        df_src = parse_source_raw(
            source=src,
            capture_date=capture_date,
            raw_base_dir=raw_base_dir,
            registry=active_registry,
        )
        if not df_src.empty:
            frames.append(df_src)

    if not frames:
        return listings_to_dataframe([])

    combined = pd.concat(frames, ignore_index=True)
    return combined.reindex(columns=list(PARSER_COLUMNS))


__all__ = [
    "AUDIT_COLUMNS",
    "DERIVED_COLUMNS",
    "INTERIM_COLUMNS",
    "PARSER_COLUMNS",
    "PARSER_REGISTRY",
    "STANDARD_COLUMNS",
    "RawListing",
    "SourceParser",
    "list_available_capture_dates",
    "listings_to_dataframe",
    "parse_all_raw",
    "parse_source_raw",
    "register_parser",
    "validate_raw_dataframe",
]
