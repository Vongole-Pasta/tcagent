from fastapi.testclient import TestClient
from api.main import app
from unittest.mock import MagicMock

client = TestClient(app)

# Mock AnalysisFlow to avoid needing a real Neo4j connection for this basic routing test
# We just want to ensure the routes are registered and handling parameters correctly.
# Ideally we would mock the DB response.

def test_routes_exist():
    # Mock the analysis_flow and connector
    mock_flow = MagicMock()
    mock_connector = MagicMock()
    mock_flow.connector = mock_connector
    
    # Mock connector.execute_query to return empty list or dummy data
    mock_connector.execute_query.return_value = []
    
    # Inject mock into app state
    app.state.analysis_flow = mock_flow

    # Test Project Nodes
    response = client.get("/projects/default/nodes")
    # Even if 503 (if mock fails injection weirdly) or 200, we know route exists.
    # But since we injected mock, it should be 200.
    assert response.status_code == 200
    assert "nodes" in response.json()

    # Test Upstream
    response = client.get("/graph/upstream/123")
    assert response.status_code == 200
    assert "nodes" in response.json()
    assert "edges" in response.json()

    # Test Downstream
    response = client.get("/graph/downstream/123")
    assert response.status_code == 200
    
    # Test Node Details
    # Build a fake response for the single node query
    mock_connector.execute_query.return_value = [{"name": "Test", "signature": "sig", "source": "code"}]
    response = client.get("/graph/node/123")
    assert response.status_code == 200
    assert response.json()["name"] == "Test"

if __name__ == "__main__":
    test_routes_exist()
    print("✅ All API existence tests passed!")
