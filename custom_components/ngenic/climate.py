import logging
from datetime import timedelta

from ngenicpy.models.measurement import MeasurementType

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode
)
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_TEMPERATURE
)

from .const import (
    DOMAIN,
    DATA_CLIENT
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""

    ngenic = hass.data[DOMAIN][DATA_CLIENT]

    devices = []
    
    for tmp_tune in await ngenic.async_tunes():
        # listing tunes contain less information than when querying a single tune
        tune = await ngenic.async_tune(tmp_tune.uuid())

        # rooms with control sensors can be found either directly on the tune, or by looking at the activeControl
        # property on the room object. if roomToControlUuid is set, it takes precedence and the activeControl
        # attribute will not be used
        control_room_uuids = []
        if tune["roomToControlUuid"]:
            control_room_uuids.append(tune["roomToControlUuid"])
        else:
            for room in tune["rooms"]:
                if room["activeControl"] is True:
                    control_room_uuids.append(room['uuid'])

        for control_room_uuid in control_room_uuids:
            # get the room whose sensor data and target temperature should be used as inputs to the Tune control system
            control_room = await tune.async_room(control_room_uuid)

            # get the room node
            control_node = await tune.async_node(control_room["nodeUuid"])

            device = NgenicTune(
                hass,
                ngenic,
                tune,
                control_room,
                control_node
            )

            # Initial update
            await device._async_update()

            # Setup update timer
            device._setup_updater()

            devices.append(device)

    async_add_entities(devices)

class NgenicTune(ClimateEntity):
    """Representation of an Ngenic Thermostat"""

    def __init__(self, hass, ngenic, tune, control_room, control_node):
        """Initialize the thermostat."""
        self._hass = hass
        self._available = False
        self._ngenic = ngenic
        self._name =  "Ngenic Tune %s" % (tune["name"])
        self._tune = tune
        self._room = control_room
        self._node = control_node
        self._current_temperature = None
        self._target_temperature = None
        self._updater = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def name(self):
        """Return the name of the Tune."""
        return self._name

    @property
    def available(self):
        return self._available

    @property
    def unique_id(self):
        return "%s-%s" % (self._node.uuid(), "climate")

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return UnitOfTemperature.CELSIUS

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
        return HVACMode.HEAT

    @property
    def hvac_modes(self):
        """Must be implemented"""
        return [HVACMode.HEAT]

    async def async_will_remove_from_hass(self):
        """Remove updater when sensor is removed."""
        if self._updater:
            self._updater()
            self._updater = None

    def _setup_updater(self):
        """Setup a timer that will execute an update every update interval"""
        # async_track_time_interval returns a function that, when executed, will remove the timer
        self._updater = async_track_time_interval(self._hass, self._async_update, timedelta(minutes=5))

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._room["targetTemperature"] = temperature
        await self._room.async_update()
        self._target_temperature = temperature

    async def _async_update(self, event_time=None):
        """Fetch new state data from the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            current = await self._node.async_measurement(MeasurementType.TEMPERATURE)
            target_room = await self._tune.async_room(self._room.uuid())
            self._available = True
        except Exception:
            # Don't throw an exception if a sensor fails to update.
            # Instead, make the sensor unavailable.
            _LOGGER.exception("Failed to update climate '%s'" % self.unique_id)
            self._available = False
            return

        self._current_temperature = round(current["value"], 1)
        self._target_temperature = round(target_room["targetTemperature"], 1)
