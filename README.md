# Cosmos Royale

Juego móvil 2D de acción y supervivencia orbital inspirado en la dinámica de absorción de masa de los juegos tipo .io, adaptado a un formato Battle Royale de sesiones cortas. 

El proyecto sitúa a 20 jugadores en la órbita de un agujero negro supermasivo central. Las partidas duran entre 3 y 5 minutos sin reaparición: el objetivo es crecer absorbiendo masa, maniobrar usando la gravedad del entorno y sobrevivir hasta ser el último cuerpo celeste en pie antes del colapso del sistema.

## Mecánicas clave

- **Física orbital e inercia:** Control basado en empuje vectorial y conservación de momento. No hay fricción artificial en el vacío; los cuerpos orbitan y se ven afectados por pozos gravitatorios activos.
- **Transferencia progresiva de masa (tidal stripping):** El contacto entre entidades no genera muertes instantáneas binarias. La absorción depende de la diferencia relativa de tamaño, permitiendo maniobras de escape a cuerpos de escala similar.
- **Entorno táctico asimétrico:** Elementos diseñados para dar contrajuego a los jugadores pequeños frente a masas mayores:
  - *Cinturones de asteroides:* Proporcionan cobertura y alimento a cuerpos ágiles, mientras aplican arrastre y frenado a los grandes.
  - *Púlsares y cuásares:* Emisiones periódicas que sirven como impulso de escape proporcional a la masa o zonas de daño por radiación.
  - *Asistencia gravitatoria:* Capacidad de trazar trayectorias cerradas alrededor de gigantes para ganar aceleración sin coste.
- **Colapso autorregulado:** La masa de los jugadores destruidos se transfiere al agujero negro central, aumentando su radio de captura y acelerando el ritmo de la partida de forma orgánica.
- **Secuencia final:** El último superviviente activa una fase de cierre donde el sistema colapsa y un chorro relativista lo eyecta al espacio exterior.

## Arquitectura y desarrollo

El proyecto sigue una estrategia de implementación por fases para validar el ciclo de juego antes de introducir infraestructura de red:

1. **Fase offline (actual):** Prototipo funcional en cliente local contra 19 agentes de IA. Implementación de controles táctiles móviles, integración física, balance numérico y shaders de distorsión espacial.
2. **Fase online:** Servidor dedicado autoritativo para la simulación física a 25 Hz, con transporte ligero sobre UDP y serialización binaria de estados.

## Tecnologías

- **Motor de juego:** Godot Engine 4 (GDScript)
- **Backend planificado:** Go (servidor de físicas dedicado)
- **Persistencia y datos:** PostgreSQL
- **Plataformas objetivo:** Android / iOS

## Estructura del repositorio

```text
├── assets/         # Texturas, audio y recursos visuales
├── scenes/         # Escenas de Godot (jugador, mapa, entidades orbitales)
├── scripts/        # Lógica de juego en GDScript (físicas, IA, estados)
├── shaders/        # Shaders de distorsión gravitatoria y efectos visuales
└── docs/           # Documentación de diseño, tablas de balance y notas técnicas
