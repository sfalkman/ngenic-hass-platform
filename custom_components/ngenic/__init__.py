"""Support for Ngenic Tune"""
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_TOKEN
)

from .config_flow import configured_instances
from .const import (
    DOMAIN,
    DATA_CLIENT,
    DATA_CONFIG
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):
    """Setup the Ngenic component"""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Store config for use during entry setup
    hass.data[DOMAIN][DATA_CONFIG] = conf
    
    # Check if already configured
    if conf[CONF_TOKEN] in configured_instances(hass):
        return True

    # Create a config flow
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TOKEN: conf[CONF_TOKEN]
            },
        )
    )

    return True

async def async_setup_entry(hass, config_entry):
    from ngenicpy import AsyncNgenic
    ngenic = AsyncNgenic(
        token=config_entry.data[CONF_TOKEN]
    )

    hass.data[DOMAIN][DATA_CLIENT] = ngenic

    for component in ("sensor", "climate"):
        hass.async_add_job(hass.config_entries.async_forward_entry_setup(config_entry, component))

    return True

async def async_unload_entry(hass, config_entry):
    for component in ("sensor", "climate"):
        await hass.config_entries.async_forward_entry_unload(config_entry, component)

    await hass.data[DOMAIN][DATA_CLIENT].async_close()

    return True