"""
Parser para fichas HTML de detalle sanitizadas de Inmobiliaria Pamplona SAS
(`data/raw/inmobiliariapamplona/<AAAA-MM-DD>/detalle_*.html`).

Decisiones clave implementadas:
- Lee únicamente las fichas `detalle_*.html` (ignora `pamplona_index_*.html` para
  no duplicar avisos) usando `<link rel="canonical">` como `url` y su slug como ID.
- Aísla exclusivamente las etiquetas propias del inmueble en `.blog-post__tags a`
  (evitando las tarjetas de publicaciones relacionadas del pie de página).
- Regla conservadora de disponibilidad: si `.blog-post__tags` incluye `Arrendado`
  o `Vendido`, prevalece `estado_aviso = "inactivo"` incluso si también aparece `Disponible`.
- Deja `precio = None` cuando la ficha solo indica "Consultar valor de arriendo"
  (Regla 11 en `cleaner.py` contabilizará el descarte).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Sequence

from bs4 import BeautifulSoup

from src.cleaning.parsers.schema import RawListing

logger = logging.getLogger(__name__)

SOURCE_NAME = "inmobiliariapamplona"

TAG_PROPERTY_TYPES = (
    "apartaestudio",
    "apartamento",
    "casa",
    "consultorio",
    "local",
    "oficina",
    "bodega",
    "lote",
    "finca",
    "cabaña",
    "cabana",
)

TEXT_TIPO_PATTERNS = (
    ("apartaestudio", "apartaestudio"),
    ("apartamento", "apartamento"),
    ("consultorio", "consultorio"),
    ("locales", "local"),
    ("local", "local"),
    ("casa", "casa"),
    ("oficina", "oficina"),
    ("bodega", "bodega"),
    ("lote", "lote"),
    ("finca", "finca"),
)


def _extract_id_from_url_or_filename(url: Optional[str], fallback_stem: Optional[str]) -> Optional[str]:
    if url:
        slug = url.split("?")[0].rstrip("/").split("/")[-1].strip()
        if slug:
            return slug
    if fallback_stem:
        cleaned = re.sub(r"^detalle_\d+_", "", fallback_stem).strip()
        return cleaned or fallback_stem
    return None


def _extract_operacion(tags: Sequence[str], title: str, slug: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    if "venta" in tags_lower:
        return "venta"
    if "arriendo" in tags_lower:
        return "arriendo"

    combined = f"{title} {slug}".lower()
    if re.search(r"\b(vendo|venta)\b", combined):
        return "venta"
    if re.search(r"\b(arriendo|arrendado|alquiler)\b", combined):
        return "arriendo"
    return None


def _extract_tipo_inmueble(tags: Sequence[str], title: str, slug: str) -> Optional[str]:
    for tag in tags:
        low = tag.lower()
        if low in TAG_PROPERTY_TYPES:
            return tag

    combined = f"{title} {slug}".lower()
    for token, canonical in TEXT_TIPO_PATTERNS:
        if re.search(rf"\b{re.escape(token)}\b", combined):
            return canonical
    return None


def _extract_estado_aviso(tags: Sequence[str]) -> str:
    tags_lower = {t.lower() for t in tags}
    if tags_lower.intersection({"arrendado", "vendido", "alquilado"}):
        return "inactivo"
    return "activo"


def _extract_price(body_text: str) -> Optional[float]:
    """Busca un precio numérico en COP con signo `$` en el cuerpo de la ficha."""
    match = re.search(r"\$\s*([\d][\d\.,]{4,})", body_text)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(1))
    if not digits:
        return None
    val = float(digits)
    return val if val >= 50_000 else None


def _extract_area(text: str) -> Optional[float]:
    match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:m²|m2|mts2?|metros\s*cuadrados)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    num_str = match.group(1).replace(",", ".")
    try:
        val = float(num_str)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_positive_int_pattern(pattern: str, text: str) -> Optional[int]:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    val = int(match.group(1))
    return val if val > 0 else None


def _extract_barrio(body_text: str, title: str) -> Optional[str]:
    """
    Extrae una referencia limpia de ubicación/sector desde la sección UBICACIÓN
    o desde el título cuando incluye 'barrio', 'urb.', 'conjunto' o 'condominio'.
    """
    m_title = re.search(
        r"(?:barrio|urb\.?|urbanizaci[oó]n|conjunto|condominio)\s+([a-záéíóúñ0-9\s\.]+?)(?:\s*[-–|]|$)",
        title,
        flags=re.IGNORECASE,
    )
    if m_title:
        candidate = re.sub(r"\s+", " ", m_title.group(1)).strip(" .,-")
        if candidate:
            return candidate

    m_ub = re.search(
        r"UBICACI[ÓO]N\s*[:\|]+\s*([^\n🏠🏪✅💰🔵📞]+)",
        body_text,
        flags=re.IGNORECASE,
    )
    if m_ub:
        raw_ub = m_ub.group(1)
        raw_ub = re.split(r"\bCARACTER[IÍ]STICAS\b", raw_ub, maxsplit=1, flags=re.IGNORECASE)[0]
        raw_ub = re.sub(r"(?i)ubica[c]i[oó]n\s*:", "", raw_ub)
        raw_ub = re.sub(r"[📍|]+", " ", raw_ub)
        raw_ub = re.sub(r"\s+", " ", raw_ub).strip(" .,-:")
        if raw_ub:
            return raw_ub[:80]
    return None


def parse_inmopamplona_detail_html(
    html: str,
    capture_date: str,
    fallback_stem: Optional[str] = None,
) -> Optional[RawListing]:
    """Parsea el HTML de una ficha individual `detalle_*.html` a `RawListing`."""
    soup = BeautifulSoup(html, "lxml")

    canonical = soup.find("link", rel="canonical")
    url: Optional[str] = None
    if canonical and canonical.get("href"):
        url = str(canonical["href"]).split("?")[0].strip()

    raw_id = _extract_id_from_url_or_filename(url, fallback_stem)
    if not raw_id:
        return None

    tags = [
        a.get_text(" ", strip=True)
        for a in soup.select(".blog-post__tags a")
        if a.get_text(strip=True)
    ]

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""

    body = soup.select_one(".blog-post__body") or soup.select_one("article") or soup.body
    body_text = body.get_text(" | ", strip=True) if body else ""
    combined_text = f"{title} | {body_text}"

    habitaciones = _extract_positive_int_pattern(
        r"\b(\d+)\s*(?:habitaci[oó]n(?:es)?|alcobas?)\b", body_text
    ) or _extract_positive_int_pattern(
        r"\b(\d+)\s*(?:habitaci[oó]n(?:es)?|alcobas?)\b", title
    )
    banos = _extract_positive_int_pattern(r"\b(\d+)\s*ba[ñn]os?\b", body_text)

    estrato_raw = _extract_positive_int_pattern(r"estrato\s*[:\-]?\s*(\d)\b", body_text)
    estrato = estrato_raw if (estrato_raw is not None and 1 <= estrato_raw <= 6) else None

    return RawListing(
        id_aviso_fuente=raw_id,
        fuente=SOURCE_NAME,
        fecha_captura=capture_date,
        url=url,
        operacion=_extract_operacion(tags, title, raw_id),
        tipo_inmueble=_extract_tipo_inmueble(tags, title, raw_id),
        municipio="pamplona",
        barrio=_extract_barrio(body_text, title),
        precio=_extract_price(body_text),
        administracion=None,
        area_m2=_extract_area(combined_text),
        habitaciones=habitaciones,
        banos=banos,
        parqueaderos=None,
        estrato=estrato,
        antiguedad=None,
        estado_aviso=_extract_estado_aviso(tags),
        municipio_consulta="pamplona",
    )


def parse_inmopamplona_dir(source_date_dir: Path, capture_date: str) -> List[RawListing]:
    """
    Parsea únicamente las fichas de detalle `detalle_*.html` en
    `data/raw/inmobiliariapamplona/<fecha>/` (omite páginas índice para evitar duplicados).
    """
    records: List[RawListing] = []
    for html_path in sorted(source_date_dir.glob("detalle_*.html")):
        html = html_path.read_text(encoding="utf-8")
        parsed = parse_inmopamplona_detail_html(
            html=html,
            capture_date=capture_date,
            fallback_stem=html_path.stem,
        )
        if parsed is not None:
            records.append(parsed)
    return records
