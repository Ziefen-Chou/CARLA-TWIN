import socket
import json
import threading
import paho.mqtt.client as mqtt
import random
import time  # simulate transmission delay

# MQTT configuration
MQTT_BROKER = "your mqtt.broker address"  
MQTT_PORT = 8883 
MQTT_USERNAME = "your mqtt username"  
MQTT_PASSWORD = "your mqtt password" 
MQTT_CLIENT_ID = "carla_sender" 
MQTT_TOPIC_PREFIX = "carla/publish" 

# packet drop probability setting
DROP_PACKET_PROBABILITY = 0.0

# delay setting in seconds
TRANSMISSION_DELAY = 0.15  # manageable delay for testing

# initialize MQTT client
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)  
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)  

# configure TLS for secure connection
mqtt_client.tls_set()  
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
print(f"Connected to MQTTS broker at {MQTT_BROKER}:{MQTT_PORT}")


def handle_client(conn, addr):
    print(f"Connected to {addr}")
    try:
        while True:
            data = conn.recv(1024) 
            if not data:
                break

            # analyze received data (assuming JSON format)
            vehicle_data = json.loads(data.decode('utf-8'))

            # check if vehicle_data contains "model"
            if "model" not in vehicle_data:
                # simulate packet drop
                if random.random() < DROP_PACKET_PROBABILITY:
                    print(f"Dropped packet from {addr}: {vehicle_data}")
                    continue  # drop current packet

            # simulate delay
            if TRANSMISSION_DELAY > 0:
                print(f"Simulating delay of {TRANSMISSION_DELAY} seconds for {vehicle_data}")
                time.sleep(TRANSMISSION_DELAY)  # delay transmission

            # mqtt topic based on vehicle ID
            car_id = vehicle_data.get("car_id", "unknown")  
            mqtt_topic = f"{MQTT_TOPIC_PREFIX}/{car_id}"

            # publish to MQTT
            mqtt_message = json.dumps(vehicle_data)  # ensure it's JSON format
            mqtt_client.publish(mqtt_topic, mqtt_message)
            print(f"Data from {addr} published to MQTT topic {mqtt_topic}: {vehicle_data}")
    except Exception as e:
        print(f"Connection error with {addr}: {e}")
    finally:
        print(f"Connection closed: {addr}")
        conn.close()


def start_server(host='127.0.0.1', port=5005):
    """start the TCP server to receive vehicle data"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(10) 
    print(f"Server running on {host}:{port}")

    try:
        while True:
            conn, addr = server_socket.accept() # accept new connection
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()  # start a new thread for each client
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()
