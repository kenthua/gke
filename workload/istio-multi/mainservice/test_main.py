import os
from unittest.mock import patch, MagicMock
import pytest

@pytest.fixture(autouse=True)
def setup_env():
    os.environ['SERVICE1_URL'] = 'http://test-service1:8080'

@pytest.fixture
def client():
    import main
    main.app.config['TESTING'] = True
    with main.app.test_client() as client:
        yield client

def test_hello_route(client):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'Hello from downstream service1'
    mock_resp.__enter__.return_value = mock_resp

    with patch('urllib.request.urlopen', return_value=mock_resp):
        res = client.get('/')
        assert res.status_code == 200
        text = res.get_data(as_text=True)
        assert 'Hello World - main!' in text
        assert 'Hello from downstream service1' in text
        assert 'main environment variables' in text

def test_server_error_handler():
    import main
    response, code = main.server_error(Exception("downstream connection dropped"))
    assert code == 500
    assert "downstream connection dropped" in response
