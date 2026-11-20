"""
Módulo de base de datos y carga idempotente (Semana 4).
Permite crear/reconstruir la base SQLite desde sql/schema.sql y cargar
archivos limpios desde data/interim/ sin duplicar registros (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/processed/mercado_inmobiliario_nds.db")
DEFAULT_SCHEMA_PATH = Path("sql/schema.sql")


def init_database(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    """Inicializa el esquema estrella en SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = schema_path.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    logger.info("Base de datos inicializada correctamente en: %s", db_path)


def _get_or_create_dim_id(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    unique_cols: dict,
) -> Optional[int]:
    """Obtiene el ID de una tabla de dimensión o lo inserta si no existe."""
    if any(v is None or pd.isna(v) for v in unique_cols.values()):
        return None

    cols = list(unique_cols.keys())
    vals = [unique_cols[c] for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)

    conn.execute(
        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
        vals,
    )
    where_clause = " AND ".join([f"{c} = ?" for c in cols])
    cur = conn.execute(f"SELECT {id_col} FROM {table} WHERE {where_clause}", vals)
    row = cur.fetchone()
    return int(row[0]) if row else None


def load_dataframe_to_db(
    df: pd.DataFrame,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """
    Carga un DataFrame limpio en fact_aviso_captura y sus dimensiones asociadas.
    Usa INSERT ... ON CONFLICT DO NOTHING para garantizar idempotencia.
    Devuelve el número de filas procesadas.
    """
    init_database(db_path=db_path)
    inserted = 0

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")

        for _, row in df.iterrows():
            fuente_id = _get_or_create_dim_id(
                conn, "dim_fuente", "fuente_id", {"nombre": row.get("fuente")}
            )
            cur = conn.execute(
                "SELECT municipio_id FROM dim_municipio WHERE codigo_dane = ? OR nombre = ?",
                (row.get("codigo_dane"), row.get("municipio")),
            )
            muni_row = cur.fetchone()
            if not muni_row or fuente_id is None:
                continue
            municipio_id = int(muni_row[0])

            tipo_id = _get_or_create_dim_id(
                conn, "dim_tipo_inmueble", "tipo_id", {"nombre": row.get("tipo_inmueble")}
            )
            barrio_id = _get_or_create_dim_id(
                conn,
                "dim_barrio",
                "barrio_id",
                {"municipio_id": municipio_id, "nombre": row.get("barrio")},
            )

            conn.execute(
                """
                INSERT INTO fact_aviso_captura (
                    fecha_captura, fuente_id, id_aviso_fuente, municipio_id,
                    barrio_id, tipo_id, operacion, precio, administracion,
                    area_m2, habitaciones, banos, parqueaderos, estrato,
                    antiguedad, precio_m2, is_outlier_iqr, url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (fecha_captura, fuente_id, id_aviso_fuente) DO NOTHING
                """,
                (
                    row.get("fecha_captura"),
                    fuente_id,
                    str(row.get("id_aviso_fuente")),
                    municipio_id,
                    barrio_id,
                    tipo_id,
                    row.get("operacion"),
                    None if pd.isna(row.get("precio")) else float(row.get("precio")),
                    None if pd.isna(row.get("administracion")) else float(row.get("administracion")),
                    None if pd.isna(row.get("area_m2")) else float(row.get("area_m2")),
                    None if pd.isna(row.get("habitaciones")) else int(row.get("habitaciones")),
                    None if pd.isna(row.get("banos")) else int(row.get("banos")),
                    None if pd.isna(row.get("parqueaderos")) else int(row.get("parqueaderos")),
                    None if pd.isna(row.get("estrato")) else int(row.get("estrato")),
                    None if pd.isna(row.get("antiguedad")) else str(row.get("antiguedad")),
                    None if pd.isna(row.get("precio_m2")) else float(row.get("precio_m2")),
                    int(row.get("is_outlier_iqr", 0)),
                    None if pd.isna(row.get("url")) else str(row.get("url")),
                ),
            )
            inserted += 1

        conn.commit()

    logger.info("Carga finalizada: %d registros procesados hacia %s", inserted, db_path)
    return inserted
