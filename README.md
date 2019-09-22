# Ngenic Sensor Platform for Home Assistant
This platform adds sensors for Ngenic Tune nodes that report temperature and humidity.

## Prerequisite
### Obtain an API token
An API token may be obtained here: https://developer.ngenic.se/

## Configuration
```yaml
sensors:
  platform: ngenic
  token: "YOUR-API-TOKEN"
```