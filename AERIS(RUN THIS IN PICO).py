from machine import Pin, SPI, I2C
import ssd1306
import time, network, urequests, math, socket, ntptime, random


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

print("=== WELCOME TO AERIS ===")

# ======================
# HARDWARE
# ======================
spi = SPI(0, baudrate=1000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
dc, res, cs = Pin(16, Pin.OUT), Pin(20, Pin.OUT), Pin(17, Pin.OUT)
oled = ssd1306.SSD1306_SPI(128, 64, spi, dc, res, cs)

i2c = I2C(0, scl=Pin(5), sda=Pin(4))
MPU_ADDR = 0x68

i2c.writeto_mem(MPU_ADDR, 0x6B, b'\x00')
print("[MPU] Ready")

# ======================
# CONFIG
# ======================
activity_pulse = 0.05
prev_mag = 0

smoothed_vol = 5.0
last_audio_trigger = 0
ENDEL_LOCK_TIME = 5   
transition_alpha = 0.0

# ======================
# WIFI
# ======================
ssid, password, city = "Janko天空糖", "JCytoooo", "Montreal"

def wifi_connect():
    print("[WIFI] Connecting...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    for i in range(60):
        if wlan.isconnected():
            print("[WIFI] Connected:", wlan.ifconfig()[0])
            return wlan
        print(f"[WIFI] Waiting... {i}s")
        time.sleep(1)

    print("[WIFI] FAILED")
    return None

wifi_connect()

# ======================
# TIME
# ======================
try:
    print("[NTP] Sync...")
    ntptime.settime()
    print("[NTP] OK")
except:
    print("[NTP] Failed")

# ======================
# WEATHER
# ======================
def get_temp():
    print("[API] Fetch weather...")
    try:
        r = urequests.get(f"http://wttr.in/{city}?format=%t")
        t = int(r.text.replace("°C",""))
        print("[API] Temp:", t)
        r.close()
        return t
    except Exception as e:
        print("[API] ERROR", e)
        return 20

temp = get_temp()

# ======================
# UDP AUDIO
# ======================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.setblocking(False)
print("[UDP] Listening on 5005")

# ======================
# MPU
# ======================
def read_motion():
    global prev_mag, activity_pulse
    
    data = i2c.readfrom_mem(MPU_ADDR, 0x3B, 6)
    ax = int.from_bytes(data[0:2], 'big', True)
    ay = int.from_bytes(data[2:4], 'big', True)
    az = int.from_bytes(data[4:6], 'big', True)

    mag = abs(ax) + abs(ay) + abs(az)

    delta = abs(mag - prev_mag)
    prev_mag = mag

    # 🔥 sensitivity boost
    motion = delta / 2000  

    activity_pulse += (motion - activity_pulse) * 0.2
    activity_pulse = max(0.01, min(1.0, activity_pulse))

    if int(time.time()) % 2 == 0:
        print(f"[MPU] Δ:{delta:.0f} pulse:{activity_pulse:.2f}")

# ======================
# TIME LOGIC
# ======================
def is_night():
    h = time.localtime()[3]
    m = time.localtime()[4]
    return (h > 19 or (h == 19 and m >= 30)) or (h < 6)

# ======================
# DRAW 
# ======================
phase1=phase2=phase3=wave_phase=0
stars = [[random.randint(0,127), random.randint(0,63)] for _ in range(15)]
snow = [[random.randint(0,127), random.randint(0,63)] for _ in range(12)]

MOON_DOTS = [
    (110, 10), (111, 10), (112, 10), 
    (109, 11), (109, 12), (109, 13), 
    (110, 14), (111, 14), (112, 14), 
    (111, 12)                        
]

def draw_crescent_moon():
    for x, y in MOON_DOTS:
        oled.pixel(x, y, 1)
def draw_night(speed):
    for s in stars:
        oled.pixel(int(s[0]), int(s[1]), 1)
        s[1]+=0.01+speed*0.15
        if s[1]>63: s[1],s[0]=0,random.randint(0,127)
    draw_crescent_moon()
def draw_snow(speed):
    for s in snow:
        oled.pixel(int(s[0]), int(s[1]), 1)
        s[1]+=0.05+speed*0.5
        if s[1]>63: s[1],s[0]=0,random.randint(0,127)

def draw_waves(speed):
    global wave_phase
    for x in range(128):
        y=int(40+3*math.sin(x/12+wave_phase))
        oled.pixel(x,y,1)
    wave_phase+=0.01+speed*0.1

def draw_endel(vol, speed):
    global phase1,phase2,phase3,smoothed_vol
    
    smoothed_vol += (vol - smoothed_vol)*0.2
    amp = 4 + smoothed_vol/20

    for x in range(128):
        y = 32 + amp*math.sin(x/18+phase1) + 3*math.sin(x/7+phase2)
        if math.sin(x/5+phase3) > -0.2:
            oled.pixel(x,int(y),1)

    # ⚠️ speed comes from AUDIO, not MPU
    phase1 += 0.01 + vol*0.002
    phase2 += 0.015
    phase3 += 0.04

# ======================
# MAIN LOOP
# ======================
print("[SYSTEM] Running...")

while True:

    read_motion()

    # ------------------
    # UDP RECEIVE FIXED
    # ------------------
    volume = 0
    try:
        data, addr = sock.recvfrom(32)
        volume = int(data.decode().strip())
        last_audio_trigger = time.time()
        print(f"[UDP] {volume} from {addr}")
    except:
        pass

    # ------------------
    # MODE LOGIC
    # ------------------
    in_endel = (time.time() - last_audio_trigger) < ENDEL_LOCK_TIME

    oled.fill(0)

    if in_endel:
        draw_endel(volume if volume>0 else 5, volume)
    else:
        if is_night():
            draw_night(activity_pulse)
        elif temp <= 0:
            draw_snow(activity_pulse)
        else:
            draw_waves(activity_pulse)

    oled.show()
    time.sleep(0.01)