import cv2, os
import numpy as np
import config
from utils import log, dbg, capture_window, find_game_window

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# -------------------------------
# 新增：带坐标的模板匹配函数
# -------------------------------
def match_template_ex(img, template_name, threshold=0.6):
    """返回 (置信度, 坐标) 或 None"""
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(template_path):
        dbg(f"模板不存在: {template_path}")
        return None

    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        dbg(f"无法读取模板: {template_path}")
        return None

    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        return (max_val, max_loc)
    return None


# -------------------------------
# 状态检测主函数
# -------------------------------
# states.py 中修改 detect_state_once()

def detect_state_once():
    hwnd = find_game_window()
    if hwnd is None:
        return "UNKNOWN", {}

    bgr, rect = capture_window(hwnd)
    if bgr is None:
        dbg("[STATE] capture_window 返回 None，跳过")
        return "UNKNOWN", {}

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    info = {}
    state = "UNKNOWN"

    # -------------------------------
    # ① 检测港口专属按钮 “开始战斗”
    # -------------------------------
    port_btn_res = match_template_ex(gray, "port_join_battle.png", threshold=0.7)
    if port_btn_res:
        v_port, pos_port = port_btn_res
        info["port_join_battle"] = v_port
        if v_port >= 0.7:
            state = "PORT"
            dbg(f"[STATE] 检测到港口按钮 port_join_battle (v={v_port:.2f}) -> 识别为港口")

    # -------------------------------
    # ② 检测 minimap_corner（战斗 / 港口都可能出现）
    # -------------------------------
    minimap_res = match_template_ex(gray, "minimap_corner.png", threshold=0.6)
    if minimap_res:
        v_minimap, (x, y) = minimap_res
        info["minimap"] = v_minimap
        dbg(f"[STATE] minimap_corner 检测: 置信度={v_minimap:.2f}, 坐标=({x},{y})")

        # 仅当尚未判断为港口时，才进一步判断是否为战斗
        if state != "PORT" and v_minimap >= 0.7 and x > 1000 and y > 600:
            state = "BATTLE"
            dbg("[STATE] minimap_corner 出现在右下角 -> 识别为战斗界面")

    # -------------------------------
    # 检测胜利、失败、返回按钮 -> RESULT
    # -------------------------------
    for name in ["victory.png", "defeat.png", "back_to_port.png"]:
        path = os.path.join(TEMPLATE_DIR, name)
        if not os.path.exists(path):
            continue
        template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        info[name.split(".")[0]] = max_val
        if max_val >= 0.8:
            state = "RESULT"

    # -------------------------------
    # 匹配中界面 -> QUEUE
    # -------------------------------
    if state == "UNKNOWN":
        queue_res = match_template_ex(gray, "queue_waiting.png", threshold=0.7)
        if queue_res:
            v_queue, _ = queue_res
            info["queue"] = v_queue
            if v_queue >= 0.7:
                state = "QUEUE"
                dbg("[STATE] 检测到匹配界面 queue_waiting.png -> QUEUE")

    dbg(f"detect_state values: {info}")
    return state, info