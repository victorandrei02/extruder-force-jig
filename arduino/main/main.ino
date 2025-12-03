/*

Arduino PIN 5 -> HX711 SCK (Clock)
Arduino PIN 6 -> HX711 DT (Data)
Arduino 5V -> HX711 VCC (Voltage)
Arduino GND -> HX711 GND (Ground)

Load Cell Red -> HX711 E+
Load Cell Black -> HX711 E-
Load Cell White -> HX711 A-
Load Cell Green -> HX711 A+

*/

// Including HX711 library, naming set to "scale".
#include "HX711.h"
HX711 scale;

// Arduino Pins for the SCK (clock) pin and DT (data) pin on the HX711 breakout board.
const unsigned int hx_sck = 5;
const unsigned int hx_dt = 6;

// Defining state names
enum {notReady, isReady};
unsigned char scaleState = notReady;


void setup() {

  Serial.begin(115200); // 115200 baud rate, can be changed

  Serial.println("Simple HX711 Load Cell Serial Plotter");
  scale.begin(hx_dt, hx_sck); // Initializing HX711 chip

  Serial.println("Taring cell in 3s...");
  delay(3000);
  scale.tare(); // Taring the cell
  delay(1000);
  scale.set_raw_mode(); // Ensure cell is running in average mode

}

void loop() {

  switch (scaleState) {

    case notReady:
      if (scale.is_ready()) {
        scaleState = isReady;
        break;
      }
      else {
        break;
      }


    case isReady:
      float measurement = scale.get_value();
      Serial.print("M:");
      Serial.println(measurement);
      scaleState = notReady;
      break;
  }
}
