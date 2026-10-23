import os
import sys
from unittest.mock import MagicMock
import pytest

# Inject mock MySQLdb module before importing application
mock_mysqldb = MagicMock()
sys.modules['MySQLdb'] = mock_mysqldb

import application

@pytest.fixture(autouse=True)
def setup_env():
    os.environ['MYSQL_USERNAME'] = 'testuser'
    os.environ['MYSQL_PASSWORD'] = 'testpass'
    os.environ['MYSQL_DB_NAME'] = 'testdb'
    os.environ['MYSQL_HOSTNAME'] = '127.0.0.1'
    os.environ['MYSQL_HOST_PORT'] = '3306'

@pytest.fixture
def client():
    application.application.config['TESTING'] = True
    with application.application.test_client() as client:
        yield client

def test_serve_route(client):
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ['Johnny']
    mock_db.cursor.return_value = mock_cursor
    mock_mysqldb.connect.return_value = mock_db

    res = client.get('/')
    assert res.status_code == 200
    assert res.get_data(as_text=True) == 'Hello World, Johnny!'

    # Verify MySQL interactions
    mock_mysqldb.connect.assert_called_with(
        user='testuser',
        passwd='testpass',
        db='testdb',
        host='127.0.0.1',
        port=3306
    )
    assert mock_cursor.execute.call_count >= 3
