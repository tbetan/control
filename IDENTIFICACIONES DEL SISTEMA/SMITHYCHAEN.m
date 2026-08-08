%% =========================================================================
% IDENTIFICACIÓN DE MODELO POMTM (Primer Orden Más Tiempo Muerto)
% MÉTODOS: SMITH  y  CHAEN Y YAN
%
% Calcula K, tau (constante de tiempo) y theta (tiempo muerto) de cada
% método directamente a partir de la respuesta al escalón guardada en la
% variable DATA (columna 1: tiempo, columna 2: voltaje/salida), sin
% pasar por Excel. Al final arma las funciones de transferencia y
% muestra los valores listos para poner en los bloques de Simulink
% ("Transfer Fcn" + "Transport Delay").
% =========================================================================
clc;

%% -------------------------------------------------------------------------
% 0. CONFIGURACIÓN
% -------------------------------------------------------------------------
var_datos = 'DTA';   % <-- variable en el Workspace con [tiempo, voltaje]
delta_u   = 3;         % <-- magnitud del escalón de ENTRADA (Xf - Xi).
                        %     AJUSTA este valor si tu escalón no fue de 3.
n_prom    = 20;         % nro. de muestras finales que se promedian para Yf

datos = evalin('base', var_datos);
t = datos(:,1);
y = datos(:,2);

%% -------------------------------------------------------------------------
% 1. GANANCIA Y VALORES INICIAL / FINAL
% -------------------------------------------------------------------------
Yi = y(1);
Yf = mean(y(end-n_prom+1:end));
Delta_y = Yf - Yi;
K = Delta_y / delta_u;

fprintf('=========== GANANCIA ===========\n');
fprintf('Yi      = %.6f\n', Yi);
fprintf('Yf      = %.6f\n', Yf);
fprintf('Delta_y = %.6f\n', Delta_y);
fprintf('Delta_u = %.6f\n', delta_u);
fprintf('K       = %.6f\n\n', K);

%% -------------------------------------------------------------------------
% 2. MÉTODO DE SMITH (28.3%% y 63.2%%)
% -------------------------------------------------------------------------
t1_smith = buscar_cruce(t, y, Yi + 0.283*Delta_y);
t2_smith = buscar_cruce(t, y, Yi + 0.632*Delta_y);

tau_smith   = 1.5*(t2_smith - t1_smith);
theta_smith = 1.5*t1_smith - 0.5*t2_smith;

G_smith = tf(K, [tau_smith 1], 'InputDelay', theta_smith);

fprintf('=========== MÉTODO DE SMITH ===========\n');
fprintf('t1 (28.3%%) = %.6f s\n', t1_smith);
fprintf('t2 (63.2%%) = %.6f s\n', t2_smith);
fprintf('tau         = %.6f s\n', tau_smith);
fprintf('theta       = %.6f s\n', theta_smith);
disp(G_smith)

%% -------------------------------------------------------------------------
% 3. MÉTODO DE CHAEN Y YAN (33%% y 67%%)
% -------------------------------------------------------------------------
t1_chaen = buscar_cruce(t, y, Yi + 0.33*Delta_y);
t2_chaen = buscar_cruce(t, y, Yi + 0.67*Delta_y);

tau_chaen   = 1.4*(t2_chaen - t1_chaen);
theta_chaen = 1.54*t1_chaen - 0.54*t2_chaen;

G_chaen = tf(K, [tau_chaen 1], 'InputDelay', theta_chaen);

fprintf('\n=========== MÉTODO DE CHAEN Y YAN ===========\n');
fprintf('t1 (33%%) = %.6f s\n', t1_chaen);
fprintf('t2 (67%%) = %.6f s\n', t2_chaen);
fprintf('tau      = %.6f s\n', tau_chaen);
fprintf('theta    = %.6f s\n', theta_chaen);
disp(G_chaen)

%% -------------------------------------------------------------------------
% 4. RESUMEN PARA PONER DIRECTO EN TUS BLOQUES DE SIMULINK
% -------------------------------------------------------------------------
fprintf('\n=========== PARA TUS BLOQUES EN SIMULINK ===========\n');
fprintf('METODO SMITH:\n');
fprintf('  Transfer Fcn   -> Numerador = %.6f | Denominador = [%.6f 1]\n', K, tau_smith);
fprintf('  Transport Delay-> Time delay = %.6f\n\n', theta_smith);

fprintf('METODO CHIEN (CHAEN Y YAN):\n');
fprintf('  Transfer Fcn   -> Numerador = %.6f | Denominador = [%.6f 1]\n', K, tau_chaen);
fprintf('  Transport Delay-> Time delay = %.6f\n', theta_chaen);

%% -------------------------------------------------------------------------
% 5. GRÁFICA DE VERIFICACIÓN
% -------------------------------------------------------------------------
figure('Color','w')
plot(t, y, 'k', 'LineWidth', 1.5); hold on
step_smith_t = 0:0.001:max(t);
step_chaen_t = step_smith_t;
[y_smith_step,~] = step(G_smith*delta_u, step_smith_t);
[y_chaen_step,~] = step(G_chaen*delta_u, step_chaen_t);
plot(step_smith_t, Yi + y_smith_step, 'b--', 'LineWidth', 1.3)
plot(step_chaen_t, Yi + y_chaen_step, 'r--', 'LineWidth', 1.3)
grid on
xlabel('Tiempo (s)'); ylabel('Voltaje (V)')
legend('DATA (experimental)','Modelo Smith','Modelo Chaen y Yan','Location','best')
title('Identificación POMTM: Smith vs Chaen y Yan')

%% =========================================================================
% FUNCIÓN LOCAL: encuentra el instante en que la señal y(t) cruza un
% valor objetivo, interpolando linealmente entre las dos muestras más
% cercanas (más robusto que interp1(y,t,...) porque no requiere que y
% sea estrictamente monótona en todo el vector, solo cerca del cruce).
% =========================================================================
function t_cruce = buscar_cruce(t, y, objetivo)
    idx = find(y >= objetivo, 1, 'first');
    if isempty(idx) || idx == 1
        error(['No se encontró el cruce con el valor objetivo %.5f. ' ...
               'Revisa que DATA cubra toda la respuesta hasta el estado ' ...
               'estacionario.'], objetivo);
    end
    t0 = t(idx-1); y0 = y(idx-1);
    t1v = t(idx);  y1v = y(idx);
    t_cruce = t0 + (objetivo - y0) * (t1v - t0) / (y1v - y0);
end