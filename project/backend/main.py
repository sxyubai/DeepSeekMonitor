#!/usr/bin/env python3
"""
DeepSeek Monitor - Windows 桌面悬浮窗
实时显示 DeepSeek 账户余额与 API Token 用量统计
© 2026 sxyubai
"""

import sys
import os
import threading

# Ensure project root is in sys.path (for utils import)
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
    QWidgetAction, QLabel, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QIcon, QAction, QFont, QPixmap, QPainter, QColor, QFontDatabase

# 本地模块
from api_client import DeepSeekAPIClient

from floating_window import FloatingWindow
from settings_dialog import (
    SettingsDialog, load_api_key, clear_api_key, save_api_key,
    load_app_settings, save_app_settings,
)
from utils.auto_start import set_auto_start, is_auto_start_enabled


# ---- 全局资源路径 ----
def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径（支持 PyInstaller 打包）"""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# ==========================================
# 跨线程信号桥（必须在主线程创建，用于从工作线程安全回传数据）
# ==========================================
class BalanceSignal(QObject):
    result_ready = Signal(object)



# ==========================================
# 主应用
# ==========================================
class DeepSeekMonitorApp:
    """DeepSeek Monitor 主应用"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("DeepSeek Monitor")
        self.app.setOrganizationName("sxyubai")

        # 设置字体
        font = QFont("Microsoft YaHei UI", 9)
        self.app.setFont(font)

        # 加载 QSS 样式表
        qss_path = resource_path("resources/style.qss")
        if os.path.exists(qss_path):
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    self.app.setStyleSheet(f.read())
            except Exception:
                pass

        # 防止无父窗口的对话框关闭时导致整个应用退出
        self.app.setQuitOnLastWindowClosed(False)

        # 初始化组件
        self._api_key: str = ""
        self._client = DeepSeekAPIClient()

        self._window = FloatingWindow()
        self._tray = None
        self._settings_dialog = None

        # 跨线程信号桥（主线程创建，工作线程安全 emit）
        self._balance_signal = BalanceSignal()
        self._balance_signal.result_ready.connect(self._on_balance_result)

        # 线程状态标记（防重入）
        self._balance_busy: bool = False

        # 初始化
        self._setup_tray()
        self._setup_connections()
        self._load_saved_key()

        # 读取应用设置
        _settings = load_app_settings()
        # 应用开机自启（默认开启）
        if _settings.get("auto_start", True):
            set_auto_start(True)
        # 仅自启动时才自动缩小到托盘
        if "--autostart" in sys.argv and _settings.get("auto_minimize", True):
            self._window.hide()
        else:
            self._window.show()

        # 首次自动刷新
        QTimer.singleShot(500, self._refresh_balance)

        # 定时自动刷新
        self._window.start_auto_refresh()

    def _setup_tray(self):
        """设置系统托盘"""
        # 创建系统托盘图标
        self._tray = QSystemTrayIcon()
        self._tray.setToolTip("DeepSeek Monitor")

        # 生成简单的托盘图标（纯色圆点）
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(99, 102, 241))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        icon = QIcon(pixmap)
        self._tray.setIcon(icon)

        # 右键菜单（显式设置样式，不受 QSS 影响）
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e2e;
                border: 1px solid #363654;
                border-radius: 8px;
                padding: 4px 0;
                color: #ffffff;
            }
            QMenu::item {
                color: #ffffff;
                padding: 6px 24px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: #363654;
            }
            QMenu::separator {
                height: 1px;
                background: #363654;
                margin: 4px 12px;
            }
        """)

        # 标题项
        title_action = QWidgetAction(menu)
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(12, 6, 12, 6)
        title_label = QLabel("DeepSeek Monitor")
        title_label.setStyleSheet("font-weight: 700; font-size: 13px; color: white;")
        title_layout.addWidget(title_label)
        subtitle_label = QLabel(
            '<a href="https://github.com/sxyubai/DeepSeekMonitor" '
            'style="color: rgba(255,255,255,0.4); text-decoration: none;">'
            "v1.1 · © 2026 sxyubai</a>"
        )
        subtitle_label.setOpenExternalLinks(True)
        subtitle_label.setStyleSheet("font-size: 10px;")
        title_layout.addWidget(subtitle_label)

        title_action.setDefaultWidget(title_widget)
        menu.addAction(title_action)
        menu.addSeparator()

        # 显示窗口
        show_action = QAction("显示悬浮窗", self._tray)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        # 刷新
        refresh_action = QAction("立即刷新", self._tray)
        refresh_action.triggered.connect(self._refresh_balance)
        menu.addAction(refresh_action)

        # 设置
        settings_action = QAction("设置", self._tray)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出", self._tray)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_connections(self):
        """连接信号与槽"""
        # 窗口刷新
        self._window.refresh_requested.connect(self._refresh_balance)
        self._window.open_settings_requested.connect(self._open_settings)
        self._window.close_requested.connect(self._on_close_window)

    def _load_saved_key(self):
        """加载已保存的 API Key"""
        key = load_api_key()
        if key:
            self._api_key = key
            self._client.set_api_key(key)

    def _refresh_balance(self):
        """刷新余额（线程安全：防重入 + 跨线程回调）"""
        if self._balance_busy:
            return

        if not self._api_key:
            self._window.update_balance(None)
            self._window.update_sync_time("未配置 API Key")
            return

        self._window.update_sync_time("正在获取...")
        self._balance_busy = True

        client = self._client
        signal = self._balance_signal  # 主线程创建，跨线程 emit 安全

        def _worker():
            try:
                data = client.get_balance(force_refresh=True)
            except Exception as e:
                data = {"error": str(e)}
            signal.result_ready.emit(data)  # Qt 自动排队到主线程执行

        threading.Thread(target=_worker, daemon=True).start()

    def _on_balance_result(self, data):
        """余额查询结果回调（主线程执行）"""
        self._balance_busy = False
        self._window.update_balance(data)

        now = datetime.now().strftime("%H:%M:%S")
        self._window.update_sync_time(now)

        # 更新托盘提示
        if data and "error" not in data:
            total = data.get("total_balance", 0)
            self._tray.setToolTip(f"DeepSeek Monitor · 余额 ¥{total:.2f}")
        elif data and "error" in data:
            self._tray.setToolTip(f"DeepSeek Monitor · {data['error']}")
        else:
            self._tray.setToolTip("DeepSeek Monitor")





    def _open_settings(self):
        """打开设置对话框"""
        # 读取已保存的设置值
        saved = load_app_settings()
        current_opacity = saved.get("opacity", 1.0)
        current_interval = saved.get("refresh_interval", 60)

        dialog = SettingsDialog(
            parent=self._window,
            current_key=self._api_key,
            current_opacity=current_opacity,
            current_interval=current_interval,
        )
        dialog.api_key_saved.connect(self._on_api_key_saved)
        dialog.api_key_cleared.connect(self._on_api_key_cleared)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self, settings: dict):
        """应用设置变更"""
        if "opacity" in settings:
            self._window.set_window_opacity_value(settings["opacity"])
        if "refresh_interval" in settings:
            interval_s = settings["refresh_interval"]
            if interval_s > 0:
                self._window.set_refresh_interval(interval_s * 1000)
                self._window.start_auto_refresh()
            else:
                self._window.stop_auto_refresh()

    def _on_api_key_saved(self, key: str):
        """API Key 已保存"""
        self._api_key = key
        self._client.set_api_key(key)
        self._refresh_balance()

    def _on_api_key_cleared(self):
        """API Key 已清除"""
        self._api_key = ""
        self._client.set_api_key("")
        self._window.update_balance(None)
        self._window.update_sync_time("未配置 API Key")
        self._tray.setToolTip("DeepSeek Monitor")

    def _show_window(self):
        """显示悬浮窗"""
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_close_window(self):
        """关闭窗口（隐藏到托盘）"""
        self._window.hide()

    def _on_tray_activated(self, reason):
        """系统托盘被激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _quit_app(self):
        """退出应用"""
        self._window.stop_auto_refresh()
        self._tray.hide()
        self.app.quit()
        sys.exit(0)

    def run(self):
        """启动应用"""
        return self.app.exec()


# ==========================================
# 入口
# ==========================================
def main():
    # 高 DPI 支持：PySide6 默认启用，配置缩放舍入策略
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = DeepSeekMonitorApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
