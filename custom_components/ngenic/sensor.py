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
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from homeassistant.components.utility_meter.sensor import UtilityMeterSensor
from homeassistant.components.utility_meter.const import (
    HOURLY as UTILITY_METER_TYPE_HOURLY,
    DAILY as UTILITY_METER_TYPE_DAILY,
    MONTHLY as UTILITY_METER_TYPE_MONTHLY,
    QUARTERLY as UTILITY_METER_TYPE_QUARTERLY,
    WEEKLY as UTILITY_METER_TYPE_WEEKLY,
    YEARLY as UTILITY_METER_TYPE_YEARLY
)

import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    DATA_CLIENT,
    SCAN_INTERVAL,
    CONF_CREATE_UTILITY_METERS,
    CONF_CREATE_CURRENT_MONTH_SENSOR,
    CONF_CREATE_PREVIOUS_MONTH_SENSOR
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

def get_from_to_datetime_last_month():
    """Get a period for last month.
    This will return two dates in ISO 8601:2004 format
    The first date will be at 00:00 in the first of last month, and the second
    date will be at 00:00 in the first day in this month.
    
    Both dates include the time zone name, or `Z` in case of UTC.
    Including these will allow the API to handle DST correctly. 

    When asking for measurements, the `from` datetime is inclusive
    and the `to` datetime is exclusive.
    """
    to_dt = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    from_dt = (to_dt + timedelta(days=-1)).replace(day=1)
    return (from_dt.isoformat() + " " + TIME_ZONE, 
            to_dt.isoformat() + " " + TIME_ZONE)


def get_from_to_datetime_total():
    """Get a period from 2000-01-01 until now
    This will return two dates in ISO 8601:2004 format
    
    Both dates include the time zone name, or `Z` in case of UTC.
    Including these will allow the API to handle DST correctly. 

    When asking for measurements, the `from` datetime is inclusive
    and the `to` datetime is exclusive.
    """
    from_dt = datetime.now().replace(year=2000, hour=0, minute=0, second=0, microsecond=0)
    to_dt = datetime.now().replace(microsecond=0)

    return (from_dt.isoformat() + " " + TIME_ZONE, 
            to_dt.isoformat() + " " + TIME_ZONE)

async def get_measurement_value(node, **kwargs):
    """Get measurement 
    This is a wrapper around the measurement API to gather
    parsing and error handling in a single place.
    """
    measurement = await node.async_measurement(**kwargs)
    if not measurement:
        # measurement API will return None if no measurements were found for the period
        _LOGGER.info("Measurement not found for period, this is expected when data have not been gathered for the period (type=%s, from=%s, to=%s)" % 
            (
                kwargs.get("measurement_type", "unknown"), 
                kwargs.get("from_dt", "None"), 
                kwargs.get("to_dt", "None")
            )
        )
        measurement_val = 0
    else:
        if isinstance(measurement, list):
            # using datetime will return a list of measurements
            # we'll use the last item in that list
            measurement_val = measurement[-1]["value"]
        else:
            measurement_val = measurement["value"]

    return measurement_val

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    ngenic = hass.data[DOMAIN][DATA_CLIENT]

    devices = []

    for tune in await ngenic.async_tunes():
        rooms = await tune.async_rooms()

        for node in await tune.async_nodes():
            node_name = "Ngenic %s" % node.get_type().name.lower()

            if node.get_type() == NodeType.SENSOR:
                # If this sensor is connected to a room
                # we'll use the room name as the sensor name
                for room in rooms:
                    if room["nodeUuid"] == node.uuid():
                        node_name = "%s %s" % (node_name, room["name"])

            measurement_types = await node.async_measurement_types()
            if MeasurementType.TEMPERATURE in measurement_types:
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
            
            if MeasurementType.HUMIDITY in measurement_types:
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

            if MeasurementType.POWER_KW in measurement_types:
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

            if MeasurementType.ENERGY_KWH in measurement_types:
                energy_sensor = NgenicEnergySensor(
                    hass,
                    ngenic,
                    node,
                    node_name,
                    timedelta(minutes=10),
                    MeasurementType.ENERGY_KWH
                )
                devices.append(energy_sensor)

                if config_entry.options.get(CONF_CREATE_UTILITY_METERS, False):
                    utility_meter_source_entity_id = generate_entity_id(ENTITY_ID_FORMAT, energy_sensor.name, None, hass)

                    def add_utility_meter(meter_type):
                        devices.append(NgenicUtilityMeterSensor(
                            utility_meter_source_entity_id,
                            "%s %s %s" % (energy_sensor.name, "meter", meter_type),
                            meter_type,
                            timedelta(0),
                            False
                        ))
                    add_utility_meter(UTILITY_METER_TYPE_YEARLY)
                    add_utility_meter(UTILITY_METER_TYPE_MONTHLY)
                    add_utility_meter(UTILITY_METER_TYPE_DAILY)
                    add_utility_meter(UTILITY_METER_TYPE_HOURLY)

                if config_entry.options.get(CONF_CREATE_CURRENT_MONTH_SENSOR, True):
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
                
                if config_entry.options.get(CONF_CREATE_PREVIOUS_MONTH_SENSOR, True):
                    devices.append(
                        NgenicEnergySensorLastMonth(
                            hass,
                            ngenic,
                            node,
                            node_name,
                            timedelta(minutes=60),
                            MeasurementType.ENERGY_KWH
                        )
                    )


            if MeasurementType.CONTROL_VALUE in measurement_types:
                devices.append(
                    NgenicControlTempSensor(
                        hass,
                        ngenic,
                        node,
                        node_name,
                        timedelta(minutes=5),
                        MeasurementType.CONTROL_VALUE
                    )
                )

    for device in devices:
        if isinstance(device, NgenicSensor):
            # Skip updating RestoreStateNgenicSensor
            # Since that is handled by the sensor it
            if not isinstance(device, RestoreStateNgenicSensor):
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

    async def _async_fetch_measurement(self):
        """Fetch the measurement data from ngenic API.
        Return measurement formatted as intended to be displayed in hass.
        Concrete classes should override this function if they
        fetch or format the measurement differently.
        """
        current = await get_measurement_value(self._node, measurement_type=self._measurement_type)
        return round(current, 1)

    async def _async_update(self, event_time=None):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Fetch measurement (name=%s, type=%s)" % (self._name, self._measurement_type))
        new_state = await self._async_fetch_measurement()
        
        if self._state != new_state:
            self._state = new_state
            _LOGGER.debug("New measurement: %f (name=%s, type=%s)" % (new_state, self._name, self._measurement_type))
            
            # self.hass is loaded once the entity have been setup.
            # Since this method is executed before adding the entity
            # the hass object might not have been loaded yet. 
            if self.hass:
                # Tell hass that an update is available
                self.schedule_update_ha_state()
        else:
            _LOGGER.debug("No new measurement (old=%f, name=%s, type=%s)" % (new_state, self._name, self._measurement_type))

class RestoreStateNgenicSensor(NgenicSensor, RestoreEntity):
    """Representation of an Ngenic Sensor with RestoreState"""

    def __init__(self, hass, ngenic, node, name, update_interval, measurement_type):
        NgenicSensor.__init__(self, hass, ngenic, node, name, update_interval, measurement_type)

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        try:
            value = state and float(state.state)
        except ValueError:
            value = None

        _LOGGER.debug("restore from restore_state (name=%s, value=%s)" %
                      (self._name, value))

        self._state = value

        # Trigger update is no cached state was found
        if value is None:
            await self._async_update()

    async def async_will_remove_from_hass(self):
        """Call when entity is being removed from Home Assistant."""
        await super().async_will_remove_from_hass()

class NgenicTempSensor(NgenicSensor):
    device_class = DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

class NgenicControlTempSensor(NgenicTempSensor):

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, "control value")

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

    async def _async_fetch_measurement(self):
        """Fetch new power state data for the sensor.
        The NGenic API returns a float with kW but HA huses W so we need to multiply by 1000
        """
        current = await get_measurement_value(self._node, measurement_type=self._measurement_type)
        return round(current*1000.0, 1)
        
class NgenicEnergySensor(RestoreStateNgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    async def _async_fetch_measurement(self):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _async_fetch_measurement method.
        """
        from_dt, to_dt = get_from_to_datetime_total()
        # using datetime will return a list of measurements
        # we'll use the last item in that list
        current = await get_measurement_value(self._node, measurement_type=self._measurement_type, from_dt=from_dt, to_dt=to_dt)
        return round(current, 1)
        
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

    async def _async_fetch_measurement(self):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _async_fetch_measurement method.
        """
        from_dt, to_dt = get_from_to_datetime_month()
        # using datetime will return a list of measurements
        # we'll use the last item in that list
        # dont send any period so the response includes the whole timespan
        current = await get_measurement_value(self._node, measurement_type=self._measurement_type, from_dt=from_dt, to_dt=to_dt)
        return round(current, 1)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, "monthly energy")

    @property
    def unique_id(self):
        return "%s-%s-%s-month" % (self._node.uuid(), self._measurement_type.name, "sensor")

class NgenicEnergySensorLastMonth(NgenicSensor):
    device_class = DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    async def _async_fetch_measurement(self):
        """Ask for measurements for a duration.
        This requires some further inputs, so we'll override the _async_fetch_measurement method.
        """
        from_dt, to_dt = get_from_to_datetime_last_month()
        current = await get_measurement_value(self._node, measurement_type=self._measurement_type, from_dt=from_dt, to_dt=to_dt)
        return round(current, 1)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "%s %s" % (self._name, "last month energy")

    @property
    def unique_id(self):
        return "%s-%s-%s-last-month" % (self._node.uuid(), self._measurement_type.name, "sensor")

class NgenicUtilityMeterSensor(UtilityMeterSensor):
    """Utility Meters used by Ngenic sensors"""

    @property
    def unique_id(self):
        return "ngenic-utility-meter-%s" % (self._name)
