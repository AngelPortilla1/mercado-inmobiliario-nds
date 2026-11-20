# Bitácora de Progreso y Continuidad entre Sesiones (`NSInmobilario`)

> **Propósito:** Este archivo mantiene el estado exacto del proyecto semana a semana para que cualquier nueva ventana de chat retome el trabajo con el 100% del contexto sin perder decisiones previas.

---

## Estado Actual
- **Semana completada:** **Semana 1 — Diseño y exploración de fuentes** (`COMPLETADA` el `2026-11-20`)
- **Próxima semana a ejecutar:** **Semana 2 — Scraper v1 y primera recolección**
- **Repositorio remoto:** `https://github.com/AngelPortilla1/mercado-inmobiliario-nds` (Privado, rama `main`)
- **Entorno Python:** `uv` configurado (`pyproject.toml` + `uv.lock`, Python 3.12.10, `uv run pytest` pasando 4/4 pruebas).

---

## Resumen de Avance por Semana

### [x] Semana 1: Diseño y exploración de fuentes (Completada — `2026-11-20`)
- [x] Estructura completa del repositorio creada (`docs/`, `src/`, `sql/`, `data/`, `notebooks/`, `dashboard/`, `reports/`, `tests/`).
- [x] `.gitignore` configurado desde el primer commit excluyendo `data/raw/*`, `*.db`, `.venv/` y `*.pdf`.
- [x] Auditoría de `robots.txt` y cobertura geográfica documentada en [`docs/legal.md`](legal.md):
  - **Fincaraíz (`fincaraiz.com.co`):** APROBADO — Cubre los 4 municipios (`pamplona`, `cucuta`, `los-patios`, `villa-del-rosario`) en `venta` y `arriendo`, con datos estructurados en `<script id="__NEXT_DATA__">`.
  - **Inmobiliaria Rentabien (`rentabien.com.co`):** APROBADO — Cubre Cúcuta, Los Patios, Villa del Rosario y Pamplona (HTML estático / WordPress).
  - **Casa Click (`casaclick.co/ciudad/pamplona/`):** APROBADO — Refuerzo de muestra local en Pamplona.
  - **Inmobiliaria Pamplona SAS (`inmobiliariapamplonasas.com.co`):** APROBADO — Refuerzo de muestra local en Pamplona.
  - **Inmobiliaria Bermúdez (`inmobiliariabermudez.com/arrienda`):** APROBADO con `Crawl-delay: 10` segundos.
  - **Metrocuadrado (`metrocuadrado.com`):** DESCARTADO / RESERVA por tener `Disallow: /detail/` y `Disallow: /metrocuadrado-results/` en su `robots.txt`.
- [x] Diccionario de datos y códigos DANE DIVIPOLA documentados en [`docs/diccionario_datos.md`](diccionario_datos.md) (`54518` Pamplona, `54001` Cúcuta, `54405` Los Patios, `54874` Villa del Rosario).
- [x] Preguntas de análisis (1 a 6) y las 9 reglas de limpieza documentadas en [`docs/metodologia.md`](metodologia.md).

---

### [ ] Semana 2: Scraper v1 y primera recolección (Siguiente paso)
- [ ] Construir scraper de **Fincaraíz** en `src/scrapers/fincaraiz.py` (para Pamplona, Cúcuta, Los Patios y Villa del Rosario; venta y arriendo) guardando crudo en `data/raw/fincaraiz/<AAAA-MM-DD>/`.
- [ ] Construir scraper de **Rentabien** en `src/scrapers/rentabien.py` guardando crudo en `data/raw/rentabien/<AAAA-MM-DD>/`.
- [ ] Construir scraper(s) de refuerzo local para **Pamplona** (`src/scrapers/casaclick.py` / `inmobiliariapamplona.py` / `bermudez.py` con pausa de 10s).
- [ ] Configurar logging detallado (páginas descargadas, avisos detectados, errores controlados).
- [ ] Hacer la primera corrida manual, inspeccionar los archivos crudos en `data/raw/` y dejar configurada la ejecución semanal.

---

### [ ] Semana 3: Parseo y limpieza
- [ ] Conectar los parsers de cada fuente en `src/cleaning/` hacia el formato estándar de 16 campos.
- [ ] Aplicar `clean_listings_dataframe()` (`src/cleaning/cleaner.py`), generar el reporte de calidad y exportar a `data/interim/` en CSV/Parquet.
- [ ] Ampliar pruebas unitarias con `uv run pytest` y crear notebook comparativo antes/después en `notebooks/`.

---

### [ ] Semana 4: Modelo SQL y carga
- [ ] Cargar los archivos de `data/interim/` hacia `data/processed/mercado_inmobiliario_nds.db` usando `src/db/load.py`.
- [ ] Verificar conteos por municipio, fechas, claves foráneas e idempotencia (`ON CONFLICT DO NOTHING`).

---

### [ ] Semana 5: Análisis y consultas
- [ ] Ejecutar las consultas de `sql/queries/analisis_mercado.sql`.
- [ ] Calcular intervalos de confianza al 95% por bootstrap (`src/analysis/stats.py`) para Pamplona.
- [ ] Ajustar modelo hedónico exploratorio $\log(\text{precio})$ con `statsmodels` y documentar 4–5 hallazgos en `notebooks/`.

---

### [ ] Semana 6: Serie de tiempo y automatización
- [ ] Integrar todo el flujo extremo a extremo en `src/pipeline.py` con alerta de caída de volumen ($< 50\%$).
- [ ] Automatizar corrida semanal (Programador de tareas de Windows o `/schedule`).

---

### [ ] Semana 7: Dashboard
- [ ] Construir dashboard de 5 páginas (Resumen, Comparativo de municipios, Pamplona en detalle, Tendencia, Metodología y calidad).

---

### [ ] Semana 8: Documentación y preparación de entrevista
- [ ] Finalizar `README.md` con hallazgos reales y capturas del dashboard.
- [ ] Redactar resumen ejecutivo de 1 página en `reports/` y practicar discurso de 60 segundos.
