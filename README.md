# Ngenic Sensor Platform for Home Assistant
This platform adds sensors for Ngenic Tune smart thermostat, Ngenic temperature sensors, and Ngenic Track nodes. 

This is an inofficial Ngenic integration which relies on Ngenic Tune API which is offered as a free cloud service for Ngenic owners. It can currently report temperature, humidity, power and energy-consumption to Home Assistant.

Ngenic thermostat and all Ngenic sensors use a propriatory wireless protocol and requires an Ngenic Gateway (RF to Ethernet bridge):

* https://ngenic.se/en/
  * https://ngenic.se/en/tune/
  * https://ngenic.se/en/track/

## Installation
You can manually install this integration as an custom_component under Home Assistant or install it using HACS (Home Assistant Community Store).

### Manual installation
Copy the `custom_components/ngenic` folder to your `<home assistant folder>/custom_components/ngenic`

### HACS installation
The repository is compatible with HACS (Home Assistant Community Store). 

Install HACS and add the repository to the Custom repositories under HACS Settings tab.

* https://hacs.xyz/docs/installation/manual
  * https://hacs.xyz/docs/basic/getting_started
## Prerequisite
### Obtain an API token
An API token may be obtained from Ngenic here: https://developer.ngenic.se/

## Configuration
Configure via UI: Configuration > Integrations

### Home Energy Management
If you have an [Ngenic Track](https://ngenic.se/track/) you may track your energy consumption with [_Energy Management_ in Home Assistant](https://www.home-assistant.io/blog/2021/08/04/home-energy-management/).

There's one thing to consider: if your Ngenic Track is placed on the central electricity meter for your whole house then you should add the _Ngenic energy sensor_ as a _Grid consumption_. However if your Track is placed on something else (such as specific energy meter only connected to your heat pump), you should instead add the _Ngenic energy sensor_ as an _Individual device_.
