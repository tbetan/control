%% =========================================================================
% CÁLCULO DE DIFERENCIAS Y % DE ERROR ENTRE LOS MODELOS IDENTIFICADOS
% (SMITH, CHIEN y SISTEMID) Y LOS DATOS EXPERIMENTALES (DATA)
%
% Todo sale directamente del modelo Simulink, desde la estructura "out"
% que arman tus bloques "To Workspace" (out.SMITH, out.CHIEN,
% out.SISTEMID, out.DATA). Genera la "Tabla de Método" (Tiempo_s,
% Voltaje_V, DIFERENCIA por cada método) y el bloque "Resultados
% Obtenidos" (PROMEDIO ERROR), y exporta todo a Excel.
% =========================================================================
clc; close all;

%% -------------------------------------------------------------------------
% 0. CONFIGURACIÓN — AJUSTA ESTO SI TUS NOMBRES SON DISTINTOS
% -------------------------------------------------------------------------
modelo          = 'IDENTIFICACION_PLANTA_CONTROL';  % <-- nombre de tu archivo .slx
var_datos_ident = 'VALIDACION';  % <-- variable YA EXISTENTE en tu Workspace
archivo_salida  = 'Tabla_Metodo_Resultados.xlsx';

%% -------------------------------------------------------------------------
% 1. CORRER LA SIMULACIÓN
% -------------------------------------------------------------------------
% IMPORTANTE: no se asigna el resultado de sim() a la variable "out",
% porque ese nombre ya lo usan tus bloques "To Workspace"
% (out.SMITH, out.CHIEN, out.SISTEMID). Si se hiciera
% "out = sim(modelo)" se sobreescribiría esa estructura.
sim(modelo);
out = evalin('base', 'out');   % recupera la estructura que armaron los bloques

%% -------------------------------------------------------------------------
% 2. EXTRACCIÓN DE TIEMPO Y VALOR DE CADA SEÑAL
% -------------------------------------------------------------------------
% Funciona sin importar si el "Save format" del To Workspace fue
% Timeseries o Structure With Time (ver función extraerSenal al final).
[t_smith, v_smith] = extraerSenal(out.SMITH);
[t_chien, v_chien] = extraerSenal(out.CHIEN);
[t_sid,   v_sid]    = extraerSenal(out.SISTEMID);

% Datos experimentales: variable de 2 columnas [tiempo, voltaje] YA
% presente en tu Workspace (no viene de la simulación ni de "out").
datos_ident = evalin('base', var_datos_ident);
t_exp = datos_ident(:,1);
v_exp = datos_ident(:,2);

%% -------------------------------------------------------------------------
% 3. INTERPOLACIÓN DE LAS SALIDAS SIMULADAS EN LOS TIEMPOS DE "DATA"
% -------------------------------------------------------------------------
v_sid_i   = interp1(t_sid,   v_sid,   t_exp, 'linear', 'extrap');
v_smith_i = interp1(t_smith, v_smith, t_exp, 'linear', 'extrap');
v_chien_i = interp1(t_chien, v_chien, t_exp, 'linear', 'extrap');

%% -------------------------------------------------------------------------
% 4. DIFERENCIA Y % DE ERROR RESPECTO A LOS DATOS EXPERIMENTALES
% -------------------------------------------------------------------------
Dif_sid   = abs(v_exp - v_sid_i);
Dif_smith = abs(v_exp - v_smith_i);
Dif_chien = abs(v_exp - v_chien_i);

Err_sid   = zeros(size(v_exp));
Err_smith = zeros(size(v_exp));
Err_chien = zeros(size(v_exp));

idx = v_exp ~= 0;   % evita división por cero en t=0, igual que en tu tabla
Err_sid(idx)   = (Dif_sid(idx)   ./ v_exp(idx)) * 100;
Err_smith(idx) = (Dif_smith(idx) ./ v_exp(idx)) * 100;
Err_chien(idx) = (Dif_chien(idx) ./ v_exp(idx)) * 100;

Promedio_Error_SID   = mean(Err_sid(idx));
Promedio_Error_Smith = mean(Err_smith(idx));
Promedio_Error_Chien = mean(Err_chien(idx));

fprintf('PROMEDIO ERROR SISTEM ID : %.6f %%\n', Promedio_Error_SID);
fprintf('PROMEDIO ERROR SMITH     : %.6f %%\n', Promedio_Error_Smith);
fprintf('PROMEDIO ERROR CHIEN     : %.6f %%\n', Promedio_Error_Chien);

%% -------------------------------------------------------------------------
% 5. EXPORTACIÓN A EXCEL CON EL MISMO FORMATO DE LA "TABLA DE MÉTODO"
% -------------------------------------------------------------------------
encabezado1 = {'SISTEM ID','','','DIFERENCIA','','','SMITH','','','DIFERENCIA','','','CHIEN','','','DIFERENCIA'};
encabezado2 = {'Tiempo_s','Voltaje_V','','V','Error_%','','Tiempo_s','Voltaje_V','','V','Error_%','','Tiempo_s','Voltaje_V','','V','Error_%'};

writecell(encabezado1, archivo_salida, 'Sheet', 1, 'Range', 'A1');
writecell(encabezado2, archivo_salida, 'Sheet', 1, 'Range', 'A2');

% NaN en las columnas separadoras se exporta como celda vacía automáticamente
datos = [t_exp, v_sid_i,   nan(size(t_exp)), Dif_sid,   Err_sid,   nan(size(t_exp)), ...
         t_exp, v_smith_i, nan(size(t_exp)), Dif_smith, Err_smith, nan(size(t_exp)), ...
         t_exp, v_chien_i, nan(size(t_exp)), Dif_chien, Err_chien];
writematrix(datos, archivo_salida, 'Sheet', 1, 'Range', 'A3');

% Bloque "Resultados Obtenidos" (promedios de error), debajo de la tabla
fila_resultados = size(datos,1) + 5;
writecell({'Resultados Obtenidos'}, archivo_salida, 'Sheet', 1, ...
    'Range', sprintf('A%d', fila_resultados));
writecell({'PROMEDIO ERROR SISTEM ID'; 'PROMEDIO ERROR SMITH'; 'PROMEDIO ERROR CHIEN'}, ...
    archivo_salida, 'Sheet', 1, 'Range', sprintf('A%d', fila_resultados + 1));
writematrix([Promedio_Error_SID; Promedio_Error_Smith; Promedio_Error_Chien], ...
    archivo_salida, 'Sheet', 1, 'Range', sprintf('B%d', fila_resultados + 1));

disp(['Archivo exportado: ', archivo_salida]);

%% =========================================================================
% FUNCIÓN LOCAL: extrae [tiempo, valor] sin importar el Save format
% usado en el bloque "To Workspace" (Timeseries o Structure With Time)
% =========================================================================
function [t, v] = extraerSenal(s)
    if isa(s, 'timeseries')
        % Save format: Timeseries
        t = s.Time;
        v = s.Data;
    elseif isstruct(s) && isfield(s, 'time') && isfield(s, 'signals')
        % Save format: Structure With Time
        t = s.time;
        v = s.signals.values;
    elseif isstruct(s) && isfield(s, 'time') && isfield(s, 'signalName')
        % Save format: Structure (sin "With Time" pero con campo time)
        t = s.time;
        v = s.values;
    else
        error(['Formato de señal no reconocido. Revisa el parámetro ' ...
               '"Save format" del bloque To Workspace (usa Timeseries ' ...
               'o Structure With Time).']);
    end
    t = t(:);
    v = v(:);
end