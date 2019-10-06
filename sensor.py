import logging

from ngenicpy import Ngenic
from ngenicpy.models.node import NodeType
from ngenicpy.models.measurement import MeasurementType

from homeassistant.const import (
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    DATA_CLIENT,
    SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

#async def async_setup_platform(hass, config, add_entities, discovery_info=None):
#    pass

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    
    ngenic = hass.data[DOMAIN][DATA_CLIENT]

    devices = []

    for tune in ngenic.tunes():
        rooms = tune.rooms()

        for node in tune.nodes():
            node_name = "Ngenic %s" % node.get_type().name.lower()

            if node.get_type() == NodeType.SENSOR:
                # If this sensor is connected to a room
                # we'll use the room name as the sensor name
                for room in rooms:
                    if room["nodeUuid"] == node.uuid():
                        node_name = room["name"]

            sensor = None
            if MeasurementType.TEMPERATURE in node.measurement_types():
                sensor = NgenicTempSensor(
                    hass,
                    ngenic,
                    node,
                    node_name,
                    MeasurementType.TEMPERATURE
                )            
            
            if MeasurementType.HUMIDITY in node.measurement_types():
                sensor = NgenicHumiditySensor(
                    hass,
                    ngenic,
                    node,
                    node_name,
                    MeasurementType.HUMIDITY
                )

            if sensor:
                # Initial update
                await sensor._async_update()

                # Setup update interval
                async_track_time_interval(hass, sensor._async_update, SCAN_INTERVAL)

                devices.append(sensor)


    async_add_entities(devices)

class NgenicSensor(Entity):
    """Representation of an Ngenic Sensor"""
    
    def __init__(self, hass, ngenic, node, name, measurement_type):
        self._hass = hass
        self._state = None
        self._ngenic = ngenic
        self._name = name
        self._node = node
        self._measurement_type = measurement_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, self.device_class)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        return "%s-%s-%s" % (self._node.uuid(), self._measurement_type.name, "sensor")

    @property
    def should_poll(self):
        """Don't poll, we got our own update tracking"""
        return False

    async def _async_update(self, event_time=None):
        """Execute the update asynchronous"""
        await self._hass.async_add_executor_job(self._update)

    def _update(self, event_time=None):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        current = self._node.measurement(self._measurement_type)
        self._state = round(current["value"], 1)

class NgenicTempSensor(NgenicSensor):
    device_class = DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        # TODO: Not sure if Ngenic API can return something
        # else than "temperature_C"
        return TEMP_CELSIUS

class NgenicHumiditySensor(NgenicSensor):
    device_class = DEVICE_CLASS_HUMIDITY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

        