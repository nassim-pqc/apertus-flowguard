"""Small numerical and refusal checks independent of the hosted model."""

import copy
import io
import json
import os
import unittest
from unittest.mock import patch

from src.apertus_client import ExtractionError, _endpoint, _unit_is_quoted, _validate_extraction
from src.app import DEMO_INPUT
from src.flowguard import analyze_question, solve_pipe
from evaluation.evaluate import _prediction


class PipeModelTests(unittest.TestCase):
    def test_reference_capillary_and_bounds(self):
        result = solve_pipe(DEMO_INPUT)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["results"]["pressure_drop_pa"], 3395.3054526, places=4)
        self.assertAlmostEqual(result["results"]["reynolds_number"], 2.117821776, places=7)
        low, high = result["uncertainty"]["pressure_drop_interval_pa"]
        self.assertLess(low, result["results"]["pressure_drop_pa"])
        self.assertGreater(high, result["results"]["pressure_drop_pa"])

    def test_absent_uncertainty_is_not_fabricated(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        del inputs["inner_diameter"]["uncertainty_relative"]
        self.assertEqual(solve_pipe(inputs)["uncertainty"]["status"], "not_quantified")

    def test_gas_and_non_newtonian_refused(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["fluid_kind"] = "gas"
        self.assertEqual(solve_pipe(inputs)["reason_code"], "unsupported_fluid")
        inputs["fluid_kind"] = "liquid"
        inputs["newtonian"] = False
        self.assertEqual(solve_pipe(inputs)["reason_code"], "non_newtonian")

    def test_turbulent_or_transition_flow_refused(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["volumetric_flow_rate"] = {"value": 1, "unit": "L/s"}
        self.assertEqual(solve_pipe(inputs)["reason_code"], "reynolds_limit")

    def test_short_tube_refused(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["inner_diameter"] = {"value": 1, "unit": "mm"}
        inputs["tube_length"] = {"value": 1, "unit": "mm"}
        inputs["volumetric_flow_rate"] = {"value": 5, "unit": "mL/min"}
        self.assertEqual(solve_pipe(inputs)["reason_code"], "undeveloped_flow")

    def test_invalid_unit_and_missing_assumption_refused(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["inner_diameter"]["unit"] = "inch"
        self.assertEqual(solve_pipe(inputs)["reason_code"], "invalid_quantity")
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["minor_losses_present"] = None
        self.assertEqual(solve_pipe(inputs)["reason_code"], "minor_losses")

    def test_spaced_viscosity_unit_is_equivalent(self):
        inputs = copy.deepcopy(DEMO_INPUT)
        inputs["dynamic_viscosity"]["unit"] = "mPa s"
        self.assertAlmostEqual(solve_pipe(inputs)["results"]["pressure_drop_pa"], 3395.3054526, places=4)


class ExtractionTests(unittest.TestCase):
    @staticmethod
    def _declared_case(extra: str = "") -> tuple[str, dict]:
        question = ("Liquid Newtonian incompressible in a straight circular capillary with inner diameter 100 um, "
                    "length 5 cm, density 998 kg/m3, viscosity 1 mPa s, flow 10 uL/min. No fittings. " + extra)
        extracted = {
            "fluid_kind": "liquid", "newtonian": True, "incompressible": True,
            "straight_circular_tube": True, "minor_losses_present": False,
            "density": {"value": 998, "unit": "kg/m3", "evidence": "998 kg/m3", "uncertainty_relative": None},
            "dynamic_viscosity": {"value": 1, "unit": "mPa*s", "evidence": "1 mPa s", "uncertainty_relative": None},
            "tube_length": {"value": 5, "unit": "cm", "evidence": "5 cm", "uncertainty_relative": None},
            "inner_diameter": {"value": 100, "unit": "um", "evidence": "100 um", "uncertainty_relative": None},
            "volumetric_flow_rate": {"value": 10, "unit": "uL/min", "evidence": "10 uL/min", "uncertainty_relative": None},
        }
        return question, extracted

    def test_spaced_viscosity_citation_matches_canonical_unit(self):
        question, extracted = self._declared_case()
        self.assertTrue(_unit_is_quoted("mPa*s", "1 mPa s"))
        self.assertEqual(_validate_extraction(extracted, question), extracted)

    def test_outer_diameter_cannot_be_used_as_inner(self):
        question, extracted = self._declared_case("The 100 um figure is the outer diameter; wall thickness is unknown.")
        with self.assertRaises(ExtractionError):
            _validate_extraction(extracted, question)

    def test_rectangular_channel_refused_even_if_model_says_circular(self):
        question, extracted = self._declared_case("Actual channel cross section is rectangular.")
        with self.assertRaises(ExtractionError):
            _validate_extraction(extracted, question)

    def test_elbow_refused_even_if_model_says_no_fittings(self):
        question, extracted = self._declared_case("But the line also contains an elbow and a valve.")
        with self.assertRaises(ExtractionError):
            _validate_extraction(extracted, question)

    def test_unspecified_minor_losses_refused(self):
        question, extracted = self._declared_case()
        question = question.replace("No fittings.", "")
        with self.assertRaises(ExtractionError):
            _validate_extraction(extracted, question)

    def test_remote_endpoint_requires_https(self):
        with self.assertRaises(ExtractionError):
            _endpoint("http://example.org/v1")
        self.assertEqual(_endpoint("http://localhost:8000/v1"), "http://localhost:8000/v1/chat/completions")

    def test_conflicting_measurement_and_quote_refused(self):
        question = "liquide 100 um"
        extracted = {key: None for key in (
            "fluid_kind", "newtonian", "incompressible", "straight_circular_tube",
            "minor_losses_present", "density", "dynamic_viscosity", "tube_length",
            "inner_diameter", "volumetric_flow_rate",
        )}
        extracted["inner_diameter"] = {
            "value": 200, "unit": "um", "evidence": "100 um", "uncertainty_relative": None,
        }
        with self.assertRaises(ExtractionError):
            _validate_extraction(extracted, question)

    def test_mock_apertus_response_flows_to_deterministic_solver(self):
        question = ("Liquide newtonien incompressible dans un tube droit circulaire sans pertes singulières : "
                    "densité 998 kg/m3, viscosité 1 mPa s, longueur 5 cm, diamètre intérieur 100 um, débit 10 uL/min.")
        extracted = {
            "fluid_kind": "liquid", "newtonian": True, "incompressible": True,
            "straight_circular_tube": True, "minor_losses_present": False,
            "density": {"value": 998, "unit": "kg/m3", "evidence": "998 kg/m3", "uncertainty_relative": None},
            "dynamic_viscosity": {"value": 1, "unit": "mPa*s", "evidence": "1 mPa s", "uncertainty_relative": None},
            "tube_length": {"value": 5, "unit": "cm", "evidence": "5 cm", "uncertainty_relative": None},
            "inner_diameter": {"value": 100, "unit": "um", "evidence": "100 um", "uncertainty_relative": None},
            "volumetric_flow_rate": {"value": 10, "unit": "uL/min", "evidence": "10 uL/min", "uncertainty_relative": None},
        }
        mocked_response = io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(extracted)}}]}).encode())
        env = {"LLM_NAME": "swiss-ai/Apertus-v1.5-8B", "LLM_BASE_URL": "https://example.org/v1", "LLM_API_KEY": "test-only-key"}
        with patch.dict(os.environ, env), patch("src.apertus_client.urllib.request.urlopen", return_value=mocked_response):
            result = analyze_question(question)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["results"]["pressure_drop_pa"], 3395.3054526, places=4)
        self.assertNotIn("test-only-key", json.dumps(result))

    def test_client_failure_on_invalid_case_is_scored_as_error(self):
        case = {"id": "offline", "class": "invalid", "question": "gas",
                "expected_status": "refused", "expected_pressure_drop_pa": None,
                "expected_reynolds": None}
        with patch("src.apertus_client.extract_quantities", side_effect=ExtractionError("offline")):
            row = _prediction(case, "workflow")
        self.assertEqual(row["status"], "error")
        self.assertFalse(row["decision_correct"])
        self.assertFalse(row["unsafe_acceptance"])


if __name__ == "__main__":
    unittest.main()
