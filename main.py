"""Run knowledge-graph filtering experiments against a Neo4j database.

Usage:
    python main.py --experiment 1     # filter "good" (curated) knowledge sources
    python main.py --experiment 2     # filter "bad" (uncurated) knowledge sources
    python main.py --experiment 3     # remove same-type (drug-drug/target-target/disease-disease) edges
    python main.py --experiment 4     # data-leakage split (drug-disease doublets)

Connection details come from the NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD
environment variables (see config.py for defaults).

"""

import argparse

import pandas as pd
from neo4j import GraphDatabase

import config
from functions.functions_for_filtering_uncurated_sources import (
    remove_low_correlated_string_ppi_edges,
    remove_text_mining_edges,
    remove_tiga_edges,
    remove_hetionet_edges,
)
from functions.functions_for_filtering_curated_sources import (
    remove_gwas_catalog_edges,
    remove_intact_edges,
)
from functions.functions_for_filtering_dd_tt_cc import (
    remove_drug_drug_edges,
    remove_target_target_edges,
    remove_disease_disease_edges,
)
from functions.data_leakage_exp_functions import exp_1, exp_2, exp_2_d_d


def connect_to_neo4j():
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        database=config.NEO4J_DATABASE,
    )
    driver.verify_connectivity()
    print("successfully connected to neo4j db")
    return driver


def remove_island_nodes(driver):
    """Delete nodes left with no relationships after edge filtering."""
    with driver.session() as session:
        session.run(
            """
            MATCH (n)
            WHERE NOT (n)--()
            DELETE n
            """
        )
    print("Nodes with no connections removed successfully")


def fetch_therapeutic_triples(driver):
    """Export the remaining therapeutic drug-target-disease triples to CSV."""
    query = """
    MATCH (c:`biolink:ChemicalEntity`)-[r0:`biolink:directly_physically_interacts_with`]-(g:`biolink:GeneOrGeneProduct`)-[r1]-(d:`biolink:DiseaseOrPhenotypicFeature`),
          (c)-[r2:`biolink:treats`]-(d)
    WHERE properties(c)["CHEBI_ROLE_pharmaceutical"] IS NOT NULL
      AND properties(r2)["primary_knowledge_source"] IN ["infores:drugcentral"]
    RETURN DISTINCT c.name, c.id, g.name, g.id, d.name, d.id
    """
    with driver.session() as session:
        result = session.run(query)
        data = [
            (r["c.name"], r["c.id"], r["g.name"], r["g.id"], r["d.name"], r["d.id"])
            for r in result
        ]
    df = pd.DataFrame(
        data,
        columns=["drug_name", "drug_id", "target_name", "target_id", "disease_name", "disease_id"],
    )
    df.to_csv(config.THERAPEUTIC_TRIPLES_CSV)
    print(f"{len(df)} therapeutic triples exported to {config.THERAPEUTIC_TRIPLES_CSV}")


def experiment_1(driver):
    """Filter high quality (curated) knowledge sources, then export triples."""
    remove_hetionet_edges(driver)
    remove_intact_edges(driver)
    remove_gwas_catalog_edges(driver)
    remove_island_nodes(driver)
    fetch_therapeutic_triples(driver)


def experiment_2(driver):
    """Filter uncurated knowledge sources, then export triples."""
    remove_text_mining_edges(driver)
    remove_tiga_edges(driver)
    remove_low_correlated_string_ppi_edges(driver)
    remove_island_nodes(driver)
    fetch_therapeutic_triples(driver)


def experiment_3(driver):
    """Remove same-type (drug-drug, target-target, disease-disease) edges."""
    remove_drug_drug_edges(driver)
    remove_target_target_edges(driver)
    remove_disease_disease_edges(driver)
    remove_island_nodes(driver)
    fetch_therapeutic_triples(driver)


def experiment_4(driver):
    """Data-leakage experiment: split drug-disease doublets and remove the external set."""
    exp_2_d_d(driver)
    remove_island_nodes(driver)


EXPERIMENTS = {
    1: experiment_1,
    2: experiment_2,
    3: experiment_3,
    4: experiment_4,
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "-e",
        "--experiment",
        type=int,
        choices=sorted(EXPERIMENTS),
        required=True,
        help="Which experiment to run (1-4).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    driver = connect_to_neo4j()
    try:
        print(f"Running experiment {args.experiment}...")
        EXPERIMENTS[args.experiment](driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()


###IMPORTANT! RUN THIS CYPHER QUERY IN NEO4J BROWSER TO EXPORT GRAPH TO CSV
##FIRST, you must make an empty apoc.conf file in the directory (THIS IS ONLY FOR MAC):
# Neo4J Desktop/Application/relate-data/dmbss/your_dbms_version/conf/
# with the line: apoc.export.file.enabled=true
##You must also change the dbms_total_max_transaction_size from 1G to 20G

"""
CALL apoc.export.csv.query(
    "
    MATCH (n) RETURN DISTINCT n.id AS id, labels(n) AS category, n.name AS name",
    "graph_nodes.tsv",
    {useTypes: true, quotes: false, delim: "\t"}
)
"""
""""
CALL apoc.export.csv.query(
    "
    MATCH (n)-[r]->(m)
    RETURN n.id AS source, m.id AS target, type(r) AS predicate
    ",
    "graph_edges.tsv",
    {useTypes: true, quotes: false, delim: "\t"}
)
"""
###MOVE TXT FILES FROM:
# Neo4j Desktop/Application/relate-data/dbmss/dbms-<id>/import
### TO:
# this directory


### SECONDARY / OPTIONAL GRAPH-ENRICHMENT HELPERS ###
# These are not wired into any experiment above; kept for reference.

def get_unique_entities(df, entity_cols):
    unique_entities = df.drop_duplicates(subset=entity_cols, keep="first")
    return list(unique_entities[entity_cols].itertuples(index=False, name=None))


def remove_subclass_edges(driver, batch_size=10000):
    with driver.session() as session:
        while True:
            cypher = """
                MATCH ()-[r]->()
                WHERE type(r) = "biolink:subclass_of"
                WITH r LIMIT $batch_size
                DELETE r
                RETURN count(r) AS deleted_count
            """
            result = session.run(cypher, batch_size=batch_size)
            deleted_count = result.single()["deleted_count"]
            print(f"Deleted {deleted_count} relationships in this batch.")
            if deleted_count == 0:
                break
    print("All subclass_of edges deleted.")


def create_nodes(driver, node_tuples, node_type):
    with driver.session() as session:
        for node_id, node_name in node_tuples:
            cypher = f"""
                MERGE (n:`{node_type}` {{id: $node_id}})
                ON CREATE SET n.name = $node_name
            """
            session.run(cypher, node_id=node_id, node_name=node_name)
    print(f"{node_type} nodes checked and created as necessary.")


def create_relationships(driver, df, node1_label, node2_label, rel_type,
                         node1_id_field, node2_id_field, knowledge_source):
    with driver.session() as session:
        for _, row in df.iterrows():
            cypher = f"""
                MATCH (n1:`{node1_label}` {{id: $node1_id}})
                MATCH (n2:`{node2_label}` {{id: $node2_id}})
                MERGE (n1)-[r:`{rel_type}`]->(n2)
                ON CREATE SET r.primary_knowledge_source = $knowledge_source
            """
            session.run(
                cypher,
                node1_id=row[node1_id_field],
                node2_id=row[node2_id_field],
                knowledge_source=knowledge_source,
            )
    print(f"{rel_type} relationships created from DataFrame successfully.")