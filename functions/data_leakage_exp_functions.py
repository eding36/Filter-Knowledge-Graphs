"""Data-leakage experiments.

Each experiment samples therapeutic drug-(target-)disease relationships from the
graph, splits them into a training set and a held-out external set, and then
removes the external set's relationships from the graph so that a model trained
on the remaining graph cannot "see" the held-out examples.

Reference slides:
https://docs.google.com/presentation/d/1cqrqE6FMP8mbnYF-cO_YjaeQHnS2aoX7GpGtFm-L2F4/edit#slide=id.g32f6b7e4dad_0_48

"""

import pandas as pd

from config import (
    THERAPEUTIC_TRIPLES_CSV,
    THERAPEUTIC_DOUBLETS_CSV,
    TRAINING_SET_CSV,
    EXTERNAL_SET_CSV,
    RANDOM_STATE,
    TRAIN_FRACTION,
)

TRIPLES_QUERY = """
MATCH (c:`biolink:ChemicalEntity`)-[r0:`biolink:directly_physically_interacts_with`]-(g:`biolink:GeneOrGeneProduct`)-[r1]-(d:`biolink:DiseaseOrPhenotypicFeature`),
      (c)-[r2:`biolink:treats`]-(d)
WHERE properties(c)["CHEBI_ROLE_pharmaceutical"] IS NOT NULL
  AND properties(r2)["primary_knowledge_source"] IN ["infores:drugcentral"]
RETURN DISTINCT c.name, c.id, g.name, g.id, d.name, d.id
"""

DOUBLETS_QUERY = """
MATCH (c:`biolink:ChemicalEntity`)-[r2:`biolink:treats`]-(d:`biolink:DiseaseOrPhenotypicFeature`)
WHERE properties(c)["CHEBI_ROLE_pharmaceutical"] IS NOT NULL
  AND properties(r2)["primary_knowledge_source"] IN ["infores:drugcentral"]
  AND size((c)--()) > 1
  AND size((d)--()) > 1
RETURN DISTINCT c.name, c.id, d.name, d.id
"""


def _fetch_triples(driver):
    """Return the therapeutic drug-target-disease triples as a DataFrame."""
    with driver.session() as session:
        result = session.run(TRIPLES_QUERY)
        data = [
            (r["c.name"], r["c.id"], r["g.name"], r["g.id"], r["d.name"], r["d.id"])
            for r in result
        ]
    return pd.DataFrame(
        data,
        columns=["drug_name", "drug_id", "target_name", "target_id", "disease_name", "disease_id"],
    )


def _remove_drug_disease_edges(driver, df_external):
    """Delete every relationship between each (drug, disease) pair in the external set."""
    with driver.session() as session:
        for _, row in df_external.iterrows():
            session.run(
                """
                MATCH (c:`biolink:ChemicalEntity` {id: $drug_id}),
                      (d:`biolink:DiseaseOrPhenotypicFeature` {id: $disease_id})
                MATCH (c)-[rel]-(d)
                DELETE rel
                """,
                drug_id=row["drug_id"],
                disease_id=row["disease_id"],
            )
    print("external set drug-disease relations removed")


def _report_split(df_model, df_external):
    print("Dataset for model development DataFrame shape:", df_model.shape)
    print("Dataset for external validation DataFrame shape:", df_external.shape)


def exp_1(driver):
    """Split at the (drug, disease) group level so a pair is never in both sets."""
    df = _fetch_triples(driver)
    df.to_csv(THERAPEUTIC_TRIPLES_CSV)
    print("total triples exported")

    grouped = (
        df.groupby(["drug_name", "drug_id", "disease_name", "disease_id"])
        .apply(lambda subdf: list(zip(subdf["target_name"], subdf["target_id"])))
        .reset_index(name="genes")
    )
    grouped = grouped.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    split_index = int(TRAIN_FRACTION * len(grouped))
    training_groups = grouped.iloc[:split_index]
    external_groups = grouped.iloc[split_index:]

    def expand_groups(df_groups):
        rows = []
        for _, row in df_groups.iterrows():
            for gene_name, gene_id in row["genes"]:
                rows.append(
                    (row["drug_name"], row["drug_id"], row["disease_name"],
                     row["disease_id"], gene_name, gene_id)
                )
        return pd.DataFrame(
            rows,
            columns=["drug_name", "drug_id", "disease_name", "disease_id", "gene_name", "gene_id"],
        )

    training_df = expand_groups(training_groups)
    external_df = expand_groups(external_groups)

    # Verify no (drug, disease) pair leaks across the split.
    keys = ["drug_name", "drug_id", "disease_name", "disease_id"]
    overlap = pd.merge(
        training_df[keys].drop_duplicates(),
        external_df[keys].drop_duplicates(),
        on=keys,
        how="inner",
    )
    print(f"Overlap in {tuple(keys)}: {len(overlap)} (should be 0)")
    _report_split(training_df, external_df)

    training_df.to_csv(TRAINING_SET_CSV, index=False)
    external_df.to_csv(EXTERNAL_SET_CSV, index=False)
    print("external set and training set fetched and exported")

    _remove_drug_disease_edges(driver, external_df)


def exp_2(driver):
    """Row-level 80/20 split; removes drug-disease, drug-target and target-disease edges."""
    df = _fetch_triples(driver)
    df.to_csv(THERAPEUTIC_TRIPLES_CSV)
    print("total triples exported")

    df = df.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    split_index = int(len(df) * TRAIN_FRACTION)
    df_model = df.iloc[:split_index]
    df_external = df.iloc[split_index:]
    _report_split(df_model, df_external)

    df_model.to_csv(TRAINING_SET_CSV, index=False)
    df_external.to_csv(EXTERNAL_SET_CSV, index=False)
    print("external set and training set fetched and exported")

    with driver.session() as session:
        for _, row in df_external.iterrows():
            session.run(
                """
                MATCH (c:`biolink:ChemicalEntity` {id: $drug_id}),
                      (d:`biolink:DiseaseOrPhenotypicFeature` {id: $disease_id}),
                      (g:`biolink:GeneOrGeneProduct` {id: $target_id})
                MATCH (c)-[rel1]-(d), (c)-[rel2]-(g), (g)-[rel3]-(d)
                DELETE rel1, rel2, rel3
                """,
                drug_id=row["drug_id"],
                disease_id=row["disease_id"],
                target_id=row["target_id"],
            )
    print("external set drug-disease, drug-target, and target-disease relations removed")


def exp_2_d_d(driver):
    """Drug-disease doublets only; row-level split, removes drug-disease edges."""
    with driver.session() as session:
        result = session.run(DOUBLETS_QUERY)
        data = [(r["c.name"], r["c.id"], r["d.name"], r["d.id"]) for r in result]
    df = pd.DataFrame(data, columns=["drug_name", "drug_id", "disease_name", "disease_id"])
    df.to_csv(THERAPEUTIC_DOUBLETS_CSV)
    print("doublets exported")

    df = df.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    split_index = int(len(df) * TRAIN_FRACTION)
    df_model = df.iloc[:split_index]
    df_external = df.iloc[split_index:]
    _report_split(df_model, df_external)

    df_model.to_csv(TRAINING_SET_CSV, index=False)
    df_external.to_csv(EXTERNAL_SET_CSV, index=False)
    print("external set and training set fetched and exported")

    _remove_drug_disease_edges(driver, df_external)


###TO CHECK NO DRUGS, DISEASES OR TARGETS WERE ISLAND NODES AFTER EDGE REMOVAL, RUN THIS AFTER MOVING therapeutic_triples_name_id.csv into your dbms import folder:
"""/Users/eding36/Library/Application Support/Neo4j Desktop/Application/relate-data/dbmss/DBMS_VERSION_HERE/import"""

"""
LOAD CSV WITH HEADERS FROM 'file:///therapeutic_triples_name_id.csv' AS row
WITH collect(row) AS all_rows
WITH all_rows, size(all_rows) AS total_rows
UNWIND all_rows AS row
MATCH (c:`biolink:ChemicalEntity` {id: row.drug_id}),
      (d:`biolink:DiseaseOrPhenotypicFeature` {id: row.disease_id}),
      (g:`biolink:GeneOrGeneProduct` {id: row.target_id})
WITH total_rows, count(*) AS matched_rows
RETURN
  total_rows,
  matched_rows,
  CASE
    WHEN matched_rows = total_rows THEN 'All CSV IDs exist in the graph'
    ELSE 'Some CSV IDs are missing in the graph'
  END AS status
"""
