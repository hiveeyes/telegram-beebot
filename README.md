# telegram-beebot
A service making hive data and event submission available for a Telegram bot instance

## Setting up a Telegam Bot instance: see here

## Functionality:
* Hiveeyes MQTT subscription is currently only possible to single topics
* TTN MQTT subscription optional
* send a daily summary (weight + daily delta) at sunset or custom time
* requesting weight and battery voltage
* configurable vocabulary for weights and battery voltage of the Hiveeyes universe
* requesting Grafana graphics
* log events into InfluxDB based Grafana annotations
* rudimentary support for sending uplinks to a TTN device (depends on LoRa device firmware)

## Commands:
* `/weights` print current weight and delta compared to last time the command was invoked. also prints Date+Time of latest data package
old data is saved in a file to survive script restarts
* the `/weights` command lists more commands for showing Grafana graphics which are configurable by subsections of the URL. Currently linked to my dashboard.
* `/enable_daily` Without arguments: set a daily timer for summary which prints current weight + daily delta + todays sunset time. Sunset is calculated from lon/lat position and weight from last summary is also stored in a local file. Command accepts hour and minute for a custom time, e.g. /event 20 15
* `/batteries` print current battery voltage when available
* `/event` send event (title and text) via MQTT to Kotori which will appear in Grafana (Dashboard needs configuration to retrieve the events from an InfluxDB events series)
* `/sleep` for LoRa firmware ready to set up a one-time sleep duration

## ToDo:
* For beekeepers observing multiple hives extend the output dynamically depending on the number of hives recognized through the MQTT subscription.
* include graphic of weight development into daily summary
