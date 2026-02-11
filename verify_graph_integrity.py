import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from infra.db_client import DBClient

def check_integrity():
    connector = DBClient()
    print("Graph Integrity Check...\n")

    # 1. Total Stats
    query_stats = """
    MATCH (n) RETURN count(n) as total_nodes
    """
    total_nodes = connector.execute_query(query_stats)[0]['total_nodes']
    
    query_rels = """
    MATCH ()-[r]->() RETURN count(r) as total_rels
    """
    total_rels = connector.execute_query(query_rels)[0]['total_rels']
    
    print(f"Total Nodes: {total_nodes}")
    print(f"Total Relationships: {total_rels}")
    print("-" * 30)

    # 2. Unlinked Parameters
    # Parameters that have a type string but no OF_TYPE relationship
    query_unlinked_params = """
    MATCH (p:PARAMETER)
    WHERE NOT (p)-[:OF_TYPE]->(:TYPE)
    RETURN p.name as name, p.type as type, p.types as types, elementId(p) as id
    LIMIT 20
    """
    unlinked_params = connector.execute_query(query_unlinked_params)
    print(f"Unlinked Parameters (Sample 20): {len(unlinked_params)}")
    for p in unlinked_params:
        print(f" - [{p['name']}] (type: {p['type']}, types: {p.get('types')})")
    
    if len(unlinked_params) == 0:
        print(" [PASS] All parameters are linked or have no type.")
    print("-" * 30)

    # 3. Unlinked Fields
    query_unlinked_fields = """
    MATCH (f:FIELD)
    WHERE NOT (f)-[:OF_TYPE]->(:TYPE)
    RETURN f.name as name, f.type as type, f.types as types, elementId(f) as id
    LIMIT 20
    """
    unlinked_fields = connector.execute_query(query_unlinked_fields)
    print(f"Unlinked Fields (Sample 20): {len(unlinked_fields)}")
    for f in unlinked_fields:
        print(f" - [{f['name']}] (type: {f['type']}, types: {f.get('types')})")

    if len(unlinked_fields) == 0:
        print(" [PASS] All fields are linked or have no type.")
    print("-" * 30)

    # 4. Orphaned Methods (No Type container)
    query_orphaned_methods = """
    MATCH (m:METHOD)
    WHERE NOT (:TYPE)-[:CONTAINS]->(m)
    RETURN m.name as name, m.signature as signature
    LIMIT 10
    """
    orphaned_methods = connector.execute_query(query_orphaned_methods)
    print(f"Orphaned Methods (Sample 10): {len(orphaned_methods)}")
    for m in orphaned_methods:
        print(f" - {m['signature']}")
        
    if len(orphaned_methods) == 0:
        print(" [PASS] All methods belong to a Type.")
    print("-" * 30)
    
    # 5. Type Nodes without File (External Types?)
    query_external_types = """
    MATCH (t:TYPE)
    WHERE NOT (:FILE)-[:CONTAINS]->(t)
    RETURN t.name as name, t.fullName as fullName
    LIMIT 10
    """
    external_types = connector.execute_query(query_external_types)
    print(f"Types without File Container (External/Built-in? Sample 10): {len(external_types)}")
    for t in external_types:
        print(f" - {t['fullName']}")

    connector.close()

if __name__ == "__main__":
    check_integrity()
