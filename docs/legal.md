# Registro de Revisión Legal y Ética (`robots.txt` y Términos de Uso)

> **Regla de oro del proyecto (Sección 2):** No asumas que se puede scrapear cualquier sitio. Antes de ejecutar un scraper sobre un portal, revisa sus Términos y Condiciones y su archivo `https://sitio.com/robots.txt`. Si prohíbe el scraping, **descarta la fuente** o aplica el Plan B (Sección 12).

---

## 1. Principios Éticos y Técnicos de Recolección

1. **Solo datos del inmueble:** Se extraen únicamente variables físicas y económicas del inmueble (`precio`, `administracion`, `area_m2`, `habitaciones`, `banos`, `parqueaderos`, `estrato`, `antiguedad`, `barrio`, `municipio`, `tipo_inmueble`, `operacion`).
2. **Cero datos personales (PII):** **Nunca** se recolectan ni almacenan teléfonos, nombres de anunciantes o propietarios, correos electrónicos ni fotografías.
3. **Respeto al servidor (Rate Limiting):**
   - Pausa aleatoria de **3 a 6 segundos** (`random.uniform(3, 6)`) entre cada petición HTTP.
   - `User-Agent` transparente que identifica el proyecto académico/portafolio y un correo de contacto.
   - Frecuencia **estrictamente semanal** (1 corrida por semana, sin paralelismo agresivo).
4. **Protección de datos crudos:** La carpeta `data/raw/` está excluida en `.gitignore` desde el primer commit. En el repositorio público solo se comparten el código, agregados estadísticos y muestras pequeñas anonimizadas en `data/processed/`.

---

## 2. Matriz de Auditoría de Fuentes (Semana 1)

Completa esta tabla al inspeccionar los 2 o 3 portales candidatos con presencia en Norte de Santander (Pamplona, Cúcuta, Los Patios, Villa del Rosario):

| Portal / Fuente | URL Base | Fecha de Revisión | Reglas en `robots.txt` | Resumen Términos y Condiciones | Renderizado (HTML estático vs. JS) | Paginación y Campos en Listado vs. Detalle | Decisión (`APROBADO` / `DESCARTADO`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| *Ejemplo: Portal A* | `https://...` | `2026-11-20` | `Allow: /` (revisar rutas bloqueadas) | Revisar cláusula de extracción automatizada | HTML / JS | Paginación por `?page=N`; listado incluye precio, área, habs. | *Pendiente de verificar* |
| *Ejemplo: Portal B* | `https://...` | `2026-11-20` | ... | ... | ... | ... | *Pendiente de verificar* |
| *Ejemplo: Portal C* | `https://...` | `2026-11-20` | ... | ... | ... | ... | *Pendiente de verificar* |

---

## 3. Evidencia de `robots.txt`

### Portal 1: [Nombre del Portal]
- **Fecha de consulta:** `AAAA-MM-DD`
- **URL consultada:** `https://.../robots.txt`
- **Extracto relevante:**
```text
# Pegar aquí las directivas User-agent y Disallow/Allow relevantes
```
- **Conclusión de uso:** [Explicar por qué es viable o por qué se descartó].
