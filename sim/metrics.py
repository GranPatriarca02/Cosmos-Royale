"""Acumulacion de metricas y evaluacion de los criterios del Hito 0.

Un Aggregate recoge los resultados de muchas partidas y sabe fusionarse con otro
(para poder repartir las partidas entre varios procesos). Al final contesta a
las seis preguntas de Docs/hito0-decisiones.md con un si o un no.
"""

from __future__ import annotations

import csv
import os
import statistics
from dataclasses import dataclass, field

import config as cfg
from match import MatchResult

ARCHETYPES = ("novice", "medium", "competent")


@dataclass
class ArchetypeStats:
    count: int = 0
    wins: int = 0
    placement_sum: int = 0
    alive_sum: float = 0.0
    max_mass_sum: float = 0.0


@dataclass
class Aggregate:
    matches: int = 0
    deaths_before_120: list[int] = field(default_factory=list)
    alive_at_120: list[int] = field(default_factory=list)
    subject_level3: list[float] = field(default_factory=list)   # solo quienes llegan
    subject_level3_misses: int = 0                              # nunca llegan
    level3_fraction_120: list[float] = field(default_factory=list)
    mass_120_mean: list[float] = field(default_factory=list)
    mass_120_median: list[float] = field(default_factory=list)
    mass_120_top: list[float] = field(default_factory=list)
    end_s: list[float] = field(default_factory=list)
    end_reasons: dict[str, int] = field(default_factory=dict)
    winner_archetypes: dict[str, int] = field(default_factory=dict)
    subject_wins: int = 0
    subject_placements: list[int] = field(default_factory=list)
    subject_death_causes: dict[str, int] = field(default_factory=dict)
    deaths_by_cause: dict[str, int] = field(default_factory=dict)
    archetypes: dict[str, ArchetypeStats] = field(default_factory=dict)
    growth_pairs: list[tuple[float, int]] = field(default_factory=list)
    ledger_error_max: float = 0.0
    over_vmax: list[float] = field(default_factory=list)
    peak_speed: list[float] = field(default_factory=list)
    # Acumulador de timeline: segundo -> [n, alive, p, arena_r, hole, free,
    #                                     mass_mean, mass_median, mass_top, level3]
    timeline: dict[int, list[float]] = field(default_factory=dict)
    rows: list[dict] = field(default_factory=list)
    sample_timelines: list[tuple[int, list[tuple]]] = field(default_factory=list)

    # --- Alta de resultados ---------------------------------------------------

    def add(self, result: MatchResult, keep_sample: bool = False) -> None:
        self.matches += 1
        self.deaths_before_120.append(result.deaths_before_120)
        snap = result.snapshot_120
        if snap is not None:
            self.alive_at_120.append(snap.alive)
            self.mass_120_mean.append(snap.mass_mean)
            self.mass_120_median.append(snap.mass_median)
            self.mass_120_top.append(snap.mass_top)
            self.level3_fraction_120.append(
                snap.level3_count / snap.alive if snap.alive else 0.0
            )
        if result.subject_level3_s is None:
            self.subject_level3_misses += 1
        else:
            self.subject_level3.append(result.subject_level3_s)
        self.end_s.append(result.end_s)
        self.end_reasons[result.end_reason] = self.end_reasons.get(result.end_reason, 0) + 1
        self.winner_archetypes[result.winner_archetype] = (
            self.winner_archetypes.get(result.winner_archetype, 0) + 1
        )
        if result.winner_is_subject:
            self.subject_wins += 1
        self.subject_placements.append(result.subject_placement)
        if result.subject_death_cause:
            self.subject_death_causes[result.subject_death_cause] = (
                self.subject_death_causes.get(result.subject_death_cause, 0) + 1
            )
        for cause, n in result.deaths_by_cause.items():
            self.deaths_by_cause[cause] = self.deaths_by_cause.get(cause, 0) + n
        for archetype, max_mass, place, alive_for in result.bodies:
            stats = self.archetypes.setdefault(archetype, ArchetypeStats())
            stats.count += 1
            stats.placement_sum += place
            stats.alive_sum += alive_for
            stats.max_mass_sum += max_mass
            if place == 1:
                stats.wins += 1
            self.growth_pairs.append((max_mass, place))
        self.ledger_error_max = max(self.ledger_error_max, result.ledger_error_max)
        self.over_vmax.append(result.over_vmax_fraction)
        self.peak_speed.append(result.peak_speed_ratio)

        self.rows.append(
            {
                "seed": result.seed,
                "dt": result.dt,
                "end_s": round(result.end_s, 2),
                "end_reason": result.end_reason,
                "winner_bid": result.winner_bid,
                "winner_archetype": result.winner_archetype,
                "winner_is_subject": int(result.winner_is_subject),
                "deaths_before_120": result.deaths_before_120,
                "alive_at_120": snap.alive if snap else 0,
                "mass_mean_120": round(snap.mass_mean, 3) if snap else "",
                "mass_median_120": round(snap.mass_median, 3) if snap else "",
                "mass_top_120": round(snap.mass_top, 3) if snap else "",
                "level3_at_120": snap.level3_count if snap else "",
                "subject_mass_120": round(snap.subject_mass, 3) if snap else "",
                "subject_level3_s": round(result.subject_level3_s, 2)
                if result.subject_level3_s is not None
                else "",
                "subject_max_mass": round(result.subject_max_mass, 3),
                "subject_placement": result.subject_placement,
                "subject_kills": result.subject_kills,
                "subject_death_cause": result.subject_death_cause or "",
                "deaths_stripping": result.deaths_by_cause.get("stripping", 0),
                "deaths_horizon": result.deaths_by_cause.get("horizon", 0),
                "deaths_radiation": result.deaths_by_cause.get("radiation", 0),
                "deaths_collapse": result.deaths_by_cause.get("collapse", 0),
                "ledger_error": f"{result.ledger_error_max:.3e}",
            }
        )

        if result.timeline:
            for snapshot in result.timeline:
                bucket = self.timeline.setdefault(int(round(snapshot.t)), [0.0] * 10)
                bucket[0] += 1
                bucket[1] += snapshot.alive
                bucket[2] += snapshot.p
                bucket[3] += snapshot.arena_r
                bucket[4] += snapshot.hole_mass
                bucket[5] += snapshot.free_mass
                bucket[6] += snapshot.mass_mean
                bucket[7] += snapshot.mass_median
                bucket[8] += snapshot.mass_top
                bucket[9] += snapshot.level3_count
            if keep_sample:
                self.sample_timelines.append(
                    (
                        result.seed,
                        [
                            (
                                round(s.t, 2),
                                s.alive,
                                round(s.p, 4),
                                round(s.arena_r, 2),
                                round(s.horizon_h, 2),
                                round(s.hole_mass, 2),
                                round(s.free_mass, 2),
                                round(s.mass_mean, 2),
                                round(s.mass_median, 2),
                                round(s.mass_top, 2),
                                s.level3_count,
                                round(s.subject_mass, 2),
                            )
                            for s in result.timeline
                        ],
                    )
                )

    def merge(self, other: Aggregate) -> None:
        self.matches += other.matches
        self.deaths_before_120 += other.deaths_before_120
        self.alive_at_120 += other.alive_at_120
        self.subject_level3 += other.subject_level3
        self.subject_level3_misses += other.subject_level3_misses
        self.level3_fraction_120 += other.level3_fraction_120
        self.mass_120_mean += other.mass_120_mean
        self.mass_120_median += other.mass_120_median
        self.mass_120_top += other.mass_120_top
        self.end_s += other.end_s
        self.subject_wins += other.subject_wins
        self.subject_placements += other.subject_placements
        self.growth_pairs += other.growth_pairs
        self.rows += other.rows
        self.over_vmax += other.over_vmax
        self.peak_speed += other.peak_speed
        self.sample_timelines += other.sample_timelines
        self.ledger_error_max = max(self.ledger_error_max, other.ledger_error_max)
        for src, dst in (
            (other.end_reasons, self.end_reasons),
            (other.winner_archetypes, self.winner_archetypes),
            (other.deaths_by_cause, self.deaths_by_cause),
            (other.subject_death_causes, self.subject_death_causes),
        ):
            for key, value in src.items():
                dst[key] = dst.get(key, 0) + value
        for archetype, stats in other.archetypes.items():
            mine = self.archetypes.setdefault(archetype, ArchetypeStats())
            mine.count += stats.count
            mine.wins += stats.wins
            mine.placement_sum += stats.placement_sum
            mine.alive_sum += stats.alive_sum
            mine.max_mass_sum += stats.max_mass_sum
        for second, bucket in other.timeline.items():
            mine_b = self.timeline.setdefault(second, [0.0] * 10)
            for i in range(10):
                mine_b[i] += bucket[i]

    # --- Criterios ------------------------------------------------------------

    def spearman_growth_vs_placement(self) -> float:
        """Correlacion de rangos entre masa maxima y puesto final (invertido).

        Positiva = crecer compensa. Es la pregunta abierta del GDD: si sale
        cerca de cero o negativa, absorber no sirve y el diseno tiene un hueco.
        """
        pairs = self.growth_pairs
        if len(pairs) < 3:
            return 0.0
        n = len(pairs)
        # Puesto invertido: 1 (ganador) pasa a ser el valor mas alto.
        masses = [m for m, _ in pairs]
        places = [-p for _, p in pairs]
        rank_m = _ranks(masses)
        rank_p = _ranks(places)
        mean_m = (n - 1) / 2.0
        num = sum((rank_m[i] - mean_m) * (rank_p[i] - mean_m) for i in range(n))
        den_m = sum((r - mean_m) ** 2 for r in rank_m)
        den_p = sum((r - mean_m) ** 2 for r in rank_p)
        if den_m == 0.0 or den_p == 0.0:
            return 0.0
        return num / (den_m**0.5 * den_p**0.5)

    def criteria(self) -> list[tuple[str, bool, str]]:
        """Los seis criterios del documento: (nombre, cumple, valor medido)."""
        out: list[tuple[str, bool, str]] = []

        lo, hi = cfg.TARGET_DEATHS_BEFORE_120S
        median_deaths = statistics.median(self.deaths_before_120)
        in_band = sum(1 for d in self.deaths_before_120 if lo <= d <= hi) / self.matches
        out.append(
            (
                f"Muertes antes de 120 s en [{lo}, {hi}]",
                lo <= median_deaths <= hi,
                f"mediana {median_deaths:.1f}, media {statistics.fmean(self.deaths_before_120):.1f},"
                f" {in_band:.0%} de partidas en banda",
            )
        )

        lo3, hi3 = cfg.TARGET_MEDIAN_LEVEL3_S
        if self.subject_level3:
            median_l3 = statistics.median(self.subject_level3)
            reach = len(self.subject_level3) / self.matches
            out.append(
                (
                    f"Mediana del sujeto a nivel III en [{lo3:.0f}, {hi3:.0f}] s",
                    lo3 <= median_l3 <= hi3 and reach >= 0.5,
                    f"mediana {median_l3:.1f} s, llega en el {reach:.0%} de partidas",
                )
            )
        else:
            out.append(
                (
                    f"Mediana del sujeto a nivel III en [{lo3:.0f}, {hi3:.0f}] s",
                    False,
                    "el sujeto no llega nunca al nivel III",
                )
            )

        frac = statistics.fmean(self.level3_fraction_120) if self.level3_fraction_120 else 0.0
        out.append(
            (
                f"Nivel III o mas entre los vivos a 120 s <= {cfg.MAX_LEVEL3_FRACTION_AT_120S:.0%}",
                frac <= cfg.MAX_LEVEL3_FRACTION_AT_120S,
                f"{frac:.0%} de los supervivientes",
            )
        )

        # La habilidad se mide por cuerpo, no por arquetipo: si hay 4 competentes
        # de 20, el azar ya les da el 20 % de las victorias, asi que la tasa en
        # bruto sube sola al cambiar la composicion de la sala. Lo que no depende
        # de la mezcla es cuantas veces gana un competente frente a un medio.
        comp = self.archetypes.get("competent")
        med = self.archetypes.get("medium")
        comp_per_body = (comp.wins / comp.count) if comp and comp.count else 0.0
        med_per_body = (med.wins / med.count) if med and med.count else 0.0
        if med_per_body > 0.0:
            edge = comp_per_body / med_per_body
            edge_text = f"x{edge:.1f}"
        else:
            edge = float("inf") if comp_per_body > 0.0 else 0.0
            edge_text = "el medio no gana nunca"
        detail = (
            f"competente gana {comp_per_body:.1%} de sus partidas por cuerpo,"
            f" medio {med_per_body:.1%} -> ventaja {edge_text}"
        )
        if cfg.NOVICE_RIVALS > 0:
            nov_rate = self.winner_archetypes.get("novice", 0) / self.matches
            ok = edge >= cfg.MIN_SKILL_EDGE and nov_rate < cfg.MAX_NOVICE_WIN_RATE
            detail += f", novato {nov_rate:.1%}"
        else:
            ok = edge >= cfg.MIN_SKILL_EDGE
        comp_lo, comp_hi = cfg.TARGET_COMPETENT_WIN_RATE
        comp_rate = self.winner_archetypes.get("competent", 0) / self.matches
        detail += f" | victorias de competentes en bruto {comp_rate:.1%}"
        if not comp_lo <= comp_rate <= comp_hi:
            detail += f" (fuera de tu banda {comp_lo:.0%}-{comp_hi:.0%})"
        out.append(
            (
                f"La habilidad importa: competente gana >= x{cfg.MIN_SKILL_EDGE:.1f}"
                f" que un medio",
                ok,
                detail,
            )
        )

        end_lo, end_hi = cfg.TARGET_MATCH_END_S
        in_window = sum(1 for e in self.end_s if end_lo <= e <= end_hi) / self.matches
        out.append(
            (
                f"La gran mayoria acaba entre {end_lo / 60:.0f}:00 y {end_hi / 60:.0f}:00",
                in_window >= 0.90,
                f"{in_window:.0%} dentro, mediana {statistics.median(self.end_s):.0f} s",
            )
        )

        out.append(
            (
                "El libro de masas cuadra",
                self.ledger_error_max <= cfg.LEDGER_TOLERANCE,
                f"error maximo {self.ledger_error_max:.2e}",
            )
        )
        return out

    # --- Informe --------------------------------------------------------------

    def report(self) -> str:
        lines: list[str] = []
        lines.append(f"Partidas simuladas: {self.matches}  (dt = {cfg.DT} s)")
        lines.append("")
        lines.append("CRITERIOS")
        for name, ok, value in self.criteria():
            lines.append(f"  [{'OK ' if ok else 'NO '}] {name}")
            lines.append(f"         -> {value}")
        lines.append("")

        lines.append("MASA A t = 120 s  (objetivo: media ~15, mediana ~11, mejor 25-40)")
        if self.mass_120_mean:
            lines.append(
                f"  media {statistics.fmean(self.mass_120_mean):.1f}"
                f" | mediana {statistics.fmean(self.mass_120_median):.1f}"
                f" | mejor {statistics.fmean(self.mass_120_top):.1f}"
                f" | vivos {statistics.fmean(self.alive_at_120):.1f}"
            )
        else:
            lines.append("  ninguna partida llega a 120 s")
        lines.append("")

        total_deaths = sum(self.deaths_by_cause.values()) or 1
        lines.append("MUERTES POR CAUSA")
        for cause, n in sorted(self.deaths_by_cause.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {cause:<10} {n / self.matches:5.1f} por partida  ({n / total_deaths:4.0%})")
        lines.append("")

        lines.append("POR ARQUETIPO")
        lines.append("  arquetipo    cuerpos  victorias  puesto medio  vive (s)  masa max media")
        for archetype in ARCHETYPES:
            stats = self.archetypes.get(archetype)
            if not stats or not stats.count:
                continue
            lines.append(
                f"  {archetype:<12} {stats.count:7d}  {stats.wins / self.matches:8.1%}"
                f"  {stats.placement_sum / stats.count:12.1f}"
                f"  {stats.alive_sum / stats.count:8.1f}"
                f"  {stats.max_mass_sum / stats.count:14.1f}"
            )
        lines.append("")

        lines.append("SUJETO MEDIDO (bid 0, competente)")
        lines.append(
            f"  victorias {self.subject_wins / self.matches:.1%} (azar = 5%)"
            f" | puesto medio {statistics.fmean(self.subject_placements):.1f}"
            f" | llega a nivel III en el {len(self.subject_level3) / self.matches:.0%} de partidas"
        )
        if self.subject_death_causes:
            causas = ", ".join(
                f"{c} {n / self.matches:.0%}"
                for c, n in sorted(self.subject_death_causes.items(), key=lambda kv: -kv[1])
            )
            lines.append(f"  muere por: {causas}")
        lines.append("")

        lines.append("USO DEL TERRENO")
        if self.over_vmax:
            lines.append(
                f"  tiempo por encima de la velocidad propia:"
                f" {statistics.fmean(self.over_vmax):.1%}"
                f" | pico medio: x{statistics.fmean(self.peak_speed):.2f} la punta"
            )
        lines.append("")

        lines.append("CRECER COMPENSA?")
        rho = self.spearman_growth_vs_placement()
        veredicto = "si" if rho >= 0.45 else ("flojo" if rho >= 0.25 else "NO")
        lines.append(
            f"  correlacion de rangos masa maxima vs puesto final: {rho:+.2f}  ({veredicto})"
        )
        lines.append("")

        lines.append("FINAL DE PARTIDA")
        for reason, n in sorted(self.end_reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {reason:<14} {n / self.matches:5.1%}")
        return "\n".join(lines)

    # --- CSV ------------------------------------------------------------------

    def write_csv(self, out_dir: str) -> list[str]:
        os.makedirs(out_dir, exist_ok=True)
        written = []

        path = os.path.join(out_dir, "summary.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(self.rows[0].keys()))
            writer.writeheader()
            writer.writerows(sorted(self.rows, key=lambda r: r["seed"]))
        written.append(path)

        path = os.path.join(out_dir, "timeline_agg.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "t", "partidas_vivas", "vivos_medio", "p_medio", "arena_r_medio",
                    "agujero_medio", "masa_libre_media", "masa_media", "masa_mediana",
                    "masa_mejor", "nivel3_medio",
                ]
            )
            for second in sorted(self.timeline):
                b = self.timeline[second]
                n = b[0] or 1
                writer.writerow(
                    [second, int(b[0])] + [round(b[i] / n, 3) for i in range(1, 10)]
                )
        written.append(path)

        if self.sample_timelines:
            path = os.path.join(out_dir, "timeline_sample.csv")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    [
                        "seed", "t", "vivos", "p", "arena_r", "horizonte", "agujero",
                        "masa_libre", "masa_media", "masa_mediana", "masa_mejor",
                        "nivel3", "masa_sujeto",
                    ]
                )
                for seed, rows in sorted(self.sample_timelines):
                    for row in rows:
                        writer.writerow([seed, *row])
            written.append(path)

        return written


def _ranks(values: list[float]) -> list[float]:
    """Rangos con empates promediados (para Spearman)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks
