#define ENA 9
#define IN3 8
#define IN4 7
#define SENSOR_VOLT A0

const unsigned long Ts = 1000;   // 1 ms

int pwm1 = 0;
int pwm2 = 0;

unsigned long tiempoEscalon1_us;
unsigned long tiempoPrimeraMuestra_us;
unsigned long tiempoSegundoEscalon_us;

bool pruebaActiva = false;
bool primerEscalonAplicado = false;
bool segundoEscalonAplicado = false;

unsigned long t0;
unsigned long tMuestra;
unsigned long tInicioPrimerEscalon;
unsigned long tInicioSegundoEscalon;

void esperarParametros()
{
    while (!Serial.available());

    String datos = Serial.readStringUntil('\n');

    int p1 = datos.indexOf(',');
    int p2 = datos.indexOf(',', p1 + 1);
    int p3 = datos.indexOf(',', p2 + 1);
    int p4 = datos.indexOf(',', p3 + 1);

    pwm1 = datos.substring(0, p1).toInt();

    tiempoEscalon1_us =
        datos.substring(p1 + 1, p2).toFloat() * 1000000UL;

    pwm2 =
        datos.substring(p2 + 1, p3).toInt();

    tiempoSegundoEscalon_us =
        datos.substring(p3 + 1, p4).toFloat() * 1000000UL;

    tiempoPrimeraMuestra_us =
        datos.substring(p4 + 1).toFloat() * 1000000UL;

    analogWrite(ENA,0);

    primerEscalonAplicado = false;
    segundoEscalonAplicado = false;

    t0 = micros();
    tMuestra = t0;

    pruebaActiva = true;

    Serial.println("READY");
}

void setup()
{
    Serial.begin(1000000);

    pinMode(ENA,OUTPUT);
    pinMode(IN3,OUTPUT);
    pinMode(IN4,OUTPUT);

    digitalWrite(IN3,LOW);
    digitalWrite(IN4,HIGH);

    analogWrite(ENA,0);
}

void loop()
{
    if(!pruebaActiva)
    {
        esperarParametros();
        return;
    }

    unsigned long ahora = micros();

    // Primer escalón
    if(!primerEscalonAplicado &&
       ahora-t0>=tiempoEscalon1_us)
    {
        analogWrite(ENA,pwm1);

        primerEscalonAplicado=true;

        tInicioPrimerEscalon=ahora;
    }

    // Segundo escalón
    if(primerEscalonAplicado &&
       !segundoEscalonAplicado &&
       ahora-tInicioPrimerEscalon>=tiempoPrimeraMuestra_us)
    {
        analogWrite(ENA,pwm2);

        segundoEscalonAplicado=true;

        tInicioSegundoEscalon=ahora;
    }

    // Muestreo
    if(ahora-tMuestra>=Ts)
    {
        tMuestra+=Ts;

        int adc=analogRead(SENSOR_VOLT);

        Serial.println(adc);
    }

    // Fin de prueba
    if(segundoEscalonAplicado &&
       ahora-tInicioSegundoEscalon>=tiempoSegundoEscalon_us)
    {
        analogWrite(ENA,0);

        pruebaActiva=false;
    }
}