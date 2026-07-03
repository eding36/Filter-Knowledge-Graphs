# Filter-KG-Experiments

Runs filtering protocols on a Neo4j biomedical knowledge graph. Each experiment
deletes a category of edges (or holds out a validation split) so that downstream
link-prediction models can be trained/evaluated on a cleaned graph.

Experiments are described in the
[project slides](https://docs.google.com/presentation/d/1cqrqE6FMP8mbnYF-cO_YjaeQHnS2aoX7GpGtFm-L2F4/edit).

## Setup

```bash
pip install -r requirements.txt
```

Connection settings are read from environment variables (defaults target a local
Neo4j Desktop instance):

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

The database must have the [APOC](https://neo4j.com/labs/apoc/) plugin
installed (the batched deletes use `apoc.periodic.iterate`).

## Running an experiment

```bash
python main.py --experiment 1   # filter good (curated) knowledge sources
python main.py --experiment 2   # filter bad (uncurated) knowledge sources
python main.py --experiment 3   # remove same-type (drug-drug/target-target/disease-disease) edges
python main.py --experiment 4   # data-leakage split of drug-disease doublets
```

Outputs (`therapeutic_triples_name_id.csv`, `training_set.csv`,
`external_set.csv`, ...) are written to the repository root.

## Exporting the filtered graph

After running an experiment, export the graph to TSV from the Neo4j browser.
See the commented Cypher blocks at the bottom of [main.py](main.py) for the
`apoc.export.csv.query` calls and the required `apoc.conf` / transaction-size
setup.

## Layout

| Path | Purpose |
| --- | --- |
| `main.py` | Entry point; selects and runs an experiment. |
| `config.py` | Connection + output-path configuration. |
| `functions/functions_for_filtering_curated_sources.py` | Remove curated sources (intact, gwas catalog). |
| `functions/functions_for_filtering_uncurated_sources.py` | Remove uncurated sources (text mining, tiga, low-confidence STRING, hetionet). |
| `functions/functions_for_filtering_dd_tt_cc.py` | Remove same-type edges (drug-drug, target-target, disease-disease). |
| `functions/data_leakage_exp_functions.py` | Train/external splits + external-edge removal. |