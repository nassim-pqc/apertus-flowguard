# Synthetic benchmark cases

`holdout.jsonl` contains 12 original questions written for this project: four in-scope capillary calculations and eight cases where the bounded model should refuse. No personal information, third-party dataset, or measured experiment is included. The numerical targets were independently calculated from the equations in the [evaluation protocol](../evaluation/PROTOCOL.md).

The cases were frozen before any Apertus model evaluation. The implementation was inspected against their wording before a live model run, so they serve as a regression benchmark rather than an independent holdout for a generalization claim. They may be read by judges, but they must not be used to tune a prompt or selection rule after evaluation. The SHA-256 digest is recorded in the protocol and checked by `evaluation/evaluate.py`.

Dataset license: [CDLA-Permissive-2.0](https://cdla.dev/permissive-2-0/), following the Hack Apertus data terms. All case text and metadata were authored for this entry.
