import asyncio
import struct
import time
import math
from typing import List, Dict, Any

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, method, dbus_property, PropertyAccess, Variant

# BLE Service and Characteristic UUIDs
CYCLING_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"

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
        while True:
            # Simulate power data (sine wave 90-130 W)
            # Center at 110, amplitude 20
            self.power = int(110 + 20 * math.sin(time.time() / 5.0))
            
            # Simulate Cadence (e.g., 90 RPM)
            # 90 RPM = 1.5 revs per second
            # Update cumulative revs
            self.cum_crank_revs += 1 
            # Last crank event time in 1/1024 seconds
            # current time * 1024
            current_time_unit = int(time.time() * 1024) % 65536
            self.last_crank_event_time = current_time_unit

            # Flags: 
            # Bit 0=0 (Pedal Power Balance present = False)
            # ...
            # Bit 5=1 (Crank Revolution Data Present = True)
            flags = (1 << 5)
            
            # Format: Flags (uint16), Instantaneous Power (sint16), 
            # Cumulative Crank Revs (uint16), Last Crank Event Time (uint16)
            # Note: struct.pack uses < for little-endian
            power_data = struct.pack('<HhHH', 
                                     flags, 
                                     self.power, 
                                     self.cum_crank_revs % 65536, 
                                     self.last_crank_event_time)
            
            self._value = power_data
            
            print(f"Update: Power={self.power}W, Flags={flags:#x}, Data={power_data.hex()}")
            
            if self.notifying:
                print("Sending notification...")
                self.emit_properties_changed({'Value': power_data})
            
            # 90 RPM is 1.5 rev/sec -> sleep 0.66s would be realistic for event based, 
            # but for notification updates 1HZ is standard for many power meters.
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
        # Just confirm
        return

    @method()
    def RequestAuthorization(self, device: 'o'):
        print(f"RequestAuthorization {device}")
        # Just authorize
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

async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Get the DBus adapter
    adapter_path = '/org/bluez/hci0'
    try:
        adapter_obj = bus.get_proxy_object('org.bluez', adapter_path, await bus.introspect('org.bluez', adapter_path))
    except Exception as e:
        print(f"Error getting adapter {adapter_path}: {e}")
        # Try to find any adapter if hci0 fails
        # In a robust app we might list adapters, but for Pi Zero 2W usually hci0 is it.
        return

    adapter_props = adapter_obj.get_interface('org.freedesktop.DBus.Properties')

    # Ensure adapter is powered
    print("Powering on adapter...")
    await adapter_props.call_set('org.bluez.Adapter1', 'Powered', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'Discoverable', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'Pairable', Variant('b', True))
    await adapter_props.call_set('org.bluez.Adapter1', 'PairableTimeout', Variant('u', 0))
    # Alias
    await adapter_props.call_set('org.bluez.Adapter1', 'Alias', Variant('s', 'Gemini Bike'))

    # Setup Agent
    agent = Agent(0)
    bus.export(agent.path, agent)
    
    # Get AgentManager1 from the root /org/bluez path
    bluez_obj = bus.get_proxy_object('org.bluez', '/org/bluez', await bus.introspect('org.bluez', '/org/bluez'))
    agent_manager = bluez_obj.get_interface('org.bluez.AgentManager1')

    print("Registering Agent...")
    try:
        await agent_manager.call_register_agent(agent.path, "NoInputNoOutput")
        await agent_manager.call_request_default_agent(agent.path)
    except Exception as e:
        print(f"Failed to register agent: {e}")

    # Setup Application (GATT)
    service = GattService(CYCLING_POWER_SERVICE_UUID, True, 0)
    chrc = CyclingPowerMeasurementChrc(service, 0)
    app = Application([service])

    # Export Application objects
    bus.export(app.path, app) 
    bus.export(service.path, service)
    for c in service.characteristics:
        bus.export(c.path, c)

    # Register Application
    gatt_manager = adapter_obj.get_interface('org.bluez.GattManager1')
    print("Registering GATT Application...")
    try:
        await gatt_manager.call_register_application(app.path, {})
    except Exception as e:
        print(f"Failed to register application: {e}")

    # Setup Advertisement
    advertisement = LEAdvertisement(0)
    bus.export(advertisement.path, advertisement)

    # Register Advertisement
    advertising_manager = adapter_obj.get_interface('org.bluez.LEAdvertisingManager1')
    print("Registering Advertisement...")
    try:
        await advertising_manager.call_register_advertisement(advertisement.path, {})
    except Exception as e:
        print(f"Failed to register advertisement: {e}")

    print("Gemini Bike Emulator Running...")
    print("Press Ctrl+C to stop.")

    # Run simulation
    await chrc.update_simulation()

if __name__ == '__main__':
    asyncio.run(main())