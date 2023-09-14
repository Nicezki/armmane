import os
from loguru import logger
try:
    import TFmane as tfm
except:
    from app import sysmane as smn



class ArmMane:  
    def __init__(self,sysmane):
        self.sysmane = sysmane
        # self.tfmane = tfm.TFMane(self.sysmane)



    if __name__ == "__main__":
        # Print Red Error Message
        print("[ERR] Armmane is a library, please run the program from server.py file.")
        exit(0)
