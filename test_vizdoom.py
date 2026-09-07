import vizdoom as vzd
import time

game = vzd.DoomGame()
game.load_config(vzd.scenarios_path + "/basic.cfg")
game.set_window_visible(True)
game.set_mode(vzd.Mode.PLAYER)
game.init()

print("ViZDoom iniciado. Ventana abierta. Moviendo agente...")
print("Acciones: [MOVE_FORWARD, TURN_LEFT, TURN_RIGHT, ATTACK]")

for i in range(200):
    if game.is_episode_finished():
        break

    state = game.get_state()
    if state:
        print(f"Tick {i}: pos={state.game_variables[:3] if len(state.game_variables) >= 3 else 'N/A'}")

    game.make_action([1, 0, 0, 0])  # MOVE_FORWARD
    time.sleep(0.03)

game.close()
print("Test completado.")