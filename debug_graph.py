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

    with driver.session() as session:
        print("\n--- Node Counts ---")
        
        # Total Methods
        result = session.run("MATCH (m:METHOD) RETURN count(m) as count")
        total = result.single()['count']
        print(f"Total METHOD nodes in DB: {total}")

        # Endpoints (Non-empty)
        result = session.run("MATCH (m:METHOD) WHERE m.endpoint IS NOT NULL AND m.endpoint <> '' RETURN count(m) as count")
        endpoints = result.single()['count']
        print(f"METHOD nodes with meaningful endpoint: {endpoints}")

        # Empty String Endpoints
        result = session.run("MATCH (m:METHOD) WHERE m.endpoint = '' RETURN count(m) as count")
        empty_endpoints = result.single()['count']
        print(f"METHOD nodes with empty endpoint: {empty_endpoints}")
        
        # Check Status Values
        result = session.run("MATCH (m:METHOD) WHERE m.status IS NOT NULL RETURN DISTINCT m.status as status")
        statuses = [r["status"] for r in result]
        print(f"Distinct Statuses found: {statuses}")

    driver.close()

if __name__ == "__main__":
    debug_graph()
