import pytest
import app

@pytest.fixture
def client():
    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client

def test_root_route(client):
    res = client.get('/')
    assert res.status_code == 200
    assert 'Hello World - root -' in res.get_data(as_text=True)

def test_service1_route(client):
    res = client.get('/service1')
    assert res.status_code == 200
    assert 'Hello World - service1! -' in res.get_data(as_text=True)

def test_service2_route(client):
    res = client.get('/service2')
    assert res.status_code == 200
    assert 'Hello World - service2! -' in res.get_data(as_text=True)

def test_server_error_handler():
    response, code = app.server_error(Exception("test failure"))
    assert code == 500
    assert "test failure" in response
