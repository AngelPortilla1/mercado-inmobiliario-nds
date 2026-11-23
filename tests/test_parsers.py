"""
Pruebas unitarias para el contrato y los parsers de fuentes (Semana 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import pytest

from src.cleaning.parsers import (
    AUDIT_COLUMNS,
    PARSER_COLUMNS,
    STANDARD_COLUMNS,
    RawListing,
    list_available_capture_dates,
    listings_to_dataframe,
    parse_all_raw,
    parse_source_raw,
    validate_raw_dataframe,
)


def test_raw_listing_contract_and_column_order():
    assert len(STANDARD_COLUMNS) == 16
    assert len(AUDIT_COLUMNS) == 2
    assert len(PARSER_COLUMNS) == 18

    item = RawListing(
        id_aviso_fuente=" 12345 ",
        fuente=" Fincaraiz ",
        fecha_captura="2026-11-21",
        operacion="venta",
        tipo_inmueble="Apartamento",
        municipio="Pamplona",
        precio=250_000_000,
    )
    assert item.id_aviso_fuente == "12345"
    assert item.fuente == "fincaraiz"
    assert item.estado_aviso == "activo"

    df = listings_to_dataframe([item])
    assert list(df.columns) == list(PARSER_COLUMNS)
    assert len(df) == 1
    assert df.loc[0, "precio"] == 250_000_000
    assert pd.isna(df.loc[0, "barrio"])


def test_raw_listing_rejects_invalid_estado_or_empty_id():
    with pytest.raises(ValueError, match="estado_aviso inválido"):
        RawListing(
            id_aviso_fuente="1",
            fuente="casaclick",
            fecha_captura="2026-11-21",
            estado_aviso="vendido",
        )

    with pytest.raises(ValueError, match="id_aviso_fuente"):
        RawListing(id_aviso_fuente="   ", fuente="casaclick", fecha_captura="2026-11-21")


def test_listings_to_dataframe_empty_preserves_schema():
    df_empty = listings_to_dataframe([])
    assert df_empty.empty
    assert list(df_empty.columns) == list(PARSER_COLUMNS)
    validate_raw_dataframe(df_empty)


def test_validate_raw_dataframe_detects_missing_columns():
    df_incomplete = pd.DataFrame({"id_aviso_fuente": ["1"], "fuente": ["bermudez"]})
    with pytest.raises(ValueError, match="Faltan columnas obligatorias"):
        validate_raw_dataframe(df_incomplete)


def test_parse_all_raw_with_custom_registry_and_date_discovery(tmp_path: Path):
    source_dir = tmp_path / "demo_source" / "2026-11-21"
    source_dir.mkdir(parents=True)
    (source_dir / "sample.json").write_text("{}", encoding="utf-8")

    def fake_parser(folder: Path, capture_date: str) -> List[RawListing]:
        assert folder == source_dir
        return [
            RawListing(
                id_aviso_fuente="D1",
                fuente="demo_source",
                fecha_captura=capture_date,
                operacion="arriendo",
                tipo_inmueble="Apartamento",
                municipio="Pamplona",
                municipio_consulta="pamplona",
                precio=900_000,
                area_m2=65,
            )
        ]

    registry = {"demo_source": fake_parser}
    assert list_available_capture_dates(tmp_path) == ["2026-11-21"]

    df = parse_all_raw("2026-11-21", raw_base_dir=tmp_path, registry=registry)
    assert len(df) == 1
    assert list(df.columns) == list(PARSER_COLUMNS)
    assert df.loc[0, "id_aviso_fuente"] == "D1"

    # Directorio inexistente devuelve DataFrame vacío con esquema completo
    df_missing = parse_source_raw("demo_source", "2099-01-01", raw_base_dir=tmp_path, registry=registry)
    assert df_missing.empty
    assert list(df_missing.columns) == list(PARSER_COLUMNS)

    with pytest.raises(KeyError, match="No existe un parser registrado"):
        parse_source_raw("no_existe", "2026-11-21", raw_base_dir=tmp_path, registry=registry)
