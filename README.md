# CARLA-TWIN

# Prerequisites
## CARLA
This framework is built upon the open-source CARLA simulator. To reproduce this environment, CARLA must first be installed on a local server. While pre-compiled versions are available at https://carla.org/, we recommend building CARLA from source to ensure full compatibility and access to customizable features, as detailed in https://carla.readthedocs.io/en/latest/build_carla/.
## Message Queue Telemetry Transport Protocol (MQTT)
Communication between CARLA instances is handled via MQTTS (encrypted MQTT). We recommend setting up a self-hosted MQTT broker; however, commercial cloud platforms like HiveMQ or EMQX are viable alternatives. Note that while these platforms often provide free access for unencrypted traffic (port 1883), encrypted connections (port 8883) usually involve additional costs.

# Running Logic
## ComDef_Syn_by_MQTT.py
## Physical_Auto.py
## Physical_Manual.py
## Twin_world_syn_by_mqtts.py
