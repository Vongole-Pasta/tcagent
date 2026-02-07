import os
import sys
from neo4j import GraphDatabase
from config import Config

def migrate_constraints():
    config = Config()
    uri = config.NEO4J_URI
    auth = (config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    print(f"Connecting to Neo4j at {uri}...")
    
    driver = GraphDatabase.driver(uri, auth=auth)
    
    with driver.session() as session:
        print("\n--- Migrating Constraints ---")
        try:
            # 1. Drop existing constraint on FILE(path)
            # Iterate to find the exact name
            result = session.run("SHOW CONSTRAINTS")
            for record in result:
                if 'FILE' in record['labelsOrTypes'] and 'path' in record['properties'] and len(record['properties']) == 1:
                    name = record['name']
                    print(f"Dropping constraint: {name}")
                    session.run(f"DROP CONSTRAINT {name}")
            
            # 2. Create new composite constraint on FILE(path, project)
            print("Creating composite unique constraint on FILE(path, project)...")
            try:
                session.run("CREATE CONSTRAINT file_path_project_unique IF NOT EXISTS FOR (f:FILE) REQUIRE (f.path, f.project) IS UNIQUE")
                print("Constraint created successfully.")
            except Exception as e:
                # Fallback for older Neo4j versions if syntax differs, but this is standard 4.4+
                print(f"Error creating constraint: {e}")

        except Exception as e:
            print(f"Migration failed: {e}")
            
    driver.close()

if __name__ == "__main__":
    migrate_constraints()
