// ESP32: recibe "1", "2" o "3" por USB serial desde la Raspberry
// y responde una linea de texto para confirmar que lo recibio.

void setup() {
  Serial.begin(115200);
  pinMode(2, OUTPUT);  // LED integrado en la mayoria de placas ESP32
}

void loop() {
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando == "1") {
      digitalWrite(2, HIGH);
      Serial.println("OK 1 - LED encendido");
    } else if (comando == "2") {
      digitalWrite(2, LOW);
      Serial.println("OK 2 - LED apagado");
    } else if (comando == "3") {
      // Ejemplo de devolver un valor: lectura analogica del pin 34
      Serial.println("OK 3 - valor=" + String(analogRead(34)));
    } else if (comando.length() > 0) {
      Serial.println("ERROR comando desconocido: " + comando);
    }
  }
}
