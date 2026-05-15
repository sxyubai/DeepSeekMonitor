"""
DeepSeek Monitor - 深色毛玻璃悬浮窗
主界面组件：显示余额、用量统计、每日消耗、可交互
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSpacerItem, QSizePolicy,
    QApplication, QTextEdit, QGraphicsOpacityEffect, QMenu,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve,
    Property, QEvent, QPoint, QRect, QMargins, QUrl,
)
from PySide6.QtGui import (
    QFont, QPainter, QColor, QLinearGradient, QBrush,
    QPen, QFontDatabase, QCursor, QDesktopServices,
    QAction, QEnterEvent,
)

import sys
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from usage_tracker import UsageTracker


class DailyConsumptionPopup(QFrame):
    """每日消耗悬浮提示框 - 显示近7天消耗。支持 hover 跟踪。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DailyConsumptionPopup")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setFixedSize(240, 200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel("近 7 天消耗")
        title.setStyleSheet(
            "color: rgba(255,255,255,0.7); font-size: 11px; font-weight: 600; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        self._list_widget = QVBoxLayout()
        self._list_widget.setSpacing(3)
        layout.addLayout(self._list_widget)
        layout.addStretch()

    def update_data(self, days_data: List[Dict[str, Any]]):
        """更新7天数据"""
        while self._list_widget.count():
            item = self._list_widget.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not days_data:
            empty = QLabel("暂无消耗记录")
            empty.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
            self._list_widget.addWidget(empty)
            return

        total_7day = sum(d.get("total_cost", 0) for d in days_data)

        for d in days_data:
            day = d.get("date", "----")
            cost = d.get("total_cost", 0)

            row = QHBoxLayout()
            row.setSpacing(8)

            day_label = QLabel(day)
            day_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
            row.addWidget(day_label)

            row.addStretch()

            cost_label = QLabel(f"¥{cost:.2f}")
            cost_label.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 11px; font-weight: 600;")
            row.addWidget(cost_label)

            container = QWidget()
            container.setLayout(row)
            self._list_widget.addWidget(container)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: rgba(255,255,255,0.08); max-height: 1px;")
        self._list_widget.addWidget(sep)

        total_row = QHBoxLayout()
        total_row.setSpacing(8)
        total_label = QLabel("7天合计")
        total_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        total_row.addWidget(total_label)
        total_row.addStretch()
        total_cost_label = QLabel(f"¥{total_7day:.2f}")
        total_cost_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        total_row.addWidget(total_cost_label)
        total_container = QWidget()
        total_container.setLayout(total_row)
        self._list_widget.addWidget(total_container)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.setBrush(QColor(24, 24, 38, 240))
        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)


class BalanceCard(QWidget):
    """余额卡片组件 — 重构布局：今日消耗独立为次级卡片"""

    balance_clicked = Signal()
    daily_cost_hovered = Signal()
    daily_cost_unhovered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BalanceCard")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # ========================
        # 第1行：账户余额 · 今日消耗 · ● 可用
        # ========================
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        balance_label = QLabel("账户余额")
        balance_label.setObjectName("BalanceLabel")
        header_row.addWidget(balance_label)

        header_row.addStretch()

        daily_title = QLabel("今日消耗")
        daily_title.setObjectName("DailyCostHeader")
        daily_title.setFixedWidth(80)
        header_row.addWidget(daily_title)

        layout.addLayout(header_row)

        # ========================
        # 第2行：金额数值 · 今日消耗值
        # ========================
        value_row = QHBoxLayout()
        value_row.setSpacing(0)

        self._amount_label = QLabel("--.--")
        self._amount_label.setObjectName("BalanceAmount")
        self._amount_label.setCursor(Qt.CursorShape.PointingHandCursor)
        value_row.addWidget(self._amount_label)

        self._currency_label = QLabel("CNY")
        self._currency_label.setObjectName("BalanceCurrency")
        value_row.addWidget(self._currency_label)

        value_row.addStretch()
        value_row.addSpacing(28)

        self._daily_cost_label = QLabel("¥--.--")
        self._daily_cost_label.setObjectName("DailyCostValue")
        self._daily_cost_label.setFixedWidth(80)
        value_row.addWidget(self._daily_cost_label)

        layout.addLayout(value_row)

        layout.addSpacing(4)

        # ========================
        # 第3行：赠送 · 充值
        # ========================
        detail_row = QHBoxLayout()
        detail_row.setSpacing(16)

        self._granted_label = QLabel("赠送: --")
        self._granted_label.setObjectName("StatsSubLabel")
        detail_row.addWidget(self._granted_label)

        self._topped_label = QLabel("充值: --")
        self._topped_label.setObjectName("StatsSubLabel")
        detail_row.addWidget(self._topped_label)

        detail_row.addStretch()
        layout.addLayout(detail_row)

        # 安装事件过滤器
        self._amount_label.installEventFilter(self)
        self._daily_cost_label.installEventFilter(self)

    def eventFilter(self, obj, event):
        if not hasattr(self, '_daily_cost_label'):
            return super().eventFilter(obj, event)

        # 点击余额数字 → 打开官网
        if obj == self._amount_label:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.balance_clicked.emit()
                    return True

        if obj == self._daily_cost_label:
            if event.type() == QEvent.Type.Enter:
                # hover 高亮效果在 QSS 中处理，此处仅触发弹窗
                self.daily_cost_hovered.emit()
            elif event.type() == QEvent.Type.Leave:
                self.daily_cost_unhovered.emit()

        return super().eventFilter(obj, event)

    def update_data(self, data: Optional[Dict[str, Any]]):
        """更新余额显示"""
        if data is None:
            self._amount_label.setText("--.--")
            self._granted_label.setText("赠送: --")
            self._topped_label.setText("充值: --")
            return

        if "error" in data:
            self._amount_label.setText("!--!")
            self._granted_label.setText("")
            self._topped_label.setText("")
            return

        total = data.get("total_balance", 0)
        granted = data.get("granted_balance", 0)
        topped = data.get("topped_up_balance", 0)

        self._amount_label.setText(f"{total:.2f}")
        self._granted_label.setText(f"赠送: ¥{granted:.2f}")
        self._topped_label.setText(f"充值: ¥{topped:.2f}")

    def update_daily_cost(self, cost: float):
        """更新今日消耗显示（保留2位小数）"""
        self._daily_cost_label.setText(f"¥{cost:.2f}")


class FloatingWindow(QWidget):
    """主悬浮窗"""

    refresh_requested = Signal()
    open_settings_requested = Signal()
    close_requested = Signal()

    _opacity: float = 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FloatingWindow")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # [FIX-1] 彻底阻止原生右键菜单，消除白色方块
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

        # 阴影/光晕效果
        self._shadow_radius = 20
        self._shadow_opacity = 0.3

        # 拖拽状态
        self._dragging = False
        self._drag_pos = None
        self._edge_margin = 10

        # 展开/折叠
        self._expanded = True
        self._collapsed_width = 80
        self._expanded_width = 280
        self._anim_width = self._expanded_width
        self.setFixedWidth(self._expanded_width)

        self._setup_ui()

        # 数据
        self._balance_data: Optional[Dict[str, Any]] = None

        # 用量追踪器
        self._usage_tracker = UsageTracker()

        # 每日消耗悬浮提示
        self._daily_popup = DailyConsumptionPopup()
        self._daily_popup.hide()

        self._daily_cost_ref = self._balance_card._daily_cost_label
        self._balance_card.daily_cost_hovered.connect(self._show_daily_popup)
        self._balance_card.daily_cost_unhovered.connect(self._on_daily_cost_unhovered)
        self._balance_card.balance_clicked.connect(self._on_balance_clicked)

        # 安装事件过滤器跟踪 popup hover
        self._daily_popup.installEventFilter(self)

        # 弹窗延迟关闭定时器
        self._popup_hide_timer = QTimer(self)
        self._popup_hide_timer.setSingleShot(True)
        self._popup_hide_timer.timeout.connect(self._hide_daily_popup)

        # 定时刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_requested.emit)
        self._refresh_timer.setInterval(60000)

        # [FIX-3] 自动安装拖动 eventFilter 到所有非交互子控件
        self._install_drag_filters(self)

    def _setup_ui(self):
        """构建主界面：标题栏 + 余额卡片 + 刷新行"""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(12, 0, 12, 14)
        self._main_layout.setSpacing(0)

        # ==== 标题栏 ====
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(4, 8, 4, 4)

        title_label = QLabel("DEEPSEEK MONITOR")
        title_label.setObjectName("TitleLabel")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        # ● 可用 — 紧邻 ✕ 按钮（初始为加载中，500ms 后首次刷新才变更）
        self._status_label = QLabel("● 加载中...")
        self._status_label.setObjectName("BalanceStatusLoading")
        title_bar_layout.addWidget(self._status_label)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        close_btn.clicked.connect(self.close_requested.emit)
        title_bar_layout.addWidget(close_btn)

        self._main_layout.addWidget(title_bar)

        # ==== 余额卡片 ====
        self._main_layout.addSpacing(4)
        self._balance_card = BalanceCard()
        self._main_layout.addWidget(self._balance_card)

        # ==== 底部刷新行 ====
        self._main_layout.addSpacing(2)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self._refresh_btn = QPushButton("⟳ 刷新")
        self._refresh_btn.setObjectName("RefreshBtn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        bottom_row.addWidget(self._refresh_btn)

        bottom_row.addStretch()

        self._sync_label = QLabel("等待同步...")
        self._sync_label.setObjectName("SyncTimeLabel")
        bottom_row.addWidget(self._sync_label)

        self._main_layout.addLayout(bottom_row)
        self._main_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)

    def _install_drag_filters(self, root: QWidget):
        """
        递归安装 eventFilter 到所有非交互子控件，
        使得鼠标点击面板任意位置都能触发拖动。
        """
        for child in root.findChildren(QWidget, options=Qt.FindChildOption.FindChildrenRecursively):
            # 跳过按钮等交互控件（它们需要自己的点击事件）
            if isinstance(child, QPushButton):
                continue
            # 跳过有点击交互光标的 QLabel（如余额数字，点击应打开官网而非拖拽）
            if isinstance(child, QLabel) and child.cursor().shape() == Qt.CursorShape.PointingHandCursor:
                continue
            # 跳过已经是顶级窗口的控件（如 popup）
            if child.isWindow():
                continue
            # 跳过自身
            if child is self:
                continue
            child.installEventFilter(self)

    # ---- 右键菜单（手动触发，消除白色方块）----
    def _show_context_menu(self, pos):
        """在指定位置弹出右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e2e;
                border: 1px solid #363654;
                border-radius: 8px;
                padding: 6px 0;
                color: #ffffff;
                font-size: 13px;
            }
            QMenu::item {
                color: #ffffff;
                padding: 8px 24px;
            }
            QMenu::item:selected {
                background: #363654;
            }
        """)
        action = menu.addAction("⚙ 设置")
        action.triggered.connect(self.open_settings_requested.emit)
        menu.exec(self.mapToGlobal(pos))

    def update_balance(self, data: Optional[Dict[str, Any]]):
        """更新余额数据"""
        self._balance_data = data
        self._balance_card.update_data(data)
        self._update_daily_cost()

        # 同步 ● 可用状态到标题栏 — 三色标识
        if data is None:
            self._status_label.setText("● 加载中...")
            self._status_label.setObjectName("BalanceStatusLoading")
        elif "error" in data:
            self._status_label.setText("● API不可用")
            self._status_label.setObjectName("BalanceStatusError")
        elif data.get("is_available", False):
            self._status_label.setText("● 可用")
            self._status_label.setObjectName("BalanceStatus")
        else:
            self._status_label.setText("● 不可用")
            self._status_label.setObjectName("BalanceStatusError")

        # 强制刷新 QSS 样式（运行时 setObjectName 不会自动应用新样式）
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def update_sync_time(self, time_str: str):
        """更新同步时间"""
        self._sync_label.setText(f"最后同步: {time_str}")

    def _on_balance_clicked(self):
        """余额点击 → 打开 DeepSeek 用量页面（QDesktopServices 兼容 PyInstaller exe）"""
        QDesktopServices.openUrl(QUrl("https://platform.deepseek.com/usage"))

    def set_refresh_interval(self, interval_ms: int):
        """设置刷新间隔"""
        self._refresh_timer.setInterval(interval_ms)

    def start_auto_refresh(self):
        """启动自动刷新"""
        self._refresh_timer.start()

    def stop_auto_refresh(self):
        """停止自动刷新"""
        self._refresh_timer.stop()

    def set_window_opacity_value(self, opacity: float):
        """设置窗口透明度"""
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    def get_window_opacity_value(self) -> float:
        return self._opacity

    # ---- 每日消耗相关 ----
    def _update_daily_cost(self):
        """基于余额差额更新每日消耗"""
        if self._balance_data and "total_balance" in self._balance_data:
            balance = self._balance_data["total_balance"]
            consumption = self._usage_tracker.update_daily_balance(balance)
            self._balance_card.update_daily_cost(consumption)
        else:
            self._balance_card.update_daily_cost(0.0)

    def _get_weekly_consumption(self) -> List[Dict[str, Any]]:
        """获取近7天消耗数据（基于余额差额）"""
        conn = self._usage_tracker._get_conn()
        try:
            rows = conn.execute("""
                SELECT date, consumption
                FROM (
                    SELECT date,
                           ROUND(MAX(max_balance) - MIN(last_balance), 6) AS consumption
                    FROM daily_balance
                    WHERE date >= date('now', '-6 days', 'localtime')
                    GROUP BY date
                )
                ORDER BY date ASC
            """).fetchall()
            result = []
            today = date.today()
            date_set = {row["date"] for row in rows}
            for i in range(6, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                if d in date_set:
                    row_data = [r for r in rows if r["date"] == d][0]
                    result.append({
                        "date": d,
                        "total_cost": row_data["consumption"],
                        "total_tokens": 0,
                    })
                else:
                    result.append({
                        "date": d,
                        "total_cost": 0.0,
                        "total_tokens": 0,
                    })
            return result
        finally:
            conn.close()

    # ---- 鼠标事件（统一手动拖拽 + 右键菜单）----
    def mousePressEvent(self, event):
        """[FIX-2] 左键拖拽 / 右键冒泡拦截（消除白闪）"""
        if event.button() == Qt.MouseButton.RightButton:
            # 立即弹出右键菜单，不冒泡到 super()
            self._show_context_menu(event.position().toPoint())
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """[FIX-2] 右键已在 mousePressEvent 处理，此处仅处理拖拽释放"""
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return

        if self._dragging:
            self._dragging = False
            self._snap_if_near_edge()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _snap_if_near_edge(self):
        """仅在靠近边缘时做贴边吸附"""
        screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if not screen:
            return
        screen_geo = screen.geometry()
        pos = self.pos()
        x, y = pos.x(), pos.y()
        w = self.width()

        snap_x, snap_y = x, y
        if abs(x) < self._edge_margin:
            snap_x = 0
        elif abs(x + w - screen_geo.width()) < self._edge_margin:
            snap_x = screen_geo.width() - w

        if abs(y) < self._edge_margin:
            snap_y = 0
        elif abs(y + self.height() - screen_geo.height()) < self._edge_margin:
            snap_y = screen_geo.height() - self.height()

        if (snap_x, snap_y) != (x, y):
            end_pos = type(pos)(snap_x, snap_y)
            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(180)
            anim.setStartValue(pos)
            anim.setEndValue(end_pos)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()

    # ---- 毛玻璃绘制 ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        bg_color = QColor(14, 14, 24, 220)

        path = self._rounded_rect_path(rect, 16)
        painter.setClipPath(path)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.fillRect(rect, bg_color)

        gradient = QLinearGradient(0, 0, 0, rect.height() * 0.4)
        gradient.setColorAt(0, QColor(255, 255, 255, 12))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, gradient)

        painter.setClipRect(rect)
        pen = QPen(QColor(255, 255, 255, 18), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 16, 16)

    def _rounded_rect_path(self, rect, radius):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        return path

    # ---- 每日消耗悬浮提示（hover 渐显 + 点击面板关闭）----
    def eventFilter(self, obj, event):
        """[FIX-3] 子控件拖动拦截 + [FIX-4] 弹窗智能关闭"""

        # == 弹窗 hover 跟踪 ==
        if obj == self._daily_popup:
            if event.type() == QEvent.Type.Enter:
                self._popup_hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._popup_hide_timer.start(300)

        # == 拖动支持：非交互子控件上按下左键时启动拖动 ==
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                # 不拦截按钮点击
                if not isinstance(obj, QPushButton):
                    self._dragging = True
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return False  # 不消费事件，让子控件正常处理
            elif event.button() == Qt.MouseButton.RightButton:
                # [FIX-4] 点击主面板任意位置 → 隐藏弹窗
                self._hide_daily_popup_immediate()
                # 子控件上的右键也弹菜单
                if not isinstance(obj, QPushButton):
                    self._show_context_menu(event.position().toPoint())
                    return True

        # [FIX-4] 鼠标按下（任何按钮）→ 关闭弹出窗
        if event.type() == QEvent.Type.MouseButtonPress and self._daily_popup.isVisible():
            self._hide_daily_popup_immediate()

        if event.type() == QEvent.Type.MouseMove and self._dragging:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                return True

        if event.type() == QEvent.Type.MouseButtonRelease and self._dragging:
            self._dragging = False
            self._snap_if_near_edge()
            return True

        return super().eventFilter(obj, event)

    # ---- 已删除：锁定相关功能 ----
    # ---- 已删除：尺寸调整相关功能 ----

    def _on_daily_cost_unhovered(self):
        """鼠标离开今日消耗标签 — 启动延迟关闭定时器"""
        self._popup_hide_timer.start(300)

    def _show_daily_popup(self):
        """鼠标悬停显示每日消耗弹窗（带渐入动画）"""
        data = self._get_weekly_consumption()
        self._daily_popup.update_data(data)

        # 定位到每日消耗label下方
        label_pos = self._daily_cost_ref.mapToGlobal(QPoint(0, self._daily_cost_ref.height()))
        self._daily_popup.move(label_pos.x(), label_pos.y() + 4)

        # 取消任何未执行的隐藏
        self._popup_hide_timer.stop()

        # 先设置为透明度0并显示，再渐入
        self._daily_popup.setWindowOpacity(0.0)
        self._daily_popup.show()
        self._daily_popup.raise_()

        self._popup_fade_anim = QPropertyAnimation(self._daily_popup, b"windowOpacity")
        self._popup_fade_anim.setDuration(200)
        self._popup_fade_anim.setStartValue(0.0)
        self._popup_fade_anim.setEndValue(1.0)
        self._popup_fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._popup_fade_anim.start()

    def _hide_daily_popup(self):
        """隐藏每日消耗弹窗（带渐出动画）"""
        if not self._daily_popup.isVisible():
            return
        self._popup_fade_anim = QPropertyAnimation(self._daily_popup, b"windowOpacity")
        self._popup_fade_anim.setDuration(150)
        self._popup_fade_anim.setStartValue(self._daily_popup.windowOpacity())
        self._popup_fade_anim.setEndValue(0.0)
        self._popup_fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._popup_fade_anim.finished.connect(self._daily_popup.hide)
        self._popup_fade_anim.start()

    def _hide_daily_popup_immediate(self):
        """立即隐藏弹窗（无动画，用于点击面板时）"""
        self._popup_hide_timer.stop()
        if self._daily_popup.isVisible():
            self._daily_popup.hide()

    # ---- 属性动画支持 ----
    def get_window_opacity(self):
        return self._opacity

    def set_window_opacity(self, opacity):
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    window_opacity = Property(float, get_window_opacity, set_window_opacity)

    def _get_anim_width(self):
        return self._anim_width

    def _set_anim_width(self, w):
        self._anim_width = w
        self.setFixedWidth(w)

    anim_width = Property(float, _get_anim_width, _set_anim_width)
