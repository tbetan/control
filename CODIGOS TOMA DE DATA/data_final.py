import serial
import pandas as pd
from datetime import datetime
import time

# =====================================================
# CONFIGURACIÓN
# =====================================================

BAUDIOS = 1000000
FACTOR_VOLT = 25.0 / 1023.0
TS = 0.001

print("\n=========== IDENTIFICACIÓN DE PLANTA ===========\n")

COM = input("Puerto COM (Ej: COM5): ")

PWM1 = int(input("PWM del primer escalón (0-255): "))

TIEMPO_ESCALON1 = float(input("Tiempo para enviar el primer escalón (s): "))

TIEMPO_PRIMERA_MUESTRA = float(input("Tiempo de la primera muestra (s): "))

PWM2 = int(input("PWM del segundo escalón (0-255): "))

TIEMPO_SEGUNDO_ESCALON = float(input("Tiempo del segundo escalón (s): "))

NUM_PRUEBAS = int(input("Cantidad de pruebas: "))

TIEMPO_TOTAL = (
    TIEMPO_ESCALON1 +
    TIEMPO_PRIMERA_MUESTRA +
    TIEMPO_SEGUNDO_ESCALON
)

NUM_MUESTRAS = int(TIEMPO_TOTAL / TS)

print("\n======================================")
print(f"Tiempo total por prueba : {TIEMPO_TOTAL:.3f} s")
print(f"Muestras por prueba     : {NUM_MUESTRAS}")
print(f"Número de pruebas       : {NUM_PRUEBAS}")
print("======================================\n")

# =====================================================
# CONEXIÓN
# =====================================================

print("Conectando con Arduino...")

ser = serial.Serial(COM, BAUDIOS, timeout=2)

time.sleep(2)

ser.reset_input_buffer()

# =====================================================
# BUCLE DE PRUEBAS
# =====================================================

for prueba in range(1, NUM_PRUEBAS + 1):

    print("\n======================================")
    print(f"PRUEBA {prueba} DE {NUM_PRUEBAS}")
    print("======================================")

    mensaje = (
        f"{PWM1},"
        f"{TIEMPO_ESCALON1},"
        f"{PWM2},"
        f"{TIEMPO_SEGUNDO_ESCALON},"
        f"{TIEMPO_PRIMERA_MUESTRA}\n"
    )

    ser.reset_input_buffer()

    ser.write(mensaje.encode())

    print("Esperando READY...")

    while True:

        respuesta = ser.readline().decode(errors="ignore").strip()

        if respuesta == "READY":
            break

    print("Arduino listo.")

    tiempo = []
    pwm = []
    voltaje = []

    contador = 0

    while contador < NUM_MUESTRAS:

        linea = ser.readline().decode(errors="ignore").strip()

        if linea == "":
            continue

        try:
            lectura = int(linea)
        except:
            continue

        t = contador * TS

        tiempo.append(t)

        # ==========================================
        # Reconstrucción del PWM aplicado
        # ==========================================

        if t < TIEMPO_ESCALON1:

            pwm_actual = 0

        elif t < (TIEMPO_ESCALON1 + TIEMPO_PRIMERA_MUESTRA):

            pwm_actual = PWM1

        else:

            pwm_actual = PWM2

        pwm.append(pwm_actual)

        voltaje.append(lectura * FACTOR_VOLT)

        contador += 1

        if contador % 500 == 0:

            print(
                f"Prueba {prueba}: {contador}/{NUM_MUESTRAS} muestras",
                end="\r"
            )

    print()

    # =====================================================
    # GUARDAR EXCEL
    # =====================================================

    df = pd.DataFrame({
        "Tiempo (s)": tiempo,
        "PWM aplicado": pwm,
        "Voltaje (V)": voltaje
    })

    nombre = (
        f"Datos_Planta_Prueba_{prueba:02d}_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".xlsx"
    )

    df.to_excel(nombre, index=False)

    print(f"Archivo guardado: {nombre}")

print("\n======================================")
print("TODAS LAS PRUEBAS HAN FINALIZADO")
print("======================================")

ser.close()