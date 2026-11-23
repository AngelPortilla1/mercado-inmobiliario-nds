# Bitácora de Hallazgos y Decisiones Técnicas (Formato STAR)

> **Propósito:** Documentar en formato **STAR** (*Situación, Tarea, Acción, Resultado*) los hallazgos reales de calidad de datos, decisiones metodológicas y soluciones de ingeniería del proyecto `NSInmobilario`, tanto para trazabilidad técnica como para preparación de entrevistas (Semana 8).

---

## Caso STAR #1: Detección y mitigación de sesgo por inmuebles no residenciales y avisos inactivos en la primera captura

* **Fecha:** `2026-11-23` (Auditoría previa a Semana 3 — Parseo y limpieza)
* **Etapa del pipeline:** Transición de `data/raw/` (Semana 2) hacia `src/cleaning/` y `data/interim/` (Semana 3)
* **Fuentes auditadas:** Fincaraíz, Inmobiliaria Rentabien, Inmobiliaria Bermúdez, Casa Click e Inmobiliaria Pamplona SAS (`80` archivos crudos del `2026-11-21`, `695` avisos brutos)

---

### S — Situación (Situation)
La pregunta central del proyecto busca comparar el **mercado de vivienda** de Pamplona frente a Cúcuta y su área metropolitana (Los Patios y Villa del Rosario) mediante medianas de precio por $\text{m}^2$, tamaño de oferta activa y proxy de liquidez semanal.

Tras completar la primera recolección ética de la Semana 2 (`2026-11-21`) con **695 avisos brutos** en 5 portales aprobados, los listados públicos de portales regionales e inmobiliarias locales devolvían bajo las mismas rutas de `venta` y `arriendo` todo su inventario mezclado sin segmentación estricta por uso del suelo (residencial vs. comercial/industrial/lotes), además de publicaciones históricas ya cerradas (`Vendido` / `Arrendado`) y fichas sin precio publicado.

---

### T — Tarea (Task)
Antes de implementar los parsers de Semana 3 y cargar datos al modelo estrella SQL (`sql/schema.sql`), era necesario auditar la composición real de los 80 archivos crudos para:
1. Cuantificar cuántos avisos no correspondían a vivienda ni a oferta activa con precio.
2. Evaluar el riesgo de sesgo estadístico sobre las medianas de `precio_m2`, el cálculo del rango intercuartílico (`is_outlier_iqr`) y el conteo de stock activo.
3. Definir una regla de filtrado auditable que preservara la integridad estadística del estudio sin comprometer el tamaño mínimo de muestra ($n \ge 15$) en el caso de estudio principal (Pamplona).

---

### A — Acción (Action)
Se ejecutó una auditoría exploratoria directa sobre los **80 archivos crudos** en `data/raw/*/2026-11-21/` antes de escribir lógica de parseo, clasificando cada aviso por fuente, tipo de inmueble, estado de disponibilidad y presencia de precio:

#### 1. Diagnóstico cuantitativo del hallazgo (695 avisos brutos)

| Fuente | Total brutos | Vivienda | No vivienda | % No vivienda | Hallazgo adicional (estado / precio) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Fincaraíz** | 380 | 273 | 107 | 28,2% | 0 inactivos, 0 sin precio |
| **Rentabien** | 220 | 172 | 48 | 21,8% | 220 marcados `"Disponible"`, 0 sin precio |
| **Bermúdez (Pamplona)** | 56 | 36 | 20 | **35,7%** | 0 inactivos, 0 sin precio (**13 de 29 arriendos eran locales = 44,8%**) |
| **Casa Click (Pamplona)** | 13 | 12 | 1 | 7,7% | **5 de 13 marcados como `Vendido`** (38,5%) |
| **Inmob. Pamplona SAS** | 26 | 20 | 6 | 23,1% | **20 de 26 marcados como `Arrendado`** y **26/26 sin precio** (`"Consultar valor"`) |
| **TOTAL** | **695** | **513** | **182** | **26,2%** | **5 viviendas `Vendido` + 20 viviendas sin precio** |

**Desglose exacto de los 182 avisos no correspondientes a vivienda (26,2% del crudo):**
* **Locales comerciales:** `108` (`62` Fincaraíz, `27` Rentabien, `14` Bermúdez, `5` Inmob. Pamplona)
* **Lotes:** `39` (`25` Fincaraíz, `10` Rentabien, `3` Bermúdez, `1` Casa Click)
* **Bodegas:** `17` (`12` Fincaraíz, `5` Rentabien)
* **Oficinas:** `4` (`3` Fincaraíz, `1` Rentabien)
* **Consultorios:** `4` (`2` Rentabien, `1` Fincaraíz, `1` Inmob. Pamplona)
* **Edificios:** `3` (`2` Fincaraíz, `1` Rentabien)
* **Fincas:** `3` (`2` Fincaraíz, `1` Bermúdez)
* **Otros / sin clasificar:** `4` (`1` parqueadero, `1` hotel, `1` otro, `1` tipo vacío en Bermúdez)

#### 2. Decisión de diseño implementada para Semana 3
En lugar de mezclar segmentos heterogéneos o borrar datos silenciosamente, se definieron **dos reglas auditables adicionales** en [`docs/metodologia.md`](metodologia.md) (Reglas 10 y 11):
1. **Taxonomía canónica y filtro de alcance residencial (antes del IQR):** Clasificar `tipo_inmueble` en vivienda (`apartamento`, `casa`, `apartaestudio`, `duplex`, `casa_campestre`, `casa_lote`, `cabana`) frente a no vivienda (`local`, `lote`, `bodega`, `oficina`, `consultorio`, `edificio`, `finca`, `parqueadero`, `hotel`, `otro`), excluyendo los no residenciales **antes** de calcular $Q_1, Q_3$ y `is_outlier_iqr` para que locales comerciales o lotes no deformen los umbrales de vivienda.
2. **Filtro de oferta activa con precio publicado:** Excluir avisos etiquetados como `Vendido` / `Arrendado` (evitando precios históricos desactualizados, stock inflado y distorsión del proxy de liquidez `dias_visible`) y registros sin precio numérico (`precio <= 0` o `NULL`).
3. **Trazabilidad total en el reporte de calidad:** Conservar el crudo intacto en `data/raw/` y registrar en `reporte_calidad` los contadores explícitos `descartados_no_vivienda` (con desglose por tipo), `descartados_inactivos` y `descartados_sin_precio`.

---

### R — Resultado (Result)
1. **Eliminación de sesgo severo antes de modelar:** Se evitó contaminar el análisis residencial con **182 inmuebles no vivienda (26,2%)** y **25 viviendas inactivas o sin precio (3,6%)**. El mayor impacto preventivo se dio en **Pamplona Arriendo**, donde los locales comerciales representaban casi la mitad de la fuente Bermúdez (`13/29 = 44,8%`) y habrían sesgado al alza la mediana de canon por $\text{m}^2$.
2. **Conservación de potencia estadística en los 8 segmentos:** Incluso tras eliminar el ~30% de registros fuera de alcance (proyección previa a deduplicación), el dataset retiene **488 avisos activos de vivienda con precio**, de los cuales **485 (99,4%) cuentan con área válida** en $[10, 5.000]\text{ m}^2$:

| Municipio | Operación | Vivienda activa con precio ($n$) | Con área válida (para `precio_m2`) | Estado frente a umbral ($n \ge 15$) |
| :--- | :--- | :---: | :---: | :---: |
| **Pamplona** | Venta | 35 | 33 | Cumple |
| **Pamplona** | Arriendo | 17 | 17 | Cumple |
| **Cúcuta** | Venta | 80 | 80 | Cumple |
| **Cúcuta** | Arriendo | 49 | 49 | Cumple |
| **Los Patios** | Venta | 89 | 89 | Cumple |
| **Los Patios** | Arriendo | 74 | 74 | Cumple |
| **Villa del Rosario** | Venta | 76 | 75 | Cumple |
| **Villa del Rosario** | Arriendo | 68 | 68 | Cumple |
| **TOTAL (captura `2026-11-21`)** | **Todas** | **488** | **485 (99,4%)** | **8/8 segmentos válidos** |

3. **Valor metodológico y de portafolio:** Convertir un problema real de datos sucios en reglas auditables y cuantificadas refuerza la confiabilidad del modelo estrella SQL (Semana 4), del modelo hedónico exploratorio (Semana 5) y de los intervalos bootstrap en Pamplona.
