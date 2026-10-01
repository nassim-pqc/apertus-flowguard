# Track 2 B: Own Project

Bring your own idea and build a working Apertus prototype that tackles a problem you care about — any domain, any use case. The project must be new, started within the hackathon period.

Submissions must use the Apertus model family.
For Track 2 this means that submitted solutions must be built with Apertus. Other open-weights models can be used to support development, e.g. as automatic judges during evaluation. Their role must be clearly described in the submission report.

💬 In case you have questions, join the conversation on [Discord](https://discord.gg/hack-apertus) or send an email to “hello@hackapertus.ch”

---

## 🔧 Resources & Tools

Check our resources & tools page for detailed information:
https://hackapertus.notion.site/resources-tools

| Models           | URL                                      |
|------------------|------------------------------------------|
| Apertus v1.5 8B  | [huggingface.co/swiss-ai/Apertus-v1.5-8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)  |
| Apertus v1.5 70B | [huggingface.co/swiss-ai/Apertus-v1.5-70B](https://huggingface.co/swiss-ai/Apertus-v1.5-70B) |


## Target architecture (mandatory)

Whatever you build in Track 2B must be deployable in one of these three architectures:

- **a) On-premise** — on the organisation's own infrastructure, under its own administration.
- **b) Air-gapped** — with no external network connection at runtime.
- **c) Sovereign Swiss cloud** — on a cloud platform operated in Switzerland, under Swiss jurisdiction, with Swiss data residency.

---

## Data

The `data/` directory must not exceed 100 MB.

---

## 📦 Submission Requirements & Deliverables

❗️ Submissions are not handled on Devpost but via this URL only:
http://hackapertus.ch/online-hack/submissions

The submission must:
1. follow the template repo and include all prerequisite files and definitions
2. follow the specified input/output formats
3. run in a Docker container, launched with `make run` from the root of the project
4. run end-to-end when judges try to run it

### Git repo (URL)
- Create your repo from this template (**Use this template**) and work in the `track_2b/` challenge directory. Delete the other track challenge directories.
- Keep `track_2b/` as it is: don't rename it or move its files.
- Set the repo to PUBLIC (Settings --> Collaborators --> Manage Visibility)
- Submit the URL of YOUR Git repo.

### Technical Report (pdf)
- Update [technical_report.md](technical_report.md) in this repository with all the details for your submission.
- Upload a pdf of your technical report to this directory, named as `TeamName_Report.pdf`.
- Format: pdf, max. 6 pages
- Submit the pdf of the technical report.

### Demo video (URL)
- Max. 2 min demo video of your prototype

### Dataset (URL) - optional, depending on your project
Submitted datasets must comply with our guidelines for responsibly sourced datasets.

- Create a user account on Hugging Face
- Clone our dataset template on Hugging Face: https://huggingface.co/datasets/HackApertus/online_hack_template
- Complete the dataset card with all required information
- Upload your dataset. It should consist of the following components:
    - evaluation dataset (i.e. individual test cases)
    - model response dataset (i.e. the model response to each test case)
    - metadata file (i.e. additional information about each test case; where relevant, this file must contain instance-level licensing information)
- Make sure your dataset access control is set to PUBLIC
- Provide the URL of _your_ data set


---

## ⚖️ Judging Criteria

1. Purposeful use of AI
2. Technical rigour
3. Value, cost & scalability
4. Sovereign deployability
5. Implementation feasibility

Judges use a Scale 0–5 per dimension.

---

## Support

**Licensing requirements**
Please check our Terms & Conditions (6. What you build is open source):
https://hackapertus.ch/terms-and-conditions

## FAQ
💡 https://hackapertus.ch/faq

## Contact
💬 In case you have questions, join the conversation on Discord or send an email to “hello@hackapertus.ch”

---

## Our project: Apertus FlowGuard

FlowGuard estimates the viscous pressure drop in a **straight circular laboratory capillary** carrying a **Newtonian incompressible liquid** at steady, laminar, developed flow. It is an educational screening tool, **not certified engineering design**.

The purposeful use of Apertus 1.5 is narrow: it extracts explicit numbers, units and stated assumptions from a French or English question. Deterministic Python then validates each unit and assumption, calculates Reynolds number, rejects cases outside the model, and evaluates the Hagen–Poiseuille equation. The model never supplies physical properties from memory or performs the final calculation.

### Run

From this directory (or the repository root):

```sh
make run
```

This builds a small Python Docker image and runs a **synthetic structured demo**, with no network request. It prints a JSON result that includes the equation, SI input values, provenance and limitations. To use Apertus, set `LLM_NAME` to an Apertus v1.5 model identifier, `LLM_BASE_URL` to an OpenAI-compatible endpoint base URL ending in `/v1`, and `LLM_API_KEY` through your private environment. Then:

```sh
FLOWGUARD_QUESTION='Liquide newtonien incompressible dans un tube droit circulaire sans pertes singulières: densité 998 kg/m3, viscosité 1 mPa*s, longueur 5 cm, diamètre intérieur 100 um, débit 10 uL/min.' make run
```

The question route fails closed if the endpoint, required remote credential, extraction, explicit physical assumptions or units are missing. An unauthenticated loopback inference server does not need `LLM_API_KEY`; credentials are never printed or saved. Remote endpoints must use HTTPS. The endpoint itself must be hosted on an approved on-premise or Swiss-sovereign deployment for a qualifying deployment; this code does not establish the provider's jurisdiction.

For the [CSCS inference service](https://docs.cscs.ch/services/inference/api/), the documented base URL is `https://api.inference.cscs.ch/v1` and a documented model identifier is `swiss-ai/Apertus-v1.5-70B`. Obtain access through the event's official process, then set the key privately in your environment. The public Docker demo above does not call this service.

For direct deterministic input, set `FLOWGUARD_INPUT_JSON` to a JSON object with the keys listed in `src/flowguard.py`. Supported units: density `kg/m3` or `g/cm3`; dynamic viscosity `Pa*s`, `Pa s`, `mPa*s`, `mPa s` or `cP`; length `m`, `cm` or `mm`; inner diameter `m`, `mm` or `um`; flow rate `m3/s`, `L/s`, `L/min`, `mL/s`, `mL/min` or `uL/min`. Unicode micro and middle-dot variants are accepted. Natural-language questions must explicitly say the diameter is **internal**, the tube is straight and circular, the liquid is Newtonian and incompressible, and fittings/minor losses are absent. Contradictions or ambiguous descriptions are refused.

### Output and refusal policy

`status=ok` includes pressure loss in Pa and kPa, Reynolds number, velocity, entrance-length estimate and a traceable equation. `status=refused` has a `reason_code`, including gas/unknown fluid, non-Newtonian or unknown behavior, noncircular/unknown geometry, minor losses, missing measurements, unsupported units, `Re >= 2300`, or a capillary shorter than the estimated entrance length. An uncertainty interval is emitted only when all five inputs carry explicit relative uncertainties; it is a deterministic input-bound interval, **not a calibrated prediction interval**. No measurement uncertainty or model error is invented.

Run `make test` for the targeted numerical and refusal checks. The separate `evaluation/` directory contains the locked benchmark and scoring protocol.

### Sources and licence

The governing pressure relation and laminar threshold come from the [NBS/NIST technical report](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nbsir74-620.pdf); the entrance-length screening correlation is documented in [Penn State fluid mechanics teaching material](https://www.me.psu.edu/cimbala/me320web_Spring_2015/Lectures/Tablet_PC_notes/ME320_Lecture_20.pdf). The source code is Apache 2.0 licensed in the repository root. No Jarvis code, private data or API key is included.
