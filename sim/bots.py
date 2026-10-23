"""Politicas de los bots: novato, medio y competente.

Un bot recibe lo que ve y devuelve solo una direccion de empuje (un vector
unitario) y si enciende el turbo. No mueve nada ni cambia masas: eso lo hace
rules.py. Es la separacion habitual entre "decidir" y "aplicar", como un
Strategy de Java que devuelve la jugada y otro objeto la ejecuta.

Lo unico aleatorio de toda la simulacion vive aqui: cada bot tiene su propio
flujo de numeros aleatorios, derivado de la semilla de la partida y de su id, de
forma que anadir o quitar un bot no cambia las decisiones de los demas.
"""

from __future__ import annotations

import math
import random

import config as cfg
import physics as ph
from state import ROCK, Body, Pickups, Pulsar, Star

# --- Utilidades ---------------------------------------------------------------


def _normalize(dx: float, dy: float) -> tuple[float, float]:
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return 0.0, 0.0
    return dx / dist, dy / dist


def _rotate(dx: float, dy: float, angle: float) -> tuple[float, float]:
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a


def _best_food(
    body: Body,
    pickups: Pickups,
    by_value: bool,
    gm: float = 0.0,
    accel: float = 0.0,
    star: Star | None = None,
) -> tuple[float, float, float] | None:
    """Mejor trozo de comida alcanzable, o None si no ve ninguno.

    Devuelve (dx, dy, puntuacion) para poder comparar con una presa.

    by_value=False devuelve el mas cercano (novato y medio).
    by_value=True devuelve el de mejor relacion masa/distancia (competente).
    """
    can_eat_rocks = body.mass >= cfg.ROCK_MIN_EAT_MASS
    indices = pickups.grid.candidates_expanding(body.x, body.y, cfg.BOT_PERCEPTION_RADIUS)
    if not indices:
        return None
    xs, ys, masses, kinds, alive = (
        pickups.xs,
        pickups.ys,
        pickups.masses,
        pickups.kinds,
        pickups.alive,
    )
    best_score = -1e30
    best: tuple[float, float, float] | None = None
    for i in indices:
        if not alive[i]:
            continue
        if kinds[i] == ROCK and not can_eat_rocks:
            continue
        dx = xs[i] - body.x
        dy = ys[i] - body.y
        dist2 = dx * dx + dy * dy
        if accel > 0.0 and not _can_escape_from(xs[i], ys[i], gm, accel, star):
            continue   # ahi no puede entrar y salir: no es comida para el
        if by_value:
            score = masses[i] / (dist2 + 1.0)
        else:
            score = -dist2
        if score > best_score:
            best_score = score
            best = (dx, dy, score)
    return best


def _gravity_magnitude(x: float, y: float, gm: float, star: Star | None) -> float:
    """Gravedad total que se siente en un punto: agujero mas estrella."""
    gx, gy = ph.gravity_accel(x, y, gm)
    if star is not None:
        sx, sy = ph.star_accel(x, y, star.x, star.y)
        gx += sx
        gy += sy
    return math.hypot(gx, gy)


def _can_escape_from(
    x: float, y: float, gm: float, accel: float, star: Star | None = None
) -> bool:
    """Si un cuerpo con esta aceleracion podria salir de ese punto.

    Es la cuenta que hace la diferencia entre el pequeno y el grande: la
    aceleracion baja con la masa (20 * m^-0,1), asi que el mismo punto que es
    seguro para un cuerpo de masa 2 es una trampa para uno de masa 80.
    """
    return _gravity_magnitude(x, y, gm, star) < cfg.COMP_GRAVITY_TOLERANCE * accel


def _best_prey(
    body: Body, others: list[Body], radius: float
) -> tuple[float, float, float] | None:
    """Mejor presa: rival al que se le puede arrancar masa, valorado con el bonus.

    La puntuacion esta en la misma escala que la de la comida (masa esperada
    partido por distancia), para poder comparar "voy a por polvo" con "voy a por
    ese rival" con el mismo criterio. Con el bonus de devorar, un rival de masa
    10 vale 15, asi que normalmente gana la caza.
    """
    limit2 = radius * radius
    best_score = -1e30
    best: tuple[float, float, float] | None = None
    for other in others:
        if other is body or not other.alive:
            continue
        if body.mass < cfg.STRIP_MIN_RATIO * other.mass:
            continue
        dx = other.x - body.x
        dy = other.y - body.y
        dist2 = dx * dx + dy * dy
        if dist2 > limit2:
            continue
        score = other.mass * cfg.PLAYER_KILL_MASS_MULT / (dist2 + 1.0)
        if score > best_score:
            best_score = score
            best = (dx, dy, score)
    return best


def _threats(body: Body, others: list[Body], radius: float) -> list[tuple[Body, float]]:
    """Cuerpos que pueden hacerle stripping y estan dentro del radio dado."""
    out = []
    limit2 = radius * radius
    for other in others:
        if other is body or not other.alive:
            continue
        if other.mass < cfg.STRIP_MIN_RATIO * body.mass:
            continue
        dx = other.x - body.x
        dy = other.y - body.y
        dist2 = dx * dx + dy * dy
        if dist2 <= limit2:
            out.append((other, math.sqrt(dist2)))
    return out


def _flee_vector(body: Body, threats: list[tuple[Body, float]]) -> tuple[float, float]:
    """Direccion de huida: suma de los vectores de alejamiento, pesados por cercania."""
    vx = 0.0
    vy = 0.0
    for other, dist in threats:
        if dist == 0.0:
            continue
        weight = 1.0 / dist
        vx += (body.x - other.x) / dist * weight
        vy += (body.y - other.y) / dist * weight
    return _normalize(vx, vy)


# --- Politicas ----------------------------------------------------------------


def _avoid_hazards(
    body: Body, dx: float, dy: float, horizon_h: float, arena_r: float
) -> tuple[float, float]:
    """Correccion minima del pozo y del borde para novato y medio, si estan activadas."""
    r = math.hypot(body.x, body.y)
    if r <= 0.0:
        return dx, dy
    if cfg.BASIC_WELL_MARGIN > 0.0 and r < horizon_h * cfg.BASIC_WELL_MARGIN:
        return _normalize(dx + 2.0 * body.x / r, dy + 2.0 * body.y / r)
    if cfg.BASIC_EDGE_MARGIN > 0.0 and r > arena_r * cfg.BASIC_EDGE_MARGIN:
        return _normalize(dx - 1.5 * body.x / r, dy - 1.5 * body.y / r)
    return dx, dy


def _beam_escape(
    body: Body, pulsars: list[Pulsar], t: float
) -> tuple[float, float] | None:
    """Si esta dentro de un haz de pulsar, por donde sale antes.

    El haz es una cuna estrecha que sale del pulsar, asi que lo rapido es
    moverse de lado (perpendicular al radio), no hacia atras.
    """
    for pulsar in pulsars:
        beam = ph.pulsar_beam_angle(t, pulsar.phase, pulsar.direction)
        dx = body.x - pulsar.x
        dy = body.y - pulsar.y
        dist = math.hypot(dx, dy)
        if dist == 0.0 or dist > cfg.PULSAR_RANGE:
            continue
        offset = ph.angle_difference(math.atan2(dy, dx), beam)
        if abs(offset) > cfg.PULSAR_HALF_ANGLE * cfg.PULSAR_FEAR_MARGIN:
            continue
        # Perpendicular al radio, hacia el lado en el que ya esta.
        sign = 1.0 if offset >= 0.0 else -1.0
        return _normalize(-dy / dist * sign, dx / dist * sign)
    return None


def _surf_vector(
    body: Body, pulsars: list[Pulsar], t: float
) -> tuple[float, float] | None:
    """Girar alrededor del pulsar en el sentido del haz, para quedarse en el
    borde el mayor tiempo posible. Es la version simple de "surfear el borde"."""
    best = None
    best_dist = cfg.PULSAR_RANGE
    for pulsar in pulsars:
        dx = body.x - pulsar.x
        dy = body.y - pulsar.y
        dist = math.hypot(dx, dy)
        if dist == 0.0 or dist > best_dist:
            continue
        best_dist = dist
        best = _normalize(-dy / dist * pulsar.direction, dx / dist * pulsar.direction)
    return best


def _brake_vector(
    body: Body, horizon_h: float, accel: float
) -> tuple[float, float] | None:
    """Si va a caer al agujero, empujar hacia fuera antes de que sea tarde.

    No mira solo donde esta, mira hacia donde va: si la distancia que le queda
    al horizonte es menor que la que necesita para frenar, hay que frenar ya.
    """
    r = math.hypot(body.x, body.y)
    if r <= 0.0:
        return None
    # Velocidad con la que se acerca al centro (positiva = cayendo).
    closing = -(body.vx * body.x + body.vy * body.y) / r
    if closing <= 0.0:
        return None
    margin = r - horizon_h
    if margin <= 0.0:
        return None
    if ph.stopping_distance(closing, accel) * cfg.BRAKE_SAFETY < margin:
        return None
    # Salir en espiral, no en linea recta: una parte hacia fuera para frenar la
    # caida y otra de lado para recuperar velocidad orbital. Empujar solo hacia
    # fuera gasta todo el empuje contra la gravedad y se vuelve a caer.
    out_x, out_y = body.x / r, body.y / r
    tan_x, tan_y = -out_y, out_x
    # El lado se elige segun el giro que ya lleva, para no pelearse con su
    # propia velocidad.
    if body.vx * tan_x + body.vy * tan_y < 0.0:
        tan_x, tan_y = -tan_x, -tan_y
    w = cfg.BRAKE_TANGENTIAL
    return _normalize(out_x + tan_x * w, out_y + tan_y * w)


def _star_escape(body: Body, star: Star | None) -> tuple[float, float] | None:
    """Si esta pegado a la estrella, salir: quema masa a toda velocidad."""
    if star is None:
        return None
    dx = body.x - star.x
    dy = body.y - star.y
    dist = math.hypot(dx, dy)
    danger = (cfg.STAR_RADIUS + ph.radius_from_mass(body.mass)) * cfg.STAR_FEAR_MARGIN
    if dist > danger or dist == 0.0:
        return None
    return _normalize(dx, dy)


def _decide_novice(
    body: Body,
    others: list[Body],
    pickups: Pickups,
    star: Star | None,
    horizon_h: float,
    arena_r: float,
    rng: random.Random,
) -> tuple[float, float, bool]:
    """Va al polvo mas cercano y no evita a nadie."""
    brake = _brake_vector(body, horizon_h, ph.accel_from_mass(body.mass))
    if brake is not None:
        return brake[0], brake[1], False
    food = _best_food(body, pickups, by_value=False)
    if food is None:
        angle = rng.uniform(-math.pi, math.pi)
        dx, dy = math.cos(angle), math.sin(angle)
    else:
        dx, dy = _normalize(food[0], food[1])
    dx, dy = _avoid_hazards(body, dx, dy, horizon_h, arena_r)
    return dx, dy, False


def _decide_medium(
    body: Body,
    others: list[Body],
    pickups: Pickups,
    pulsars: list[Pulsar],
    star: Star | None,
    t: float,
    horizon_h: float,
    arena_r: float,
    rng: random.Random,
) -> tuple[float, float, bool]:
    """Como el novato, pero huye de cuerpos mayores y sale del haz del pulsar.

    El medio entiende que el haz le quita masa y se aparta, pero no sabe
    aprovechar el borde: eso es lo que distingue al competente.
    """
    brake = _brake_vector(body, horizon_h, ph.accel_from_mass(body.mass))
    if brake is not None:
        return brake[0], brake[1], False
    burn = _star_escape(body, star)
    if burn is not None:
        return burn[0], burn[1], False
    escape = _beam_escape(body, pulsars, t)
    if escape is not None:
        return escape[0], escape[1], False
    threats = _threats(body, others, cfg.MEDIUM_FLEE_RADIUS)
    if threats:
        dx, dy = _flee_vector(body, threats)
        dx, dy = _avoid_hazards(body, dx, dy, horizon_h, arena_r)
        return dx, dy, False
    # Desde que devorar rinde mas que pastar, el medio tambien va a por rivales
    # mas pequenos, aunque sin valorar la jugada: coge al que tenga mas cerca.
    prey = _best_prey(body, others, cfg.MEDIUM_HUNT_RADIUS)
    if prey is not None:
        dx, dy = _normalize(prey[0], prey[1])
        dx, dy = _avoid_hazards(body, dx, dy, horizon_h, arena_r)
        return dx, dy, False
    return _decide_novice(body, others, pickups, star, horizon_h, arena_r, rng)


def _decide_competent(
    body: Body,
    others: list[Body],
    pickups: Pickups,
    pulsars: list[Pulsar],
    star: Star | None,
    t: float,
    p: float,
    arena_r: float,
    horizon_h: float,
    rng: random.Random,
) -> tuple[float, float, bool]:
    """Huye con margen segun la velocidad del rival, caza a los pequenos, come
    por valor y entra al pozo solo hasta donde puede volver a salir."""
    gm = ph.gravity_gm(p) * ph.endgame_gravity_factor(t)
    accel = ph.accel_from_mass(body.mass)
    can_turbo = ph.level_from_mass(body.mass) >= cfg.TURBO_MIN_LEVEL
    brake = _brake_vector(body, horizon_h, accel)
    if brake is not None:
        return brake[0], brake[1], can_turbo
    burn = _star_escape(body, star)
    if burn is not None:
        return burn[0], burn[1], can_turbo
    # 1. Huir: el margen depende de lo rapido que sea el depredador.
    max_margin = cfg.COMP_FLEE_BASE_MARGIN + cfg.COMP_FLEE_SPEED_MARGIN * ph.vmax_from_mass(
        cfg.START_MASS
    )
    threats = _threats(body, others, max_margin)
    real_threats = []
    for other, dist in threats:
        margin = cfg.COMP_FLEE_BASE_MARGIN + cfg.COMP_FLEE_SPEED_MARGIN * ph.vmax_from_mass(
            other.mass
        )
        if dist <= margin:
            real_threats.append((other, dist))

    fleeing = bool(real_threats)
    escape = _beam_escape(body, pulsars, t)
    if escape is not None:
        # Dentro del haz se pierde masa muy rapido: salir es lo primero.
        return escape[0], escape[1], ph.level_from_mass(body.mass) >= cfg.TURBO_MIN_LEVEL

    if fleeing:
        base_x, base_y = _flee_vector(body, real_threats)
        if cfg.COMP_SURF_PULSAR:
            surf = _surf_vector(body, pulsars, t)
            if surf is not None:
                # Girar alrededor del pulsar mientras huye: el borde del haz da
                # velocidad al que lo cronometra bien.
                base_x += surf[0] * 1.2
                base_y += surf[1] * 1.2
    else:
        # 2. Elegir entre cazar y comer con el mismo criterio: masa esperada
        #    partido por distancia. El bonus de devorar entra en la cuenta, asi
        #    que un rival a tiro suele valer mas que un trozo de polvo cerca.
        prey = _best_prey(body, others, cfg.COMP_HUNT_RADIUS)
        if cfg.COMP_PHYSICAL_WELL_CHECK:
            food = _best_food(
                body, pickups, by_value=True, gm=gm, accel=accel, star=star
            )
        else:
            food = _best_food(body, pickups, by_value=True)
        target = None
        if prey is not None and food is not None:
            target = prey if prey[2] >= food[2] else food
        elif prey is not None:
            target = prey
        elif food is not None:
            target = food
        if target is None:
            angle = rng.uniform(-math.pi, math.pi)
            base_x, base_y = math.cos(angle), math.sin(angle)
        else:
            base_x, base_y = _normalize(target[0], target[1])

    # Correcciones: salir del pozo y no pegarse al borde.
    r = math.hypot(body.x, body.y)
    escaping_well = False
    if r > 0.0:
        if cfg.COMP_PHYSICAL_WELL_CHECK:
            too_deep = not _can_escape_from(body.x, body.y, gm, accel, star)
        else:
            too_deep = r < horizon_h * cfg.COMP_WELL_MARGIN
        if too_deep:
            escaping_well = True
            base_x += 2.0 * body.x / r
            base_y += 2.0 * body.y / r
        elif r > arena_r * cfg.COMP_EDGE_MARGIN:
            base_x -= 1.5 * body.x / r
            base_y -= 1.5 * body.y / r

    dx, dy = _normalize(base_x, base_y)
    turbo = cfg.COMP_TURBO_WHEN_FLEEING and (fleeing or escaping_well)
    return dx, dy, turbo


# --- Punto de entrada ---------------------------------------------------------


def decide(
    body: Body,
    others: list[Body],
    pickups: Pickups,
    pulsars: list[Pulsar],
    star: Star | None,
    t: float,
    p: float,
    arena_r: float,
    horizon_h: float,
    rng: random.Random,
) -> tuple[float, float, bool]:
    """Decide la direccion de empuje y el turbo de un cuerpo."""
    if body.archetype == "novice":
        dx, dy, turbo = _decide_novice(body, others, pickups, star, horizon_h, arena_r, rng)
    elif body.archetype == "medium":
        dx, dy, turbo = _decide_medium(
            body, others, pickups, pulsars, star, t, horizon_h, arena_r, rng
        )
    else:
        dx, dy, turbo = _decide_competent(
            body, others, pickups, pulsars, star, t, p, arena_r, horizon_h, rng
        )

    if cfg.BOT_NOISE_RAD > 0.0 and (dx or dy):
        dx, dy = _rotate(dx, dy, rng.uniform(-cfg.BOT_NOISE_RAD, cfg.BOT_NOISE_RAD))

    # El turbo solo existe desde el nivel III.
    if turbo and ph.level_from_mass(body.mass) < cfg.TURBO_MIN_LEVEL:
        turbo = False
    return dx, dy, turbo


def make_rng(seed: int, bid: int) -> random.Random:
    """Flujo aleatorio propio de cada bot, estable frente a cambios en la sala."""
    return random.Random((seed * 1_000_003) ^ (bid * 2_654_435_761))
