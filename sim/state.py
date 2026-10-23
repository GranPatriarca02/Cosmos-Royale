"""Estructuras de datos de la simulacion.

Aqui solo viven los datos, sin reglas: las reglas estan en physics.py y
rules.py. En Java esto serian POJOs; en Go seran structs y se podra traducir
campo a campo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import config as cfg

DUST = 0
ROCK = 1


@dataclass(slots=True)
class Body:
    """Un jugador o bot."""

    bid: int
    archetype: str
    is_subject: bool
    mass: float
    x: float
    y: float
    vx: float
    vy: float
    alive: bool = True
    # Historia y metricas del cuerpo
    max_mass: float = 0.0
    kills: int = 0
    mass_eaten: float = 0.0        # masa absorbida de polvo y rocas
    mass_stolen: float = 0.0       # masa absorbida de otros cuerpos
    level3_time: float | None = None
    death_time: float | None = None
    death_cause: str | None = None
    # Estado temporal
    assist_ready_at: float = 0.0   # cuando vuelve a poder usar el escape asistido
    # Permiso temporal para pasarse de la velocidad maxima. Lo usan el escape
    # asistido, la onda del cuasar y el surf del borde del pulsar.
    boost_until: float = 0.0
    boost_mult: float = 1.0
    quasar_rides: int = 0          # veces que le ha empujado un cuasar
    surf_time: float = 0.0         # segundos surfeando el borde de un haz
    beam_loss: float = 0.0         # masa perdida en haces de pulsar
    # Velocidad radial con la que cruzo el borde hacia fuera. Se registra al
    # cruzar y se borra al volver dentro: es lo que mide el tiron de vuelta.
    edge_charge: float = 0.0
    outside: bool = False
    # Cuanto se ha movido mas rapido de lo que su propio empuje permite. Es la
    # medida directa de si el terreno (hondas, cuasares, borde) se esta usando.
    time_over_vmax: float = 0.0
    alive_time: float = 0.0
    peak_speed_ratio: float = 0.0
    turbo_on: bool = False
    turbo_time: float = 0.0        # segundos con el turbo encendido
    # Masa soltada como polvo que todavia no llega para un trozo entero. Sin esto
    # el turbo crearia un pickup nuevo en cada tick y la rejilla se llenaria de
    # migajas; aqui se acumula y se suelta un trozo de DUST_MASS cuando toca.
    dust_debt: float = 0.0
    desired_x: float = 0.0         # direccion de empuje decidida por el bot
    desired_y: float = 0.0
    next_decision_t: float = 0.0


@dataclass(slots=True)
class Quasar:
    """Emisor ciclico: cada PERIOD_S lanza una onda de choque radial."""

    x: float
    y: float
    phase: float = 0.0    # desfase para que no emitan todos a la vez


@dataclass(slots=True)
class Pulsar:
    """Faro con un haz que gira: drena masa dentro y da velocidad en el borde."""

    x: float
    y: float
    phase: float = 0.0    # angulo inicial del haz
    direction: float = 1.0  # sentido de giro


@dataclass(slots=True)
class Star:
    """Estrella masiva en orbita. Su posicion se calcula cada tick a partir del
    tiempo (va sobre rieles), asi que esto es solo la foto del instante."""

    x: float
    y: float


class PickupGrid:
    """Rejilla uniforme para encontrar polvo cercano sin recorrerlo todo.

    Sin esto habria que comprobar los 20 cuerpos contra los ~560 trozos de polvo
    en cada tick. La rejilla parte el espacio en celdas y solo se mira en las
    celdas que toca el radio de recoleccion. Es la misma idea que un indice en
    SQL: en lugar de un barrido completo, se va directo al cajon que interesa.
    """

    __slots__ = ("cell_size", "cells")

    def __init__(self, cell_size: float) -> None:
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list[int]] = {}

    def key(self, x: float, y: float) -> tuple[int, int]:
        inv = 1.0 / self.cell_size
        return (int(x * inv // 1), int(y * inv // 1))

    def add(self, index: int, x: float, y: float) -> None:
        self.cells.setdefault(self.key(x, y), []).append(index)

    def discard(self, index: int, x: float, y: float) -> None:
        bucket = self.cells.get(self.key(x, y))
        if bucket is not None:
            try:
                bucket.remove(index)
            except ValueError:
                pass

    def candidates(self, x: float, y: float, radius: float) -> list[int]:
        """Indices de los pickups en las celdas que toca el circulo (x, y, radius)."""
        inv = 1.0 / self.cell_size
        cx0 = int((x - radius) * inv // 1)
        cx1 = int((x + radius) * inv // 1)
        cy0 = int((y - radius) * inv // 1)
        cy1 = int((y + radius) * inv // 1)
        out: list[int] = []
        cells = self.cells
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out

    def candidates_expanding(self, x: float, y: float, max_radius: float) -> list[int]:
        """Busca comida cercana en anillos de celdas que se van ensanchando.

        Para decidir a donde va un bot no hace falta mirar todo su radio de
        percepcion: se mira su celda, luego el anillo de alrededor, y se para en
        cuanto encuentra algo (mas un anillo extra, porque el mas cercano puede
        estar justo al otro lado del borde de la celda). Asi el coste no depende
        del tamano del radio de percepcion.
        """
        inv = 1.0 / self.cell_size
        cx = int(x * inv // 1)
        cy = int(y * inv // 1)
        max_ring = int(max_radius * inv) + 1
        cells = self.cells
        out: list[int] = []
        extra_ring = -1
        ring = 0
        while ring <= max_ring:
            if ring == 0:
                bucket = cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
            else:
                for dx in range(-ring, ring + 1):
                    for dy in range(-ring, ring + 1):
                        # Solo el borde del cuadrado: el interior ya se miro.
                        if max(abs(dx), abs(dy)) != ring:
                            continue
                        bucket = cells.get((cx + dx, cy + dy))
                        if bucket:
                            out.extend(bucket)
            if out and extra_ring < 0:
                extra_ring = ring + 1
            if extra_ring >= 0 and ring >= extra_ring:
                break
            ring += 1
        return out


class Pickups:
    """Polvo y rocas, en listas paralelas para que el bucle caliente sea rapido."""

    __slots__ = ("xs", "ys", "masses", "kinds", "alive", "grid", "free_slots", "count_alive")

    def __init__(self, cell_size: float = 8.0) -> None:
        self.xs: list[float] = []
        self.ys: list[float] = []
        self.masses: list[float] = []
        self.kinds: list[int] = []
        self.alive: list[bool] = []
        self.grid = PickupGrid(cell_size)
        self.free_slots: list[int] = []
        self.count_alive = 0

    def add(self, x: float, y: float, mass: float, kind: int) -> int:
        if self.free_slots:
            i = self.free_slots.pop()
            self.xs[i] = x
            self.ys[i] = y
            self.masses[i] = mass
            self.kinds[i] = kind
            self.alive[i] = True
        else:
            i = len(self.xs)
            self.xs.append(x)
            self.ys.append(y)
            self.masses.append(mass)
            self.kinds.append(kind)
            self.alive.append(True)
        self.grid.add(i, x, y)
        self.count_alive += 1
        return i

    def remove(self, index: int) -> None:
        if not self.alive[index]:
            return
        self.grid.discard(index, self.xs[index], self.ys[index])
        self.alive[index] = False
        self.masses[index] = 0.0
        self.free_slots.append(index)
        self.count_alive -= 1

    def total_mass(self) -> float:
        return sum(m for m, a in zip(self.masses, self.alive) if a)


@dataclass
class WorldState:
    """Estado completo de una partida en un instante."""

    t: float = 0.0
    bodies: list[Body] = field(default_factory=list)
    pickups: Pickups = field(default_factory=Pickups)
    quasars: list[Quasar] = field(default_factory=list)
    pulsars: list[Pulsar] = field(default_factory=list)
    star: "Star | None" = None
    star_phase: float = 0.0
    next_wave_t: float = 0.0          # proxima oleada de comida
    waves_done: int = 0
    deaths: int = 0
    hole_mass: float = 0.0            # masa tragada por el agujero central
    radiation_lost: float = 0.0       # masa destruida por la zona de radiacion
    beam_lost: float = 0.0            # masa destruida por los haces de pulsar
    mass_created: float = 0.0         # masa creada por el bonus de devorar jugadores
    collapse_lost: float = 0.0        # polvo borrado por el colapso de las fases
    replenished: float = 0.0          # masa de polvo repuesta desde el inicio
    initial_mass: float = 0.0         # masa total al empezar (cuerpos + libre)
    p: float = 0.0                    # progreso del colapso
    replenish_debt: float = 0.0       # masa de reposicion pendiente de soltar
    next_cleanup_t: float = 0.0       # proximo barrido de polvo fuera de la arena
    finished: bool = False
    end_reason: str = ""
    winner_bid: int | None = None
    # Pares (bid_menor, bid_mayor) que ya estaban en contacto en el tick anterior,
    # para saber cuando un stripping "empieza" y tirar el dado del escape asistido.
    contacts: set[tuple[int, int]] = field(default_factory=set)

    def alive_bodies(self) -> list[Body]:
        return [b for b in self.bodies if b.alive]

    def ledger_error(self) -> float:
        """Cuanta masa no cuadra: debe ser practicamente cero en todo momento.

        masa en cuerpos + masa libre + agujero + radiacion + haces + colapso
        debe igualar  masa inicial + repuesta + creada por el bonus de devorar.
        """
        in_bodies = sum(b.mass for b in self.bodies if b.alive)
        pending = sum(b.dust_debt for b in self.bodies) + self.replenish_debt
        total = (
            in_bodies
            + self.pickups.total_mass()
            + self.hole_mass
            + self.radiation_lost
            + self.beam_lost
            + self.collapse_lost
            + pending
        )
        expected = self.initial_mass + self.replenished + self.mass_created
        return abs(total - expected)


def level_targets() -> tuple[float, ...]:
    """Umbral de masa de cada nivel, por comodidad."""
    return cfg.LEVEL_MIN_MASS
