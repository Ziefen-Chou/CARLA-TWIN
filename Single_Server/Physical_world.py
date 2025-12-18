#!/usr/bin/env python
# CARLA1 Sender - Robust, timestamped, multi-run safe + graceful shutdown

import glob, os, sys, time, argparse, socket, threading, pickle, csv, copy
from numpy import random

try:
    sys.path.append(
        glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
            sys.version_info.major, sys.version_info.minor,
            'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

def get_blueprints(world, filt, gen="All"):
    bps = world.get_blueprint_library().filter(filt)
    if gen.lower() == "all": return bps
    try: return [bp for bp in bps if int(bp.get_attribute('generation')) == int(gen)]
    except: return bps

def clean_world(client, world):
    actors = world.get_actors()
    todel = [a.id for a in actors.filter('vehicle.*')] + [a.id for a in actors.filter('walker.pedestrian.*')]
    if todel:
        client.apply_batch([carla.command.DestroyActor(x) for x in todel])
        world.tick()
        time.sleep(0.3)
        print(f"[Clean] Destroyed {len(todel)} actors")

def extract_actor_states(world, v_ids, w_ids):
    actors = world.get_actors(); data = []
    for vid in v_ids:
        a = actors.find(vid)
        if a:
            tf, vel = a.get_transform(), a.get_velocity()
            data.append({
                'id': vid, 'type': 'vehicle', 'bp': a.type_id,
                'color': a.attributes.get('color'),
                'loc': (tf.location.x, tf.location.y, tf.location.z),
                'rot': (tf.rotation.pitch, tf.rotation.yaw, tf.rotation.roll),
                'vel': (vel.x, vel.y, vel.z)
            })
    for w in w_ids:
        a = actors.find(w['id'])
        if a:
            tf = a.get_transform()
            data.append({
                'id': w['id'], 'type': 'walker', 'bp': a.type_id,
                'loc': (tf.location.x, tf.location.y, tf.location.z),
                'rot': (tf.rotation.pitch, tf.rotation.yaw, tf.rotation.roll)
            })
    return data

def start_sender(world, vehicles, walkers, ip='127.0.0.1', port=8999, shutdown_event=None):
    def run():
        log_path = 'physical_vehicle_log4.csv'
        with open(log_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp','id','x','y','z'])
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                print(f"[Sender] Connected to scheduler at {ip}:{port}")

                ts0 = world.get_snapshot().timestamp.elapsed_seconds
                init_payload = extract_actor_states(world, vehicles, walkers)
                for e in init_payload: e['physical_timestamp'] = ts0
                blob = pickle.dumps({'init': True, 'vehicles': init_payload})
                sock.sendall(len(blob).to_bytes(4, 'big') + blob)
                print(f"[Sender] Init packet sent ({len(init_payload)} entities)")

                while not shutdown_event.is_set():
                    ts = world.get_snapshot().timestamp.elapsed_seconds
                    data = extract_actor_states(world, vehicles, walkers)
                    for e in data:
                        e['physical_timestamp'] = ts
                        if e['type'] == 'vehicle':
                            x, y, z = e['loc']
                            writer.writerow([ts, e['id'], x, y, z])
                    f.flush()
                    blob = pickle.dumps(copy.deepcopy(data))
                    try:
                        sock.sendall(len(blob).to_bytes(4, 'big') + blob)
                    except BrokenPipeError:
                        print("[Sender] Scheduler closed connection. Shutting down sender...")
                        shutdown_event.set()
                        break
                    time.sleep(0.02)
            except Exception as e:
                print(f"[Sender Error] {e}")
                shutdown_event.set()
            finally:
                sock.close()
    threading.Thread(target=run, daemon=True).start()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n','--number-of-vehicles',type=int,default=100)
    parser.add_argument('-w','--number-of-walkers',type=int,default=0)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('-p','--port',type=int,default=2000)
    parser.add_argument('--tm-port',type=int,default=8000)
    parser.add_argument('--scheduler-ip',default='127.0.0.1')
    parser.add_argument('--scheduler-port',type=int,default=8999)
    args = parser.parse_args()

    client = carla.Client(args.host, args.port); client.set_timeout(10)
    world = client.get_world()
    clean_world(client, world)

    tm = client.get_trafficmanager(args.tm_port)
    tm.set_synchronous_mode(True)
    tm.set_respawn_dormant_vehicles(False)
    tm.set_global_distance_to_leading_vehicle(2.5)

    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.02
    world.apply_settings(settings)

    v_bps = get_blueprints(world, 'vehicle.*', 'All')
    w_bps = get_blueprints(world, 'walker.pedestrian.*', '2')
    spawn_pts = world.get_map().get_spawn_points()

    vehicles, walkers = [], []
    for sp in spawn_pts[:args.number_of_vehicles]:
        bp = random.choice(v_bps)
        if bp.has_attribute('color'):
            bp.set_attribute('color', random.choice(bp.get_attribute('color').recommended_values))
        v = world.try_spawn_actor(bp, sp)
        if v:
            vehicles.append(v.id)
            v.set_autopilot(True, args.tm_port)

    for _ in range(args.number_of_walkers):
        loc = world.get_random_location_from_navigation()
        if loc:
            tf = carla.Transform(loc)
            bp = random.choice(w_bps)
            w = world.try_spawn_actor(bp, tf)
            if w: walkers.append({'id': w.id})

    world.tick()

    shutdown_event = threading.Event()
    start_sender(world, vehicles, walkers, args.scheduler_ip, args.scheduler_port, shutdown_event)

    print(f"[CARLA1] Running with {len(vehicles)} vehicles, {len(walkers)} walkers.")
    try:
        while not shutdown_event.is_set():
            world.tick()
    except KeyboardInterrupt:
        print("[CARLA1] KeyboardInterrupt received. Shutting down...")
    finally:
        client.apply_batch([carla.command.DestroyActor(x) for x in vehicles])
        client.apply_batch([carla.command.DestroyActor(w['id']) for w in walkers])
        print("[CARLA1] Cleanup complete.")

if __name__ == '__main__':
    main()