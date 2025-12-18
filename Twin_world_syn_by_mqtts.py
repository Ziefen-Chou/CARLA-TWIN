from __future__ import print_function

import glob
import os
import sys
import time
from datetime import datetime

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla
import atexit
import paho.mqtt.client as mqtt
import json
import threading

# Dictionaries to store vehicle objects and their last update times
generated_vehicles = {}
last_update_times = {}

# Timeout duration for vehicle inactivity (in seconds)
VEHICLE_TIMEOUT = 10


def create_vehicle(world, vehicle_info, car_id):
    """Create a vehicle in CARLA for a specific car ID."""
    global generated_vehicles, last_update_times

    if car_id in generated_vehicles:
        print(f"Vehicle for {car_id} already exists.")
        return

    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.find(vehicle_info['model'])

    if vehicle_bp is None:
        print(f"Blueprint for model {vehicle_info['model']} not found.")
        return

    if vehicle_bp.has_attribute('color') and 'color' in vehicle_info:
        vehicle_bp.set_attribute('color', vehicle_info['color'])

    spawn_point = carla.Transform(
        carla.Location(
            x=vehicle_info['location']['x'],
            y=vehicle_info['location']['y'],
            z=vehicle_info['location']['z']
        ),
        carla.Rotation(
            pitch=vehicle_info['rotation']['pitch'],
            yaw=vehicle_info['rotation']['yaw'],
            roll=vehicle_info['rotation']['roll']
        )
    )

    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
    if vehicle is None:
        print(f"Failed to spawn vehicle {car_id}. Check the spawn point.")
    else:
        generated_vehicles[car_id] = vehicle
        last_update_times[car_id] = datetime.now()
        vehicle.set_simulate_physics(True)
        print(f"Vehicle {car_id} spawned successfully at {spawn_point.location}")


def update_vehicle_state(vehicle, state, car_id):
    """Update the state of a specific vehicle."""
    global last_update_times

    if vehicle is None:
        print(f"No vehicle available to update for {car_id}.")
        return

    # Update vehicle's transform (location and rotation)
    location = carla.Location(
        x=state['location']['x'],
        y=state['location']['y'],
        z=state['location']['z']
    )
    rotation = carla.Rotation(
        pitch=state['rotation']['pitch'],
        yaw=state['rotation']['yaw'],
        roll=state['rotation']['roll']
    )
    transform = carla.Transform(location, rotation)
    vehicle.set_transform(transform)

    # Update vehicle velocity using apply_control
    control = carla.VehicleControl()

    if 'velocity' in state:
        velocity = state['velocity']
        # Set throttle based on x-velocity (scale this as needed)
        control.throttle = min(max(velocity['x'] / 10.0, 0.0), 1.0)
        # Set steering to 0 for simplicity (modify as needed for actual turning)
        control.steer = 0.0
        control.brake = 0.0
        print(f"Applied control for car {car_id}: throttle={control.throttle}, velocity={velocity}")
    else:
        print(f"Warning: No velocity information for car {car_id}. Applying default control.")
        control.throttle = 0.0
        control.brake = 1.0  # Apply brakes if no velocity is provided

    vehicle.apply_control(control)
    last_update_times[car_id] = datetime.now()  # Update the last update time


def destroy_inactive_vehicles(world):
    """Destroy vehicles that haven't received updates for a specified timeout."""
    global generated_vehicles, last_update_times

    current_time = datetime.now()
    to_remove = []

    for car_id, last_update in last_update_times.items():
        elapsed_time = (current_time - last_update).total_seconds()
        if elapsed_time > VEHICLE_TIMEOUT:
            print(f"Destroying vehicle {car_id} due to inactivity ({elapsed_time:.1f} seconds).")
            vehicle = generated_vehicles[car_id]
            vehicle.destroy()
            to_remove.append(car_id)

    for car_id in to_remove:
        del generated_vehicles[car_id]
        del last_update_times[car_id]


def on_message(client, userdata, message):
    """Callback function for processing incoming MQTT messages."""
    global generated_vehicles

    # Decode and parse the received message
    payload = message.payload.decode('utf-8')
    print(f"Raw message payload: {payload}")

    try:
        vehicle_info = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON message: {e}")
        return

    topic = message.topic
    car_id = topic.split('/')[-1]  # Extract car_id from topic
    print(f"Received message for car ID: {car_id}")

    world = userdata['world']

    if car_id not in generated_vehicles and 'model' in vehicle_info:
        print(f"Creating vehicle for {car_id}...")
        create_vehicle(world, vehicle_info, car_id)
    elif car_id in generated_vehicles:
        print(f"Updating vehicle for {car_id}...")
        update_vehicle_state(generated_vehicles[car_id], vehicle_info, car_id)

def destroy_all_vehicles():
    """Destroy all vehicles in the simulation."""
    global generated_vehicles
    print("Destroying all vehicles before exit...")
    for car_id, vehicle in generated_vehicles.items():
        print(f"Destroying vehicle {car_id}...")
        vehicle.destroy()
    generated_vehicles.clear()

def start_receiver_mqtt(broker, port, topic_prefix, username, password, client_id):
    """Start the MQTT receiver for multiple topics with MQTTS."""
    global generated_vehicles, last_update_times

    carla_client = carla.Client('127.0.0.1', 2000)
    carla_client.set_timeout(10.0)
    world = carla_client.get_world()

    client = mqtt.Client(client_id=client_id, userdata={'world': world})
    client.username_pw_set(username, password)
    client.tls_set()
    client.on_message = on_message
    client.connect(broker, port, 60)

    # Subscribe to all car-related topics
    topic = f"{topic_prefix}/#"
    client.subscribe(topic)
    print(f"Subscribed to MQTT topic: {topic}")

    def periodic_cleanup():
        while True:
            destroy_inactive_vehicles(world)
            time.sleep(1)  # Check every second

    # Start a thread for periodic cleanup
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("MQTT receiver stopped.")
    finally:
        destroy_all_vehicles()  # Ensure all vehicles are destroyed

# Register cleanup function at exit
atexit.register(destroy_all_vehicles)

if __name__ == "__main__":
    MQTT_BROKER = "your mqtt.broker address"
    MQTT_PORT = 8883
    MQTT_TOPIC_PREFIX = "carla"
    MQTT_USERNAME = "your mqtt username"
    MQTT_PASSWORD = "your mqtt password"
    MQTT_CLIENT_ID = "carla_receiver"

    start_receiver_mqtt(
        broker=MQTT_BROKER,
        port=MQTT_PORT,
        topic_prefix=MQTT_TOPIC_PREFIX,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        client_id=MQTT_CLIENT_ID
    )


