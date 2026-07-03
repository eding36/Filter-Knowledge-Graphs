"""Central configuration for the Filter-KG experiments.

Connection details are read from environment variables so credentials never
live in source control. Sensible localhost defaults are kept for convenience.
All output paths are resolved relative to this file, so the experiments work
regardless of the current working directory or where the repo is checked out.
"""

import os
from pathlib import Path

# Repository root (the directory containing this file).
PROJECT_ROOT = Path(__file__).resolve().parent

# --- Neo4j connection -------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# --- Output files -----------------------------------------------------------
THERAPEUTIC_TRIPLES_CSV = PROJECT_ROOT / "therapeutic_triples_name_id.csv"
THERAPEUTIC_DOUBLETS_CSV = PROJECT_ROOT / "therapeutic_doublets_name_id.csv"
TRAINING_SET_CSV = PROJECT_ROOT / "training_set.csv"
EXTERNAL_SET_CSV = PROJECT_ROOT / "external_set.csv"

# Reproducible train/external split.
RANDOM_STATE = 42
TRAIN_FRACTION = 0.8
