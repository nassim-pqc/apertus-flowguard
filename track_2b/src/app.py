"""Command-line demonstration. All output is JSON; no credentials are printed."""

from __future__ import annotations

import argparse
import json
import os

from .flowguard import analyze_question, solve_pipe


DEMO_INPUT = {
    "fluid_kind": "liquid",
    "newtonian": True,
    "incompressible": True,
    "straight_circular_tube": True,
    "minor_losses_present": False,
    "density": {"value": 998, "unit": "kg/m3", "uncertainty_relative": 0.01},
    "dynamic_viscosity": {"value": 1, "unit": "mPa*s", "uncertainty_relative": 0.02},
    "tube_length": {"value": 5, "unit": "cm", "uncertainty_relative": 0.01},
    "inner_diameter": {"value": 100, "unit": "um", "uncertainty_relative": 0.02},
    "volumetric_flow_rate": {"value": 10, "unit": "uL/min", "uncertainty_relative": 0.02},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apertus FlowGuard — bounded capillary pressure estimate")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--question", help="French or English text; requires configured Apertus 1.5 endpoint")
    group.add_argument("--input-json", help="Explicit structured input JSON; deterministic mode")
    args = parser.parse_args()
    question = args.question or os.getenv("FLOWGUARD_QUESTION")
    structured = args.input_json or os.getenv("FLOWGUARD_INPUT_JSON")
    if question and structured:
        result = {"status": "refused", "reason_code": "ambiguous_mode", "reason": "Choisir question OU entrée JSON."}
    elif question:
        result = analyze_question(question)
    elif structured:
        try:
            result = solve_pipe(json.loads(structured))
        except json.JSONDecodeError:
            result = {"status": "refused", "reason_code": "invalid_json", "reason": "Entrée JSON illisible."}
    else:
        result = solve_pipe(DEMO_INPUT)
        result["demo_mode"] = "Données synthétiques intégrées ; aucun appel au modèle. Définir FLOWGUARD_QUESTION et LLM_* pour tester Apertus."
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
