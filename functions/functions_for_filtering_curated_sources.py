"""Filters for curated knowledge sources."""


def _batch_iterate(driver, match_return, message, batch_size=10000, parallel=True):
    cypher = f"""
        CALL apoc.periodic.iterate(
            "{match_return}",
            "DELETE r",
            {{ batchSize: $batch_size, parallel: {str(parallel).lower()} }}
        )
        YIELD batches, total
        RETURN batches, total;
    """
    with driver.session() as session:
        session.run(cypher, batch_size=batch_size)
    print(message)


def remove_intact_edges(driver):
    _batch_iterate(
        driver,
        "MATCH ()-[r]->() WHERE properties(r)['primary_knowledge_source'] = 'infores:intact' RETURN r",
        "intact edges removed successfully",
    )


def remove_gwas_catalog_edges(driver):
    _batch_iterate(
        driver,
        "MATCH (c1:`biolink:ChemicalEntity`)-[r]-(c2:`biolink:ChemicalEntity`) WHERE c1 <> c2 RETURN r",
        "gwas catalog edges removed successfully",
    )
