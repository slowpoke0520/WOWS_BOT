# utils.py - 日志、截图、模板匹配、多尺度支持、文件工具
import os
import time
import cv2
import numpy as np
import pyautogui
from datetime import datetime
from typing import Optional, Dict  # 修复 Optional/Dict 未定义问题
import config

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(ROOT, config.TEMPLATE_DIR)
LOG_DIR = os.path.join(ROOT, config.LOG_DIR)

os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(s):
    line = f"[{ts()}] {s}"
    print(line)
    try:
        with open(os.path.join(LOG_DIR, f"run_{datetime.now().date()}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def dbg(s):
    if config.DEBUG:
        log("[DEBUG] " + s)

# ------------------------
# 窗口 / 截图
# ------------------------
import win32gui, win32con

def find_game_window(title=None):
    if title is None:
        title = config.GAME_TITLE
    hwnd = win32gui.FindWindow(None, title)
    if hwnd == 0:
        return None
    return hwnd

def get_client_rect(hwnd) -> Optional[Dict]:
    """
    返回客户区左上角屏幕坐标以及宽高
    """
    try:
        left_top = win32gui.ClientToScreen(hwnd, (0, 0))
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        width = cr
        height = cb
        return {"left": left_top[0], "top": left_top[1], "width": width, "height": height, "hwnd": hwnd}
    except Exception as e:
        dbg(f"get_client_rect error: {e}")
        return None

def capture_window(hwnd):
    rect = get_client_rect(hwnd)
    if rect is None:
        return None, None
    x, y, w, h = rect["left"], rect["top"], rect["width"], rect["height"]
    try:
        img = pyautogui.screenshot(region=(x, y, w, h))
        bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return bgr, rect
    except Exception as e:
        dbg(f"capture_window error: {e}")
        return None, None

# ------------------------
def to_gray(bgr):
    """将BGR彩色图像转换为灰度图像"""
    if bgr is None:
        return None
    if len(bgr.shape) == 2:
        return bgr
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return gray
    except Exception:
        return bgr

# 模板加载与多尺度匹配
# ------------------------
def load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    if not os.path.exists(path):
        dbg(f"模板不存在: {path}")
        return None
    tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        dbg(f"读取模板失败: {path}")
    return tpl

def match_template_once(gray_img, tpl, method=cv2.TM_CCOEFF_NORMED):
    try:
        res = cv2.matchTemplate(gray_img, tpl, method)
        minv, maxv, minloc, maxloc = cv2.minMaxLoc(res)
        return float(maxv), maxloc
    except Exception as e:
        dbg(f"match_template_once error: {e}")
        return 0.0, (0, 0)

def match_template_multiscale(gray_img, tpl, threshold=None):
    if tpl is None:
        return None, 0.0
    if threshold is None:
        threshold = config.DEFAULT_THRESHOLD
    best_val = 0.0
    best_center = None
    scales = config.SCALES if config.MULTISCALE else [1.0]
    for s in scales:
        tw = max(1, int(tpl.shape[1] * s))
        th = max(1, int(tpl.shape[0] * s))
        try:
            tpl_r = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
        except Exception:
            tpl_r = tpl
        if tpl_r.shape[0] > gray_img.shape[0] or tpl_r.shape[1] > gray_img.shape[1]:
            continue
        val, loc = match_template_once(gray_img, tpl_r)
        if val > best_val:
            best_val = val
            cx = loc[0] + tpl_r.shape[1] // 2
            cy = loc[1] + tpl_r.shape[0] // 2
            best_center = (int(cx), int(cy))
    if best_val >= threshold:
        return best_center, best_val
    return None, best_val

# ------------------------
# 点击封装（相对于客户区 -> 转为屏幕坐标）
# ------------------------
def safe_click_screen_abs(x_abs, y_abs, hold=None):
    try:
        pyautogui.moveTo(x_abs, y_abs, duration=config.CLICK_MOVE_DURATION)
        pyautogui.mouseDown()
        if hold is None:
            hold = config.CLICK_HOLD
        time.sleep(hold)
        pyautogui.mouseUp()
        dbg(f"safe_click_screen_abs ({x_abs},{y_abs})")
        return True
    except Exception as e:
        log(f"[ERROR] safe_click_screen_abs: {e}")
        return False

def safe_click_in_window(rect, pos_in_client, hold=None):
    if pos_in_client is None:
        dbg("safe_click_in_window: pos_in_client is None")
        return False
    x_abs = rect["left"] + int(pos_in_client[0])
    y_abs = rect["top"] + int(pos_in_client[1])
    return safe_click_screen_abs(x_abs, y_abs, hold=hold)

# ------------------------
# 高级：搜索模板并返回相对客户区坐标
# ------------------------
def find_template_in_window(gray_img_or_bgr, template_name, threshold=None):
    """
    在窗口截图中查找模板。
    - 对于占点/敌我相关模板，启用颜色过滤。
    - 对于一般UI按钮（港口/返回按钮等），禁用颜色过滤。
    返回 (坐标, 置信度)
    """
    path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(path):
        dbg(f"模板不存在: {path}")
        return None, 0.0

    tpl_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if tpl_bgr is None:
        dbg(f"读取模板失败: {path}")
        return None, 0.0

    # 判断是否为需要颜色识别的模板
    use_color_filter = any(key in template_name.lower() for key in [
        "cap_enemy", "cap_neutral", "cap_friendly"
   ])

    # --------------------------
    # 如果不需要颜色过滤，则直接灰度匹配
    # --------------------------
    if not use_color_filter:
        dbg(f"[COLOR] {template_name} -> 普通模板，跳过颜色过滤")
        if len(gray_img_or_bgr.shape) == 3:
            gray_img = cv2.cvtColor(gray_img_or_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray_img = gray_img_or_bgr
        tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_img, tpl_gray, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if threshold is None:
            threshold = config.DEFAULT_THRESHOLD
        if maxv < threshold:
            return None, float(maxv)
        cx = maxloc[0] + tpl_gray.shape[1] // 2
        cy = maxloc[1] + tpl_gray.shape[0] // 2
        return (int(cx), int(cy)), float(maxv)

    # --------------------------
    # 启用颜色过滤逻辑（仅用于占点/敌我识别）
    # --------------------------
    if len(gray_img_or_bgr.shape) == 2:
        img_bgr = cv2.cvtColor(gray_img_or_bgr, cv2.COLOR_GRAY2BGR)
    else:
        img_bgr = gray_img_or_bgr

    mean_color = tpl_bgr.mean(axis=(0, 1))
    b, g, r = mean_color
    dominant = "neutral"
    if r > g * 1.2 and r > b * 1.2:
        dominant = "enemy"
    elif g > r * 1.2 and g > b * 1.2:
        dominant = "friendly"
    elif abs(r - g) < 40 and abs(r - b) < 40:
        dominant = "neutral"

    if dominant == "enemy":
        lower = np.array([0, 0, 120])
        upper = np.array([180, 120, 255])
    elif dominant == "neutral":
        lower = np.array([90, 90, 90])
        upper = np.array([255, 255, 255])
    elif dominant == "friendly":
        dbg(f"[COLOR] {template_name} 判定为友方模板，跳过匹配。")
        return None, 0.0
    else:
        lower = np.array([0, 0, 0])
        upper = np.array([255, 255, 255])

    mask = cv2.inRange(img_bgr, lower, upper)
    masked = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)

    try:
        res = cv2.matchTemplate(masked, tpl_bgr, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if threshold is None:
            threshold = config.DEFAULT_THRESHOLD
        if maxv < threshold:
            return None, float(maxv)
        cx = maxloc[0] + tpl_bgr.shape[1] // 2
        cy = maxloc[1] + tpl_bgr.shape[0] // 2
        dbg(f"[COLOR] 模板 {template_name} ({dominant}) 匹配置信度={maxv:.2f}")
        return (int(cx), int(cy)), float(maxv)
    except Exception as e:
        dbg(f"find_template_in_window error: {e}")
        return None, 0.0


# ------------------------
# 兼容旧接口（main.py 旧调用）
# ------------------------
def ensure_templates_exist():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        log(f"[SYSTEM] Created templates folder: {TEMPLATE_DIR}")
    else:
        dbg(f"templates folder exists: {TEMPLATE_DIR}")

# ------------------------
# 预览 / debug helper（保存截图带标记）
# ------------------------
def save_debug_overlay(bgr_img, rect, matches):
    out = bgr_img.copy()
    for name, pos, val in matches:
        if pos is None:
            continue
        cv2.circle(out, (int(pos[0]), int(pos[1])), 8, (0, 255, 0), 2)
        cv2.putText(out, f"{name}:{val:.2f}", (int(pos[0]) + 10, int(pos[1]) + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
    p = os.path.join(LOG_DIR, f"debug_{int(time.time())}.png")
    cv2.imwrite(p, out)
    dbg(f"Saved debug overlay: {p}")
    return p
