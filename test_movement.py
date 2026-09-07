import vizdoom as vzd
import time
import os

game = vzd.DoomGame()
config_path = os.path.join(os.path.dirname(__file__), "scenarios", "limpieza_angulos.cfg")
game.load_config(config_path)
game.set_window_visible(True)
game.set_mode(vzd.Mode.PLAYER)
game.init()

print("ViZDoom iniciado con config custom.")
print(f"Actions: {game.get_available_buttons()}")
print(f"Game variables: {game.get_available_game_variables()}")

actions = {
    "forward":     [1, 0, 0, 0, 0, 0, 0, 0],
    "backward":    [0, 1, 0, 0, 0, 0, 0, 0],
    "left":        [0, 0, 1, 0, 0, 0, 0, 0],
    "right":       [0, 0, 0, 1, 0, 0, 0, 0],
    "turn_left":   [0, 0, 0, 0, 1, 0, 0, 0],
    "turn_right":  [0, 0, 0, 0, 0, 1, 0, 0],
    "attack":      [0, 0, 0, 0, 0, 0, 1, 0],
    "use":         [0, 0, 0, 0, 0, 0, 0, 1],
}

sequence = ["forward"] * 50 + ["turn_right"] * 20 + ["forward"] * 50 + ["turn_left"] * 20 + ["left"] * 30

for i, act_name in enumerate(sequence):
    if game.is_episode_finished():
        break

    state = game.get_state()
    if state:
        vars = state.game_variables
        pos_str = f"pos=({vars[0]:.1f}, {vars[1]:.1f}, {vars[2]:.1f}) angle={vars[3]:.1f}" if len(vars) >= 4 else f"vars={vars}"
        print(f"Tick {i}: {act_name:12s} | {pos_str} | health={vars[4] if len(vars)>4 else '?'} | ammo={vars[5] if len(vars)>5 else '?'}")

    game.make_action(actions[act_name])
    time.sleep(0.03)

game.close()
print("Test completado.")