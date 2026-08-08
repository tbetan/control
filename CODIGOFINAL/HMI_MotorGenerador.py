"""
============================================================
 HMI - Control PID Motor/Generador DC
 Universidad de Pamplona - Control Industrial 1
============================================================

 Requisitos:
     pip install pyserial matplotlib

 Uso:
     python HMI_MotorGenerador.py

 Flujo:
     1. Conectar al puerto COM
     2. Escribir Kp, Ti, Td, Ts  ->  Aplicar parámetros
     3. Elegir la referencia     ->  Iniciar control
     4. Mover la referencia en caliente para hacer escalones
     5. Detener  ->  Guardar CSV
============================================================
"""

import csv
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import serial
import serial.tools.list_ports

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ============================================================
#  Sistema de diseño
# ============================================================
# Direccion: panel de instrumento de banco.  Gris frio de chasis,
# tarjetas mas claras, y un unico visor tipo LCD para la medicion.

# --- Superficies ---
CHASIS      = "#aab2be"      # fondo general
PANEL       = "#e2e6eb"      # tarjetas
PANEL_HOND  = "#d2d8e0"      # zonas hundidas dentro de una tarjeta
LCD         = "#dae2d9"      # visor de medicion
LIENZO      = "#ffffff"      # area de las graficas
CAMPO       = "#f3f5f7"      # campos de entrada

# --- Lineas ---
BORDE       = "#98a1af"      # contorno de tarjeta
BORDE_FINO  = "#c2c9d3"      # separadores internos
REJILLA     = "#e6e9ed"      # cuadricula de graficas

# --- Tinta ---
TINTA       = "#1a2029"      # texto principal y digitos del visor
TINTA_2     = "#525c6b"      # etiquetas
TINTA_3     = "#7b8593"      # texto terciario / eyebrows

# --- Acentos ---
ACENTO      = "#2f5d8a"      # accion primaria
ACENTO_HL   = "#3a6f9f"
OK          = "#2c6b46"      # en consigna / conectado
OK_HL       = "#347e52"
ALERTA      = "#a3452b"      # detener / saturacion
ALERTA_HL   = "#bb5134"
NEUTRO      = "#5d6775"      # acciones secundarias
NEUTRO_HL   = "#6d7787"

# --- Trazos de las graficas ---
TR_MEDIDO   = "#1a5c7a"
TR_CONSIGNA = "#b4472c"
TR_ERROR    = "#a06a14"

# --- Tipografia ---
F_EYEBROW   = ("Segoe UI", 8, "bold")
F_ETIQUETA  = ("Segoe UI", 9)
F_ETIQ_B    = ("Segoe UI", 9, "bold")
F_MINI      = ("Segoe UI", 8)
F_BOTON     = ("Segoe UI", 9, "bold")
F_DATO      = ("Consolas", 11, "bold")
F_MONO      = ("Consolas", 10)
F_MONO_MINI = ("Consolas", 8)
F_VISOR     = ("Consolas", 30, "bold")
F_VISOR_2   = ("Consolas", 18, "bold")

# --- Ritmo ---
PAD  = 12
GAP  = 8

# --- Parametros identificados de la planta ---
PREDETERMINADOS = {
    "kp":   "0.163414",
    "ti":   "0.165464",
    "td":   "0.018299",
    "ts":   "0.01",
    "bias": "7.0",
    "vfte": "12.0",
}

BAUDIOS     = 115200
VENTANA_SEG = 15.0
REFRESCO_MS = 50


# ============================================================
class HMIMotorGenerador:

    def __init__(self, root):
        self.root = root
        self.root.title("Control PID  ·  Motor / Generador DC")
        self.root.configure(bg=CHASIS)

        alto  = min(900, self.root.winfo_screenheight() - 80)
        ancho = min(1280, self.root.winfo_screenwidth() - 40)
        self.root.geometry(f"{ancho}x{alto}")
        self.root.minsize(920, 520)

        # Estado
        self.puerto = None
        self.hilo_lectura = None
        self.leyendo = False
        self.control_activo = False
        self.cola = queue.Queue()
        self._entradas = []

        # Buffers
        self.t_datos = []
        self.v_datos = []
        self.e_datos = []
        self.p_datos = []
        self.ref_datos = []
        self.uf_datos = []
        self.us_datos = []
        self.registro_completo = []

        self._construir_interfaz()
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.root.after(REFRESCO_MS, self._actualizar)

    # --------------------------------------------------------
    #  Estructura
    # --------------------------------------------------------
    def _construir_interfaz(self):
        contenedor = tk.Frame(self.root, bg=CHASIS)
        contenedor.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        # ---- Columna izquierda, con scroll ----
        marco_izq = tk.Frame(contenedor, bg=CHASIS, width=372)
        marco_izq.pack(side="left", fill="y", padx=(0, PAD))
        marco_izq.pack_propagate(False)

        self.lienzo_izq = tk.Canvas(marco_izq, bg=CHASIS, highlightthickness=0,
                                    width=354)
        barra = ttk.Scrollbar(marco_izq, orient="vertical",
                              command=self.lienzo_izq.yview)
        self.lienzo_izq.configure(yscrollcommand=barra.set)

        barra.pack(side="right", fill="y")
        self.lienzo_izq.pack(side="left", fill="both", expand=True)

        izq = tk.Frame(self.lienzo_izq, bg=CHASIS)
        self.lienzo_izq.create_window((0, 0), window=izq, anchor="nw", width=350)

        izq.bind("<Configure>", lambda _:
                 self.lienzo_izq.configure(scrollregion=self.lienzo_izq.bbox("all")))

        self.lienzo_izq.bind_all(
            "<MouseWheel>",
            lambda e: self.lienzo_izq.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.lienzo_izq.bind_all(
            "<Button-4>", lambda e: self.lienzo_izq.yview_scroll(-1, "units"))
        self.lienzo_izq.bind_all(
            "<Button-5>", lambda e: self.lienzo_izq.yview_scroll(1, "units"))

        der = tk.Frame(contenedor, bg=CHASIS)
        der.pack(side="right", fill="both", expand=True)

        self._panel_visor(izq)
        self._panel_conexion(izq)
        self._panel_referencia(izq)
        self._panel_operacion(izq)
        self._panel_parametros(izq)
        self._panel_indicadores(izq)
        self._panel_grafica(der)

        self._alternar_predeterminados()

    # --------------------------------------------------------
    #  Primitivas de interfaz
    # --------------------------------------------------------
    def _tarjeta(self, padre, titulo=None):
        """Tarjeta con contorno fino y, opcionalmente, un eyebrow."""
        cont = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE,
                        highlightthickness=1)
        cont.pack(fill="x", pady=(0, GAP))

        if titulo:
            tk.Label(cont, text=titulo.upper(), bg=PANEL, fg=TINTA_3,
                     font=F_EYEBROW, anchor="w").pack(
                     fill="x", padx=PAD, pady=(10, 0))
            tk.Frame(cont, bg=BORDE_FINO, height=1).pack(
                     fill="x", padx=PAD, pady=(5, 0))

        cuerpo = tk.Frame(cont, bg=PANEL)
        cuerpo.pack(fill="x", padx=PAD, pady=(10, PAD))
        return cuerpo

    def _campo(self, padre, etiqueta, valor):
        fila = tk.Frame(padre, bg=PANEL)
        fila.pack(fill="x", pady=2)
        tk.Label(fila, text=etiqueta, bg=PANEL, fg=TINTA_2,
                 font=F_ETIQUETA, width=5, anchor="w").pack(side="left")
        var = tk.StringVar(value=valor)
        ent = tk.Entry(fila, textvariable=var, bg=CAMPO, fg=TINTA,
                       insertbackground=TINTA, justify="right",
                       relief="flat", highlightthickness=1,
                       highlightbackground=BORDE_FINO, highlightcolor=ACENTO,
                       font=F_MONO)
        ent.pack(side="left", fill="x", expand=True, ipady=4)
        self._entradas.append(ent)
        return var

    def _boton(self, padre, texto, fondo, hover, comando, **kw):
        return tk.Button(padre, text=texto, bg=fondo, fg="#ffffff",
                         activebackground=hover, activeforeground="#ffffff",
                         relief="flat", borderwidth=0, font=F_BOTON,
                         cursor="hand2", command=comando,
                         disabledforeground="#ffffff", **kw)

    # --------------------------------------------------------
    #  1. Visor de medición
    # --------------------------------------------------------
    def _panel_visor(self, padre):
        self.cont_visor = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE,
                                   highlightthickness=1)
        self.cont_visor.pack(fill="x", pady=(0, GAP))

        cab = tk.Frame(self.cont_visor, bg=PANEL)
        cab.pack(fill="x", padx=PAD, pady=(10, 0))
        tk.Label(cab, text="MEDICIÓN", bg=PANEL, fg=TINTA_3,
                 font=F_EYEBROW).pack(side="left")
        self.var_visor_ref = tk.StringVar(value="ref  —")
        tk.Label(cab, textvariable=self.var_visor_ref, bg=PANEL, fg=TINTA_3,
                 font=F_MONO_MINI).pack(side="right")

        # --- Visor tipo LCD ---
        self.lcd = tk.Frame(self.cont_visor, bg=LCD,
                            highlightbackground=BORDE, highlightthickness=1)
        self.lcd.pack(fill="x", padx=PAD, pady=(6, 0))

        cuerpo = tk.Frame(self.lcd, bg=LCD)
        cuerpo.pack(fill="x", padx=14, pady=10)

        # Voltaje
        blq_v = tk.Frame(cuerpo, bg=LCD)
        blq_v.pack(side="left")
        self.var_visor = tk.StringVar(value="0.00")
        tk.Label(blq_v, textvariable=self.var_visor, bg=LCD, fg=TINTA,
                 font=F_VISOR).pack(side="left")
        tk.Label(blq_v, text="V", bg=LCD, fg=TINTA_2,
                 font=("Segoe UI", 12)).pack(side="left", padx=(4, 0), pady=(14, 0))

        tk.Frame(cuerpo, bg=BORDE_FINO, width=1).pack(
            side="left", fill="y", padx=16, pady=4)

        # PWM
        blq_p = tk.Frame(cuerpo, bg=LCD)
        blq_p.pack(side="left")
        tk.Label(blq_p, text="PWM", bg=LCD, fg=TINTA_3,
                 font=F_EYEBROW).pack(anchor="w")
        self.var_visor_pwm = tk.StringVar(value="0")
        tk.Label(blq_p, textvariable=self.var_visor_pwm, bg=LCD, fg=TINTA,
                 font=F_VISOR_2).pack(anchor="w")

        # --- Barras de estado ---
        barras = tk.Frame(self.cont_visor, bg=PANEL)
        barras.pack(fill="x", padx=PAD, pady=(8, PAD))

        self.barra_lienzo = tk.Canvas(barras, height=4, bg=PANEL_HOND,
                                      highlightthickness=0)
        self.barra_lienzo.pack(fill="x")
        self.barra = self.barra_lienzo.create_rectangle(
            0, 0, 0, 4, fill=ACENTO, width=0)

        self.barra_pwm_lienzo = tk.Canvas(barras, height=4, bg=PANEL_HOND,
                                          highlightthickness=0)
        self.barra_pwm_lienzo.pack(fill="x", pady=(3, 0))
        self.barra_pwm = self.barra_pwm_lienzo.create_rectangle(
            0, 0, 0, 4, fill=NEUTRO, width=0)

        pie = tk.Frame(barras, bg=PANEL)
        pie.pack(fill="x", pady=(4, 0))
        tk.Label(pie, text="salida", bg=PANEL, fg=TINTA_3,
                 font=F_MINI).pack(side="left")
        tk.Label(pie, text="actuador", bg=PANEL, fg=TINTA_3,
                 font=F_MINI).pack(side="right")

    def _actualizar_visor(self, voltaje, consigna, pwm=0):
        self.var_visor.set(f"{voltaje:.2f}")
        self.var_visor_pwm.set(f"{int(pwm)}")
        self.var_visor_ref.set(f"ref  {consigna:.2f} V")

        ancho = self.barra_lienzo.winfo_width()
        if ancho > 1 and consigna > 0.01:
            frac = max(0.0, min(1.0, voltaje / consigna))
            self.barra_lienzo.coords(self.barra, 0, 0, ancho * frac, 4)
            dentro = abs(voltaje - consigna) <= max(0.05, consigna * 0.02)
            self.barra_lienzo.itemconfig(self.barra, fill=OK if dentro else ACENTO)
            self.lcd.config(highlightbackground=OK if dentro else BORDE)

        ancho_p = self.barra_pwm_lienzo.winfo_width()
        if ancho_p > 1:
            frac_p = max(0.0, min(1.0, pwm / 255.0))
            self.barra_pwm_lienzo.coords(self.barra_pwm, 0, 0, ancho_p * frac_p, 4)
            self.barra_pwm_lienzo.itemconfig(
                self.barra_pwm, fill=ALERTA if pwm >= 255 else NEUTRO)

    def _resetear_visor(self):
        self.var_visor.set("0.00")
        self.var_visor_pwm.set("0")
        self.var_visor_ref.set("ref  —")
        self.barra_lienzo.coords(self.barra, 0, 0, 0, 4)
        self.barra_pwm_lienzo.coords(self.barra_pwm, 0, 0, 0, 4)
        self.lcd.config(highlightbackground=BORDE)

    # --------------------------------------------------------
    #  2. Conexión
    # --------------------------------------------------------
    def _panel_conexion(self, padre):
        c = self._tarjeta(padre, "Conexión")

        fila = tk.Frame(c, bg=PANEL)
        fila.pack(fill="x", pady=(0, GAP))
        tk.Label(fila, text="Puerto", bg=PANEL, fg=TINTA_2,
                 font=F_ETIQUETA, width=7, anchor="w").pack(side="left")

        self.var_puerto = tk.StringVar()
        self.combo_puerto = ttk.Combobox(fila, textvariable=self.var_puerto,
                                         font=F_MONO, state="readonly")
        self.combo_puerto.pack(side="left", fill="x", expand=True)
        self._refrescar_puertos()

        fila2 = tk.Frame(c, bg=PANEL)
        fila2.pack(fill="x")
        self.btn_conectar = self._boton(fila2, "Conectar", ACENTO, ACENTO_HL,
                                        self._conectar)
        self.btn_conectar.pack(side="left", fill="x", expand=True, ipady=7,
                               padx=(0, 3))
        self.btn_desconectar = self._boton(fila2, "Desconectar", NEUTRO, NEUTRO_HL,
                                           self._desconectar, state="disabled")
        self.btn_desconectar.pack(side="left", fill="x", expand=True, ipady=7,
                                  padx=(3, 0))

        fila3 = tk.Frame(c, bg=PANEL)
        fila3.pack(fill="x", pady=(GAP, 0))
        self.lbl_estado = tk.Label(fila3, text="●  Desconectado", bg=PANEL,
                                   fg=TINTA_3, font=F_ETIQ_B, anchor="w")
        self.lbl_estado.pack(side="left")
        tk.Button(fila3, text="actualizar", bg=PANEL, fg=TINTA_3, relief="flat",
                  font=F_MINI, cursor="hand2", activebackground=PANEL,
                  activeforeground=ACENTO, borderwidth=0,
                  command=self._refrescar_puertos).pack(side="right")

    # --------------------------------------------------------
    #  3. Referencia
    # --------------------------------------------------------
    def _panel_referencia(self, padre):
        c = self._tarjeta(padre, "Referencia")

        self.var_ref = tk.DoubleVar(value=5.0)
        self.slider_ref = tk.Scale(c, from_=0.0, to=10.0, resolution=0.1,
                                   orient="horizontal", variable=self.var_ref,
                                   bg=PANEL, fg=TINTA_2, troughcolor=PANEL_HOND,
                                   highlightthickness=0, relief="flat",
                                   activebackground=ACENTO, borderwidth=1,
                                   sliderrelief="flat", font=F_MONO_MINI,
                                   command=self._cambiar_referencia)
        self.slider_ref.pack(fill="x")

        fila = tk.Frame(c, bg=PANEL)
        fila.pack(fill="x", pady=(2, 0))
        tk.Label(fila, text="Consigna", bg=PANEL, fg=TINTA_2,
                 font=F_ETIQUETA, anchor="w").pack(side="left")
        tk.Label(fila, text="V", bg=PANEL, fg=TINTA_3,
                 font=F_ETIQUETA).pack(side="right", padx=(4, 0))
        self.var_ref_txt = tk.StringVar(value="5.0")
        ent = tk.Entry(fila, textvariable=self.var_ref_txt, bg=CAMPO, fg=TINTA,
                       insertbackground=TINTA, justify="right", relief="flat",
                       highlightthickness=1, highlightbackground=BORDE_FINO,
                       highlightcolor=ACENTO, font=F_DATO, width=8)
        ent.pack(side="right", ipady=4)
        ent.bind("<Return>", self._referencia_desde_texto)

        tk.Label(c, text="Se puede mover con el control en marcha",
                 bg=PANEL, fg=TINTA_3, font=F_MINI, anchor="w").pack(
                 fill="x", pady=(6, 0))

    # --------------------------------------------------------
    #  4. Operación
    # --------------------------------------------------------
    def _panel_operacion(self, padre):
        fila = tk.Frame(padre, bg=CHASIS)
        fila.pack(fill="x", pady=(0, GAP))

        self.btn_iniciar = self._boton(fila, "Iniciar control", OK, OK_HL,
                                       self._iniciar_control, state="disabled")
        self.btn_iniciar.pack(side="left", fill="x", expand=True, ipady=12,
                              padx=(0, 3))
        self.btn_detener = self._boton(fila, "Detener", ALERTA, ALERTA_HL,
                                       self._detener_control, state="disabled")
        self.btn_detener.pack(side="left", fill="x", expand=True, ipady=12,
                              padx=(3, 0))

    # --------------------------------------------------------
    #  5. Parámetros
    # --------------------------------------------------------
    def _panel_parametros(self, padre):
        c = self._tarjeta(padre, "Controlador")

        self.usar_pred = tk.BooleanVar(value=True)
        tk.Checkbutton(c, text="Usar valores identificados",
                       variable=self.usar_pred,
                       command=self._alternar_predeterminados,
                       bg=PANEL, fg=TINTA, selectcolor=CAMPO,
                       activebackground=PANEL, activeforeground=ACENTO,
                       font=F_ETIQ_B, anchor="w", cursor="hand2",
                       highlightthickness=0, borderwidth=0).pack(
                       fill="x", pady=(0, GAP))

        self.var_kp = self._campo(c, "Kp", PREDETERMINADOS["kp"])
        self.var_ti = self._campo(c, "Ti", PREDETERMINADOS["ti"])
        self.var_td = self._campo(c, "Td", PREDETERMINADOS["td"])
        self.var_ts = self._campo(c, "Ts", PREDETERMINADOS["ts"])

        tk.Frame(c, bg=BORDE_FINO, height=1).pack(fill="x", pady=GAP)

        self.var_bias = self._campo(c, "Bias", PREDETERMINADOS["bias"])
        self.var_vfte = self._campo(c, "Vfte", PREDETERMINADOS["vfte"])

        # --- Bloque derivado, hundido ---
        derivado = tk.Frame(c, bg=PANEL_HOND)
        derivado.pack(fill="x", pady=(GAP, 0))
        interior = tk.Frame(derivado, bg=PANEL_HOND)
        interior.pack(fill="x", padx=10, pady=8)

        tk.Label(interior, text="COEFICIENTES DISCRETOS", bg=PANEL_HOND,
                 fg=TINTA_3, font=F_EYEBROW, anchor="w").pack(fill="x")
        self.lbl_q = tk.Label(interior, text="—", bg=PANEL_HOND, fg=TINTA_2,
                              font=F_MONO_MINI, anchor="w", justify="left")
        self.lbl_q.pack(fill="x", pady=(3, 0))
        self.lbl_bias = tk.Label(interior, text="—", bg=PANEL_HOND, fg=TINTA_2,
                                 font=F_MONO_MINI, anchor="w")
        self.lbl_bias.pack(fill="x")

        self.btn_aplicar = self._boton(c, "Aplicar parámetros", ACENTO, ACENTO_HL,
                                       self._aplicar_parametros, state="disabled")
        self.btn_aplicar.pack(fill="x", ipady=7, pady=(GAP, 4))

        tk.Label(c, text="Solo se aplican con el motor detenido",
                 bg=PANEL, fg=TINTA_3, font=F_MINI, anchor="w").pack(fill="x")

    def _alternar_predeterminados(self):
        """Activado: restaura los valores identificados y bloquea los campos."""
        bloqueado = self.usar_pred.get()

        if bloqueado:
            self.var_kp.set(PREDETERMINADOS["kp"])
            self.var_ti.set(PREDETERMINADOS["ti"])
            self.var_td.set(PREDETERMINADOS["td"])
            self.var_ts.set(PREDETERMINADOS["ts"])
            self.var_bias.set(PREDETERMINADOS["bias"])
            self.var_vfte.set(PREDETERMINADOS["vfte"])

        for ent in self._entradas:
            ent.config(state="readonly" if bloqueado else "normal",
                       readonlybackground=PANEL_HOND,
                       fg=TINTA_2 if bloqueado else TINTA)

        self._previsualizar_q()

    def _previsualizar_q(self):
        try:
            kp   = float(self.var_kp.get())
            ti   = float(self.var_ti.get())
            td   = float(self.var_td.get())
            ts   = float(self.var_ts.get())
            bias = float(self.var_bias.get())
            vfte = float(self.var_vfte.get())
        except ValueError:
            return
        if ti <= 0 or ts <= 0 or vfte <= 0:
            return

        q0 =  kp * (1.0 + ts / (2.0 * ti) + td / ts)
        q1 = -kp * (1.0 - ts / (2.0 * ti) + (2.0 * td) / ts)
        q2 =  kp * (td / ts)

        self.lbl_q.config(
            text=f"q0 {q0:+.6f}   q1 {q1:+.6f}\nq2 {q2:+.6f}")
        self.lbl_bias.config(
            text=f"PWM en reposo  {int(round(bias * 255.0 / vfte))}")

    # --------------------------------------------------------
    #  6. Indicadores
    # --------------------------------------------------------
    def _panel_indicadores(self, padre):
        c = self._tarjeta(padre, "Lecturas")

        self.ind = {}
        campos = [("Voltaje", "V"), ("Error", "V"),
                  ("PWM", ""), ("U(s) sat", "V"), ("Tiempo", "s")]

        for i, (etiqueta, unidad) in enumerate(campos):
            fila = tk.Frame(c, bg=PANEL)
            fila.pack(fill="x", pady=1)
            tk.Label(fila, text=etiqueta, bg=PANEL, fg=TINTA_2,
                     font=F_ETIQUETA, width=10, anchor="w").pack(side="left")
            if unidad:
                tk.Label(fila, text=unidad, bg=PANEL, fg=TINTA_3,
                         font=F_MINI, width=2, anchor="w").pack(side="right")
            v = tk.StringVar(value="—")
            tk.Label(fila, textvariable=v, bg=PANEL, fg=TINTA,
                     font=F_DATO, anchor="e").pack(side="right")
            self.ind[etiqueta] = v

            if i < len(campos) - 1:
                tk.Frame(c, bg=BORDE_FINO, height=1).pack(fill="x")

        self.btn_csv = self._boton(c, "Guardar CSV", NEUTRO, NEUTRO_HL,
                                   self._guardar_csv)
        self.btn_csv.pack(fill="x", ipady=7, pady=(GAP, 0))

    # --------------------------------------------------------
    #  7. Gráficas
    # --------------------------------------------------------
    def _panel_grafica(self, padre):
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE,
                         highlightthickness=1)
        marco.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(8, 7), dpi=100, facecolor=PANEL)
        self.ax1 = self.fig.add_subplot(211, facecolor=LIENZO)
        self.ax2 = self.fig.add_subplot(212, facecolor=LIENZO, sharex=self.ax1)

        for ax in (self.ax1, self.ax2):
            ax.tick_params(colors=TINTA_3, labelsize=8, length=3, width=0.6)
            ax.grid(True, color=REJILLA, linestyle="-", linewidth=0.8)
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color(BORDE_FINO)
            ax.spines["bottom"].set_color(BORDE_FINO)
            ax.spines["left"].set_linewidth(0.8)
            ax.spines["bottom"].set_linewidth(0.8)

        self.ax1.set_ylabel("Salida", color=TINTA_2, fontsize=9)
        self.ax1.set_title("Respuesta del sistema  ·  voltios",
                           color=TINTA_2, fontsize=10, loc="left", pad=10)
        self.linea_v,   = self.ax1.plot([], [], color=TR_MEDIDO, lw=1.7,
                                        label="medido")
        self.linea_ref, = self.ax1.plot([], [], color=TR_CONSIGNA, lw=1.3,
                                        linestyle="--", label="consigna")

        self.ax2.set_ylabel("Error", color=TINTA_2, fontsize=9)
        self.ax2.set_xlabel("Tiempo  ·  s", color=TINTA_2, fontsize=9)
        self.ax2.set_title("Señal de error  e(k)  ·  voltios",
                           color=TINTA_2, fontsize=10, loc="left", pad=10)
        self.linea_e,   = self.ax2.plot([], [], color=TR_ERROR, lw=1.5,
                                        label="e(k)")
        self.ax2.axhline(0, color=TINTA_3, lw=0.9)

        for ax, loc in ((self.ax1, "lower right"), (self.ax2, "upper right")):
            leg = ax.legend(loc=loc, fontsize=8, facecolor=LIENZO,
                            edgecolor=BORDE_FINO, framealpha=1.0)
            leg.get_frame().set_linewidth(0.6)
            for t in leg.get_texts():
                t.set_color(TINTA_2)

        self.ax1.set_ylim(0, 11)
        self.ax2.set_ylim(-2, 2)
        self.fig.tight_layout(pad=2.0)

        self.canvas = FigureCanvasTkAgg(self.fig, master=marco)
        self.canvas.get_tk_widget().pack(fill="both", expand=True,
                                         padx=2, pady=2)

    # --------------------------------------------------------
    #  Serial
    # --------------------------------------------------------
    def _refrescar_puertos(self):
        puertos = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_puerto["values"] = puertos
        if puertos and not self.var_puerto.get():
            self.var_puerto.set(puertos[0])

    def _conectar(self):
        nombre = self.var_puerto.get()
        if not nombre:
            messagebox.showwarning("Puerto", "Selecciona un puerto COM.")
            return
        try:
            self.puerto = serial.Serial(nombre, BAUDIOS, timeout=0.1)
            time.sleep(2.0)          # el Arduino se reinicia al abrir el puerto
            self.puerto.reset_input_buffer()
        except serial.SerialException as e:
            messagebox.showerror("Error de conexión", str(e))
            self.puerto = None
            return

        self.leyendo = True
        self.hilo_lectura = threading.Thread(target=self._hilo_serial, daemon=True)
        self.hilo_lectura.start()

        self.lbl_estado.config(text="●  Conectado", fg=OK)
        self.btn_conectar.config(state="disabled")
        self.btn_desconectar.config(state="normal")
        self.btn_aplicar.config(state="normal")
        self.btn_iniciar.config(state="normal")

    def _desconectar(self):
        if self.control_activo:
            self._detener_control()
        self.leyendo = False
        time.sleep(0.2)
        if self.puerto and self.puerto.is_open:
            self.puerto.close()
        self.puerto = None

        self.lbl_estado.config(text="●  Desconectado", fg=TINTA_3)
        self.btn_conectar.config(state="normal")
        self.btn_desconectar.config(state="disabled")
        self.btn_aplicar.config(state="disabled")
        self.btn_iniciar.config(state="disabled")
        self.btn_detener.config(state="disabled")

    def _hilo_serial(self):
        """Lee lineas del Arduino y las deposita en la cola."""
        while self.leyendo:
            try:
                if self.puerto and self.puerto.in_waiting:
                    linea = self.puerto.readline().decode("utf-8", "ignore").strip()
                    if linea:
                        self.cola.put(linea)
                else:
                    time.sleep(0.002)
            except (serial.SerialException, OSError):
                break

    def _enviar(self, texto):
        if self.puerto and self.puerto.is_open:
            try:
                self.puerto.write((texto + "\n").encode())
            except serial.SerialException as e:
                messagebox.showerror("Error", f"No se pudo enviar: {e}")

    # --------------------------------------------------------
    #  Acciones
    # --------------------------------------------------------
    def _aplicar_parametros(self):
        try:
            kp   = float(self.var_kp.get())
            ti   = float(self.var_ti.get())
            td   = float(self.var_td.get())
            ts   = float(self.var_ts.get())
            bias = float(self.var_bias.get())
            vfte = float(self.var_vfte.get())
        except ValueError:
            messagebox.showerror("Parámetros",
                                 "Todos los valores deben ser numéricos.")
            return

        if ti <= 0:
            messagebox.showerror("Parámetros", "Ti debe ser mayor que cero.")
            return
        if ts <= 0:
            messagebox.showerror("Parámetros", "Ts debe ser mayor que cero.")
            return
        if vfte <= 0:
            messagebox.showerror("Parámetros",
                                 "El voltaje de fuente debe ser mayor que cero.")
            return
        if not (0.0 <= bias <= vfte):
            messagebox.showerror("Parámetros",
                                 "El bias debe estar entre 0 y el voltaje de fuente.")
            return
        if self.control_activo:
            messagebox.showwarning("Parámetros",
                                   "Detén el control antes de cambiar los parámetros.")
            return

        self._previsualizar_q()

        self._enviar(f"B,{bias:.3f},{vfte:.3f}")
        time.sleep(0.05)
        self._enviar(f"P,{kp:.6f},{ti:.6f},{td:.6f},{ts:.4f}")

    def _iniciar_control(self):
        ref = self.var_ref.get()
        self._limpiar_datos()
        self._enviar(f"S,{ref:.3f}")
        self.control_activo = True
        self.btn_iniciar.config(state="disabled")
        self.btn_detener.config(state="normal")
        self.btn_aplicar.config(state="disabled")

    def _detener_control(self):
        self._enviar("X")
        self._resetear_visor()
        self.control_activo = False
        self.btn_iniciar.config(state="normal")
        self.btn_detener.config(state="disabled")
        self.btn_aplicar.config(state="normal")

    def _cambiar_referencia(self, _=None):
        valor = self.var_ref.get()
        self.var_ref_txt.set(f"{valor:.1f}")
        if self.control_activo:
            self._enviar(f"R,{valor:.3f}")

    def _referencia_desde_texto(self, _=None):
        try:
            valor = float(self.var_ref_txt.get())
        except ValueError:
            return
        self.var_ref.set(max(0.0, min(10.0, valor)))
        self._cambiar_referencia()

    def _limpiar_datos(self):
        for b in (self.t_datos, self.v_datos, self.e_datos, self.p_datos,
                  self.ref_datos, self.uf_datos, self.us_datos,
                  self.registro_completo):
            b.clear()

    def _guardar_csv(self):
        if not self.registro_completo:
            messagebox.showinfo("Guardar", "No hay datos capturados todavía.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="respuesta_planta.csv")
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tiempo_s", "consigna_V", "voltaje_V", "error_V",
                        "pwm", "u_f_V", "u_sat_V"])
            w.writerows(self.registro_completo)
        messagebox.showinfo("Guardar",
                            f"Se guardaron {len(self.registro_completo)} muestras.")

    # --------------------------------------------------------
    #  Bucle de actualización
    # --------------------------------------------------------
    def _actualizar(self):
        hubo_datos = False

        while not self.cola.empty():
            linea = self.cola.get()

            if linea.startswith("D,"):
                partes = linea.split(",")
                if len(partes) != 7:
                    continue
                try:
                    t  = float(partes[1])
                    v  = float(partes[2])
                    e  = float(partes[3])
                    p  = float(partes[4])
                    uf = float(partes[5])
                    us = float(partes[6])
                except ValueError:
                    continue

                ref = v + e   # la consigna se reconstruye del error

                self.t_datos.append(t)
                self.v_datos.append(v)
                self.e_datos.append(e)
                self.p_datos.append(p)
                self.ref_datos.append(ref)
                self.uf_datos.append(uf)
                self.us_datos.append(us)
                self.registro_completo.append([t, ref, v, e, p, uf, us])

                self.ind["Voltaje"].set(f"{v:.3f}")
                self.ind["Error"].set(f"{e:+.3f}")
                self.ind["PWM"].set(f"{int(p)}")
                self.ind["Tiempo"].set(f"{t:.2f}")
                self.ind["U(s) sat"].set(
                    "saturado" if abs(uf - us) > 0.01 else f"{us:.3f}")

                self._actualizar_visor(v, ref, p)
                hubo_datos = True

            elif linea == "OK_BIAS":
                pass
            elif linea == "OK_PARAM":
                self.lbl_estado.config(text="●  Parámetros cargados", fg=ACENTO)
            elif linea == "OK_START":
                self.lbl_estado.config(text="●  Controlando", fg=OK)
            elif linea == "OK_STOP":
                self.lbl_estado.config(text="●  Detenido", fg=TINTA_2)

        if hubo_datos:
            self._redibujar()

        self.root.after(REFRESCO_MS, self._actualizar)

    def _redibujar(self):
        if not self.t_datos:
            return

        t_fin = self.t_datos[-1]
        t_ini = max(0.0, t_fin - VENTANA_SEG)

        i = 0
        for i in range(len(self.t_datos) - 1, -1, -1):
            if self.t_datos[i] < t_ini:
                break
        t = self.t_datos[i:]
        v = self.v_datos[i:]
        e = self.e_datos[i:]
        r = self.ref_datos[i:]

        self.linea_v.set_data(t, v)
        self.linea_ref.set_data(t, r)
        self.linea_e.set_data(t, e)

        self.ax1.set_xlim(t_ini, max(t_ini + VENTANA_SEG, t_fin))

        tope = max(max(v, default=1), max(r, default=1)) * 1.25
        self.ax1.set_ylim(0, max(2.0, tope))

        lim_e = max(0.5, max((abs(x) for x in e), default=0.5) * 1.3)
        self.ax2.set_ylim(-lim_e, lim_e)

        self.canvas.draw_idle()

    def _al_cerrar(self):
        try:
            if self.control_activo:
                self._enviar("X")
                time.sleep(0.1)
            self.leyendo = False
            time.sleep(0.15)
            if self.puerto and self.puerto.is_open:
                self.puerto.close()
        except Exception:
            pass
        self.root.destroy()


# ============================================================
if __name__ == "__main__":
    raiz = tk.Tk()

    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    estilo.configure("TCombobox", fieldbackground=CAMPO, background=PANEL,
                     foreground=TINTA, arrowcolor=TINTA_2,
                     bordercolor=BORDE_FINO, lightcolor=CAMPO, darkcolor=CAMPO)
    estilo.configure("Vertical.TScrollbar", background=PANEL_HOND,
                     troughcolor=CHASIS, bordercolor=CHASIS,
                     arrowcolor=TINTA_2, relief="flat")

    app = HMIMotorGenerador(raiz)
    raiz.mainloop()