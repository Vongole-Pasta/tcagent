from infra.db_client import DBClient

def verify():
    connector = DBClient()
    
    print("Verifying Generic Links...")
    
    # Check 1: Parameter 'userList' in GenericTestDto.processUsers
    # Expected: Should link to UserDto (but currently fails)
    query_param = """
    MATCH (c:TYPE {name: 'GenericTestDto'})-[:CONTAINS]->(m:METHOD {name: 'processUsers'})-[:CONTAINS]->(p:PARAMETER {name: 'userList'})
    OPTIONAL MATCH (p)-[:OF_TYPE]->(t:TYPE)
    RETURN t.name as type_name
    """
    result_param = connector.execute_query(query_param)
    if result_param and result_param[0]['type_name'] == 'UserDto':
        print("[PASS] Parameter 'userList' is linked to 'UserDto'")
    else:
        print(f"[FAIL] Parameter 'userList' is NOT linked to 'UserDto'. Actual: {result_param[0]['type_name'] if result_param else 'None'}")

    # Check 2: Field 'productCache' in GenericTestDto
    # Expected: Should link to Product (but currently fails)
    query_field = """
    MATCH (c:TYPE {name: 'GenericTestDto'})-[:CONTAINS]->(f:FIELD {name: 'productCache'})
    OPTIONAL MATCH (f)-[:OF_TYPE]->(t:TYPE)
    RETURN t.name as type_name
    """
    result_field = connector.execute_query(query_field)
    if result_field and result_field[0]['type_name'] == 'Product':
        print("[PASS] Field 'productCache' is linked to 'Product'")
    else:
        print(f"[FAIL] Field 'productCache' is NOT linked to 'Product'. Actual: {result_field[0]['type_name'] if result_field else 'None'}")

    connector.close()

if __name__ == "__main__":
    verify()
