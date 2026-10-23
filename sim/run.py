"""Punto de entrada de la simulacion del Hito 0.

Ejemplos:
  python sim/run.py                          500 partidas con los valores de config.py
  python sim/run.py --matches 50              una tanda corta
  python sim/run.py --validate                repite con dt = 0,04 y compara
  python sim/run.py --sweep STRIP_K=1.2,1.5,1.8 ARENA_R0=80,100
  python sim/run.py --one 12345               una sola partida, con detalle

Las partidas se reparten entre los nucleos de la maquina con multiprocessing,
que viene en la biblioteca estandar. Cada partida es independiente y su semilla
es SEED_BASE + i, asi que el resultado no depende de cuantos procesos se usen.
"""

from __future__ import annotations

import argparse
import itertools
import multiprocessing as mp
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg  # noqa: E402
import metrics  # noqa: E402
from match import run_match  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def apply_overrides(overrides: dict[str, float]) -> None:
    """Cambia constantes de config.py en caliente (para los barridos)."""
    for name, value in overrides.items():
        if not hasattr(cfg, name):
            raise SystemExit(f"config.py no tiene ninguna constante llamada {name}")
        setattr(cfg, name, value)


def _worker(payload):
    seeds, dt, overrides, sample_seeds = payload
    apply_overrides(overrides)
    agg = metrics.Aggregate()
    for seed in seeds:
        result = run_match(seed, dt=dt, keep_timeline=True)
        agg.add(result, keep_sample=seed in sample_seeds)
    return agg


def run_batch(
    n_matches: int,
    dt: float,
    overrides: dict[str, float] | None = None,
    jobs: int = 0,
    with_samples: bool = True,
) -> metrics.Aggregate:
    """Corre n_matches partidas y devuelve las metricas agregadas."""
    overrides = overrides or {}
    seeds = [cfg.SEED_BASE + i for i in range(n_matches)]
    sample_seeds = (
        set(seeds[: cfg.TIMELINE_SAMPLE_MATCHES]) if with_samples else set()
    )
    if jobs <= 0:
        jobs = min(os.cpu_count() or 1, max(1, n_matches))

    if jobs == 1:
        return _worker((seeds, dt, overrides, sample_seeds))

    chunks: list[list[int]] = [[] for _ in range(jobs)]
    for i, seed in enumerate(seeds):
        chunks[i % jobs].append(seed)
    payloads = [(chunk, dt, overrides, sample_seeds) for chunk in chunks if chunk]

    total = metrics.Aggregate()
    with mp.Pool(len(payloads)) as pool:
        for agg in pool.imap_unordered(_worker, payloads):
            total.merge(agg)
    return total


def _skill_edge(agg: metrics.Aggregate) -> float:
    """Cuantas veces gana un competente mas que un medio, por cuerpo."""
    comp = agg.archetypes.get("competent")
    med = agg.archetypes.get("medium")
    comp_rate = (comp.wins / comp.count) if comp and comp.count else 0.0
    med_rate = (med.wins / med.count) if med and med.count else 0.0
    if med_rate > 0.0:
        return comp_rate / med_rate
    return 99.0 if comp_rate > 0.0 else 0.0


def _score(agg: metrics.Aggregate) -> float:
    """Distancia a los criterios: 0 = los cumple todos. Para ordenar barridos."""
    penalty = 0.0

    lo, hi = cfg.TARGET_DEATHS_BEFORE_120S
    median_deaths = statistics.median(agg.deaths_before_120)
    penalty += max(0.0, lo - median_deaths, median_deaths - hi)

    lo3, hi3 = cfg.TARGET_MEDIAN_LEVEL3_S
    if agg.subject_level3 and len(agg.subject_level3) / agg.matches >= 0.5:
        median_l3 = statistics.median(agg.subject_level3)
        penalty += max(0.0, lo3 - median_l3, median_l3 - hi3) / 10.0
    else:
        penalty += 5.0

    if agg.level3_fraction_120:
        frac = statistics.fmean(agg.level3_fraction_120)
        penalty += max(0.0, frac - cfg.MAX_LEVEL3_FRACTION_AT_120S) / 0.05

    # La habilidad se mide por cuerpo (ver metrics.criteria): la tasa en bruto de
    # victorias de competentes sube sola al meter mas competentes en la sala.
    edge = _skill_edge(agg)
    if edge < cfg.MIN_SKILL_EDGE:
        penalty += (cfg.MIN_SKILL_EDGE - edge) / 0.25
    if cfg.NOVICE_RIVALS > 0:
        nov = agg.winner_archetypes.get("novice", 0) / agg.matches
        penalty += max(0.0, nov - cfg.MAX_NOVICE_WIN_RATE) / 0.01

    end_lo, end_hi = cfg.TARGET_MATCH_END_S
    in_window = sum(1 for e in agg.end_s if end_lo <= e <= end_hi) / agg.matches
    penalty += max(0.0, 0.90 - in_window) / 0.05
    return penalty


def cmd_one(seed: int) -> None:
    """Una sola partida, con el detalle de cada 20 segundos."""
    result = run_match(seed, keep_timeline=True)
    print(f"Partida con semilla {seed}")
    print(f"  fin a los {result.end_s:.1f} s por '{result.end_reason}'")
    print(
        f"  gana bid {result.winner_bid} ({result.winner_archetype})"
        f"{' = el sujeto' if result.winner_is_subject else ''}"
    )
    print(f"  muertes antes de 120 s: {result.deaths_before_120}")
    print(
        f"  sujeto: nivel III a los "
        f"{f'{result.subject_level3_s:.1f} s' if result.subject_level3_s else 'nunca'}"
        f", masa maxima {result.subject_max_mass:.1f}, puesto {result.subject_placement}"
    )
    print(f"  muertes por causa: {result.deaths_by_cause}")
    print(f"  error del libro de masas: {result.ledger_error_max:.2e}")
    print()
    print("     t  vivos      P  arena  horiz  agujero  libre   media  mejor  niv3  sujeto")
    for snapshot in result.timeline:
        if abs(snapshot.t % 20.0) > 1e-6 and snapshot.t != result.timeline[-1].t:
            continue
        print(
            f"  {snapshot.t:4.0f}  {snapshot.alive:5d}  {snapshot.p:5.2f}"
            f"  {snapshot.arena_r:5.1f}  {snapshot.horizon_h:5.1f}"
            f"  {snapshot.hole_mass:7.1f}  {snapshot.free_mass:5.1f}"
            f"  {snapshot.mass_mean:6.1f}  {snapshot.mass_top:5.1f}"
            f"  {snapshot.level3_count:4d}  {snapshot.subject_mass:6.1f}"
        )


def cmd_sweep(specs: list[str], n_matches: int, jobs: int) -> None:
    """Barrido por rejilla sobre 1-3 constantes de config.py."""
    names: list[str] = []
    value_lists: list[list[float]] = []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"formato esperado NOMBRE=v1,v2 (recibido: {spec})")
        name, raw = spec.split("=", 1)
        names.append(name.strip())
        values = []
        for piece in raw.split(","):
            piece = piece.strip()
            values.append(int(piece) if piece.isdigit() else float(piece))
        value_lists.append(values)

    combos = list(itertools.product(*value_lists))
    print(f"Barrido: {len(combos)} configuraciones x {n_matches} partidas")
    print()
    rows = []
    for combo in combos:
        overrides = dict(zip(names, combo))
        t0 = time.time()
        agg = run_batch(n_matches, cfg.DT, overrides, jobs, with_samples=False)
        score = _score(agg)
        median_l3 = statistics.median(agg.subject_level3) if agg.subject_level3 else float("nan")
        row = {
            **{name: value for name, value in overrides.items()},
            "score": round(score, 3),
            "muertes_120_mediana": statistics.median(agg.deaths_before_120),
            "nivel3_mediana_s": round(median_l3, 1),
            "nivel3_llega": round(len(agg.subject_level3) / agg.matches, 3),
            "nivel3_frac_120": round(
                statistics.fmean(agg.level3_fraction_120) if agg.level3_fraction_120 else 0.0, 3
            ),
            "win_competente": round(agg.winner_archetypes.get("competent", 0) / agg.matches, 3),
            "ventaja_habilidad": round(_skill_edge(agg), 2),
            "muertes_combate": round(
                agg.deaths_by_cause.get("stripping", 0) / agg.matches, 2
            ),
            "terreno": round(statistics.fmean(agg.over_vmax), 3),
            "pico_vel": round(statistics.fmean(agg.peak_speed), 2),
            "frac_combate": round(
                agg.deaths_by_cause.get("stripping", 0)
                / max(1, sum(agg.deaths_by_cause.values())), 3
            ),
            "win_novato": round(agg.winner_archetypes.get("novice", 0) / agg.matches, 3),
            "fin_mediana_s": round(statistics.median(agg.end_s), 1),
            "fin_por_eliminacion": round(
                agg.end_reasons.get("last_standing", 0) / agg.matches, 3
            ),
            "masa_media_120": round(
                statistics.fmean(agg.mass_120_mean) if agg.mass_120_mean else 0.0, 1
            ),
        }
        rows.append(row)
        desc = " ".join(f"{k}={v}" for k, v in overrides.items())
        print(
            f"  {desc:<36} score {score:6.2f}"
            f" | muertes120 {row['muertes_120_mediana']:4.1f}"
            f" | nivIII {row['nivel3_mediana_s']:6.1f} s ({row['nivel3_llega']:.0%})"
            f" | winC {row['win_competente']:.0%}"
            f" | habil x{row['ventaja_habilidad']:.1f}"
            f" | combate {row['frac_combate']:4.0%}"
            f" | terreno {row['terreno']:4.0%} pico x{row['pico_vel']:.1f}"
            f" | elim {row['fin_por_eliminacion']:.0%}"
            f" | fin {row['fin_mediana_s']:5.1f} s"
            f" | {time.time() - t0:.0f} s"
        )

    rows.sort(key=lambda r: r["score"])
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "sweep.csv")
    import csv

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print()
    print(f"Mejor configuracion: {rows[0]}")
    print(f"Escrito {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulacion de balance de Cosmos Royale")
    parser.add_argument("--matches", type=int, default=cfg.N_RUNS, help="numero de partidas")
    parser.add_argument("--dt", type=float, default=cfg.DT, help="paso de simulacion (s)")
    parser.add_argument("--jobs", type=int, default=0, help="procesos (0 = todos los nucleos)")
    parser.add_argument("--out", default=OUT_DIR, help="carpeta de los CSV")
    parser.add_argument("--one", type=int, metavar="SEMILLA", help="una sola partida")
    parser.add_argument("--validate", action="store_true", help="repite con dt fino y compara")
    parser.add_argument("--sweep", nargs="+", metavar="NOMBRE=v1,v2", help="barrido por rejilla")
    parser.add_argument("--no-csv", action="store_true", help="no escribir CSV")
    args = parser.parse_args()

    if args.one is not None:
        cmd_one(args.one)
        return

    if args.sweep:
        cmd_sweep(args.sweep, args.matches, args.jobs)
        return

    t0 = time.time()
    agg = run_batch(args.matches, args.dt, None, args.jobs)
    elapsed = time.time() - t0
    print(agg.report())
    print()
    print(f"Simuladas {agg.matches} partidas en {elapsed:.1f} s")

    if not args.no_csv:
        for path in agg.write_csv(args.out):
            print(f"Escrito {path}")

    if args.validate:
        print()
        print(f"VALIDACION con dt = {cfg.DT_VALIDATION} s ({cfg.VALIDATION_RUNS} partidas)")
        coarse = run_batch(cfg.VALIDATION_RUNS, cfg.DT, None, args.jobs, with_samples=False)
        fine = run_batch(cfg.VALIDATION_RUNS, cfg.DT_VALIDATION, None, args.jobs, with_samples=False)
        print(f"  {'metrica':<28} {'dt=' + str(cfg.DT):>10} {'dt=' + str(cfg.DT_VALIDATION):>10}")
        comparisons = [
            ("muertes antes de 120 s", lambda a: statistics.fmean(a.deaths_before_120)),
            ("vivos a 120 s", lambda a: statistics.fmean(a.alive_at_120) if a.alive_at_120 else 0.0),
            ("masa media a 120 s", lambda a: statistics.fmean(a.mass_120_mean) if a.mass_120_mean else 0.0),
            ("nivel III del sujeto (s)", lambda a: statistics.median(a.subject_level3) if a.subject_level3 else float("nan")),
            ("fin de partida (s)", lambda a: statistics.fmean(a.end_s)),
            ("victorias competente", lambda a: a.winner_archetypes.get("competent", 0) / a.matches),
        ]
        for name, fn in comparisons:
            print(f"  {name:<28} {fn(coarse):10.2f} {fn(fine):10.2f}")


if __name__ == "__main__":
    main()
