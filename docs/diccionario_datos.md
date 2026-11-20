# Diccionario de Datos y Referencia Geográfica (DANE DIVIPOLA)

Este documento define los campos estandarizados que se extraen de cada aviso inmobiliario y su mapeo hacia el modelo estrella en SQL (`sql/schema.sql`).

---

## 1. Campos de Captura por Aviso

> **Nota:** Si un campo no aparece en un portal específico, se almacena como `NULL` (`None` en Python) y se documenta en el reporte de calidad. Nunca se imputan valores sin justificación explícita.

| Campo | Tipo en SQL | Tipo en Python / Pandas | Obligatorio | Descripción y Regla de Negocio |
| :--- | :--- | :--- | :---: | :--- |
| `id_aviso_fuente` | `TEXT` | `str` | Sí | Identificador único del aviso dentro del portal de origen. |
| `fuente` | `TEXT` (FK `dim_fuente`) | `str` | Sí | Nombre estandarizado del portal origen (en minúsculas). |
| `url` | `TEXT` | `str` | Sí | Enlace público del aviso (usado también para validar el municipio real). |
| `operacion` | `TEXT` | `str` | Sí | Tipo de transacción: estrictamente `'venta'` o `'arriendo'`. Nunca mezclar. |
| `tipo_inmueble` | `TEXT` (FK `dim_tipo_inmueble`) | `str` | Sí | Categoría normalizada: `'apartamento'`, `'casa'`, `'apartaestudio'`, `'lote'`, `'local'`, etc. |
| `municipio` | `TEXT` (FK `dim_municipio`) | `str` | Sí | Municipio normalizado y validado contra código DANE DIVIPOLA. |
| `barrio` | `TEXT` (FK `dim_barrio`) | `str` | No | Nombre del barrio o sector normalizado (minúsculas, sin tildes). |
| `precio` | `NUMERIC` | `float` | Sí | Valor pedido en pesos colombianos (COP), sin puntos ni símbolos, separado de la administración. |
| `administracion` | `NUMERIC` | `float` | No | Cuota de administración mensual en COP (si se especifica por separado). |
| `area_m2` | `NUMERIC` | `float` | No* | Área construida o privada en metros cuadrados ($m^2$). Rango válido urbano: $[10, 5000]$. |
| `precio_m2` | `NUMERIC` | `float` | Calculado | `precio / area_m2`. Se calcula **solo** cuando `precio` y `area_m2` son válidos. |
| `habitaciones` | `INTEGER` | `Int64` | No | Número de habitaciones o alcobas. |
| `banos` | `INTEGER` | `Int64` | No | Número de baños. |
| `parqueaderos` | `INTEGER` | `Int64` | No | Número de garajes o parqueaderos. |
| `estrato` | `INTEGER` | `Int64` | No | Estrato socioeconómico ($1$ a $6$), si el portal lo reporta. |
| `antiguedad` | `TEXT` | `str` | No | Rango o años de antigüedad del inmueble, si el portal lo reporta. |
| `fecha_captura` | `DATE` | `str` (`YYYY-MM-DD`) | Sí | Fecha ISO en la que el scraper descargó el aviso. |

---

## 2. Códigos DANE (DIVIPOLA) — Norte de Santander (Departamento `54`)

Para garantizar integridad referencial en `dim_municipio`, se utilizan los códigos oficiales DIVIPOLA del DANE:

| `codigo_dane` | Municipio (`nombre`) | Departamento | Rol en el Estudio |
| :---: | :--- | :--- | :--- |
| **`54518`** | **Pamplona** | Norte de Santander | **Caso de estudio principal** (ciudad universitaria/intermedia, muestra pequeña). |
| **`54001`** | **Cúcuta** | Norte de Santander | Capital departamental y principal referente comparativo. |
| **`54405`** | **Los Patios** | Norte de Santander | Área Metropolitana de Cúcuta. |
| **`54874`** | **Villa del Rosario** | Norte de Santander | Área Metropolitana de Cúcuta. |
| **`54261`** | **El Zulia** | Norte de Santander | Área Metropolitana de Cúcuta (opcional según cobertura). |
| **`54673`** | **San Cayetano** | Norte de Santander | Área Metropolitana de Cúcuta (opcional según cobertura). |
| **`54498`** | **Ocaña** | Norte de Santander | Referente regional secundario (opcional para ampliar universo regional). |
