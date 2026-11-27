/*
 * =====================================================================
 *  IRB2001 - Fundamentos a la Robótica - U4 Entrega 1
 *  Receptor Bluetooth + control PID de velocidad para ambas ruedas
 * =====================================================================
 *
 *  Descripción general
 *  -------------------
 *  El robot recibe por Bluetooth (Serial3, 38400 baudios) una velocidad
 *  de referencia [RPM] para cada rueda, de forma independiente y
 *  simultánea. Cada 10 ms (100 Hz) mide la velocidad real de cada rueda
 *  con los encoders y aplica un PID incremental que calcula el comando
 *  para el driver DualVNH5019 (rango -400 a 400).
 *
 *  ---------------------------------------------------------------------
 *  FORMATO DE MENSAJES QUE EL ROBOT RECIBE  (PC -> Arduino, Bluetooth)
 *  ---------------------------------------------------------------------
 *  Paquete binario de 3 bytes:
 *
 *      +--------+---------------------+---------------------+
 *      | Byte 0 |       Byte 1        |       Byte 2        |
 *      +--------+---------------------+---------------------+
 *      |  0xFF  | vel_izquierda + 100 |  vel_derecha + 100  |
 *      +--------+---------------------+---------------------+
 *
 *   - Byte 0 (0xFF): encabezado / inicio de trama. Como los datos
 *     nunca superan 200, el valor 0xFF (255) solo puede ser encabezado.
 *   - Byte 1 y 2: velocidad en RPM desplazada en +100 para que quepa en
 *     un byte sin signo. Rango válido del byte: 0..200, es decir,
 *     velocidades enteras de -100 a +100 RPM (negativo = retroceso).
 *
 *   Ejemplos:
 *     izq =  100, der =  50   ->  FF C8 96
 *     izq =   50, der = -30   ->  FF 96 46
 *     izq =    0, der =   0   ->  FF 64 64   (detener)
 *
 *   El programa en Python reenvía el paquete cada 0,3 s. Si pasan más
 *   de 1,5 s (TIMEOUT_COMANDO_MS) sin recibir un paquete completo, el
 *   robot avisa con "STOP,TIMEOUT;".
 *
 *  ---------------------------------------------------------------------
 *  FORMATO DE MENSAJES QUE EL ROBOT ENTREGA  (Arduino -> PC, Bluetooth)
 *  ---------------------------------------------------------------------
 *  Texto ASCII, terminado en ';' + salto de línea (\r\n):
 *
 *   OK,<izq>,<der>;   Paquete válido recibido. <izq> y <der> son las
 *                     referencias aplicadas en RPM (enteros). <der> se
 *                     muestra ya multiplicada por signo2 (= -1), por lo
 *                     que aparece con el signo invertido.
 *                     Ej: se envía izq=50, der=30 -> "OK,50,-30;"
 *   ERR,VALOR;        Se recibió un byte de dato mayor a 200. El paquete
 *                     se descarta y se espera un nuevo encabezado 0xFF.
 *   STOP,TIMEOUT;     Pasaron más de 1,5 s sin recibir comandos.
 *
 *  ---------------------------------------------------------------------
 *  TELEMETRÍA POR MONITOR SERIAL (USB, Serial, 115200 baudios)
 *  ---------------------------------------------------------------------
 *  Cada 50 ms (1 de cada 5 ciclos de control) se imprime una línea CSV:
 *
 *      velizq,velder,error2,vel1,vel2
 *
 *   velizq / velder : referencias de velocidad [RPM]
 *   error2          : error del PID de la rueda derecha [RPM]
 *   vel1 / vel2     : velocidad medida izquierda / derecha [RPM]
 *
 *  Conexiones: Motor 1 = rueda izquierda, Motor 2 = rueda derecha.
 * =====================================================================
 */

#include "DualVNH5019MotorShield.h"
DualVNH5019MotorShield md;      // Driver de los dos motores

// Pines de los encoders
#define encoder1PinA 19  // Motor 1 (izquierda)
#define encoder1PinB 18
#define encoder2PinA 20  // Motor 2 (derecha)
#define encoder2PinB 21

// Configuracion del protocolo
const byte INICIO_TRAMA = 0xFF;               // Encabezado de cada paquete
const byte DESPLAZAMIENTO_RPM = 100;          // Offset: byte = RPM + 100
const byte MAX_DATO = 200;                    // Máximo byte de dato válido (= +100 RPM)
const unsigned long TIMEOUT_COMANDO_MS = 1500UL; // Tiempo máximo sin comandos [ms]

byte estadoRecepcion = 0;       // 0: espera 0xFF; 1: izquierda; 2: derecha
byte datoIzquierda = 0;         // Guarda el byte izquierdo hasta recibir el derecho
unsigned long ultimoComandoMs = 0; // Instante (millis) del último paquete válido
bool comandoActivo = false;     // true mientras se reciban comandos dentro del timeout

// Referencias de velocidad [RPM]
float velizq = 0.0f;
float velder = 0.0f;

// Parametros PID

// izq
float Kp_i = 10.0f;
float Ki_i = 4.5f;
float Kd_i = 0.0f;

// der
float Kp_d = 10.0f;
float Ki_d = 4.5f;
float Kd_d = 0.0f;

// Sentido de giro de cada rueda. El motor derecho está montado en espejo,
// por lo que su referencia se invierte para que ambas ruedas avancen igual.
float signo1 = 1.0f;
float signo2 = - 1.0f;

// Tiempo de muestreo: 10 ms = 100 Hz
const unsigned long Period = 10000UL;   // Periodo de control [us]
const float dt = Period * 0.000001f;    // Periodo de control [s]
// Conversión de (cuentas / microsegundo) a RPM:
// RPM = cuentas * 60e6 / (deltaUs * cuentas_por_vuelta) = cuentas * FACTOR_RPM / deltaUs
// 31250 = 60e6 / 1920  ->  1920 cuentas por vuelta de la rueda
const float FACTOR_RPM = 31250.0f;
unsigned long time_ant = 0;   // Instante del ciclo de control anterior [us]
unsigned long newtime;        // Instante actual [us]

// Salidas a los motores (-400 a 400)
float motor1 = 0.0f;
float motor2 = 0.0f;

// Memoria del PID
// error = error actual, error_ant = k-1, error_ant2 = k-2, control_ant = u(k-1)
float error1 = 0.0f, error1_ant = 0.0f, error1_ant2 = 0.0f, control1_ant = 0.0f;
float error2 = 0.0f, error2_ant = 0.0f, error2_ant2 = 0.0f, control2_ant = 0.0f;

// Encoders
volatile long encoder1Pos = 0;   // Cuentas acumuladas (modificadas en interrupciones)
volatile long encoder2Pos = 0;
long newposition1 = 0, oldposition1 = 0;
long newposition2 = 0, oldposition2 = 0;
float vel1 = 0.0f, vel2 = 0.0f; // RPM
byte contadorTelemetria = 0;    // Cuenta ciclos para imprimir telemetría cada 5

//-----------------------------------
// INTERRUPCIONES DE LOS ENCODERS
// Decodificación en cuadratura: se cuenta en cada flanco de los canales A y B.
// El sentido (++ / --) depende de si A y B tienen el mismo nivel.
void doEncoder1A() { if (digitalRead(encoder1PinA) == digitalRead(encoder1PinB)) encoder1Pos++; else encoder1Pos--; }
void doEncoder1B() { if (digitalRead(encoder1PinA) == digitalRead(encoder1PinB)) encoder1Pos--; else encoder1Pos++; }
void doEncoder2A() { if (digitalRead(encoder2PinA) == digitalRead(encoder2PinB)) encoder2Pos++; else encoder2Pos--; }
void doEncoder2B() { if (digitalRead(encoder2PinA) == digitalRead(encoder2PinB)) encoder2Pos--; else encoder2Pos++; }

void setup() {
  // Inicializa el driver con ambos motores detenidos
  md.init();
  md.setM1Speed(0);
  md.setM2Speed(0);

  // Entradas de encoders con pull-up interno
  pinMode(encoder1PinA, INPUT_PULLUP);
  pinMode(encoder1PinB, INPUT_PULLUP);
  pinMode(encoder2PinA, INPUT_PULLUP);
  pinMode(encoder2PinB, INPUT_PULLUP);

  // Interrupción en cada cambio de nivel de los 4 canales
  attachInterrupt(digitalPinToInterrupt(encoder1PinA), doEncoder1A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(encoder1PinB), doEncoder1B, CHANGE);
  attachInterrupt(digitalPinToInterrupt(encoder2PinA), doEncoder2A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(encoder2PinB), doEncoder2B, CHANGE);

  Serial.begin(115200);   // Monitor serial
  Serial3.begin(38400);   // Comunicación Bluetooth

  Serial.println(F("Inicio"));
  time_ant = micros();
}


//-----------------------------------
// RECEPCIÓN BLUETOOTH
// Lee todos los bytes disponibles en Serial3 y arma el paquete
// [0xFF][izq+100][der+100] con una máquina de estados:
//   estado 0 -> espera el encabezado 0xFF (descarta cualquier otro byte)
//   estado 1 -> el siguiente byte es la velocidad izquierda
//   estado 2 -> el siguiente byte es la velocidad derecha; se aplican
//               ambas referencias y se responde "OK,<izq>,<der>;"
// Un 0xFF en cualquier momento reinicia la trama (resincronización).
// Un byte de dato > 200 descarta el paquete y responde "ERR,VALOR;".
void recibirBluetooth() {
  while (Serial3.available() > 0) {
    byte dato = (byte)Serial3.read();

    // Encabezado: comienza un paquete nuevo
    if (dato == INICIO_TRAMA) {
      estadoRecepcion = 1;
      continue;
    }

    if (estadoRecepcion == 0) {
      continue; // Ignorar bytes sin encabezado
    }

    if (dato > MAX_DATO) {
      estadoRecepcion = 0; // Dato inválido
      Serial3.println(F("ERR,VALOR;"));
      continue;
    }

    if (estadoRecepcion == 1) {
      // Primer dato: se guarda hasta tener el de la derecha
      datoIzquierda = dato;
      estadoRecepcion = 2;
    } else { // estadoRecepcion == 2: ambas ruedas
      // Se quita el desplazamiento (+100) y se aplica el sentido de giro
      velizq = (float)((int)datoIzquierda - (int)DESPLAZAMIENTO_RPM) * signo1;
      velder = (float)((int)dato - (int)DESPLAZAMIENTO_RPM) * signo2;
      estadoRecepcion = 0;
      ultimoComandoMs = millis();   // Reinicia el contador de timeout
      comandoActivo = true;

      // Confirmación al PC: "OK,<izq>,<der>;"
      Serial3.print(F("OK,"));
      Serial3.print((int)velizq);
      Serial3.print(',');
      Serial3.print((int)velder);
      Serial3.println(';');
    }
  }
}

void loop() {
  // 1) Procesar mensajes Bluetooth entrantes
  recibirBluetooth();

  // 2) Timeout: si no llegan comandos en 1,5 s se avisa con "STOP,TIMEOUT;"
  if (comandoActivo && (unsigned long)(millis() - ultimoComandoMs) > TIMEOUT_COMANDO_MS) {
    comandoActivo = false;
    estadoRecepcion = 0;
    Serial3.println(F("STOP,TIMEOUT;"));
  }

  // 3) Ciclo de control: se ejecuta cada Period (10 ms)
  newtime = micros();
  if ((unsigned long)(newtime - time_ant) >= Period) {
    unsigned long deltaUs = newtime - time_ant;   // Tiempo real transcurrido [us]
    time_ant = newtime;

    // Lectura atómica de los encoders (se modifican dentro de interrupciones)
    noInterrupts();
    newposition1 = encoder1Pos;
    newposition2 = encoder2Pos;
    interrupts();

    // Velocidad medida [RPM] = variación de cuentas en el periodo
    vel1 = (float)(newposition1 - oldposition1) * FACTOR_RPM / (float)deltaUs;
    vel2 = (float)(newposition2 - oldposition2) * FACTOR_RPM / (float)deltaUs;
    oldposition1 = newposition1;
    oldposition2 = newposition2;

    // PID
    // Forma incremental (discreta):
    //   u(k) = u(k-1) + q0*e(k) + q1*e(k-1) + q2*e(k-2)
    //   q0 = Kp + Ki*dt + Kd/dt,  q1 = -Kp - 2*Kd/dt,  q2 = Kd/dt

    // izq
    float q0_i = Kp_i + dt * Ki_i + Kd_i / dt;
    float q1_i = -Kp_i - 2.0f * Kd_i / dt;
    float q2_i = Kd_i / dt;

    // der
    float q0_d = Kp_d + dt * Ki_d + Kd_d / dt;
    float q1_d = -Kp_d - 2.0f * Kd_d / dt;
    float q2_d = Kd_d / dt;

    // Motor 1 = izquierda
    error1 = velizq - vel1;
    float control1 = control1_ant + q0_i * error1 + q1_i * error1_ant + q2_i * error1_ant2;
    control1 = constrain(control1, -400.0f, 400.0f);   // Saturación del driver
    error1_ant2 = error1_ant;
    error1_ant = error1;
    control1_ant = control1;

    // Motor 2 = derecha
    error2 = velder - vel2;
    float control2 = control2_ant + q0_d * error2 + q1_d * error2_ant + q2_d * error2_ant2;
    control2 = constrain(control2, -400.0f, 400.0f);   // Saturación del driver
    error2_ant2 = error2_ant;
    error2_ant = error2;
    control2_ant = control2;


    // Si la referencia es 0 se reinicia la memoria del PID y el motor se
    // apaga inmediatamente (evita que el término integral lo mantenga girando)
    if (velizq == 0.0f) {control1 = control1_ant = error1 = error1_ant = error1_ant2 = 0.0f;}
    if (velder == 0.0f) {control2 = control2_ant = error2 = error2_ant = error2_ant2 = 0.0f;}

    // Aplicar comando a los motores (-400 a 400)
    motor1 = control1;
    motor2 = control2;
    md.setM1Speed((int)motor1);
    md.setM2Speed((int)motor2);

    // Telemetría por USB cada 5 ciclos (50 ms): velizq,velder,error2,vel1,vel2
    if (++contadorTelemetria >= 5) {
      contadorTelemetria = 0;
      //Serial.print(F("$,"));
      //Serial.print(newtime);       Serial.print(',');
      //Serial.print(newposition1);  Serial.print(',');
      //Serial.print(newposition2);  Serial.print(',');
      Serial.print(velizq);        Serial.print(',');
      Serial.print(velder);        Serial.print(',');
      Serial.print(error2);        Serial.print(',');
      Serial.print(vel1);          Serial.print(',');
      Serial.println(vel2);          Serial.print(',');
      //Serial.print(motor1);        Serial.print(',');
      //Serial.println(motor2);
    }
  }
}