"""
Módulo de rigor estadístico (Sección 8 y Semana 5):
- Intervalos de confianza por Bootstrap para la mediana (clave para Pamplona por muestra pequeña).
- Modelo hedónico exploratorio log(precio) ~ area_m2 + habitaciones + banos + C(municipio).
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def bootstrap_median_ci(
    values: pd.Series,
    n_boot: int = 10000,
    ci: float = 0.95,
    random_state: int = 42,
) -> Dict[str, Optional[float]]:
    """
    Calcula la mediana muestral y su intervalo de confianza por bootstrap.
    Ideal para reportar incertidumbre en municipios con muestra pequeña como Pamplona.
    """
    clean = values.dropna().to_numpy(dtype=float)
    n = len(clean)
    if n == 0:
        return {"n": 0, "mediana": None, "ci_lower": None, "ci_upper": None}

    mediana = float(np.median(clean))
    if n < 3:
        return {"n": n, "mediana": mediana, "ci_lower": None, "ci_upper": None}

    rng = np.random.default_rng(random_state)
    samples = rng.choice(clean, size=(n_boot, n), replace=True)
    boot_medians = np.median(samples, axis=1)

    alpha = (1.0 - ci) / 2.0
    lower = float(np.quantile(boot_medians, alpha))
    upper = float(np.quantile(boot_medians, 1.0 - alpha))

    return {
        "n": n,
        "mediana": round(mediana, 2),
        "ci_lower": round(lower, 2),
        "ci_upper": round(upper, 2),
    }
