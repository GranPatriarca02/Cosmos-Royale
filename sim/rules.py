"""Reglas de partida: colapso, recoleccion, stripping, muertes y desempates.

physics.py tiene las formulas puras; aqui se aplican al estado del mundo. Si una
regla del diseno cambia, se cambia en este archivo o en config.py, nunca en
physics.py.
"""

from __future__ import annotations

import math
import random

import bots
import config as cfg
import physics as ph
from state import DUST, ROCK, Body, Pickups, Pulsar, Quasar, Star, WorldState

# --- Creacion del mundo -------------------------------------------------------


def _area_uniform_radius(r_min: float, r_max: float, rng: random.Random) -> float:
    """Radio al azar entre r_min y r_max con densidad uniforme por area.

    Sortear el radio de forma uniforme amontonaria los puntos cerca del centro,
    porque un anillo exterior tiene mas area que uno interior del mismo grosor.
    """
    u = rng.random()
    return math.sqrt(r_min * r_min + u * (r_max * r_max - r_min * r_min))


def _spawn_in_belts(pickups: Pickups, count: int, mass: float, kind: int, rng) -> None:
    belts = cfg.BELTS
    for i in range(count):
        r_min, r_max = belts[i % len(belts)]
        r = _area_uniform_radius(r_min, r_max, rng)
        theta = rng.uniform(0.0, 2.0 * math.pi)
        pickups.add(r * math.cos(theta), r * math.sin(theta), mass, kind)


def _spawn_outside_belts(pickups: Pickups, count: int, mass: float, kind: int, rng) -> None:
    """Reparte fuera de los cinturones, sin pegarlo al horizonte inicial."""
    inner_limit = cfg.HORIZON_H0 * 2.0
    placed = 0
    while placed < count:
        r = _area_uniform_radius(inner_limit, cfg.ARENA_R0, rng)
        if any(r_min <= r <= r_max for r_min, r_max in cfg.BELTS):
            continue
        theta = rng.uniform(0.0, 2.0 * math.pi)
        pickups.add(r * math.cos(theta), r * math.sin(theta), mass, kind)
        placed += 1


def create_world(seed: int) -> WorldState:
    """Monta una partida: 20 cuerpos en el anillo de aparicion, polvo y rocas."""
    rng = random.Random(seed)
    world = WorldState()

    # Arquetipos: el sujeto medido es el bid 0; los 19 rivales se mezclan.
    n_rivals = cfg.N_PLAYERS - 1
    n_novice = int(cfg.NOVICE_RIVALS)
    n_competent = int(cfg.COMPETENT_RIVALS)
    n_medium = n_rivals - n_novice - n_competent
    if n_medium < 0:
        raise ValueError(
            f"NOVICE_RIVALS + COMPETENT_RIVALS no puede pasar de {n_rivals}"
        )
    rivals = ["novice"] * n_novice + ["medium"] * n_medium + ["competent"] * n_competent
    rng.shuffle(rivals)
    archetypes = ["competent"] + rivals

    # Posiciones: 20 puntos equiespaciados en el anillo, con el orden mezclado
    # para que el sujeto no salga siempre en el mismo sitio.
    slots = list(range(cfg.N_PLAYERS))
    rng.shuffle(slots)
    gm0 = ph.gravity_gm(0.0)
    orbital = ph.circular_orbit_speed(cfg.SPAWN_RING_RADIUS, gm0) * cfg.SPAWN_VELOCITY_FACTOR

    for bid in range(cfg.N_PLAYERS):
        angle = 2.0 * math.pi * slots[bid] / cfg.N_PLAYERS
        x = cfg.SPAWN_RING_RADIUS * math.cos(angle)
        y = cfg.SPAWN_RING_RADIUS * math.sin(angle)
        if cfg.SPAWN_VELOCITY_MODE == "orbital":
            vx, vy = -orbital * math.sin(angle), orbital * math.cos(angle)
        elif cfg.SPAWN_VELOCITY_MODE == "random":
            a = rng.uniform(0.0, 2.0 * math.pi)
            vx, vy = orbital * math.cos(a), orbital * math.sin(a)
        else:
            vx, vy = 0.0, 0.0
        world.bodies.append(
            Body(
                bid=bid,
                archetype=archetypes[bid],
                is_subject=(bid == 0),
                mass=cfg.START_MASS,
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                max_mass=cfg.START_MASS,
            )
        )

    # Masa libre: 60 % en cinturones, 40 % repartida, por cada tipo.
    dust_in_belts = int(round(cfg.DUST_COUNT * cfg.BELT_FRACTION))
    rocks_in_belts = int(round(cfg.ROCK_COUNT * cfg.BELT_FRACTION))
    _spawn_in_belts(world.pickups, dust_in_belts, cfg.DUST_MASS, DUST, rng)
    _spawn_outside_belts(world.pickups, cfg.DUST_COUNT - dust_in_belts, cfg.DUST_MASS, DUST, rng)
    _spawn_in_belts(world.pickups, rocks_in_belts, cfg.ROCK_MASS, ROCK, rng)
    _spawn_outside_belts(world.pickups, cfg.ROCK_COUNT - rocks_in_belts, cfg.ROCK_MASS, ROCK, rng)

    # Cuasares y pulsares: en anillos, equiespaciados y con el ciclo desfasado
    # para que no emitan todos a la vez.
    for i in range(int(cfg.QUASAR_COUNT)):
        angle = 2.0 * math.pi * i / max(1, int(cfg.QUASAR_COUNT)) + rng.uniform(0.0, 1.0)
        world.quasars.append(
            Quasar(
                x=cfg.QUASAR_RING_R * math.cos(angle),
                y=cfg.QUASAR_RING_R * math.sin(angle),
                phase=cfg.QUASAR_PERIOD_S * i / max(1, int(cfg.QUASAR_COUNT)),
            )
        )
    for i in range(int(cfg.PULSAR_COUNT)):
        angle = 2.0 * math.pi * i / max(1, int(cfg.PULSAR_COUNT)) + rng.uniform(0.0, 1.0)
        world.pulsars.append(
            Pulsar(
                x=cfg.PULSAR_RING_R * math.cos(angle),
                y=cfg.PULSAR_RING_R * math.sin(angle),
                phase=rng.uniform(0.0, 2.0 * math.pi),
                direction=1.0 if i % 2 == 0 else -1.0,
            )
        )

    world.star_phase = rng.uniform(0.0, 2.0 * math.pi)
    world.next_wave_t = cfg.FOOD_WAVE_FIRST_S
    world.initial_mass = cfg.N_PLAYERS * cfg.START_MASS + world.pickups.total_mass()
    return world


# --- Polvo suelto -------------------------------------------------------------


def drop_dust(world: WorldState, body: Body, amount: float) -> None:
    """Suelta masa como polvo en la posicion del cuerpo, por trozos enteros."""
    body.dust_debt += amount
    while body.dust_debt >= cfg.DUST_MASS:
        body.dust_debt -= cfg.DUST_MASS
        world.pickups.add(body.x, body.y, cfg.DUST_MASS, DUST)


def flush_dust(world: WorldState, body: Body) -> None:
    """Suelta lo que quede pendiente (al morir)."""
    if body.dust_debt > 0.0:
        world.pickups.add(body.x, body.y, body.dust_debt, DUST)
        body.dust_debt = 0.0


# --- Muertes ------------------------------------------------------------------


def kill(world: WorldState, body: Body, cause: str, t: float) -> None:
    body.alive = False
    body.death_time = t
    body.death_cause = cause
    world.deaths += 1


# --- Un tick ------------------------------------------------------------------


def tick(
    world: WorldState,
    dt: float,
    bot_rngs: list[random.Random],
    world_rng: random.Random,
) -> None:
    """Avanza la partida dt segundos. Modifica world en el sitio.

    bot_rngs tiene un flujo aleatorio por cuerpo y world_rng es el del mundo
    (reposicion de polvo). Estan separados a proposito: asi lo que decide un bot
    no desplaza la aleatoriedad del mapa ni al contrario.
    """
    t = world.t
    p = ph.collapse_progress(t, world.deaths)
    world.p = p
    gm = ph.gravity_gm(p) * ph.endgame_gravity_factor(t)
    arena_r = ph.arena_radius(p)
    horizon_h = ph.horizon_radius(p)
    pickups = world.pickups
    alive = [b for b in world.bodies if b.alive]

    # La estrella va sobre rieles: su posicion se calcula, no se integra. Deja
    # de contar cuando el colapso la mete dentro del horizonte.
    star = None
    if cfg.STAR_ENABLED:
        star_x, star_y = ph.star_position(t, p, world.star_phase)
        if math.hypot(star_x, star_y) > horizon_h:
            star = Star(x=star_x, y=star_y)
    world.star = star

    # 1. Decisiones de los bots, a intervalos fijos independientes de dt.
    for b in alive:
        if t >= b.next_decision_t:
            dx, dy, turbo = bots.decide(
                b, alive, pickups, world.pulsars, star, t, p, arena_r, horizon_h,
                bot_rngs[b.bid],
            )
            b.desired_x = dx
            b.desired_y = dy
            b.turbo_on = turbo
            b.next_decision_t = t + cfg.BOT_DECISION_INTERVAL_S

    # 2. Turbo: quema masa y la suelta como polvo.
    for b in alive:
        if b.turbo_on:
            burn = ph.decay_amount(b.mass, cfg.TURBO_MASS_BURN_PER_S, dt)
            b.mass -= burn
            b.turbo_time += dt
            drop_dust(world, b, burn)

    # 3. Movimiento: empuje propio + gravedad del agujero + gravedad de la
    #    estrella + zona de radiacion. El empuje se desvanece cerca de la
    #    velocidad punta, pero nada recorta la velocidad que da el terreno.
    for b in alive:
        accel = ph.accel_from_mass(b.mass)
        if b.turbo_on:
            accel *= 1.0 + cfg.TURBO_ACCEL_BONUS
        vmax = ph.vmax_from_mass(b.mass)
        ax, ay = ph.thrust_vector(b.desired_x, b.desired_y, b.vx, b.vy, accel, vmax)
        gx, gy = ph.gravity_accel(b.x, b.y, gm)
        ax += gx
        ay += gy
        if star is not None:
            sx, sy = ph.star_accel(b.x, b.y, star.x, star.y)
            ax += sx
            ay += sy
        r = math.hypot(b.x, b.y)
        if r > 0.0:
            radial = (b.vx * b.x + b.vy * b.y) / r   # positiva = saliendo
            if r > arena_r:
                if not b.outside:
                    # Acaba de cruzar: se registra con que ganas queria salir.
                    b.outside = True
                    b.edge_charge = max(0.0, radial)
                pull = ph.edge_pull_accel(r - arena_r, b.edge_charge)
                ax -= pull * b.x / r
                ay -= pull * b.y / r
            elif b.outside:
                b.outside = False
                b.edge_charge = 0.0
        ceiling = vmax * cfg.SPEED_CEILING_MULT
        b.x, b.y, b.vx, b.vy = ph.integrate_body(b.x, b.y, b.vx, b.vy, ax, ay, dt, ceiling)

    # 4b. Cuasares: onda de choque radial, inversamente proporcional a la masa.
    fade = ph.env_help_fade(p)
    if fade > 0.0:
        for quasar in world.quasars:
            if not ph.element_is_active(quasar.x, quasar.y, arena_r, horizon_h):
                continue
            if not ph.quasar_fires_this_tick(t, dt, quasar.phase):
                continue
            for b in alive:
                dx = b.x - quasar.x
                dy = b.y - quasar.y
                dist = math.hypot(dx, dy)
                if dist > cfg.QUASAR_RADIUS or dist == 0.0:
                    continue
                speed = ph.quasar_impulse_speed(b.mass, fade)
                if speed <= 0.0:
                    continue
                b.vx += speed * dx / dist
                b.vy += speed * dy / dist
                b.quasar_rides += 1

    # 4c. Pulsares: el haz drena masa (mas al grande) y el borde da velocidad.
    for pulsar in world.pulsars:
        if not ph.element_is_active(pulsar.x, pulsar.y, arena_r, horizon_h):
            continue
        beam = ph.pulsar_beam_angle(t, pulsar.phase, pulsar.direction)
        for b in alive:
            zone = ph.pulsar_zone(b.x, b.y, pulsar.x, pulsar.y, beam)
            if zone == 1:
                loss = ph.decay_amount(b.mass, ph.pulsar_drain_rate(b.mass), dt)
                b.mass -= loss
                b.beam_loss += loss
                world.beam_lost += loss
            elif zone == 2 and fade > 0.0:
                # Surfear el borde: empuja de verdad en el sentido en que gira
                # el haz, asi que el que lo cronometra bien sale disparado.
                dx = b.x - pulsar.x
                dy = b.y - pulsar.y
                dist = math.hypot(dx, dy)
                if dist > 0.0:
                    b.vx += -dy / dist * pulsar.direction * cfg.PULSAR_SURF_SPEED * fade * dt
                    b.vy += dx / dist * pulsar.direction * cfg.PULSAR_SURF_SPEED * fade * dt
                    b.surf_time += dt

    # 4d. Tocar la estrella quema masa muy rapido.
    if star is not None:
        for b in alive:
            reach = cfg.STAR_RADIUS + ph.radius_from_mass(b.mass)
            dx = b.x - star.x
            dy = b.y - star.y
            if dx * dx + dy * dy <= reach * reach:
                loss = ph.decay_amount(b.mass, cfg.STAR_CONTACT_DRAIN, dt)
                b.mass -= loss
                world.radiation_lost += loss

    # 5. Recoleccion de polvo (instantanea) y rocas (con la formula de stripping).
    xs, ys, masses, kinds, pick_alive = (
        pickups.xs,
        pickups.ys,
        pickups.masses,
        pickups.kinds,
        pickups.alive,
    )
    for b in alive:
        level = ph.level_from_mass(b.mass)
        reach = ph.collect_radius(b.mass, level)
        body_r = ph.radius_from_mass(b.mass)
        can_eat_rocks = b.mass >= cfg.ROCK_MIN_EAT_MASS
        search = max(reach, body_r + ph.radius_from_mass(cfg.ROCK_MASS))
        for i in pickups.grid.candidates(b.x, b.y, search):
            if not pick_alive[i]:
                continue
            dx = xs[i] - b.x
            dy = ys[i] - b.y
            dist2 = dx * dx + dy * dy
            if kinds[i] == DUST:
                if dist2 <= reach * reach:
                    b.mass += masses[i]
                    b.mass_eaten += masses[i]
                    pickups.remove(i)
            else:
                if not can_eat_rocks:
                    continue
                rock_mass = masses[i]
                contact = body_r + ph.radius_from_mass(rock_mass)
                if dist2 > contact * contact:
                    continue
                f = ph.strip_fraction_per_s(b.mass, rock_mass)
                if f <= 0.0:
                    continue
                loss = ph.decay_amount(rock_mass, f, dt)
                remaining = rock_mass - loss
                if remaining < cfg.MIN_MASS_ALIVE:
                    loss = rock_mass
                    remaining = 0.0
                b.mass += loss * cfg.STRIP_TO_ATTACKER
                b.mass_eaten += loss * cfg.STRIP_TO_ATTACKER
                drop_dust(world, b, loss * cfg.STRIP_TO_DUST)
                if remaining <= 0.0:
                    pickups.remove(i)
                else:
                    masses[i] = remaining

    # 6. Tidal stripping entre cuerpos. Se calcula todo con las masas de este
    #    instante y se aplica despues, para que el orden de los pares no cambie
    #    el resultado.
    transfers: list[tuple[Body, Body, float]] = []
    new_contacts: set[tuple[int, int]] = set()
    n = len(alive)
    for i in range(n):
        a = alive[i]
        r_a = ph.radius_from_mass(a.mass)
        for j in range(i + 1, n):
            b = alive[j]
            r_b = ph.radius_from_mass(b.mass)
            if not ph.in_contact(a.x, a.y, r_a, b.x, b.y, r_b):
                continue
            key = (a.bid, b.bid)
            if a.mass >= cfg.STRIP_MIN_RATIO * b.mass:
                attacker, victim = a, b
            elif b.mass >= cfg.STRIP_MIN_RATIO * a.mass:
                attacker, victim = b, a
            else:
                # Mismo tamano: rebote suave, nadie pierde masa.
                a.vx, a.vy, b.vx, b.vy = ph.elastic_bounce(
                    a.x, a.y, a.vx, a.vy, a.mass,
                    b.x, b.y, b.vx, b.vy, b.mass,
                    cfg.BOUNCE_RESTITUTION,
                )
                new_contacts.add(key)
                continue

            # Inmunidad de aparicion: la victima no puede ser desgarrada.
            if t < cfg.SPAWN_INVULN_S:
                new_contacts.add(key)
                continue

            # Escape asistido por el entorno: solo al empezar el contacto.
            if key not in world.contacts:
                if (
                    victim.mass <= cfg.ASSIST_VICTIM_MAX_RATIO * attacker.mass
                    and t >= victim.assist_ready_at
                    and bot_rngs[victim.bid].random() < ph.assist_probability(p)
                ):
                    dx = victim.x - attacker.x
                    dy = victim.y - attacker.y
                    dist = math.hypot(dx, dy)
                    if dist == 0.0:
                        dx, dy, dist = 1.0, 0.0, 1.0
                    speed = ph.vmax_from_mass(victim.mass) * cfg.ASSIST_IMPULSE_MULT
                    victim.vx = speed * dx / dist
                    victim.vy = speed * dy / dist
                    victim.assist_ready_at = t + cfg.ASSIST_COOLDOWN_S
                    continue  # rompe el contacto: este tick no pierde masa

            f = ph.strip_fraction_per_s(attacker.mass, victim.mass)
            loss = ph.decay_amount(victim.mass, f, dt)
            if loss > 0.0:
                transfers.append((attacker, victim, loss))
            new_contacts.add(key)

    world.contacts = new_contacts

    # Si varios atacan a la vez, la victima no puede perder mas masa de la que
    # tiene: se reparte proporcionalmente.
    if transfers:
        total_by_victim: dict[int, float] = {}
        for _, victim, loss in transfers:
            total_by_victim[victim.bid] = total_by_victim.get(victim.bid, 0.0) + loss
        best_attacker: dict[int, tuple[Body, float]] = {}
        for attacker, victim, loss in transfers:
            total = total_by_victim[victim.bid]
            scale = 1.0 if total <= victim.mass else victim.mass / total
            applied = loss * scale
            victim.mass -= applied
            # Devorar a un jugador rinde mas de lo que el rival tenia.
            gained = applied * cfg.PLAYER_KILL_MASS_MULT
            attacker.mass += gained
            attacker.mass_stolen += gained
            world.mass_created += gained - applied
            drop_dust(world, victim, applied * cfg.STRIP_TO_DUST)
            world.mass_created += applied * cfg.STRIP_TO_DUST
            previous = best_attacker.get(victim.bid)
            if previous is None or applied > previous[1]:
                best_attacker[victim.bid] = (attacker, applied)

        # Muertes por stripping: lo que queda va al atacante principal.
        for victim_bid, (attacker, _) in best_attacker.items():
            victim = world.bodies[victim_bid]
            if victim.alive and victim.mass < cfg.MIN_MASS_ALIVE:
                gained = victim.mass * cfg.PLAYER_KILL_MASS_MULT
                attacker.mass += gained
                attacker.mass_stolen += gained
                world.mass_created += gained - victim.mass
                attacker.kills += 1
                victim.mass = 0.0
                flush_dust(world, victim)
                kill(world, victim, "stripping", t)

    # 7. Muertes por el horizonte y por quedarse sin masa en la radiacion.
    for b in alive:
        if not b.alive:
            continue
        if math.hypot(b.x, b.y) <= horizon_h:
            world.hole_mass += b.mass
            b.mass = 0.0
            flush_dust(world, b)
            kill(world, b, "horizon", t)
        elif b.mass < cfg.MIN_MASS_ALIVE:
            # Sin masa suficiente para seguir siendo un cuerpo: lo que queda se
            # pierde. Ahora solo puede pasar por el haz de un pulsar o por tocar
            # la estrella, porque el borde ya no quita masa.
            world.radiation_lost += b.mass
            b.mass = 0.0
            flush_dust(world, b)
            kill(world, b, "drenaje", t)

    # 8. Marcas de nivel y masa maxima.
    for b in world.bodies:
        if not b.alive:
            continue
        if b.mass > b.max_mass:
            b.max_mass = b.mass
        if b.level3_time is None and b.mass >= cfg.LEVEL_MIN_MASS[2]:
            b.level3_time = t

    # 8b. Volver a aplicar el techo de velocidad, porque la masa ha cambiado en
    #     este tick (comer, crecer o perder masa mueve vmax). Sin esto, crecer no
    #     te frena hasta el tick siguiente.
    for b in alive:
        if not b.alive:
            continue
        vmax = ph.vmax_from_mass(b.mass)
        b.vx, b.vy = ph.clamp_speed(b.vx, b.vy, vmax * cfg.SPEED_CEILING_MULT)
        speed = math.hypot(b.vx, b.vy)
        b.alive_time += dt
        ratio = speed / vmax if vmax > 0.0 else 0.0
        if ratio > 1.0:
            b.time_over_vmax += dt
        if ratio > b.peak_speed_ratio:
            b.peak_speed_ratio = ratio

    # 9. El colapso se come el polvo: fuera de la arena desde la fase 2, todo en
    #    la fase 4, y lo que cae dentro del horizonte va al agujero.
    if t >= world.next_cleanup_t:
        world.next_cleanup_t = t + 1.0
        phase = ph.phase_from_p(p)
        no_dust = p >= cfg.NO_DUST_FROM_P
        h2 = horizon_h * horizon_h
        r2 = arena_r * arena_r
        for i in range(len(xs)):
            if not pick_alive[i]:
                continue
            d2 = xs[i] * xs[i] + ys[i] * ys[i]
            if d2 <= h2:
                world.hole_mass += masses[i]
                pickups.remove(i)
            elif no_dust:
                world.collapse_lost += masses[i]
                pickups.remove(i)
            elif phase >= 2 and d2 > r2:
                world.collapse_lost += masses[i]
                pickups.remove(i)

    # 9b. Oleadas de comida: cada FOOD_WAVE_INTERVAL_S cae polvo nuevo, en parte
    #     en los cinturones y en parte repartido dentro de la arena actual. En la
    #     fase 4 ya no queda polvo en el mapa, asi que tampoco se reponen.
    if (
        cfg.FOOD_WAVE_MASS > 0.0
        and t >= world.next_wave_t
        and p < cfg.NO_DUST_FROM_P
    ):
        world.next_wave_t = t + cfg.FOOD_WAVE_INTERVAL_S
        world.waves_done += 1
        pieces = int(round(cfg.FOOD_WAVE_MASS / cfg.DUST_MASS))
        in_belts = int(round(pieces * cfg.FOOD_WAVE_IN_BELTS))
        inner = horizon_h * 1.5
        for k in range(pieces):
            if cfg.FOOD_WAVE_NEAR_HOLE:
                # Comida de riesgo: anillo pegado al horizonte.
                r_min = horizon_h * cfg.FOOD_WAVE_INNER_MULT
                r_max = min(horizon_h * cfg.FOOD_WAVE_OUTER_MULT, arena_r)
            elif k < in_belts:
                r_min, r_max = cfg.BELTS[world_rng.randrange(len(cfg.BELTS))]
                # Si el cinturon ya quedo fuera de la arena, se usa el borde.
                r_max = min(r_max, arena_r)
                r_min = min(r_min, r_max)
            else:
                r_min, r_max = inner, arena_r
            if r_max <= r_min:
                world.collapse_lost += cfg.DUST_MASS
                world.replenished += cfg.DUST_MASS
                continue
            r = _area_uniform_radius(r_min, r_max, world_rng)
            theta = world_rng.uniform(0.0, 2.0 * math.pi)
            world.pickups.add(r * math.cos(theta), r * math.sin(theta), cfg.DUST_MASS, DUST)
            world.replenished += cfg.DUST_MASS

    # 10. Reposicion de polvo en los cinturones.
    rate = ph.replenish_rate(p)
    if rate > 0.0:
        amount = rate * dt
        world.replenished += amount
        world.replenish_debt += amount
        while world.replenish_debt >= cfg.DUST_MASS:
            world.replenish_debt -= cfg.DUST_MASS
            r_min, r_max = cfg.BELTS[world_rng.randrange(len(cfg.BELTS))]
            r = _area_uniform_radius(r_min, r_max, world_rng)
            if r > arena_r:
                # Fuera de la arena no tiene sentido: se pierde.
                world.collapse_lost += cfg.DUST_MASS
                continue
            theta = world_rng.uniform(0.0, 2.0 * math.pi)
            pickups.add(r * math.cos(theta), r * math.sin(theta), cfg.DUST_MASS, DUST)

    world.t = t + dt


# --- Fin de partida -----------------------------------------------------------


def resolve_end(world: WorldState, pre_tick_mass: dict[int, float]) -> bool:
    """Decide si la partida ha acabado y quien gana. Devuelve True si acabo.

    Desempates del diseno: mayor masa en ese tick y, si persiste, quien mas
    tiempo estuvo vivo.
    """
    alive = world.alive_bodies()
    t = world.t
    # P se recalcula con el tiempo ya avanzado: si se usara el P del principio
    # del tick, la partida acabaria por limite duro un tick antes de que el
    # horizonte llegue a la arena, y el cierre por colapso no saltaria nunca.
    world.p = ph.collapse_progress(t, world.deaths)

    if len(alive) == 1:
        world.finished = True
        world.end_reason = "last_standing"
        world.winner_bid = alive[0].bid
        return True

    if len(alive) == 0:
        # Todos cayeron en el mismo tick: gana el de mayor masa al empezar el
        # tick y, si empatan, el que estuvo vivo mas tiempo.
        candidates = [b for b in world.bodies if b.death_time == t] or world.bodies
        winner = max(
            candidates,
            key=lambda b: (pre_tick_mass.get(b.bid, 0.0), b.death_time or 0.0, -b.bid),
        )
        world.finished = True
        world.end_reason = "mutual"
        world.winner_bid = winner.bid
        return True

    # Ya no hay corte a los 5:00: la partida acaba cuando queda uno o cuando el
    # agujero se los lleva. Lo de abajo es solo una red de seguridad de la
    # simulacion, para que un bucle no se quede corriendo para siempre. Si
    # aparece en los resultados, es un sintoma de que algo no cierra.
    if t >= cfg.MATCH_SAFETY_LIMIT_S:
        winner = max(alive, key=lambda b: (b.mass, -b.bid))
        world.finished = True
        world.end_reason = "safety_limit"
        world.winner_bid = winner.bid
        return True

    return False
