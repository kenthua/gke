import os
import shutil
import subprocess
import sys
import pytest
import app

@pytest.fixture
def client():
    app.app.config['TESTING'] = True
    with app.app.test_client() as client:
        yield client

def test_root_serves_index(client):
    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Identity Platform' in html
    assert 'firebaseui-auth-container' in html

def test_gunicorn_config():
    gunicorn_bin = shutil.which('gunicorn') or os.path.join(os.path.dirname(sys.executable), 'gunicorn')
    result = subprocess.run(
        [gunicorn_bin, '--check-config', 'app:app'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
