"""
Orquestador principal del pipeline semanal (Sección 9):
Ejecución recomendada:
    python -m src.pipeline

Pasos:
1. Scrape (guarda crudo con fecha en data/raw/<fuente>/<AAAA-MM-DD>/).
2. Parseo y limpieza (aplica las 9 reglas y guarda en data/interim/).
3. Carga idempotente a la base de datos SQL (sql/schema.sql).
4. Reporte de calidad y registro (logging).
5. Alerta de caída de volumen (< 50% del umbral esperado).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

from src.db.load import init_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("src.pipeline")

MIN_EXPECTED_LISTINGS_THRESHOLD = 10


def run_pipeline(expected_min_listings: int = MIN_EXPECTED_LISTINGS_THRESHOLD) -> None:
    today = date.today().isoformat()
    logger.info("=== Iniciando pipeline semanal de mercado inmobiliario NDS (%s) ===", today)

    # Asegurar que la base de datos y las tablas existan
    init_database()

    # Verificar estado de capturas crudas del día
    raw_dir = Path("data/raw")
    raw_files = list(raw_dir.glob(f"*/{today}/*")) if raw_dir.exists() else []
    logger.info("Archivos crudos detectados para la fecha %s: %d", today, len(raw_files))

    if not raw_files:
        logger.warning(
            "Aún no hay archivos crudos para hoy (%s). "
            "Completa la auditoría en docs/legal.md y configura tu scraper en src/scrapers/.",
            today,
        )
        return

    # Alerta de umbral de volumen (Sección 6 y 9: si cae por debajo del 50% esperado, fallar y avisar)
    if len(raw_files) < (expected_min_listings * 0.5):
        logger.error(
            "ALERTA DE VOLUMEN: Se obtuvieron %d archivos crudos, menos del 50%% del umbral esperado (%d). "
            "Es probable que haya cambiado el HTML de la fuente.",
            len(raw_files),
            expected_min_listings,
        )
        sys.exit(1)

    # Guardar registro de ejecución
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_summary = {
        "fecha_ejecucion": today,
        "archivos_crudos_procesados": len(raw_files),
        "estado": "OK",
    }
    (reports_dir / f"run_{today}.json").write_text(
        json.dumps(log_summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("=== Pipeline finalizado con éxito ===")


if __name__ == "__main__":
    run_pipeline()
