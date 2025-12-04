/*
Arduino Scale Controller - Clean Version

Pin Configuration:
Arduino PIN 5 -> HX711 SCK (Clock)
Arduino PIN 6 -> HX711 DT (Data)
Arduino 5V -> HX711 VCC
Arduino GND -> HX711 GND

Load Cell Red -> HX711 E+
Load Cell Black -> HX711 E-
Load Cell White -> HX711 A-
Load Cell Green -> HX711 A+
*/

#include "HX711.h"

// Pin definitions
const int HX_SCK = 5;
const int HX_DT = 6;

// HX711 instance
HX711 scale;

// Device states
enum DeviceState { IDLE, MEASURING, CALIBRATING };
DeviceState deviceState = IDLE;

// Calibration states
enum CalState { CAL_INIT, CAL_WAIT_READY, CAL_TARE, CAL_WAIT_WEIGHT, CAL_MEASURE, CAL_DONE };
CalState calState = CAL_INIT;

// Variables
float calWeight = 0;
unsigned long calTimer = 0;

// Serial parsing
const byte MAX_CHARS = 32;
char buffer[MAX_CHARS];
bool newCommand = false;

void setup() {
  Serial.begin(115200);
  scale.begin(HX_DT, HX_SCK);
  Serial.println("r");  // Ready signal
}

void loop() {
  readSerial();
  processCommands();
  
  switch (deviceState) {
    case IDLE:
      // Do nothing, wait for commands
      break;
      
    case MEASURING:
      doMeasurement();
      break;
      
    case CALIBRATING:
      doCalibration();
      break;
  }
}

// ============ SERIAL HANDLING ============

void readSerial() {
  static byte idx = 0;
  static bool receiving = false;
  
  while (Serial.available() && !newCommand) {
    char c = Serial.read();
    
    if (c == '<') {
      receiving = true;
      idx = 0;
    }
    else if (c == '>') {
      buffer[idx] = '\0';
      receiving = false;
      newCommand = true;
    }
    else if (receiving) {
      if (idx < MAX_CHARS - 1) {
        buffer[idx++] = c;
      }
    }
  }
}

void processCommands() {
  if (!newCommand) return;
  
  // Check if calibration needs the command first
  if (deviceState == CALIBRATING && calState == CAL_WAIT_WEIGHT) {
    if (strncmp(buffer, "weight:", 7) == 0) {
      // Let calibration handle it, don't clear yet
      return;
    }
  }
  
  // Universal commands (work in any state)
  if (strcmp(buffer, "tare") == 0) {
    scale.tare();
    Serial.println("TARED");
  }
  else if (strcmp(buffer, "start") == 0) {
    deviceState = MEASURING;
    Serial.println("MEASURING");
  }
  else if (strcmp(buffer, "stop") == 0) {
    deviceState = IDLE;
    Serial.println("STOPPED");
  }
  else if (strcmp(buffer, "calibrate") == 0) {
    deviceState = CALIBRATING;
    calState = CAL_INIT;
    Serial.println("CAL_START");
  }
  else if (strcmp(buffer, "cancel") == 0 && deviceState == CALIBRATING) {
    deviceState = IDLE;
    Serial.println("CAL_CANCEL");
  }
  else if (strcmp(buffer, "get_scale") == 0) {
    // Get current scale factor
    Serial.print("SCALE_FACTOR:");
    Serial.println(scale.get_scale(), 6);
  }
  else if (strncmp(buffer, "set_scale:", 10) == 0) {
    // Set scale factor: <set_scale:123.456>
    float factor = atof(buffer + 10);
    if (factor != 0) {
      scale.set_scale(factor);
      Serial.print("SCALE_SET:");
      Serial.println(factor, 6);
    } else {
      Serial.println("ERROR:Invalid scale factor");
    }
  }
  
  newCommand = false;
  memset(buffer, 0, MAX_CHARS);
}

// ============ MEASUREMENT ============

void doMeasurement() {
  if (scale.is_ready()) {
    float weight = scale.get_units();
    Serial.println(weight, 2);
  }
}

// ============ CALIBRATION ============

void doCalibration() {
  switch (calState) {
    case CAL_INIT:
      // Give GUI time to open window
      calTimer = millis();
      calState = CAL_WAIT_READY;
      break;
      
    case CAL_WAIT_READY:
      // Wait 500ms before showing clear scale message
      if (millis() - calTimer > 500) {
        Serial.println("CAL_CLEAR_SCALE");
        calTimer = millis();
        calState = CAL_TARE;
      }
      break;
      
    case CAL_TARE:
      // Wait 2 seconds, then tare
      if (millis() - calTimer > 2000) {
        if (scale.is_ready()) {
          scale.tare();
          Serial.println("CAL_TARED");
          calState = CAL_WAIT_WEIGHT;
        }
      }
      break;
      
    case CAL_WAIT_WEIGHT:
      // Wait for weight command from serial
      if (newCommand && strncmp(buffer, "weight:", 7) == 0) {
        calWeight = atof(buffer + 7);
        
        Serial.print("CAL_WEIGHT:");
        Serial.println(calWeight, 2);
        
        // Clear command after processing
        newCommand = false;
        memset(buffer, 0, MAX_CHARS);
        
        if (calWeight > 0) {
          calState = CAL_MEASURE;
          calTimer = millis();
        } else {
          Serial.println("CAL_ERROR:Invalid weight");
          // Stay in CAL_WAIT_WEIGHT
        }
      }
      break;
      
    case CAL_MEASURE:
      // Wait 3 seconds for weight to settle
      if (millis() - calTimer > 3000) {
        if (scale.is_ready()) {
          // Get the current reading (after tare, this is the weight value)
          long raw = scale.get_value();  // This gets (reading - offset)
          
          Serial.print("CAL_RAW:");
          Serial.println(raw);
          
          if (abs(raw) > 1000) {
            // Calculate scale factor: raw_value / known_weight
            float factor = (float)raw / calWeight;
            scale.set_scale(factor);
            
            Serial.print("CAL_FACTOR:");
            Serial.println(factor, 2);
            
            calState = CAL_DONE;
          } else {
            Serial.println("CAL_ERROR:No weight detected");
            calState = CAL_WAIT_WEIGHT;
          }
        }
      }
      break;
      
    case CAL_DONE:
      if (scale.is_ready()) {
        float test = scale.get_units();
        Serial.print("CAL_TEST:");
        Serial.println(test, 2);
        deviceState = IDLE;
        calState = CAL_INIT;
      }
      break;
  }
}