# BikeBridge

I have a FlyWheel Studio bike which was designed to be used in gym. After FlyWheel went out of business, there is no way to connect to the bike.

Even [Gymnasticon](https://github.com/ptx2/gymnasticon) which reverse engineered FlyWheel Homebike doesn't work with FlyWheel Studio bike.

My solution is using a camera to minitor the build on console of the bike and read of the torque and speed (RPM) from the screen. We than calculate power from it and broadcast it to BLE for biking apps, like [MyWhoosh](https://www.mywhoosh.com/) and [Zwift](https://www.zwift.com/), to consume.

## Supported Apps

| App | Platform | Status |
|-----|----------|--------|
| Zwift | iPad/iOS | ✅ Works |
| MyWhoosh | iPad/iOS | ✅ Works |
| MyWhoosh | Windows | ✅ Works (v2.0+) |
| Zwift | Windows | ✅ Works (v2.0+) |

## BLE Services

The emulator broadcasts as a proper BLE fitness device with the following services:

### FTMS (Fitness Machine Service) - 0x1826
- **Primary for Windows compatibility** - MyWhoosh on Windows specifically looks for this
- Indoor Bike Data (0x2AD2): Broadcasts power and cadence
- FTMS Feature (0x2ACC): Reports supported features
- FTMS Control Point (0x2AD9): Handles control commands

### Cycling Power Service - 0x1818
- **For iOS apps like Zwift** - Works with most cycling apps
- Cycling Power Measurement (0x2A63): Power and crank data
- Cycling Power Feature (0x2A65): Supported features
- Sensor Location (0x2A5D): Reports sensor position

### Device Information Service - 0x180A
- Manufacturer Name, Model Number

## Windows Compatibility

Windows 10/11 has a strict Bluetooth stack that requires proper BLE advertisement configuration:

1. **Advertisement Flags**: Set to `0x06` (LE General Discoverable + BR/EDR Not Supported)
2. **Appearance Value**: Set to `1155` (Cycling: Power Sensor) for device filtering
3. **FTMS Service**: Required for MyWhoosh on Windows (it ignores Cycling Power alone)
4. **Public Address**: Windows prefers Public Device Address over Random addresses

## Troubleshooting Windows Detection

If Windows still doesn't detect the bike:

### 1. Run the diagnostic script on Raspberry Pi
```bash
chmod +x diagnose_ble.sh
./diagnose_ble.sh
```

### 2. Manual BLE configuration (before starting bike_emulator.py)
```bash
# Stop bluetooth, reset adapter
sudo systemctl stop bluetooth
sudo hciconfig hci0 down
sudo hciconfig hci0 up

# Disable classic Bluetooth (BR/EDR) - use LE only
sudo btmgmt --index 0 bredr off
sudo btmgmt --index 0 le on

# Start bluetooth
sudo systemctl start bluetooth
```

### 3. Check BlueZ version (need 5.50+)
```bash
bluetoothctl --version
```

### 4. On Windows PC
- Open Bluetooth settings and remove any existing "Gemini Bike" devices
- Restart Bluetooth on Windows (toggle off/on in Settings)
- Try scanning with a BLE scanner app (like "Bluetooth LE Explorer") to verify the device is visible
- Check if Windows Bluetooth drivers are up to date

### 5. Verify advertisement is correct
Use a BLE scanner app on your phone to verify you can see:
- Device name: "Gemini Bike"  
- Service UUIDs: 0x1826 (FTMS), 0x1818 (Cycling Power)
- Appearance: 1155 (Cycling Power Sensor)

### 6. Alternative: Use nRF Connect
On your phone, install "nRF Connect" and scan for BLE devices. If you can see "Gemini Bike" with the correct services, the issue is Windows-specific.

## Requirements

- Raspberry Pi with Bluetooth LE support
- BlueZ 5.50 or higher
- Python 3.7+
- Required packages: `dbus-next`, `aiohttp`

```bash
pip install dbus-next aiohttp
```

## Reference
- https://github.com/iaroslavn/peloton-bike-metrics-server
- https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/
- https://www.bluetooth.com/specifications/specs/gatt-specification-supplement-6/