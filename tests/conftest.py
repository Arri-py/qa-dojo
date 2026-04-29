import pytest
import requests


BASE_URL = "http://localhost:8088"


@pytest.fixture
def base_url():
    return BASE_URL


@pytest.fixture
def created_calculation(base_url):
    """Создаёт вычисление перед тестом и удаляет его после."""
    response = requests.post(
        f"{base_url}/api/v1/calculations",
        json={"operation": "add", "a": 10, "b": 5},
    )
    calc = response.json()
    yield calc
    requests.delete(f"{base_url}/api/v1/calculations/{calc['id']}")
