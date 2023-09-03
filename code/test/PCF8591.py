#!/usr/bin/python
'''
**********************************************************************
* Filename    : PCF8591
* Description : A module to read the analog value with ADC PCF8591
* Author      : Dream
* Brand       : SunFounder
* E-mail      : service@sunfounder.com
* Website     : www.sunfounder.com
* Update      : Dream    2016-09-19    New release
**********************************************************************
'''

import smbus
import time
import math

class PCF(object):
    AD_CHANNEL = [0x43, 0x42, 0x41, 0x40]
    RPI_REVISION_4_MODULE_B = ["c03115"]

    _DEBUG = False
    _DEBUG_INFO = 'DEBUG "PCA9685.py":'

    def _get_bus_number(self):
        pi_revision = self._get_pi_revision()
        print(f"2. {pi_revision}")
        if pi_revision == '4 Module B':
            return 1

    def _get_pi_revision(self):
        "Gets the version number of the Raspberry Pi board"
        # Courtesy quick2wire-python-api
        # https://github.com/quick2wire/quick2wire-python-api
        # Updated revision info from: http://elinux.org/RPi_HardwareHistory#Board_Revision_History
        try:
            f = open('/proc/cpuinfo','r')
            for line in f:
                if line.startswith('Revision'):
                    if line[11:-1] in self.RPI_REVISION_4_MODULE_B:
                        print("1. success return 4 module B")
                        return '4 Module B'
                    else:
                        print("Error. Pi revision didn't recognize, module number: %s" % line[11:-1])
                        print('Exiting...')
                        quit()
        except Exception as e:
            f.close()
            print(e)
            print('Exiting...')
            quit()
        finally:
            f.close()

    def __init__(self, address=0x48, bus_number=1):
        self.address = address
        self._bus_number = bus_number
        self.bus = smbus.SMBus(self._bus_number)

    def read(self, chn): #channel
        self.bus.write_byte(self.address, self.AD_CHANNEL[chn])
        self.bus.read_byte(self.address) # dummy read to start conversion
        return self.bus.read_byte(self.address)
    
    @property
    def A0(self):
        return self.read(0)
    @property
    def A1(self):
        return self.read(1)
    @property
    def A2(self):
        return self.read(2)
    @property
    def A3(self):
        return self.read(3)
    


if __name__ == '__main__':
    import time

    ADC = PCF(0x48)
    while True:
        A0 = ADC.read(0)
        A1 = ADC.read(1)
        A2 = ADC.read(2)

        print("A0 = %d  A1 = %d  A2 = %d"%(A0,A1,A2))
        time.sleep(0.5)