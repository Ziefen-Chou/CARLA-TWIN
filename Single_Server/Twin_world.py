#!/usr/bin/env python
"""
Twin World (CARLA2) receiver with collision counting.
- Reconstructs vehicles/walkers from scheduler data
- Tracks collisions per vehicle using sensor.other.collision
- Logs positions and outputs collision summary at shutdown
"""
import glob, os, sys, time, socket, pickle, struct, csv

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

RECV_PORT   = 9999   # from scheduler
CARLA2_PORT = 2100   # CARLA2 simulator port

vehicle_map   = {}   # id -> vehicle actor
walker_map    = {}   # id -> walker actor
sensor_map    = {}   # id -> collision sensor actor
collision_cnt = {}   # id -> collision count
last_col_time = {}   # id -> last collision time
COLLISION_WINDOW = 5.0  # seconds

# ───────────────────────────────────────── helper ─────────────────────────────

def receive_exact(sock, size):
    data = b''
    while len(data) < size:
        pkt = sock.recv(size - len(data))
        if not pkt: return None
        data += pkt
    return data

# attach collision sensor ------------------------------------------------------

def attach_collision_sensor(world, parent, actor_id):
    blueprint = world.get_blueprint_library().find('sensor.other.collision')
    sensor = world.try_spawn_actor(blueprint, carla.Transform(), attach_to=parent)
    if not sensor:
        print(f"[Sensor] failed to attach collision sensor to id={actor_id}")
        return

    def _on_col(event):
        now = time.time()
        prev = last_col_time.get(actor_id, 0)
        if now - prev > COLLISION_WINDOW:
            collision_cnt[actor_id] = collision_cnt.get(actor_id, 0) + 1
            print(f"[Collision] id={actor_id}, total={collision_cnt[actor_id]}")
            last_col_time[actor_id] = now
    sensor.listen(_on_col)
    sensor_map[actor_id] = sensor

# spawn / sync actor -----------------------------------------------------------

def sync_actor(world, actor_map, state, is_vehicle=True):
    aid = state['id']
    loc = carla.Location(*state['loc']); rot = carla.Rotation(*state['rot'])
    tf  = carla.Transform(loc, rot)

    if aid not in actor_map:
        bp_id = state.get('bp') or state.get('blueprint')
        bp = world.get_blueprint_library().find(bp_id)
        if bp.has_attribute('color') and state.get('color'):
            bp.set_attribute('color', state['color'])
        actor = world.try_spawn_actor(bp, tf)
        if actor:
            if is_vehicle:
                actor.set_autopilot(False)
                attach_collision_sensor(world, actor, aid)
            actor_map[aid] = actor
    else:
        actor = actor_map[aid]
        actor.set_transform(tf)
        if is_vehicle and 'vel' in state:
            actor.set_target_velocity(carla.Vector3D(*state['vel']))

# ───────────────────────────────────── main routine ───────────────────────────

def carla2_main():
    client = carla.Client('127.0.0.1', CARLA2_PORT); client.set_timeout(10)
    world  = client.get_world()
    settings = world.get_settings(); settings.synchronous_mode = True; settings.fixed_delta_seconds = 0.02
    world.apply_settings(settings)

    print(f"[CARLA2] listening on {RECV_PORT}…")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(('0.0.0.0', RECV_PORT)); srv.listen(1)
    conn, addr = srv.accept(); print(f"[CARLA2] connected from {addr}")

    csvf = open('twin_vehicle_log_pod4.csv','w',newline=''); writer = csv.writer(csvf)
    writer.writerow(['timestamp','id','x','y','z'])

    try:
        while True:
            hdr = receive_exact(conn,4)
            if not hdr: break
            ln  = struct.unpack('>I', hdr)[0]
            data = receive_exact(conn, ln)
            if not data: break
            states = pickle.loads(data)

            # init dict --------------------------------------------------
            if isinstance(states, dict) and states.get('init'):
                for ent in states.get('vehicles', []):
                    sync_actor(world, vehicle_map, ent, ent['type']=='vehicle')
                print(f"[CARLA2] init {len(vehicle_map)} vehicles from packet")
                world.tick(); continue

            # regular list ----------------------------------------------
            ts = None
            for ent in states:
                if ent['type']=='vehicle' and 'physical_timestamp' in ent:
                    ts = ent['physical_timestamp']; break
            if ts is None:
                ts = world.get_snapshot().timestamp.elapsed_seconds

            for ent in states:
                if ent['type']=='vehicle': sync_actor(world, vehicle_map, ent, True)
                elif ent['type']=='walker': sync_actor(world, walker_map, ent, False)

            for vid, act in vehicle_map.items():
                loc = act.get_transform().location
                writer.writerow([ts, vid, loc.x, loc.y, loc.z])
            csvf.flush()
            world.tick()

    except Exception as e:
        print(f"[CARLA2 Error] {e}")

    finally:
        print("[CARLA2] cleanup …")
        for s in sensor_map.values():
            try: s.stop(); s.destroy()
            except: pass
        for a in list(vehicle_map.values())+list(walker_map.values()):
            try: a.destroy()
            except: pass
        world.apply_settings(carla.WorldSettings())
        conn.close(); srv.close(); csvf.close()
        with open('collision_summary.csv','w',newline='') as f:
            csw = csv.writer(f); csw.writerow(['id','collision_count'])
            for k,v in collision_cnt.items(): csw.writerow([k,v])
        print("[CARLA2] shutdown complete")

if __name__ == '__main__':
    carla2_main()