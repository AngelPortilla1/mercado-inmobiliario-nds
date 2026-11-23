"""
Parser para archivos JSON crudos sanitizados de Fincaraíz
(`data/raw/fincaraiz/<AAAA-MM-DD>/*.json`).

Proyecta cada aviso hacia el contrato estándar `RawListing` (16 campos de captura
+ 2 campos de auditoría) sin aplicar filtros de negocio (los cuales viven en
`src/cleaning/cleaner.py`).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.cleaning.parsers.schema import RawListing

logger = logging.getLogger(__name__)

SOURCE_NAME = "fincaraiz"
BASE_URL = "https://www.fincaraiz.com.co"

# Respaldo de códigos internos de antigüedad en Fincaraíz si falta en technicalSheet
ANTIQUITY_CODE_MAP: Dict[str, str] = {
    "1": "menor a 1 año",
    "2": "1 a 8 años",
    "3": "9 a 15 años",
    "4": "16 a 30 años",
    "5": "más de 30 años",
}

# Slugs de municipios de Norte de Santander presentes en las URLs de Fincaraíz
URL_MUNICIPIO_SLUGS: Dict[str, str] = {
    "villa-del-rosario": "villa del rosario",
    "los-patios": "los patios",
    "san-jose-de-cucuta": "cucuta",
    "san-cayetano": "san cayetano",
    "el-zulia": "el zulia",
    "pamplona": "pamplona",
    "cucuta": "cucuta",
    "ocana": "ocana",
}


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
        return num if num > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_positive_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = int(float(value))
        return num if num > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_non_negative_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = int(float(value))
        return num if num >= 0 else None
    except (TypeError, ValueError):
        return None


def _extract_municipio_from_link(link: Optional[str]) -> Optional[str]:
    """
    Extrae el municipio real desde el slug de la URL de Fincaraíz
    (ej. '/apartamento-en-venta-en-la-rinconada-los-patios/194463484' -> 'los patios').
    Prioriza slugs más largos primero para evitar coincidencias parciales.
    """
    if not link:
        return None
    path_lower = link.strip().lower()
    for slug, nombre in URL_MUNICIPIO_SLUGS.items():
        if re.search(rf"(?:-|/)({re.escape(slug)})(?:/|$)", path_lower):
            return nombre
    return None


def _extract_municipio(item: Dict[str, Any], link: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """
    Resuelve el municipio real del aviso (Regla 4):
    1. Slug explícito de la URL (`link`) — resuelve ambigüedades de frontera metropolitana.
    2. Primera ciudad en `locations.city`.
    3. Respaldo: `municipio_consulta`.
    """
    from_link = _extract_municipio_from_link(link)
    if from_link:
        return from_link

    locations = item.get("locations") or {}
    if isinstance(locations, dict):
        cities = locations.get("city") or []
        if isinstance(cities, list) and cities:
            first_city = cities[0]
            if isinstance(first_city, dict) and first_city.get("name"):
                return str(first_city["name"]).strip()

    return fallback


def _extract_barrio(item: Dict[str, Any]) -> Optional[str]:
    """Extrae el nombre del barrio desde `locations.neighbourhood` o `location_main`."""
    locations = item.get("locations") or {}
    if not isinstance(locations, dict):
        return None

    neighbourhoods = locations.get("neighbourhood") or []
    if isinstance(neighbourhoods, list) and neighbourhoods:
        first = neighbourhoods[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"]).strip()

    loc_main = locations.get("location_main") or {}
    if isinstance(loc_main, dict):
        loc_type = str(loc_main.get("location_type") or "").lower()
        if "neighbourhood" in loc_type and loc_main.get("name"):
            return str(loc_main["name"]).strip()

    return None


def _extract_technical_sheet_map(item: Dict[str, Any]) -> Dict[str, Any]:
    sheet = item.get("technicalSheet") or []
    if not isinstance(sheet, list):
        return {}
    result: Dict[str, Any] = {}
    for entry in sheet:
        if isinstance(entry, dict) and entry.get("field"):
            result[str(entry["field"])] = entry.get("value")
    return result


def _extract_estrato(item: Dict[str, Any]) -> Optional[int]:
    """Acepta únicamente estratos residenciales colombianos válidos (1 a 6)."""
    raw = item.get("stratum")
    val = _safe_positive_int(raw)
    if val is not None and 1 <= val <= 6:
        return val
    return None


def _extract_antiguedad(item: Dict[str, Any], tech_sheet: Dict[str, Any]) -> Optional[str]:
    ts_val = tech_sheet.get("antiquity")
    if isinstance(ts_val, str) and ts_val.strip():
        return ts_val.strip()

    code = item.get("antiquity")
    if code is not None:
        mapped = ANTIQUITY_CODE_MAP.get(str(code).strip())
        if mapped:
            return mapped
    return None


def _extract_area_m2(item: Dict[str, Any]) -> Optional[float]:
    for key in ("m2", "m2Built", "m2apto", "m2Terrain"):
        val = _safe_float(item.get(key))
        if val is not None:
            return val
    return None


def _build_full_url(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    cleaned = str(link).strip()
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return f"{BASE_URL}{cleaned}"


def parse_fincaraiz_item(
    item: Dict[str, Any],
    capture_date: str,
    municipio_consulta: Optional[str] = None,
    operacion_consulta: Optional[str] = None,
) -> Optional[RawListing]:
    """Convierte un aviso individual del JSON de Fincaraíz a `RawListing`."""
    raw_id = item.get("id") or item.get("idFincaLegacy") or item.get("code")
    if raw_id is None or not str(raw_id).strip():
        return None

    link = item.get("link")
    url = _build_full_url(link)

    op_field = item.get("operation_type")
    if isinstance(op_field, dict):
        operacion = op_field.get("name") or operacion_consulta
    else:
        operacion = op_field or operacion_consulta

    pt_field = item.get("property_type")
    if isinstance(pt_field, dict):
        tipo_inmueble = pt_field.get("name")
    else:
        tipo_inmueble = pt_field

    price_obj = item.get("price")
    if isinstance(price_obj, dict):
        precio = _safe_float(price_obj.get("amount"))
        hide_price = bool(price_obj.get("hidePrice") or item.get("hidePrice"))
    else:
        precio = _safe_float(price_obj)
        hide_price = bool(item.get("hidePrice"))
    if hide_price and precio is None:
        precio = None

    admin_obj = item.get("commonExpenses")
    if isinstance(admin_obj, dict):
        administracion = _safe_float(admin_obj.get("amount"))
    else:
        administracion = _safe_float(admin_obj)

    tech_sheet = _extract_technical_sheet_map(item)
    municipio = _extract_municipio(item, link=link, fallback=municipio_consulta)
    barrio = _extract_barrio(item)
    area_m2 = _extract_area_m2(item)

    # En vivienda de Fincaraíz las alcobas vienen en `bedrooms` (`rooms` suele ser 0 en aptos)
    habitaciones = _safe_positive_int(item.get("bedrooms"))
    banos = _safe_positive_int(item.get("bathrooms"))
    parqueaderos = _safe_non_negative_int(item.get("garage"))
    estrato = _extract_estrato(item)
    antiguedad = _extract_antiguedad(item, tech_sheet)

    is_inactive = (
        bool(item.get("sold"))
        or bool(item.get("deleted"))
        or (item.get("active") is False)
    )
    estado_aviso = "inactivo" if is_inactive else "activo"

    return RawListing(
        id_aviso_fuente=str(raw_id).strip(),
        fuente=SOURCE_NAME,
        fecha_captura=capture_date,
        url=url,
        operacion=str(operacion).strip() if operacion else None,
        tipo_inmueble=str(tipo_inmueble).strip() if tipo_inmueble else None,
        municipio=municipio,
        barrio=barrio,
        precio=precio,
        administracion=administracion,
        area_m2=area_m2,
        habitaciones=habitaciones,
        banos=banos,
        parqueaderos=parqueaderos,
        estrato=estrato,
        antiguedad=antiguedad,
        estado_aviso=estado_aviso,
        municipio_consulta=municipio_consulta,
    )


def parse_fincaraiz_file(file_path: Path, capture_date: Optional[str] = None) -> List[RawListing]:
    """Parsea un archivo JSON crudo de Fincaraíz y devuelve sus `RawListing`."""
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    day_str = capture_date or str(payload.get("fecha_captura") or file_path.parent.name)
    muni_consulta = payload.get("municipio_consulta")
    op_consulta = payload.get("operacion_consulta")

    listings: List[RawListing] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        parsed = parse_fincaraiz_item(
            item=item,
            capture_date=day_str,
            municipio_consulta=muni_consulta,
            operacion_consulta=op_consulta,
        )
        if parsed is not None:
            listings.append(parsed)
    return listings


def parse_fincaraiz_dir(source_date_dir: Path, capture_date: str) -> List[RawListing]:
    """Parsea todos los JSON crudos de Fincaraíz en `data/raw/fincaraiz/<fecha>/`."""
    records: List[RawListing] = []
    for json_path in sorted(source_date_dir.glob("*.json")):
        records.extend(parse_fincaraiz_file(json_path, capture_date=capture_date))
    return records
