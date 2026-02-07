import os
import sys
from neo4j import GraphDatabase
from config import Config

def list_constraints():
    config = Config()
    uri = config.NEO4J_URI
    auth = (config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    print(f"Connecting to Neo4j at {uri}...")
    
    driver = GraphDatabase.driver(uri, auth=auth)
    
    with driver.session() as session:
        print("\n--- Current Constraints ---")
        try:
            # Neo4j 4.x/5.x syntax
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            if not constraints:
                print("No constraints found.")
            for record in constraints:
                print(f"Name: {record.get('name')}, Type: {record.get('type')}, Entity: {record.get('entityType')}, Labels: {record.get('labelsOrTypes')}, Properties: {record.get('properties')}")
                
        except Exception as e:
            print(f"Error listing constraints: {e}")
            
    driver.close()

if __name__ == "__main__":
    list_constraints()
