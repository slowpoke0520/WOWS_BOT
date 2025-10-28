# actions.py - 点击 / 确认 / 自动导航等动作（都基于客户区坐标转换）
from utils import find_game_window, capture_window, safe_click_in_window, find_template_in_window, log, dbg, save_debug_overlay
import time, config, cv2

def click_with_confirm(click_templates, confirm_templates, max_retry=None, delay_between=None):
    if max_retry is None: max_retry = config.MAX_RETRY
    if delay_between is None: delay_between = config.CLICK_CONFIRM_DELAY

    hwnd = find_game_window()
    if not hwnd:
        log("[ACTION] 找不到游戏窗口，无法点击")
        return False

    bgr, rect = capture_window(hwnd)
    if bgr is None:
        log("[ACTION] 截图失败，无法点击")
        return False
    gray = bgr if len(bgr.shape) == 2 else cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    for attempt in range(1, max_retry+1):
        # refresh screenshot each attempt
        bgr, rect = capture_window(hwnd)
        gray = bgr if len(bgr.shape) == 2 else cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        pos = None
        val = 0.0
        for tpl in click_templates:
            p, v = find_template_in_window(gray, tpl, threshold=None)
            if p:
                pos = p; val = v; break
        if not pos:
            dbg(f"[ACTION] 第{attempt}次：未找到点击模板 {click_templates}")
            time.sleep(delay_between)
            continue
        # click relative to client
        ok = safe_click_in_window(rect, pos)
        if not ok:
            dbg("[ACTION] 点击执行失败")
            time.sleep(delay_between)
            continue
        # wait and verify
        time.sleep(delay_between)
        bgr2, _ = capture_window(hwnd)
        gray2 = bgr2 if len(bgr2.shape) == 2 else cv2.cvtColor(bgr2, cv2.COLOR_BGR2GRAY)
        confirmed = False
        for ctpl in confirm_templates:
            p2, v2 = find_template_in_window(gray2, ctpl, threshold=None)
            if p2:
                confirmed = True; break
        dbg(f"[ACTION] 点击后确认结果: {confirmed}")
        if confirmed:
            return True
        else:
            dbg("[ACTION] 点击后未确认，重试中...")
            time.sleep(0.5)
    log("[ACTION] 点击确认失败，超出重试次数")
    return False

def ensure_auto_nav_enabled():
    # Example: press 'm' to open map and try to click central point if auto nav not detected
    hwnd = find_game_window()
    if not hwnd:
        return False
    bgr, rect = capture_window(hwnd)
    if bgr is None:
        return False
    gray = bgr if len(bgr.shape) == 2 else cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    p_auto, v_auto = find_template_in_window(gray, "auto_nav_icon.png", threshold=None)
    if p_auto and v_auto >= 0.75:
        dbg("[NAV] 自动导航已启用")
        return True
    # otherwise try to open map and click center (simple heuristic)
    import pyautogui
    pyautogui.press("m")
    time.sleep(0.6)
    # click center of client
    cx = rect["width"] // 2
    cy = rect["height"] // 2
    safe_click_in_window(rect, (cx, cy))
    time.sleep(0.2)
    pyautogui.press("m")
    time.sleep(0.6)
    return True
