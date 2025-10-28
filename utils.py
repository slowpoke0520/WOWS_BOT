# utils.py - 日志、截图、模板匹配、多尺度支持、文件工具
import os, time, cv2, numpy as np, pyautogui
from datetime import datetime
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

def get_client_rect(hwnd):
    # 返回客户区左上角屏幕坐标以及宽高
    left_top = win32gui.ClientToScreen(hwnd, (0,0))
    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    width = cr
    height = cb
    return {"left": left_top[0], "top": left_top[1], "width": width, "height": height, "hwnd": hwnd}

def capture_window(hwnd):
    rect = get_client_rect(hwnd)
    if rect is None:
        return None
    x,y,w,h = rect["left"], rect["top"], rect["width"], rect["height"]
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
    import cv2
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
    # return max_val, max_loc
    try:
        res = cv2.matchTemplate(gray_img, tpl, method)
        minv, maxv, minloc, maxloc = cv2.minMaxLoc(res)
        return float(maxv), maxloc
    except Exception as e:
        dbg(f"match_template_once error: {e}")
        return 0.0, (0,0)

def match_template_multiscale(gray_img, tpl, threshold=None):
    if tpl is None:
        return None, 0.0
    if threshold is None:
        threshold = config.DEFAULT_THRESHOLD
    best_val = 0.0
    best_center = None
    # try scales
    scales = config.SCALES if config.MULTISCALE else [1.0]
    for s in scales:
        tw = max(1, int(tpl.shape[1]*s))
        th = max(1, int(tpl.shape[0]*s))
        try:
            tpl_r = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
        except Exception:
            tpl_r = tpl
        if tpl_r.shape[0] > gray_img.shape[0] or tpl_r.shape[1] > gray_img.shape[1]:
            continue
        val, loc = match_template_once(gray_img, tpl_r)
        if val > best_val:
            best_val = val
            # center relative to image
            cx = loc[0] + tpl_r.shape[1]//2
            cy = loc[1] + tpl_r.shape[0]//2
            best_center = (int(cx), int(cy))
    if best_val >= threshold:
        return best_center, best_val
    return None, best_val

# ------------------------
# 点击封装（相对于客户区 -> 转为屏幕坐标）
# ------------------------
import pyautogui, time

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
    # rect: dict {left,top,width,height}; pos_in_client: (cx,cy) relative to client top-left
    if pos_in_client is None:
        dbg("safe_click_in_window: pos_in_client is None")
        return False
    x_abs = rect["left"] + int(pos_in_client[0])
    y_abs = rect["top"] + int(pos_in_client[1])
    return safe_click_screen_abs(x_abs, y_abs, hold=hold)

# ------------------------
# 高级：搜索模板并返回相对客户区坐标
# ------------------------
def find_template_in_window(gray_img, template_name, threshold=None):
    tpl = load_template(template_name)
    if tpl is None:
        return None, 0.0
    pos, val = match_template_multiscale(gray_img, tpl, threshold)
    return pos, val

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
    # matches: list of tuples (name, (cx,cy), val)
    out = bgr_img.copy()
    for name, pos, val in matches:
        if pos is None: continue
        cv2.circle(out, (int(pos[0]), int(pos[1])), 8, (0,255,0), 2)
        cv2.putText(out, f"{name}:{val:.2f}", (int(pos[0])+10,int(pos[1])+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 1, cv2.LINE_AA)
    # save
    p = os.path.join(LOG_DIR, f"debug_{int(time.time())}.png")
    cv2.imwrite(p, out)
    dbg(f"Saved debug overlay: {p}")
    return p
