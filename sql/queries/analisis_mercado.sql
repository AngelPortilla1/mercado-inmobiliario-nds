-- =============================================================================
-- Consultas Analíticas del Proyecto (Sección 8)
-- Incluye sintaxis PostgreSQL (PERCENTILE_CONT) y alternativa portable con
-- funciones de ventana para SQLite 3.25+ / PostgreSQL.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Mediana de precio por m² y tamaño de muestra (n) por municipio y operación
--    en la captura más reciente (Versión PostgreSQL)
-- -----------------------------------------------------------------------------
SELECT
    m.nombre AS municipio,
    f.operacion,
    COUNT(*) AS n_avisos,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.precio_m2) AS mediana_precio_m2,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY f.precio_m2) AS p25_precio_m2,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY f.precio_m2) AS p75_precio_m2
FROM fact_aviso_captura f
JOIN dim_municipio m USING (municipio_id)
WHERE f.precio_m2 IS NOT NULL
  AND COALESCE(f.is_outlier_iqr, 0) = 0
  AND f.fecha_captura = (SELECT MAX(fecha_captura) FROM fact_aviso_captura)
GROUP BY m.nombre, f.operacion
ORDER BY f.operacion, mediana_precio_m2 DESC;


-- -----------------------------------------------------------------------------
-- 1B. Mediana de precio por m² compatible con SQLite (usando Window Functions)
-- -----------------------------------------------------------------------------
WITH base AS (
    SELECT
        m.nombre AS municipio,
        f.operacion,
        f.precio_m2,
        ROW_NUMBER() OVER (
            PARTITION BY m.nombre, f.operacion
            ORDER BY f.precio_m2
        ) AS rn,
        COUNT(*) OVER (
            PARTITION BY m.nombre, f.operacion
        ) AS n_avisos
    FROM fact_aviso_captura f
    JOIN dim_municipio m USING (municipio_id)
    WHERE f.precio_m2 IS NOT NULL
      AND COALESCE(f.is_outlier_iqr, 0) = 0
      AND f.fecha_captura = (SELECT MAX(fecha_captura) FROM fact_aviso_captura)
)
SELECT
    municipio,
    operacion,
    MAX(n_avisos) AS n_avisos,
    ROUND(AVG(precio_m2), 2) AS mediana_precio_m2
FROM base
WHERE rn IN ((n_avisos + 1) / 2, (n_avisos + 2) / 2)
GROUP BY municipio, operacion
ORDER BY operacion, mediana_precio_m2 DESC;


-- -----------------------------------------------------------------------------
-- 2. Variación del precio según habitaciones, tipo de inmueble y administración
-- -----------------------------------------------------------------------------
SELECT
    m.nombre AS municipio,
    f.operacion,
    t.nombre AS tipo_inmueble,
    f.habitaciones,
    COUNT(*) AS n_avisos,
    ROUND(AVG(f.precio), 0) AS promedio_precio,
    ROUND(AVG(f.administracion), 0) AS promedio_admin,
    ROUND(AVG(f.precio_m2), 0) AS promedio_precio_m2
FROM fact_aviso_captura f
JOIN dim_municipio m USING (municipio_id)
LEFT JOIN dim_tipo_inmueble t USING (tipo_id)
WHERE f.fecha_captura = (SELECT MAX(fecha_captura) FROM fact_aviso_captura)
  AND COALESCE(f.is_outlier_iqr, 0) = 0
GROUP BY m.nombre, f.operacion, t.nombre, f.habitaciones
HAVING COUNT(*) >= 3
ORDER BY m.nombre, f.operacion, t.nombre, f.habitaciones;


-- -----------------------------------------------------------------------------
-- 3. Tamaño del mercado: stock de avisos en Pamplona frente a otros municipios
-- -----------------------------------------------------------------------------
SELECT
    m.nombre AS municipio,
    f.operacion,
    COUNT(*) AS total_avisos,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY f.operacion),
        2
    ) AS pct_oferta_departamental
FROM fact_aviso_captura f
JOIN dim_municipio m USING (municipio_id)
WHERE f.fecha_captura = (SELECT MAX(fecha_captura) FROM fact_aviso_captura)
GROUP BY m.nombre, f.operacion
ORDER BY f.operacion, total_avisos DESC;


-- -----------------------------------------------------------------------------
-- 4. Evolución semanal de la mediana y del stock (PostgreSQL)
-- -----------------------------------------------------------------------------
SELECT
    DATE_TRUNC('week', f.fecha_captura) AS semana,
    m.nombre AS municipio,
    f.operacion,
    COUNT(*) AS n_stock,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.precio_m2) AS mediana_precio_m2
FROM fact_aviso_captura f
JOIN dim_municipio m USING (municipio_id)
WHERE f.precio_m2 IS NOT NULL
  AND COALESCE(f.is_outlier_iqr, 0) = 0
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;


-- -----------------------------------------------------------------------------
-- 5. Tiempo en el mercado (Proxy de liquidez: primera y última fecha visible)
-- -----------------------------------------------------------------------------
SELECT
    f.id_aviso_fuente,
    fu.nombre AS fuente,
    m.nombre AS municipio,
    f.operacion,
    MIN(f.fecha_captura) AS primera_vez,
    MAX(f.fecha_captura) AS ultima_vez,
    COUNT(DISTINCT f.fecha_captura) AS semanas_capturado,
    -- En PostgreSQL: MAX(f.fecha_captura) - MIN(f.fecha_captura)
    -- En SQLite: JULIANDAY(MAX(f.fecha_captura)) - JULIANDAY(MIN(f.fecha_captura))
    CAST(
        JULIANDAY(MAX(f.fecha_captura)) - JULIANDAY(MIN(f.fecha_captura))
        AS INTEGER
    ) AS dias_visible
FROM fact_aviso_captura f
JOIN dim_fuente fu USING (fuente_id)
JOIN dim_municipio m USING (municipio_id)
GROUP BY f.id_aviso_fuente, fu.nombre, m.nombre, f.operacion
ORDER BY dias_visible DESC;


-- -----------------------------------------------------------------------------
-- 6. Barrios de Pamplona que concentran la oferta y rangos de precio
--    (Incluye bandera de advertencia cuando n < 10)
-- -----------------------------------------------------------------------------
SELECT
    COALESCE(b.nombre, 'sin especificar') AS barrio,
    f.operacion,
    COUNT(*) AS n_avisos,
    MIN(f.precio) AS precio_min,
    MAX(f.precio) AS precio_max,
    ROUND(AVG(f.precio_m2), 0) AS precio_m2_ref,
    CASE
        WHEN COUNT(*) < 5 THEN 'MUESTRA MUY PEQUEÑA (n < 5): solo referencial'
        WHEN COUNT(*) < 15 THEN 'MUESTRA PEQUEÑA (n < 15): interpretar con cautela'
        ELSE 'MUESTRA ACEPTABLE'
    END AS advertencia_estadistica
FROM fact_aviso_captura f
JOIN dim_municipio m USING (municipio_id)
LEFT JOIN dim_barrio b USING (barrio_id)
WHERE m.codigo_dane = '54518' -- Pamplona
  AND f.fecha_captura = (SELECT MAX(fecha_captura) FROM fact_aviso_captura)
  AND COALESCE(f.is_outlier_iqr, 0) = 0
GROUP BY COALESCE(b.nombre, 'sin especificar'), f.operacion
ORDER BY f.operacion, n_avisos DESC;
