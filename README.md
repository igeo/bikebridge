# BikeBridge

I have a FlyWheel Studio bike which was designed to be used in gym. After FlyWheel went out of business, there is no way to connect to the bike.

Even [Gymnasticon](https://github.com/ptx2/gymnasticon) which reverse engineered FlyWheel Homebike doesn't work with FlyWheel Studio bike.

My solution is using a camera to minitor the build on console of the bike and read of the torque and speed (RPM) from the screen. We than calculate power from it and broadcast it to BLE for biking apps, like [MyWhoosh](https://www.mywhoosh.com/) and [Zwift](https://www.zwift.com/), to consume.

## Reference
https://github.com/iaroslavn/peloton-bike-metrics-server