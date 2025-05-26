import pytest


def test_login_route_returns_200(client):
    response = client.get('/login')
    assert response.status_code == 200


def test_crear_requisicion_requires_login(client, setup_db):
    response = client.get('/requisiciones/crear')
    assert response.status_code == 302
    assert '/login' in response.headers.get('Location', '')


def test_login_valid_credentials_redirects(client, setup_db, admin_user):
    response = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    assert response.status_code == 302
    assert '/' in response.headers.get('Location', '')


def test_login_success_html_contains_inicio(client, setup_db, admin_user):
    response = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Inicio' in response.data
