# Reglas del Proyecto: Mercado Inmobiliario en Norte de Santander (`NSInmobilario`)

## 1. Legalidad, Ética y Privacidad en Scraping (Sección 2)
- **Cero Datos Personales (PII):** Nunca extraigas, proceses ni almacenes teléfonos, nombres de anunciantes o propietarios, correos electrónicos ni fotografías. Solo se recolectan atributos físicos, geográficos y económicos del inmueble.
- **Cumplimiento de `robots.txt` y Rate Limiting:**
  - Solo se pueden consultar fuentes aprobadas en `docs/legal.md`.
  - Mantener pausa aleatoria de **3 a 6 segundos** (`random.uniform(3, 6)`) entre peticiones HTTP (y mínimo **10 segundos** en `inmobiliariabermudez.com`).
  - Usar siempre un `User-Agent` que identifique el proyecto académico/portafolio.
- **Persistencia del Crudo y Protección en Git:**
  - Guardar siempre primero el HTML o JSON crudo en `data/raw/<fuente>/<AAAA-MM-DD>/` antes de parsear.
  - Nunca subir el contenido de `data/raw/`, bases de datos `.db` ni el PDF guía al repositorio de GitHub.

## 2. Limpieza de Datos e Integridad Geográfica (Secciones 6 y 7)
- **Separación estricta de operación:** Nunca mezclar precios ni métricas de `venta` y `arriendo`.
- **Plausibilidad y Outliers:** Filtrar áreas urbanas fuera de $[10\text{ m}^2, 5.000\text{ m}^2]$ y **marcar** (no borrar a ciegas) los valores atípicos mediante rango intercuartílico (`is_outlier_iqr`) agrupado por `(municipio, operacion)`.
- **Validación DANE DIVIPOLA:** Todo municipio debe estar normalizado y mapeado a su código oficial DANE (`54518` Pamplona, `54001` Cúcuta, `54405` Los Patios, `54874` Villa del Rosario).

## 3. Rigor Estadístico (Sección 8)
- **Mediana y tamaño de muestra ($n$):** Reportar siempre la **mediana** (nunca solo el promedio) acompañada explícitamente del número de avisos ($n$).
- **Incertidumbre en muestras pequeñas (Pamplona):** Incluir intervalos de confianza al 95% por **bootstrap** para la mediana del precio por $\text{m}^2$ y mostrar advertencias explícitas cuando $n < 15$.
