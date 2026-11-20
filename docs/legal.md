# Registro de Revisión Legal y Ética (`robots.txt` y Términos de Uso)

> **Fecha de auditoría:** `2026-11-20`
> **Regla de oro del proyecto (Sección 2):** No asumir que se puede scrapear cualquier sitio. Todos los portales candidatos fueron verificados mediante su archivo `/robots.txt` y estructura pública antes de escribir código de extracción.

---

## 1. Principios Éticos y Técnicos de Recolección

1. **Solo datos del inmueble:** Se extraen únicamente variables físicas y económicas del inmueble (`precio`, `administracion`, `area_m2`, `habitaciones`, `banos`, `parqueaderos`, `estrato`, `antiguedad`, `barrio`, `municipio`, `tipo_inmueble`, `operacion`).
2. **Cero datos personales (PII):** **Nunca** se recolectan ni almacenan teléfonos, nombres de anunciantes o propietarios, correos electrónicos ni fotografías.
3. **Respeto al servidor (Rate Limiting):**
   - Pausa aleatoria de **3 a 6 segundos** (`random.uniform(3, 6)`) entre cada petición HTTP (y **10 segundos** en `inmobiliariabermudez.com` para respetar su directiva `Crawl-delay: 10`).
   - `User-Agent` transparente que identifica el proyecto académico/portafolio.
   - Frecuencia **estrictamente semanal** (1 corrida por semana, sin paralelismo agresivo).
4. **Protección de datos crudos:** La carpeta `data/raw/` está excluida en `.gitignore` desde el primer commit.

---

## 2. Matriz de Auditoría de Fuentes (Semana 1 — `2026-11-20`)

| Portal / Fuente | URL Base | Fecha de Revisión | Reglas en `robots.txt` (`User-agent: *`) | Cobertura en Norte de Santander | Renderizado y Estructura | Decisión |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **1. Fincaraíz** | `https://www.fincaraiz.com.co` | `2026-11-20` | Permite listados públicos (`/venta/<municipio>/norte-de-santander`, `/arriendo/...`). Solo restringe rutas combinadas `/*-y-*` y `/superadmin/`. | **Completa:** Pamplona, Cúcuta, Los Patios, Villa del Rosario. | HTML con JSON estructurado en `<script id="__NEXT_DATA__">`. | **APROBADO (Fuente Regional/Nacional 1)** |
| **2. Inmobiliaria Rentabien** | `https://rentabien.com.co` | `2026-11-20` | `Disallow: /wp-admin/` (WordPress estándar). Sin restricción sobre listados de inmuebles. | **Completa (Área Metropolitana y Regional):** Cúcuta, Los Patios, Villa del Rosario, Pamplona. | HTML estático / WordPress (`requests` + `BeautifulSoup`). | **APROBADO (Fuente Regional 2)** |
| **3. Casa Click** | `https://www.casaclick.co` | `2026-11-20` | `Disallow: /wp-admin/` (WordPress estándar). Incluye `Sitemap` público. | **Enfoque local:** Pamplona (`/ciudad/pamplona/`). | HTML estático / WordPress (`requests` + `BeautifulSoup`). | **APROBADO (Refuerzo Muestra Pamplona)** |
| **4. Inmobiliaria Pamplona SAS** | `https://inmobiliariapamplonasas.com.co` | `2026-11-20` | Solo restringe rutas de previsualización de HubSpot (`/_hcms/preview/`). | **Enfoque local:** Pamplona. | HTML estático (`requests` + `BeautifulSoup`). | **APROBADO (Refuerzo Muestra Pamplona)** |
| **5. Inmobiliaria Bermúdez** | `https://www.inmobiliariabermudez.com` | `2026-11-20` | Drupal estándar. Especifica **`Crawl-delay: 10`**; permite rutas públicas `/arrienda` y `/vende`. | **Enfoque local:** Pamplona. | HTML estático (`requests` + `BeautifulSoup` con pausa $\ge 10\text{ s}$). | **APROBADO (Con `Crawl-delay: 10s`)** |
| **6. Metrocuadrado** | `https://www.metrocuadrado.com` | `2026-11-20` | Restringe `/detail/`, `/metrocuadrado-results/` y rutas internas `Disallow: /web/`. | Cúcuta, Los Patios, Villa del Rosario. | Requiere cuidado por restricción en `/detail/` y `/metrocuadrado-results/`. | **RESERVA / SECUNDARIO** |

---

## 3. Evidencia de `robots.txt` Consultados (`2026-11-20`)

### 3.1. Fincaraíz (`https://www.fincaraiz.com.co/robots.txt`)
```text
User-agent: *
Disallow: /fbapps/
Disallow: /superadmin/
Disallow: /wsdl/
Disallow: /sitio/admin/
Disallow: /venta/*-y-*
Disallow: /arriendo/*-y-*
Sitemap: https://www.fincaraiz.com.co/cde-sitemap-listings-index.xml
```
- **Conclusión:** Las rutas por municipio individual (`/venta/pamplona/norte-de-santander`, `/arriendo/pamplona/norte-de-santander`, `/venta/cucuta/norte-de-santander`, `/venta/los-patios/norte-de-santander`, `/venta/villa-del-rosario/norte-de-santander`) están permitidas y devuelven el JSON completo de los avisos en `__NEXT_DATA__` sin necesidad de entrar al detalle de cada inmueble.

### 3.2. Inmobiliaria Rentabien (`https://rentabien.com.co/robots.txt`)
```text
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
```
- **Conclusión:** Permite la consulta de páginas públicas de arriendo y venta en Cúcuta, Los Patios, Villa del Rosario y Pamplona.

### 3.3. Casa Click (`https://www.casaclick.co/robots.txt`)
```text
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
Disallow: /wp-content/uploads/wpforms/
Sitemap: https://www.casaclick.co/sitemap.xml
```
- **Conclusión:** Permite acceso a `/ciudad/pamplona/`. Excelente fuente para aumentar el tamaño de muestra ($n$) en Pamplona.

### 3.4. Inmobiliaria Pamplona SAS (`https://inmobiliariapamplonasas.com.co/robots.txt`)
```text
User-agent: *
Disallow: /_hcms/preview/
Disallow: /hs/manage-preferences/
Disallow: /hs/preferences-center/
```
- **Conclusión:** Permite acceso a su catálogo público de inmuebles en Pamplona.

### 3.5. Inmobiliaria Bermúdez (`https://www.inmobiliariabermudez.com/robots.txt`)
```text
User-agent: *
Crawl-delay: 10
Disallow: /includes/
Disallow: /misc/
Disallow: /modules/
Disallow: /profiles/
Disallow: /scripts/
Disallow: /themes/
```
- **Conclusión:** Permite acceso a `/arrienda` y `/vende`, exigiendo explícitamente un `Crawl-delay: 10` segundos entre peticiones.

### 3.6. Metrocuadrado (`https://www.metrocuadrado.com/robots.txt`)
```text
User-agent: *
Disallow: /detail/
Disallow: /metrocuadrado-results/
Disallow: /_Incapsula_Resource?
```
- **Conclusión:** Dado que incluye `Disallow: /detail/` y `Disallow: /metrocuadrado-results/`, y siguiendo la Sección 2 del plan (*"Si un sitio restringe rutas de resultados o detalle, descártalo y documéntalo"*), lo dejamos documentado como descartado/reserva por precaución ética, lo cual demuestra rigor ante reclutadores.
