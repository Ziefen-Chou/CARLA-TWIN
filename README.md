<div align="center">
  <h1>CARLA-Twin: A Large-Scale Digital Twin Platform for Advanced Networking Research</h1>

  <a href="https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=11152793"><img src="https://img.shields.io/badge/Paper-blue"></a>
</div>

# Overview
CARLA-Twin facilitates networking research for Digital Twins by utilizing a dual-computer CARLA architecture. In this setup, one CARLA instance represents the physical world and the other acts as the twin, connected through a bidirectional MQTT communication bridge. The framework allows researchers to define network impairments, such as latency and packet loss, to evaluate how communication constraints impact DT synchronization and application-level performance.
<div align="center">
  <img src="https://i.postimg.cc/W4vpqtLv/effect-ezgif-com-video-to-gif-converter.gif" width="100%" alt="CARLA-Twin Demo">
  <p align="center">Figure: Demonstration of CARLA-Twin Synchronization.</p>
</div>

# Prerequisites
## CARLA
This framework is built upon the open-source CARLA simulator. To reproduce this environment, CARLA must first be installed on a local server. While pre-compiled versions are available at https://carla.org/, we recommend building CARLA from source to ensure full compatibility and access to customizable features, as detailed in https://carla.readthedocs.io/en/latest/build_carla/.
## Message Queue Telemetry Transport Protocol (MQTT)
Communication between CARLA instances is handled via MQTTS (encrypted MQTT). We recommend setting up a self-hosted MQTT broker; however, commercial cloud platforms like HiveMQ or EMQX are viable alternatives. Note that while these platforms often provide free access for unencrypted traffic (port 1883), encrypted connections (port 8883) usually involve additional costs.

# Running Logic
## ComDef_Syn_by_MQTT.py
Please first run this file. This script receives state data from the physical world CARLA and forwards it to the twin world CARLA. It includes configurable parameters for packet loss and transmission latency, allowing users to investigate how different communication flaws affect the system's performance.
## Physical_Auto.py
This script populates the physical world CARLA with autonomous vehicles and captures state data, such as position, speed, and collision logs. The collected data is then transmitted to the MQTT broker to enable communication with the twin world CARLA.
## Physical_Manual.py
This is the manual control version of the physical world CARLA.
## Twin_world_syn_by_mqtts.py
This script subscribes to the MQTT broker to retrieve state data from the physical world CARLA. It then populates the twin world CARLA environment with corresponding vehicles, maintaining real-time synchronisation of their positions and speeds.
