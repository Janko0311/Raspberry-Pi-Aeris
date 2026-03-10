import sounddevice as sd
import numpy as np
import socket
#################
#      ###      #
#      ###      #
#      ###      #
#      ###      #CHANGE your PICO IP at line 14
#      ###      #You can see your ip in Pico console
#               #
#      ###      #
#      ###      #
#################
PICO_IP = "172.20.10.9"  
PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def callback(indata, frames, time, status):

    volume = np.linalg.norm(indata)

    level = int(min(volume * 200, 255))

    sock.sendto(str(level).encode(), (PICO_IP, PORT))

stream = sd.InputStream(
    device="BlackHole 16ch",
    channels=2,
    samplerate=44100,
    callback=callback
)

with stream:
    print("Streaming audio level...")
    while True:
        pass