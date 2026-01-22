import os
import asyncio
import struct
import time
import math
import threading
import traceback
from typing import List, Dict, Any

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, method, dbus_property, PropertyAccess, Variant

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# BLE Service and Characteristic UUIDs
CYCLING_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"

# ============================================
# Shared State for Web Interface Control
# ============================================
class BikeState:
    """Thread-safe shared state between web server and BLE emulator."""
    def __init__(self):
        self._lock = threading.Lock()
        self._cadence = 60  # RPM (0-200)
        self._torque = 30   # % (1-100)
        self._calibration_factor = 1/18  # Default calibration factor
        self._power = 0     # Calculated power (read-only)
    
    @property
    def cadence(self):
        with self._lock:
            return self._cadence
    
    @cadence.setter
    def cadence(self, value):
        with self._lock:
            try:
                self._cadence = max(0, min(200, int(value)))
            except (ValueError, TypeError):
                print(f"Invalid cadence value: {value}")
    
    @property
    def torque(self):
        with self._lock:
            return self._torque
    
    @torque.setter
    def torque(self, value):
        with self._lock:
            try:
                self._torque = max(1, min(100, int(value)))
            except (ValueError, TypeError):
                print(f"Invalid torque value: {value}")
    
    @property
    def calibration_factor(self):
        with self._lock:
            return self._calibration_factor
    
    @calibration_factor.setter
    def calibration_factor(self, value):
        with self._lock:
            try:
                self._calibration_factor = max(0.001, min(1.0, float(value)))
            except (ValueError, TypeError):
                print(f"Invalid calibration value: {value}")
    
    @property
    def power(self):
        with self._lock:
            return self._power
    
    @power.setter
    def power(self, value):
        with self._lock:
            try:
                self._power = int(value)
            except (ValueError, TypeError):
                 # Fallback/ignore if value is weird, though usually calculated internally
                 pass
    
    def calculate_power(self):
        """Calculate power: P = cadence * torque * calibration_factor"""
        with self._lock:
            # Re-read values safely inside the lock if we weren't already holding it?
            # actually we are calling properties which lock. 
            # But for atomicity in calculation:
            c = self._cadence
            t = self._torque
            f = self._calibration_factor
        return int(c * t * f)
    
    def get_all(self):
        """Get all state values as a dictionary."""
        with self._lock:
            return {
                'cadence': self._cadence,
                'torque': self._torque,
                'calibration_factor': self._calibration_factor,
                'power': self._power
            }

# Global shared state
bike_state = BikeState()

# ============================================
# Flask Web Server
# ============================================
# Ensure we find the templates folder relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(script_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)
CORS(app)

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        traceback.print_exc()
        return f"Error loading template: {str(e)}", 500

@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current bike state."""
    try:
        return jsonify(bike_state.get_all())
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/cadence', methods=['POST'])
def set_cadence():
    """Set cadence value."""
    try:
        data = request.get_json(force=True)
        if data and 'value' in data:
            bike_state.cadence = data['value']
        return jsonify({'cadence': bike_state.cadence})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/torque', methods=['POST'])
def set_torque():
    """Set torque value."""
    try:
        data = request.get_json(force=True)
        if data and 'value' in data:
            bike_state.torque = data['value']
        return jsonify({'torque': bike_state.torque})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/calibration', methods=['POST'])
def set_calibration():
    """Set calibration factor."""
    try:
        data = request.get_json(force=True)
        if data and 'value' in data:
            bike_state.calibration_factor = data['value']
        return jsonify({'calibration_factor': bike_state.calibration_factor})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def run_flask():
    """Run Flask server in a separate thread."""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ============================================
# BLE Classes
# ============================================
class Application(ServiceInterface):
    def __init__(self, services):
        super().__init__('org.freedesktop.DBus.ObjectManager')
        self.path = '/org/bluez/example'
        self.services = services

    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        response = {}
        for service in self.services:
            response[service.path] = service.get_properties_dict()
            for chrc in service.characteristics:
                response[chrc.path] = chrc.get_properties_dict()
        return response

class GattService(ServiceInterface):
    def __init__(self, uuid, primary, index):
        super().__init__('org.bluez.GattService1')
        self.uuid = uuid
        self.primary = primary
        self.path = f'/org/bluez/example/service{index}'
        self.characteristics = []

    def get_properties_dict(self):
        return {
            'org.bluez.GattService1': {
                'UUID': Variant('s', self.uuid),
                'Primary': Variant('b', self.primary),
            }
        }

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> 'b':
        return self.primary

class GattCharacteristic(ServiceInterface):
    def __init__(self, uuid, flags, service, index):
        super().__init__('org.bluez.GattCharacteristic1')
        self.uuid = uuid
        self.flags = flags
        self.service = service
        self.path = f'{service.path}/char{index}'
        self.service.characteristics.append(self)
        self.notifying = False

    def get_properties_dict(self):
        return {
            'org.bluez.GattCharacteristic1': {
                'UUID': Variant('s', self.uuid),
                'Service': Variant('o', self.service.path),
                'Flags': Variant('as', self.flags),
            }
        }

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> 'o':
        return self.service.path

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> 'as':
        return self.flags

class CyclingPowerMeasurementChrc(GattCharacteristic):
    def __init__(self, service, index):
        super().__init__(CYCLING_POWER_MEASUREMENT_UUID, ['notify'], service, index)
        self.power = 0
        self._value = b''
        self.cum_crank_revs = 0
        self.last_crank_event_time = 0 

    def get_properties_dict(self):
        props = super().get_properties_dict()
        return props

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> 'ay':
        return self._value

    @method()
    def StartNotify(self):
        self.notifying = True
        print("Notify started - client connected")

    @method()
    def StopNotify(self):
        self.notifying = False
        print("Notify stopped - client disconnected")

    async def update_simulation(self):
        print("Starting simulation loop...")
        print("Web interface available at http://localhost:5000")
        while True:
            # Calculate power from web interface values
            self.power = bike_state.calculate_power()
            bike_state.power = self.power
            
            # Update cumulative revs based on cadence
            # cadence is in RPM, so revs per second = cadence / 60
            cadence = bike_state.cadence
            revs_per_second = cadence / 60.0
            
            # Increment cumulative crank revs
            self.cum_crank_revs += int(revs_per_second)
            
            # Last crank event time in 1/1024 seconds
            current_time_unit = int(time.time() * 1024) % 65536
            self.last_crank_event_time = current_time_unit

            # Flags: 
            # Bit 0=0 (Pedal Power Balance present = False)
            # ...
            # Bit 5=1 (Crank Revolution Data Present = True)
            flags = (1 << 5)
            
            # Format: Flags (uint16), Instantaneous Power (sint16), 
            # Cumulative Crank Revs (uint16), Last Crank Event Time (uint16)
            power_data = struct.pack('<HhHH', 
                                     flags, 
                                     self.power, 
                                     self.cum_crank_revs % 65536, 
                                     self.last_crank_event_time)
            
            self._value = power_data
            
            print(f"Update: Power={self.power}W, Cadence={cadence}RPM, Torque={bike_state.torque}%, Cal={bike_state.calibration_factor:.4f}")
            
            if self.notifying:
                print("Sending notification...")
                self.emit_properties_changed({'Value': power_data})
            
            await asyncio.sleep(1)

class Agent(ServiceInterface):
    def __init__(self, index):
        super().__init__('org.bluez.Agent1')
        self.path = f'/org/bluez/example/agent{index}'

    @method()
    def Release(self):
        print("Agent Release")

    @method()
    def RequestPinCode(self, device: 'o') -> 's':
        print(f"RequestPinCode {device}")
        return "0000"

    @method()
    def DisplayPinCode(self, device: 'o', pincode: 's'):
        print(f"DisplayPinCode {device} {pincode}")

    @method()
    def RequestPasskey(self, device: 'o') -> 'u':
        print(f"RequestPasskey {device}")
        return 0

    @method()
    def DisplayPasskey(self, device: 'o', passkey: 'u', entered: 'q'):
        print(f"DisplayPasskey {device} {passkey} entered {entered}")

    @method()
    def RequestConfirmation(self, device: 'o', passkey: 'u'):
        print(f"RequestConfirmation {device} {passkey}")
        return

    @method()
    def RequestAuthorization(self, device: 'o'):
        print(f"RequestAuthorization {device}")
        return

    @method()
    def AuthorizeService(self, device: 'o', uuid: 's'):
        print(f"AuthorizeService {device} {uuid}")
        return

    @method()
    def Cancel(self):
        print("Agent Cancel")
            
class LEAdvertisement(ServiceInterface):
    def __init__(self, index):
        super().__init__('org.bluez.LEAdvertisement1')
        self.path = f'/org/bluez/example/advertisement{index}'
        self.type = 'peripheral'
        self.service_uuids = [CYCLING_POWER_SERVICE_UUID]
        self.local_name = 'Gemini Bike'
        self.discoverable = True

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> 's':
        return self.type

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> 'as':
        return self.service_uuids

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> 's':
        return self.local_name
        
    @dbus_property(access=PropertyAccess.READ)
    def Discoverable(self) -> 'b':
        return self.discoverable
        
    @method()
    def Release(self):
        print(f'{self.path}: Released!')

class DeviceInformationService(GattService):
    pass

class StaticCharacteristic(GattCharacteristic):
    def __init__(self, uuid, flags, service, index, value):
        super().__init__(uuid, flags, service, index)
        self._value = value

    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        return self._value

async def main():
    # Start Flask web server in a background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Web interface starting on http://0.0.0.0:5000")
    
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Get the DBus adapter
    adapter_path = '/org/bluez/hci0'
    try:
        adapter_obj = bus.get_proxy_object('org.bluez', adapter_path, await bus.introspect('org.bluez', adapter_path))
    except Exception as e:
        print(f"Error getting adapter {adapter_path}: {e}")
        return

    adapter_props = adapter_obj.get_interface('org.freedesktop.DBus.Properties')

    # Ensure adapter is powered
    print("Powering on adapter...")
    await adapter_props.call_set('org.bluez.Adapter1', 'Powered', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'Discoverable', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'Pairable', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'PairableTimeout', Variant('u', 0))
    await adapter_props.call_set('org.bluez.Adapter1', 'Alias', Variant('s', 'Gemini Bike'))

    # Setup Agent
    agent = Agent(0)
    bus.export(agent.path, agent)
    
    bluez_obj = bus.get_proxy_object('org.bluez', '/org/bluez', await bus.introspect('org.bluez', '/org/bluez'))
    agent_manager = bluez_obj.get_interface('org.bluez.AgentManager1')

    print("Registering Agent...")
    try:
        await agent_manager.call_register_agent(agent.path, "NoInputNoOutput")
        await agent_manager.call_request_default_agent(agent.path)
    except Exception as e:
        print(f"Failed to register agent: {e}")

    # Setup Application (GATT)
    service_cp = GattService(CYCLING_POWER_SERVICE_UUID, True, 0)
    chrc_cp = CyclingPowerMeasurementChrc(service_cp, 0)
    
    service_dis = GattService('0000180a-0000-1000-8000-00805f9b34fb', True, 1)
    StaticCharacteristic('00002a29-0000-1000-8000-00805f9b34fb', ['read'], service_dis, 0, b'Google DeepMind')
    StaticCharacteristic('00002a24-0000-1000-8000-00805f9b34fb', ['read'], service_dis, 1, b'Gemini-Bike-01')

    app_ble = Application([service_cp, service_dis])

    bus.export(app_ble.path, app_ble) 
    
    for service in app_ble.services:
        bus.export(service.path, service)
        for c in service.characteristics:
            bus.export(c.path, c)

    gatt_manager = adapter_obj.get_interface('org.bluez.GattManager1')
    print("Registering GATT Application...")
    try:
        await gatt_manager.call_register_application(app_ble.path, {})
    except Exception as e:
        print(f"Failed to register application: {e}")

    advertisement = LEAdvertisement(0)
    bus.export(advertisement.path, advertisement)

    advertising_manager = adapter_obj.get_interface('org.bluez.LEAdvertisingManager1')
    print("Registering Advertisement...")
    try:
        await advertising_manager.call_register_advertisement(advertisement.path, {})
    except Exception as e:
        print(f"Failed to register advertisement: {e}")

    print("Gemini Bike Emulator Running...")
    print("Web interface: http://localhost:5000")
    print("Press Ctrl+C to stop.")

    await chrc_cp.update_simulation()

if __name__ == '__main__':
    asyncio.run(main())