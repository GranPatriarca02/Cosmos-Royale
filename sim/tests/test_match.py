"""Pruebas de una partida completa. Se corren con: python sim/tests/test_match.py

Son mas lentas que las de physics.py (simulan partidas de verdad), pero cubren
lo que ninguna prueba de una formula puede cubrir: que la masa no se cree ni se
destruya sola, que la misma semilla de el mismo resultado y que la partida
siempre acabe.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as cfg  # noqa: E402
import rules  # noqa: E402
from match import run_match  # noqa: E402


class TestPartida(unittest.TestCase):
    def test_el_libro_de_masas_cuadra(self):
        for seed in (1, 12345, 999):
            result = run_match(seed)
            self.assertLessEqual(
                result.ledger_error_max,
                cfg.LEDGER_TOLERANCE,
                f"semilla {seed}: error {result.ledger_error_max:.2e}",
            )

    def test_la_misma_semilla_da_el_mismo_resultado(self):
        a = run_match(4242)
        b = run_match(4242)
        self.assertEqual(a.end_s, b.end_s)
        self.assertEqual(a.winner_bid, b.winner_bid)
        self.assertEqual(a.deaths_before_120, b.deaths_before_120)
        self.assertEqual(a.subject_max_mass, b.subject_max_mass)
        self.assertEqual(a.bodies, b.bodies)

    def test_semillas_distintas_dan_partidas_distintas(self):
        a = run_match(1)
        b = run_match(2)
        self.assertNotEqual(
            (a.winner_bid, a.subject_max_mass), (b.winner_bid, b.subject_max_mass)
        )

    def test_la_partida_siempre_acaba_y_con_un_ganador(self):
        for seed in range(5):
            result = run_match(seed)
            self.assertGreater(result.end_s, 0.0)
            self.assertLessEqual(result.end_s, cfg.MATCH_HARD_LIMIT_S)
            self.assertGreaterEqual(result.winner_bid, 0)
            self.assertIn(
                result.end_reason, ("last_standing", "collapse", "mutual", "hard_limit")
            )

    def test_la_sala_tiene_la_composicion_pedida(self):
        world = rules.create_world(7)
        self.assertEqual(len(world.bodies), cfg.N_PLAYERS)
        self.assertTrue(world.bodies[0].is_subject)
        self.assertEqual(world.bodies[0].archetype, "competent")
        counts = {}
        for body in world.bodies[1:]:
            counts[body.archetype] = counts.get(body.archetype, 0) + 1
        self.assertEqual(counts.get("novice", 0), cfg.NOVICE_RIVALS)
        self.assertEqual(counts.get("competent", 0), cfg.COMPETENT_RIVALS)
        self.assertEqual(sum(counts.values()), cfg.N_PLAYERS - 1)

    def test_el_mapa_arranca_con_la_masa_libre_del_documento(self):
        world = rules.create_world(7)
        esperado = cfg.DUST_COUNT * cfg.DUST_MASS + cfg.ROCK_COUNT * cfg.ROCK_MASS
        self.assertAlmostEqual(world.pickups.total_mass(), esperado, places=6)
        self.assertAlmostEqual(
            world.initial_mass, cfg.N_PLAYERS * cfg.START_MASS + esperado, places=6
        )

    def test_el_entorno_esta_colocado(self):
        world = rules.create_world(7)
        self.assertEqual(len(world.quasars), cfg.QUASAR_COUNT)
        self.assertEqual(len(world.pulsars), cfg.PULSAR_COUNT)

    def test_nadie_pasa_del_techo_de_seguridad(self):
        """Ya NO hay tope duro en la velocidad punta: el terreno (hondas,
        cuasares, borde del pulsar) puede pasarla, y eso es intencionado. Lo que
        no se puede cruzar es el techo de seguridad numerico."""
        import math

        import physics as ph

        world = rules.create_world(31)
        import bots

        bot_rngs = [bots.make_rng(31, b.bid) for b in world.bodies]
        import random

        world_rng = random.Random(31)
        for _ in range(600):   # 60 s
            rules.tick(world, cfg.DT, bot_rngs, world_rng)
            for b in world.bodies:
                if not b.alive:
                    continue
                speed = math.hypot(b.vx, b.vy)
                techo = ph.vmax_from_mass(b.mass) * cfg.SPEED_CEILING_MULT
                self.assertLessEqual(
                    speed,
                    techo * 1.001,
                    f"bid {b.bid} a {speed:.2f} u/s con masa {b.mass:.2f}",
                )


if __name__ == "__main__":
    unittest.main()
