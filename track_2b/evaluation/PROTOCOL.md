# Frozen evaluation protocol

The benchmark in `../data/holdout.jsonl` was written before the first Apertus model run. Keep it unchanged when tuning prompts or code. Its SHA-256 digest is `86a63a7e688b3329bcde6df51d765d624b75b43bdd58326ce8fcaed4fd6c4a1d`; verify it with every result. The examples are synthetic questions with analytical reference values, not independent physical measurements. The implementation was inspected against these questions before live inference, so this set is a frozen regression benchmark, **not** an independent holdout for a generalization claim. A second case set authored after the code is frozen is needed for that claim.

## Scope and references

The numerical target is the Hagen–Poiseuille pressure drop for a straight circular tube with an incompressible Newtonian liquid and fully developed laminar flow: `Δp = 128 μ L Q / (π D⁴)`. The Reynolds number uses `Re = 4 ρ Q / (π μ D)`. The conservative applicability rule is `Re < 2300`. NIST documents the capillary equation and this approximate transition threshold in [NBS IR 74-620](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nbsir74-620.pdf) and [Technical Note 831](https://nvlpubs.nist.gov/nistpubs/Legacy/TN/nbstechnicalnote831.pdf). The entrance-length screen `L_e ≈ 0.05 Re D` is an engineering approximation supported by [published flow research](https://www.jstage.jst.go.jp/article/jcej1968/5/2/5_2_132/_pdf); report it as a screening rule, not a validated measurement.

## Predeclared scores

Run each of the 12 frozen prompts once through the complete Apertus extraction and deterministic decision path. Report (1) exact accept/refuse accuracy, (2) unsafe acceptances among the eight out-of-scope prompts, (3) relative errors in `Δp` and `Re` for the four valid prompts, and (4) latency and request count. An unsafe acceptance is the most serious error. The target for this proof of concept is zero unsafe acceptances and at least three of four valid cases calculated within 2% of the analytical targets. Report every failure, including parse/API errors, rather than omitting it.

Run an independent baseline with the same Apertus model asked to answer each question directly without the deterministic calculator. Use the same prompts and score its decisions and numbers with the same rules. Do not compare against a different model or hand-select successful outputs.

There is no claim of calibration to measured pressure drops or performance outside the stated physical regime. Real fluid-property measurements and external validation are future work.
