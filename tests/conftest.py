import pytest
from ble_inventory.config import load_config


@pytest.fixture
def config():
    return load_config("config/site.example.json")
