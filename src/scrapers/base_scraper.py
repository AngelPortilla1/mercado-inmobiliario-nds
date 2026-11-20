"""
Esqueleto base para scrapers éticos del mercado inmobiliario en Norte de Santander.
Cumple con la Sección 2 y Semana 2 del plan de proyecto:
- Rate limiting de 3 a 6 segundos entre peticiones.
- User-Agent identificable con correo de contacto.
- Almacenamiento obligatorio del crudo (HTML o JSON) en data/raw/<fuente>/<AAAA-MM-DD>/.
- Registro detallado (logging) de páginas, avisos y errores.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Proyecto-portafolio-datos-NDS/1.0 "
        "(Estudio academico mercado inmobiliario Norte de Santander; "
        "contacto: tu_correo@ejemplo.com)"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
}

MUNICIPIOS_OBJETIVO = (
    "pamplona",
    "cucuta",
    "los-patios",
    "villa-del-rosario",
)


def fetch(
    url: str,
    session: Optional[requests.Session] = None,
    min_delay: float = 3.0,
    max_delay: float = 6.0,
    timeout: int = 30,
) -> str:
    """
    Descarga el contenido de una URL aplicando pausa ética de 3 a 6 segundos.
    """
    client = session or requests
    logger.info("Descargando URL: %s", url)
    response = client.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()

    delay = random.uniform(min_delay, max_delay)
    logger.debug("Pausa ética con el servidor: %.2f segundos", delay)
    time.sleep(delay)
    return response.text


def save_raw(
    source: str,
    name: str,
    content: str,
    capture_date: Optional[str] = None,
    extension: str = "html",
    base_dir: Path = Path("data/raw"),
) -> Path:
    """
    Guarda el archivo crudo en data/raw/<fuente>/<AAAA-MM-DD>/<name>.<ext>.
    Permite re-parsear en el futuro si cambian las reglas de limpieza sin re-scrapear.
    """
    day_str = capture_date or date.today().isoformat()
    folder = base_dir / source.lower().strip() / day_str
    folder.mkdir(parents=True, exist_ok=True)

    ext = extension.lstrip(".")
    path = folder / f"{name}.{ext}"
    path.write_text(content, encoding="utf-8")
    logger.info("Crudo guardado en: %s (%d bytes)", path, len(content))
    return path
