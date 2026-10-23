from unittest.mock import patch
import pytest
import subprocess
import app

@pytest.fixture
def client():
    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client

def test_healthz(client):
    res = client.get('/api/healthz')
    assert res.status_code == 200
    assert res.get_data(as_text=True) == 'ok'
    cache_control = res.headers.get('Cache-Control', '')
    assert 'no-cache' in cache_control
    assert 'no-store' in cache_control
    assert 'must-revalidate' in cache_control

def test_secure_missing_auth(client):
    res = client.get('/api/secure.json')
    assert res.status_code == 401
    assert 'Unauthorized' in res.get_data(as_text=True)

def test_secure_invalid_token(client):
    with patch('google.oauth2.id_token.verify_firebase_token', return_value=None):
        res = client.get('/api/secure.json', headers={'Authorization': 'Bearer invalid-token'})
        assert res.status_code == 401
        assert 'Unauthorized' in res.get_data(as_text=True)

def test_secure_valid_token(client):
    with patch('google.oauth2.id_token.verify_firebase_token', return_value={'sub': 'user-123', 'email': 'user@example.com'}):
        res = client.get('/api/secure.json', headers={'Authorization': 'Bearer valid-token'})
        assert res.status_code == 200
        assert res.get_json() == {'message': 'Hello World Standalone'}

def test_cors_headers(client):
    res = client.get('/api/healthz', headers={'Origin': 'https://example.com'})
    assert res.headers.get('Access-Control-Allow-Origin') is not None

def test_gunicorn_config():
    import sys, shutil, os
    gunicorn_bin = shutil.which('gunicorn') or os.path.join(os.path.dirname(sys.executable), 'gunicorn')
    result = subprocess.run(
        [gunicorn_bin, '--check-config', 'app:app'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
