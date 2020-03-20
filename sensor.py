import logging
from datetime import datetime, timedelta

from ngenicpy import Ngenic
from ngenicpy.models.node import NodeType
from ngenicpy.models.measurement import MeasurementType

from homeassistant.const import (
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT
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

TIME_ZONE = "Z" if str(dt_util.DEFAULT_TIME_ZONE) == "UTC" else str(dt_util.DEFAULT_TIME_ZONE)

def get_from_to_datetime_month():
    """Get a period for this month.
    This will return two dates in ISO 8601:2004 format
    The first date will be at 00:00 in the first of this month, and the second
    date will be at 00:00 in the first day in the following month, as we are measuring historic
    data a month back and forward to todays date its not 
    an issue that the we have a future end date.
    
    Both dates include the time zone name, or `Z` in case of UTC.
    Including these will allow the API to handle DST correctly. 

    When asking for measurements, the `from` datetime is inclusive
    and the `to` datetime is exclusive.
    """
    from_dt = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    to_dt = (from_dt + timedelta(days=31)).replace(day=1)
    return (from_dt.isoformat() + " " + TIME_ZONE, 
            to_dt.isoformat() + " " + TIME_ZONE)

def get_from_to_datetime(days=1):
    """Get a period
    This will return two dates in ISO 8601:2004 format
    The first date will be at 00:00 today, and the second
    date will be at 00:00 n days ahead of now.

    Both dates include the time zone name, or `Z` in case of UTC.
    Including these will allow the API to handle DST correctly. 

    When asking for measurements, the `from` datetime is inclusive
    and the `to` datetime is exclusive. 
    """
    from_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_dt = from_dt + timedelta(days=days)

    return (from_dt.isoformat() + " " + TIME_ZONE, 
            to_dt.isoformat() + " " + TIME_ZONE)

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
                        node_name = "%s %s" % (node_name, room["name"])

            if MeasurementType.TEMPERATURE in node.measurement_types():
                devices.append(
                    NgenicTempSensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        timedelta(minutes=5),
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
                        timedelta(minutes=5),
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
                        timedelta(minutes=1),
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
                        timedelta(minutes=10),
                        MeasurementType.ENERGY_KWH
                    )
                )
                devices.append(
                    NgenicEnergySensorMonth(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        timedelta(minutes=20),
                        MeasurementType.ENERGY_KWH
                    )
                )

    for device in devices:
        # Initial update (will not update hass state)
        await device._async_update()

        # Setup update interval
        async_track_time_interval(hass, device._async_update, device._update_interval)

    # Add entities to hass (and trigger a state update)
    async_add_entities(devices, update_before_add=True)

class NgenicSensor(Entity):
    """Representation of an Ngenic Sensor"""
    
    def __init__(self, hass, ngenic, node, name, update_interval, measurement_type):
        self._hass = hass
        self._state = None
        self._ngenic = ngenic
        self._name = name
        self._node = node
        self._update_interval = update_interval
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
        """An update is pushed when device is updated"""
        return False

    async def _async_update(self, event_time=None):
        """Execute the update asynchronous"""
        await self._hass.async_add_executor_job(self._update)


    def _fetch_ngenic_api_update(self):
        """Make the acctual API call to NGenic API """
        current = self._node.measurement(self._measurement_type)
        return round(current["value"], 1)

    def _update(self, event_time=None):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("NgenicSensor._update getting API state for %s %s" % (self._name, self._measurement_type))
        new_state = self._fetch_ngenic_api_update()
        
        if self._state != new_state:
            self._state = new_state
            _LOGGER.debug("NgenicSensor._update got updated state %f for %s %s" % (new_state, self._name, self._measurement_type))
            # self.hass is loaded once the entity have been setup.
            # Since this method is executed before adding the entity
            # the hass object might not have been loaded yet. 
            if self.hass:
                # Tell hass that an update is available
                self.schedule_update_ha_state()
        else:
            _LOGGER.debug("NgenicSensor._update NOT updated state %f for %s %s" % (new_state, self._name, self._measurement_type))


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
        return POWER_WATT

    def _fetch_ngenic_api_update(self):
        """Fetch new power state data for the sensor.
        The NGenic API returns a float with kW but HA huses W so we need to multiply by 1000
        """
        current = self._node.measurement(self._measurement_type)
        return round(current["value"]*1000.0, 1)


        
class NgenicEnergySensor(NgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    def _fetch_ngenic_api_update(self):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _update method.
        """
        from_dt, to_dt = get_from_to_datetime()
        # using datetime will return a list of measurements
        # we'll use the last item in that list
        current = self._node.measurement(self._measurement_type, from_dt, to_dt, "P1D")
        return round(current[-1]["value"], 1)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, "energy")

class NgenicEnergySensorMonth(NgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    def _fetch_ngenic_api_update(self):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _update method.
        """
        from_dt, to_dt = get_from_to_datetime_month()

        # using datetime will return a list of measurements
        # we'll use the last item in that list
        # dont send any period so the response includes the whole timespan
        current = self._node.measurement(self._measurement_type, from_dt, to_dt)
        return round(current[-1]["value"], 1)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, "monthly energy")

    @property
    def unique_id(self):
        return "%s-%s-%s-month" % (self._node.uuid(), self._measurement_type.name, "sensor")
