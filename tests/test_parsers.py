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
from src.cleaning.parsers.fincaraiz import parse_fincaraiz_item
from src.cleaning.parsers.rentabien import parse_rentabien_item


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


def test_parse_fincaraiz_item_resolves_url_slug_bedrooms_stratum_and_admin():
    sample_item = {
        "id": 194522321,
        "link": "/apartamento-en-arriendo-en-bellavista-cucuta/194522321",
        "operation_type": {"id": 2, "name": "Arriendo"},
        "property_type": {"id": 2, "name": "Apartamento"},
        "locations": {
            "city": [{"name": "Los patios"}, {"name": "Cúcuta"}],
            "neighbourhood": [{"name": "Bellavista"}],
        },
        "price": {"amount": 1_200_000, "admin_included": 1_432_800, "hidePrice": False},
        "commonExpenses": {"amount": 232_800, "hidePrice": False},
        "m2": 82,
        "bedrooms": 3,
        "rooms": 0,
        "bathrooms": 2,
        "garage": 1,
        "stratum": 4,
        "antiquity": "3",
        "technicalSheet": [{"field": "antiquity", "value": "9 a 15 años"}],
        "sold": False,
        "active": True,
        "deleted": False,
    }
    parsed = parse_fincaraiz_item(
        sample_item,
        capture_date="2026-11-21",
        municipio_consulta="los-patios",
        operacion_consulta="arriendo",
    )
    assert parsed is not None
    assert parsed.id_aviso_fuente == "194522321"
    assert parsed.url == "https://www.fincaraiz.com.co/apartamento-en-arriendo-en-bellavista-cucuta/194522321"
    # Municipio real viene del slug '-cucuta/', no de la consulta 'los-patios'
    assert parsed.municipio == "cucuta"
    assert parsed.municipio_consulta == "los-patios"
    assert parsed.barrio == "Bellavista"
    assert parsed.precio == 1_200_000.0
    assert parsed.administracion == 232_800.0
    assert parsed.area_m2 == 82.0
    assert parsed.habitaciones == 3
    assert parsed.banos == 2
    assert parsed.parqueaderos == 1
    assert parsed.estrato == 4
    assert parsed.antiguedad == "9 a 15 años"
    assert parsed.estado_aviso == "activo"


def test_parse_fincaraiz_item_filters_invalid_stratum_zero_admin_and_sold():
    sample_item = {
        "id": 193631576,
        "link": "/casa-en-venta-en-centro-pamplona/193631576",
        "operation_type": {"name": "Venta"},
        "property_type": {"name": "Casa"},
        "price": {"amount": 450_000_000},
        "commonExpenses": {"amount": 0},
        "m2": 180,
        "bedrooms": 4,
        "bathrooms": 3,
        "garage": 0,
        "stratum": 110,  # Código interno inválido (fuera de 1..6)
        "antiquity": "5",
        "technicalSheet": [],
        "sold": True,
        "active": True,
    }
    parsed = parse_fincaraiz_item(sample_item, capture_date="2026-11-21", municipio_consulta="pamplona")
    assert parsed is not None
    assert parsed.municipio == "pamplona"
    assert parsed.administracion is None
    assert parsed.estrato is None
    assert parsed.antiguedad == "más de 30 años"
    assert parsed.parqueaderos == 0
    assert parsed.estado_aviso == "inactivo"


def test_parse_rentabien_item_handles_mixed_biz_and_reference_arrendado():
    # Caso 1: ARRIENDO/VENTA con price compuesto "9000000/480000000" consultado como arriendo
    mixed_item = {
        "codpro": 5711,
        "idpro": 483651,
        "city": "Villa Del Rosario ",
        "city_code": 54874,
        "neighborhood": "Centro",
        "type": "CONSULTORIO",
        "biz": "ARRIENDO/VENTA",
        "biz_code": 3,
        "area_cons": 120,
        "area_lot": 120,
        "bedrooms": 0,
        "bathrooms": 2,
        "price": "9000000/480000000",
        "rent": 9_000_000,
        "saleprice": 480_000_000,
        "administration": 0,
        "parking": 1,
        "stratum": 4,
        "build_year": 2015,
        "status": 1,
        "status_name": "Disponible",
        "reference": "Desocupado",
    }
    parsed_arr = parse_rentabien_item(
        mixed_item,
        capture_date="2026-11-21",
        municipio_consulta="villa-del-rosario",
        operacion_consulta="arriendo",
    )
    assert parsed_arr is not None
    assert parsed_arr.id_aviso_fuente == "5711"
    assert parsed_arr.url is None
    assert parsed_arr.operacion == "arriendo"
    assert parsed_arr.precio == 9_000_000.0
    assert parsed_arr.administracion is None
    assert parsed_arr.municipio == "villa del rosario"
    assert parsed_arr.habitaciones is None
    assert parsed_arr.antiguedad == "2015"
    assert parsed_arr.estado_aviso == "activo"

    # Caso 2: VENTA con reference="Arrendado" pero status_name="Disponible" (sigue activo en venta)
    sale_with_tenant = {
        "codpro": 15794,
        "city": "Cúcuta",
        "city_code": 54001,
        "neighborhood": "Caobos",
        "type": "CASA",
        "biz": "VENTA",
        "biz_code": 2,
        "area_cons": 0,
        "area_lot": 180,
        "bedrooms": 3,
        "bathrooms": 2,
        "price": "200000000",
        "rent": 0,
        "saleprice": 200_000_000,
        "administration": 150_000,
        "parking": 1,
        "stratum": 4,
        "build_year": 0,
        "status": 1,
        "status_name": "Disponible",
        "reference": "Arrendado",
    }
    parsed_sale = parse_rentabien_item(
        sale_with_tenant,
        capture_date="2026-11-21",
        municipio_consulta="cucuta",
        operacion_consulta="venta",
    )
    assert parsed_sale is not None
    assert parsed_sale.operacion == "venta"
    assert parsed_sale.precio == 200_000_000.0
    assert parsed_sale.administracion == 150_000.0
    assert parsed_sale.area_m2 == 180.0
    assert parsed_sale.antiguedad is None
    assert parsed_sale.estado_aviso == "activo"

