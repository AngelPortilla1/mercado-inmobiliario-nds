# Mercado Inmobiliario en Norte de Santander (Pamplona como caso de estudio)

> **Pregunta central:** ¿Cómo se compara el mercado de vivienda de Pamplona con el de Cúcuta y su área metropolitana (Los Patios y Villa del Rosario), y cómo evoluciona en el tiempo?

---

## 1. Resumen Ejecutivo
Proyecto de ingeniería y análisis de datos end-to-end que recolecta semanalmente avisos públicos de vivienda en Norte de Santander, aplica reglas auditables de limpieza y deduplicación, modela la información en un esquema estrella SQL y expone hallazgos con rigor estadístico (medianas e intervalos de confianza por bootstrap para muestras pequeñas como Pamplona).

---

## 2. Vista Previa del Dashboard
*(En Semana 7 se insertarán aquí las capturas de pantalla del dashboard de Power BI / Tableau con sus 5 páginas: Resumen, Comparativo de municipios, Pamplona en detalle, Tendencia y Metodología).*

---

## 3. Hallazgos Clave
*(Se completará en Semana 5 con las cifras reales y el tamaño de muestra $n$ de cada municipio)*:
- **Comparativo de precio por $m^2$ (Venta y Arriendo):** `[Pendiente primera captura - siempre reportando mediana y n]`
- **Tamaño relativo del mercado:** `[Oferta activa en Pamplona vs. Cúcuta, Los Patios y Villa del Rosario]`
- **Proxy de liquidez (Tiempo en el mercado):** `[Días promedio/mediana de permanencia de los avisos]`
- **Micro-mercados en Pamplona:** `[Concentración por barrios con intervalo bootstrap 95%]`

---

## 4. Datos, Legalidad y Ética
- **Auditoría previa:** Antes de recolectar datos, se revisan los Términos y Condiciones y `robots.txt` de cada portal en [`docs/legal.md`](docs/legal.md).
- **Privacidad (Cero PII):** Solo se extraen atributos físicos y de precio del inmueble. **Nunca** se descargan teléfonos, nombres de anunciantes, correos ni fotografías.
- **Respeto al servidor:** Ejecución estrictamente semanal con pausas aleatorias de 3 a 6 segundos entre peticiones y `User-Agent` identificable.
- **Protección de datos crudos:** El directorio `data/raw/` está excluido mediante `.gitignore`. En el repositorio público solo se incluyen el código, agregados y muestras anonimizadas.

---

## 5. Metodología y Limpieza de Datos
Documentada en detalle en [`docs/metodologia.md`](docs/metodologia.md) y [`docs/diccionario_datos.md`](docs/diccionario_datos.md):
1. Separación de precio principal y cuota de administración.
2. Filtro de plausibilidad física para vivienda urbana ($10\text{ m}^2 \le \text{área} \le 5.000\text{ m}^2$).
3. Marcado de valores atípicos por rango intercuartílico ($\text{IQR}$) agrupado por municipio y operación (`is_outlier_iqr`).
4. Estandarización geográfica validada con códigos oficiales **DANE DIVIPOLA** (`54518` Pamplona, `54001` Cúcuta, `54405` Los Patios, `54874` Villa del Rosario).
5. Deduplicación intra-fuente e inter-fuente.
6. Separación estricta entre **venta** y **arriendo**.

---

## 6. Limitaciones y Sesgos Declarados
- **Precios pedidos (Asking prices):** Los avisos reflejan el precio de oferta inicial y no el precio final de cierre tras negociación.
- **Cobertura parcial:** En municipios intermedios y universitarios como Pamplona, una fracción importante del mercado de arriendo circula por redes informales o carteles físicos.
- **Tamaño de muestra en Pamplona:** Debido al menor número de avisos ($n$), se reportan medianas acompañadas de intervalos de confianza por **bootstrap** y advertencias explícitas cuando $n < 15$.

---

## 7. Estructura del Repositorio y Reproducibilidad

```text
mercado-inmobiliario-nds/
├── README.md
├── requirements.txt
├── docs/
│   ├── legal.md               # Términos y robots.txt revisados, con fecha
│   ├── diccionario_datos.md   # Campos y códigos DANE DIVIPOLA
│   └── metodologia.md         # Reglas de limpieza y diseño estadístico
├── src/
│   ├── scrapers/              # Un módulo por fuente + base_scraper.py
│   ├── cleaning/              # Reglas de limpieza y reporte de calidad
│   ├── db/                    # Carga idempotente al esquema estrella
│   ├── analysis/              # Bootstrap e inferencia exploratoria
│   └── pipeline.py            # Orquestador semanal
├── sql/
│   ├── schema.sql             # Modelo estrella (dimensiones y tabla de hechos)
│   └── queries/               # Consultas analíticas comentadas
├── data/
│   ├── raw/                   # Ignorado en Git (.gitignore)
│   ├── interim/               # Tablas limpias en CSV/Parquet
│   └── processed/             # Base SQLite y muestras agregadas
├── notebooks/
├── dashboard/
├── reports/
└── tests/
```

### Instalación y Ejecución (con `uv`)
```powershell
# 1. Crear entorno e instalar dependencias desde pyproject.toml / uv.lock
uv sync

# 2. Ejecutar pruebas unitarias de limpieza
uv run pytest

# 3. Inicializar base de datos y correr pipeline semanal
uv run python -m src.pipeline
```

---

## 8. Stack Tecnológico
- **Lenguaje y Scraping:** Python (`requests`, `BeautifulSoup4`, `lxml`, `Playwright` opcional)
- **Limpieza y Estadística:** `pandas`, `numpy`, `statsmodels`, `scipy`, `pytest`
- **Base de Datos:** SQL (`SQLite` / `PostgreSQL`) con modelado dimensional en estrella
- **Visualización:** Power BI / Tableau
- **Automatización:** Programador de tareas de Windows / GitHub Actions
