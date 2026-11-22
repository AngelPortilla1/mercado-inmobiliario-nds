"""
Registro y orquestación de todos los scrapers aprobados en docs/legal.md:
1. Fincaraíz (fincaraiz.com.co) — Pamplona, Cúcuta, Los Patios, Villa del Rosario
2. Inmobiliaria Rentabien (rentabien.com.co) — Pamplona, Cúcuta, Los Patios, Villa del Rosario
3. Casa Click (casaclick.co) — Refuerzo muestra Pamplona
4. Inmobiliaria Pamplona SAS (inmobiliariapamplonasas.com.co) — Refuerzo muestra Pamplona
5. Inmobiliaria Bermúdez (inmobiliariabermudez.com) — Refuerzo muestra Pamplona (Crawl-delay: 10s)
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from src.scrapers.base_scraper import ScrapeResult, configure_scraper_logging
from src.scrapers.bermudez import scrape_bermudez
from src.scrapers.casaclick import scrape_casaclick
from src.scrapers.fincaraiz import scrape_fincaraiz
from src.scrapers.inmobiliariapamplona import scrape_inmobiliariapamplona
from src.scrapers.rentabien import scrape_rentabien

logger = logging.getLogger(__name__)


def run_all_scrapers(
    capture_date: Optional[str] = None,
    base_dir: Path = Path("data/raw"),
    max_pages_fincaraiz: int = 5,
    max_pages_rentabien: int = 5,
    include_inmopamplona_details: bool = True,
) -> List[ScrapeResult]:
    """
    Ejecuta secuencialmente todos los scrapers aprobados, respetando los tiempos
    de pausa por dominio y registrando estadísticas detalladas en reports/.
    """
    day_str = capture_date or date.today().isoformat()
    log_path = configure_scraper_logging(capture_date=day_str)
    logger.info("=== Iniciando recolección semanal de las 5 fuentes aprobadas (%s) ===", day_str)
    logger.info("Archivo de log: %s", log_path)

    results: List[ScrapeResult] = []

    # 1. Fincaraíz
    results.append(
        scrape_fincaraiz(
            max_pages_per_query=max_pages_fincaraiz,
            capture_date=day_str,
            base_dir=base_dir,
        )
    )

    # 2. Rentabien
    results.append(
        scrape_rentabien(
            max_pages_per_query=max_pages_rentabien,
            capture_date=day_str,
            base_dir=base_dir,
        )
    )

    # 3. Casa Click (Refuerzo Pamplona)
    results.append(
        scrape_casaclick(
            capture_date=day_str,
            base_dir=base_dir,
        )
    )

    # 4. Inmobiliaria Pamplona SAS (Refuerzo Pamplona)
    results.append(
        scrape_inmobiliariapamplona(
            include_details=include_inmopamplona_details,
            capture_date=day_str,
            base_dir=base_dir,
        )
    )

    # 5. Inmobiliaria Bermúdez (Refuerzo Pamplona con Crawl-delay: 10s)
    results.append(
        scrape_bermudez(
            capture_date=day_str,
            base_dir=base_dir,
        )
    )

    total_pages = sum(r.paginas_descargadas for r in results)
    total_listings = sum(r.avisos_detectados for r in results)
    total_errors = sum(len(r.errores) for r in results)

    logger.info(
        "=== Recolección finalizada (%s): %d páginas descargadas | %d avisos detectados | %d errores ===",
        day_str,
        total_pages,
        total_listings,
        total_errors,
    )
    return results


__all__ = [
    "ScrapeResult",
    "run_all_scrapers",
    "scrape_bermudez",
    "scrape_casaclick",
    "scrape_fincaraiz",
    "scrape_inmobiliariapamplona",
    "scrape_rentabien",
]
