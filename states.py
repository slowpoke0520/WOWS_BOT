# states.py - 状态识别（使用 utils）
from utils import find_game_window, capture_window, get_client_rect, find_template_in_window, save_debug_overlay, log, dbg
import utils, config

# 固定要检测的模板文件名（与上面模板清单一致）
TEMPLATE_PORT = "port_join_battle.png"
TEMPLATE_PORT_DISABLED = "port_join_battle_disabled.png"
TEMPLATE_QUEUE = "queue_waiting.png"
TEMPLATE_SCORE = "battle_score_bar.png"
TEMPLATE_MINIMAP = "minimap_corner.png"
TEMPLATE_AUTO_NAV = "auto_nav_icon.png"
TEMPLATE_VICTORY = "result_victory.png"
TEMPLATE_DEFEAT = "result_defeat.png"
TEMPLATE_BACK = "back_to_port.png"

def detect_state_once():
    hwnd = find_game_window()
    if not hwnd:
        return "UNKNOWN", {"reason":"no_window"}
    img_rect = capture_window(hwnd)
    if img_rect is None or img_rect[0] is None:
        return "UNKNOWN", {"reason":"capture_failed"}
    bgr, rect = img_rect
    gray = utils.to_gray(bgr)

    matches = []
    # detect each template, store values
    pos_port, v_port = find_template_in_window(gray, TEMPLATE_PORT, threshold=0.75)
    pos_port_disabled, v_port_dis = find_template_in_window(gray, TEMPLATE_PORT_DISABLED, threshold=0.75)
    pos_queue, v_queue = find_template_in_window(gray, TEMPLATE_QUEUE, threshold=0.7)
    pos_score, v_score = find_template_in_window(gray, TEMPLATE_SCORE, threshold=0.6)
    pos_minimap, v_minimap = find_template_in_window(gray, TEMPLATE_MINIMAP, threshold=0.6)
    pos_auto, v_auto = find_template_in_window(gray, TEMPLATE_AUTO_NAV, threshold=0.75)
    pos_vict, v_vict = find_template_in_window(gray, TEMPLATE_VICTORY, threshold=0.8)
    pos_defeat, v_defeat = find_template_in_window(gray, TEMPLATE_DEFEAT, threshold=0.8)
    pos_back, v_back = find_template_in_window(gray, TEMPLATE_BACK, threshold=0.7)

    info = {
        "port": v_port, "port_disabled": v_port_dis, "queue": v_queue,
        "score": v_score, "minimap": v_minimap, "auto_nav": v_auto,
        "victory": v_vict, "defeat": v_defeat, "back": v_back
    }

    # log the values compactly
    dbg(f"detect_state values: {info}")

    # Decision rules (priority order)
    if v_vict >= 0.8 or v_defeat >= 0.8:
        return "RESULT", info
    # If score bar exists AND minimap exists -> battle
    if v_score >= 0.55 and v_minimap >= 0.45:
        return "BATTLE", info
    # auto nav alone is strong indicator
    if v_auto >= 0.75:
        return "BATTLE", info
    # queue detection
    if v_queue >= 0.7:
        return "QUEUE", info
    # port (join click) - if enabled (not disabled)
    if v_port >= 0.75:
        return "PORT", info
    # if only disabled button found, treat as PORT (but disabled)
    if v_port_dis >= 0.75:
        return "PORT_DISABLED", info
    # fallback: not recognized
    return "UNKNOWN", info
