# actions.py - 点击 / 确认 / 自动导航等动作（多模板占点识别版）
from utils import (
    find_game_window, capture_window, safe_click_in_window,
    find_template_in_window, log, dbg, save_debug_overlay
)
import time, config, cv2, os, pyautogui

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

    for attempt in range(1, max_retry + 1):
        bgr, rect = capture_window(hwnd)
        if bgr is None:
            time.sleep(delay_between)
            continue
        gray = bgr if len(bgr.shape) == 2 else cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        pos = None

        for tpl in click_templates:
            p, v = find_template_in_window(gray, tpl, threshold=None)
            if p:
                pos = p
                dbg(f"[ACTION] 找到点击模板 {tpl} (v={v:.2f})")
                break

        if not pos:
            dbg(f"[ACTION] 第{attempt}次未找到任何模板，等待重试")
            time.sleep(delay_between)
            continue

        ok = safe_click_in_window(rect, pos)
        if not ok:
            dbg("[ACTION] 点击失败，重试中...")
            time.sleep(delay_between)
            continue

        time.sleep(delay_between)
        bgr2, _ = capture_window(hwnd)
        if bgr2 is None:
            continue
        gray2 = bgr2 if len(bgr2.shape) == 2 else cv2.cvtColor(bgr2, cv2.COLOR_BGR2GRAY)

        confirmed = False
        for ctpl in confirm_templates:
            p2, v2 = find_template_in_window(gray2, ctpl, threshold=None)
            if p2:
                confirmed = True
                dbg(f"[ACTION] 点击后检测到确认模板 {ctpl} (v={v2:.2f})")
                break

        if confirmed:
            return True

    log("[ACTION] 点击确认失败，超过重试次数")
    return False

#<<<<<<< Updated upstream
# -----------------------------------------------------
# 自动导航增强版：多模板检测中立 & 敌方占领点
# -----------------------------------------------------
def ensure_auto_nav_enabled(screenshot=None):
    """
    确保战斗中启用了自动导航：
    - 若已启用自动导航，则不再重复打开地图
    - 启用成功后自动关闭地图
    """
    import time
    import keyboard
    from utils import dbg, log, find_game_window, capture_window, to_gray, find_template_in_window, safe_click_screen_abs
    import config

    hwnd = find_game_window()
    if hwnd is None:
        log("[NAV] 未找到游戏窗口，无法导航")
        return False

    # 1️⃣ 获取截图（若主循环传入则复用）
    if screenshot is not None:
        gray = to_gray(screenshot)
    else:
        gray = to_gray(capture_window(hwnd)[0])

    # 2️⃣ 检测自动导航图标是否已启用
    p_auto, v_auto = find_template_in_window(gray, "auto_nav_icon.png", threshold=0.6)
    if p_auto and v_auto >= 0.85:
        dbg(f"[NAV] 自动导航已启用 (v={v_auto:.2f}) -> 不再重复操作")
        keyboard.send("m")  # ✅ 自动关闭地图
        time.sleep(0.3)
        return True

    # 3️⃣ 检测地图是否打开
    p_map, v_map = find_template_in_window(gray, "map_open_indicator.png", threshold=0.4)
    dbg(f"[NAV] 地图界面检测: {bool(p_map)} (v={v_map:.2f} if detected)")

    if not p_map:
        dbg("[NAV] 导航未启用且地图未开，按 M 打开地图 (第 1 次)")
        keyboard.send("m")
        time.sleep(1.2)
        gray = to_gray(capture_window(hwnd)[0])

    # 4️⃣ 搜索目标占领点（中立 + 敌方）
    # 4️⃣ 搜索目标占领点（中立 + 敌方）
    candidates = []
    cap_templates = [
        "cap_enemy.png", "cap_enemy_1.png", "cap_enemy_2.png", "cap_enemy_3.png",
        "cap_neutral.png", "cap_neutral_1.png", "cap_neutral_2.png", "cap_neutral_3.png"
    ]

    import os
    from utils import save_debug_overlay

    dbg("[NAV] 开始检测占领点模板...")

    for tpl in cap_templates:
        path = os.path.join(config.TEMPLATE_DIR, tpl)
        dbg(f"[NAV] 尝试加载模板 {tpl}: {os.path.exists(path)}")
        p, v = find_template_in_window(gray, tpl, threshold=0.6)
        dbg(f"[NAV] 模板 {tpl} 匹配结果: p={p}, v={v:.2f}")
        if p and v >= 0.6:
            dbg(f"[NAV] 检测到目标 {tpl} (v={v:.2f}) 坐标 {p}")
            candidates.append((tpl, v, p))
    # 🚫 过滤掉屏幕上方 UI 的误检点（例如战斗界面上方的 cap 图标）
    before_filter = len(candidates)
    candidates = [(tpl, v, p) for tpl, v, p in candidates if p[1] > 100]

    if len(candidates) < before_filter:
        dbg(f"[NAV] 过滤掉 {before_filter - len(candidates)} 个靠上方的误检点 (y < 100)")

    if not candidates:
        dbg("[NAV] 未检测到可导航的目标点")
        # 保存当前地图截图方便调试
        try:
            save_debug_overlay(gray, {"left": 0, "top": 0}, [])
        except Exception as e:
            dbg(f"[NAV] 保存调试截图失败: {e}")
        return False

    if not candidates:
        dbg("[NAV] 未检测到可导航的目标点")
        return False

    # 5️⃣ 连续 Shift 点击多个导航点
    import pyautogui

    # 按置信度从高到低排序，最多选取 3 个目标点
    candidates.sort(key=lambda x: x[1], reverse=True)
    selected_points = [c[2] for c in candidates[:3]]

    dbg(f"[NAV] 检测到 {len(selected_points)} 个导航点，将按住 Shift 连续点击: {selected_points}")

    # 按住 Shift
    pyautogui.keyDown('shift')
    time.sleep(0.15)

    # 逐个点击目标点
    for i, (x, y) in enumerate(selected_points, start=1):
        dbg(f"[NAV] Shift点击第 {i} 个点: ({x + 11}, {y + 45})")
        safe_click_screen_abs(x + 11, y + 45)
        time.sleep(0.35)  # 避免点击过快漏点

    # 松开 Shift
    pyautogui.keyUp('shift')
    dbg("[NAV] 释放 Shift，完成多点路径导航")
    time.sleep(1.0)

    # 6️⃣ 再次检测导航是否启用
    gray = to_gray(capture_window(hwnd)[0])
    p_auto2, v_auto2 = find_template_in_window(gray, "auto_nav_icon.png", threshold=0.8)
    if p_auto2 and v_auto2 >= 0.8:
        dbg(f"[NAV] 导航已成功启用 (v={v_auto2:.2f}) -> 关闭地图")
        keyboard.send("m")  # ✅ 导航成功后自动关闭地图
        time.sleep(0.3)
        return True
    else:
        dbg(f"[NAV] 尝试点击后仍未检测到导航图标 (v={v_auto2:.2f})")
        return False
