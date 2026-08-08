// ============================================================
//  Controlador PID discreto (forma incremental / velocidad)
//  Planta: motor - generador DC
//  Control en VOLTIOS, parametros por serial desde la HMI
// ============================================================
//
//  PROTOCOLO SERIAL
//  ----------------
//  Recibe:
//    P,kp,ti,td,ts   -> carga parametros (solo con el motor detenido)
//    B,bias,vfuente  -> punto de operacion y voltaje de la fuente
//    S,ref           -> inicia el control con esa consigna
//    R,ref           -> cambia la consigna en caliente
//    X               -> detiene, PWM a cero
//    Q               -> consulta los parametros actuales
//
//  Envia:
//    D,tiempo,voltaje,error,pwm   -> una linea por muestra
//    OK_PARAM / OK_START / OK_STOP / PARAM,...
// ============================================================

// --- Parametros del controlador ---
float Kp = 0.163414;
float Ti = 0.165463865649618;
float Td = 0.018299369825879;
float Ts = 0.01;              // segundos
float q0, q1, q2;

unsigned long TsMs = 10;      // Ts en milisegundos

// --- Escala del sensor ---
const float CUENTAS_POR_VOLT = 1023.0 / 25.0;

// --- Punto de operacion y actuador ---
// El controlador trabaja en VOLTIOS (igual que el modelo de Simulink).
// BIAS es la parte fija que la identificacion incremental no cubre.
float BIAS          = 7.0;    // voltios que se le mandan al motor en reposo
float VOLT_FUENTE   = 12.0;   // alimentacion del motor
float PWM_POR_VOLT  = 255.0 / 12.0;

// --- Variables del Sistema ---
float puntoConsigna = 0.0;    // VOLTIOS
float valorProceso;
float error;
float errorAnterior;
float errorPrevio;
float salidaControl;          // VOLTIOS (salida del controlador)
float salidaControlAnterior;
int   pwmAplicado = 0;        // lo que realmente recibe el motor

bool controlActivo = false;

unsigned long tiempoActual, tiempoAnterior, tiempoInicio;

// --- Pines de Hardware ---
#define ENA          9
#define IN3          8
#define IN4          7
#define SENSOR_VOLT  A0

// ------------------------------------------------------------
void calcularConstantes()
{
    q0 =  Kp * (1.0 + Ts / (2.0 * Ti) + Td / Ts);
    q1 = -Kp * (1.0 - Ts / (2.0 * Ti) + (2.0 * Td) / Ts);
    q2 =  Kp * (Td / Ts);
}

void reiniciarEstado()
{
    error                 = 0.0;
    errorAnterior         = 0.0;
    errorPrevio           = 0.0;
    salidaControl         = 0.0;
    salidaControlAnterior = 0.0;
    pwmAplicado           = 0;
    analogWrite(ENA, 0);
}

void enviarParametros()
{
    Serial.print("PARAM,");
    Serial.print(Kp, 6);  Serial.print(",");
    Serial.print(Ti, 6);  Serial.print(",");
    Serial.print(Td, 6);  Serial.print(",");
    Serial.print(Ts, 4);  Serial.print(",");
    Serial.print(BIAS, 3); Serial.print(",");
    Serial.println(VOLT_FUENTE, 2);
}

// ------------------------------------------------------------
void procesarComando()
{
    if (!Serial.available()) return;

    String linea = Serial.readStringUntil('\n');
    linea.trim();
    if (linea.length() == 0) return;

    char cmd = linea.charAt(0);

    // ---- Cargar parametros ----
    if (cmd == 'P')
    {
        int p1 = linea.indexOf(',');
        int p2 = linea.indexOf(',', p1 + 1);
        int p3 = linea.indexOf(',', p2 + 1);
        int p4 = linea.indexOf(',', p3 + 1);

        if (p1 < 0 || p2 < 0 || p3 < 0 || p4 < 0) return;

        float nKp = linea.substring(p1 + 1, p2).toFloat();
        float nTi = linea.substring(p2 + 1, p3).toFloat();
        float nTd = linea.substring(p3 + 1, p4).toFloat();
        float nTs = linea.substring(p4 + 1).toFloat();

        // Ti y Ts no pueden ser cero (van en denominadores)
        if (nTi <= 0.0) return;
        if (nTs <= 0.0) return;

        Kp = nKp;  Ti = nTi;  Td = nTd;  Ts = nTs;

        TsMs = (unsigned long)(Ts * 1000.0);
        if (TsMs < 1) TsMs = 1;

        calcularConstantes();
        reiniciarEstado();
        controlActivo = false;

        Serial.println("OK_PARAM");
    }

    // ---- Iniciar control ----
    else if (cmd == 'S')
    {
        int p1 = linea.indexOf(',');
        if (p1 > 0)
        {
            float v = linea.substring(p1 + 1).toFloat();
            if (v >= 0.0 && v <= 25.0) puntoConsigna = v;
        }

        reiniciarEstado();

        tiempoAnterior = millis();
        tiempoInicio   = tiempoAnterior;
        controlActivo  = true;

        Serial.println("OK_START");
    }

    // ---- Cambiar consigna en caliente ----
    else if (cmd == 'R')
    {
        int p1 = linea.indexOf(',');
        if (p1 > 0)
        {
            float v = linea.substring(p1 + 1).toFloat();
            if (v >= 0.0 && v <= 25.0) puntoConsigna = v;
        }
    }

    // ---- Detener ----
    else if (cmd == 'X')
    {
        controlActivo = false;
        reiniciarEstado();
        Serial.println("OK_STOP");
    }

    // ---- Bias y voltaje de fuente ----
    else if (cmd == 'B')
    {
        int p1 = linea.indexOf(',');
        int p2 = linea.indexOf(',', p1 + 1);
        if (p1 < 0 || p2 < 0) return;

        float nBias = linea.substring(p1 + 1, p2).toFloat();
        float nVf   = linea.substring(p2 + 1).toFloat();

        if (nVf <= 0.0) return;
        if (nBias < 0.0 || nBias > nVf) return;

        BIAS         = nBias;
        VOLT_FUENTE  = nVf;
        PWM_POR_VOLT = 255.0 / VOLT_FUENTE;

        reiniciarEstado();
        controlActivo = false;

        Serial.println("OK_BIAS");
    }

    // ---- Consultar parametros ----
    else if (cmd == 'Q')
    {
        enviarParametros();
    }
}

// ------------------------------------------------------------
void setup()
{
    Serial.begin(115200);

    pinMode(ENA, OUTPUT);
    pinMode(IN3, OUTPUT);
    pinMode(IN4, OUTPUT);

    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);

    analogWrite(ENA, 0);

    TsMs = (unsigned long)(Ts * 1000.0);
    PWM_POR_VOLT = 255.0 / VOLT_FUENTE;
    calcularConstantes();
    reiniciarEstado();

    tiempoAnterior = millis();
}

// ------------------------------------------------------------
void loop()
{
    procesarComando();

    if (!controlActivo) return;

    tiempoActual = millis();

    if (tiempoActual - tiempoAnterior >= TsMs)
    {
        // 1. Leer el sensor y pasarlo a voltios
        int adc = analogRead(SENSOR_VOLT);
        valorProceso = adc / CUENTAS_POR_VOLT;

        // 2. Error en voltios
        error = puntoConsigna - valorProceso;

        // 3. Salida del controlador, en VOLTIOS
        salidaControl = (q0 * error)
                      + (q1 * errorAnterior)
                      + (q2 * errorPrevio)
                      + salidaControlAnterior;

        // 4. Sumar el punto de operacion y convertir a PWM
        float pwm = (salidaControl + BIAS) * PWM_POR_VOLT;
        pwm = constrain(pwm, 0.0, 255.0);
        pwmAplicado = (int)pwm;

        // 5. Aplicar al motor
        analogWrite(ENA, pwmAplicado);

        // 6. Anti-windup: devolver el valor saturado en unidades del modelo
        salidaControlAnterior = (pwm / PWM_POR_VOLT) - BIAS;
        errorPrevio           = errorAnterior;
        errorAnterior         = error;

        // 7. Temporizador
        tiempoAnterior = tiempoActual;

        // 8. Enviar muestra
        Serial.print("D,");
        Serial.print((tiempoActual - tiempoInicio) / 1000.0, 3);  Serial.print(",");
        Serial.print(valorProceso, 3);                            Serial.print(",");
        Serial.print(error, 3);                                   Serial.print(",");
        Serial.println(pwmAplicado);
    }
}
