"""
Contrato estándar de datos entre los parsers de cada fuente (`src/cleaning/parsers/`)
y el motor de limpieza (`src/cleaning/cleaner.py`).

Define:
- Los 16 campos de captura documentados en docs/diccionario_datos.md (`STANDARD_COLUMNS`).
- 2 campos auxiliares de auditoría (`AUDIT_COLUMNS`) que solo viajan del parser hacia
  `cleaner.py` para ejecutar de forma auditable las Reglas 4 y 11 sin que ningún parser
  filtre registros en silencio.
- El dataclass `RawListing` y helpers para construir y validar DataFrames uniformes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import pandas as pd

# 16 campos de captura por aviso (docs/diccionario_datos.md; precio_m2 es calculado)
STANDARD_COLUMNS: Tuple[str, ...] = (
    "id_aviso_fuente",
    "fuente",
    "url",
    "operacion",
    "tipo_inmueble",
    "municipio",
    "barrio",
    "precio",
    "administracion",
    "area_m2",
    "habitaciones",
    "banos",
    "parqueaderos",
    "estrato",
    "antiguedad",
    "fecha_captura",
)

# 2 campos auxiliares de auditoría (parser -> cleaner.py; no se cargan a fact_aviso_captura)
AUDIT_COLUMNS: Tuple[str, ...] = (
    "estado_aviso",
    "municipio_consulta",
)

# Esquema completo que todo parser debe entregar
PARSER_COLUMNS: Tuple[str, ...] = STANDARD_COLUMNS + AUDIT_COLUMNS

# Columnas calculadas en cleaner.py antes de exportar a data/interim/ y cargar a SQL
DERIVED_COLUMNS: Tuple[str, ...] = (
    "codigo_dane",
    "precio_m2",
    "is_outlier_iqr",
)

# Columnas finales esperadas por src/db/load.py y sql/schema.sql
INTERIM_COLUMNS: Tuple[str, ...] = STANDARD_COLUMNS + DERIVED_COLUMNS

VALID_ESTADOS_AVISO: Tuple[str, ...] = ("activo", "inactivo")


@dataclass
class RawListing:
    """
    Registro estandarizado emitido por cualquier parser de fuente antes de aplicar
    las 11 reglas de limpieza en `src/cleaning/cleaner.py`.
    """

    id_aviso_fuente: str
    fuente: str
    fecha_captura: str
    url: Optional[str] = None
    operacion: Optional[str] = None
    tipo_inmueble: Optional[str] = None
    municipio: Optional[str] = None
    barrio: Optional[str] = None
    precio: Optional[Any] = None
    administracion: Optional[Any] = None
    area_m2: Optional[Any] = None
    habitaciones: Optional[int] = None
    banos: Optional[int] = None
    parqueaderos: Optional[int] = None
    estrato: Optional[int] = None
    antiguedad: Optional[str] = None
    estado_aviso: str = "activo"
    municipio_consulta: Optional[str] = None

    def __post_init__(self) -> None:
        self.id_aviso_fuente = str(self.id_aviso_fuente).strip()
        self.fuente = str(self.fuente).strip().lower()
        self.fecha_captura = str(self.fecha_captura).strip()

        if not self.id_aviso_fuente:
            raise ValueError("id_aviso_fuente no puede estar vacío.")
        if not self.fuente:
            raise ValueError("fuente no puede estar vacío.")
        if not self.fecha_captura:
            raise ValueError("fecha_captura no puede estar vacío.")

        self.estado_aviso = str(self.estado_aviso).strip().lower()
        if self.estado_aviso not in VALID_ESTADOS_AVISO:
            raise ValueError(
                f"estado_aviso inválido: {self.estado_aviso!r}. "
                f"Debe ser uno de {VALID_ESTADOS_AVISO}."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Devuelve el registro como diccionario con el orden exacto de PARSER_COLUMNS."""
        return {col: getattr(self, col) for col in PARSER_COLUMNS}


def listings_to_dataframe(records: Sequence[RawListing]) -> pd.DataFrame:
    """
    Convierte una secuencia de `RawListing` a un DataFrame con el esquema exacto
    `PARSER_COLUMNS`, incluso si la secuencia está vacía.
    """
    if not records:
        return pd.DataFrame(columns=list(PARSER_COLUMNS))
    rows = [record.to_dict() for record in records]
    return pd.DataFrame(rows, columns=list(PARSER_COLUMNS))


def validate_raw_dataframe(df: pd.DataFrame) -> None:
    """
    Valida que un DataFrame crudo contenga al menos todas las `STANDARD_COLUMNS`
    antes de pasarlo al motor de limpieza.
    """
    missing = [col for col in STANDARD_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias del contrato de parsers: {missing}"
        )
