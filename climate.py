import logging

from ngenicpy.models.measurement import MeasurementType

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    HVAC_MODE_HEAT
)
from homeassistant.const import (
    TEMP_CELSIUS, 
    ATTR_TEMPERATURE
)

from .const import (
    DOMAIN,
    DATA_CLIENT,
    SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

#async def async_setup_platform(hass, config, add_devices, discovery_info=None):
#    """Set up the climate platform."""
#    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""

    ngenic = hass.data[DOMAIN][DATA_CLIENT]

    devices = []
    
    for tmp_tune in ngenic.tunes():
        # listing tunes contain less information than when querying a single tune
        tune = ngenic.tune(tmp_tune.uuid())

        # get the room whose sensor data and target temperature should be used as inputs to the Tune control system
        control_room = tune.room(tune["roomToControlUuid"])
        
        # get the room node
        control_node = tune.node(control_room["nodeUuid"])

        device = NgenicTune(
            hass,
            ngenic,
            tune,
            control_room,
            control_node
        )

        # Initial update
        await device._async_update()

        # Setup update interval
        async_track_time_interval(hass, device._async_update, SCAN_INTERVAL)
        
        devices.append(device)

    async_add_entities(devices)

class NgenicTune(ClimateDevice):
    """Representation of an Ngenic Thermostat"""

    def __init__(self, hass, ngenic, tune, control_room, control_node):
        """Initialize the thermostat."""
        self._hass = hass
        self._ngenic = ngenic
        self._name = tune["name"]
        self._tune = tune
        self._room = control_room
        self._node = control_node
        self._current_temperature = None
        self._target_temperature = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def name(self):
        """Return the name of the Tune."""
        return self._name

    @property
    def unique_id(self):
        return "%s-%s" % (self._node.uuid(), "climate")

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Must be implemented"""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Must be implemented"""
        return [HVAC_MODE_HEAT]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._room["targetTemperature"] = temperature
        self._room.update()
        self._target_temperature = temperature

    async def _async_update(self, event_time=None):
        """Execute the update asynchronous"""
        await self._hass.async_add_executor_job(self._update)

    def _update(self, event_time=None):
        """Fetch new state data from the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        current = self._node.measurement(MeasurementType.TEMPERATURE)
        target = self._tune.room(self._room.uuid())["targetTemperature"]

        self._current_temperature = round(current["value"], 1)
        self._target_temperature = round(target, 1)