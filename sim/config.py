"""Cosmos Royale - Hito 0: parametros de la simulacion.

Todos los numeros de balance viven aqui y SOLO aqui. Son hipotesis de partida
(ver Docs/hito0-decisiones.md); la simulacion sirve para corregirlas.

Unidades: u = unidad de arena, s = segundo, masa en unidades de masa (m).
"""

# --- Simulacion ---------------------------------------------------------------
DT = 0.1                 # paso de simulacion (s)
DT_VALIDATION = 0.04     # paso fino para validar que los resultados no cambian
N_RUNS = 500             # partidas por configuracion
VALIDATION_RUNS = 50     # partidas para la validacion con DT_VALIDATION
SEED_BASE = 12345        # semilla base; la partida i usa SEED_BASE + i

# --- Sala ---------------------------------------------------------------------
N_PLAYERS = 20                 # 1 sujeto competente + 19 rivales
MATCH_HARD_LIMIT_S = 240       # referencia del colapso: P llega a 1 aqui (s)
START_MASS = 1.0               # masa inicial de cada jugador
MIN_MASS_ALIVE = 0.5           # por debajo de esta masa el cuerpo muere
SPAWN_RING_RADIUS = 55.0       # anillo de aparicion (20 puntos equiespaciados)
SPAWN_INVULN_S = 8.0           # inmunidad al stripping tras aparecer (s)

# Rivales del sujeto. Se dan por numero de cada tipo y el resto son medios, de
# forma que la proporcion se puede barrer con --sweep (un diccionario no se
# puede). Sala sin novatos: NOVICE_RIVALS = 0.
NOVICE_RIVALS = 0              # novatos entre los 19 rivales
COMPETENT_RIVALS = 3           # competentes entre los 19 rivales
# Los medios son N_PLAYERS - 1 - NOVICE_RIVALS - COMPETENT_RIVALS.

# --- Niveles ------------------------------------------------------------------
# Masa minima de cada nivel: I, II, III, IV, V
LEVEL_MIN_MASS = (1.0, 8.0, 25.0, 80.0, 250.0)

RADIUS_COEF = 1.0        # radio = RADIUS_COEF * m ** RADIUS_EXP
RADIUS_EXP = 0.35
# Velocidad punta: ya NO depende de la masa (VMAX_EXP = 0). Lo que se pierde al
# crecer es maniobrabilidad, no velocidad: la aceleracion cae con la masa, asi
# que el grande tarda mucho mas en girar y en arrancar. Antes, con VMAX_EXP =
# -0,2, el grande era siempre mas lento que su presa y cazar era imposible.
VMAX_COEF = 16.0         # velocidad punta = VMAX_COEF * m ** VMAX_EXP (u/s)
VMAX_EXP = 0.0
ACCEL_COEF = 34.0        # aceleracion = ACCEL_COEF * m ** ACCEL_EXP (u/s^2)
ACCEL_EXP = -0.35        # antes -0,1: ahora crecer cuesta maniobrabilidad

# El empuje propio se desvanece al acercarse a la velocidad punta, en lugar de
# cortarse de golpe, y solo en la direccion en la que ya te mueves: girar y
# frenar siempre funcionan al 100 %. La velocidad que regala el terreno (honda
# gravitatoria, onda de cuasar, borde del pulsar) NO se recorta, que es lo que
# permite ir mas rapido de lo normal aprovechando el mapa. El techo de abajo es
# solo una red de seguridad numerica.
SPEED_CEILING_MULT = 4.0
# Con que agresividad se desvanece el empuje al acercarse a la velocidad punta.
# 1 = lineal (la segunda mitad de la velocidad cuesta una eternidad y el control
# se siente pastoso). 3 = casi todo el empuje disponible hasta el 80 % de la
# punta, y solo el ultimo tramo cuesta: el control responde de golpe.
THRUST_FADE_POWER = 3.0
COLLECT_STEP = 0.35      # recoleccion = radio * (1 + COLLECT_STEP * (nivel - 1))

# --- Turbo (desde el nivel III) -----------------------------------------------
TURBO_MIN_LEVEL = 3
TURBO_ACCEL_BONUS = 0.65     # +65 % de aceleracion
TURBO_MASS_BURN_PER_S = 0.03 # fraccion de la masa que se suelta como polvo por s

# --- Tidal stripping ----------------------------------------------------------
STRIP_MIN_RATIO = 1.15       # mA >= STRIP_MIN_RATIO * mB para que haya transferencia
STRIP_K = 6.5                # f = STRIP_K * delta ** STRIP_ALPHA (fraccion/s)
# MEDIDO: subir STRIP_K de 1,5 a 6,5 es LA palanca del combate. Con 1,5 solo el
# 29 % de las eliminaciones eran peleando (el resto se las llevaba el mapa); con
# 6,5 son el 73 %. El ratio minimo de 1,15 apenas influye en esto (27 % contra
# 29 %): lo que cambia las cosas es que, una vez pegados, la pelea se resuelva.
STRIP_ALPHA = 1.5            # delta = (mA - mB) / mA
STRIP_TO_ATTACKER = 0.75     # parte de lo arrancado que gana el atacante (rocas)
STRIP_TO_DUST = 0.25         # parte que se suelta como polvo en el contacto

# Devorar a un JUGADOR da mas masa de la que tenia: un rival de masa 10 te deja
# 15. Esto CREA masa a proposito, para que eliminar rente mas que pastar. El
# libro de masas lo lleva en una cuenta aparte (world.mass_created) para seguir
# cuadrando. Las rocas y el polvo no llevan bonus: usan STRIP_TO_ATTACKER.
PLAYER_KILL_MASS_MULT = 1.5

# --- Masa libre ---------------------------------------------------------------
DUST_MASS = 0.3
DUST_COUNT = 200             # 60 de masa en total
# MEDIDO EN EL HITO 0, tercera vuelta. Historia de este numero: tu doc decia 560;
# con novatos en la sala 500 daba el nivel III a los 104 s; al quitar los novatos
# hubo que subir a 800 porque su masa era la que alimentaba la partida; y con el
# bonus de devorar (x1,5) la masa ya viene de las eliminaciones, asi que baja a
# 200. Masa libre inicial: 60 de polvo + 72 de rocas = 132, mas las oleadas.
ROCK_MASS = 2.0
ROCK_COUNT = 36              # 72 de masa en total (cuerpos estaticos)
ROCK_MIN_EAT_MASS = 2.3      # masa minima para empezar a absorber rocas
BELTS = ((35.0, 45.0), (65.0, 75.0))   # (r_min, r_max) de los dos cinturones
BELT_FRACTION = 0.60         # fraccion de la masa libre inicial en cinturones
REPLENISH_RATE = 0.8         # masa de polvo repuesta por segundo en cinturones
REPLENISH_END_P = 0.5        # la reposicion baja linealmente hasta 0 en este P

# --- Oleadas de comida --------------------------------------------------------
# Inyeccion periodica de polvo, ademas del goteo de arriba. Nace del Hito 0: la
# masa libre se agotaba hacia el minuto 3 y la segunda mitad de la partida se
# quedaba sin nada que hacer. Con 0 se apagan y vuelve el comportamiento viejo.
FOOD_WAVE_INTERVAL_S = 45.0  # cada cuanto cae una oleada (s)
FOOD_WAVE_MASS = 40.0        # masa de polvo por oleada (medido en el Hito 0)
FOOD_WAVE_FIRST_S = 30.0     # instante de la primera oleada (s)
FOOD_WAVE_IN_BELTS = 0.6     # fraccion en cinturones (solo si NEAR_HOLE esta apagado)

# La oleada cae pegada al agujero: el pequeno maniobra bien ahi y el grande, que
# acelera menos, lo tiene crudo para entrar y salir. Es comida de riesgo.
FOOD_WAVE_NEAR_HOLE = True
FOOD_WAVE_INNER_MULT = 1.25  # desde el horizonte * esto
FOOD_WAVE_OUTER_MULT = 3.5   # hasta el horizonte * esto

# --- Colapso ------------------------------------------------------------------
# P = max(P_TIME_WEIGHT * t / MATCH_HARD_LIMIT_S + P_DEATH_WEIGHT * muertos / (N_PLAYERS - 1),
#         clamp((t - P_HARD_START_S) / P_HARD_SPAN_S, 0, 1))
P_TIME_WEIGHT = 0.6
P_DEATH_WEIGHT = 0.4
P_HARD_START_S = 95.0
P_HARD_SPAN_S = 145.0

PHASE_BOUNDS = (0.25, 0.55, 0.85, 1.0)   # fin de cada fase en P
NO_DUST_FROM_P = 0.85                    # fase 4: sin polvo

# --- Estrella masiva en orbita ------------------------------------------------
# Un segundo pozo gravitatorio, pero movil y predecible: da la mejor honda del
# mapa y quema masa al contacto. Va sobre rieles (orbita prescrita, no
# simulada) para que el jugador pueda aprenderse su ciclo, igual que los
# cuasares. Espiralea hacia dentro con el colapso hasta que el agujero se la
# traga, lo que la convierte en una barredora que empuja a todos al centro.
STAR_ENABLED = True
STAR_ORBIT_R0 = 78.0         # radio de su orbita al empezar (fuera del anillo)
STAR_ORBIT_R1 = 14.0         # radio al final del colapso (P = 1)
STAR_PERIOD_S = 60.0         # una vuelta completa (s)
# La honda de la estrella vale como maximo el doble de su velocidad orbital
# (2*pi*r/T). Con 88 s eran ~11 u/s de regalo; con 60 s son ~17, por encima de
# la velocidad punta. Es la asistencia gravitatoria que de verdad se nota.
STAR_RADIUS = 6.5            # radio fisico
STAR_GM = 950.0              # su propia gravedad (el agujero empieza en 540)
# MEDIDO: con 680 y la aceleracion subida a 34, un cuerpo de masa 120 ya salia
# de su superficie y la estrella dejaba de ser una trampa para los grandes. Con
# 950 vuelve a atrapar a partir de ~masa 100. Lo pillo un test, no el barrido.
STAR_EPS = 6.0               # suavizado de Plummer de su pozo
STAR_CONTACT_DRAIN = 1.1     # fraccion de masa por segundo tocandola

# --- Final por gravedad -------------------------------------------------------
# No hay corte a los 5:00. A partir del minuto 4 la gravedad del agujero se
# multiplica hasta que, hacia el 5:00, se lo lleva todo. La partida acaba cuando
# queda uno (y entonces sí salta el Apex) o cuando el agujero se los traga.
ENDGAME_START_S = 190.0      # cuando empieza a crecer la gravedad
ENDGAME_FULL_S = 240.0       # cuando llega al maximo
ENDGAME_GRAVITY_MULT = 12.0  # multiplicador de GM al final
MATCH_SAFETY_LIMIT_S = 360.0 # red de seguridad de la simulacion, no regla de juego

ARENA_R0 = 130.0             # R(P) = ARENA_R0 - ARENA_R_SHRINK * P
ARENA_R_SHRINK = 105.0       # el final sigue siendo 25, como el horizonte
# MEDIDO: con la arena de 100 u y el combate rapido, morian 12 antes del minuto
# 2 y el nivel III caia a los 69 s. Con 130 u los encuentros tardan mas en
# llegar: 9 muertes y nivel III a los 104 s, dentro de tus dos bandas.
HORIZON_H0 = 3.0             # h(P) = HORIZON_H0 + HORIZON_H_GROWTH * P
HORIZON_H_GROWTH = 22.0

# Gravedad central: g(r) = GM(P) * r / (r**2 + PLUMMER_EPS**2) ** 1.5
GRAVITY_GM0 = 800.0          # GM(P) = GRAVITY_GM0 * (1 + GRAVITY_GROWTH * P)
# MEDIDO: subir el pozo central de 540 a 800 cuesta unos 5 puntos de combate
# (85 % -> 80 %), porque los bots se vuelven mas cautos y pelean menos, no
# porque la gravedad sea mala. Sigue muy por encima del objetivo del 70 %. Con
# 1100 el combate baja al 77 % y empieza a no merecer la pena.
GRAVITY_GROWTH = 4.0
PLUMMER_EPS = 4.0

# --- Borde elastico (antes zona de radiacion) ---------------------------------
# Ya no hay zona de radiacion: cruzar el borde no drena masa ni frena. Lo que
# hay es un tiron gravitatorio hacia dentro proporcional a la velocidad con la
# que intentaste salir, que se registra en el momento de cruzar. Embestir el
# borde a tope te devuelve disparado; asomarse despacio apenas se nota. Asi el
# borde deja de ser un castigo y pasa a ser una herramienta de movimiento.
EDGE_PULL_BASE = 5.0         # tiron minimo al estar fuera (u/s^2)
EDGE_PULL_SPEED = 2.4        # multiplica la velocidad de salida registrada
EDGE_PULL_DEPTH = 1.1        # tiron extra por unidad de profundidad fuera
EDGE_PULL_MAX = 150.0        # techo del tiron (u/s^2)

# --- Ventajas del grande ------------------------------------------------------
ROCHE = 0.0                  # limite de Roche desactivado en el Hito 0
# Las otras ventajas salen de COLLECT_STEP, STRIP_MIN_RATIO, TURBO_* y del
# desempate final por masa si en P = 1 siguen vivos varios.

# --- Entorno abstracto (escape asistido) --------------------------------------
ASSIST_P0 = 0.30             # p_asist = ASSIST_P0 * (1 - P)
ASSIST_VICTIM_MAX_RATIO = 0.5    # solo si masa victima <= 0.5 * masa atacante
ASSIST_IMPULSE_MULT = 1.5    # impulso = 1.5 * velocidad maxima de la victima
ASSIST_DURATION_S = 1.0
ASSIST_COOLDOWN_S = 8.0      # por cuerpo

# --- Entorno real: cuasares y pulsares ----------------------------------------
# Sustituyen (o complementan) al parametro abstracto de arriba. Un elemento deja
# de funcionar cuando el colapso lo deja fuera de la arena o dentro del
# horizonte, asi que se agotan solos con las fases sin regla extra.

# Cuasares: onda de choque ciclica y predecible. El impulso es inversamente
# proporcional a la masa, asi que al pequeno lo dispara y al grande casi no lo
# mueve. Contrajuego del grande: esperar al pequeno en la salida.
QUASAR_COUNT = 3             # subido de 2
QUASAR_RING_R = 45.0         # radio del anillo donde se colocan
QUASAR_PERIOD_S = 9.0        # cada cuanto emite (antes 12)
QUASAR_RADIUS = 30.0         # alcance de la onda (antes 22)
QUASAR_IMPULSE = 34.0        # velocidad anadida = QUASAR_IMPULSE / masa (antes 20)

# Pulsares: haz giratorio. Drena masa en proporcion a la masa (castiga mas al
# grande) y el borde del haz da velocidad al que lo cronometra bien.
PULSAR_COUNT = 2             # subido de 1
PULSAR_RING_R = 30.0
PULSAR_PERIOD_S = 7.0        # vuelta completa del haz (antes 8)
PULSAR_RANGE = 38.0          # largo del haz (medido: con 60 los haces se
                             # comian el 57 % de la masa del sistema)
PULSAR_HALF_ANGLE = 0.20     # semiancho del haz (radianes)
PULSAR_EDGE_BAND = 1.7       # el borde va de HALF_ANGLE a HALF_ANGLE * esto
PULSAR_DRAIN_COEF = 0.09     # fraccion/s = COEF * masa ** EXP (antes 0,06)
PULSAR_DRAIN_EXP = 0.35
PULSAR_SURF_SPEED = 9.0      # velocidad que regala el borde del haz (u/s)

# Las ayudas del entorno (impulso del cuasar, surf del pulsar) se desvanecen
# entre estos dos valores de P; los danos no.
ENV_FADE_FROM_P = 0.55
ENV_FADE_END_P = 0.85

# --- Bots ---------------------------------------------------------------------
MEDIUM_FLEE_RADIUS = 20.0    # el "medio" huye de cuerpos mayores dentro de este radio
PULSAR_FEAR_MARGIN = 1.25    # medio y competente salen del haz con este margen
MEDIUM_HUNT_RADIUS = 22.0    # el medio tambien caza desde que eliminar rinde mas
STAR_FEAR_MARGIN = 1.8       # a cuanto de la estrella empiezan a apartarse
# Frenado: un bot decente no se deja caer al pozo. Compara su distancia al
# horizonte con la distancia que necesita para parar a la velocidad que lleva.
BRAKE_SAFETY = 7.0           # frena si le queda menos de esto por distancia de parada
BRAKE_TANGENTIAL = 1.0       # cuanto del frenado va de lado (recuperar orbita)
COMP_SURF_PULSAR = True      # el competente busca el borde del haz cuando huye
# El "competente" caza a cuerpos con mA >= STRIP_MIN_RATIO * mB.

# --- Criterios de exito (por configuracion, sobre N_RUNS partidas) ------------
TARGET_DEATHS_BEFORE_120S = (8, 10)
TARGET_MEDIAN_LEVEL3_S = (100.0, 130.0)     # mediana del tiempo en llegar a masa 25
MAX_LEVEL3_FRACTION_AT_120S = 0.25          # de los supervivientes a t = 120 s
TARGET_COMPETENT_WIN_RATE = (0.20, 0.50)
MAX_NOVICE_WIN_RATE = 0.02
# Con la sala sin novatos, "el novato gana menos del 2 %" ya no mide nada. Lo
# que sigue midiendo si la habilidad importa es comparar victorias por cuerpo:
# un competente debe ganar al menos esta proporcion de veces mas que un medio.
MIN_SKILL_EDGE = 1.5
# Con el final por gravedad la partida puede pasarse un poco de los 5:00, que es
# cuando el agujero acaba de tragarse todo. Banda ampliada a 5:30 por eso.
TARGET_MATCH_END_S = (150.0, 270.0)
# El objetivo del diseno: la mayoria de las eliminaciones vienen de pelear, no
# de que el mapa te mate.
TARGET_COMBAT_FRACTION = 0.70
# A t = 120 s: masa media ~15, mediana ~11 y los mejores entre 25 y 40.
TARGET_MASS_AT_120S = {"mean": 15.0, "median": 11.0, "top": (25.0, 40.0)}

# ==============================================================================
# AÑADIDO POR LA SIMULACION - PENDIENTE DE TU OK
# Las decisiones del Hito 0 no fijan estos valores y el codigo no puede correr
# sin ellos. Estan aqui separados para que los revises; cambiarlos no toca codigo.
# ==============================================================================

# Velocidad en el anillo de aparicion. "orbital" = velocidad de orbita circular
# tangencial (todos en el mismo sentido), que es coherente con "los cuerpos
# orbitan" del GDD. Alternativas: "zero" (quietos) o "random".
SPAWN_VELOCITY_MODE = "orbital"
SPAWN_VELOCITY_FACTOR = 1.0    # multiplica la velocidad orbital circular

# Rebote suave cuando ninguno de los dos alcanza STRIP_MIN_RATIO sobre el otro:
# se invierte la componente normal de la velocidad relativa con esta restitucion,
# conservando el momento. 0 = se quedan pegados, 1 = rebote elastico.
BOUNCE_RESTITUTION = 0.5

# Percepcion y decision de los bots.
BOT_DECISION_INTERVAL_S = 0.08 # cada cuanto re-decide un bot (igual para todo DT)
# MEDIDO: con el juego mas rapido, 0,2 s dejaba a los bots reaccionando tarde y
# la ventaja del competente caia a x1,3. Con 0,08 vuelve a x1,9.
BOT_NOISE_RAD = 0.12           # ruido angular por decision (radianes, +/-)
BOT_PERCEPTION_RADIUS = 45.0   # hasta donde ve comida y rivales

# Bot competente.
COMP_FLEE_BASE_MARGIN = 14.0   # margen base de huida (u)
COMP_FLEE_SPEED_MARGIN = 1.6   # + este factor por la vmax del depredador (u por u/s)
COMP_HUNT_RADIUS = 50.0        # hasta donde persigue presas (subido por el bonus)
COMP_WELL_MARGIN = 2.2         # margen fijo del pozo (solo si el check fisico esta off)
# El competente decide si entra al pozo calculando si puede salir: compara la
# gravedad del sitio con su propia aceleracion. Asi el pequeno agil baja a por
# la comida pegada al agujero y el grande no puede, que es el objetivo de poner
# la comida ahi. Con el margen fijo de arriba, ningun bot bajaba nunca y la
# comida de riesgo simplemente desaparecia del juego.
COMP_PHYSICAL_WELL_CHECK = True
COMP_GRAVITY_TOLERANCE = 0.45  # entra si la gravedad del sitio < esto * su aceleracion
COMP_EDGE_MARGIN = 0.88        # evita el borde por encima de R(P) * este factor
COMP_TURBO_WHEN_FLEEING = True # usa turbo al huir y al salir del pozo

# Novato y medio: evitar el agujero central. Tus decisiones dicen que el novato
# "no evita a nadie", pero eso habla de rivales, no del pozo. Con 0.0 (tu
# especificacion literal) el novato se deja caer dentro persiguiendo polvo y el
# agujero se come dos tercios de la sala. Es el parametro del barrido.
BASIC_WELL_MARGIN = 1.5        # si > 0, se alejan por debajo de h(P) * este factor
# MEDIDO EN EL HITO 0: con 0.0 el agujero se comia 12,4 cuerpos por partida
# (65 % de las muertes) y morian 14 antes del minuto 2. Con 1.5, 9-10.

# Lo mismo con el borde de la arena: con 0.0 el novato y el medio se quedan en
# la zona de radiacion sin enterarse. Es la otra mitad de la pregunta: cuanto
# del mapa entiende un jugador basico.
BASIC_EDGE_MARGIN = 0.88       # si > 0, vuelven dentro por encima de R(P) * este factor
# MEDIDO EN EL HITO 0: con 0.0 los competentes ganaban el 74 % de las partidas
# solo por ser los unicos que no se quedaban en la radiacion. Con 0.88, 43-47 %.

# Muestreo de metricas.
SAMPLE_INTERVAL_S = 1.0        # cada cuanto se guarda una fila de timeline
TIMELINE_SAMPLE_MATCHES = 5    # partidas con timeline detallado en CSV
LEDGER_TOLERANCE = 1e-6        # error maximo admitido en el libro de masas
