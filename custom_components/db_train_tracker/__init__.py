import asyncio
from datetime import timedelta
from typing import Any

from homeassistant import config_entries, core

from custom_components.db_train_tracker.config_flow import DOMAIN

CONF_SCAN_INTERVAL = 2
SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the db_train_tracker component."""
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def options_update_listener(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Handle options update."""
    return await hass.config_entries.async_reload(config_entry.entry_id)


async def async_update(self: Any) -> bool:
    """Async wrapper for update method."""
    return await self._hass.async_add_executor_job(self._update)


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(await asyncio.gather(*[hass.config_entries.async_forward_entry_unload(entry, "sensor")]))
    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
