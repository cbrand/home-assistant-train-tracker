import logging
from typing import Any, Dict, List, Optional, Tuple

import homeassistant.helpers.config_validation as cv
import schiene
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from custom_components.db_train_tracker.const import (
    CONF_CALENDARS,
    CONF_DURATION,
    CONF_FILTERED_REGULAR_EXPRESSIONS,
    CONF_HOME_STATION,
    CONF_MAPPINGS,
    CONF_MAX_RESULTS,
    DEFAULT_DURATION,
    DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING,
    DEFAULT_MAPPINGS_STRING,
    DEFAULT_MAX_RESULTS,
    DOMAIN,
)

DB_TRAIN_TRACKER_DATA_SCHEMA = vol.Schema({vol.Required("")})

_LOGGER = logging.getLogger(__name__)

SCHIENE = schiene.Schiene()


async def _validate_station(hass: HomeAssistant, station: str) -> str:
    if not station:
        raise vol.Invalid("station_empty")

    station_check = await hass.async_add_executor_job(SCHIENE.stations, station, 1)
    if len(station_check) == 0:
        raise vol.Invalid("station_not_found")

    return station_check[0]["value"]


async def _validate_mappings(mappings: str) -> Tuple[Tuple[str, str], ...]:
    if not mappings:
        return tuple()
    to_return_mappings: List[Tuple[str, str]] = []
    for line in mappings.split(";"):
        items = line.strip().split(",")
        if not len(items) == 2:
            raise vol.Invalid("mapping_format")
        mapping_tuple: Tuple[str, str] = tuple(item.strip() for item in items)  # type: ignore[assignment]
        to_return_mappings.append(mapping_tuple)
    return tuple(to_return_mappings)


async def _validate_regular_expressions(expressions: str) -> Tuple[str, ...]:
    if not expressions:
        raise vol.Invalid("expressions_empty")
    return tuple(item.strip() for item in expressions.split(";"))


class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        return await self.async_step_menu(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        return await self.async_step_menu(user_input)

    async def async_step_menu(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        def __get_option(key: str, default: Any) -> Any:
            result = self.config_entry.options.get(key, self.config_entry.data.get(key, default))
            if key == CONF_FILTERED_REGULAR_EXPRESSIONS:
                return ";".join(result)
            if key == CONF_MAPPINGS:
                return ";".join(",".join(mapping) for mapping in result)
            return result

        errors = {}
        if user_input is not None:
            try:
                await _validate_mappings(user_input.get(CONF_MAPPINGS, DEFAULT_MAPPINGS_STRING))
            except vol.Invalid as error:
                errors[CONF_MAPPINGS] = error.error_message

            try:
                await _validate_regular_expressions(
                    user_input.get(
                        CONF_FILTERED_REGULAR_EXPRESSIONS,
                        DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING,
                    )
                )
            except vol.Invalid as error:
                errors[CONF_FILTERED_REGULAR_EXPRESSIONS] = error.error_message

            if len(errors) == 0:
                return self.async_create_entry(
                    data=user_input,
                )

        calendars = self.hass.states.async_entity_ids("calendar")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CALENDARS, default=__get_option(CONF_CALENDARS, [])): cv.multi_select(calendars),
                    vol.Required(
                        CONF_DURATION,
                        default=__get_option(CONF_DURATION, DEFAULT_DURATION),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_FILTERED_REGULAR_EXPRESSIONS,
                        default=__get_option(
                            CONF_FILTERED_REGULAR_EXPRESSIONS,
                            DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING,
                        ),
                    ): cv.string,
                    vol.Optional(
                        CONF_MAPPINGS,
                        default=__get_option(
                            CONF_MAPPINGS,
                            DEFAULT_MAPPINGS_STRING,
                        ),
                    ): cv.string,
                    vol.Required(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): cv.positive_int,
                }
            ),
            errors=errors,
        )


class DBTrainTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            unique_id = user_input[CONF_HOME_STATION]
            try:
                unique_id = await _validate_station(self.hass, unique_id)
            except vol.Invalid as error:
                errors[CONF_HOME_STATION] = error.error_message
            user_input[CONF_HOME_STATION] = unique_id

            try:
                user_input[CONF_MAPPINGS] = await _validate_mappings(
                    user_input.get(CONF_MAPPINGS, DEFAULT_MAPPINGS_STRING)
                )
            except vol.Invalid as error:
                errors[CONF_MAPPINGS] = error.error_message

            try:
                user_input[CONF_FILTERED_REGULAR_EXPRESSIONS] = await _validate_regular_expressions(
                    user_input.get(
                        CONF_FILTERED_REGULAR_EXPRESSIONS,
                        DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING,
                    )
                )
            except vol.Invalid as error:
                errors[CONF_FILTERED_REGULAR_EXPRESSIONS] = error.error_message

            if len(errors) == 0:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                _LOGGER.debug("Initialized new db calendar train tracker with id: {unique_id}")
                return self.async_create_entry(
                    title=f"Calendar Train Tracker {user_input[CONF_HOME_STATION]}",
                    data=user_input,
                )

        calendars = self.hass.states.async_entity_ids("calendar")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CALENDARS): cv.multi_select(calendars),
                    vol.Required(CONF_HOME_STATION): cv.string,
                    vol.Required(CONF_DURATION, default=DEFAULT_DURATION): cv.positive_int,
                    vol.Required(
                        CONF_FILTERED_REGULAR_EXPRESSIONS,
                        default=DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING,
                    ): cv.string,
                    vol.Required(
                        CONF_MAPPINGS,
                        default=DEFAULT_MAPPINGS_STRING,
                    ): cv.string,
                    vol.Required(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): cv.positive_int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)
