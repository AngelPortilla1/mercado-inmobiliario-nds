"""
Parser para archivos JSON crudos sanitizados de Inmobiliaria Rentabien
(`data/raw/rentabien/<AAAA-MM-DD>/*.json`).

Decisiones clave implementadas:
- Para avisos con `biz = "ARRIENDO/VENTA"` (`price = "9000000/480000000"`), selecciona
  exclusivamente `rent` o `saleprice` según `operacion_consulta` para no mezclar precios.
- `estado_aviso` depende de `status == 1` / `status_name == "Disponible"` (NO de
  `reference = "Arrendado"`, que corresponde a propiedades activas en venta con inquilino).
- `url` se deja en `None` porque la API Domus de Rentabien no devuelve enlace público.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.cleaning.parsers.schema import RawListing

logger = logging.getLogger(__name__)

SOURCE_NAME = "rentabien"

DANE_TO_MUNICIPIO: Dict[str, str] = {
    "54518": "pamplona",
    "54001": "cucuta",
    "54405": "los patios",
    "54874": "villa del rosario",
    "54261": "el zulia",
    "54673": "san cayetano",
    "54498": "ocana",
}


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str) and "/" in value:
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


def _resolve_operacion(item: Dict[str, Any], operacion_consulta: Optional[str]) -> Optional[str]:
    biz_code = item.get("biz_code")
    biz_text = str(item.get("biz") or "").strip().lower()

    # Caso mixto "ARRIENDO/VENTA" (biz_code == 3): respetar la operación consultada
    if biz_code == 3 or ("arriendo" in biz_text and "venta" in biz_text):
        return operacion_consulta.strip().lower() if operacion_consulta else None

    if biz_code == 1 or biz_text == "arriendo":
        return "arriendo"
    if biz_code == 2 or biz_text == "venta":
        return "venta"

    return operacion_consulta.strip().lower() if operacion_consulta else None


def _resolve_precio(item: Dict[str, Any], operacion: Optional[str]) -> Optional[float]:
    """
    Lee el precio específico de la operación (`rent` para arriendo, `saleprice` para venta)
    evitando concatenar precios compuestos como '9000000/480000000'.
    """
    if operacion == "arriendo":
        val = _safe_float(item.get("rent"))
        if val is not None:
            return val
    elif operacion == "venta":
        val = _safe_float(item.get("saleprice"))
        if val is not None:
            return val

    return _safe_float(item.get("price"))


def _resolve_municipio(item: Dict[str, Any], fallback: Optional[str]) -> Optional[str]:
    city_code = str(item.get("city_code") or "").strip()
    if city_code in DANE_TO_MUNICIPIO:
        return DANE_TO_MUNICIPIO[city_code]

    city = item.get("city")
    if isinstance(city, str) and city.strip():
        return city.strip()

    return fallback


def _resolve_estrato(item: Dict[str, Any]) -> Optional[int]:
    val = _safe_positive_int(item.get("stratum"))
    if val is not None and 1 <= val <= 6:
        return val
    return None


def _resolve_antiguedad(item: Dict[str, Any]) -> Optional[str]:
    year = _safe_positive_int(item.get("build_year"))
    if year is not None and 1900 <= year <= 2035:
        return str(year)
    return None


def _resolve_estado_aviso(item: Dict[str, Any]) -> str:
    status = item.get("status")
    status_name = str(item.get("status_name") or "").strip().lower()
    if status == 1 or status_name == "disponible":
        return "activo"
    return "inactivo"


def parse_rentabien_item(
    item: Dict[str, Any],
    capture_date: str,
    municipio_consulta: Optional[str] = None,
    operacion_consulta: Optional[str] = None,
) -> Optional[RawListing]:
    """Convierte un aviso individual del JSON de Rentabien a `RawListing`."""
    raw_id = item.get("codpro") or item.get("idpro")
    if raw_id is None or not str(raw_id).strip():
        return None

    operacion = _resolve_operacion(item, operacion_consulta)
    precio = _resolve_precio(item, operacion)
    administracion = _safe_float(item.get("administration"))

    # Área construida prioritaria; respaldo a área de lote (ej. lotes con area_cons == 0)
    area_m2 = _safe_float(item.get("area_cons"))
    if area_m2 is None:
        area_m2 = _safe_float(item.get("area_lot"))

    tipo_raw = item.get("type")
    tipo_inmueble = str(tipo_raw).strip() if tipo_raw else None

    barrio_raw = item.get("neighborhood")
    barrio = str(barrio_raw).strip() if isinstance(barrio_raw, str) and barrio_raw.strip() else None

    return RawListing(
        id_aviso_fuente=str(raw_id).strip(),
        fuente=SOURCE_NAME,
        fecha_captura=capture_date,
        url=None,
        operacion=operacion,
        tipo_inmueble=tipo_inmueble,
        municipio=_resolve_municipio(item, fallback=municipio_consulta),
        barrio=barrio,
        precio=precio,
        administracion=administracion,
        area_m2=area_m2,
        habitaciones=_safe_positive_int(item.get("bedrooms")),
        banos=_safe_positive_int(item.get("bathrooms")),
        parqueaderos=_safe_non_negative_int(item.get("parking")),
        estrato=_resolve_estrato(item),
        antiguedad=_resolve_antiguedad(item),
        estado_aviso=_resolve_estado_aviso(item),
        municipio_consulta=municipio_consulta,
    )


def parse_rentabien_file(file_path: Path, capture_date: Optional[str] = None) -> List[RawListing]:
    """Parsea un archivo JSON crudo de Rentabien y devuelve sus `RawListing`."""
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    day_str = capture_date or str(payload.get("fecha_captura") or file_path.parent.name)
    muni_consulta = payload.get("municipio_consulta")
    op_consulta = payload.get("operacion_consulta")

    listings: List[RawListing] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        parsed = parse_rentabien_item(
            item=item,
            capture_date=day_str,
            municipio_consulta=muni_consulta,
            operacion_consulta=op_consulta,
        )
        if parsed is not None:
            listings.append(parsed)
    return listings


def parse_rentabien_dir(source_date_dir: Path, capture_date: str) -> List[RawListing]:
    """Parsea todos los JSON crudos de Rentabien en `data/raw/rentabien/<fecha>/`."""
    records: List[RawListing] = []
    for json_path in sorted(source_date_dir.glob("*.json")):
        records.extend(parse_rentabien_file(json_path, capture_date=capture_date))
    return records
