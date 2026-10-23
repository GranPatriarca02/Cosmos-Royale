"""Fisica de Cosmos Royale en funciones puras.

Todas las funciones de este modulo son puras: no leen ni escriben estado global,
no usan aleatoriedad y con las mismas entradas devuelven siempre lo mismo. En
Java serian metodos `static` de una clase de utilidades. Esto es lo que se
reescribira tal cual en Go en la fase online, asi que aqui no hay objetos de
juego: solo numeros dentro, numeros fuera.
"""

from __future__ import annotations

import math

import config as cfg

# --- Masa, radio y movilidad --------------------------------------------------


def radius_from_mass(mass: float) -> float:
    """Radio de un cuerpo a partir de su masa."""
    return cfg.RADIUS_COEF * mass ** cfg.RADIUS_EXP


def vmax_from_mass(mass: float) -> float:
    """Velocidad maxima: crecer te hace mas lento."""
    return cfg.VMAX_COEF * mass ** cfg.VMAX_EXP


def accel_from_mass(mass: float) -> float:
    """Aceleracion por empuje propio: crecer te hace menos agil."""
    return cfg.ACCEL_COEF * mass ** cfg.ACCEL_EXP


def level_from_mass(mass: float) -> int:
    """Nivel (1..5) a partir de la masa."""
    level = 1
    for i, min_mass in enumerate(cfg.LEVEL_MIN_MASS):
        if mass >= min_mass:
            level = i + 1
    return level


def collect_radius(mass: float, level: int) -> float:
    """Radio de recoleccion de polvo: se amplia con el nivel."""
    return radius_from_mass(mass) * (1.0 + cfg.COLLECT_STEP * (level - 1))


# --- Colapso ------------------------------------------------------------------


def collapse_progress(t: float, deaths: int) -> float:
    """Progreso del colapso P en [0, 1].

    Mezcla tiempo y muertes, con un suelo duro que garantiza P = 1 en t = 300 s
    aunque no muera nadie.
    """
    organic = (
        cfg.P_TIME_WEIGHT * t / cfg.MATCH_HARD_LIMIT_S
        + cfg.P_DEATH_WEIGHT * deaths / (cfg.N_PLAYERS - 1)
    )
    hard = (t - cfg.P_HARD_START_S) / cfg.P_HARD_SPAN_S
    hard = min(1.0, max(0.0, hard))
    return min(1.0, max(0.0, max(organic, hard)))


def phase_from_p(p: float) -> int:
    """Fase del colapso (1..4) a partir de P."""
    for i, bound in enumerate(cfg.PHASE_BOUNDS):
        if p <= bound:
            return i + 1
    return len(cfg.PHASE_BOUNDS)


def arena_radius(p: float) -> float:
    """Radio de la arena; fuera de el esta la zona de radiacion."""
    return cfg.ARENA_R0 - cfg.ARENA_R_SHRINK * p


def horizon_radius(p: float) -> float:
    """Radio del horizonte del agujero central."""
    return cfg.HORIZON_H0 + cfg.HORIZON_H_GROWTH * p


def gravity_gm(p: float) -> float:
    """Parametro GM del pozo central, que crece con el colapso."""
    return cfg.GRAVITY_GM0 * (1.0 + cfg.GRAVITY_GROWTH * p)


def endgame_gravity_factor(t: float) -> float:
    """Multiplicador de gravedad del final: 1 hasta el minuto 4, maximo al 5.

    Sustituye al corte seco a los 5:00. En lugar de que el reloj mate, la
    gravedad se vuelve inescapable y es el agujero el que cierra la partida.
    """
    if t <= cfg.ENDGAME_START_S:
        return 1.0
    if t >= cfg.ENDGAME_FULL_S:
        return cfg.ENDGAME_GRAVITY_MULT
    span = cfg.ENDGAME_FULL_S - cfg.ENDGAME_START_S
    k = (t - cfg.ENDGAME_START_S) / span
    return 1.0 + (cfg.ENDGAME_GRAVITY_MULT - 1.0) * k


def gravity_accel(x: float, y: float, gm: float) -> tuple[float, float]:
    """Aceleracion gravitatoria hacia el centro, con suavizado de Plummer.

    El suavizado evita que la fuerza se vaya a infinito en r = 0, que es lo que
    rompe cualquier integrador numerico.
    """
    r2 = x * x + y * y
    denom = (r2 + cfg.PLUMMER_EPS * cfg.PLUMMER_EPS) ** 1.5
    factor = -gm / denom
    return factor * x, factor * y


def replenish_rate(p: float) -> float:
    """Masa de polvo repuesta por segundo, que baja linealmente hasta P = 0,5."""
    if p >= cfg.REPLENISH_END_P:
        return 0.0
    return cfg.REPLENISH_RATE * (1.0 - p / cfg.REPLENISH_END_P)


def assist_probability(p: float) -> float:
    """Probabilidad de escape asistido por el entorno, que se agota con las fases."""
    return cfg.ASSIST_P0 * (1.0 - p)


def env_help_fade(p: float) -> float:
    """Cuanto queda de las AYUDAS del entorno (1 al principio, 0 en la fase 3).

    Los danos del entorno no se desvanecen: lo que se agota es la ventaja del
    pequeno, que es lo que dice el diseno.
    """
    if p <= cfg.ENV_FADE_FROM_P:
        return 1.0
    if p >= cfg.ENV_FADE_END_P:
        return 0.0
    span = cfg.ENV_FADE_END_P - cfg.ENV_FADE_FROM_P
    return (cfg.ENV_FADE_END_P - p) / span


# --- Cuasares -----------------------------------------------------------------


def quasar_fires_this_tick(t: float, dt: float, phase: float) -> bool:
    """True si la onda de choque salta en este tick.

    Es ciclico y predecible a proposito: se mira si el contador de periodos
    cambia de numero entre el principio y el final del tick, igual que se
    detecta un cambio de minuto mirando si el entero de t/60 ha subido.
    """
    period = cfg.QUASAR_PERIOD_S
    if period <= 0.0:
        return False
    before = (t - phase) / period
    after = (t + dt - phase) / period
    return math.floor(after) > math.floor(before) and after >= 0.0


def quasar_impulse_speed(mass: float, fade: float) -> float:
    """Velocidad que anade la onda: inversamente proporcional a la masa."""
    if mass <= 0.0:
        return 0.0
    return cfg.QUASAR_IMPULSE / mass * fade


# --- Pulsares -----------------------------------------------------------------


def pulsar_beam_angle(t: float, phase: float, direction: float) -> float:
    """Angulo del haz en el instante t."""
    if cfg.PULSAR_PERIOD_S <= 0.0:
        return phase
    return phase + direction * 2.0 * math.pi * t / cfg.PULSAR_PERIOD_S


def angle_difference(a: float, b: float) -> float:
    """Diferencia angular mas corta entre dos angulos, en [-pi, pi]."""
    d = (a - b) % (2.0 * math.pi)
    if d > math.pi:
        d -= 2.0 * math.pi
    return d


def pulsar_drain_rate(mass: float) -> float:
    """Fraccion de masa por segundo que drena el haz.

    Crece con la masa, que es como se castiga mas al grande: a igual tiempo
    dentro del haz, el grande pierde un porcentaje mayor que el pequeno.
    """
    return cfg.PULSAR_DRAIN_COEF * mass ** cfg.PULSAR_DRAIN_EXP


def pulsar_zone(
    body_x: float,
    body_y: float,
    pulsar_x: float,
    pulsar_y: float,
    beam_angle: float,
) -> int:
    """Donde esta el cuerpo respecto al haz: 0 fuera, 1 dentro, 2 en el borde."""
    dx = body_x - pulsar_x
    dy = body_y - pulsar_y
    dist = math.hypot(dx, dy)
    if dist > cfg.PULSAR_RANGE or dist == 0.0:
        return 0
    offset = abs(angle_difference(math.atan2(dy, dx), beam_angle))
    if offset <= cfg.PULSAR_HALF_ANGLE:
        return 1
    if offset <= cfg.PULSAR_HALF_ANGLE * cfg.PULSAR_EDGE_BAND:
        return 2
    return 0


def element_is_active(
    x: float, y: float, arena_r: float, horizon_h: float
) -> bool:
    """Un elemento del entorno deja de funcionar si el colapso lo deja fuera de
    la arena o se lo traga el agujero. Asi se agotan con las fases sin regla
    aparte."""
    r = math.hypot(x, y)
    return horizon_h < r <= arena_r


# --- Tidal stripping ----------------------------------------------------------


def strip_fraction_per_s(attacker_mass: float, victim_mass: float) -> float:
    """Fraccion de masa que la victima pierde por segundo.

    Devuelve 0 si no se alcanza el ratio minimo: por debajo de el no hay
    transferencia en ninguna direccion, solo rebote.
    """
    if attacker_mass < cfg.STRIP_MIN_RATIO * victim_mass:
        return 0.0
    delta = (attacker_mass - victim_mass) / attacker_mass
    return cfg.STRIP_K * delta ** cfg.STRIP_ALPHA


def decay_amount(mass: float, rate_per_s: float, dt: float) -> float:
    """Masa perdida en dt con una tasa continua de rate_per_s por segundo.

    Se usa la forma exponencial m*(1 - e^(-rate*dt)) en lugar de mass*rate*dt
    para que el resultado no dependa del paso de simulacion: es la misma regla
    corriendo a 10 Hz y a 25 Hz.
    """
    if rate_per_s <= 0.0 or dt <= 0.0:
        return 0.0
    return mass * (1.0 - math.exp(-rate_per_s * dt))


def in_contact(
    x_a: float, y_a: float, r_a: float, x_b: float, y_b: float, r_b: float
) -> bool:
    """Hay contacto si la distancia es menor o igual que la suma de radios."""
    dx = x_a - x_b
    dy = y_a - y_b
    reach = r_a + r_b
    return dx * dx + dy * dy <= reach * reach


# --- Integracion --------------------------------------------------------------


def star_orbit_radius(p: float) -> float:
    """Radio de la orbita de la estrella: espiralea hacia dentro con el colapso."""
    return cfg.STAR_ORBIT_R0 + (cfg.STAR_ORBIT_R1 - cfg.STAR_ORBIT_R0) * p


def star_position(t: float, p: float, phase: float) -> tuple[float, float]:
    """Donde esta la estrella en el instante t. Orbita prescrita, no simulada.

    Va sobre rieles a proposito: el jugador puede aprenderse su ciclo y
    planificar la honda, y el servidor en Go no necesita integrarla.
    """
    r = star_orbit_radius(p)
    angle = phase + 2.0 * math.pi * t / cfg.STAR_PERIOD_S
    return r * math.cos(angle), r * math.sin(angle)


def star_accel(
    x: float, y: float, star_x: float, star_y: float
) -> tuple[float, float]:
    """Gravedad de la estrella sobre un cuerpo, con su propio suavizado."""
    dx = x - star_x
    dy = y - star_y
    r2 = dx * dx + dy * dy
    denom = (r2 + cfg.STAR_EPS * cfg.STAR_EPS) ** 1.5
    factor = -cfg.STAR_GM / denom
    return factor * dx, factor * dy


# --- Empuje propio ------------------------------------------------------------


def edge_pull_accel(depth: float, escape_speed: float) -> float:
    """Tiron hacia dentro cuando un cuerpo esta fuera del borde de la arena.

    Depende de la velocidad con la que intento salir (registrada al cruzar) y
    de lo lejos que haya llegado. No quita masa: solo devuelve. El efecto es que
    el borde se puede usar como una pared de rebote para cambiar de direccion
    sin gastar empuje.
    """
    pull = (
        cfg.EDGE_PULL_BASE
        + cfg.EDGE_PULL_SPEED * max(0.0, escape_speed)
        + cfg.EDGE_PULL_DEPTH * max(0.0, depth)
    )
    return min(pull, cfg.EDGE_PULL_MAX)


def stopping_distance(speed: float, accel: float) -> float:
    """Distancia que necesita un cuerpo para pararse desde esta velocidad.

    Es la cuenta del frenado de un coche: v^2 / (2a). Con la aceleracion
    cayendo con la masa (m^-0,35), un cuerpo grande necesita muchisimo mas
    sitio para parar, y eso es lo que le hace peligroso acercarse al pozo.
    """
    if accel <= 0.0:
        return float("inf")
    return speed * speed / (2.0 * accel)


def thrust_vector(
    desired_x: float,
    desired_y: float,
    vx: float,
    vy: float,
    accel: float,
    vmax: float,
) -> tuple[float, float]:
    """Empuje propio, con el componente de avance desvanecido cerca de vmax.

    En lugar de cortar la velocidad de golpe al llegar al tope, se apaga el
    empuje en la direccion en la que ya se avanza. Girar y frenar siguen al
    100 %, asi que un cuerpo rapido mantiene el control, y la velocidad que
    regala el terreno (hondas, cuasares, pulsares) no se recorta nunca porque
    no viene del empuje.
    """
    if desired_x == 0.0 and desired_y == 0.0:
        return 0.0, 0.0
    speed = math.hypot(vx, vy)
    if speed <= 1e-9 or vmax <= 0.0:
        return accel * desired_x, accel * desired_y
    # Descomponer el empuje en "a lo largo de la velocidad" y "de lado".
    ux = vx / speed
    uy = vy / speed
    along = desired_x * ux + desired_y * uy
    side_x = desired_x - along * ux
    side_y = desired_y - along * uy
    if along > 0.0:
        # Acelerar: se desvanece al acercarse a la velocidad punta, con una
        # curva que deja casi todo el empuje disponible hasta cerca del tope.
        ratio = speed / vmax
        fade = 1.0 - ratio ** cfg.THRUST_FADE_POWER if ratio < 1.0 else 0.0
        if fade < 0.0:
            fade = 0.0
        along *= fade
    # along < 0 es frenar: se deja entero.
    return accel * (along * ux + side_x), accel * (along * uy + side_y)


def clamp_speed(vx: float, vy: float, vmax: float) -> tuple[float, float]:
    """Limita el modulo de la velocidad sin cambiar su direccion."""
    speed2 = vx * vx + vy * vy
    if speed2 <= vmax * vmax or speed2 == 0.0:
        return vx, vy
    scale = vmax / math.sqrt(speed2)
    return vx * scale, vy * scale


def integrate_body(
    x: float,
    y: float,
    vx: float,
    vy: float,
    ax: float,
    ay: float,
    dt: float,
    vmax: float,
) -> tuple[float, float, float, float]:
    """Euler semi-implicito: primero la velocidad, luego la posicion.

    Es el integrador que usan la mayoria de los motores de juego porque conserva
    la energia mucho mejor que el Euler normal en orbitas, y cuesta lo mismo.
    """
    vx += ax * dt
    vy += ay * dt
    vx, vy = clamp_speed(vx, vy, vmax)
    x += vx * dt
    y += vy * dt
    return x, y, vx, vy


def elastic_bounce(
    x_a: float,
    y_a: float,
    vx_a: float,
    vy_a: float,
    m_a: float,
    x_b: float,
    y_b: float,
    vx_b: float,
    vy_b: float,
    m_b: float,
    restitution: float,
) -> tuple[float, float, float, float]:
    """Rebote suave entre dos cuerpos que no pueden absorberse.

    Invierte la componente normal de la velocidad relativa conservando el
    momento. Devuelve las velocidades nuevas de A y B.
    """
    dx = x_b - x_a
    dy = y_b - y_a
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return vx_a, vy_a, vx_b, vy_b
    nx = dx / dist
    ny = dy / dist
    rel = (vx_b - vx_a) * nx + (vy_b - vy_a) * ny
    if rel > 0.0:
        # Ya se estan separando: no hay que hacer nada.
        return vx_a, vy_a, vx_b, vy_b
    impulse = -(1.0 + restitution) * rel / (1.0 / m_a + 1.0 / m_b)
    return (
        vx_a - impulse * nx / m_a,
        vy_a - impulse * ny / m_a,
        vx_b + impulse * nx / m_b,
        vy_b + impulse * ny / m_b,
    )


def circular_orbit_speed(r: float, gm: float) -> float:
    """Velocidad de una orbita circular a radio r con el pozo suavizado."""
    if r <= 0.0:
        return 0.0
    denom = (r * r + cfg.PLUMMER_EPS * cfg.PLUMMER_EPS) ** 1.5
    return math.sqrt(gm * r * r / denom)
