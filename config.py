# 配置项（固定，不要随意改模板名）
GAME_TITLE = "《战舰世界》"      # 游戏窗口标题（和窗口标题完全匹配）
TEMPLATE_DIR = "templates"       # 模板文件夹（相对 main.py）
LOG_DIR = "logs"

# 匹配与重试参数（可调）
DEFAULT_THRESHOLD = 0.75        # 默认模板匹配阈值（可微调）
MULTISCALE = True               # 是否启用多尺度尝试（0.9,1.0,1.1）
SCALES = [0.9, 1.0, 1.1]

CLICK_HOLD = 0.08               # 点击时按住时长（秒）
CLICK_MOVE_DURATION = 0.08      # 移动鼠标到目标的时长（秒）
CLICK_CONFIRM_DELAY = 1.2       # 点击后等待确认的时间（秒）
MAX_RETRY = 3                   # 点击确认最大重试次数

SCAN_INTERVAL = 1.0             # 主循环截图间隔（秒）
STATE_CHECK_INTERVAL = 1.0      # 状态检测间隔（秒）

HOTKEY_TOGGLE = "f8"            # 启动/停止（切换）
HOTKEY_FORCE_STOP = "f9"        # 强制停止脚本

# 日志开关
DEBUG = True
