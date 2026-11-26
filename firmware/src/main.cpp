#include <Arduino.h>
#include <NimBLEDevice.h>

#ifndef DEVICE_ROLE
#define DEVICE_ROLE 1
#endif
#ifndef DEVICE_ORDINAL
#define DEVICE_ORDINAL 1
#endif

// Manufacturer-specific payload: company ID (0xFFFF prototype) + <2sBBHbH>.
// RSSI_AT_1M is a calibrated received RSSI, NOT the radio transmit power.
void setup() {
  Serial.begin(115200);
  delay(1000);
  char deviceName[8];
  snprintf(deviceName, sizeof(deviceName), "%c%02d", DEVICE_ROLE == 1 ? 'A' : 'T', DEVICE_ORDINAL);
  NimBLEDevice::init(deviceName);
  NimBLEDevice::setPower(3);
  auto* advertising = NimBLEDevice::getAdvertising();
  advertising->setConnectableMode(BLE_GAP_CONN_MODE_NON);
  advertising->enableScanResponse(false);
  advertising->setMinInterval(ADV_INTERVAL_MS * 1000 / 625);
  advertising->setMaxInterval(ADV_INTERVAL_MS * 1000 / 625);
  const uint8_t payload[] = {
    0xff, 0xff, 'B', 'I', 1, DEVICE_ROLE,
    static_cast<uint8_t>(DEVICE_ORDINAL & 0xff), static_cast<uint8_t>((DEVICE_ORDINAL >> 8) & 0xff),
    static_cast<uint8_t>(static_cast<int8_t>(RSSI_AT_1M)), 0, 0
  };
  advertising->setName(deviceName);
  advertising->setManufacturerData(payload, sizeof(payload));
  if (!advertising->start()) Serial.println("Advertising failed");
  else Serial.printf("BLE %s role=%d interval=%dms measured_RSSI_1m=%d\n",deviceName,DEVICE_ROLE,ADV_INTERVAL_MS,RSSI_AT_1M);
}

void loop() { delay(1000); }
