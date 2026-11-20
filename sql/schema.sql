-- =============================================================================
-- Esquema Estrella: Mercado Inmobiliario en Norte de Santander
-- Compatible con SQLite y PostgreSQL
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_municipio (
    municipio_id INTEGER PRIMARY KEY,
    codigo_dane  TEXT UNIQUE NOT NULL,
    nombre       TEXT NOT NULL,
    departamento TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_fuente (
    fuente_id INTEGER PRIMARY KEY,
    nombre    TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_tipo_inmueble (
    tipo_id INTEGER PRIMARY KEY,
    nombre  TEXT UNIQUE NOT NULL -- apartamento, casa, apartaestudio, lote...
);

CREATE TABLE IF NOT EXISTS dim_barrio (
    barrio_id    INTEGER PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES dim_municipio(municipio_id),
    nombre       TEXT NOT NULL,
    UNIQUE (municipio_id, nombre)
);

CREATE TABLE IF NOT EXISTS fact_aviso_captura (
    captura_id      INTEGER PRIMARY KEY,
    fecha_captura   DATE NOT NULL,
    fuente_id       INTEGER NOT NULL REFERENCES dim_fuente(fuente_id),
    id_aviso_fuente TEXT NOT NULL,
    municipio_id    INTEGER NOT NULL REFERENCES dim_municipio(municipio_id),
    barrio_id       INTEGER REFERENCES dim_barrio(barrio_id),
    tipo_id         INTEGER REFERENCES dim_tipo_inmueble(tipo_id),
    operacion       TEXT NOT NULL CHECK (operacion IN ('venta', 'arriendo')),
    precio          NUMERIC,
    administracion  NUMERIC,
    area_m2         NUMERIC,
    habitaciones    INTEGER,
    banos           INTEGER,
    parqueaderos    INTEGER,
    estrato         INTEGER,
    antiguedad      TEXT,
    precio_m2       NUMERIC,
    is_outlier_iqr  INTEGER DEFAULT 0,
    url             TEXT,
    UNIQUE (fecha_captura, fuente_id, id_aviso_fuente)
);

-- Índices para acelerar consultas analíticas y series de tiempo
CREATE INDEX IF NOT EXISTS idx_fact_fecha_operacion
    ON fact_aviso_captura (fecha_captura, operacion);

CREATE INDEX IF NOT EXISTS idx_fact_municipio_operacion
    ON fact_aviso_captura (municipio_id, operacion);

CREATE INDEX IF NOT EXISTS idx_fact_aviso_historico
    ON fact_aviso_captura (fuente_id, id_aviso_fuente, fecha_captura);

-- Semilla inicial de municipios de Norte de Santander (Códigos DANE DIVIPOLA oficiales)
INSERT INTO dim_municipio (municipio_id, codigo_dane, nombre, departamento) VALUES
    (1, '54518', 'pamplona', 'norte de santander'),
    (2, '54001', 'cucuta', 'norte de santander'),
    (3, '54405', 'los patios', 'norte de santander'),
    (4, '54874', 'villa del rosario', 'norte de santander'),
    (5, '54261', 'el zulia', 'norte de santander'),
    (6, '54673', 'san cayetano', 'norte de santander'),
    (7, '54498', 'ocana', 'norte de santander')
ON CONFLICT (codigo_dane) DO NOTHING;
