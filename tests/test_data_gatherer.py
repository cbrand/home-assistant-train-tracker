import datetime

from homeassistant.core import HomeAssistant
from pytest_mock import MockerFixture

from custom_components.db_train_tracker.data_gatherer import DataGatherer, GathererConfig


async def test_gather_data(hass: HomeAssistant, mocker: MockerFixture) -> None:
    services_mock = mocker.patch.object(hass, "services")
    async_call = services_mock.async_call = mocker.AsyncMock()
    async_call.return_value = {
        "calendar.xyz": {
            "events": [
                {
                    "start": "2022-01-01T18:14:00+00:00",
                    "end": "2022-01-01T20:20:00+00:00",
                    "summary": "Berlin Hbf → Hamburg Hbf",
                }
            ]
        }
    }
    hass.states = mocker.MagicMock()
    hass.states.get = mocker.MagicMock(return_value=mocker.MagicMock(state="on"))

    schiene = mocker.MagicMock()
    connection_mock = schiene.connections = mocker.MagicMock()
    connection_mock.return_value = [
        {
            "details": "http://temp123",
            "departure": "18:14",
            "arrival": "20:20",
            "transfers": 0,
            "time": "2:06",
            "products": ["ICE"],
            "price": 103.3,
            "ontime": True,
            "canceled": False,
        },
        {
            "details": "http://temp123",
            "departure": "18:20",
            "arrival": "21:20",
            "transfers": 0,
            "time": "2:06",
            "products": ["ICE"],
            "price": 103.3,
            "ontime": True,
            "canceled": False,
        },
    ]

    gatherer = DataGatherer(hass, schiene)
    result = await gatherer.collect(
        GathererConfig(
            origin="Hamburg Hbf",
            calendars=("calendar.xyz",),
        )
    )
    assert result.exists is True
    assert result.origin == "Berlin Hbf"
    assert result.destination == "Hamburg Hbf"
    assert result.start is not None
    assert result.start.time() == datetime.time(18, 14)
    assert result.end is not None
    assert result.end.time() == datetime.time(20, 20)
    assert result.next_start is not None
    assert result.next_start.time() == datetime.time(18, 20)
    assert result.next_end is not None
    assert result.next_end.time() == datetime.time(21, 20)


async def test_gather_data_different_summary(hass: HomeAssistant, mocker: MockerFixture) -> None:
    hass.states = mocker.MagicMock()
    hass.states.get = mocker.MagicMock(return_value=mocker.MagicMock(state="on"))
    services_mock = mocker.patch.object(hass, "services")
    async_call = services_mock.async_call = mocker.AsyncMock()
    hass.states.set("calendar.xyz", "on")
    async_call.return_value = {
        "calendar.xyz": {
            "events": [
                {
                    "start": "2022-01-01T18:14:00+00:00",
                    "end": "2022-01-01T20:20:00+00:00",
                    "summary": "Train travel to Düsseldorf Hbf",
                }
            ]
        }
    }

    schiene = mocker.MagicMock()
    connection_mock = schiene.connections = mocker.MagicMock()
    connection_mock.return_value = [
        {
            "details": "http://temp123",
            "departure": "18:14",
            "arrival": "20:20",
            "transfers": 0,
            "time": "2:06",
            "products": ["ICE"],
            "price": 103.3,
            "ontime": True,
            "canceled": False,
        },
        {
            "details": "http://temp123",
            "departure": "18:20",
            "arrival": "21:20",
            "transfers": 0,
            "time": "2:06",
            "products": ["ICE"],
            "price": 103.3,
            "ontime": True,
            "canceled": False,
        },
    ]

    gatherer = DataGatherer(hass, schiene)
    result = await gatherer.collect(
        GathererConfig(
            origin="Hamburg Hbf",
            calendars=("calendar.xyz",),
        )
    )
    assert result.exists is True
    assert result.origin == "Hamburg Hbf"
    assert result.destination == "Düsseldorf Hbf"
    assert result.start is not None
    assert result.start.time() == datetime.time(18, 14)
    assert result.end is not None
    assert result.end.time() == datetime.time(20, 20)
    assert result.next_start is not None
    assert result.next_start.time() == datetime.time(18, 20)
    assert result.next_end is not None
    assert result.next_end.time() == datetime.time(21, 20)


async def test_gather_data_no_calendar(hass: HomeAssistant, mocker: MockerFixture) -> None:
    hass.states = mocker.MagicMock()
    hass.states.get = mocker.MagicMock(return_value=mocker.MagicMock(state="on"))
    services_mock = mocker.patch.object(hass, "services")
    async_call = services_mock.async_call = mocker.AsyncMock()
    async_call.return_value = {"calendar.xyz": {"events": []}}

    gatherer = DataGatherer(hass, mocker.MagicMock())
    result = await gatherer.collect(
        GathererConfig(
            origin="Hamburg Hbf",
            calendars=("calendar.xyz",),
        )
    )
    assert result.exists is False
