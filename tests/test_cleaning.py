"""Pruebas unitarias para verificar las 9 reglas de limpieza (Semana 3)."""

import pandas as pd

from src.cleaning.cleaner import (
    clean_listings_dataframe,
    normalize_text,
    parse_area_m2,
    parse_price_and_admin,
)


def test_parse_price_and_admin():
    precio, admin = parse_price_and_admin("$ 1.300.000 + $ 120.000 admin")
    assert precio == 1_300_000.0
    assert admin == 120_000.0

    precio_solo, admin_nulo = parse_price_and_admin("$ 250.000.000")
    assert precio_solo == 250_000_000.0
    assert admin_nulo is None


def test_parse_area_m2_bounds():
    assert parse_area_m2("116 m²") == 116.0
    assert parse_area_m2("45,5 m2") == 45.5
    # Regla 2: Descartar áreas menores a 10 m² o mayores a 5000 m²
    assert parse_area_m2("5 m²") is None
    assert parse_area_m2("8500 m²") is None


def test_normalize_text():
    assert normalize_text("  San José de Cúcuta ") == "san jose de cucuta"
    assert normalize_text("Pamplona") == "pamplona"


def test_clean_listings_dataframe_dedup_and_rules():
    raw = pd.DataFrame(
        [
            {
                "id_aviso_fuente": "A1",
                "fuente": "PortalX",
                "url": "https://portalx.com/pamplona/a1",
                "operacion": "Arriendo",
                "tipo_inmueble": "Apartamento",
                "municipio": "Pamplona",
                "barrio": "Centro",
                "precio": "$ 800.000 + $ 50.000 admin",
                "administracion": None,
                "area_m2": "80 m²",
                "habitaciones": 3,
                "banos": 2,
                "fecha_captura": "2026-11-20",
            },
            # Duplicado intra-fuente (mismo id_aviso_fuente, fuente y fecha)
            {
                "id_aviso_fuente": "A1",
                "fuente": "PortalX",
                "url": "https://portalx.com/pamplona/a1",
                "operacion": "Arriendo",
                "tipo_inmueble": "Apartamento",
                "municipio": "Pamplona",
                "barrio": "Centro",
                "precio": "$ 800.000",
                "administracion": None,
                "area_m2": "80 m²",
                "habitaciones": 3,
                "banos": 2,
                "fecha_captura": "2026-11-20",
            },
        ]
    )
    df_clean, report = clean_listings_dataframe(raw)
    assert len(df_clean) == 1
    assert report["duplicados_intra_fuente_eliminados"] == 1
    row = df_clean.iloc[0]
    assert row["codigo_dane"] == "54518"
    assert row["precio"] == 800_000.0
    assert row["administracion"] == 50_000.0
    assert row["precio_m2"] == 10_000.0
