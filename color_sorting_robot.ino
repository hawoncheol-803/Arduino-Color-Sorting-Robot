#include <Servo.h>

Servo bottom;
Servo grip;

const int CENTER = 75;
const int RIGHT = 120;
const int LEFT = 30;

const int GRIP_OPEN = 60;
const int GRIP_CLOSE = 10;

void setup() {
  Serial.begin(9600);

  bottom.attach(4);
  grip.attach(7);

  bottom.write(CENTER);
  grip.write(GRIP_OPEN);
}

void loop() {
  if (Serial.available() > 0) {
    char color = Serial.read();

    if (color == 'R') {
      grip.write(GRIP_CLOSE);
      delay(1000);

      bottom.write(RIGHT);
      delay(1500);

      grip.write(GRIP_OPEN);
      delay(1000);

      bottom.write(CENTER);
      delay(1500);

      Serial.println("DONE");
    }

    else if (color == 'Y') {
      grip.write(GRIP_CLOSE);
      delay(1000);

      bottom.write(LEFT);
      delay(1500);

      grip.write(GRIP_OPEN);
      delay(1000);

      bottom.write(CENTER);
      delay(1500);

      Serial.println("DONE");
    }
  }
}
