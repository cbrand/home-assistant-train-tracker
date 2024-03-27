import pytest
from homeassistant.core import HomeAssistant
from homeassistant.loader import DATA_CUSTOM_COMPONENTS


@pytest.fixture
def hass(hass: HomeAssistant) -> HomeAssistant:
    hass.data[DATA_CUSTOM_COMPONENTS] = None
    return hass
