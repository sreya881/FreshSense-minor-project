
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "your_actual_wifi";
const char* password = "your_actual_password";

const char* serverURL = "http://your_ip_address:5000/sensor";

void setup() {
  Serial.begin(115200);

  analogReadResolution(12);
  analogSetPinAttenuation(34, ADC_11db);

  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");
}

void loop() {

  long totalADC = 0;
  long totalMilliVolts = 0;

  for (int i = 0; i < 10; i++) {
    totalADC += analogRead(34);
    totalMilliVolts += analogReadMilliVolts(34);
    delay(10);
  }

  float gasValue = totalADC / 10.0;
  float voltageMV = totalMilliVolts / 10.0;

  Serial.print("Gas value: ");
  Serial.println(gasValue);

  Serial.print("GPIO voltage: ");
  Serial.print(voltageMV);
  Serial.println(" mV");

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;

    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"gas_value\":" + String(gasValue, 2) +
                  ",\"voltage_mv\":" + String(voltageMV, 2) + "}";

    int responseCode = http.POST(json);

    Serial.print("Server response: ");
    Serial.println(responseCode);

    http.end();
  }

  delay(1000);
}