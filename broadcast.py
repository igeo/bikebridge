#!/usr/bin/env python3
from bluezero import adapter, peripheral, async_tools
import struct, time

CPS_UUID = '1818'       # Cycling Power Service
MEAS_UUID = '2A63'      #   …Measurement characteristic
flags = 0x40            # bit-6 = crank-revolution data present

periph = peripheral.Peripheral(adapter.addresses()[0],
                               local_name='Pi-Power')

# Add the service & empty characteristic -----------------------------
periph.add_service(srv_id=1, uuid=CPS_UUID, primary=True)
periph.add_characteristic(srv_id=1, chr_id=1, uuid=MEAS_UUID,
                          value=[], notifying=True,
                          flags=['notify'])

# State we must keep --------------------------------------------------
crank_revs = 0          # cumulative (uint32, wraps at 4 294 967 295)
last_event = 0          # 1/1024 s tick (uint16, wraps at 65 535)

def notify_cb(chrc):
    global crank_revs, last_event
    watts, rpm = 300, 60 #get_metrics()          # <-- your OCR function
    dt = 1                              # send once per second
    crank_revs += int(rpm * dt / 60)
    last_event = (last_event + dt*1024) & 0xFFFF

    payload = struct.pack('<HB', flags, 0)          # flags + 1 byte pad
    payload += struct.pack('<h', watts)             # Instant. Power (sint16)
    payload += struct.pack('<I', crank_revs)[:4]    # uint32 LE
    payload += struct.pack('<H', last_event)        # uint16 LE

    chrc.set_value(list(payload))       # Bluezero wants a list of ints
    return chrc.is_notifying            # keep timer running

chrc = periph.get_characteristic(srv_id=1, chr_id=1)
async_tools.add_timer_seconds(1, notify_cb, chrc)

periph.publish()        # Pi is now advertising “Cycling Power”
async_tools.run()
