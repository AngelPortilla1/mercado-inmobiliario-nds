"""
Parser para archivos HTML crudos sanitizados de Casa Click
(`data/raw/casaclick/<AAAA-MM-DD>/*.html`) — Refuerzo local Pamplona.

Decisiones clave implementadas:
- Separa estrictamente `.property_area_type1` (barrio/sector, incluyendo el barrio
  "El Zulia" de Pamplona) de `.property_city_type1` (municipio = Pamplona).
- Detecta avisos cerrados (`estado_aviso = "inactivo"`) cuando un `.ribbon-inside`
  o el título incluye `Vendido` / `Arrendado`.
- Resuelve `operacion` desde `a[href*="/tipos/"]`, con respaldo en `.ribbon-inside`
  y el título (porque las tarjetas `Vendido` omiten el enlace `/tipos/venta/`).
- Extrae `area_m2` antes de `m<sup>2</sup>` para no concatenar el exponente `2`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from src.cleaning.parsers.schema import RawListing

logger = logging.getLogger(__name__)

SOURCE_NAME = "casaclick"

CONDITION_RIBBONS = ("nuevo", "usado", "en construcción", "en construccion")


def _parse_cop_price(raw_text: Optional[str]) -> Optional[float]:
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
    if not raw_text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|mts)", raw_text, flags=re.IGNORECASE)
    if not match:
        return None
    num_str = match.group(1).replace(",", ".")
    try:
        val = float(num_str)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_barrio(card: Tag) -> Optional[str]:
    """
    Extrae el barrio desde `.property_area_type1`. Si contiene varios enlaces
    (ej. 'Pamplona norte de santander, Los Nazarenos'), prioriza el nombre de barrio
    específico en lugar del texto genérico de la ciudad.
    """
    area_el = card.select_one(".property_area_type1")
    if not area_el:
        return None

    links = [a.get_text(" ", strip=True) for a in area_el.find_all("a") if a.get_text(strip=True)]
    if links:
        specific = [
            lbl for lbl in links
            if "norte de santander" not in lbl.lower() and lbl.lower() != "pamplona"
        ]
        if specific:
            return specific[-1]
        return links[-1]

    raw = area_el.get_text(" ", strip=True)
    return raw or None


def _extract_municipio(card: Tag) -> str:
    city_el = card.select_one(".property_city_type1")
    if city_el:
        city = city_el.get_text(" ", strip=True)
        if city:
            return city
    return "pamplona"


def _extract_operacion(card: Tag, ribbons: List[str], title: Optional[str]) -> Optional[str]:
    for a_tag in card.select(".property_categories_type1_wrapper a"):
        href = (a_tag.get("href") or "").lower()
        if "/tipos/" in href:
            txt = a_tag.get_text(" ", strip=True).lower()
            if "venta" in txt:
                return "venta"
            if "arriendo" in txt or "alquiler" in txt:
                return "arriendo"

    for r in ribbons:
        low = r.lower()
        if low == "venta":
            return "venta"
        if low in ("arriendo", "alquiler"):
            return "arriendo"

    title_low = (title or "").lower()
    if re.search(r"\b(venta|vendo|vendido)\b", title_low):
        return "venta"
    if re.search(r"\b(arriendo|arrendado|alquiler)\b", title_low):
        return "arriendo"

    return None


def _extract_tipo_inmueble(card: Tag, ribbons: List[str], title: Optional[str]) -> Optional[str]:
    for a_tag in card.select(".property_categories_type1_wrapper a"):
        href = (a_tag.get("href") or "").lower()
        if "/listados/" in href:
            txt = a_tag.get_text(" ", strip=True)
            if txt:
                return txt

    for r in ribbons:
        if r.lower() in ("lote", "casa", "apartamento", "local", "apartaestudio", "duplex"):
            return r

    title_low = (title or "").lower()
    for token in ("apartaestudio", "apartamento", "duplex", "casa", "lote", "local"):
        if token in title_low:
            return token
    return None


def _extract_antiguedad(ribbons: List[str]) -> Optional[str]:
    matched = [r for r in ribbons if r.lower() in CONDITION_RIBBONS]
    if not matched:
        return None
    # Mantener orden único (ej. ["En construcción", "Nuevo"])
    unique: List[str] = []
    for item in matched:
        if item not in unique:
            unique.append(item)
    return " / ".join(unique)


def parse_casaclick_card(card: Tag, capture_date: str) -> Optional[RawListing]:
    """Convierte una tarjeta `.property_listing` de Casa Click en `RawListing`."""
    title_link = card.select_one("h4 a")
    title = title_link.get_text(" ", strip=True) if title_link else None
    url = (card.get("data-link") or (title_link.get("href") if title_link else None) or "").strip() or None

    id_el = card.select_one(".property_details_type1_id .property_details_type1_value")
    raw_id = id_el.get_text(" ", strip=True) if id_el else None
    if not raw_id:
        fav = card.select_one("span.icon-fav[data-postid]")
        raw_id = fav.get("data-postid") if fav else None
    if not raw_id:
        comp = card.select_one("span.compare-action[data-pid]")
        raw_id = comp.get("data-pid") if comp else None
    if not raw_id and url:
        raw_id = url.rstrip("/").split("/")[-1]
    if not raw_id:
        return None

    ribbons = [
        el.get_text(" ", strip=True)
        for el in card.select(".ribbon-inside, .action_tag_wrapper")
        if el.get_text(strip=True)
    ]

    price_el = card.select_one(".listing_unit_price_wrapper")
    precio = _parse_cop_price(price_el.get_text(" ", strip=True)) if price_el else None

    rooms_el = card.select_one(".property_details_type1_rooms .property_details_type1_value")
    habitaciones = _parse_positive_int(rooms_el.get_text(" ", strip=True)) if rooms_el else None

    baths_el = card.select_one(".property_details_type1_baths .property_details_type1_value")
    banos = _parse_positive_int(baths_el.get_text(" ", strip=True)) if baths_el else None

    size_el = card.select_one(".property_details_type1_size")
    area_m2 = _parse_area(size_el.get_text(" ", strip=True)) if size_el else None

    is_inactive = any(
        token in text.lower()
        for text in (*ribbons, title or "")
        for token in ("vendido", "arrendado", "alquilado")
    )
    estado_aviso = "inactivo" if is_inactive else "activo"

    return RawListing(
        id_aviso_fuente=str(raw_id).strip(),
        fuente=SOURCE_NAME,
        fecha_captura=capture_date,
        url=url,
        operacion=_extract_operacion(card, ribbons, title),
        tipo_inmueble=_extract_tipo_inmueble(card, ribbons, title),
        municipio=_extract_municipio(card),
        barrio=_extract_barrio(card),
        precio=precio,
        administracion=None,
        area_m2=area_m2,
        habitaciones=habitaciones,
        banos=banos,
        parqueaderos=None,
        estrato=None,
        antiguedad=_extract_antiguedad(ribbons),
        estado_aviso=estado_aviso,
        municipio_consulta="pamplona",
    )


def parse_casaclick_html(html: str, capture_date: str) -> List[RawListing]:
    """Parsea una página HTML de listado de Casa Click."""
    soup = BeautifulSoup(html, "lxml")
    listings: List[RawListing] = []
    for card in soup.select(".property_listing"):
        parsed = parse_casaclick_card(card, capture_date=capture_date)
        if parsed is not None:
            listings.append(parsed)
    return listings


def parse_casaclick_dir(source_date_dir: Path, capture_date: str) -> List[RawListing]:
    """Parsea todos los HTML crudos de Casa Click en `data/raw/casaclick/<fecha>/`."""
    records: List[RawListing] = []
    for html_path in sorted(source_date_dir.glob("*.html")):
        html = html_path.read_text(encoding="utf-8")
        records.extend(parse_casaclick_html(html, capture_date=capture_date))
    return records
