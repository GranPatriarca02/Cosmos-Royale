"""Invariantes de la fisica. Se corren con: python -m unittest discover sim/tests

Estos tests no comprueban que el balance sea divertido, sino que las reglas no
se contradicen: que nadie gana masa de la nada, que el integrador no destruye
una orbita y que las formulas dan los numeros de Docs/hito0-decisiones.md.
"""

from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as cfg  # noqa: E402
import physics as ph  # noqa: E402


class TestNiveles(unittest.TestCase):
    def test_radio_crece_con_la_masa(self):
        anterior = 0.0
        for mass in (1.0, 8.0, 25.0, 80.0, 250.0, 1000.0):
            r = ph.radius_from_mass(mass)
            self.assertGreater(r, anterior)
            anterior = r

    def test_radios_de_la_tabla_del_documento(self):
        # El radio no ha cambiado: sigue siendo m^0,35.
        self.assertAlmostEqual(ph.radius_from_mass(1.0), 1.0, places=3)
        self.assertAlmostEqual(ph.radius_from_mass(8.0), 2.1, places=1)
        self.assertAlmostEqual(ph.radius_from_mass(25.0), 3.1, places=1)
        self.assertAlmostEqual(ph.radius_from_mass(250.0), 6.9, places=1)

    def test_crecer_no_quita_velocidad_punta(self):
        """La velocidad punta es la misma con cualquier masa."""
        base = ph.vmax_from_mass(1.0)
        for mass in (8.0, 25.0, 80.0, 250.0):
            self.assertAlmostEqual(ph.vmax_from_mass(mass), base, places=6)

    def test_crecer_quita_maniobrabilidad(self):
        """Lo que se pierde al crecer es aceleracion, y con margen."""
        anterior = ph.accel_from_mass(1.0)
        for mass in (8.0, 25.0, 80.0, 250.0):
            actual = ph.accel_from_mass(mass)
            self.assertLess(actual, anterior)
            anterior = actual
        # Un cuerpo de nivel V gira al menos tres veces peor que uno de nivel I.
        self.assertLess(ph.accel_from_mass(250.0) * 3, ph.accel_from_mass(1.0))

    def test_umbrales_de_nivel(self):
        self.assertEqual(ph.level_from_mass(1.0), 1)
        self.assertEqual(ph.level_from_mass(7.9), 1)
        self.assertEqual(ph.level_from_mass(8.0), 2)
        self.assertEqual(ph.level_from_mass(24.9), 2)
        self.assertEqual(ph.level_from_mass(25.0), 3)
        self.assertEqual(ph.level_from_mass(79.9), 3)
        self.assertEqual(ph.level_from_mass(80.0), 4)
        self.assertEqual(ph.level_from_mass(250.0), 5)

    def test_recoleccion_crece_con_el_nivel(self):
        base = ph.collect_radius(25.0, 1)
        self.assertAlmostEqual(ph.collect_radius(25.0, 3) / base, 1.7, places=6)


class TestStripping(unittest.TestCase):
    def test_la_perdida_crece_con_la_diferencia_de_tamano(self):
        """Mas diferencia de masa, mas masa por segundo. Los valores absolutos
        dependen de STRIP_K, que es la palanca del combate; la forma no."""
        anterior = 0.0
        for ratio in (1.15, 1.5, 2.0, 10.0):
            f = ph.strip_fraction_per_s(ratio, 1.0)
            self.assertGreater(f, anterior, f"ratio {ratio}")
            anterior = f

    def test_la_pelea_se_resuelve_en_segundos(self):
        """Con STRIP_K actual, un rival un 50 % mayor te vacia en pocos segundos.
        Es el cambio que llevo el combate del 29 % al 73 % de las muertes."""
        mass = 10.0
        f = ph.strip_fraction_per_s(15.0, mass)
        segundos = 0.0
        while mass >= cfg.MIN_MASS_ALIVE and segundos < 60.0:
            mass -= ph.decay_amount(mass, f, 0.1)
            segundos += 0.1
        self.assertLess(segundos, 10.0, f"tardo {segundos:.1f} s")

    def test_sin_transferencia_por_debajo_del_ratio(self):
        self.assertEqual(ph.strip_fraction_per_s(1.14, 1.0), 0.0)
        self.assertEqual(ph.strip_fraction_per_s(1.0, 1.0), 0.0)
        self.assertEqual(ph.strip_fraction_per_s(0.5, 1.0), 0.0)

    def test_el_ratio_minimo_es_el_limite_exacto(self):
        self.assertEqual(ph.strip_fraction_per_s(cfg.STRIP_MIN_RATIO - 1e-9, 1.0), 0.0)
        self.assertGreater(ph.strip_fraction_per_s(cfg.STRIP_MIN_RATIO, 1.0), 0.0)

    def test_reparto_atacante_mas_polvo_es_todo(self):
        self.assertAlmostEqual(cfg.STRIP_TO_ATTACKER + cfg.STRIP_TO_DUST, 1.0, places=9)


class TestDecaimiento(unittest.TestCase):
    def test_no_depende_del_paso(self):
        """Perder el 40 %/s durante 1 s debe dar lo mismo en 1, 10 o 25 pasos."""
        rate = 0.4
        resultados = []
        for dt in (1.0, 0.1, 0.04):
            mass = 10.0
            pasos = int(round(1.0 / dt))
            for _ in range(pasos):
                mass -= ph.decay_amount(mass, rate, dt)
            resultados.append(mass)
        for valor in resultados[1:]:
            self.assertAlmostEqual(valor, resultados[0], places=9)
        # Y coincide con la solucion analitica.
        self.assertAlmostEqual(resultados[0], 10.0 * math.exp(-rate), places=9)

    def test_nunca_quita_mas_de_lo_que_hay(self):
        # Con tasas enormes la perdida tiende a toda la masa, pero nunca la pasa.
        for rate in (0.07, 1.28, 5.0, 50.0):
            perdida = ph.decay_amount(3.0, rate, 1.0)
            self.assertGreaterEqual(perdida, 0.0)
            self.assertLessEqual(perdida, 3.0)


class TestIntegracion(unittest.TestCase):
    def test_clamp_conserva_la_direccion(self):
        vx, vy = ph.clamp_speed(30.0, 40.0, 5.0)
        self.assertAlmostEqual(math.hypot(vx, vy), 5.0, places=9)
        self.assertAlmostEqual(vx / vy, 30.0 / 40.0, places=9)

    def test_clamp_no_toca_lo_que_esta_por_debajo(self):
        self.assertEqual(ph.clamp_speed(1.0, 2.0, 10.0), (1.0, 2.0))

    def test_gravedad_apunta_al_centro(self):
        ax, ay = ph.gravity_accel(10.0, 0.0, 540.0)
        self.assertLess(ax, 0.0)
        self.assertAlmostEqual(ay, 0.0, places=12)
        # Simetria radial
        ax2, ay2 = ph.gravity_accel(0.0, 10.0, 540.0)
        self.assertAlmostEqual(math.hypot(ax, ay), math.hypot(ax2, ay2), places=12)

    def test_gravedad_finita_en_el_centro(self):
        ax, ay = ph.gravity_accel(0.0, 0.0, 540.0)
        self.assertEqual((ax, ay), (0.0, 0.0))

    def test_orbita_circular_se_mantiene(self):
        """Una orbita circular no debe abrirse ni cerrarse mas de un 2 % en 60 s."""
        gm = ph.gravity_gm(0.0)
        r0 = 55.0
        x, y = r0, 0.0
        speed = ph.circular_orbit_speed(r0, gm)
        vx, vy = 0.0, speed
        dt = 0.1
        radios = [r0]
        for _ in range(int(60.0 / dt)):
            ax, ay = ph.gravity_accel(x, y, gm)
            x, y, vx, vy = ph.integrate_body(x, y, vx, vy, ax, ay, dt, 1e9)
            radios.append(math.hypot(x, y))
        deriva = max(abs(r - r0) for r in radios) / r0
        self.assertLess(deriva, 0.02, f"deriva radial {deriva:.4f}")

    def test_rebote_conserva_el_momento(self):
        m_a, m_b = 3.0, 5.0
        vx_a, vy_a, vx_b, vy_b = 2.0, 0.0, -1.0, 0.5
        p_antes = (m_a * vx_a + m_b * vx_b, m_a * vy_a + m_b * vy_b)
        nvx_a, nvy_a, nvx_b, nvy_b = ph.elastic_bounce(
            0.0, 0.0, vx_a, vy_a, m_a, 1.0, 0.0, vx_b, vy_b, m_b, 0.5
        )
        p_despues = (m_a * nvx_a + m_b * nvx_b, m_a * nvy_a + m_b * nvy_b)
        self.assertAlmostEqual(p_antes[0], p_despues[0], places=9)
        self.assertAlmostEqual(p_antes[1], p_despues[1], places=9)

    def test_rebote_no_actua_si_ya_se_separan(self):
        antes = (1.0, 0.0, 5.0, 0.0)  # B se aleja de A
        despues = ph.elastic_bounce(0.0, 0.0, 1.0, 0.0, 2.0, 1.0, 0.0, 5.0, 0.0, 2.0, 0.5)
        self.assertEqual(antes, despues)


class TestColapso(unittest.TestCase):
    def test_p_empieza_en_cero_y_acaba_en_uno(self):
        self.assertAlmostEqual(ph.collapse_progress(0.0, 0), 0.0, places=9)
        self.assertAlmostEqual(ph.collapse_progress(300.0, 0), 1.0, places=9)
        self.assertAlmostEqual(ph.collapse_progress(300.0, 19), 1.0, places=9)

    def test_p_crece_con_el_tiempo_y_con_las_muertes(self):
        self.assertGreater(ph.collapse_progress(100.0, 5), ph.collapse_progress(100.0, 0))
        self.assertGreater(ph.collapse_progress(150.0, 5), ph.collapse_progress(100.0, 5))

    def test_p_nunca_sale_del_rango(self):
        for t in (0.0, 50.0, 120.0, 299.0, 300.0, 400.0):
            for d in (0, 10, 19):
                p = ph.collapse_progress(t, d)
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_en_p_uno_el_horizonte_se_come_la_arena(self):
        self.assertLessEqual(ph.arena_radius(1.0), ph.horizon_radius(1.0))

    def test_la_arena_se_encoge_y_el_horizonte_crece(self):
        self.assertAlmostEqual(ph.arena_radius(0.0), cfg.ARENA_R0, places=9)
        self.assertAlmostEqual(ph.horizon_radius(0.0), cfg.HORIZON_H0, places=9)
        self.assertLess(ph.arena_radius(1.0), ph.arena_radius(0.0))
        self.assertGreater(ph.horizon_radius(1.0), ph.horizon_radius(0.0))
        # Al final del colapso el horizonte alcanza a la arena: no queda sitio.
        self.assertLessEqual(ph.arena_radius(1.0), ph.horizon_radius(1.0) + 1e-9)

    def test_la_reposicion_se_apaga_en_p_medio(self):
        self.assertAlmostEqual(ph.replenish_rate(0.0), cfg.REPLENISH_RATE, places=9)
        self.assertAlmostEqual(ph.replenish_rate(0.25), cfg.REPLENISH_RATE * 0.5, places=9)
        self.assertEqual(ph.replenish_rate(0.5), 0.0)
        self.assertEqual(ph.replenish_rate(0.9), 0.0)

    def test_la_ayuda_del_entorno_se_agota(self):
        self.assertAlmostEqual(ph.assist_probability(0.0), 0.30, places=9)
        self.assertAlmostEqual(ph.assist_probability(1.0), 0.0, places=9)


class TestCuasares(unittest.TestCase):
    def test_emite_una_vez_por_periodo(self):
        dt = 0.1
        duracion = 60.0
        disparos = sum(
            1
            for i in range(int(duracion / dt))
            if ph.quasar_fires_this_tick(i * dt, dt, 0.0)
        )
        self.assertEqual(disparos, int(duracion / cfg.QUASAR_PERIOD_S))

    def test_el_numero_de_emisiones_no_depende_del_paso(self):
        cuentas = set()
        for dt in (0.1, 0.04, 0.02):
            cuentas.add(sum(
                1
                for i in range(int(120.0 / dt))
                if ph.quasar_fires_this_tick(i * dt, dt, 3.0)
            ))
        self.assertEqual(len(cuentas), 1, f"el paso cambia el numero de emisiones: {cuentas}")
        esperado = int((120.0 - 3.0) / cfg.QUASAR_PERIOD_S) + 1
        self.assertAlmostEqual(cuentas.pop(), esperado, delta=1)

    def test_impulso_inversamente_proporcional_a_la_masa(self):
        pequeno = ph.quasar_impulse_speed(1.0, 1.0)
        grande = ph.quasar_impulse_speed(20.0, 1.0)
        self.assertAlmostEqual(pequeno / grande, 20.0, places=6)
        self.assertGreater(pequeno, ph.vmax_from_mass(1.0))   # al pequeno lo dispara
        self.assertLess(grande, ph.vmax_from_mass(20.0) * 0.5)  # al grande casi nada

    def test_la_ayuda_se_desvanece_con_las_fases(self):
        self.assertAlmostEqual(ph.env_help_fade(0.0), 1.0, places=9)
        self.assertAlmostEqual(ph.env_help_fade(cfg.ENV_FADE_FROM_P), 1.0, places=9)
        self.assertAlmostEqual(ph.env_help_fade(cfg.ENV_FADE_END_P), 0.0, places=9)
        self.assertAlmostEqual(ph.env_help_fade(1.0), 0.0, places=9)
        medio = (cfg.ENV_FADE_FROM_P + cfg.ENV_FADE_END_P) / 2.0
        self.assertAlmostEqual(ph.env_help_fade(medio), 0.5, places=6)
        self.assertEqual(ph.quasar_impulse_speed(1.0, ph.env_help_fade(1.0)), 0.0)


class TestPulsares(unittest.TestCase):
    def test_el_haz_da_una_vuelta_por_periodo(self):
        inicio = ph.pulsar_beam_angle(0.0, 0.0, 1.0)
        vuelta = ph.pulsar_beam_angle(cfg.PULSAR_PERIOD_S, 0.0, 1.0)
        self.assertAlmostEqual((vuelta - inicio) % (2 * math.pi), 0.0, places=9)
        mitad = ph.pulsar_beam_angle(cfg.PULSAR_PERIOD_S / 2.0, 0.0, 1.0)
        self.assertAlmostEqual((mitad - inicio) % (2 * math.pi), math.pi, places=9)

    def test_diferencia_angular_toma_el_camino_corto(self):
        self.assertAlmostEqual(ph.angle_difference(0.1, 6.2), 0.1 - 6.2 + 2 * math.pi, places=9)
        self.assertAlmostEqual(abs(ph.angle_difference(0.0, math.pi)), math.pi, places=9)
        for a, b in ((0.0, 0.3), (3.0, 2.5), (6.0, 0.2)):
            self.assertLessEqual(abs(ph.angle_difference(a, b)), math.pi)

    def test_drenaje_castiga_mas_al_grande(self):
        pequeno = ph.pulsar_drain_rate(1.0)
        grande = ph.pulsar_drain_rate(25.0)
        self.assertGreater(grande, pequeno)
        # Y en masa absoluta la diferencia es mucho mayor todavia.
        self.assertGreater(
            ph.decay_amount(25.0, grande, 1.0), ph.decay_amount(1.0, pequeno, 1.0) * 25
        )

    def test_zonas_del_haz(self):
        # Pulsar en el origen, haz apuntando al eje X positivo.
        dentro = ph.pulsar_zone(10.0, 0.0, 0.0, 0.0, 0.0)
        self.assertEqual(dentro, 1)
        borde_r = cfg.PULSAR_HALF_ANGLE * (1.0 + cfg.PULSAR_EDGE_BAND) / 2.0
        borde = ph.pulsar_zone(
            10.0 * math.cos(borde_r), 10.0 * math.sin(borde_r), 0.0, 0.0, 0.0
        )
        self.assertEqual(borde, 2)
        fuera_angulo = ph.pulsar_zone(0.0, 10.0, 0.0, 0.0, 0.0)
        self.assertEqual(fuera_angulo, 0)
        fuera_alcance = ph.pulsar_zone(cfg.PULSAR_RANGE + 1.0, 0.0, 0.0, 0.0, 0.0)
        self.assertEqual(fuera_alcance, 0)


class TestElementosDelEntorno(unittest.TestCase):
    def test_se_apagan_cuando_el_colapso_los_alcanza(self):
        # Un elemento a r = 45 funciona al principio...
        self.assertTrue(
            ph.element_is_active(45.0, 0.0, ph.arena_radius(0.0), ph.horizon_radius(0.0))
        )
        # ...y deja de funcionar cuando la arena se encoge por debajo de el.
        p_fuera = 1.0
        self.assertLess(ph.arena_radius(p_fuera), 45.0)
        self.assertFalse(
            ph.element_is_active(45.0, 0.0, ph.arena_radius(p_fuera), ph.horizon_radius(p_fuera))
        )

    def test_se_apagan_si_se_los_traga_el_agujero(self):
        self.assertFalse(ph.element_is_active(2.0, 0.0, 100.0, 3.0))


class TestEmpuje(unittest.TestCase):
    def test_empuje_entero_desde_parado(self):
        ax, ay = ph.thrust_vector(1.0, 0.0, 0.0, 0.0, 20.0, 12.0)
        self.assertAlmostEqual(ax, 20.0, places=6)
        self.assertAlmostEqual(ay, 0.0, places=6)

    def test_el_avance_se_desvanece_en_la_velocidad_punta(self):
        vmax = ph.vmax_from_mass(1.0)
        accel = ph.accel_from_mass(1.0)
        # Yendo a tope y queriendo seguir recto: no queda empuje.
        ax, ay = ph.thrust_vector(1.0, 0.0, vmax, 0.0, accel, vmax)
        self.assertAlmostEqual(math.hypot(ax, ay), 0.0, places=6)
        # Pero hasta media velocidad queda casi todo: es lo que hace que el
        # control responda en lugar de sentirse pastoso.
        ax, ay = ph.thrust_vector(1.0, 0.0, vmax * 0.5, 0.0, accel, vmax)
        self.assertGreater(ax, accel * 0.8)
        # Y decae de forma monotona hasta el tope.
        anterior = accel + 1.0
        for frac in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0):
            ax, _ = ph.thrust_vector(1.0, 0.0, vmax * frac, 0.0, accel, vmax)
            self.assertLess(ax, anterior)
            anterior = ax

    def test_girar_y_frenar_siempre_al_cien_por_cien(self):
        # De lado, yendo a tope: empuje entero.
        ax, ay = ph.thrust_vector(0.0, 1.0, 12.0, 0.0, 20.0, 12.0)
        self.assertAlmostEqual(math.hypot(ax, ay), 20.0, places=6)
        # Frenando, incluso por encima de la velocidad punta: empuje entero.
        ax, ay = ph.thrust_vector(-1.0, 0.0, 30.0, 0.0, 20.0, 12.0)
        self.assertAlmostEqual(ax, -20.0, places=6)

    def test_el_terreno_puede_pasar_de_la_velocidad_punta(self):
        """Lo que da el terreno no se recorta: es la clave de las hondas."""
        vx = 25.0
        ax, ay = ph.thrust_vector(1.0, 0.0, vx, 0.0, 20.0, 12.0)
        self.assertEqual((ax, ay), (0.0, 0.0))   # no puede empujar mas
        # pero nadie le quita la velocidad que ya tiene
        self.assertEqual(ph.clamp_speed(vx, 0.0, 12.0 * cfg.SPEED_CEILING_MULT), (vx, 0.0))

    def test_distancia_de_parada(self):
        # v^2 / 2a
        self.assertAlmostEqual(ph.stopping_distance(10.0, 5.0), 10.0, places=6)
        # El grande necesita mucho mas sitio para parar que el pequeno.
        d_pequeno = ph.stopping_distance(10.0, ph.accel_from_mass(1.0))
        d_grande = ph.stopping_distance(10.0, ph.accel_from_mass(100.0))
        self.assertGreater(d_grande, d_pequeno * 3)


class TestBordeElastico(unittest.TestCase):
    def test_crece_con_la_velocidad_de_salida(self):
        suave = ph.edge_pull_accel(1.0, 0.0)
        fuerte = ph.edge_pull_accel(1.0, 16.0)
        self.assertGreater(fuerte, suave * 3.0)

    def test_crece_con_la_profundidad(self):
        self.assertGreater(ph.edge_pull_accel(10.0, 5.0), ph.edge_pull_accel(1.0, 5.0))

    def test_hay_un_tiron_minimo_aunque_salgas_parado(self):
        self.assertGreater(ph.edge_pull_accel(0.0, 0.0), 0.0)

    def test_tiene_techo(self):
        self.assertLessEqual(ph.edge_pull_accel(1e6, 1e6), cfg.EDGE_PULL_MAX)

    def test_no_es_un_trampolin(self):
        """El borde no puede devolver mas energia de la que recibe.

        Si este test se rompe, el borde se ha vuelto una fuente de velocidad
        gratis: dar botes contra el para acelerar sin coste. Se simula un cuerpo
        lanzado hacia fuera sin empuje y sin el pozo central, para aislar el
        borde del resto.
        """
        arena_r = 100.0
        dt = 0.02
        for salida in (4.0, 10.0, 20.0):
            x, y = arena_r, 0.0
            vx, vy = salida, 0.0
            charge = salida
            for _ in range(int(60.0 / dt)):
                r = math.hypot(x, y)
                if r > arena_r:
                    pull = ph.edge_pull_accel(r - arena_r, charge)
                    vx -= pull * x / r * dt
                    vy -= pull * y / r * dt
                x += vx * dt
                y += vy * dt
                if r <= arena_r and vx < 0.0:
                    break
            vuelta = abs(vx)
            self.assertLessEqual(
                vuelta,
                salida * 1.15,
                f"saliendo a {salida} volvio a {vuelta:.2f} u/s",
            )


class TestEstrella(unittest.TestCase):
    def test_orbita_hacia_dentro_con_el_colapso(self):
        self.assertAlmostEqual(ph.star_orbit_radius(0.0), cfg.STAR_ORBIT_R0, places=6)
        self.assertAlmostEqual(ph.star_orbit_radius(1.0), cfg.STAR_ORBIT_R1, places=6)
        self.assertLess(ph.star_orbit_radius(0.7), ph.star_orbit_radius(0.3))

    def test_empieza_fuera_del_anillo_de_aparicion(self):
        """Si naciera encima de los jugadores, la honda los mata en el arranque."""
        self.assertGreater(cfg.STAR_ORBIT_R0, cfg.SPAWN_RING_RADIUS + cfg.STAR_RADIUS * 2)

    def test_da_una_vuelta_por_periodo(self):
        x0, y0 = ph.star_position(0.0, 0.0, 0.0)
        x1, y1 = ph.star_position(cfg.STAR_PERIOD_S, 0.0, 0.0)
        self.assertAlmostEqual(x0, x1, places=6)
        self.assertAlmostEqual(y0, y1, places=6)
        xm, ym = ph.star_position(cfg.STAR_PERIOD_S / 2.0, 0.0, 0.0)
        self.assertAlmostEqual(xm, -x0, places=6)

    def test_su_gravedad_apunta_a_la_estrella(self):
        ax, ay = ph.star_accel(20.0, 0.0, 0.0, 0.0)
        self.assertLess(ax, 0.0)
        self.assertAlmostEqual(ay, 0.0, places=12)

    def test_el_pozo_de_la_estrella_filtra_por_masa(self):
        """La asimetria que justifica la estrella: el pequeno agil entra y sale,
        y a partir de cierta masa ya no puedes. Si este test se rompe al tocar
        ACCEL_COEF, la estrella ha dejado de ser una trampa para los grandes."""
        x = cfg.STAR_RADIUS + 2.0
        g = math.hypot(*ph.star_accel(x, 0.0, 0.0, 0.0))
        self.assertLess(g, ph.accel_from_mass(cfg.START_MASS))
        # Existe una masa atrapada, y esta dentro de la tabla de niveles.
        atrapado = next(
            (m for m in (25.0, 50.0, 80.0, 120.0, 250.0) if ph.accel_from_mass(m) < g),
            None,
        )
        self.assertIsNotNone(atrapado, f"ningun cuerpo queda atrapado (g = {g:.2f})")
        self.assertLessEqual(atrapado, cfg.LEVEL_MIN_MASS[4])


if __name__ == "__main__":
    unittest.main()
