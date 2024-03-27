"""Test component setup."""

from unittest import mock

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from pytest_mock import MockerFixture

from custom_components.db_train_tracker.config_flow import DOMAIN, SCHIENE, _validate_station
from custom_components.db_train_tracker.const import CONF_HOME_STATION


async def test_schiene_station_validation(hass: HomeAssistant, mocker: MockerFixture) -> None:
    mocker.patch.object(SCHIENE, "stations", return_value=[{"value": "Hamburg Hbf"}])
    assert await _validate_station(hass, "Hambu") == "Hamburg Hbf"


async def test_schiene_station_validation_empty(hass: HomeAssistant, mocker: MockerFixture) -> None:
    with pytest.raises(vol.Invalid):
        await _validate_station(hass, "")


async def test_schiene_station_validation_not_found(hass: HomeAssistant, mocker: MockerFixture) -> None:
    mocker.patch.object(SCHIENE, "stations", return_value=[])
    with pytest.raises(vol.Invalid):
        await _validate_station(hass, "Hamburg")


async def test_flow_user_init(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    expected = {
        "data_schema": mock.ANY,
        "description_placeholders": None,
        "errors": {},
        "flow_id": mock.ANY,
        "handler": "db_train_tracker",
        "step_id": "user",
        "type": "form",
        "last_step": mock.ANY,
        "preview": mock.ANY,
    }
    assert expected == result


async def test_flow_user_init_with_valid_data(hass: HomeAssistant, mocker: MockerFixture) -> None:
    patched = mocker.patch(
        "custom_components.db_train_tracker.config_flow._validate_station",
        return_value="Hamburg Hbf",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"home_station": "Hamburg Hbf", "calendars": []},
    )
    patched.assert_called_with(hass, "Hamburg Hbf")
    item = result["result"]
    assert item.data["home_station"] == "Hamburg Hbf"
    assert item.data["calendars"] == []


async def test_flow_user_init_with_renamed_station_data(hass: HomeAssistant, mocker: MockerFixture) -> None:
    patched = mocker.patch(
        "custom_components.db_train_tracker.config_flow._validate_station",
        return_value="Hamburg Hbf",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"home_station": "Hamburg", "calendars": []},
    )
    patched.assert_called_with(hass, "Hamburg")
    item = result["result"]
    assert item.data["home_station"] == "Hamburg Hbf"


async def test_flow_user_with_invalid_data(hass: HomeAssistant, mocker: MockerFixture) -> None:
    mocker.patch(
        "custom_components.db_train_tracker.config_flow._validate_station",
        side_effect=vol.Invalid("Station does not exist"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"home_station": "", "calendars": []},
    )
    assert result["errors"] == {CONF_HOME_STATION: "Station does not exist"}
