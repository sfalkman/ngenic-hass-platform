import logging

from ngenicpy import Ngenic
from ngenicpy.models.node import NodeType

from homeassistant.const import (
    CONF_TOKEN,
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    ngenic = Ngenic(
        token=config[CONF_TOKEN]
    )

    devices = []

    tunes = ngenic.tunes()
    for tune in tunes:
        rooms = tune.rooms()
        nodes = tune.nodes()

        for node in nodes:
            # TODO: make _get_measurement_types public
            # TODO: Make struct out of temperature_C/humidity_relative_percent etc
            measurement_types = node._get_measurement_types()

            node_name = "Ngenic %s" % node.getType().name.lower()

            if node.getType() == NodeType.SENSOR:
                # If this sensor is connected to a room
                # we'll use the room name as the sensor name
                for room in rooms:
                    if room["nodeUuid"] == node.uuid():
                        node_name = room["name"]

            for measurement_type in measurement_types:
                _LOGGER.info("Adding Ngenic sensor with name %s and measurement of %s" % (node_name, measurement_type))

                if(measurement_type == "temperature_C"):
                    devices.append(
                        NgenicTempSensor(
                            ngenic,
                            node,
                            node_name,
                            "temperature_C"
                        )
                    )
                elif(measurement_type == "humidity_relative_percent"):
                    devices.append(
                        NgenicHumiditySensor(
                            ngenic,
                            node,
                            node_name,
                            "humidity_relative_percent"
                        )
                    )

    add_entities(devices)

class NgenicSensor(Entity):

    def __init__(self, ngenic, node, name, measurement_type):
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

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        current = self._node.latest_measurement(self._measurement_type)
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

        