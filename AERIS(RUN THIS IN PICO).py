from machine import Pin, SPI
import ssd1306
import time
import network
import urequests
import math
import socket
import ntptime
import random
#################
#      ###      #
#      ###      #
#      ###      #
#      ###      # IMPORTANT: Please Edit the Wifi SSID and password in Line 46
#      ###      #
#               #
#      ###      #
#      ###      #
#################

# ======================
# 1.HARDWARE SETUP
# ======================
spi = SPI(0, baudrate=1000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
dc, res, cs = Pin(16, Pin.OUT), Pin(20, Pin.OUT), Pin(17, Pin.OUT)
oled = ssd1306.SSD1306_SPI(128, 64, spi, dc, res, cs)

pir = Pin(0, Pin.IN)

#Configuration
UTC_OFFSET = -5
activity_pulse = 0.01
presence_timeout = 60
is_awake = False
last_motion_time = time.time()

#Audio animation smoothness control
smoothed_vol = 5.0        # This will slide instead of jump
last_audio_trigger = 0
ENDEL_LOCK_TIME = 10      
transition_alpha = 0.0    
grace_period_start = 0
GRACE_DURATION = 4        

# ======================
# 2.NETWORK!!!!!!!!!!!  IMPORTANT:Edit the ssid and password for your Wifi (Enterprise WLAN is not supported,home router/hotspot recommend)
# ======================
ssid, password, city = "Janko天空糖", "JCytoooo", "Montreal"

def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    oled.fill(0); oled.text("WiFi Connecting", 0, 0); oled.show()
    
    max_wait = 20
    while max_wait > 0 and not wlan.isconnected():
        max_wait -= 1; time.sleep(1)
    
    if wlan.isconnected():
        #connected
        ip = wlan.ifconfig()[0]
        print("========================================")
        print(f"WiFi Connection Successful!")
        print(f"SSID: {ssid}")
        print(f"IP Address: {ip}")
        print("========================================")
        return wlan
    else:
        print("WiFi Connection Failed.")
        return None

wlan = wifi_connect()
try: ntptime.settime()
except: pass

def get_temp():
    try:
        r = urequests.get(f"http://wttr.in/{city}?format=%t", timeout=5)
        t = int(r.text.strip().replace("°C",""))
        r.close()
        return t
    except: return 20 

temp = get_temp()
last_temp_update = time.time()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.setblocking(False)

# ======================
# 3. UTILITIES
# ======================

def update_presence():
    global activity_pulse, last_motion_time, is_awake
    raw_motion = pir.value()
    if raw_motion == 1:
        activity_pulse = min(1.0, activity_pulse + 0.02) 
        last_motion_time = time.time()
        if not is_awake:
            is_awake = True
            for i in range(0, 255, 15): oled.contrast(i); time.sleep(0.01)
    else:
        activity_pulse = max(0.01, activity_pulse - 0.01)
        
    if time.time() - last_motion_time > presence_timeout:
        if is_awake:
            for i in range(255, -1, -15): oled.contrast(i); time.sleep(0.01)
            is_awake = False
    return is_awake

def get_local_hour():
    return time.localtime(time.time() + (UTC_OFFSET * 3600))[3]

# ======================
# 4. DRAWING
# ======================
phase1, phase2, phase3, wave_phase = 0, 0, 0, 0
stars = [[random.randint(0,127), random.randint(0,63)] for _ in range(15)]
snow = [[random.randint(0,127), random.randint(0,63)] for _ in range(12)]

def draw_nature(speed, hr, t):
    global wave_phase
    if hr >= 22 or hr < 6: # Night
        mx, my = 100, 12
        for y in range(-4,5):
            for x in range(-4,5):
                if x*x + y*y <= 16: oled.pixel(mx+x, my+y, 1)
                if (x-2)*(x-2) + y*y <= 16: oled.pixel(mx+x, my+y, 0)
        for s in stars:
            oled.pixel(int(s[0]), int(s[1]), 1)
            s[1] += (0.01 + speed * 0.15)
            if s[1] > 63: s[1], s[0] = 0, random.randint(0,127)
    elif t <= 0: # Snow
        for s in snow:
            oled.pixel(int(s[0]), int(s[1]), 1)
            s[1] += (0.05 + speed * 0.5); s[0] += (0.02 + speed * 0.25)
            if s[1]>63: s[1], s[0] = 0, random.randint(0,127)
    else: # Waves
        for x in range(128):
            y = int(40 + 3 * math.sin(x/12 + wave_phase))
            oled.pixel(x,y,1)
        wave_phase += (0.01 + speed * 0.1)

def draw_endel(vol_target, speed):
    """Smoothed fragmented animation."""
    global phase1, phase2, phase3, grace_period_start, smoothed_vol
    
    # 1. LERP volume
    # This prevents 'jumping' pixels. It moves only 10% toward target each frame.
    lerp_factor = 0.1
    smoothed_vol += (vol_target - smoothed_vol) * lerp_factor

    if grace_period_start == 0: grace_period_start = time.time()
    time_since_start = time.time() - grace_period_start
    
    if time_since_start < GRACE_DURATION:
        curr_amp, curr_speed = 8, 0.02
    else:
        # Intensity is tied to smoothed_vol
        curr_amp = 4 + (smoothed_vol / 20.0)
        curr_speed = speed

    for x in range(0, 128, 1):
        # Using floating point math for wave generation
        y_val = 32 + (curr_amp * math.sin(x/18 + phase1)) + (3 * math.sin(x/7 + phase2))
        
        mask = math.sin(x/5 + phase3)
        if mask > -0.2:
            oled.pixel(x, int(y_val), 1)
            if x % 8 == 0 and mask > 0.6: 
                oled.pixel(x, int(y_val + 2), 1)

    # These speed increase very small to ensure no 'jitter'
    phase1 += (0.008 + curr_speed * 0.1)
    phase2 += (0.015 + curr_speed * 0.05)
    phase3 += 0.04 

# ======================
# 5. MAIN LOOP
# ======================
while True:
    if not update_presence():
        grace_period_start = 0; time.sleep(1); continue

    target_volume = 0
    try:
        data, addr = sock.recvfrom(32)
        target_volume = int(data.decode())
        if target_volume > 3:
            if (time.time() - last_audio_trigger) > ENDEL_LOCK_TIME:
                grace_period_start = time.time()
            last_audio_trigger = time.time()
    except: pass

    oled.fill(0)
    
    in_endel_window = (time.time() - last_audio_trigger) < ENDEL_LOCK_TIME
    
    if in_endel_window:
        transition_alpha = min(1.0, transition_alpha + 0.03) 
    else:
        transition_alpha = max(0.0, transition_alpha - 0.03)
        grace_period_start = 0

    if transition_alpha < 0.9:
        draw_nature(activity_pulse, get_local_hour(), temp)
        
    if transition_alpha > 0.1:
        # Pass the raw target, the function handles the smoothing
        draw_endel(target_volume if target_volume > 0 else 5, activity_pulse)

    oled.show()
    time.sleep(0.01)