import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import verify_domain_control

from .const import (
    DOMAIN,
    DATA_CLIENT,
    SERVICE_SET_ACTIVE_CONTROL
)

_LOGGER = logging.getLogger(__name__)

def async_register_services(hass):
    """Register services for Ngenic integration."""

    async def set_active_control(service, skip_reload=True) -> None:
        """List available rooms"""
        # Get parameters
        room_uuid = service.data["room_uuid"]
        active = service.data.get("active", False)

        ngenic = hass.data[DOMAIN][DATA_CLIENT]
        for tune in await ngenic.async_tunes():
            rooms = await tune.async_rooms()
            for room in rooms:
                if room.uuid() == room_uuid:
                    room["activeControl"] = active
                    _LOGGER.debug("Room: %s" % (room.json()))
                    await room.async_update()

    if not hass.services.has_service(DOMAIN, SERVICE_SET_ACTIVE_CONTROL):
        # Register services
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_ACTIVE_CONTROL,
            verify_domain_control(hass, DOMAIN)(set_active_control),
            schema=vol.Schema(
                {
                    vol.Required("room_uuid"): cv.string,
                    vol.Required("active"): cv.boolean
                }
            ),
        )
