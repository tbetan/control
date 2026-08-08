%% ==========================================================
% PREPARAR DATOS PARA SYSTEM IDENTIFICATION
%
% MATRIZ:
%   VALIDACION(:,1) = Tiempo (s)
%   VALIDACION(:,2) = Voltaje (V)
%
% ESCALÓN APLICADO = 3 V
%
% MATLAB R2026a
%% ==========================================================

clc

%% ===========================
% EXTRAER DATOS
%% ===========================

t = DTA(:,1);
y = DTA(:,2);

%% ===========================
% ENTRADA (ESCALÓN)
%% ===========================

u = 3*ones(length(y),1);

%% ===========================
% TIEMPO DE MUESTREO
%% ===========================

Ts = mean(diff(t));

fprintf('\n=========================================\n');
fprintf('Tiempo de muestreo : %.6f s\n',Ts);
fprintf('Número de muestras : %d\n',length(y));
fprintf('=========================================\n\n');

%% ===========================
% CREAR OBJETO IDDATA
%% ===========================

dat = iddata(y,u,Ts);

disp('Objeto creado correctamente:')
disp(dat)

%% ===========================
% ABRIR SYSTEM IDENTIFICATION
%% ===========================

systemIdentification