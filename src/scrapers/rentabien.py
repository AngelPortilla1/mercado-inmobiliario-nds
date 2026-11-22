"""
Scraper para Inmobiliaria Rentabien (rentabien.com.co) — Fuente Regional 2.
Consulta el endpoint público Domus del portal para los 4 municipios objetivo:
- Pamplona (54518)
- Cúcuta (54001)
- Los Patios (54405)
- Villa del Rosario (54874)
en operaciones de 'arriendo' (biz=1) y 'venta' (biz=2).

Sanitiza la respuesta eliminando URLs de fotografías y datos de la agencia
antes de persistir el JSON crudo en data/raw/rentabien/<AAAA-MM-DD>/.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import requests

from src.scrapers.base_scraper import (
    DANE_MUNICIPIOS_OBJETIVO,
    MUNICIPIOS_OBJETIVO,
    ScrapeResult,
    create_ethical_session,
    post_json,
    save_raw,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "rentabien"
API_URL = "https://rentabien.com.co/wp-content/plugins/domus/config/api.php"

OPERACIONES_BIZ: Dict[str, int] = {
    "arriendo": 1,
    "venta": 2,
}

PII_AND_MEDIA_KEYS = (
    "image1",
    "image1_wm",
    "image2",
    "image2_wm",
    "image3",
    "image3_wm",
    "real_state",
    "real_state_name",
    "real_state_logo",
    "video",
    "tour3d",
    "comment",
    "comment2",
    "",
)


def sanitize_rentabien_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elimina campos de fotografías, logos y comentarios internos de un aviso de Rentabien.
    """
    clean_item = {k: v for k, v in item.items() if k not in PII_AND_MEDIA_KEYS}
    if "description" in clean_item and isinstance(clean_item["description"], str):
        clean_item["description"] = re.sub(
            r"(?:\+?57\s*)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}",
            "[PHONE_REDACTED]",
            clean_item["description"],
        )
    return clean_item


def scrape_rentabien(
    municipios: Sequence[str] = MUNICIPIOS_OBJETIVO,
    operaciones: Sequence[str] = ("venta", "arriendo"),
    max_pages_per_query: int = 5,
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    min_delay: float = 3.0,
    max_delay: float = 6.0,
) -> ScrapeResult:
    """
    Ejecuta la captura de Rentabien por municipio (código DANE) y operación.
    Guarda el JSON crudo sanitizado en data/raw/rentabien/<AAAA-MM-DD>/.
    """
    day_str = capture_date or date.today().isoformat()
    result = ScrapeResult(fuente=SOURCE_NAME, fecha_captura=day_str)
    session = create_ethical_session()

    for municipio in municipios:
        city_code = DANE_MUNICIPIOS_OBJETIVO.get(municipio)
        if not city_code:
            logger.warning("[Rentabien] Municipio sin código DANE configurado: %s", municipio)
            continue

        for operacion in operaciones:
            biz_code = OPERACIONES_BIZ.get(operacion)
            if not biz_code:
                continue

            combo_key = f"{municipio}_{operacion}"
            result.desglose[combo_key] = 0
            page = 1
            last_page = 1

            while page <= min(last_page, max_pages_per_query):
                query_str = f"city={city_code}&biz={biz_code}"
                if page > 1:
                    query_str += f"&page={page}"

                payload_req = {
                    "url": API_URL,
                    "method": "properties",
                    "params": [query_str],
                }
                try:
                    raw_resp = post_json(
                        url=API_URL,
                        payload=payload_req,
                        session=session,
                        min_delay=min_delay,
                        max_delay=max_delay,
                    )
                    raw_items = raw_resp.get("data") or []
                    sanitized_items = [
                        sanitize_rentabien_item(item)
                        for item in raw_items
                        if isinstance(item, dict)
                    ]
                    last_page = int(raw_resp.get("last_page") or 1)
                    total_avail = int(raw_resp.get("total") or len(sanitized_items))

                    payload_to_save = {
                        "fuente": SOURCE_NAME,
                        "fecha_captura": day_str,
                        "municipio_consulta": municipio,
                        "codigo_dane": city_code,
                        "operacion_consulta": operacion,
                        "query": query_str,
                        "current_page": int(raw_resp.get("current_page") or page),
                        "last_page": last_page,
                        "per_page": int(raw_resp.get("per_page") or 12),
                        "total_disponible": total_avail,
                        "total_items_pagina": len(sanitized_items),
                        "data": sanitized_items,
                    }

                    file_stem = f"{municipio}_{operacion}_p{page:02d}"
                    saved_path = save_raw(
                        source=SOURCE_NAME,
                        name=file_stem,
                        content=json.dumps(payload_to_save, ensure_ascii=False, indent=2),
                        capture_date=day_str,
                        extension="json",
                        base_dir=base_dir,
                    )

                    n_items = len(sanitized_items)
                    result.paginas_descargadas += 1
                    result.avisos_detectados += n_items
                    result.desglose[combo_key] += n_items
                    result.archivos_crudos.append(str(saved_path))

                    logger.info(
                        "[Rentabien] %s (%s) | %s | pág %d/%d -> %d avisos detectados (total: %d)",
                        municipio,
                        city_code,
                        operacion,
                        page,
                        min(last_page, max_pages_per_query),
                        n_items,
                        total_avail,
                    )

                    if n_items == 0 or page >= last_page:
                        break
                    page += 1

                except Exception as exc:
                    msg = f"Error en Rentabien ({query_str}): {exc}"
                    logger.error("[Rentabien] %s", msg)
                    result.errores.append(msg)
                    break

    logger.info(
        "=== Resumen Rentabien: %d páginas descargadas, %d avisos detectados, %d errores ===",
        result.paginas_descargadas,
        result.avisos_detectados,
        len(result.errores),
    )
    return result


if __name__ == "__main__":
    from src.scrapers.base_scraper import configure_scraper_logging

    configure_scraper_logging()
    scrape_rentabien()
