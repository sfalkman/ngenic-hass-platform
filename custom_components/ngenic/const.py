from datetime import timedelta

DOMAIN = "ngenic"
DATA_CLIENT = "data_client"
DATA_CONFIG = "config"

"""
How often to re-scan sensor information.
From API doc: Tune system Nodes generally report data in intervals of five 
minutes, so there is no point in polling the API for new data at a higher rate.
"""
SCAN_INTERVAL = timedelta(seconds=(60 * 5))

CONF_CREATE_UTILITY_METERS = "create_utility_meters"
CONF_CREATE_CURRENT_MONTH_SENSOR = "create_current_month_sensor"
CONF_CREATE_PREVIOUS_MONTH_SENSOR = "create_previous_month_sensor"
