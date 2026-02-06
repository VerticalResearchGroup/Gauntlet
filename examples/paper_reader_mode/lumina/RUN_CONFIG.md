# Gauntlet — Run Configuration

- **Model:** `claude-opus-4-5-20251101`
- **Personas:** reading_assistant/dr_microarch_reader, reading_assistant/prof_workloads_reader, reading_assistant/prof_simtools_reader, reading_assistant/chief_architect
- **Runs per persona:** 1
- **Temperatures:** [0.3]
- **Synthesis temperature:** 0.5
- **Total expert reviews:** 4
- **Total syntheses:** 1

## Temperature → run mapping

- `run_1` → temperature **0.3**

## Synthesis folder naming

`silas_<a>__amara_<b>__julian_<c>` means the synthesiser received
silas `run_<a>`, amara `run_<b>`, julian `run_<c>`.

Each folder contains `SYNTHESIS.md` **plus** copies of the three
source reviews that produced it — no need to cross-reference.
