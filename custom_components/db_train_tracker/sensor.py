import logging
from datetime import timedelta
from typing import Any, Callable, Dict, Optional

import requests
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from schiene import Schiene

from custom_components.db_train_tracker.const import (
    CONF_CALENDARS,
    CONF_FILTERED_REGULAR_EXPRESSIONS,
    CONF_HOME_STATION,
    CONF_MAPPINGS,
    CONF_MAX_RESULTS,
    DEFAULT_FILTERED_REGULAR_EXPRESSIONS,
    DEFAULT_MAPPINGS,
    DEFAULT_MAX_RESULTS,
    DOMAIN,
)
from custom_components.db_train_tracker.data_gatherer import DataGatherer, GathererConfig

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=3)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigType,
    async_add_entities: Callable,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry")
    if entry.options:
        config.update(entry.options)
    schiene = Schiene()
    sensor = DBTrainTrackerSensor(hass, schiene, config)
    async_add_entities([sensor], update_before_add=True)


class DBTrainTrackerSensor(Entity):
    """Tracker for one starting station of a train checking departure times for calendar entries."""

    def __init__(self, hass: HomeAssistant, schiene: Schiene, data: Dict[str, Any]):
        super().__init__()
        self.hass = hass
        self.schiene = schiene
        self.home_station = data[CONF_HOME_STATION]
        self._name = data.get("name", f"Train Tracker {self.home_station}")
        self._state: Optional[str] = None
        self.calendars = data[CONF_CALENDARS]
        self.gatherer = DataGatherer(self.hass, self.schiene)
        self.attrs: Dict[str, Any] = {
            "home_station": self.home_station,
            "calendars": self.calendars,
        }
        regular_expression_strings = data.get(CONF_FILTERED_REGULAR_EXPRESSIONS, DEFAULT_FILTERED_REGULAR_EXPRESSIONS)
        mappings = data.get(CONF_MAPPINGS, DEFAULT_MAPPINGS)
        max_results = data.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS)

        self.gatherer_config = GathererConfig(
            calendars=tuple(self.calendars),
            origin=self.home_station,
            filtered_regular_expressions=tuple(regular_expression_strings),
            mappings=tuple(mappings),
            max_results=max_results,
        )

        self._available = True

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.home_station

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self.attrs

    async def async_update(self) -> None:
        try:
            result = await self.gatherer.collect(self.gatherer_config)

            self._state = "on" if result.exists else "off"
            self.attrs["destination"] = result.destination
            self.attrs["origin"] = result.origin
            self.attrs["start"] = result.start
            self.attrs["end"] = result.end
            self.attrs["start_time"] = result.start_string
            self.attrs["end_time"] = result.end_string
            self.attrs["time"] = result.time
            self.attrs["delay"] = result.departure_delay
            self.attrs["arrival_delay"] = result.arrival_delay
            self.attrs["products"] = result.products
            self.attrs["ontime"] = result.ontime
            self.attrs["canceled"] = result.canceled
            self.attrs["next_start"] = result.next_start
            self.attrs["next_start_time"] = result.next_start_string
            self.attrs["next_end"] = result.next_end
            self.attrs["next_end_time"] = result.next_end_string
            self.attrs["next_time"] = result.next_time
            self.attrs["next_delay"] = result.next_departure_delay
            self.attrs["next_arrival_delay"] = result.next_arrival_delay
            self.attrs["next_products"] = result.next_products
            self.attrs["next_ontime"] = result.next_ontime
            self.attrs["next_canceled"] = result.next_canceled
            self.attrs["planned_travels"] = [travel_time.to_dict() for travel_time in result.travel_times]

            self._available = True
        except (requests.ConnectionError, ValueError):
            self._available = False
            _LOGGER.exception("Error retrieving data from DBTrainTracker for sensor %s.", self.name)
