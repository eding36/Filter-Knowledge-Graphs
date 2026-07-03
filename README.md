# Filter-KG-Experiments

Runs filtering protocols on a Neo4j biomedical knowledge graph. Each experiment
deletes a category of edges (or holds out a validation split) before embedding the graph, as to evaluate the effect of edge filtering on transfer learning tasks such as edge prediction (a classification task).

# Motivation
Graph embedding methods such as Node2Vec (n2v) and GraphSAGE are extremely effective in learning the relationship between nodes. Thus, in drug repurposing applications where biomedical knowledge graphs are embedded, these methods may lead to data leakage in which the embeddings already contain information about drug-disease relationships. We hypothesize that this may overinflate model performance in transfer learning tasks such as predicting whether a drug is an indication or a contraindication for a disease. 

Each experiment generates a filtered subgraph that will be embedded, as well as drug-disease combinations that will be used as the training set for downstream classification tasks (e.g. predicting whether a drug-disease edge is a contraindication or an indication.)

Experiments 1 and 2 test the effect on data source quality on downstream model performance on drug repurposing tasks

Experiments 3 and 4 examine whether including drug, target, and disease relationships in the graph prior to graph embedding overinflates the model performance on downstream drug repurposing tasks.

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
python main.py --experiment 1   # filter out good (curated) knowledge sources
python main.py --experiment 2   # filter out bad (uncurated) knowledge sources
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

