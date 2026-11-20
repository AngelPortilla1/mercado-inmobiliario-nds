# Metodología, Preguntas de Análisis y Reglas de Limpieza

## 1. Pregunta Central del Proyecto
> **¿Cómo se compara el mercado de vivienda de Pamplona con el de Cúcuta y su área metropolitana, y cómo evoluciona en el tiempo?**

### Preguntas Específicas de Análisis (Sección 8)
1. **Nivel de precios por $m^2$:** ¿Cuál es la mediana de precio por $m^2$ por municipio, separando estrictamente `venta` y `arriendo`?
2. **Determinantes del precio:** ¿Cómo varía el precio según número de habitaciones, tipo de inmueble y valor de administración?
3. **Tamaño del mercado (oferta relativa):** ¿Cuántos avisos activos hay en Pamplona frente a Cúcuta, Los Patios y Villa del Rosario?
4. **Dinámica temporal:** ¿Cómo evolucionan la mediana del precio por $m^2$ y el stock total de avisos semana a semana?
5. **Proxy de liquidez (tiempo en el mercado):** ¿Cuánto tiempo permanece publicado un aviso (`MAX(fecha_captura) - MIN(fecha_captura)`) antes de retirarse?
6. **Micro-mercados en Pamplona:** ¿Qué barrios de Pamplona concentran la oferta disponible y en qué rangos de precio (reportando explícitamente la advertencia de muestra pequeña)?

---

## 2. Reglas de Limpieza Estandarizadas (Sección 7)

Cada transformación en `src/cleaning/cleaner.py` sigue estas 9 reglas auditables:

1. **Precios y Administración:**
   - Convertir cadenas como `"$ 1.300.000"` a numérico (`1300000`).
   - Separar explícitamente la cuota de administración cuando venga concatenada (ej. `"+ $ 30.000 admin"`).
2. **Área ($m^2$):**
   - Extraer el valor numérico de expresiones como `"116 m²"`.
   - **Filtro de plausibilidad física:** Descartar áreas menores a $10\text{ m}^2$ o mayores a $5.000\text{ m}^2$ para vivienda urbana (se registran en el reporte de calidad como descartados por área fuera de rango).
3. **Valores Atípicos (Outliers):**
   - **Marcar (`is_outlier_iqr`), no borrar a ciegas.**
   - Calcular el rango intercuartílico ($\text{IQR} = Q_3 - Q_1$) agrupando por `(municipio, operacion)`.
   - Marcar registros fuera de $[Q_1 - 1.5 \times \text{IQR},\; Q_3 + 1.5 \times \text{IQR}]$ para revisión manual de errores de digitación (como un cero de más).
4. **Ubicación Geográfica:**
   - Normalizar `municipio` y `barrio` a minúsculas, sin tildes y con espacios limpios.
   - Mapear contra la tabla DIVIPOLA del DANE.
   - **Validación cruzada:** Muchos portales mezclan municipios en los resultados de búsqueda; el municipio debe validarse contra el slug de la URL o el campo de ubicación explícita del aviso.
5. **Duplicados Intra-fuente:**
   - Deduplicar por clave única `(fecha_captura, fuente, id_aviso_fuente)`.
6. **Duplicados Inter-fuentes:**
   - Detectar el mismo inmueble publicado en distintos portales mediante clave aproximada `(municipio, barrio, round(area_m2), round(precio, -4), habitaciones)`.
   - Regla de resolución: conservar el registro de la fuente con mayor completitud de campos (menos `NULL`s).
7. **Tratamiento de Nulos:**
   - No imputar valores faltantes sin justificación estadística o de dominio.
8. **Cálculo de `precio_m2`:**
   - Se calcula como `precio / area_m2` **únicamente** cuando ambos campos son no nulos y válidos.
9. **Separación Estricta de Operaciones:**
   - Ninguna métrica, gráfico ni consulta puede mezclar `venta` con `arriendo`.

---

## 3. Rigor Estadístico y Limitaciones Declaradas

- **Mediana sobre promedio:** Los precios inmobiliarios presentan fuerte asimetría positiva (cola derecha). Todas las comparaciones principales utilizan la **mediana** y el rango intercuartílico.
- **Tamaño de muestra visible ($n$):** Todo KPI, tabla o gráfico debe mostrar explícitamente el número de avisos ($n$) sobre el cual se calculó.
- **Incertidumbre en Pamplona (Bootstrap):** Dado que Pamplona tiene un volumen de avisos significativamente menor que Cúcuta, se calcula un **intervalo de confianza al 95% mediante bootstrap** (ej. $10.000$ remuestreos con reemplazo sobre la mediana del precio por $m^2$). Cuando $n < 15$, se incluye advertencia expresa de muestra insuficiente para inferencia fuerte.
- **Modelo Hedónico Exploratorio (Semana 5):** Regresión lineal de $\log(\text{precio})$ sobre $\text{area\_m2}$, $\text{habitaciones}$, $\text{banos}$ y efectos fijos de $\text{municipio}$ usando `statsmodels`, presentada con carácter descriptivo/exploratorio.
- **Sesgo de cobertura y precios pedidos:** Los portales reflejan **precios de oferta (asking prices)**, no precios efectivos de cierre tras negociación, y subrepresentan el mercado informal o de voz a voz (muy común en arriendos estudiantiles en Pamplona).
