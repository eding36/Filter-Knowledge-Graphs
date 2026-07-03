"""Filters for uncurated / lower-confidence knowledge sources."""


def _delete_edges_where(driver, where_clause, message, batch_size=10000, parallel=True):
    """Batch-delete relationships matching a WHERE clause via apoc.periodic.iterate."""
    cypher = f"""
        CALL apoc.periodic.iterate(
            "MATCH ()-[r]->() WHERE {where_clause} RETURN r",
            "DELETE r",
            {{ batchSize: $batch_size, parallel: {str(parallel).lower()} }}
        )
        YIELD batches, total
        RETURN batches, total;
    """
    with driver.session() as session:
        session.run(cypher, batch_size=batch_size)
    print(message)


def remove_text_mining_edges(driver):
    _delete_edges_where(
        driver,
        "r.agent_type = 'text_mining_agent'",
        "Text mined edges removed successfully",
    )


def remove_low_correlated_string_ppi_edges(driver, min_combined_score=160):
    # Parallel deletion is unsafe when the same node can be touched concurrently;
    # keep it serial. min_combined_score is interpolated (not a Cypher param)
    # because it lives inside the apoc.periodic.iterate query string.
    _delete_edges_where(
        driver,
        f'toInteger(properties(r)["Combined_score"]) < {int(min_combined_score)} '
        'AND properties(r)["primary_knowledge_source"] = "infores:string"',
        "low confidence string ppi scores removed.",
        parallel=False,
    )


def remove_hetionet_edges(driver):
    _delete_edges_where(
        driver,
        "properties(r)['primary_knowledge_source'] = 'infores:hetionet'",
        "hetionet edges removed successfully",
    )


def remove_tiga_edges(driver):
    _delete_edges_where(
        driver,
        "properties(r)['primary_knowledge_source'] = 'infores:tiga'",
        "tiga edges removed successfully",
    )
