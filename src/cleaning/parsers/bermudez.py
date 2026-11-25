"""
Parser para archivos HTML crudos sanitizados de Inmobiliaria Bermúdez
(`data/raw/bermudez/<AAAA-MM-DD>/*.html`) — Refuerzo local Pamplona.

Decisiones clave implementadas:
- Lee exclusivamente las tarjetas principales `.view-id-arrienda .item.span9`
  (excluyendo el bloque lateral `.view-id-apartments`).
- Si el campo `Tipo:` viene vacío (ej. "ESPACIOSA CASA EN VENTA" en `pamplona_venta_p03.html`),
  infiere `tipo_inmueble` desde el slug de la URL (`/property/<tipo>/...`) o el título `h2.title`.
- Extrae la cuota de administración cuando se especifica en `.cbody`
  (ej. "SE CANCELA CUOTA DE ADMINISTRACIÓN $80.000").
- Extrae `area_m2` aislando el número antes de `m²` (`<sup>2</sup>`) para evitar concatenar el "2".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from src.cleaning.parsers.schema import RawListing

logger = logging.getLogger(__name__)

SOURCE_NAME = "bermudez"
BASE_URL = "https://www.inmobiliariabermudez.com"

# Palabras clave ordenadas de más específica a más general para inferir tipo si `Tipo:` viene vacío
TIPO_FALLBACK_PATTERNS = (
    ("apartaestudio", "apartaestudio"),
    ("apta-estudio", "apartaestudio"),
    ("apartamento", "apartamento"),
    ("apto", "apartamento"),
    ("casa campestre", "casa campestre"),
    ("casa lote", "casa lote"),
    ("cabaña", "cabaña"),
    ("cabana", "cabaña"),
    ("casa", "casa"),
    ("consultorio", "consultorio"),
    ("oficina", "oficina"),
    ("bodega", "bodega"),
    ("local", "local"),
    ("lote", "lote"),
    ("finca", "finca"),
)


def _parse_cop_amount(raw_text: Optional[str]) -> Optional[float]:
    if not raw_text:
        return None
    digits = re.sub(r"[^\d]", "", raw_text)
    if not digits:
        return None
    val = float(digits)
    return val if val > 0 else None


def _parse_positive_int(raw_text: Optional[str]) -> Optional[int]:
    if not raw_text:
        return None
    match = re.search(r"\d+", raw_text)
    if not match:
        return None
    val = int(match.group(0))
    return val if val > 0 else None


def _parse_area(raw_text: Optional[str]) -> Optional[float]:
    """Extrae el área antes de `m` / `m²` evitando absorber el exponente `2` de `<sup>2</sup>`."""
    if not raw_text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|mts)", raw_text, flags=re.IGNORECASE)
    if not match:
        return None
    num_str = match.group(1)
    if "," in num_str and "." in num_str:
        num_str = num_str.replace(".", "").replace(",", ".")
    elif "," in num_str:
        num_str = num_str.replace(",", ".")
    elif re.match(r"^\d{1,3}\.\d{3}$", num_str):
        num_str = num_str.replace(".", "")
    try:
        val = float(num_str)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_admin_from_description(description: Optional[str]) -> Optional[float]:
    """Extrae la cuota de administración si aparece explícita en la descripción `.cbody`."""
    if not description:
        return None
    match = re.search(
        r"administraci[oó]n[^$\d]{0,25}\$\s*([\d][\d\.\s,]*)",
        description,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    amount = _parse_cop_amount(match.group(1))
    # Evitar falsos positivos de dígitos sueltos menores a $5.000 COP
    if amount is not None and amount >= 5_000:
        return amount
    return None


def _extract_labeled_fields(card: Tag) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for div in card.select(".span5 > .content"):
        label_el = div.select_one(".label")
        if not label_el:
            continue
        label_raw = label_el.get_text(" ", strip=True)
        key = label_raw.rstrip(":").strip().lower()
        full_text = div.get_text(" ", strip=True)
        val = full_text[len(label_raw):].strip() if full_text.startswith(label_raw) else full_text.replace(label_raw, "", 1).strip()
        fields[key] = val
    return fields


def _infer_tipo_fallback(url_path: Optional[str], title: Optional[str]) -> Optional[str]:
    """Rescata `tipo_inmueble` desde `/property/<tipo>/...` o `h2.title` si `Tipo:` viene vacío."""
    candidates: List[str] = []
    if url_path:
        m = re.search(r"/property/([^/]+)/", url_path.lower())
        if m:
            candidates.append(m.group(1).replace("-", " "))
    if title:
        candidates.append(title.lower())

    for text in candidates:
        for token, canonical in TIPO_FALLBACK_PATTERNS:
            if re.search(rf"\b{re.escape(token)}\b", text):
                return canonical
    return None


def _build_full_url(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    cleaned = href.strip()
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return f"{BASE_URL}{cleaned}"


def _infer_operacion_from_filename(filename: str) -> Optional[str]:
    low = filename.lower()
    if "arriendo" in low or "arrienda" in low:
        return "arriendo"
    if "venta" in low or "vende" in low:
        return "venta"
    return None


def parse_bermudez_card(
    card: Tag,
    capture_date: str,
    operacion: Optional[str] = None,
) -> Optional[RawListing]:
    """Convierte una tarjeta `.item.span9` de Bermúdez en `RawListing`."""
    title_link = card.select_one("h2.title a")
    title_text = title_link.get_text(" ", strip=True) if title_link else None
    href = title_link.get("href") if title_link else None
    url = _build_full_url(href)

    codigo_el = card.select_one(".codigo")
    raw_id: Optional[str] = None
    if codigo_el:
        raw_id = re.sub(r"(?i)^c[oó]digo\s*:\s*", "", codigo_el.get_text(" ", strip=True)).strip()
    if not raw_id and href:
        raw_id = href.rstrip("/").split("/")[-1]
    if not raw_id:
        return None

    barrio_el = card.select_one(".barrio")
    barrio = barrio_el.get_text(" ", strip=True) if barrio_el else None
    barrio = barrio or None

    price_el = card.select_one(".price")
    precio = _parse_cop_amount(price_el.get_text(" ", strip=True)) if price_el else None

    fields = _extract_labeled_fields(card)
    tipo_inmueble = fields.get("tipo") or _infer_tipo_fallback(href, title_text)

    estrato_val = _parse_positive_int(fields.get("estrato"))
    estrato = estrato_val if (estrato_val is not None and 1 <= estrato_val <= 6) else None

    cbody_el = card.select_one(".cbody")
    description = cbody_el.get_text(" ", strip=True) if cbody_el else None
    administracion = _extract_admin_from_description(description)

    area_el = card.select_one(".area")
    area_m2 = _parse_area(area_el.get_text(" ", strip=True)) if area_el else None

    baths_el = card.select_one(".bathrooms")
    banos = _parse_positive_int(baths_el.get_text(" ", strip=True)) if baths_el else None

    beds_el = card.select_one(".bedrooms")
    habitaciones = _parse_positive_int(beds_el.get_text(" ", strip=True)) if beds_el else None

    title_lower = (title_text or "").lower()
    estado_aviso = "inactivo" if re.search(r"\b(vendido|arrendado|alquilado)\b", title_lower) else "activo"

    return RawListing(
        id_aviso_fuente=raw_id,
        fuente=SOURCE_NAME,
        fecha_captura=capture_date,
        url=url,
        operacion=operacion,
        tipo_inmueble=tipo_inmueble,
        municipio="pamplona",
        barrio=barrio,
        precio=precio,
        administracion=administracion,
        area_m2=area_m2,
        habitaciones=habitaciones,
        banos=banos,
        parqueaderos=None,
        estrato=estrato,
        antiguedad=None,
        estado_aviso=estado_aviso,
        municipio_consulta="pamplona",
    )


def parse_bermudez_html(
    html: str,
    capture_date: str,
    operacion: Optional[str] = None,
) -> List[RawListing]:
    """Parsea el HTML de una página de listado de Inmobiliaria Bermúdez."""
    soup = BeautifulSoup(html, "lxml")
    listings: List[RawListing] = []
    for card in soup.select(".view-id-arrienda .item.span9"):
        parsed = parse_bermudez_card(card, capture_date=capture_date, operacion=operacion)
        if parsed is not None:
            listings.append(parsed)
    return listings


def parse_bermudez_dir(source_date_dir: Path, capture_date: str) -> List[RawListing]:
    """Parsea todos los HTML crudos de Bermúdez en `data/raw/bermudez/<fecha>/`."""
    records: List[RawListing] = []
    for html_path in sorted(source_date_dir.glob("*.html")):
        op = _infer_operacion_from_filename(html_path.name)
        html = html_path.read_text(encoding="utf-8")
        records.extend(parse_bermudez_html(html, capture_date=capture_date, operacion=op))
    return records
