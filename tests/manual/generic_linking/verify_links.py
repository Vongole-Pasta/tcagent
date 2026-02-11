import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

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

    # Check 3: Field 'userArray' (Array)
    # Expected: Should link to UserDto
    query_array = """
    MATCH (c:TYPE {name: 'GenericTestDto'})-[:CONTAINS]->(f:FIELD {name: 'userArray'})
    OPTIONAL MATCH (f)-[:OF_TYPE]->(t:TYPE)
    RETURN t.name as type_name
    """
    result_array = connector.execute_query(query_array)
    if result_array and result_array[0]['type_name'] == 'UserDto':
        print("[PASS] Field 'userArray' is linked to 'UserDto'")
    else:
        print(f"[FAIL] Field 'userArray' is NOT linked to 'UserDto'. Actual: {result_array[0]['type_name'] if result_array else 'None'}")

    # Check 4: Field 'productList' (Wildcard)
    # Expected: Should link to Product
    query_wildcard = """
    MATCH (c:TYPE {name: 'GenericTestDto'})-[:CONTAINS]->(f:FIELD {name: 'productList'})
    OPTIONAL MATCH (f)-[:OF_TYPE]->(t:TYPE)
    RETURN t.name as type_name
    """
    result_wildcard = connector.execute_query(query_wildcard)
    if result_wildcard and result_wildcard[0]['type_name'] == 'Product':
        print("[PASS] Field 'productList' is linked to 'Product'")
    else:
        print(f"[FAIL] Field 'productList' is NOT linked to 'Product'. Actual: {result_wildcard[0]['type_name'] if result_wildcard else 'None'}")

    # Check 5: Parameter 'users' (Varargs)
    # Expected: Should link to UserDto
    query_varargs = """
    MATCH (c:TYPE {name: 'GenericTestDto'})-[:CONTAINS]->(m:METHOD {name: 'processVarargs'})-[:CONTAINS]->(p:PARAMETER {name: 'users'})
    OPTIONAL MATCH (p)-[:OF_TYPE]->(t:TYPE)
    RETURN t.name as type_name
    """
    result_varargs = connector.execute_query(query_varargs)
    if result_varargs and result_varargs[0]['type_name'] == 'UserDto':
        print("[PASS] Parameter 'users' (varargs) is linked to 'UserDto'")
    else:
        print(f"[FAIL] Parameter 'users' (varargs) is NOT linked to 'UserDto'. Actual: {result_varargs[0]['type_name'] if result_varargs else 'None'}")

    connector.close()

if __name__ == "__main__":
    verify()
