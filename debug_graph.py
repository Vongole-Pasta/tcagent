import os
import sys
from neo4j import GraphDatabase

# Adjust path to import local modules if needed
sys.path.append(os.getcwd())

from config import Config

def debug_graph():
    config = Config()
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )

    method_name = "saveProblem" # The one we used in verification

    with driver.session() as session:
        # 1. Find a target method ID
        print(f"--- Searching for method: {method_name} ---")
        result = session.run("MATCH (m:METHOD) WHERE m.name CONTAINS $name RETURN elementId(m) as id, m.name as name, m.id as original_id LIMIT 1", name=method_name)
        record = result.single()
        
        if not record:
            print("Target method not found.")
            return

        target_id = record['id']
        original_id = record.get('original_id')
        print(f"Found Target: {record['name']} (Neo4j ID: {target_id}, App ID: {original_id})")

        # 2. Check DIRECT Callers (Simple check)
        print("\n--- Checking Direct CALLERS (Upstream) ---")
        query_direct = """
        MATCH (caller)-[r:CALLS]->(m:METHOD)
        WHERE elementId(m) = $id
        RETURN caller.name as caller, type(r) as rel, m.name as callee
        """
        result = session.run(query_direct, id=target_id)
        callers = list(result)
        if callers:
            for c in callers:
                print(f"{c['caller']} -[:{c['rel']}]-> {c['callee']}")
        else:
            print("No direct callers found.")

        # 3. Test the UPSTREAM Query
        print("\n--- Testing GET_UPSTREAM_IMPACT Query ---")
        query_upstream = """
        MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
        WHERE (elementId(target) = $id OR target.id = $id)
        RETURN path, length(path) as len
        LIMIT 5
        """
        # Try with elementId first
        result = session.run(query_upstream, id=target_id)
        paths = list(result)
        print(f"Found {len(paths)} paths.")
        for p in paths:
            path = p['path']
            print(f"Path length: {p['len']}")
            for node in path.nodes:
                print(f" - {node.get('name')} ({node.element_id})")

    driver.close()

if __name__ == "__main__":
    debug_graph()
