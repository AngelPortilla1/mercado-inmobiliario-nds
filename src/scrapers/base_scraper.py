"""
Esqueleto base para scrapers éticos del mercado inmobiliario en Norte de Santander.
Cumple con la Sección 2 y Semana 2 del plan de proyecto:
- Rate limiting de 3 a 6 segundos entre peticiones (y >= 10s para Bermúdez).
- User-Agent identificable del proyecto académico/portafolio.
- Cero Datos Personales (PII): sanitización preventiva de imágenes, teléfonos, correos y nombres.
- Almacenamiento obligatorio del crudo (HTML o JSON) en data/raw/<fuente>/<AAAA-MM-DD>/.
- Registro detallado (logging) de páginas descargadas, avisos detectados y errores controlados.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def create_ethical_session(max_retries: int = 3) -> requests.Session:
    """
    Crea una sesión HTTP con reintentos automáticos ante desconexiones transitorias
    del servidor remoto (RemoteDisconnected, 429, 500, 502, 503, 504).
    """
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        backoff_factor=2.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

HEADERS = {
    "User-Agent": (
        "Proyecto-portafolio-datos-NDS/1.0 "
        "(Estudio academico mercado inmobiliario Norte de Santander; "
        "https://github.com/AngelPortilla1/mercado-inmobiliario-nds)"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
}

MUNICIPIOS_OBJETIVO = (
    "pamplona",
    "cucuta",
    "los-patios",
    "villa-del-rosario",
)

DANE_MUNICIPIOS_OBJETIVO: Dict[str, str] = {
    "pamplona": "54518",
    "cucuta": "54001",
    "los-patios": "54405",
    "villa-del-rosario": "54874",
}


@dataclass
class ScrapeResult:
    """Resumen estructurado de la ejecución de un scraper."""

    fuente: str
    fecha_captura: str
    paginas_descargadas: int = 0
    avisos_detectados: int = 0
    archivos_crudos: List[str] = field(default_factory=list)
    desglose: Dict[str, int] = field(default_factory=dict)
    errores: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def configure_scraper_logging(
    capture_date: Optional[str] = None,
    log_dir: Path = Path("reports"),
) -> Path:
    """
    Configura logging detallado en consola y archivo reports/scraper_<AAAA-MM-DD>.log.
    """
    day_str = capture_date or date.today().isoformat()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"scraper_{day_str}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    has_file_handler = any(
        isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == log_path.resolve()
        for h in root_logger.handlers
    )
    if not has_file_handler:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        root_logger.addHandler(fh)

    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_logger.handlers
    )
    if not has_stream_handler:
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        root_logger.addHandler(sh)

    return log_path


def fetch(
    url: str,
    session: Optional[requests.Session] = None,
    min_delay: float = 3.0,
    max_delay: float = 6.0,
    timeout: int = 30,
) -> str:
    """
    Descarga el contenido HTML/texto de una URL aplicando pausa ética aleatoria.
    """
    client = session or requests
    logger.info("Descargando URL (GET): %s", url)
    response = client.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()

    delay = random.uniform(min_delay, max_delay)
    logger.debug("Pausa ética con el servidor: %.2f segundos", delay)
    time.sleep(delay)
    return response.text


def post_json(
    url: str,
    payload: Dict[str, Any],
    session: Optional[requests.Session] = None,
    min_delay: float = 3.0,
    max_delay: float = 6.0,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Envía una petición POST con JSON aplicando la misma pausa ética de 3 a 6 segundos.
    """
    client = session or requests
    headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.info("Consultando endpoint (POST): %s | params=%s", url, payload.get("params"))
    response = client.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()

    delay = random.uniform(min_delay, max_delay)
    logger.debug("Pausa ética con el servidor: %.2f segundos", delay)
    time.sleep(delay)
    return response.json()


def strip_html_pii(html: str, extra_selectors: Optional[List[str]] = None) -> str:
    """
    Elimina fotografías (<img>, <picture>), enlaces de teléfonos/WhatsApp/correos
    y selectores de agentes/propietarios antes de guardar el HTML crudo en disco.
    Cumple estrictamente la Regla 1 (Cero Datos Personales - PII).
    """
    soup = BeautifulSoup(html, "lxml")

    # Eliminar etiquetas de imágenes y multimedia
    for tag in soup.find_all(["img", "picture", "source", "video", "iframe"]):
        tag.decompose()

    # Eliminar enlaces a teléfonos, correos o WhatsApp
    for a_tag in soup.find_all("a", href=True):
        href_lower = a_tag["href"].lower()
        if any(
            token in href_lower
            for token in ("tel:", "mailto:", "wa.me", "whatsapp.com", "api.whatsapp")
        ):
            a_tag.decompose()

    # Eliminar selectores específicos de anunciantes/agentes
    if extra_selectors:
        for sel in extra_selectors:
            for match in soup.select(sel):
                match.decompose()

    sanitized = str(soup)
    # Enmascarar posibles correos electrónicos o celulares colombianos sueltos en texto libre
    sanitized = re.sub(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "[EMAIL_REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?:\+?57\s*)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}",
        "[PHONE_REDACTED]",
        sanitized,
    )
    return sanitized


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
