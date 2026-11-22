"""
Scraper de refuerzo local para Pamplona: Inmobiliaria Pamplona SAS
(inmobiliariapamplonasas.com.co/propiedades).
Descarga las páginas índice del catálogo (/propiedades y /propiedades/page/<n>)
y las fichas de detalle de cada inmueble para obtener habitaciones, baños,
estrato y ubicación en Pamplona, eliminando previamente bloques de contacto,
teléfonos, correos e imágenes (Regla 1: Cero PII).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import List, Optional

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

SOURCE_NAME = "inmobiliariapamplona"
BASE_URL = "https://inmobiliariapamplonasas.com.co/propiedades"


def extract_property_detail_urls(html: str) -> List[str]:
    """
    Extrae las URLs únicas de detalle de inmuebles desde una página de listado
    de Inmobiliaria Pamplona SAS (excluyendo enlaces de tags /propiedades/tag/*).
    """
    soup = BeautifulSoup(html, "lxml")
    urls: List[str] = []
    seen = set()

    for card in soup.select(".two-columns-blog-post"):
        link_tag = card.select_one("a.blog-index__post-title") or card.find("a", href=True)
        if not link_tag:
            continue
        href = link_tag.get("href", "").split("?")[0].strip()
        if "/propiedades/" in href and "/tag/" not in href and "/page/" not in href:
            if href not in seen:
                seen.add(href)
                urls.append(href)
    return urls


def sanitize_inmopamplona_html(html: str) -> str:
    """
    Elimina imágenes, enlaces de WhatsApp/teléfono y la sección de 'CONTACTO DIRECTO'
    del HTML de Inmobiliaria Pamplona SAS antes de guardarlo en disco.
    """
    cleaned = strip_html_pii(html)
    # Cortar texto de contacto directo (WhatsApp / email de la oficina) en las fichas
    cleaned = re.sub(
        r"📞\s*CONTACTO DIRECTO:.*?(?=</div|Ver todas las propiedades|$)",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned


def scrape_inmobiliariapamplona(
    max_pages: int = 5,
    include_details: bool = True,
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    min_delay: float = 3.0,
    max_delay: float = 6.0,
) -> ScrapeResult:
    """
    Descarga el catálogo de Inmobiliaria Pamplona SAS y las páginas de detalle,
    guardando el HTML crudo sanitizado en data/raw/inmobiliariapamplona/<AAAA-MM-DD>/.
    """
    day_str = capture_date or date.today().isoformat()
    result = ScrapeResult(fuente=SOURCE_NAME, fecha_captura=day_str)
    result.desglose["pamplona_catalogo"] = 0
    session = create_ethical_session()
    detail_urls: List[str] = []

    for page in range(1, max_pages + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}"
        try:
            raw_html = fetch(
                url,
                session=session,
                min_delay=min_delay,
                max_delay=max_delay,
            )
            sanitized_html = sanitize_inmopamplona_html(raw_html)
            page_detail_urls = extract_property_detail_urls(sanitized_html)

            if not page_detail_urls:
                break

            file_stem = f"pamplona_index_p{page:02d}"
            saved_path = save_raw(
                source=SOURCE_NAME,
                name=file_stem,
                content=sanitized_html,
                capture_date=day_str,
                extension="html",
                base_dir=base_dir,
            )

            n_cards = len(page_detail_urls)
            result.paginas_descargadas += 1
            result.avisos_detectados += n_cards
            result.desglose["pamplona_catalogo"] += n_cards
            result.archivos_crudos.append(str(saved_path))

            for d_url in page_detail_urls:
                if d_url not in detail_urls:
                    detail_urls.append(d_url)

            logger.info(
                "[InmobiliariaPamplona] pamplona | índice pág %d -> %d avisos detectados",
                page,
                n_cards,
            )

        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logger.info("[InmobiliariaPamplona] Fin de paginación en página %d (HTTP 404)", page)
                break
            msg = f"Error HTTP en {url}: {exc}"
            logger.error("[InmobiliariaPamplona] %s", msg)
            result.errores.append(msg)
            break
        except Exception as exc:
            msg = f"Error en {url}: {exc}"
            logger.error("[InmobiliariaPamplona] %s", msg)
            result.errores.append(msg)
            break

    if include_details and detail_urls:
        for idx, d_url in enumerate(detail_urls, start=1):
            slug = d_url.rstrip("/").split("/")[-1][:60]
            try:
                raw_detail = fetch(
                    d_url,
                    session=session,
                    min_delay=min_delay,
                    max_delay=max_delay,
                )
                sanitized_detail = sanitize_inmopamplona_html(raw_detail)
                saved_detail = save_raw(
                    source=SOURCE_NAME,
                    name=f"detalle_{idx:02d}_{slug}",
                    content=sanitized_detail,
                    capture_date=day_str,
                    extension="html",
                    base_dir=base_dir,
                )
                result.paginas_descargadas += 1
                result.archivos_crudos.append(str(saved_detail))
            except Exception as exc:
                msg = f"Error descargando detalle {d_url}: {exc}"
                logger.error("[InmobiliariaPamplona] %s", msg)
                result.errores.append(msg)

    logger.info(
        "=== Resumen InmobiliariaPamplona: %d páginas descargadas, %d avisos detectados, %d errores ===",
        result.paginas_descargadas,
        result.avisos_detectados,
        len(result.errores),
    )
    return result


if __name__ == "__main__":
    from src.scrapers.base_scraper import configure_scraper_logging

    configure_scraper_logging()
    scrape_inmobiliariapamplona()
