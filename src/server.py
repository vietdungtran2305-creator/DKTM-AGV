# Flask server for ESP32 AGV warehouse dashboard
# Run on the laptop: py server.py
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'agv_data.sqlite3')
app = Flask(__name__)

DEVICE_ID = 'AGV01'
TELEMETRY_TIMEOUT_SECONDS = 15
RESUME_REQUEST_TIMEOUT_SECONDS = 12
OBSTACLE_STATES = {'OBSTACLE_STOP', 'WAIT_RESUME', 'EMERGENCY_STOP'}

# In-memory live state. Inventory and delivery history are persisted in SQLite.
STATE = {
    'device_id': DEVICE_ID,
    'status': 'WAITING',
    'weight_g': None,
    'load_level': 'UNKNOWN',
    'alert': '',
    'warehouse': '',
    'updated_at': None,
    'emergency_stop': False,
}
LAST_TELEMETRY_AT = None
COMMANDS = {DEVICE_ID: None}
RESUME_REQUESTED_AT = {DEVICE_ID: None}


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS deliveries (
            trip_id TEXT PRIMARY KEY,
            warehouse TEXT NOT NULL,
            load_level TEXT NOT NULL,
            weight_before REAL,
            weight_after REAL,
            delivered_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS stock (
            warehouse TEXT NOT NULL,
            load_level TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (warehouse, load_level)
        )''')
        for wh in ('KHO1', 'KHO2'):
            for level in ('LIGHT', 'HEAVY', 'OTHER'):
                db.execute(
                    'INSERT OR IGNORE INTO stock(warehouse, load_level, quantity) VALUES (?, ?, 0)',
                    (wh, level)
                )


def stock_snapshot():
    # Mỗi kho chỉ thống kê đúng loại hàng đã quy định.
    result = {'KHO1': {'total': 0}, 'KHO2': {'total': 0}}
    expected_level = {'KHO1': 'LIGHT', 'KHO2': 'HEAVY'}
    with db_connect() as db:
        rows = db.execute('SELECT warehouse, load_level, quantity FROM stock').fetchall()
        for row in rows:
            wh, level, qty = row['warehouse'], row['load_level'], row['quantity']
            if wh in expected_level and level == expected_level[wh]:
                result[wh]['total'] += qty
    return result


def recent_deliveries(limit=100):
    with db_connect() as db:
        rows = db.execute(
            '''SELECT trip_id, warehouse, load_level, weight_before, weight_after, delivered_at
               FROM deliveries ORDER BY delivered_at DESC LIMIT ?''', (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def telemetry_is_fresh(now=None):
    if LAST_TELEMETRY_AT is None:
        return False
    now = now or datetime.now()
    return (now - LAST_TELEMETRY_AT).total_seconds() <= TELEMETRY_TIMEOUT_SECONDS


def resume_request_is_pending(now=None):
    requested_at = RESUME_REQUESTED_AT.get(DEVICE_ID)
    if requested_at is None:
        return False
    now = now or datetime.now()
    return (now - requested_at).total_seconds() <= RESUME_REQUEST_TIMEOUT_SECONDS


def parse_optional_weight(value):
    if value is None or value == '':
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float('inf'), float('-inf')) or number < 0:
        return None
    return number


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/status')
def api_status():
    return jsonify({
        'state': STATE,
        'stock': stock_snapshot(),
        'deliveries': recent_deliveries(),
        'device_online': telemetry_is_fresh(),
        'resume_requested': resume_request_is_pending(),
        'server_time': datetime.now().isoformat(timespec='seconds'),
    })


@app.post('/api/telemetry')
def api_telemetry():
    global LAST_TELEMETRY_AT
    payload = request.get_json(silent=True) or {}

    for key in ('device_id', 'status', 'weight_g', 'load_level', 'alert', 'warehouse'):
        if key in payload:
            STATE[key] = payload[key]

    STATE['device_id'] = str(STATE.get('device_id') or DEVICE_ID)
    STATE['status'] = str(STATE.get('status') or 'UNKNOWN').upper().strip()
    STATE['load_level'] = str(STATE.get('load_level') or 'UNKNOWN').upper().strip()
    STATE['alert'] = str(STATE.get('alert') or '').strip()
    STATE['weight_g'] = parse_optional_weight(STATE.get('weight_g'))
    
    # Nếu server đang bật cờ dừng khẩn cấp, giữ nguyên trạng thái khẩn cấp cho xe
    if STATE.get('emergency_stop'):
        STATE['status'] = 'EMERGENCY_STOP'

    LAST_TELEMETRY_AT = datetime.now()
    STATE['updated_at'] = LAST_TELEMETRY_AT.isoformat(timespec='seconds')

    if STATE['status'] not in OBSTACLE_STATES:
        RESUME_REQUESTED_AT[DEVICE_ID] = None
    elif not STATE['alert']:
        STATE['alert'] = 'Xe phát hiện vật cản và đã dừng. Hãy kiểm tra đường đi trước khi xác nhận.'

    return jsonify({'ok': True, 'received_at': STATE['updated_at'], 'emergency_stop': STATE.get('emergency_stop', False)})


@app.post('/api/delivery')
def api_delivery():
    payload = request.get_json(silent=True) or {}
    trip_id = str(payload.get('trip_id', '')).strip()[:100]
    warehouse = str(payload.get('warehouse', '')).upper().strip()
    load_level = str(payload.get('load_level', 'OTHER')).upper().strip()

    if not trip_id or warehouse not in ('KHO1', 'KHO2'):
        return jsonify({'ok': False, 'error': 'trip_id or warehouse invalid'}), 400
    if load_level not in ('LIGHT', 'HEAVY'):
        return jsonify({'ok': False, 'error': 'Loại hàng phải là LIGHT hoặc HEAVY.'}), 400

    expected_level = {'KHO1': 'LIGHT', 'KHO2': 'HEAVY'}[warehouse]
    if load_level != expected_level:
        message = 'Kho 1 chỉ nhận hàng nhẹ.' if warehouse == 'KHO1' else 'Kho 2 chỉ nhận hàng nặng.'
        return jsonify({'ok': False, 'error': message}), 400

    weight_before = parse_optional_weight(payload.get('weight_before'))
    weight_after = parse_optional_weight(payload.get('weight_after'))
    delivered_at = datetime.now().isoformat(timespec='seconds')
    inserted = False

    with db_connect() as db:
        cur = db.execute(
            '''INSERT OR IGNORE INTO deliveries
               (trip_id, warehouse, load_level, weight_before, weight_after, delivered_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (trip_id, warehouse, load_level, weight_before, weight_after, delivered_at)
        )
        inserted = cur.rowcount == 1
        if inserted:
            db.execute(
                'UPDATE stock SET quantity = quantity + 1 WHERE warehouse = ? AND load_level = ?',
                (warehouse, load_level)
            )

    if inserted:
        STATE['status'] = 'DELIVERED'
        STATE['warehouse'] = warehouse
        STATE['alert'] = ''
        RESUME_REQUESTED_AT[DEVICE_ID] = None

    return jsonify({
        'ok': True,
        'counted': inserted,
        'duplicate': not inserted,
        'stock': stock_snapshot(),
    })


# Route xử lý nút Dừng Khẩn Cấp (E-STOP) trên Web
@app.post('/api/emergency')
def handle_emergency():
    payload = request.get_json(silent=True) or {}
    stop_flag = bool(payload.get('emergency_stop', True))
    
    STATE['emergency_stop'] = stop_flag
    if stop_flag:
        STATE['status'] = 'EMERGENCY_STOP'
        STATE['alert'] = payload.get('alert') or 'Dừng khẩn cấp kích hoạt từ Trung tâm điều khiển Web!'
        COMMANDS[DEVICE_ID] = 'stop'
    else:
        STATE['status'] = 'WAITING'
        STATE['alert'] = ''
        COMMANDS[DEVICE_ID] = 'resume'
        RESUME_REQUESTED_AT[DEVICE_ID] = datetime.now()
        
    return jsonify({
        "ok": True,
        "emergency_stop": STATE['emergency_stop'],
        "status": STATE['status']
    })


@app.post('/api/command')
def api_set_command():
    payload = request.get_json(silent=True) or {}
    device_id = str(payload.get('device_id', DEVICE_ID)).strip()
    command = str(payload.get('command', '')).lower().strip()

    if device_id != DEVICE_ID:
        return jsonify({'ok': False, 'error': 'unknown device'}), 404
    if command != 'resume':
        return jsonify({'ok': False, 'error': 'unsupported command'}), 400
    if STATE.get('status') not in OBSTACLE_STATES:
        return jsonify({'ok': False, 'error': 'Xe không ở trạng thái dừng do vật cản.'}), 409
    if not telemetry_is_fresh():
        return jsonify({'ok': False, 'error': 'Dữ liệu xe đã cũ hoặc xe mất kết nối.'}), 409

    STATE['emergency_stop'] = False
    COMMANDS[DEVICE_ID] = 'resume'
    RESUME_REQUESTED_AT[DEVICE_ID] = datetime.now()
    return jsonify({'ok': True, 'message': 'Đã gửi yêu cầu chạy tiếp.'})


@app.get('/api/command/<device_id>')
def api_get_command(device_id):
    if device_id != DEVICE_ID:
        return jsonify({'command': None, 'error': 'unknown device'}), 404
    command = COMMANDS.get(device_id)
    COMMANDS[device_id] = None  # one-shot command
    return jsonify({'command': command, 'emergency_stop': STATE.get('emergency_stop', False)})


# Mẹo: Nếu bạn muốn xóa sạch dữ liệu trong database để test lại từ đầu (về 0), 
# hãy chạy script nhỏ này hoặc xóa file agv_data.sqlite3 trong thư mục dự án.
def reset_database_for_testing():
    if os.path.exists(DB_PATH):
        try:
            with db_connect() as db:
                db.execute('DELETE FROM deliveries')
                db.execute('UPDATE stock SET quantity = 0')
                db.commit()
            print("Đã làm sạch toàn bộ cơ sở dữ liệu về 0 thành công!")
        except Exception as e:
            print("Lỗi reset DB:", e)

# Nếu bạn muốn mỗi lần bật server là dữ liệu tự động reset về 0 để test, hãy bỏ dấu # ở dòng dưới đây:
#reset_database_for_testing()

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)