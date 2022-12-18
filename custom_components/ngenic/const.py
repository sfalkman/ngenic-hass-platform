from datetime import timedelta

DOMAIN = "ngenic"
DATA_CLIENT = "data_client"
DATA_CONFIG = "config"

SERVICE_SET_ACTIVE_CONTROL = "set_active_control"

"""
How often to re-scan sensor information.
From API doc: Tune system Nodes generally report data in intervals of five 
minutes, so there is no point in polling the API for new data at a higher rate.
"""
SCAN_INTERVAL = timedelta(minutes=5)
