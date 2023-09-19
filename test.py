from app.serimane import SeriMane
from app.sysmane import SysMane
import threading
import time

# Create the SysMane and SeriMane objects
sysmane = SysMane()
serimane = SeriMane(sysmane)

# Start the obstacle detection thread
obstacle_thread = threading.Thread(target=serimane.detectObstacle)
obstacle_thread.daemon = True
obstacle_thread.start()

serimane.sendMessageToArduino("PS")
time.sleep(1)
serimane.sendMessageToArduino("R")

while True:
    # Message prompt
    message = input("Enter message: ")
    if message == "exit":
        break
    serimane.sendMessageToArduino(message)
