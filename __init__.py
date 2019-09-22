"""Support for Ngenic Tune"""
import logging

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_TOKEN
)

DOMAIN = "ngenic"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


