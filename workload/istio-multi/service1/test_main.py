from unittest.mock import patch, MagicMock
import pytest
import main

@pytest.fixture
def client():
    main.app.config['TESTING'] = True
    with main.app.test_client() as client:
        yield client

def test_hello_route(client):
    with patch('google.cloud.logging.Client') as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        res = client.get('/')
        assert res.status_code == 200
        text = res.get_data(as_text=True)
        assert 'Hello World - service1! - hostname:' in text
        mock_client.setup_logging.assert_called_once()

def test_server_error_handler():
    response, code = main.server_error(Exception("database timeout"))
    assert code == 500
    assert "database timeout" in response
