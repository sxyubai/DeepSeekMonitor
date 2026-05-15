"""
设置对话框
API Key 配置、加密存储、刷新间隔设置、透明度调节
"""

import os
import json
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpacerItem, QSizePolicy,
    QWidget, QMessageBox, QSlider, QComboBox,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon

# 尝试使用 keyring，失败则回退到文件加密存储
try:
    import keyring
    HAS_KEYRING = True
except Exception:
    HAS_KEYRING = False

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False

SERVICE_NAME = "DeepSeekMonitor"
KEY_NAME = "api_key"
CONFIG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "DeepSeekMonitor"
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def _get_machine_key() -> bytes:
    """生成基于机器的密钥（用于文件加密回退）"""
    machine_id = os.environ.get("COMPUTERNAME", "default-pc")
    salt = b"deepseek-monitor-salt"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))


def save_api_key(api_key: str) -> bool:
    """安全存储 API Key"""
    if not api_key:
        return False

    os.makedirs(CONFIG_DIR, exist_ok=True)

    if HAS_KEYRING:
        try:
            keyring.set_password(SERVICE_NAME, KEY_NAME, api_key)
            # 同时保存一个标记，表示 key 已存在
            config = {"has_key": True}
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
            return True
        except Exception:
            pass

    # 回退：加密文件存储
    if HAS_CRYPTO:
        try:
            cipher = Fernet(_get_machine_key())
            encrypted = cipher.encrypt(api_key.encode())
            config = {
                "storage": "file_encrypted",
                "encrypted_key": encrypted.decode(),
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
            return True
        except Exception:
            pass

    # 最终回退：明文（仅开发环境）
    config = {"storage": "plaintext", "key": api_key}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    return True


def load_api_key() -> Optional[str]:
    """加载已存储的 API Key"""
    if not os.path.exists(CONFIG_FILE):
        return None

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except Exception:
        return None

    storage = config.get("storage", "")

    if storage == "file_encrypted" and HAS_CRYPTO:
        try:
            cipher = Fernet(_get_machine_key())
            encrypted = config["encrypted_key"].encode()
            return cipher.decrypt(encrypted).decode()
        except Exception:
            return None

    if storage == "plaintext":
        return config.get("key")

    # 尝试 keyring
    if HAS_KEYRING:
        try:
            key = keyring.get_password(SERVICE_NAME, KEY_NAME)
            if key:
                return key
        except Exception:
            pass

    # 兼容旧格式：直接存了 has_key 标记
    if config.get("has_key") and HAS_KEYRING:
        try:
            return keyring.get_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass

    return None


def clear_api_key():
    """清除存储的 API Key"""
    if HAS_KEYRING:
        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass

    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
        except Exception:
            pass


def load_app_settings() -> dict:
    """加载应用设置"""
    settings_file = os.path.join(CONFIG_DIR, "app_settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_app_settings(settings: dict):
    """保存应用设置"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    settings_file = os.path.join(CONFIG_DIR, "app_settings.json")
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


class SettingsDialog(QDialog):
    """设置对话框"""

    api_key_saved = Signal(str)
    api_key_cleared = Signal()
    settings_changed = Signal(dict)  # 当其他设置（透明度、刷新间隔）变化时触发

    def __init__(self, parent=None, current_key: str = "", current_opacity: float = 1.0, current_interval: int = 60):
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("DeepSeek Monitor · 设置")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 460)

        self._current_key = current_key
        self._current_opacity = current_opacity
        self._current_interval = current_interval
        self._dragging = False
        self._drag_pos = None

        self._setup_ui()

        # 如果已有 key，显示掩码形式
        if current_key:
            self._key_input.setText("••••••••" + current_key[-4:] if len(current_key) > 4 else "••••••••")
            self._key_actual = current_key
            self._key_modified = False
        else:
            self._key_actual = ""
            self._key_modified = True

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 主容器
        container = QWidget()
        container.setObjectName("SettingsDialog")
        layout.addWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 20, 24, 20)
        container_layout.setSpacing(0)

        # ---- 标题栏（可拖动） ----
        title_bar = QWidget()
        title_bar.setObjectName("SettingsTitleBar")
        title_bar.setCursor(Qt.SizeAllCursor)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("⚙ 设置")
        title_label.setObjectName("SettingsTitle")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.ArrowCursor)
        close_btn.clicked.connect(self.reject)
        title_bar_layout.addWidget(close_btn)

        container_layout.addWidget(title_bar)
        container_layout.addSpacing(16)

        # ---- API Key 区域 ----
        section_label = QLabel("API 配置")
        section_label.setObjectName("SettingsSectionTitle")
        container_layout.addWidget(section_label)
        container_layout.addSpacing(8)

        api_key_label = QLabel("DeepSeek API Key")
        api_key_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
        container_layout.addWidget(api_key_label)

        container_layout.addSpacing(4)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self._key_input.setFixedHeight(28)
        self._key_input.textChanged.connect(self._on_key_changed)

        # 已有 key 时输入框只读
        if bool(self._current_key):
            self._key_input.setReadOnly(True)
            self._key_input.setStyleSheet("""
                QLineEdit {
                    background: rgba(255,255,255,0.04);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: rgba(255,255,255,0.4);
                    font-size: 13px;
                    min-height: 20px;
                }
            """)

        # API Key 输入行：输入框 + 操作按钮（同行，上下平齐）
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_row.addWidget(self._key_input, 1)

        self._action_btn = QPushButton("清除" if bool(self._current_key) else "保存")
        self._action_btn.setFixedSize(70, 28)
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.clicked.connect(self._on_action_clicked)
        self._update_action_btn_style(bool(self._current_key))
        key_row.addWidget(self._action_btn)

        container_layout.addLayout(key_row)

        container_layout.addSpacing(4)

        key_desc = QLabel("API Key 安全存储在本地，不会上传至第三方服务器。")
        key_desc.setObjectName("SettingsDesc")
        key_desc.setWordWrap(True)
        container_layout.addWidget(key_desc)

        container_layout.addSpacing(16)

        # ---- 显示设置区域 ----
        display_label = QLabel("显示设置")
        display_label.setObjectName("SettingsSectionTitle")
        container_layout.addWidget(display_label)
        container_layout.addSpacing(8)

        # 透明度滑块
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(8)

        opacity_title = QLabel("窗口透明度")
        opacity_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
        opacity_row.addWidget(opacity_title)

        opacity_row.addStretch()

        self._opacity_value_label = QLabel(f"{int(self._current_opacity * 100)}%")
        self._opacity_value_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px; min-width: 36px;")
        opacity_row.addWidget(self._opacity_value_label)

        container_layout.addLayout(opacity_row)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._current_opacity * 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255,255,255,0.1);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgba(99, 102, 241, 0.9);
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(99, 102, 241, 1);
            }
            QSlider::sub-page:horizontal {
                background: rgba(99, 102, 241, 0.6);
                border-radius: 2px;
            }
        """)
        container_layout.addWidget(self._opacity_slider)

        container_layout.addSpacing(12)

        # 刷新间隔
        interval_row = QHBoxLayout()
        interval_row.setSpacing(8)

        interval_title = QLabel("自动刷新间隔")
        interval_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
        interval_row.addWidget(interval_title)

        interval_row.addStretch()

        self._interval_combo = QComboBox()
        self._interval_combo.addItems(["30 秒", "60 秒", "120 秒", "300 秒", "关闭"])
        interval_values = [30, 60, 120, 300, 0]
        current_index = 1  # 默认 60 秒
        for i, v in enumerate(interval_values):
            if v == self._current_interval:
                current_index = i
                break
        self._interval_combo.setCurrentIndex(current_index)
        self._interval_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 6px 12px;
                color: white;
                font-size: 13px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid rgba(255,255,255,0.5);
                margin-right: 8px;
            }
            QComboBox:hover {
                border: 1px solid rgba(255,255,255,0.2);
            }
            QComboBox QAbstractItemView {
                background: #1e1e30;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                selection-background-color: rgba(99,102,241,0.3);
                color: white;
                padding: 4px;
                outline: none;
            }
        """)
        self._interval_combo.currentIndexChanged.connect(self._on_interval_changed)
        interval_row.addWidget(self._interval_combo)

        container_layout.addLayout(interval_row)

        container_layout.addSpacing(12)

        # 状态指示
        self._status_label = QLabel("")
        self._status_label.setObjectName("StatusIndicator")
        self._status_label.setVisible(False)
        container_layout.addWidget(self._status_label)

    def _update_action_btn_style(self, has_key: bool):
        """根据是否有 key 切换按钮样式"""
        if has_key:
            self._action_btn.setText("清除")
            self._action_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(239, 68, 68, 0.2);
                    border: 1px solid rgba(239, 68, 68, 0.3);
                    border-radius: 6px;
                    color: #ef4444;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(239, 68, 68, 0.35);
                }
            """)
        else:
            self._action_btn.setText("保存")
            self._action_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(99, 102, 241, 0.9);
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(99, 102, 241, 1);
                }
            """)

    def _on_opacity_changed(self, value: int):
        """透明度滑块变化 — 即时生效并自动保存"""
        self._opacity_value_label.setText(f"{value}%")
        opacity = value / 100.0
        if self.parent():
            self.parent().setWindowOpacity(opacity)
        # 合并保存，不覆盖其他设置
        merged = load_app_settings()
        merged["opacity"] = opacity
        save_app_settings(merged)
        self.settings_changed.emit({"opacity": opacity})

    def _on_interval_changed(self, index: int):
        """刷新间隔变化 — 即时生效并自动保存"""
        interval = [30, 60, 120, 300, 0][index]
        # 合并保存，不覆盖其他设置
        merged = load_app_settings()
        merged["refresh_interval"] = interval
        save_app_settings(merged)
        self.settings_changed.emit({"refresh_interval": interval})

    def _on_key_changed(self, text: str):
        """API Key 输入变化 — 仅追踪文本"""
        if self._current_key:
            return
        self._key_actual = text

    def _on_action_clicked(self):
        """操作按钮点击：有 key 时清除，无 key 时保存"""
        if self._current_key:
            self._on_clear()
        else:
            self._on_save()

    def _on_save(self):
        """保存 API Key + 显示设置"""
        key = self._key_actual.strip()
        if key:
            success = save_api_key(key)
            if success:
                self.api_key_saved.emit(key)
                self._key_input.setReadOnly(True)
                self._current_key = key
                self._update_action_btn_style(True)
                self._status_label.setText("✓ 已保存")
                self._status_label.setStyleSheet(
                    "background: rgba(74,222,128,0.15); color: #4ade80; border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;"
                )
                self._status_label.setVisible(True)
            else:
                self._status_label.setText("✗ 保存失败")
                self._status_label.setStyleSheet(
                    "background: rgba(239, 68, 68, 0.15); color: #ef4444; border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;"
                )
                self._status_label.setVisible(True)

        merged = load_app_settings()
        merged["opacity"] = self._opacity_slider.value() / 100.0
        merged["refresh_interval"] = [30, 60, 120, 300, 0][self._interval_combo.currentIndex()]
        save_app_settings(merged)
        self.settings_changed.emit(merged)

    def _on_clear(self):
        """清除 API Key"""
        reply = QMessageBox.question(
            self, "确认清除",
            "确定要清除已保存的 API Key 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            clear_api_key()
            self._key_input.setReadOnly(False)
            self._key_input.setStyleSheet("")
            self._key_input.clear()
            self._key_actual = ""
            self._current_key = ""
            self._update_action_btn_style(False)
            self._status_label.setText("✓ 已清除")
            self._status_label.setStyleSheet(
                "background: rgba(251, 191, 36, 0.15); color: #fbbf24; border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 600;"
            )
            self._status_label.setVisible(True)
            self.api_key_cleared.emit()

    # ---- 窗口拖动 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()
