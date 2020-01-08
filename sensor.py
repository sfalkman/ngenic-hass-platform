import logging
import datetime

from ngenicpy import Ngenic
from ngenicpy.models.node import NodeType
from ngenicpy.models.measurement import MeasurementType

from homeassistant.const import (
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    DATA_CLIENT,
    SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

TIME_ZONE = "Z" if str(dt_util.DEFAULT_TIME_ZONE) == "UTC" else " " + str(dt_util.DEFAULT_TIME_ZONE)

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

            if MeasurementType.TEMPERATURE in node.measurement_types():
                devices.append(
                    NgenicTempSensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        MeasurementType.TEMPERATURE
                    )
                )            
            
            if MeasurementType.HUMIDITY in node.measurement_types():
                devices.append(
                    NgenicHumiditySensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        MeasurementType.HUMIDITY
                    )
                )

            if MeasurementType.POWER_KW in node.measurement_types():
                devices.append(
                    NgenicPowerSensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        MeasurementType.POWER_KW
                    )
                )

            if MeasurementType.ENERGY_KWH in node.measurement_types():
                devices.append(
                    NgenicEnergySensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        MeasurementType.ENERGY_KWH
                    )
                )

    for device in devices:
        # Initial update
        await device._async_update()

        # Setup update interval
        async_track_time_interval(hass, device._async_update, SCAN_INTERVAL)

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
        """Enable polling. We got our own timer for actually refreshing
        the status, but this will poll the state variable.
        """
        return True

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

class NgenicPowerSensor(NgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "kW"

    def _update(self, event_time=None):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _update method.
        """
        from_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = from_dt + datetime.timedelta(days=1)
        iso_from_dt = from_dt.isoformat() + TIME_ZONE
        iso_to_dt = to_dt.isoformat() + TIME_ZONE

        # using datetime will return a list of measurements
        # we'll use the last item in that list
        current = self._node.measurement(self._measurement_type, iso_from_dt, iso_to_dt, "P1D")
        self._state = round(current[-1]["value"], 1)

class NgenicEnergySensor(NgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    def _update(self, event_time=None):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _update method.
        """
        from_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = from_dt + datetime.timedelta(days=1)
        iso_from_dt = from_dt.isoformat() + TIME_ZONE
        iso_to_dt = to_dt.isoformat() + TIME_ZONE

        # using datetime will return a list of measurements
        # we'll use the last item in that list
        current = self._node.measurement(self._measurement_type, iso_from_dt, iso_to_dt, "P1D")
        self._state = round(current[-1]["value"], 1)

        