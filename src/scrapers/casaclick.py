"""
Scraper de refuerzo local para Pamplona: Casa Click (casaclick.co/ciudad/pamplona/).
Extrae el listado HTML de propiedades en Pamplona, elimina nombres de agentes
y fotografías (PII/multimedia) antes de persistir el HTML crudo en
data/raw/casaclick/<AAAA-MM-DD>/.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

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

SOURCE_NAME = "casaclick"
BASE_PAMPLONA_URL = "https://www.casaclick.co/ciudad/pamplona/"

AGENT_SELECTORS = [
    ".unit-agent-wrapper",
    ".agent_unit",
    ".property_agent_wrapper",
    ".agent_card_my_listings",
]


def count_casaclick_cards(html: str) -> int:
    """Cuenta las tarjetas de inmuebles (.property_listing) presentes en la página."""
    soup = BeautifulSoup(html, "lxml")
    return len(soup.select(".property_listing"))


def scrape_casaclick(
    max_pages: int = 5,
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    min_delay: float = 3.0,
    max_delay: float = 6.0,
) -> ScrapeResult:
    """
    Descarga las páginas de Casa Click para Pamplona (/ciudad/pamplona/),
    sanitiza PII/imágenes y guarda el HTML crudo en data/raw/casaclick/<AAAA-MM-DD>/.
    """
    day_str = capture_date or date.today().isoformat()
    result = ScrapeResult(fuente=SOURCE_NAME, fecha_captura=day_str)
    result.desglose["pamplona_todas"] = 0
    session = create_ethical_session()

    for page in range(1, max_pages + 1):
        url = BASE_PAMPLONA_URL if page == 1 else f"{BASE_PAMPLONA_URL}page/{page}/"
        try:
            raw_html = fetch(
                url,
                session=session,
                min_delay=min_delay,
                max_delay=max_delay,
            )
            sanitized_html = strip_html_pii(raw_html, extra_selectors=AGENT_SELECTORS)
            n_cards = count_casaclick_cards(sanitized_html)

            if n_cards == 0 and page > 1:
                break

            file_stem = f"pamplona_p{page:02d}"
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
            result.desglose["pamplona_todas"] += n_cards
            result.archivos_crudos.append(str(saved_path))

            logger.info(
                "[CasaClick] pamplona | pág %d -> %d avisos detectados",
                page,
                n_cards,
            )

            # Verificar si existe enlace a página siguiente en la paginación
            soup = BeautifulSoup(sanitized_html, "lxml")
            next_links = [
                a.get("href", "")
                for a in soup.select(".pagination a")
                if f"/page/{page + 1}" in a.get("href", "")
            ]
            if not next_links:
                break

        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404 and page > 1:
                break
            msg = f"Error HTTP en {url}: {exc}"
            logger.error("[CasaClick] %s", msg)
            result.errores.append(msg)
            break
        except Exception as exc:
            msg = f"Error en {url}: {exc}"
            logger.error("[CasaClick] %s", msg)
            result.errores.append(msg)
            break

    logger.info(
        "=== Resumen CasaClick: %d páginas descargadas, %d avisos detectados, %d errores ===",
        result.paginas_descargadas,
        result.avisos_detectados,
        len(result.errores),
    )
    return result


if __name__ == "__main__":
    from src.scrapers.base_scraper import configure_scraper_logging

    configure_scraper_logging()
    scrape_casaclick()
