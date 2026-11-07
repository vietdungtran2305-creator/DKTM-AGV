from machine import Pin, PWM, time_pulse_us, disable_irq, enable_irq
from time import sleep_ms, sleep_us, ticks_ms, ticks_diff
import json
import socket

try:
    import network
    import config
    NETWORK_AVAILABLE = True
except Exception:
    network = None
    config = None
    NETWORK_AVAILABLE = False

try:
    import _thread
except Exception:
    _thread = None


# =========================================================
# 1. THONG SO PROFILE - GIU CAC GIA TRI TUNE HIEN TAI
# =========================================================
PROFILES = {
    "NONE": dict(
        BASE_SPEED=30, SEARCH_SPEED=44, SHARP_SPEED=48,
        MIN_DUTY=12,
        TRIM_LF=1.0, TRIM_LB=1.0, TRIM_RF=1.0, TRIM_RB=1.0,
        CROSS_CENTER_SPEED=26,
        CROSS_CENTER_MS_L=170, CROSS_CENTER_MS_R=170,
        CROSS_TURN_SPEED_L=50, CROSS_TURN_SPEED_R=51,
        CROSS_LEAVE_MIN_MS_L=580, CROSS_LEAVE_MIN_MS_R=580,
        CROSS_LEAVE_MAX_MS_L=680, CROSS_LEAVE_MAX_MS_R=680,
    ),
    "LIGHT": dict(
        BASE_SPEED=30, SEARCH_SPEED=47, SHARP_SPEED=50,
        MIN_DUTY=13,
        TRIM_LF=1.0, TRIM_LB=1.0, TRIM_RF=1.0, TRIM_RB=1.0,
        CROSS_CENTER_SPEED=27,
        CROSS_CENTER_MS_L=170, CROSS_CENTER_MS_R=170,
        CROSS_TURN_SPEED_L=52, CROSS_TURN_SPEED_R=65,
        CROSS_LEAVE_MIN_MS_L=580, CROSS_LEAVE_MIN_MS_R=580,
        CROSS_LEAVE_MAX_MS_L=680, CROSS_LEAVE_MAX_MS_R=680,
    ),
    "HEAVY": dict(
        BASE_SPEED=31, SEARCH_SPEED=50, SHARP_SPEED=52,
        MIN_DUTY=14,
        TRIM_LF=1.0, TRIM_LB=1.0, TRIM_RF=1.0, TRIM_RB=1.0,
        CROSS_CENTER_SPEED=28,
        CROSS_CENTER_MS_L=170, CROSS_CENTER_MS_R=170,
        CROSS_TURN_SPEED_L=65, CROSS_TURN_SPEED_R=60,
        CROSS_LEAVE_MIN_MS_L=580, CROSS_LEAVE_MIN_MS_R=580,
        CROSS_LEAVE_MAX_MS_L=680, CROSS_LEAVE_MAX_MS_R=680,
    ),
}


# =========================================================
# 2. CAM BIEN LINE TCRT5000 - 5 MAT
# Black = 0, white = 1
# =========================================================
Sensor = [
    Pin(32, Pin.IN, Pin.PULL_UP),
    Pin(33, Pin.IN, Pin.PULL_UP),
    Pin(34, Pin.IN),
    Pin(35, Pin.IN),
    Pin(25, Pin.IN, Pin.PULL_UP),
]
LINE_BLACK = 0


# =========================================================
# 3. TB6612FNG
# =========================================================
PWM_FREQ = 10000
AIN1 = Pin(26, Pin.OUT, value=0)
AIN2 = Pin(27, Pin.OUT, value=0)
PWMA = PWM(Pin(23), freq=PWM_FREQ, duty_u16=0)
BIN1 = Pin(18, Pin.OUT, value=0)
BIN2 = Pin(19, Pin.OUT, value=0)
PWMB = PWM(Pin(14), freq=PWM_FREQ, duty_u16=0)
STBY = Pin(13, Pin.OUT, value=0)


# =========================================================
# 4. HC-SR04
# =========================================================
SONAR_TRIG = Pin(21, Pin.OUT, value=0)
SONAR_ECHO = Pin(22, Pin.IN)


# =========================================================
# 5. LOAD CELL + HX711
# =========================================================
SCALE_DOUT_PIN = 16
SCALE_SCK_PIN = 17
CALIBRATION_FACTOR = 945.5705

SCALE_TOTAL_VALUES = 10
SCALE_FINAL_AVERAGE_COUNT = 5
SCALE_ZERO_THRESHOLD_G = 1.0
SCALE_MAX_SPREAD_G = 1.0
SCALE_MAX_LOAD_G = 120.0
SCALE_LIGHT_LIMIT_G = 50.0
SCALE_READ_COUNT = 10
SCALE_EMPTY_G = 1.0

UNLOAD_WAIT_MS = 5000

hx_dout = Pin(SCALE_DOUT_PIN, Pin.IN)
hx_sck = Pin(SCALE_SCK_PIN, Pin.OUT, value=0)


# =========================================================
# 6. THONG SO MOTOR VA PD LINE
# =========================================================
MIN_DUTY = 12
TRIM_LF = 1.0
TRIM_LB = 1.0
TRIM_RF = 1.0
TRIM_RB = 1.0
MAX_SPEED = 70

BASE_SPEED = 30
SEARCH_SPEED = 30
KP = 12
KD = 8
SHARP_SPEED = 40
PRINT_SENSOR = False
WEIGHTS = [-2, -1, 0, 1, 2]


# =========================================================
# 7. THONG SO HC-SR04
# =========================================================
SONAR_ENABLED = True
OBSTACLE_CM = 15
SONAR_INTERVAL_MS = 60
SONAR_TIMEOUT_US = 3000
OBSTACLE_CONFIRM = 2


# =========================================================
# 8. THONG SO NETWORK/FLASK (GIAM CHU KY POLL DE E-STOP NHAY TUC THI)
# =========================================================
NETWORK_TELEMETRY_INTERVAL_MS = 350
NETWORK_STATE_RETRY_MS = 200
NETWORK_TIMEOUT_S = 0.5
NETWORK_DEVICE_ID = "AGV01"


# =========================================================
# 9. THONG SO GIAO LO
# =========================================================
CROSS_ENABLED = True
CROSS_MIN_SENSORS = 4
CROSS_DETECT_WINDOW_MS = 110
CROSS_HOLD_MS = 45
CROSS_HOLD_SPEED = 20
CROSS_COOLDOWN_MS = 1200

CROSS_FORWARD_SPEED = 25
CROSS_FORWARD_MS = 170

CROSS_CENTER_SPEED = 25
CROSS_CENTER_MS_L = 170
CROSS_CENTER_MS_R = 170

CROSS_EXIT_SPEED = 20
CROSS_EXIT_MS = 100

CROSS_TURN_CATCH_SPEED = 42
CROSS_TURN_CATCH_MS = 350
CROSS_BRAKE_MS = 85


# =========================================================
# 10. BIEN TRANG THAI
# =========================================================
_last_sonar = ticks_ms()
_close_count = 0

last_error = 0.0
last_dir = 0

cross_count = 0
_black_latch_time = [-99999, -99999, -99999, -99999, -99999]
_cross_hold_start = None
_cross_cooldown_start = None

measured_weight_g = 0.0
load_mode = "NONE"
first_turn = "L"
mission_finished = False

_trip_tare_value = None
_current_trip_id = ""
_delivery_recorded = False

_net_wlan = None
_net_running = False
_net_thread_started = False
_net_status = "WAITING"
_net_weight_g = None
_net_load_level = "UNKNOWN"
_net_alert = ""
_net_warehouse = ""
_net_state_version = 0
_net_last_sent_version = -1

# Co dung khan cap nhan tu Server Flask
_estop_from_server = False

try:
    _net_lock = _thread.allocate_lock() if _thread is not None else None
except Exception:
    _net_lock = None


# =========================================================
# 11. PROFILE APPLY
# =========================================================
def apply_speed_profile(mode):
    p = PROFILES.get(mode, PROFILES["NONE"])
    globals().update(p)
    print("PROFILE:", mode,
          "| BASE:", BASE_SPEED,
          "| SEARCH:", SEARCH_SPEED,
          "| SHARP:", SHARP_SPEED,
          "| MIN_DUTY:", MIN_DUTY,
          "| CENTER L/R:", CROSS_CENTER_MS_L, "/", CROSS_CENTER_MS_R,
          "@", CROSS_CENTER_SPEED,
          "| CROSS TURN L/R:", CROSS_TURN_SPEED_L, "/", CROSS_TURN_SPEED_R)


# =========================================================
# 12. DIEU KHIEN MOTOR
# =========================================================
def _apply(pwm, in1, in2, speed, trim):
    speed = max(-MAX_SPEED, min(MAX_SPEED, speed))

    if speed == 0:
        in1.off()
        in2.off()
        pwm.duty_u16(0)
        return

    if speed > 0:
        in1.on()
        in2.off()
    else:
        in1.off()
        in2.on()

    duty = min(100, max(MIN_DUTY, abs(speed) * trim))
    pwm.duty_u16(int(duty * 65535 / 100))


def Drive(left, right):
    # Neu dang bi khoa khan cap tu Web thi khong cap xung ra motor
    if _estop_from_server:
        Stop()
        return
    STBY.on()
    _apply(PWMA, AIN1, AIN2, left, TRIM_LF if left >= 0 else TRIM_LB)
    _apply(PWMB, BIN1, BIN2, right, TRIM_RF if right >= 0 else TRIM_RB)


def Forward(left_speed=BASE_SPEED, right_speed=BASE_SPEED):
    Drive(left_speed, right_speed)


def Stop():
    PWMA.duty_u16(0)
    PWMB.duty_u16(0)
    AIN1.off()
    AIN2.off()
    BIN1.off()
    BIN2.off()


def Brake(ms=60):
    STBY.on()
    AIN1.on()
    AIN2.on()
    BIN1.on()
    BIN2.on()
    PWMA.duty_u16(65535)
    PWMB.duty_u16(65535)
    sleep_ms(ms)
    Stop()


def Shutdown():
    Stop()
    STBY.off()


# =========================================================
# HAM KIEM TRA VA DUNG KHAN CAP (E-STOP) TU WEB
# =========================================================
def wait_if_emergency_stopped(restore_status="RUN"):
    global _close_count, last_error
    if not _estop_from_server:
        return False

    Brake(100)
    Stop()
    print("[E-STOP] XE DA DUNG KHAN CAP THEO LENH TU WEB!")
    set_web_state("EMERGENCY_STOP", measured_weight_g, load_mode,
                  "Xe đã dừng khẩn cấp theo lệnh từ Trung tâm điều khiển Web!", _net_warehouse)

    while _estop_from_server:
        Stop()
        sleep_ms(50)

    print("[E-STOP] DA MO KHOA TU WEB -> TIEP TUC HANH TRINH")
    _close_count = 0
    last_error = 0.0
    set_web_state(restore_status, measured_weight_g, load_mode, "", _net_warehouse)
    return True


def sleep_with_estop_check(total_ms, restore_status="RUN"):
    start = ticks_ms()
    while ticks_diff(ticks_ms(), start) < total_ms:
        if _estop_from_server:
            wait_if_emergency_stopped(restore_status)
        sleep_ms(20)


# =========================================================
# 13. DOC CAN HX711
# =========================================================
def hx711_read():
    timeout = 1000

    while hx_dout.value() == 1:
        sleep_ms(1)
        timeout -= 1
        if timeout <= 0:
            return None

    data = 0

    for _ in range(24):
        irq = disable_irq()
        try:
            hx_sck.value(1)
            bit = hx_dout.value()
            hx_sck.value(0)
        finally:
            enable_irq(irq)
        data = (data << 1) | bit

    irq = disable_irq()
    try:
        hx_sck.value(1)
        hx_sck.value(0)
    finally:
        enable_irq(irq)

    if data & 0x800000:
        data -= 0x1000000

    return data


def scale_read_raw_average(samples=20):
    readings = []
    for _ in range(samples):
        value = hx711_read()
        if value is not None:
            readings.append(value)
        sleep_ms(5)

    if len(readings) < samples * 0.8:
        return None
    return sum(readings) / len(readings)


def scale_tare(samples=20):
    print("TRU BI: hay de ban can rong")
    zero = scale_read_raw_average(samples)

    if zero is None:
        print("LOI HX711: khong du du lieu tru bi")
        return None

    print("TRU BI XONG")
    return zero


def scale_get_weight(tare_value):
    readings = []
    for _ in range(SCALE_READ_COUNT):
        raw = hx711_read()
        if raw is not None:
            weight = (raw - tare_value) / CALIBRATION_FACTOR
            readings.append(weight)
        sleep_ms(5)

    if len(readings) < 8:
        return None

    readings.sort()
    filtered = readings[2:-2]
    if not filtered:
        return None

    weight_g = sum(filtered) / len(filtered)
    if abs(weight_g) < SCALE_ZERO_THRESHOLD_G:
        return 0.0
    return weight_g


def weigh_package(tare_value):
    samples = []
    print("DAT HANG LEN BAN CAN (toi da", int(SCALE_MAX_LOAD_G), "g)")
    print("Dang cho 10 mau on dinh; do chenh lech toi da 1.0 g")

    while True:
        if _estop_from_server:
            wait_if_emergency_stopped("WEIGHING")

        w = scale_get_weight(tare_value)

        if w is None or w <= 0.0:
            sleep_ms(50)
            continue

        if samples and (max(max(samples), w) - min(min(samples), w) > SCALE_MAX_SPREAD_G):
            print("Can dao dong > 1.0 g - thu lai tu dau")
            samples = [w]
        else:
            samples.append(w)

        print("Mau %d/%d: %.3f g" % (len(samples), SCALE_TOTAL_VALUES, w))

        if len(samples) >= SCALE_TOTAL_VALUES:
            samples = samples[-SCALE_TOTAL_VALUES:]
            spread = max(samples) - min(samples)

            if spread <= SCALE_MAX_SPREAD_G:
                last_samples = samples[-SCALE_FINAL_AVERAGE_COUNT:]
                final_weight = sum(last_samples) / len(last_samples)
                print("10 mau dat yeu cau; do rong: %.3f g" % spread)
                print("Trung binh 5 mau cuoi: %.3f g" % final_weight)

                if final_weight > SCALE_MAX_LOAD_G:
                    print("VUOT GIOI HAN", int(SCALE_MAX_LOAD_G), "g")
                    return None
                return final_weight
            print("Bo mau chua on dinh - thu lai")
            samples = []

        sleep_ms(200)


def wait_until_empty(tare_value, need=8, restore_status="WAITING"):
    print("KIEM TRA BAN CAN TRONG...")
    ok = 0
    while ok < need:
        if _estop_from_server:
            wait_if_emergency_stopped(restore_status)
        w = scale_get_weight(tare_value)
        if w is not None and abs(w) < SCALE_EMPTY_G:
            ok += 1
        else:
            ok = 0
        sleep_ms(200)
    print("BAN CAN TRONG")


# =========================================================
# 14. DOC CAM BIEN LINE
# =========================================================
def read_sensor():
    return [sensor.value() for sensor in Sensor]


# =========================================================
# 15. HC-SR04
# =========================================================
def read_distance_cm():
    SONAR_TRIG.off()
    sleep_us(2)
    SONAR_TRIG.on()
    sleep_us(10)
    SONAR_TRIG.off()
    t = time_pulse_us(SONAR_ECHO, 1, SONAR_TIMEOUT_US)
    if t < 0:
        return None
    return t / 58.0


# =========================================================
# 16. PHAT HIEN VAT CAN
# =========================================================
def obstacle_ahead():
    global _last_sonar, _close_count

    if not SONAR_ENABLED:
        return False
    if _cross_hold_start is not None:
        return False

    now = ticks_ms()
    if ticks_diff(now, _last_sonar) < SONAR_INTERVAL_MS:
        return False

    _last_sonar = now
    distance = read_distance_cm()
    if PRINT_SENSOR:
        print("Distance:", distance)

    if distance is not None and distance < OBSTACLE_CM:
        _close_count += 1
    else:
        _close_count = 0
    return _close_count >= OBSTACLE_CONFIRM


# =========================================================
# 17. NHAN DIEN GIAO LO
# =========================================================
def _reset_cross_latch():
    global _black_latch_time, _cross_hold_start
    _black_latch_time = [-99999, -99999, -99999, -99999, -99999]
    _cross_hold_start = None


def Cross_Spin(direction, speed):
    if direction == "L":
        Drive(-speed, speed)
    else:
        Drive(speed, -speed)


def check_crossroad(data):
    global _black_latch_time, _cross_hold_start, last_dir

    if not CROSS_ENABLED:
        return "NONE"

    now = ticks_ms()
    if _cross_cooldown_start is not None:
        if ticks_diff(now, _cross_cooldown_start) < CROSS_COOLDOWN_MS:
            _reset_cross_latch()
            return "NONE"

    for i in range(5):
        if data[i] == LINE_BLACK:
            _black_latch_time[i] = now

    in_win = [ticks_diff(now, _black_latch_time[i]) <= CROSS_DETECT_WINDOW_MS for i in range(5)]
    win_count = sum(1 for x in in_win if x)
    has_left = in_win[0] or in_win[1]
    has_right = in_win[3] or in_win[4]
    both_outer = in_win[0] and in_win[4] and (in_win[1] or in_win[2] or in_win[3])

    if ((win_count >= CROSS_MIN_SENSORS and has_left and has_right) or both_outer):
        _reset_cross_latch()
        return "CROSS"

    outer_left = data[0] == LINE_BLACK
    outer_right = data[4] == LINE_BLACK
    cur_black = sum(1 for v in data if v == LINE_BLACK)

    if outer_left or outer_right or cur_black >= 3:
        if outer_left and not outer_right:
            last_dir = -1
        elif outer_right and not outer_left:
            last_dir = 1
        if _cross_hold_start is None:
            _cross_hold_start = now
        if ticks_diff(now, _cross_hold_start) < CROSS_HOLD_MS:
            return "HOLD"
    else:
        if not in_win[0] and not in_win[4]:
            _cross_hold_start = None
    return "NONE"


# =========================================================
# 18. XOAY TAI GIAO LO (GL1 VA GL3)
# =========================================================
def Turn_Crossroad(direction):
    global last_error, last_dir, _cross_cooldown_start

    if _estop_from_server:
        wait_if_emergency_stopped("RUN")

    if direction == "L":
        spin_speed = CROSS_TURN_SPEED_L
        t_min = CROSS_LEAVE_MIN_MS_L
        t_max = CROSS_LEAVE_MAX_MS_L
        center_ms = CROSS_CENTER_MS_L
    else:
        spin_speed = CROSS_TURN_SPEED_R
        t_min = CROSS_LEAVE_MIN_MS_R
        t_max = CROSS_LEAVE_MAX_MS_R
        center_ms = CROSS_CENTER_MS_R

    print("[GIAO LO] 1. Tien lay tam", center_ms, "ms", "speed", CROSS_CENTER_SPEED)
    if center_ms > 0:
        Forward(CROSS_CENTER_SPEED, CROSS_CENTER_SPEED)
        sleep_ms(center_ms)

    Brake(65)
    sleep_ms(80)
    print("[GIAO LO] 2. Roi line cu, huong", direction, "speed", spin_speed)

    Cross_Spin(direction, spin_speed)
    t0 = ticks_ms()
    white = 0

    while True:
        if _estop_from_server:
            wait_if_emergency_stopped("RUN")
            Cross_Spin(direction, spin_speed)

        el = ticks_diff(ticks_ms(), t0)
        if el >= t_max:
            print("[GIAO LO] ! het t_max khi roi line cu")
            break

        d = read_sensor()
        if d[1] != LINE_BLACK and d[2] != LINE_BLACK and d[3] != LINE_BLACK:
            white += 1
        else:
            white = 0
        if el >= t_min and white >= 2:
            break
        sleep_ms(1)

    leave_ms = ticks_diff(ticks_ms(), t0)
    Cross_Spin(direction, CROSS_TURN_CATCH_SPEED)
    start_catch = ticks_ms()
    caught = False
    outer_hit_time = None

    while ticks_diff(ticks_ms(), start_catch) < CROSS_TURN_CATCH_MS:
        if _estop_from_server:
            wait_if_emergency_stopped("RUN")
            Cross_Spin(direction, CROSS_TURN_CATCH_SPEED)

        d = read_sensor()
        now = ticks_ms()
        if direction == "L":
            if d[0] == LINE_BLACK and outer_hit_time is None:
                outer_hit_time = now
            on_new_line = (d[1] == LINE_BLACK or d[2] == LINE_BLACK or
                           (outer_hit_time is not None and ticks_diff(now, outer_hit_time) >= 40))
        else:
            if d[4] == LINE_BLACK and outer_hit_time is None:
                outer_hit_time = now
            on_new_line = (d[3] == LINE_BLACK or d[2] == LINE_BLACK or
                           (outer_hit_time is not None and ticks_diff(now, outer_hit_time) >= 40))
        if on_new_line:
            caught = True
            break
        sleep_ms(1)

    catch_ms = ticks_diff(ticks_ms(), start_catch)
    Brake(CROSS_BRAKE_MS)
    sleep_ms(60)
    print("[GIAO LO] dir", direction,
          "| roi line:", leave_ms, "ms | bat line:", catch_ms,
          "ms | tong:", leave_ms + catch_ms, "| caught:", caught)

    last_error = 0.0
    last_dir = -1 if direction == "L" else 1
    _cross_cooldown_start = ticks_ms()
    _reset_cross_latch()
    if not caught:
        print("[GIAO LO] -> Chua bat duoc line moi, giao cho PD bat tiep!")
    return True


# =========================================================
# 19. XU LY 4 GIAO LO
# =========================================================
def Handle_Crossroad():
    global cross_count, mission_finished, _cross_cooldown_start
    cross_count += 1
    print("GIAO LO:", cross_count)

    if cross_count == 1:
        action = first_turn
        print("GIAO LO 1 - RE", "TRAI" if action == "L" else "PHAI")
        return Turn_Crossroad(action)

    if cross_count == 2:
        warehouse = "KHO1" if load_mode == "LIGHT" else "KHO2"
        print("GIAO LO 2 /", warehouse, "- TIEN THEM MOT CHUT ROI DUNG")
        Forward(CROSS_EXIT_SPEED, CROSS_EXIT_SPEED)
        sleep_ms(CROSS_EXIT_MS)
        Brake(100)
        Stop()

        set_web_state("WAIT_UNLOAD", measured_weight_g, load_mode, "", warehouse)
        print("GIAO LO 2 /", warehouse, "- DUNG", UNLOAD_WAIT_MS // 1000, "GIAY, LAY HANG RA")
        sleep_with_estop_check(UNLOAD_WAIT_MS, "WAIT_UNLOAD")

        record_warehouse_delivery(warehouse)

        apply_speed_profile("NONE")
        set_web_state("RUN", measured_weight_g, load_mode, "", "")
        print("GIAO LO 2 - DA GHI NHAN", warehouse, "- DI THANG TIEP")
        Forward(CROSS_FORWARD_SPEED, CROSS_FORWARD_SPEED)
        sleep_ms(CROSS_FORWARD_MS)
        Brake(65)
        sleep_ms(80)
        _cross_cooldown_start = ticks_ms()
        _reset_cross_latch()
        return True

    if cross_count == 3:
        action = first_turn
        print("GIAO LO 3 - RE LAI", "TRAI" if action == "L" else "PHAI")
        return Turn_Crossroad(action)

    print("GIAO LO 4 - TIEN THEM MOT CHUT ROI DUNG")
    Forward(CROSS_EXIT_SPEED, CROSS_EXIT_SPEED)
    sleep_ms(CROSS_EXIT_MS)
    Brake(150)
    Stop()
    _cross_cooldown_start = ticks_ms()
    _reset_cross_latch()
    mission_finished = True
    print("GIAO LO 4 - DA DUNG, KET THUC LUOT CHAY")
    return False


# =========================================================
# 20. DO LINE PD
# =========================================================
def Mode_DoLine():
    global last_error, last_dir

    data = read_sensor()
    if PRINT_SENSOR:
        print(data)

    cross_status = check_crossroad(data)
    if cross_status == "CROSS":
        Handle_Crossroad()
        return
    if cross_status == "HOLD":
        Forward(CROSS_HOLD_SPEED, CROSS_HOLD_SPEED)
        return

    black_positions = [WEIGHTS[i] for i in range(5) if data[i] == LINE_BLACK]
    if len(black_positions) == 0:
        if last_dir > 0:
            Drive(SEARCH_SPEED, -SEARCH_SPEED)
        else:
            Drive(-SEARCH_SPEED, SEARCH_SPEED)
        return

    if data[0] == LINE_BLACK and data[4] != LINE_BLACK:
        last_dir = -1
        last_error = -2.0
        Drive(-SHARP_SPEED, SHARP_SPEED)
        return

    if data[4] == LINE_BLACK and data[0] != LINE_BLACK:
        last_dir = 1
        last_error = 2.0
        Drive(SHARP_SPEED, -SHARP_SPEED)
        return

    error = sum(black_positions) / len(black_positions)
    correction = KP * error + KD * (error - last_error)
    last_error = error
    if error < -0.05:
        last_dir = -1
    elif error > 0.05:
        last_dir = 1

    left_speed = BASE_SPEED + correction
    right_speed = BASE_SPEED - correction
    if abs(left_speed) < MIN_DUTY:
        left_speed = 0
    if abs(right_speed) < MIN_DUTY:
        right_speed = 0
    Drive(left_speed, right_speed)


# =========================================================
# 21. WIFI, TELEMETRY VA NHAN LENH E-STOP NGAM
# =========================================================
def set_web_state(status, weight_g=None, load_level="UNKNOWN", alert="", warehouse=""):
    global _net_status, _net_weight_g, _net_load_level, _net_alert
    global _net_warehouse, _net_state_version
    _net_status = str(status).upper()
    _net_weight_g = weight_g
    _net_load_level = str(load_level or "UNKNOWN").upper()
    _net_alert = str(alert or "")
    _net_warehouse = str(warehouse or "")
    _net_state_version += 1
    return _net_state_version


def _update_estop_from_response(result):
    global _estop_from_server
    if not isinstance(result, dict):
        return
    if "emergency_stop" in result:
        new_flag = bool(result.get("emergency_stop"))
        if new_flag and not _estop_from_server:
            _estop_from_server = True
            Stop()  # Ngat motor ngay lap tuc tu luong mang
        elif not new_flag and _estop_from_server:
            _estop_from_server = False


def _http_json_unlocked(method, path, payload=None, timeout_s=NETWORK_TIMEOUT_S):
    if not NETWORK_AVAILABLE or _net_wlan is None:
        return None
    try:
        if not _net_wlan.isconnected():
            return None
    except Exception:
        return None

    sock = None
    try:
        body = b"" if payload is None else json.dumps(payload).encode()
        host = config.SERVER_IP
        port = config.SERVER_PORT
        address = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket()
        sock.settimeout(timeout_s)
        sock.connect(address)

        request = "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n" % (method, path, host)
        if payload is not None:
            request += "Content-Type: application/json\r\nContent-Length: %d\r\n" % len(body)
        request += "\r\n"
        sock.send(request.encode() + body)

        response = b""
        while len(response) < 4096:
            try:
                part = sock.recv(512)
            except Exception:
                break
            if not part:
                break
            response += part

        split = response.find(b"\r\n\r\n")
        if split < 0:
            return None
        status_line = response.split(b"\r\n", 1)[0]
        if b" 200 " not in status_line:
            return None
        parsed = json.loads(response[split + 4:].decode())
        _update_estop_from_response(parsed)
        return parsed
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _http_json(method, path, payload=None, timeout_s=NETWORK_TIMEOUT_S):
    if _net_lock is None:
        return _http_json_unlocked(method, path, payload, timeout_s)
    _net_lock.acquire()
    try:
        return _http_json_unlocked(method, path, payload, timeout_s)
    finally:
        _net_lock.release()


def record_warehouse_delivery(warehouse):
    global _delivery_recorded

    if _delivery_recorded:
        return True

    warehouse = str(warehouse).upper()
    wait_until_empty(_trip_tare_value, need=8, restore_status="WAIT_UNLOAD")

    payload = {
        "device_id": NETWORK_DEVICE_ID,
        "trip_id": _current_trip_id,
        "warehouse": warehouse,
        "load_level": load_mode,
        "weight_g": measured_weight_g,
        "weight_before": measured_weight_g,
    }

    while True:
        if _estop_from_server:
            wait_if_emergency_stopped("WAIT_UNLOAD")
        result = _http_json("POST", "/api/delivery", payload, timeout_s=2.0)
        if result and result.get("ok"):
            _delivery_recorded = True
            return True
        sleep_ms(500)


def _network_worker():
    global _net_wlan, _net_last_sent_version
    try:
        _net_wlan = network.WLAN(network.STA_IF)
        _net_wlan.active(True)
    except Exception:
        return

    last_telemetry = ticks_ms() - NETWORK_TELEMETRY_INTERVAL_MS

    while _net_running:
        try:
            if not _net_wlan.isconnected():
                try:
                    _net_wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                except Exception:
                    pass
                connect_start = ticks_ms()
                while (_net_running and not _net_wlan.isconnected() and
                       ticks_diff(ticks_ms(), connect_start) < 5000):
                    sleep_ms(250)
                if not _net_wlan.isconnected():
                    sleep_ms(1000)
                    continue

            now = ticks_ms()
            elapsed_telemetry = ticks_diff(now, last_telemetry)
            state_changed = _net_state_version != _net_last_sent_version
            if (elapsed_telemetry >= NETWORK_TELEMETRY_INTERVAL_MS or
                    (state_changed and elapsed_telemetry >= NETWORK_STATE_RETRY_MS)):
                version = _net_state_version
                payload = {
                    "device_id": NETWORK_DEVICE_ID,
                    "status": "EMERGENCY_STOP" if _estop_from_server else _net_status,
                    "weight_g": _net_weight_g,
                    "load_level": _net_load_level,
                    "alert": _net_alert,
                    "warehouse": _net_warehouse,
                }
                result = _http_json("POST", "/api/telemetry", payload)
                if result and result.get("ok"):
                    _net_last_sent_version = version
                last_telemetry = now
        except Exception:
            pass
        sleep_ms(40)


def start_network_worker():
    global _net_running, _net_thread_started, _net_wlan
    if not NETWORK_AVAILABLE:
        return False

    if _net_thread_started:
        return True

    _net_running = True
    if _thread is not None:
        try:
            _thread.start_new_thread(_network_worker, ())
            _net_thread_started = True
            return True
        except Exception:
            pass

    try:
        _net_wlan = network.WLAN(network.STA_IF)
        _net_wlan.active(True)
        if not _net_wlan.isconnected():
            _net_wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            start = ticks_ms()
            while (not _net_wlan.isconnected() and ticks_diff(ticks_ms(), start) < 8000):
                sleep_ms(200)
    except Exception:
        pass

    _net_thread_started = False
    return _net_wlan is not None and _net_wlan.isconnected()


def wait_for_telemetry_ack(version, timeout_ms=8000):
    global _net_last_sent_version
    if not NETWORK_AVAILABLE:
        return False

    start = ticks_ms()
    while ticks_diff(ticks_ms(), start) < timeout_ms:
        if _net_last_sent_version >= version:
            return True

        if not _net_thread_started:
            payload = {
                "device_id": NETWORK_DEVICE_ID,
                "status": _net_status,
                "weight_g": _net_weight_g,
                "load_level": _net_load_level,
                "alert": _net_alert,
                "warehouse": _net_warehouse,
            }
            result = _http_json("POST", "/api/telemetry", payload)
            if result and result.get("ok"):
                _net_last_sent_version = version
                return True
            sleep_ms(300)
        else:
            sleep_ms(40)

    return _net_last_sent_version >= version


# =========================================================
# HAM XU LY VAT CAN TU DONG
# =========================================================
def wait_for_server_resume():
    global _close_count, last_error

    alert_text = "Phát hiện vật cản. Xe đã dừng và đang chờ thông thoáng đường đi..."
    Brake(100)
    Stop()

    set_web_state("OBSTACLE_STOP", measured_weight_g, load_mode, alert_text, "")
    print("[VAT CAN] XE DA DUNG. Dang lien tuc quet cam bien sieu am...")

    while obstacle_ahead():
        if _estop_from_server:
            wait_if_emergency_stopped("OBSTACLE_STOP")
        set_web_state("OBSTACLE_STOP", measured_weight_g, load_mode, "Đang vướng vật cản — xe đang dừng.", "")
        sleep_ms(150)

    _close_count = 0
    last_error = 0.0
    set_web_state("RUN", measured_weight_g, load_mode, "", "")
    print("[VAT CAN] Duong da thoang. Tu dong tiep tuc chay line.")
    return True


# =========================================================
# 22. CAC CHE DO TEST
# =========================================================
def test_sonar():
    print("TEST_SONAR")
    while True:
        d = read_distance_cm()
        if d is None:
            print("Khong co Echo")
        else:
            print("%.1f cm" % d)
        sleep_ms(300)


def test_drive():
    print("TEST_DRIVE: chay thang 2 giay")
    sleep_ms(3000)
    Drive(BASE_SPEED, BASE_SPEED)
    sleep_ms(2000)
    Brake()


def test_sensor():
    print("TEST_SENSOR")
    while True:
        print(read_sensor())
        sleep_ms(200)


# =========================================================
# 23. CAU HINH CHUONG TRINH
# =========================================================
MODE = "RUN"
TEST_PROFILE = "NONE"


def reset_mission(after_first_cycle):
    global cross_count, mission_finished, _cross_cooldown_start
    global last_error, last_dir, _close_count
    cross_count = 0
    mission_finished = False
    last_error = 0.0
    last_dir = 0
    _close_count = 0
    _reset_cross_latch()
    if after_first_cycle:
        _cross_cooldown_start = ticks_ms()
    else:
        _cross_cooldown_start = None


def run_one_mission():
    last_sync_poll = ticks_ms()
    while not mission_finished:
        # 1. Neu khong co thread ngam thi poll nhanh moi 350ms
        if not _net_thread_started and NETWORK_AVAILABLE:
            now = ticks_ms()
            if ticks_diff(now, last_sync_poll) >= 350:
                last_sync_poll = now
                _http_json("GET", "/api/command/" + NETWORK_DEVICE_ID, None, timeout_s=0.25)

        # 2. Kiem tra co Dung Khan Cap tu Web (0ms delay)
        if _estop_from_server:
            wait_if_emergency_stopped("RUN")
            continue

        # 3. Kiem tra vat can sieu am hoac do line
        if obstacle_ahead():
            wait_for_server_resume()
        else:
            Mode_DoLine()
        sleep_ms(1)
    return True


def run_cycles():
    global measured_weight_g, load_mode, first_turn
    global _trip_tare_value, _current_trip_id, _delivery_recorded
    cycle = 0
    apply_speed_profile("NONE")
    set_web_state("WAITING", None, "UNKNOWN", "", "")

    while True:
        Stop()
        sleep_with_estop_check(1000, "WAITING")
        set_web_state("WEIGHING", None, "UNKNOWN", "", "")

        tare_value = scale_tare(20)
        if tare_value is None:
            Brake(100)
            set_web_state("SCALE_ERROR", None, "UNKNOWN", "Không thể trừ bì HX711.", "")
            return

        _trip_tare_value = tare_value

        measured_weight_g = weigh_package(tare_value)
        if measured_weight_g is None:
            set_web_state("OVERLOAD", None, "UNKNOWN", "Khối lượng vượt giới hạn cân.", "")
            wait_until_empty(tare_value, need=8, restore_status="OVERLOAD")
            continue

        if measured_weight_g <= SCALE_LIGHT_LIMIT_G:
            load_mode = "LIGHT"
            first_turn = "L"
        else:
            load_mode = "HEAVY"
            first_turn = "R"

        load_code = "H" if load_mode == "HEAVY" else "L"
        _current_trip_id = "%s-%s-%d" % (NETWORK_DEVICE_ID, load_code, ticks_ms())
        _delivery_recorded = False

        apply_speed_profile(load_mode)
        print("KHOI LUONG: %.3f g | LOAI: %s | GIAO LO 1: %s" %
              (measured_weight_g, load_mode, "TRAI" if first_turn == "L" else "PHAI"))

        weight_version = set_web_state("WAITING", measured_weight_g, load_mode, "", "")
        if not wait_for_telemetry_ack(weight_version, 8000):
            Brake(100)
            set_web_state("WIFI_LOST", measured_weight_g, load_mode,
                          "Chưa gửi được khối lượng lên máy chủ. Xe chưa khởi hành.", "")
            return

        if _estop_from_server:
            wait_if_emergency_stopped("WAITING")

        set_web_state("RUN", measured_weight_g, load_mode, "", "")
        print("FLASK DA XAC NHAN - BAT DAU HANH TRINH")
        reset_mission(cycle > 0)
        run_one_mission()
        Brake()

        cycle += 1
        print("HOAN THANH CHUYEN", cycle)
        apply_speed_profile("NONE")
        set_web_state("WAITING", None, "UNKNOWN", "", "")
        wait_until_empty(tare_value, need=8, restore_status="WAITING")


def run():
    global _net_running
    Stop()
    print("ESP32 AGV + HX711 + 4 GIAO LO | MODE =", MODE)
    set_web_state("WAITING", None, "UNKNOWN", "", "")
    start_network_worker()
    try:
        if MODE == "RUN":
            run_cycles()
        else:
            apply_speed_profile(TEST_PROFILE)
            sleep_ms(500)
            if MODE == "TEST_SONAR":
                test_sonar()
            elif MODE == "TEST_DRIVE":
                test_drive()
            elif MODE == "TEST_SENSOR":
                test_sensor()
            else:
                print("MODE khong hop le:", MODE)
    except KeyboardInterrupt:
        print("DA DUNG CTRL+C")
    finally:
        Shutdown()
        _net_running = False


if __name__ == "__main__":
    sleep_ms(2000)
    run()