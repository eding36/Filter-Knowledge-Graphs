"""Filters that remove edges between two nodes of the same biolink type
(drug-drug, target-target, disease-disease)."""


def _remove_same_type_edges(driver, label, message, batch_size=10000):
    cypher = f"""
        CALL apoc.periodic.iterate(
            "MATCH (a:`{label}`)-[r]-(b:`{label}`) WHERE a <> b RETURN r",
            "DELETE r",
            {{ batchSize: $batch_size, parallel: false }}
        );
    """
    with driver.session() as session:
        session.run(cypher, batch_size=batch_size)
    print(message)


def remove_drug_drug_edges(driver):
    _remove_same_type_edges(
        driver, "biolink:ChemicalEntity", "drug-drug edges removed successfully"
    )


def remove_target_target_edges(driver):
    _remove_same_type_edges(
        driver, "biolink:GeneOrGeneProduct", "target-target edges removed successfully"
    )


def remove_disease_disease_edges(driver):
    _remove_same_type_edges(
        driver, "biolink:DiseaseOrPhenotypicFeature", "disease-disease edges removed successfully"
    )
