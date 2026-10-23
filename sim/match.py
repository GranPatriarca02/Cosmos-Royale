"""Bucle de una partida: ticks de dt fijo hasta que queda uno o colapsa todo.

El bucle de paso fijo es el patron de cualquier servidor de juego: en lugar de
reaccionar a eventos, se avanza el mundo en trozos iguales de tiempo. En Java
seria un while con `tick(); sleep(40ms)`; aqui no hay sleep porque se simula lo
mas rapido posible, y dt es el mismo numero que usara el servidor en Go.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field

import bots
import config as cfg
import physics as ph
import rules
from state import WorldState


@dataclass
class Snapshot:
    """Foto del estado en un instante, para el timeline y para t = 120 s."""

    t: float
    alive: int
    p: float
    arena_r: float
    horizon_h: float
    hole_mass: float
    free_mass: float
    mass_mean: float
    mass_median: float
    mass_top: float
    level3_count: int
    subject_mass: float
    subject_alive: bool


@dataclass
class MatchResult:
    seed: int
    dt: float
    end_s: float = 0.0
    end_reason: str = ""
    winner_bid: int = -1
    winner_archetype: str = ""
    winner_is_subject: bool = False
    deaths_before_120: int = 0
    snapshot_120: Snapshot | None = None
    subject_level3_s: float | None = None
    subject_max_mass: float = 0.0
    subject_placement: int = 0
    subject_death_cause: str | None = None
    subject_kills: int = 0
    deaths_by_cause: dict[str, int] = field(default_factory=dict)
    ledger_error_max: float = 0.0
    over_vmax_fraction: float = 0.0   # tiempo movidose mas rapido de lo propio
    peak_speed_ratio: float = 0.0     # pico de velocidad / velocidad punta
    mass_closing_error: float = 0.0
    # (arquetipo, masa maxima, puesto final, tiempo vivo) de los 20 cuerpos
    bodies: list[tuple[str, float, int, float]] = field(default_factory=list)
    timeline: list[Snapshot] = field(default_factory=list)


def _snapshot(world: WorldState) -> Snapshot:
    alive = world.alive_bodies()
    masses = [b.mass for b in alive]
    subject = world.bodies[0]
    return Snapshot(
        t=world.t,
        alive=len(alive),
        p=world.p,
        arena_r=ph.arena_radius(world.p),
        horizon_h=ph.horizon_radius(world.p),
        hole_mass=world.hole_mass,
        free_mass=world.pickups.total_mass(),
        mass_mean=statistics.fmean(masses) if masses else 0.0,
        mass_median=statistics.median(masses) if masses else 0.0,
        mass_top=max(masses) if masses else 0.0,
        level3_count=sum(1 for m in masses if m >= cfg.LEVEL_MIN_MASS[2]),
        subject_mass=subject.mass,
        subject_alive=subject.alive,
    )


def _placements(world: WorldState) -> dict[int, int]:
    """Puesto final: 1 para el ganador, 20 para el primero en morir."""
    order = sorted(
        world.bodies,
        key=lambda b: (
            0 if b.bid == world.winner_bid else 1,
            -(b.death_time if b.death_time is not None else math.inf),
            b.bid,
        ),
    )
    return {b.bid: i + 1 for i, b in enumerate(order)}


def run_match(
    seed: int, dt: float = cfg.DT, keep_timeline: bool = False, check_ledger: bool = True
) -> MatchResult:
    """Corre una partida completa y devuelve sus metricas."""
    world = rules.create_world(seed)
    bot_rngs = [bots.make_rng(seed, b.bid) for b in world.bodies]
    world_rng = random.Random(seed * 7_919 + 13)
    result = MatchResult(seed=seed, dt=dt)

    next_sample = 0.0
    ledger_check_at = 0.0
    snapshot_120_taken = False

    if keep_timeline:
        world.p = ph.collapse_progress(0.0, 0)
        result.timeline.append(_snapshot(world))
        next_sample = cfg.SAMPLE_INTERVAL_S

    while not world.finished:
        pre_tick_mass = {b.bid: b.mass for b in world.bodies if b.alive}
        rules.tick(world, dt, bot_rngs, world_rng)
        rules.resolve_end(world, pre_tick_mass)

        t = world.t
        # Foto de t = 120 s, que es donde viven dos de los criterios de exito.
        if not snapshot_120_taken and t >= cfg.P_HARD_START_S:
            snapshot_120_taken = True
            result.snapshot_120 = _snapshot(world)
            result.deaths_before_120 = world.deaths
        if keep_timeline and t >= next_sample:
            result.timeline.append(_snapshot(world))
            next_sample += cfg.SAMPLE_INTERVAL_S
        if check_ledger and t >= ledger_check_at:
            ledger_check_at = t + 5.0
            error = world.ledger_error()
            if error > result.ledger_error_max:
                result.ledger_error_max = error

    result.end_s = world.t
    result.end_reason = world.end_reason
    result.winner_bid = world.winner_bid if world.winner_bid is not None else -1
    winner = world.bodies[result.winner_bid]
    result.winner_archetype = winner.archetype
    result.winner_is_subject = winner.is_subject
    result.mass_closing_error = world.ledger_error()
    if result.mass_closing_error > result.ledger_error_max:
        result.ledger_error_max = result.mass_closing_error

    if result.snapshot_120 is None:
        # La partida acabo antes del minuto 2.
        result.deaths_before_120 = world.deaths

    total_alive = sum(b.alive_time for b in world.bodies) or 1.0
    result.over_vmax_fraction = sum(b.time_over_vmax for b in world.bodies) / total_alive
    result.peak_speed_ratio = max(b.peak_speed_ratio for b in world.bodies)

    places = _placements(world)
    subject = world.bodies[0]
    result.subject_level3_s = subject.level3_time
    result.subject_max_mass = subject.max_mass
    result.subject_placement = places[0]
    result.subject_death_cause = subject.death_cause
    result.subject_kills = subject.kills

    for b in world.bodies:
        if b.death_cause:
            result.deaths_by_cause[b.death_cause] = (
                result.deaths_by_cause.get(b.death_cause, 0) + 1
            )
        alive_for = b.death_time if b.death_time is not None else world.t
        result.bodies.append((b.archetype, b.max_mass, places[b.bid], alive_for))

    return result
