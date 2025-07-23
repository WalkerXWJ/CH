#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mac剪贴板历史管理器 - 菜单栏功能版
1. 移除主窗口上的设置按钮
2. 在菜单栏中实现置顶、透明度和排序功能
3. 保留所有原有功能
"""

import sys
import os
import pickle
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, 
                            QScrollArea, QPushButton, QHBoxLayout, QFrame, QSizePolicy,
                            QLineEdit, QTextEdit, QMessageBox, QDialog, QSlider, 
                            QComboBox, QFormLayout, QMenu, QSystemTrayIcon)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon, QColor, QTextOption, QAction, QGuiApplication
from AppKit import NSPasteboard, NSObject, NSData
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
import objc
from Foundation import NSDistributedNotificationCenter
from Cocoa import NSApplication, NSApp
import pyperclip

# 常量定义
MAX_HISTORY_ITEMS = 1000000  # 历史记录中保存的最大项目数量
ITEM_HEIGHT = 100  # 每个历史记录项的高度(像素)
MARGIN = 10  # 统一边距(像素)
CLIPBOARD_CHECK_INTERVAL = 0.5  # 剪贴板检查间隔(秒)
DEFAULT_OPACITY = 80  # 窗口默认透明度百分比(0-100)

class AboutDialog(QDialog):
    """关于对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于剪贴板历史管理器")
        self.setFixedSize(300, 200)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 应用图标和名称
        icon_label = QLabel()
        icon_label.setPixmap(QIcon.fromTheme("edit-copy").pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel("剪贴板历史管理器")
        name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        version_label = QLabel("版本 1.0")
        version_label.setStyleSheet("color: gray;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 描述文本
        desc_label = QLabel("一个简单的剪贴板历史管理工具\n支持文本和图片内容")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 确定按钮
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        # 添加到布局
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(version_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(ok_button)
        
        self.setLayout(layout)

class OpacityDialog(QDialog):
    """透明度设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置透明度")
        self.setFixedSize(300, 120)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 透明度滑块
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(30, 100)  # 30%-100%透明度
        self.slider.setValue(DEFAULT_OPACITY)
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        # 透明度值显示
        self.value_label = QLabel(f"{DEFAULT_OPACITY}%")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slider.valueChanged.connect(
            lambda v: self.value_label.setText(f"{v}%"))
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 添加到主布局
        layout.addWidget(self.slider)
        layout.addWidget(self.value_label)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

class SortDialog(QDialog):
    """排序规则设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置排序规则")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 排序选项
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "按修改时间(最旧在前)", 
            "按修改时间(最新在前)", 
            "按复制次数(最多在前)"
        ])
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 添加到主布局
        layout.addWidget(QLabel("选择排序规则:"))
        layout.addWidget(self.sort_combo)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

class ClipboardSignals(QObject):
    clipboardChanged = pyqtSignal(str, bytes)
    themeChanged = pyqtSignal(bool)

class ClipboardMonitor(NSObject):
    def init(self):
        self = objc.super(ClipboardMonitor, self).init()
        if not self:
            return None
            
        self.signals = ClipboardSignals()
        self.last_content = None
        self.current_theme_dark = False
        
        # 设置剪贴板变化通知
        center = NSDistributedNotificationCenter.defaultCenter()
        center.addObserver_selector_name_object_(
            self, 'clipboardChanged:', 'com.apple.pasteboard.clipboardChanged', None)
        
        # 定时检查剪贴板
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            CLIPBOARD_CHECK_INTERVAL, self, 'checkClipboard:', None, True)
        
        # 检查初始主题
        self.checkTheme_(None)
        # 定时检查主题变化
        self.theme_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, 'checkTheme:', None, True)
        
        return self
    
    def checkClipboard_(self, timer):
        """检查剪贴板内容变化"""
        pasteboard = NSPasteboard.generalPasteboard()
        
        # 检查文本内容
        if content := pasteboard.stringForType_("public.utf8-plain-text"):
            if content != self.last_content:
                self.signals.clipboardChanged.emit("text", content.encode('utf-8'))
                self.last_content = content
            return
        
        # 检查图片内容
        if image_data := pasteboard.dataForType_("public.tiff"):
            self.signals.clipboardChanged.emit("image", bytes(image_data))
            self.last_content = None
            return
        
        # 其他类型暂不处理
        self.last_content = None
    
    def checkTheme_(self, timer):
        """检查系统主题变化"""
        appearance = NSApp.effectiveAppearance()
        is_dark = "dark" in appearance.name().lower()
        if is_dark != self.current_theme_dark:
            self.current_theme_dark = is_dark
            self.signals.themeChanged.emit(is_dark)
    
    def clipboardChanged_(self, notification):
        """剪贴板变化通知处理"""
        self.checkClipboard_(None)

# 注册Objective-C选择器
ClipboardMonitor.clipboardChanged_ = objc.selector(
    ClipboardMonitor.clipboardChanged_,
    signature=b'v@:@'
)
ClipboardMonitor.checkClipboard_ = objc.selector(
    ClipboardMonitor.checkClipboard_,
    signature=b'v@:@'
)
ClipboardMonitor.checkTheme_ = objc.selector(
    ClipboardMonitor.checkTheme_,
    signature=b'v@:@'
)

NSTimer = objc.lookUpClass('NSTimer')

class ClipboardItemWidget(QWidget):
    """剪贴板历史项组件"""
    def __init__(self, content_type, content, timestamp, copy_count=0, is_pinned=False, parent=None, main_window=None):
        super().__init__(parent)
        self.content_type = content_type
        self.content = content
        self.timestamp = timestamp
        self.copy_count = copy_count
        self.is_pinned = is_pinned
        self.main_window = main_window
        self.is_pressed = False
        
        self.setup_ui()
        self.update_style()
        
    def setup_ui(self):
        """设置UI组件"""
        self.setFixedHeight(ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, 5, MARGIN, 5)  # 统一左右边距
        layout.setSpacing(5)
        
        # 顶部布局(时间和固定按钮)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)
        
        # 显示时间和复制次数
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        count_str = f"复制 {self.copy_count} 次" if self.copy_count > 0 else "未复制"
        self.time_label = QLabel(f"{time_str} | {count_str}")
        self.time_label.setStyleSheet("color: gray; font-size: 11px;")
        self.time_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.pin_button = QPushButton()
        self.pin_button.setFixedSize(20, 20)
        self.pin_button.setFlat(True)
        self.pin_button.setIconSize(QSize(16, 16))
        self.update_pin_icon()
        self.pin_button.clicked.connect(self.toggle_pin)
        
        top_layout.addWidget(self.time_label, stretch=1)
        top_layout.addWidget(self.pin_button, Qt.AlignmentFlag.AlignRight)
        
        # 内容显示区域
        self.content_display = QTextEdit()
        self.content_display.setReadOnly(True)
        self.content_display.setFrameShape(QFrame.Shape.NoFrame)
        self.content_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_display.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.content_display.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # 根据内容类型设置显示
        if self.content_type == "text":
            text = self.content.decode('utf-8') if isinstance(self.content, bytes) else str(self.content)
            self.content_display.setPlainText(text)
            self.content_display.setMaximumHeight(ITEM_HEIGHT - 30)
        elif self.content_type == "image":
            self.content_display.setPlainText("[图片]")
            self.content_display.setMaximumHeight(ITEM_HEIGHT - 30)
        
        # 添加到主布局
        layout.addLayout(top_layout)
        layout.addWidget(self.content_display)
        
        # 设置背景和阴影效果
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)
        
        # 设置整个widget可点击
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.update_style(pressed=True)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件处理"""
        if self.is_pressed and event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = False
            self.update_style(pressed=False)
            if not self.pin_button.underMouse():  # 如果点击的不是固定按钮
                self.main_window.copy_to_clipboard(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def enterEvent(self, event):
        """鼠标进入事件处理"""
        self.update_style(hover=True)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件处理"""
        self.update_style(hover=False)
        super().leaveEvent(event)
    
    def update_pin_icon(self):
        """更新固定按钮图标"""
        self.pin_button.setIcon(QIcon.fromTheme("pin" if self.is_pinned else "unpin"))
    
    def toggle_pin(self):
        """切换固定状态"""
        self.is_pinned = not self.is_pinned
        self.update_pin_icon()
        if self.main_window:
            self.main_window.pin_status_changed(self, self.is_pinned)

    def update_style(self, is_dark=None, hover=False, pressed=False):
        """更新组件样式"""
        if is_dark is None:
            is_dark = self.main_window.current_theme_dark if self.main_window else False
        
        # 根据主题设置颜色
        if is_dark:
            bg_color = QColor(50, 50, 50)
            border_color = QColor(70, 70, 70)
            text_color = QColor(220, 220, 220)
            hover_color = QColor(60, 60, 60)
            pressed_color = QColor(70, 70, 70)
        else:
            bg_color = QColor(255, 255, 255)
            border_color = QColor(230, 230, 230)
            text_color = QColor(50, 50, 50)
            hover_color = QColor(240, 240, 240)
            pressed_color = QColor(230, 230, 230)
        
        # 根据状态确定背景色
        current_bg = pressed_color if pressed else hover_color if hover else bg_color
        
        # 设置样式表
        self.setStyleSheet(f"""
            ClipboardItemWidget {{
                background-color: {current_bg.name()};
                border: 1px solid {border_color.name()};
                border-radius: 6px;
                padding: 3px;
            }}
            QTextEdit {{
                background-color: transparent;
                color: {text_color.name()};
                font-size: 12px;
                padding: 0;
                margin: 0;
            }}
        """)

class ClipboardHistoryWindow(QMainWindow):
    """剪贴板历史窗口"""
    def __init__(self):
        super().__init__()
        self.clipboard_history = []
        self.pinned_items = []
        self.is_first_run = True
        self.current_theme_dark = False
        self.opacity = DEFAULT_OPACITY / 100  # 初始透明度
        self.sort_rule = 0  # 0=按修改时间(最新在前), 1=按修改时间(最旧在前), 2=按复制次数(最多在前)
        self.always_on_top = True  # 默认窗口置顶
        
        self.set_initial_style()
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_clipboard_monitor()
        self.load_history()
        self.load_settings()
    
        self.update_clear_button_visibility()
        self.update_style()
    
    def set_initial_style(self):
        """设置初始样式"""
        appearance = NSApp.effectiveAppearance()
        self.current_theme_dark = "dark" in appearance.name().lower()
        
        # 设置窗口背景色
        bg_color = QColor(45, 45, 45) if self.current_theme_dark else QColor(250, 250, 250)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(f"QMainWindow {{ background-color: {bg_color.name()}; }}")
        self.setWindowOpacity(self.opacity)
    
    def setup_menu_bar(self):
        """设置macOS菜单栏"""
        menubar = self.menuBar()
        
        # 应用菜单
        app_menu = menubar.addMenu("剪贴板历史")
        
        # 置顶选项
        self.always_on_top_action = QAction("窗口置顶", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(self.always_on_top)
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        
        # 透明度选项
        opacity_action = QAction("设置透明度...", self)
        opacity_action.triggered.connect(self.show_opacity_dialog)
        
        # 排序选项
        sort_action = QAction("设置排序规则...", self)
        sort_action.triggered.connect(self.show_sort_dialog)
        
        # 关于选项
        about_action = QAction("关于...", self)
        about_action.triggered.connect(self.show_about)
        
        # 退出选项
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        
        # 添加到菜单
        app_menu.addAction(self.always_on_top_action)
        app_menu.addAction(opacity_action)
        app_menu.addAction(sort_action)
        app_menu.addSeparator()
        app_menu.addAction(about_action)
        app_menu.addAction(quit_action)
    
    def show_opacity_dialog(self):
        """显示透明度设置对话框"""
        dialog = OpacityDialog(self)
        dialog.slider.setValue(int(self.opacity * 100))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.opacity = dialog.slider.value() / 100
            self.setWindowOpacity(self.opacity)
            self.save_settings()
    
    def show_sort_dialog(self):
        """显示排序规则设置对话框"""
        dialog = SortDialog(self)
        dialog.sort_combo.setCurrentIndex(self.sort_rule)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.sort_rule = dialog.sort_combo.currentIndex()
            self.sort_history()
            self.update_history_display()
            self.save_settings()
    
    def toggle_always_on_top(self, checked):
        """切换窗口置顶状态"""
        self.always_on_top = checked
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        self.save_settings()
    
    def show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("剪贴板历史🍀")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        main_widget = QWidget()
        main_widget.setObjectName("MainWidget")
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)  # 统一边距
        layout.setSpacing(8)
        
        # 标题栏布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)
        
        self.title_label = QLabel("🍀剪贴板历史")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.count_label = QLabel()
        self.count_label.setStyleSheet("font-size: 11px; color: gray;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.count_label)
        layout.addLayout(title_layout)
        
        # 搜索框和清除按钮布局
        search_clear_layout = QHBoxLayout()
        search_clear_layout.setContentsMargins(0, 0, 0, 0)
        search_clear_layout.setSpacing(5)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索...")
        self.search_box.textChanged.connect(self.filter_history)
        
        self.clear_button = QPushButton("🧹清除")
        self.clear_button.setFixedSize(60, 28)
        self.clear_button.clicked.connect(self.clear_clipboard_history)
        
        search_clear_layout.addWidget(self.search_box)
        search_clear_layout.addWidget(self.clear_button)
        layout.addLayout(search_clear_layout)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")  # 添加ID以便样式化
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)  # 右侧留出滚动条空间
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch(1)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        
        # 设置窗口大小
        self.resize(350, 500)
        self.setStatusBar(None)
    
    def load_settings(self):
        """加载设置"""
        path = os.path.expanduser("~/.clipboard_settings")
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    settings = pickle.load(f)
                    self.opacity = settings.get('opacity', DEFAULT_OPACITY / 100)
                    self.sort_rule = settings.get('sort_rule', 0)
                    self.always_on_top = settings.get('always_on_top', True)
                    
                    # 应用设置
                    self.setWindowOpacity(self.opacity)
                    self.always_on_top_action.setChecked(self.always_on_top)
                    self.toggle_always_on_top(self.always_on_top)
            except Exception as e:
                print(f"加载设置失败: {e}")
    
    def save_settings(self):
        """保存设置"""
        path = os.path.expanduser("~/.clipboard_settings")
        try:
            with open(path, 'wb') as f:
                pickle.dump({
                    'opacity': self.opacity,
                    'sort_rule': self.sort_rule,
                    'always_on_top': self.always_on_top
                }, f)
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def setup_clipboard_monitor(self):
        """设置剪贴板监视器"""
        self.monitor = ClipboardMonitor.alloc().init()
        if self.monitor:
            self.monitor.signals.clipboardChanged.connect(self.add_to_clipboard_history)
            self.monitor.signals.themeChanged.connect(self.handle_theme_change)
    
    def handle_theme_change(self, is_dark):
        """处理主题变化"""
        if is_dark != self.current_theme_dark:
            self.current_theme_dark = is_dark
            self.update_style()
            for widget in self.findChildren(ClipboardItemWidget):
                widget.update_style(is_dark)
    
    def load_history(self):
        """加载历史记录"""
        path = os.path.expanduser("~/.clipboard_history")
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    history = pickle.load(f)
                    # 现在每个历史项是 (content_type, content, timestamp, copy_count, is_pinned)
                    self.clipboard_history = [item for item in history if not item[4]]  # 未固定的
                    self.pinned_items = [item for item in history if item[4]]  # 固定的
                    
                    # 按当前排序规则排序
                    self.sort_history()
                    
                    self.update_history_display()
                
                self.is_first_run = False
            except Exception as e:
                print(f"加载历史记录失败: {e}")
                # 加载失败时初始化空历史
                self.clipboard_history = []
                self.pinned_items = []
        else:
            if self.is_first_run:
                # 首次运行添加欢迎消息
                self.add_to_clipboard_history("text", "欢迎使用剪贴板历史管理器")
                self.add_to_clipboard_history("text", "点击项目将内容复制到剪贴板")
                self.is_first_run = False
        
        # 确保显示更新
        self.update_history_display()
        self.update_clear_button_visibility()
    
    def sort_history(self):
        """对所有历史记录进行排序"""
        # 合并固定和非固定项目
        all_items = self.clipboard_history + self.pinned_items
        
        # 根据当前排序规则排序
        if self.sort_rule == 0:  # 按修改时间(最新在前)
            all_items.sort(key=lambda x: x[2], reverse=True)
        elif self.sort_rule == 1:  # 按修改时间(最旧在前)
            all_items.sort(key=lambda x: x[2], reverse=False)
        elif self.sort_rule == 2:  # 按复制次数(最多在前)
            all_items.sort(key=lambda x: x[3], reverse=False)
        
        # 重新分离固定和非固定项目
        self.clipboard_history = [item for item in all_items if not item[4]]
        self.pinned_items = [item for item in all_items if item[4]]
    
    def save_history(self):
        """保存历史记录"""
        path = os.path.expanduser("~/.clipboard_history")
        try:
            with open(path, 'wb') as f:
                # 保存所有历史项，包括复制次数和固定状态
                pickle.dump(self.clipboard_history + self.pinned_items, f)
        except Exception as e:
            print(f"保存历史记录失败: {e}")
    
    def add_to_clipboard_history(self, content_type, content):
        """
        添加内容到剪贴板历史
        优化点:
        1. 避免重复内容
        2. 更新现有项目的时间戳
        3. 限制历史记录数量
        """
        # 如果内容为空，不添加
        if not content:
            return
            
        # 检查内容是否已存在
        if self.content_exists(content_type, content):
            return
            
        # 如果是文本内容且是字节类型，解码为字符串
        if content_type == "text" and isinstance(content, bytes):
            try:
                content = content.decode('utf-8')
            except UnicodeDecodeError:
                # 如果解码失败，使用原始字节数据
                pass
        
        # 更新现有项目的时间戳(如果存在且未固定)
        for i, (item_type, item_content, _, copy_count, is_pinned) in enumerate(self.clipboard_history):
            if self.compare_content(item_type, item_content, content_type, content) and not is_pinned:
                self.clipboard_history[i] = (item_type, item_content, datetime.now(), copy_count, False)
                self.sort_history()
                self.update_history_display()
                self.update_clear_button_visibility()
                return
        
        # 添加新项目到历史记录开头，初始复制次数为0
        self.clipboard_history.insert(0, (content_type, content, datetime.now(), 0, False))
        
        # 限制历史记录数量
        if len(self.clipboard_history) > MAX_HISTORY_ITEMS:
            # 保留所有固定项目
            pinned = [item for item in self.clipboard_history if item[4]]
            # 保留最新的非固定项目
            non_pinned = [item for item in self.clipboard_history if not item[4]]
            non_pinned = non_pinned[:MAX_HISTORY_ITEMS - len(pinned)]
            # 合并固定和非固定项目
            self.clipboard_history = pinned + non_pinned
        
        # 排序并更新显示
        self.sort_history()
        self.update_history_display()
        self.update_clear_button_visibility()
        self.save_history()
    
    def compare_content(self, type1, content1, type2, content2):
        """比较两个内容是否相同"""
        if type1 != type2:
            return False
            
        if type1 == "text":
            # 处理文本内容比较
            text1 = content1.decode('utf-8') if isinstance(content1, bytes) else str(content1)
            text2 = content2.decode('utf-8') if isinstance(content2, bytes) else str(content2)
            return text1.strip() == text2.strip()
        elif type1 == "image":
            # 图片内容直接比较字节数据
            return content1 == content2
        return False
    
    def update_clear_button_visibility(self):
        """更新清除按钮可见性"""
        total_count = len(self.clipboard_history) + len(self.pinned_items)
        self.clear_button.setVisible(total_count > 0)
    
    def content_exists(self, content_type, content):
        """检查内容是否已存在于历史记录中"""
        for item in self.clipboard_history + self.pinned_items:
            if self.compare_content(item[0], item[1], content_type, content):
                return True
        return False
    
    def update_history_display(self):
        """更新历史记录显示"""
        # 清除现有项(保留最后的拉伸项)
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # 先显示已固定的项目
        for pinned_item in self.pinned_items:
            item_type, content, timestamp, copy_count, _ = pinned_item
            item_widget = ClipboardItemWidget(item_type, content, timestamp, copy_count, True, main_window=self)
            self.scroll_layout.insertWidget(0, item_widget)
        
        # 然后显示未固定的项目
        for item in self.clipboard_history:
            item_type, content, timestamp, copy_count, is_pinned = item
            if not is_pinned:
                item_widget = ClipboardItemWidget(item_type, content, timestamp, copy_count, False, main_window=self)
                self.scroll_layout.insertWidget(len(self.pinned_items), item_widget)
        
        # 更新计数标签
        total_count = len(self.clipboard_history) + len(self.pinned_items)
        pinned_count = len(self.pinned_items)
        self.count_label.setText(f"{total_count} 项 | 钉 {pinned_count}")
    
    def filter_history(self, text):
        """过滤历史记录"""
        text = text.lower()
        for i in range(self.scroll_layout.count() - 1):
            item = self.scroll_layout.itemAt(i)
            if item.widget():
                widget = item.widget()
                if widget.content_type == "text":
                    # 文本内容过滤
                    content = widget.content.decode('utf-8').lower() if isinstance(widget.content, bytes) else str(widget.content).lower()
                    widget.setVisible(text in content)
                else:
                    # 图片内容默认隐藏
                    widget.setVisible(not text)
    
    def copy_to_clipboard(self, item_widget):
        """
        复制内容到系统剪贴板
        并更新复制次数和最后修改时间
        """
        try:
            content_type = item_widget.content_type
            content = item_widget.content
            
            if content_type == "text":
                # 确保内容是字符串类型
                text = content.decode('utf-8') if isinstance(content, bytes) else str(content)
                pyperclip.copy(text)
                self.show_message("已复制到剪贴板", 1000)
            elif content_type == "image":
                # 处理图片内容
                pasteboard = NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                ns_data = NSData.dataWithBytes_length_(content, len(content))
                pasteboard.setData_forType_(ns_data, "public.tiff")
                self.show_message("图片已复制到剪贴板", 1000)
            
            # 更新复制次数和最后修改时间
            self.update_item_copy_count(item_widget)
            
        except Exception as e:
            error_msg = f"复制失败: {str(e)}"
            print(error_msg)
            self.show_error_message("复制失败", error_msg)
    
    def update_item_copy_count(self, item_widget):
        """更新项目的复制次数和最后修改时间"""
        # 查找项目在历史记录中的位置
        for i, (item_type, item_content, _, item_copy_count, is_pinned) in enumerate(self.clipboard_history):
            if (item_type == item_widget.content_type and 
                self.compare_content(item_type, item_content, item_widget.content_type, item_widget.content) and not is_pinned):
                # 更新复制次数和时间戳
                self.clipboard_history[i] = (
                    item_type, item_content, datetime.now(), item_copy_count + 1, False
                )
                break
        
        # 查找项目在固定列表中的位置
        for i, (item_type, item_content, _, item_copy_count, is_pinned) in enumerate(self.pinned_items):
            if (item_type == item_widget.content_type and 
                self.compare_content(item_type, item_content, item_widget.content_type, item_widget.content) and is_pinned):
                # 更新复制次数和时间戳
                self.pinned_items[i] = (
                    item_type, item_content, datetime.now(), item_copy_count + 1, True
                )
                break
        
        # 重新排序并更新显示
        self.sort_history()
        self.update_history_display()
        self.save_history()
    
    def show_message(self, message, timeout=0):
        """显示临时消息"""
        if not hasattr(self, 'message_label'):
            self.message_label = QLabel(self)
            self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.message_label.setStyleSheet("""
                background-color: rgba(0, 0, 0, 180);
                color: white;
                padding: 5px;
                border-radius: 4px;
            """)
            self.message_label.hide()
        
        self.message_label.setText(message)
        self.message_label.adjustSize()
        self.message_label.move(
            (self.width() - self.message_label.width()) // 2,
            self.height() - self.message_label.height() - 20
        )
        self.message_label.show()
        
        if timeout > 0:
            QTimer.singleShot(timeout, self.message_label.hide)
    
    def show_error_message(self, title, message):
        """显示错误消息"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def pin_status_changed(self, widget, is_pinned):
        """处理固定状态变化"""
        content_type = widget.content_type
        content = widget.content
        timestamp = datetime.now()  # 更新为当前时间
        copy_count = widget.copy_count
        
        # 查找并更新历史记录中的项目
        for i, (item_type, item_content, _, item_copy_count, _) in enumerate(self.clipboard_history):
            if self.compare_content(item_type, item_content, content_type, content) and not self.is_item_pinned_at_index(i):
                self.clipboard_history[i] = (item_type, item_content, timestamp, item_copy_count, is_pinned)
                break
        
        # 更新固定项目列表
        if is_pinned:
            # 添加到固定列表
            self.pinned_items.append((content_type, content, timestamp, copy_count, True))
            # 从历史记录中移除
            self.clipboard_history = [item for item in self.clipboard_history 
                                    if not self.compare_content(item[0], item[1], content_type, content)]
        else:
            # 从固定列表中移除
            self.pinned_items = [item for item in self.pinned_items 
                               if not self.compare_content(item[0], item[1], content_type, content)]
            # 添加到历史记录开头
            self.clipboard_history.insert(0, (content_type, content, timestamp, copy_count, False))
        
        # 重新排序并更新显示
        self.sort_history()
        self.update_history_display()
        self.update_clear_button_visibility()
        self.save_history()
    
    def is_item_pinned_at_index(self, index):
        """检查指定索引的项目是否已固定"""
        if 0 <= index < len(self.clipboard_history):
            return self.clipboard_history[index][4]
        return False
    
    def clear_clipboard_history(self):
        """清除剪贴板历史（保留被钉住的项目）"""
        # 确认对话框
        reply = QMessageBox.question(
            self, '确认清除',
            '确定要清除所有未被固定的剪贴板历史吗?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 只清除未被钉住的项目
            self.clipboard_history = [item for item in self.clipboard_history if item[4]]  # 只保留固定项目
            
            # 更新显示
            self.update_history_display()
            self.update_clear_button_visibility()
            self.save_history()
            
            # 显示清除完成提示
            self.show_message("已清除未被固定的历史记录", 2000)
    
    def update_style(self):
        """更新窗口样式"""
        if self.current_theme_dark:
            bg_qcolor = QColor(45, 45, 45)
            text_qcolor = QColor(220, 220, 220)
            border_color = QColor(70, 70, 70)
        else:
            bg_qcolor = QColor(250, 250, 250)
            text_qcolor = QColor(50, 50, 50)
            border_color = QColor(210, 210, 210)
        
        self.setStyleSheet(f"""
            #MainWidget {{
                background-color: {bg_qcolor.name()};
                color: {text_qcolor.name()};
                border: 1px solid {border_color.name()};
                border-radius: 8px;
                padding: 8px;
            }}
            
            QScrollArea {{
                border: none;
            }}
            
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {border_color.name()};
                min-height: 20px;
                border-radius: 3px;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
            }}
            
            QPushButton {{
                background-color: {bg_qcolor.lighter(110).name()};
                border: 1px solid {border_color.name()};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }}
            
            QPushButton:hover {{
                background-color: {bg_qcolor.lighter(120).name()};
            }}
            
            QPushButton:pressed {{
                background-color: {bg_qcolor.lighter(90).name()};
            }}
            
            QLineEdit {{
                border: 1px solid {border_color.name()};
                border-radius: 4px;
                padding: 4px;
                background: {bg_qcolor.lighter(105).name()};
                font-size: 12px;
            }}
        """)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理 - 用于窗口拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件处理 - 用于窗口拖动"""
        if hasattr(self, 'drag_position') and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用信息，有助于在macOS上正确显示
    app.setApplicationName("Clipboard History")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("ClipboardManager")
    
    window = ClipboardHistoryWindow()
    window.show()
    sys.exit(app.exec())
