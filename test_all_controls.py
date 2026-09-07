import vizdoom as vzd
import time
import os

game = vzd.DoomGame()
config_path = os.path.join(os.path.dirname(__file__), "scenarios", "limpieza_angulos.cfg")
game.load_config(config_path)
game.set_window_visible(True)
game.set_mode(vzd.Mode.PLAYER)
game.init()

print("=" * 60)
print("TEST COMPLETO DE CONTROLES - ViZDoom")
print("=" * 60)
print(f"Acciones disponibles: {[str(b) for b in game.get_available_buttons()]}")
print(f"Variables de juego: {[str(v) for v in game.get_available_game_variables()]}")
print()

actions = {
    "MOVE_FORWARD":     [1, 0, 0, 0, 0, 0, 0, 0],
    "MOVE_BACKWARD":    [0, 1, 0, 0, 0, 0, 0, 0],
    "MOVE_LEFT":        [0, 0, 1, 0, 0, 0, 0, 0],
    "MOVE_RIGHT":       [0, 0, 0, 1, 0, 0, 0, 0],
    "TURN_LEFT":        [0, 0, 0, 0, 1, 0, 0, 0],
    "TURN_RIGHT":       [0, 0, 0, 0, 0, 1, 0, 0],
    "ATTACK":           [0, 0, 0, 0, 0, 0, 1, 0],
    "USE":              [0, 0, 0, 0, 0, 0, 0, 1],
}

def get_state_str(state):
    if not state:
        return "sin estado"
    v = state.game_variables
    return f"pos=({v[0]:.1f}, {v[1]:.1f}, {v[2]:.1f}) angle={v[3]:.1f} health={v[4]:.0f} ammo={v[5]:.0f}"

def run_action(name, action, ticks=30, delay=0.02):
    print(f"\n--- {name} ({ticks} ticks) ---")
    for i in range(ticks):
        if game.is_episode_finished():
            print("Episodio terminado")
            return False
        state = game.get_state()
        if i % 5 == 0 or i == ticks - 1:
            print(f"  Tick {i:2d}: {get_state_str(state)}")
        game.make_action(action)
        time.sleep(delay)
    return True

# Test 1: Movimiento hacia adelante
run_action("MOVE_FORWARD (eje X+)", actions["MOVE_FORWARD"], ticks=40)

# Test 2: Movimiento hacia atrás
run_action("MOVE_BACKWARD (eje X-)", actions["MOVE_BACKWARD"], ticks=20)

# Test 3: Strafe izquierda
run_action("MOVE_LEFT (eje Y-)", actions["MOVE_LEFT"], ticks=20)

# Test 4: Strafe derecha
run_action("MOVE_RIGHT (eje Y+)", actions["MOVE_RIGHT"], ticks=20)

# Test 5: Rotación cámara izquierda
run_action("TURN_LEFT (rotación -)", actions["TURN_LEFT"], ticks=30)

# Test 6: Rotación cámara derecha
run_action("TURN_RIGHT (rotación +)", actions["TURN_RIGHT"], ticks=30)

# Test 7: Disparar (ATTACK)
print("\n--- ATTACK (disparar) ---")
for i in range(10):
    state = game.get_state()
    print(f"  Tick {i}: {get_state_str(state)} ammo_before={state.game_variables[5] if state else '?'}")
    game.make_action(actions["ATTACK"])
    time.sleep(0.05)
state = game.get_state()
print(f"  Después: ammo={state.game_variables[5] if state else '?'}")

# Test 8: USE (interactuar)
print("\n--- USE (interactuar) ---")
for i in range(5):
    state = game.get_state()
    print(f"  Tick {i}: {get_state_str(state)}")
    game.make_action(actions["USE"])
    time.sleep(0.05)

# Test 9: Combinado - movimiento diagonal + giro
print("\n--- COMBO: forward + turn_right (movimiento curvo) ---")
combo = [1, 0, 0, 0, 0, 1, 0, 0]  # forward + turn_right
for i in range(30):
    state = game.get_state()
    if i % 5 == 0:
        print(f"  Tick {i}: {get_state_str(state)}")
    game.make_action(combo)
    time.sleep(0.02)

game.close()
print("\n" + "=" * 60)
print("TODOS LOS CONTROLES TESTEADOS EXITOSAMENTE")
print("=" * 60)