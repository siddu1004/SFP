---
name: ruview
description: "Enable RuView to integrate with Home Assistant for real-time spatial sensing and vital sign monitoring. Use when working with WiFi-based spatial sensing or vital-sign monitoring through RuView."
---

> Written for SFP in its own words from the project at https://github.com/ruvnet/RuView (upstream license: MIT).

# Skill: Integrate RuView with Home Assistant

## Use this skill when
- You need to monitor presence, activity, and vital signs through walls.
- Your smart home setup uses Home Assistant as the central hub.

## What it is
This skill automates the process of setting up RuView's WiFi sensing capabilities with Home Assistant. It allows you to leverage RuView's advanced spatial intelligence features within your existing smart home ecosystem.

## Steps
1. **Install RuView Node**: Ensure that your RuView node (ESP32-based) is properly installed and configured in your environment.
2. **Enable MQTT Publisher**: Configure the RuView node to publish data using the HA-DISCO MQTT publisher.
3. **Set Up Home Assistant**: Install and configure the MQTT integration in Home Assistant.
4. **Connect RuView to Home Assistant**: Pair the RuView node with Home Assistant via the MQTT bridge.
5. **Import Blueprints**: Add starter blueprints provided by RuView for automations and monitoring.

## Checks
- Verify that the RuView node is connected to your network and publishing data.
- Ensure that Home Assistant can receive and process MQTT messages from the RuView node.
- Confirm that all entities (presence, vital signs, etc.) are correctly displayed in Home Assistant.

## Pitfalls
- **Network Interference**: WiFi interference might affect the accuracy of spatial sensing. Ensure minimal interference for optimal performance.
- **Configuration Errors**: Incorrect MQTT settings can lead to data loss or misinterpretation. Double-check configurations.
- **Privacy Concerns**: Be aware of privacy implications when using RuView's sensing capabilities. Ensure compliance with local regulations and user consent.
