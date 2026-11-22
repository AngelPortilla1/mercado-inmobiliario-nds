"""
Scraper para Fincaraíz (fincaraiz.com.co) — Fuente Regional/Nacional 1.
Cubre los 4 municipios objetivo de Norte de Santander:
- Pamplona (54518)
- Cúcuta (54001)
- Los Patios (54405)
- Villa del Rosario (54874)
en operaciones de 'venta' y 'arriendo'.

Extrae el bloque estructurado <script id="__NEXT_DATA__">, elimina cualquier
campo de PII o multimedia (owner, seller, images, img, logo, socialMediaLinks, files)
y guarda el JSON crudo sanitizado en data/raw/fincaraiz/<AAAA-MM-DD>/.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import (
    MUNICIPIOS_OBJETIVO,
    ScrapeResult,
    create_ethical_session,
    fetch,
    save_raw,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "fincaraiz"
BASE_URL = "https://www.fincaraiz.com.co"
OPERACIONES = ("venta", "arriendo")

# Campos con información de anunciantes, propietarios o fotografías que NUNCA se almacenan
PII_AND_MEDIA_KEYS = (
    "owner",
    "seller",
    "images",
    "img",
    "logo",
    "socialMediaLinks",
    "files",
    "idForm",
    "youtube",
    "tour3d",
)


def sanitize_fincaraiz_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elimina campos de propietarios, anunciantes y fotografías de un aviso de Fincaraíz.
    Conserva únicamente atributos físicos, geográficos y económicos del inmueble.
    """
    clean_item = {k: v for k, v in item.items() if k not in PII_AND_MEDIA_KEYS}
    return clean_item


def extract_sanitized_payload(
    html: str,
    municipio: str,
    operacion: str,
    url: str,
    capture_date: str,
) -> Dict[str, Any]:
    """
    Extrae searchFast de <script id="__NEXT_DATA__"> y sanitiza cada aviso.
    """
    soup = BeautifulSoup(html, "lxml")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag or not script_tag.string:
        raise ValueError(f"No se encontró <script id='__NEXT_DATA__'> en {url}")

    raw_next = json.loads(script_tag.string)
    search_fast = (
        raw_next.get("props", {})
        .get("pageProps", {})
        .get("fetchResult", {})
        .get("searchFast", {})
    )
    paginator = search_fast.get("paginatorInfo") or search_fast.get("paginator") or {}
    raw_items = search_fast.get("data") or []
    sanitized_items = [sanitize_fincaraiz_item(item) for item in raw_items if isinstance(item, dict)]

    return {
        "fuente": SOURCE_NAME,
        "fecha_captura": capture_date,
        "municipio_consulta": municipio,
        "operacion_consulta": operacion,
        "url_origen": url,
        "paginatorInfo": paginator,
        "total_items_pagina": len(sanitized_items),
        "data": sanitized_items,
    }


def build_fincaraiz_url(municipio: str, operacion: str, page: int = 1) -> str:
    """Construye la URL pública permitida por robots.txt para un municipio y operación."""
    base = f"{BASE_URL}/{operacion}/{municipio}/norte-de-santander"
    if page <= 1:
        return base
    return f"{base}/pagina{page}"


def scrape_fincaraiz(
    municipios: Sequence[str] = MUNICIPIOS_OBJETIVO,
    operaciones: Sequence[str] = OPERACIONES,
    max_pages_per_query: int = 5,
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    min_delay: float = 3.0,
    max_delay: float = 6.0,
) -> ScrapeResult:
    """
    Ejecuta la captura de Fincaraíz para los municipios y operaciones indicados.
    Guarda cada página como JSON sanitizado en data/raw/fincaraiz/<AAAA-MM-DD>/.
    """
    day_str = capture_date or date.today().isoformat()
    result = ScrapeResult(fuente=SOURCE_NAME, fecha_captura=day_str)
    session = create_ethical_session()

    for municipio in municipios:
        for operacion in operaciones:
            combo_key = f"{municipio}_{operacion}"
            result.desglose[combo_key] = 0
            page = 1
            last_page = 1

            while page <= min(last_page, max_pages_per_query):
                url = build_fincaraiz_url(municipio=municipio, operacion=operacion, page=page)
                try:
                    html = fetch(
                        url,
                        session=session,
                        min_delay=min_delay,
                        max_delay=max_delay,
                    )
                    payload = extract_sanitized_payload(
                        html=html,
                        municipio=municipio,
                        operacion=operacion,
                        url=url,
                        capture_date=day_str,
                    )
                    n_items = payload["total_items_pagina"]
                    pinfo = payload.get("paginatorInfo") or {}
                    last_page = int(pinfo.get("lastPage") or 1)

                    file_stem = f"{municipio}_{operacion}_p{page:02d}"
                    saved_path = save_raw(
                        source=SOURCE_NAME,
                        name=file_stem,
                        content=json.dumps(payload, ensure_ascii=False, indent=2),
                        capture_date=day_str,
                        extension="json",
                        base_dir=base_dir,
                    )

                    result.paginas_descargadas += 1
                    result.avisos_detectados += n_items
                    result.desglose[combo_key] += n_items
                    result.archivos_crudos.append(str(saved_path))

                    logger.info(
                        "[Fincaraíz] %s | %s | pág %d/%d -> %d avisos detectados (total disponible: %s)",
                        municipio,
                        operacion,
                        page,
                        min(last_page, max_pages_per_query),
                        n_items,
                        pinfo.get("total", n_items),
                    )

                    if n_items == 0 or not pinfo.get("hasMorePages", False):
                        break
                    page += 1

                except Exception as exc:
                    msg = f"Error en {url}: {exc}"
                    logger.error("[Fincaraíz] %s", msg)
                    result.errores.append(msg)
                    break

    logger.info(
        "=== Resumen Fincaraíz: %d páginas descargadas, %d avisos detectados, %d errores ===",
        result.paginas_descargadas,
        result.avisos_detectados,
        len(result.errores),
    )
    return result


if __name__ == "__main__":
    from src.scrapers.base_scraper import configure_scraper_logging

    configure_scraper_logging()
    scrape_fincaraiz()
