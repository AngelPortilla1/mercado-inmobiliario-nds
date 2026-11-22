"""
Orquestador principal del pipeline semanal (Sección 9 y Semana 2):
Ejecución recomendada:
    uv run python -m src.pipeline
    uv run python -m src.pipeline --scrape

Pasos:
1. Scrape de las 5 fuentes aprobadas en docs/legal.md (guarda crudo en data/raw/<fuente>/<AAAA-MM-DD>/).
2. Verificación de archivos crudos y alerta de caída de volumen (< 50% del umbral esperado).
3. Inicialización de la base de datos SQL (sql/schema.sql).
4. Reporte de calidad y bitácora de captura en reports/run_<AAAA-MM-DD>.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.db.load import init_database
from src.scrapers import ScrapeResult, run_all_scrapers
from src.scrapers.base_scraper import configure_scraper_logging

logger = logging.getLogger("src.pipeline")

MIN_EXPECTED_LISTINGS_THRESHOLD = 100


def run_pipeline(
    expected_min_listings: int = MIN_EXPECTED_LISTINGS_THRESHOLD,
    force_scrape: bool = False,
    capture_date: Optional[str] = None,
    max_pages_fincaraiz: int = 5,
    max_pages_rentabien: int = 5,
) -> Dict[str, Any]:
    today = capture_date or date.today().isoformat()
    log_path = configure_scraper_logging(capture_date=today)
    logger.info("=== Iniciando pipeline semanal de mercado inmobiliario NDS (%s) ===", today)

    # Asegurar que la base de datos y las tablas existan
    init_database()

    raw_dir = Path("data/raw")
    existing_raw_files = list(raw_dir.glob(f"*/{today}/*")) if raw_dir.exists() else []

    scrape_results: List[ScrapeResult] = []
    if force_scrape or not existing_raw_files:
        logger.info("Ejecutando scrapers para la fecha %s...", today)
        scrape_results = run_all_scrapers(
            capture_date=today,
            base_dir=raw_dir,
            max_pages_fincaraiz=max_pages_fincaraiz,
            max_pages_rentabien=max_pages_rentabien,
        )

    raw_files = list(raw_dir.glob(f"*/{today}/*")) if raw_dir.exists() else []
    logger.info("Archivos crudos disponibles para la fecha %s: %d", today, len(raw_files))

    if not raw_files:
        logger.error("No se encontraron ni generaron archivos crudos para %s.", today)
        sys.exit(1)

    total_avisos_detectados = sum(r.avisos_detectados for r in scrape_results)
    total_paginas = sum(r.paginas_descargadas for r in scrape_results)
    total_errores = sum(len(r.errores) for r in scrape_results)

    # Si no se corrió el scraper en esta invocación pero ya había archivos crudos en disco,
    # leer el resumen previo o contabilizar archivos
    if not scrape_results:
        prev_report = Path("reports") / f"run_{today}.json"
        if prev_report.exists():
            try:
                prev_data = json.loads(prev_report.read_text(encoding="utf-8"))
                total_avisos_detectados = int(prev_data.get("total_avisos_detectados", len(raw_files)))
                total_paginas = int(prev_data.get("total_paginas_descargadas", len(raw_files)))
            except Exception:
                total_avisos_detectados = len(raw_files)
        else:
            total_avisos_detectados = len(raw_files)

    # Alerta de umbral de volumen (Sección 6 y 9: si cae por debajo del 50% esperado, fallar y avisar)
    if total_avisos_detectados < (expected_min_listings * 0.5):
        logger.error(
            "ALERTA DE VOLUMEN: Se detectaron %d avisos, menos del 50%% del umbral esperado (%d). "
            "Es probable que haya cambiado el HTML o API de alguna fuente.",
            total_avisos_detectados,
            expected_min_listings,
        )
        sys.exit(1)

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_summary: Dict[str, Any] = {
        "fecha_ejecucion": today,
        "archivo_log": str(log_path),
        "archivos_crudos_guardados": len(raw_files),
        "total_paginas_descargadas": total_paginas,
        "total_avisos_detectados": total_avisos_detectados,
        "total_errores_controlados": total_errores,
        "fuentes": [r.to_dict() for r in scrape_results] if scrape_results else "archivos_existentes_en_disco",
        "estado": "OK",
    }
    report_path = reports_dir / f"run_{today}.json"
    report_path.write_text(
        json.dumps(log_summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Reporte de ejecución guardado en: %s", report_path)
    logger.info("=== Pipeline finalizado con éxito ===")
    return log_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestador semanal del proyecto Mercado Inmobiliario NDS."
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Forzar ejecución de los 5 scrapers incluso si ya existen archivos crudos hoy.",
    )
    parser.add_argument(
        "--max-pages-fincaraiz",
        type=int,
        default=5,
        help="Máximo de páginas por (municipio, operación) en Fincaraíz (default: 5).",
    )
    parser.add_argument(
        "--max-pages-rentabien",
        type=int,
        default=5,
        help="Máximo de páginas por (municipio, operación) en Rentabien (default: 5).",
    )
    args = parser.parse_args()
    run_pipeline(
        force_scrape=args.scrape,
        max_pages_fincaraiz=args.max_pages_fincaraiz,
        max_pages_rentabien=args.max_pages_rentabien,
    )


if __name__ == "__main__":
    main()
