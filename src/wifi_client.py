# MicroPython helper for ESP32 AGV. Copy to ESP32 as wifi_client.py.
# Configure WIFI_SSID, WIFI_PASSWORD and SERVER_IP before running.
import network
import socket
import json
import time

WIFI_SSID = 'YOUR_WIFI_NAME'
WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
SERVER_IP = '192.168.1.100'  # Laptop IPv4 address from ipconfig
SERVER_PORT = 5000
DEVICE_ID = 'AGV01'

_wlan = network.WLAN(network.STA_IF)


def connect_wifi(timeout_ms=10000):
    try:
        _wlan.active(True)
        if _wlan.isconnected():
            return True
        _wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        start = time.ticks_ms()
        while not _wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            time.sleep_ms(250)
        return _wlan.isconnected()
    except Exception as exc:
        print('[WiFi] connect error:', exc)
        return False


def wifi_connected():
    try:
        return _wlan.active() and _wlan.isconnected()
    except Exception:
        return False


def _request(method, path, payload=None, timeout_s=0.8):
    if not wifi_connected():
        return None
    sock = None
    try:
        body = b'' if payload is None else json.dumps(payload).encode()
        addr = socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1]
        sock = socket.socket()
        sock.settimeout(timeout_s)
        sock.connect(addr)
        headers = '%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n' % (method, path, SERVER_IP)
        if payload is not None:
            headers += 'Content-Type: application/json\r\nContent-Length: %d\r\n' % len(body)
        sock.send((headers + '\r\n').encode() + body)
        chunks = []
        while True:
            try:
                part = sock.recv(512)
                if not part:
                    break
                chunks.append(part)
            except Exception:
                break
        raw = b''.join(chunks)
        split = raw.find(b'\r\n\r\n')
        if split < 0:
            return None
        status_line = raw.split(b'\r\n', 1)[0]
        if b' 200 ' not in status_line and b' 201 ' not in status_line:
            return None
        return json.loads(raw[split + 4:].decode())
    except Exception:
        return None
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def send_telemetry(status, weight_g=None, load_level='UNKNOWN', distance_cm=None, alert='', warehouse=''):
    payload = {'device_id': DEVICE_ID, 'status': status, 'weight_g': weight_g,
               'load_level': load_level, 'distance_cm': distance_cm,
               'alert': alert, 'warehouse': warehouse}
    return _request('POST', '/api/telemetry', payload) is not None


def send_delivery(trip_id, warehouse, load_level, weight_before, weight_after):
    payload = {'trip_id': trip_id, 'warehouse': warehouse, 'load_level': load_level,
               'weight_before': weight_before, 'weight_after': weight_after}
    result = _request('POST', '/api/delivery', payload, timeout_s=1.2)
    return result if result and result.get('ok') else None


def get_command():
    result = _request('GET', '/api/command/' + DEVICE_ID, timeout_s=0.6)
    return result.get('command') if result else None
