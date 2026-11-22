"""
Scraper de refuerzo local para Pamplona: Inmobiliaria Bermúdez
(inmobiliariabermudez.com/arrienda y /vende).

CUMPLIMIENTO ESTRICTO DE ROBOTS.TXT:
El archivo https://www.inmobiliariabermudez.com/robots.txt especifica:
    Crawl-delay: 10
Por tanto, este scraper aplica una pausa obligatoria de 10 a 12 segundos
entre cada petición HTTP (min_delay=10.0, max_delay=12.0).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import (
    ScrapeResult,
    create_ethical_session,
    fetch,
    save_raw,
    strip_html_pii,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "bermudez"
BASE_URL = "https://www.inmobiliariabermudez.com"
BERMUDEZ_MIN_DELAY = 10.0
BERMUDEZ_MAX_DELAY = 12.0

RUTAS_OPERACION: Dict[str, str] = {
    "arriendo": "arrienda",
    "venta": "vende",
}


def count_bermudez_cards(html: str) -> int:
    """
    Cuenta los avisos principales (.view-id-arrienda .item.span9) en la página
    excluyendo el bloque lateral de destacados (.view-id-apartments).
    """
    soup = BeautifulSoup(html, "lxml")
    return len(soup.select(".view-id-arrienda .item.span9"))


def get_bermudez_max_page_index(html: str) -> int:
    """
    Detecta el índice máximo de paginación 0-based (?page=N) dentro de la vista principal.
    """
    soup = BeautifulSoup(html, "lxml")
    max_idx = 0
    for a_tag in soup.select(".view-id-arrienda .pagination a, .view-id-arrienda .pager a"):
        href = a_tag.get("href", "")
        match = re.search(r"[?&]page=(\d+)", href)
        if match:
            max_idx = max(max_idx, int(match.group(1)))
    return max_idx


def scrape_bermudez(
    operaciones: Sequence[str] = ("arriendo", "venta"),
    max_pages_per_op: int = 10,
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    min_delay: float = BERMUDEZ_MIN_DELAY,
    max_delay: float = BERMUDEZ_MAX_DELAY,
) -> ScrapeResult:
    """
    Descarga las páginas de arriendo (/arrienda) y venta (/vende) de Inmobiliaria Bermúdez
    en Pamplona respetando estrictamente Crawl-delay >= 10 segundos.
    """
    if min_delay < 10.0:
        raise ValueError(
            "Inmobiliaria Bermúdez exige Crawl-delay: 10 en su robots.txt. "
            "No se permite min_delay menor a 10.0 segundos."
        )

    day_str = capture_date or date.today().isoformat()
    result = ScrapeResult(fuente=SOURCE_NAME, fecha_captura=day_str)
    session = create_ethical_session()

    for operacion in operaciones:
        ruta = RUTAS_OPERACION.get(operacion)
        if not ruta:
            continue

        combo_key = f"pamplona_{operacion}"
        result.desglose[combo_key] = 0
        page_idx = 0
        max_page_idx = 0

        while page_idx <= max_page_idx and (page_idx + 1) <= max_pages_per_op:
            url = f"{BASE_URL}/{ruta}" if page_idx == 0 else f"{BASE_URL}/{ruta}?page={page_idx}"
            try:
                raw_html = fetch(
                    url,
                    session=session,
                    min_delay=min_delay,
                    max_delay=max_delay,
                )
                sanitized_html = strip_html_pii(raw_html)
                n_cards = count_bermudez_cards(sanitized_html)

                if page_idx == 0:
                    max_page_idx = get_bermudez_max_page_index(sanitized_html)

                if n_cards == 0 and page_idx > 0:
                    break

                human_page = page_idx + 1
                file_stem = f"pamplona_{operacion}_p{human_page:02d}"
                saved_path = save_raw(
                    source=SOURCE_NAME,
                    name=file_stem,
                    content=sanitized_html,
                    capture_date=day_str,
                    extension="html",
                    base_dir=base_dir,
                )

                result.paginas_descargadas += 1
                result.avisos_detectados += n_cards
                result.desglose[combo_key] += n_cards
                result.archivos_crudos.append(str(saved_path))

                logger.info(
                    "[Bermúdez] pamplona | %s | pág %d/%d -> %d avisos detectados (Crawl-delay >= 10s)",
                    operacion,
                    human_page,
                    min(max_page_idx + 1, max_pages_per_op),
                    n_cards,
                )
                page_idx += 1

            except Exception as exc:
                msg = f"Error en {url}: {exc}"
                logger.error("[Bermúdez] %s", msg)
                result.errores.append(msg)
                break

    logger.info(
        "=== Resumen Bermúdez: %d páginas descargadas, %d avisos detectados, %d errores ===",
        result.paginas_descargadas,
        result.avisos_detectados,
        len(result.errores),
    )
    return result


if __name__ == "__main__":
    from src.scrapers.base_scraper import configure_scraper_logging

    configure_scraper_logging()
    scrape_bermudez()
