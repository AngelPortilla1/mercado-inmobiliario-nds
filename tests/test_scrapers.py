"""
Pruebas unitarias para los scrapers de la Semana 2:
- Sanitización estricta de PII y fotografías (Regla 1: Cero Datos Personales).
- Extracción y conteo de avisos en Fincaraíz, Rentabien, Casa Click, Inmobiliaria Pamplona SAS y Bermúdez.
- Validación de Crawl-delay >= 10s en Inmobiliaria Bermúdez.
- Persistencia del crudo en data/raw/<fuente>/<AAAA-MM-DD>/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scrapers.base_scraper import save_raw, strip_html_pii
from src.scrapers.bermudez import (
    count_bermudez_cards,
    get_bermudez_max_page_index,
    scrape_bermudez,
)
from src.scrapers.casaclick import AGENT_SELECTORS, count_casaclick_cards
from src.scrapers.fincaraiz import extract_sanitized_payload, sanitize_fincaraiz_item
from src.scrapers.inmobiliariapamplona import (
    extract_property_detail_urls,
    sanitize_inmopamplona_html,
)
from src.scrapers.rentabien import sanitize_rentabien_item


def test_strip_html_pii_removes_images_phones_emails_and_agents():
    raw_html = """
    <html>
      <body>
        <div class="property_listing">
          <img src="https://ejemplo.com/foto.jpg" />
          <a href="https://wa.me/+573128972899">WhatsApp</a>
          <a href="tel:3151234567">Llamar</a>
          <a href="mailto:ventas@inmobiliaria.com">Correo</a>
          <p>Contacto directo al 312 897 2899 o correo asesor@portal.co</p>
          <div class="unit-agent-wrapper">Marco Gutiérrez</div>
          <span class="price">$ 240.000.000</span>
        </div>
      </body>
    </html>
    """
    cleaned = strip_html_pii(raw_html, extra_selectors=AGENT_SELECTORS)
    assert "<img" not in cleaned
    assert "wa.me" not in cleaned
    assert "tel:" not in cleaned
    assert "mailto:" not in cleaned
    assert "312 897 2899" not in cleaned
    assert "asesor@portal.co" not in cleaned
    assert "Marco Gutiérrez" not in cleaned
    assert "$ 240.000.000" in cleaned


def test_sanitize_fincaraiz_item_and_payload():
    sample_html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {
      "props": {
        "pageProps": {
          "fetchResult": {
            "searchFast": {
              "paginatorInfo": {"currentPage": 1, "lastPage": 1, "total": 1, "hasMorePages": false},
              "data": [
                {
                  "id": 194426075,
                  "title": "Casa en Venta en El centro, Pamplona",
                  "price": {"amount": 900000000},
                  "m2": 180,
                  "rooms": 4,
                  "bathrooms": 3,
                  "owner": {"name": "Juan Perez", "phone": "3100000000"},
                  "seller": {"name": "Inmobiliaria X"},
                  "images": ["https://cdn.com/1.jpg"],
                  "img": "https://cdn.com/main.jpg"
                }
              ]
            }
          }
        }
      }
    }
    </script>
    </body></html>
    """
    payload = extract_sanitized_payload(
        html=sample_html,
        municipio="pamplona",
        operacion="venta",
        url="https://www.fincaraiz.com.co/venta/pamplona/norte-de-santander",
        capture_date="2026-11-21",
    )
    assert payload["total_items_pagina"] == 1
    item = payload["data"][0]
    assert item["id"] == 194426075
    assert "owner" not in item
    assert "seller" not in item
    assert "images" not in item
    assert "img" not in item


def test_sanitize_rentabien_item():
    raw_item = {
        "codpro": 15801,
        "city": "Pamplona",
        "city_code": 54518,
        "price": "160000000",
        "description": "Hermoso apartamento en Pamplona. Llamar al 311 456 7890.",
        "image1": "https://s3.amazonaws.com/pic1.jpg",
        "real_state_name": "RENTABIEN SAS",
        "real_state_logo": "https://logo.jpg",
    }
    clean = sanitize_rentabien_item(raw_item)
    assert clean["codpro"] == 15801
    assert "image1" not in clean
    assert "real_state_name" not in clean
    assert "real_state_logo" not in clean
    assert "311 456 7890" not in clean["description"]


def test_casaclick_and_inmopamplona_and_bermudez_parsers():
    casaclick_html = '<div class="property_listing">A</div><div class="property_listing">B</div>'
    assert count_casaclick_cards(casaclick_html) == 2

    inmo_html = """
    <div class="two-columns-blog-post">
      <a class="blog-index__post-title" href="https://inmobiliariapamplonasas.com.co/propiedades/arriendo-apto-centro?hsLang=en">Apto</a>
      <a href="https://inmobiliariapamplonasas.com.co/propiedades/tag/arriendo">Tag</a>
    </div>
    """
    urls = extract_property_detail_urls(inmo_html)
    assert urls == ["https://inmobiliariapamplonasas.com.co/propiedades/arriendo-apto-centro"]

    bermudez_html = """
    <div class="view view-id-arrienda">
      <div class="item span9">Card 1</div>
      <div class="item span9">Card 2</div>
      <div class="pagination">
        <a href="/arrienda?page=1">2</a>
        <a href="/arrienda?page=4">Último</a>
      </div>
    </div>
    <div class="view view-id-apartments">
      <div class="views-row">Sidebar</div>
    </div>
    """
    assert count_bermudez_cards(bermudez_html) == 2
    assert get_bermudez_max_page_index(bermudez_html) == 4


def test_bermudez_enforces_10s_crawl_delay(tmp_path: Path):
    with pytest.raises(ValueError, match="Crawl-delay: 10"):
        scrape_bermudez(min_delay=3.0, max_delay=6.0, base_dir=tmp_path)


def test_save_raw_creates_dated_folder(tmp_path: Path):
    saved = save_raw(
        source="fincaraiz",
        name="pamplona_venta_p01",
        content=json.dumps({"ok": True}),
        capture_date="2026-11-21",
        extension="json",
        base_dir=tmp_path,
    )
    assert saved.exists()
    assert saved.parent == tmp_path / "fincaraiz" / "2026-11-21"
