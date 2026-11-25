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
from src.cleaning.parsers.bermudez import parse_bermudez_html
from src.cleaning.parsers.casaclick import parse_casaclick_html
from src.cleaning.parsers.fincaraiz import parse_fincaraiz_item
from src.cleaning.parsers.inmobiliariapamplona import parse_inmopamplona_detail_html
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


def test_parse_bermudez_html_extracts_admin_area_and_recovers_empty_tipo():
    sample_html = """
    <div class="view-id-arrienda">
      <div class="item span9">
        <div class="card">
          <h2 class="title"><a href="/property/apartaestudio/san-rafael/hermoso">HERMOSO APTA-ESTUDIO</a></h2>
          <div class="barrio">CONJUNTO RESIDENCIAL SAN RAFAEL</div>
          <div class="codigo">Código: 0741</div>
          <div class="price">$680 000</div>
          <div class="span5">
            <div class="content"><span class="label">Tipo:</span> Apartaestudio</div>
            <div class="content"><span class="label">Estrato:</span> 2</div>
            <div class="content"><div class="cbody"><p>1 HABITACION. ( SE CANCELA CUOTA DE ADMINISTRACIÓN $80.000).</p></div></div>
            <div class="content">
              <span class="area"><span class="label">Area:</span> 35m<sup>2</sup></span>
              <span class="bathrooms">1</span>
              <span class="bedrooms">1</span>
            </div>
          </div>
        </div>
      </div>
      <div class="item span9">
        <div class="card">
          <h2 class="title"><a href="/property/casa/centro/espaciosa-casa">ESPACIOSA CASA EN VENTA</a></h2>
          <div class="barrio">Centro</div>
          <div class="codigo">Código: 0999</div>
          <div class="price">$450 000 000</div>
          <div class="span5">
            <div class="content"><span class="label">Tipo:</span></div>
            <div class="content"><span class="label">Estrato:</span> 4</div>
            <div class="content">
              <span class="area"><span class="label">Area:</span> 218m<sup>2</sup></span>
              <span class="bathrooms">2</span>
              <span class="bedrooms">7</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="view-id-apartments"><div class="item span9">Sidebar ignorado</div></div>
    """
    records = parse_bermudez_html(sample_html, capture_date="2026-11-21", operacion="arriendo")
    assert len(records) == 2

    r1 = records[0]
    assert r1.id_aviso_fuente == "0741"
    assert r1.url == "https://www.inmobiliariabermudez.com/property/apartaestudio/san-rafael/hermoso"
    assert r1.precio == 680_000.0
    assert r1.administracion == 80_000.0
    assert r1.area_m2 == 35.0
    assert r1.habitaciones == 1
    assert r1.banos == 1
    assert r1.estrato == 2
    assert r1.estado_aviso == "activo"

    r2 = records[1]
    assert r2.id_aviso_fuente == "0999"
    assert r2.tipo_inmueble == "casa"
    assert r2.area_m2 == 218.0
    assert r2.habitaciones == 7
    assert r2.banos == 2
    assert r2.administracion is None


def test_parse_casaclick_html_separates_barrio_el_zulia_and_detects_vendido():
    sample_html = """
    <div class="property_listing" data-link="https://www.casaclick.co/propiedades/apto-ana-sofia/">
      <div class="listing_unit_price_wrapper">$240,000,000</div>
      <div class="status-wrapper"><div class="ribbon-inside Vendido">Vendido</div></div>
      <div class="property-unit-information-wrapper">
        <h4><a href="https://www.casaclick.co/propiedades/apto-ana-sofia/">Venta de Apartamento Ana Sofía</a></h4>
        <div class="property_address_type1_wrapper">
          <span class="property_area_type1"><a href="/zona/chapinero/">Chapinero</a></span>,
          <span class="property_city_type1"><a href="/ciudad/pamplona/">Pamplona</a></span>
        </div>
        <div class="property_categories_type1_wrapper">
          <a href="https://www.casaclick.co/listados/apartamento/">Apartamento</a>
        </div>
        <div class="property_details_type1_wrapper">
          <span class="property_details_type1_baths"><span class="property_details_type1_value">2</span> Baths</span>
          <span class="property_details_type1_id">ID <span class="property_details_type1_value">31071</span></span>
          <span class="property_details_type1_size"><span class="property_details_type1_value">Size <span>80 m<sup>2</sup></span></span></span>
        </div>
      </div>
    </div>
    <div class="property_listing" data-link="https://www.casaclick.co/propiedades/apto-el-zulia/">
      <div class="listing_unit_price_wrapper">$230,000,000</div>
      <div class="status-wrapper">
        <div class="ribbon-inside">Venta</div>
        <div class="ribbon-inside">En construcción</div>
      </div>
      <div class="property-unit-information-wrapper">
        <h4><a href="https://www.casaclick.co/propiedades/apto-el-zulia/">Edificios SCS en El Zulia</a></h4>
        <div class="property_address_type1_wrapper">
          <span class="property_area_type1"><a href="/zona/el-zulia/">El Zulia</a></span>,
          <span class="property_city_type1"><a href="/ciudad/pamplona/">Pamplona</a></span>
        </div>
        <div class="property_categories_type1_wrapper">
          <a href="https://www.casaclick.co/listados/apartamento/">Apartamento</a> in
          <a href="https://www.casaclick.co/tipos/venta/">Venta</a>
        </div>
        <div class="property_details_type1_wrapper">
          <span class="property_details_type1_rooms"><span class="property_details_type1_value">3</span> Rooms</span>
          <span class="property_details_type1_baths"><span class="property_details_type1_value">2</span> Baths</span>
          <span class="property_details_type1_id">ID <span class="property_details_type1_value">30851</span></span>
          <span class="property_details_type1_size"><span class="property_details_type1_value">Size <span>95 m<sup>2</sup></span></span></span>
        </div>
      </div>
    </div>
    """
    records = parse_casaclick_html(sample_html, capture_date="2026-11-21")
    assert len(records) == 2

    sold = records[0]
    assert sold.id_aviso_fuente == "31071"
    assert sold.operacion == "venta"
    assert sold.estado_aviso == "inactivo"
    assert sold.area_m2 == 80.0
    assert sold.municipio == "Pamplona"
    assert sold.barrio == "Chapinero"

    active = records[1]
    assert active.id_aviso_fuente == "30851"
    assert active.estado_aviso == "activo"
    assert active.barrio == "El Zulia"
    assert active.municipio == "Pamplona"
    assert active.habitaciones == 3
    assert active.banos == 2
    assert active.area_m2 == 95.0
    assert active.antiguedad == "En construcción"


def test_parse_inmopamplona_detail_html_isolates_tags_and_handles_contradictory_status():
    sample_html = """
    <html>
      <head>
        <link rel="canonical" href="https://inmobiliariapamplonasas.com.co/propiedades/arriendo-casa-urb-augusto-ramirez?hsLang=es" />
      </head>
      <body>
        <div class="blog-post__tags">
          <a href="/propiedades/tag/casa">Casa</a>
          <a href="/propiedades/tag/disponible">Disponible</a>
          <a href="/propiedades/tag/arrendado">Arrendado</a>
        </div>
        <h1>ARRIENDO CASA Urb. Augusto Ramírez</h1>
        <article class="blog-post__body">
          <p>UBICACIÓN: Calle 11E 12-09 Urb. Augusto Ramírez</p>
          <p>4 habitaciones amplias, 3 baños completos, 110 m², Estrato 3</p>
          <p>PRECIO: Consultar valor de arriendo</p>
        </article>
        <aside class="related-posts">
          <a href="/propiedades/tag/venta">Venta</a>
          <a href="/propiedades/tag/local">Local</a>
        </aside>
      </body>
    </html>
    """
    parsed = parse_inmopamplona_detail_html(sample_html, capture_date="2026-11-21")
    assert parsed is not None
    assert parsed.id_aviso_fuente == "arriendo-casa-urb-augusto-ramirez"
    assert parsed.url == "https://inmobiliariapamplonasas.com.co/propiedades/arriendo-casa-urb-augusto-ramirez"
    # Aislado del aside: no toma 'Venta' ni 'Local'
    assert parsed.operacion == "arriendo"
    assert parsed.tipo_inmueble == "Casa"
    # Conservador: 'Arrendado' prevalece sobre 'Disponible'
    assert parsed.estado_aviso == "inactivo"
    assert parsed.precio is None
    assert parsed.area_m2 == 110.0
    assert parsed.habitaciones == 4
    assert parsed.banos == 3
    assert parsed.estrato == 3
    assert parsed.municipio == "pamplona"


