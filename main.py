# main.py - 程序入口：状态机 + 热键启动/停止（固定模板名）
import time, keyboard, config
from utils import log, dbg, ensure_templates_exist, find_game_window
from states import detect_state_once
import actions
from typing import Optional, Dict

def main():
    log("WoWsBot 启动 - 固定模板版本")
    ensure_templates_exist()
    running = False
    last_state = None
    nav_done = False  # ✅ 用于记忆是否已经完成自动导航

    log(f"按 {config.HOTKEY_TOGGLE} 切换启动/停止，按 {config.HOTKEY_FORCE_STOP} 强制退出")

    # 注册热键
    def toggle():
        nonlocal running
        running = not running
        log(f"[HOTKEY] 运行状态切换为：{'运行中' if running else '已暂停'}")

    def force_stop():
        log("[HOTKEY] 收到强制停止指令，程序退出")
        raise SystemExit()

    keyboard.add_hotkey(config.HOTKEY_TOGGLE, toggle)
    keyboard.add_hotkey(config.HOTKEY_FORCE_STOP, force_stop)

    try:
        while True:
            hwnd = find_game_window()
            if hwnd is None:
                log("未找到游戏窗口，等待中...")
                time.sleep(2)
                continue

            if not running:
                time.sleep(0.3)
                continue

            state, info = detect_state_once()
            if state != last_state:
                log(f"State change: {last_state} -> {state} | info={info}")
                last_state = state

            # === 状态处理 ===
            if state == "PORT":
                log("[MAIN] 在港口 - 尝试点击加入战斗")
                nav_done = False  # ✅ 每次回到港口重置
                actions.click_with_confirm(
                    ["port_join_battle.png", "port_join_battle_disabled.png"],
                    ["queue_waiting.png", "battle_score_bar.png"],
                    max_retry=3
                )

            elif state == "QUEUE":
                log("[MAIN] 匹配中 - 等待进入战斗")
                time.sleep(2)

            elif state == "BATTLE":
                if not nav_done:  # ✅ 仅第一次执行导航逻辑
                    log("[MAIN] 战斗中 - 确保自动导航")
                    success = actions.ensure_auto_nav_enabled()
                    if success:
                        nav_done = True  # ✅ 记住导航已完成
                        dbg("[MAIN] 自动导航完成，后续不再重复执行")
                else:
                    dbg("[MAIN] 自动导航已完成，无需重复操作")
                time.sleep(2)

            elif state == "RESULT":
                log("[MAIN] 结算界面 - 点击返回港口按钮")
                nav_done = False  # ✅ 战斗结束重置
                actions.click_with_confirm(
                    ["back_to_port.png"],
                    ["port_join_battle.png"],
                    max_retry=3
                )

            else:
                dbg("[MAIN] 未识别状态，继续检测")

            time.sleep(config.STATE_CHECK_INTERVAL)

    except KeyboardInterrupt:
        log("收到 Ctrl+C，退出")
    except SystemExit:
        log("强制退出")
    except Exception as e:
        log(f"[FATAL] 未处理异常: {e}")

if __name__ == "__main__":
    main()
