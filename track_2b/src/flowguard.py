"""Deterministic, bounded Hagen–Poiseuille calculation for lab capillaries.

The model must never be used for safety-critical equipment sizing. The LLM may
extract quantities, but all units, equations and domain checks live here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


MODEL_ID = "hagen-poiseuille-circular-tube-v1"
MODEL_SOURCE = "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nbsir74-620.pdf"
ENTRY_SOURCE = "https://www.me.psu.edu/cimbala/me320web_Spring_2015/Lectures/Tablet_PC_notes/ME320_Lecture_20.pdf"
LIMITATIONS = [
    "Tube droit de section circulaire, diamètre intérieur constant.",
    "Liquide newtonien incompressible, écoulement stationnaire, laminaire et développé.",
    "Pertes d'entrée, de sortie, raccords, coudes et rugosité non modélisés.",
    "Estimation pédagogique, sans certification ni garantie de sécurité du montage.",
]

_UNITS: dict[str, dict[str, float]] = {
    "density": {"kg/m3": 1.0, "kg/m^3": 1.0, "g/cm3": 1000.0, "g/cm^3": 1000.0},
    "dynamic_viscosity": {"Pa*s": 1.0, "Pa·s": 1.0, "Pa.s": 1.0, "Pa s": 1.0,
                          "mPa*s": 1e-3, "mPa·s": 1e-3, "mPa.s": 1e-3, "mPa s": 1e-3,
                          "cP": 1e-3},
    "tube_length": {"m": 1.0, "cm": 1e-2, "mm": 1e-3},
    "inner_diameter": {"m": 1.0, "mm": 1e-3, "um": 1e-6, "µm": 1e-6, "μm": 1e-6},
    "volumetric_flow_rate": {
        "m3/s": 1.0, "m^3/s": 1.0,
        "L/s": 1e-3, "L/min": 1e-3 / 60, "mL/s": 1e-6,
        "mL/min": 1e-6 / 60, "uL/min": 1e-9 / 60,
        "µL/min": 1e-9 / 60, "μL/min": 1e-9 / 60,
    },
}

_SI_UNITS = {
    "density": "kg/m3",
    "dynamic_viscosity": "Pa*s",
    "tube_length": "m",
    "inner_diameter": "m",
    "volumetric_flow_rate": "m3/s",
}


def _refuse(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "refused",
        "reason_code": code,
        "reason": message,
        "model": {"id": MODEL_ID, "source": MODEL_SOURCE, "entry_length_source": ENTRY_SOURCE},
        "limitations": LIMITATIONS,
    }


def _quantity(name: str, raw: Any) -> tuple[float, float | None, dict[str, Any]]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{name}: valeur et unité explicites requises")
    value = raw.get("value")
    unit = raw.get("unit")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: nombre fini strictement positif requis")
    if not isinstance(unit, str) or unit not in _UNITS[name]:
        raise ValueError(f"{name}: unité absente ou non prise en charge")
    rel = raw.get("uncertainty_relative")
    if rel is not None:
        if isinstance(rel, bool) or not isinstance(rel, (int, float)) or not math.isfinite(rel) or not 0 <= rel < 1:
            raise ValueError(f"{name}: incertitude relative attendue entre 0 inclus et 1 exclu")
        rel = float(rel)
    si_value = float(value) * _UNITS[name][unit]
    if not math.isfinite(si_value) or si_value <= 0:
        raise ValueError(f"{name}: valeur SI hors plage numérique")
    return si_value, rel, {"value": si_value, "unit": _SI_UNITS[name]}


def solve_pipe(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Validate explicit inputs and compute pressure loss, or refuse with a reason.

    Required keys: fluid_kind="liquid", newtonian=True, incompressible=True,
    straight_circular_tube=True, minor_losses_present=False, and five quantities
    (density, dynamic_viscosity, tube_length, inner_diameter,
    volumetric_flow_rate) as {value, unit, uncertainty_relative?}.
    """
    if not isinstance(inputs, Mapping):
        return _refuse("invalid_input", "Objet JSON d'entrée requis.")

    conditions = (
        ("fluid_kind", "liquid", "unsupported_fluid", "Seuls les liquides sont pris en charge ; gaz et état inconnu refusés."),
        ("newtonian", True, "non_newtonian", "Fluide newtonien confirmé requis."),
        ("incompressible", True, "compressible_or_unknown", "Hypothèse incompressible confirmée requise."),
        ("straight_circular_tube", True, "unsupported_geometry", "Tube droit circulaire confirmé requis."),
        ("minor_losses_present", False, "minor_losses", "Présence ou incertitude sur des coudes, raccords ou pertes singulières."),
    )
    for key, expected, code, message in conditions:
        if key == "fluid_kind" and inputs.get(key) != expected:
            return _refuse(code, message)
        if key != "fluid_kind" and (type(inputs.get(key)) is not bool or inputs[key] is not expected):
            return _refuse(code, message)

    values: dict[str, float] = {}
    uncertainty: dict[str, float | None] = {}
    inputs_si: dict[str, dict[str, Any]] = {}
    try:
        for name in _UNITS:
            values[name], uncertainty[name], inputs_si[name] = _quantity(name, inputs.get(name))
    except ValueError as exc:
        return _refuse("invalid_quantity", str(exc))

    rho = values["density"]
    mu = values["dynamic_viscosity"]
    length = values["tube_length"]
    diameter = values["inner_diameter"]
    flow_rate = values["volumetric_flow_rate"]
    try:
        area = math.pi * diameter**2 / 4
        velocity = flow_rate / area
        reynolds = rho * velocity * diameter / mu
        entry_length = 0.05 * reynolds * diameter
        delta_p = 128 * mu * length * flow_rate / (math.pi * diameter**4)
        gradient = delta_p / length
    except (OverflowError, ZeroDivisionError):
        return _refuse("numeric_range", "Calcul hors plage numérique fiable.")
    if not all(math.isfinite(v) for v in (area, velocity, reynolds, entry_length, delta_p, gradient)):
        return _refuse("numeric_range", "Calcul hors plage numérique fiable.")
    if reynolds >= 2300:
        return _refuse("reynolds_limit", f"Re = {reynolds:.6g} ≥ 2300 : régime laminaire non établi.")
    if length < entry_length:
        return _refuse("undeveloped_flow", f"Longueur {length:.6g} m < longueur d'entrée estimée {entry_length:.6g} m.")

    if all(value is not None for value in uncertainty.values()):
        u = {key: float(value) for key, value in uncertainty.items() if value is not None}
        try:
            re_high = 4 * (rho * (1 + u["density"])) * (flow_rate * (1 + u["volumetric_flow_rate"])) / (
                math.pi * (mu * (1 - u["dynamic_viscosity"])) * (diameter * (1 - u["inner_diameter"]))
            )
        except (OverflowError, ZeroDivisionError):
            return _refuse("numeric_range", "Intervalle d'incertitude hors plage numérique fiable.")
        if re_high >= 2300:
            return _refuse("uncertain_regime", "L'intervalle des mesures peut dépasser Re = 2300.")
        try:
            entry_high = 0.05 * 4 * (rho * (1 + u["density"])) * (flow_rate * (1 + u["volumetric_flow_rate"])) / (
                math.pi * (mu * (1 - u["dynamic_viscosity"]))
            )
        except (OverflowError, ZeroDivisionError):
            return _refuse("numeric_range", "Intervalle d'incertitude hors plage numérique fiable.")
        if length * (1 - u["tube_length"]) < entry_high:
            return _refuse("uncertain_entry_length", "L'intervalle des mesures peut inclure un écoulement non développé.")
        try:
            low = 128 * (mu * (1 - u["dynamic_viscosity"])) * (length * (1 - u["tube_length"])) * (
                flow_rate * (1 - u["volumetric_flow_rate"])
            ) / (math.pi * (diameter * (1 + u["inner_diameter"]))**4)
            high = 128 * (mu * (1 + u["dynamic_viscosity"])) * (length * (1 + u["tube_length"])) * (
                flow_rate * (1 + u["volumetric_flow_rate"])
            ) / (math.pi * (diameter * (1 - u["inner_diameter"]))**4)
        except (OverflowError, ZeroDivisionError):
            return _refuse("numeric_range", "Intervalle d'incertitude hors plage numérique fiable.")
        if not all(math.isfinite(v) for v in (low, high, re_high)):
            return _refuse("numeric_range", "Intervalle d'incertitude hors plage numérique fiable.")
        uncertainty_result: dict[str, Any] = {
            "status": "quantified",
            "method": "Bornes déterministes par combinaison extrême des incertitudes relatives fournies ; sans hypothèse statistique.",
            "pressure_drop_interval_pa": [low, high],
            "reynolds_upper_bound": re_high,
        }
    else:
        uncertainty_result = {
            "status": "not_quantified",
            "reason": "Incertitude relative absente pour au moins une grandeur ; aucune borne n'est inventée.",
        }

    return {
        "status": "ok",
        "model": {"id": MODEL_ID, "source": MODEL_SOURCE, "entry_length_source": ENTRY_SOURCE},
        "inputs_si": inputs_si,
        "results": {
            "pressure_drop_pa": delta_p,
            "pressure_drop_kpa": delta_p / 1000,
            "reynolds_number": reynolds,
            "mean_velocity_m_s": velocity,
            "laminar_entry_length_m": entry_length,
            "pressure_gradient_pa_m": gradient,
        },
        "equations": {
            "pressure_drop": "Δp = 128 μ L Q / (π d⁴)",
            "reynolds": "Re = 4 ρ Q / (π μ d)",
            "entry_length_estimate": "Lₑ ≈ 0.05 Re d",
        },
        "uncertainty": uncertainty_result,
        "limitations": LIMITATIONS,
    }


def analyze_question(question: str) -> dict[str, Any]:
    """Extract explicit quantities with Apertus, then apply the fixed physics gate."""
    from .apertus_client import AssumptionError, ExtractionError, extract_quantities

    try:
        extracted, model_name = extract_quantities(question)
    except AssumptionError as exc:
        return _refuse("unsafe_assumption", str(exc))
    except ExtractionError as exc:
        return {"status": "error", "reason_code": "extraction_error", "reason": str(exc)}
    result = solve_pipe(extracted)
    result["extraction"] = {
        "model": model_name,
        "role": "Extraction de grandeurs et d'hypothèses déclarées ; aucun calcul physique par le LLM.",
        "values": extracted,
    }
    return result
