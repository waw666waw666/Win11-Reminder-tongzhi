import os
import sys
import json
import logging
import threading
import time
import queue
import tkinter as tk
from tkinter import messagebox
import winreg # 用于操作 Windows 注册表实现自启动
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from win11toast import toast
import winshell
from win32com.client import Dispatch
import win32event
import win32api
import winerror
import win32gui
import win32con

# ==========================================
# 视觉与 UI 规范 (UI/UX) - 现代 macOS 风格
# ==========================================
COLORS = {
    "accent": "#007AFF",         # 标准 iOS/macOS 蓝色
    "accent_hover": "#0062CC",   # 深蓝色 (悬停)
    "accent_light": "#E5F1FF",   # 极浅蓝色 (用于“试一下”按钮)
    "background": "#F5F5F7",     # macOS 系统浅色背景
    "card_bg": "#FFFFFF",
    "text_main": "#1D1D1F",      # 深黑色 (Apple 规范)
    "text_secondary": "#86868B", # 次要灰色 (Apple 规范)
    "border": "#D2D2D7",
    "danger": "#FF3B30",         # 标准 iOS 红色
    "danger_light": "#FFE9E8",   # 极浅红色 (用于删除按钮背景)
    "success": "#34C759",        # 标准 iOS 绿色
    "hover": "#E8E8ED"
}

FONT_NAME = "Microsoft YaHei UI"

APP_NAME = "提醒管家"

# 确定基础路径
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe，配置文件保存在 exe 同级目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 如果是源码运行，配置文件保存在当前脚本同级目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "error.log")
# 注意：打包后 icon 仍然在临时目录中（资源文件），所以 icon 的路径逻辑可能需要单独处理
# 这里我们假设 icon 是作为资源打包进去的，或者用户在目录下放了 icon
# 为了兼容性，我们优先从资源目录找 icon，找不到再从 BASE_DIR 找
if getattr(sys, 'frozen', False):
    # PyInstaller 临时资源目录
    RESOURCE_DIR = sys._MEIPASS
else:
    RESOURCE_DIR = BASE_DIR

ICON_FILE = os.path.join(RESOURCE_DIR, "app_icon.ico")

def create_app_icon():
    """生成应用图标文件"""
    if os.path.exists(ICON_FILE):
        return
    try:
        size = 256
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # 背景圆角矩形
        draw.rounded_rectangle([16, 16, 240, 240], radius=60, fill="#007AFF")
        # 简单的闹钟形状 (白色)
        draw.ellipse([60, 80, 196, 216], outline="white", width=12)
        draw.line([128, 148, 128, 112], fill="white", width=12)
        draw.line([128, 148, 168, 148], fill="white", width=12)
        draw.arc([40, 40, 100, 100], start=180, end=0, fill="white", width=12)
        draw.arc([156, 40, 216, 40+60], start=180, end=0, fill="white", width=12)
        image.save(ICON_FILE, format='ICO')
    except Exception as e:
        logging.error(f"生成图标失败: {e}")

# ==========================================
# 核心架构：日志与错误管理
# ==========================================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def show_error_and_exit(msg):
    logging.error(msg)
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("启动失败", f"程序启动时遇到错误：\n{msg}\n详情请查看 error.log")
    sys.exit(1)

# ==========================================
# 数据持久化与配置管理
# ==========================================
class AutoStartManager:
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "ReminderManager"

    @staticmethod
    def set_autostart(enable=True):
        try:
            # 获取当前可执行文件路径
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                # 开发环境下使用 pythonw.exe 运行当前脚本
                app_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                AutoStartManager.REG_PATH, 
                0, 
                winreg.KEY_ALL_ACCESS
            )
            
            if enable:
                winreg.SetValueEx(key, AutoStartManager.APP_NAME, 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, AutoStartManager.APP_NAME)
                except FileNotFoundError:
                    pass # 如果本来就没有设置，忽略错误
                    
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"自启动设置失败: {e}")
            return False

    @staticmethod
    def is_autostart_enabled():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                AutoStartManager.REG_PATH, 
                0, 
                winreg.KEY_READ
            )
            winreg.QueryValueEx(key, AutoStartManager.APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

class ConfigManager:
    @staticmethod
    def load():
        if not os.path.exists(CONFIG_FILE):
            default_config = {"tasks": []}
            ConfigManager.save(default_config)
            return default_config
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            return {"tasks": []}

    @staticmethod
    def save(data):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存配置失败: {e}")

# ==========================================
# 任务调度与通知引擎
# ==========================================
class TaskScheduler(threading.Thread):
    def __init__(self, task_queue):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.running = True
        self.tasks = []
        self.last_triggered = {} # task_id -> last_time

    def update_tasks(self, tasks):
        self.tasks = tasks

    def run(self):
        while self.running:
            now = time.time()
            for task in self.tasks:
                task_id = task.get("id")
                interval = float(task.get("interval", 1)) * 60 # 分钟转秒
                
                if task_id not in self.last_triggered:
                    self.last_triggered[task_id] = now
                    continue
                
                if now - self.last_triggered[task_id] >= interval:
                    self.trigger_task(task)
                    self.last_triggered[task_id] = now
            
            # 检查是否有立即触发的任务
            try:
                while not self.task_queue.empty():
                    msg = self.task_queue.get_nowait()
                    if msg["type"] == "test_trigger":
                        self.trigger_task(msg["task"])
            except queue.Empty:
                pass
                
            time.sleep(1)

    def trigger_task(self, task):
        try:
            toast(
                task.get("title", "提醒"),
                task.get("content", "时间到了！"),
                app_id=APP_NAME
            )
        except Exception as e:
            logging.error(f"发送通知失败: {e}")

# ==========================================
# UI 界面：主窗口与组件
# ==========================================
class CustomConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, on_confirm):
        super().__init__(master)
        self.title(title)
        self.geometry("340x200")
        self.configure(fg_color=COLORS["card_bg"])
        self.on_confirm = on_confirm
        
        # 隐藏标题栏以实现更圆润的外观 (可选，但为了吸引力，我们可以保持标准但增加内容圆润度)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        # 居中显示
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (340 // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (200 // 2)
        self.geometry(f"+{x}+{y}")

        # 容器
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=25, pady=25)

        # 标题
        ctk.CTkLabel(
            self.main_frame, text=title, font=(FONT_NAME, 18, "bold"), 
            text_color=COLORS["text_main"]
        ).pack(pady=(0, 10))

        # 消息
        ctk.CTkLabel(
            self.main_frame, text=message, font=(FONT_NAME, 13), 
            text_color=COLORS["text_secondary"], wraplength=280
        ).pack(pady=(0, 20))

        # 按钮容器
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x")

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="算啦", width=120, height=38,
            fg_color="#F2F2F2", text_color=COLORS["text_main"],
            hover_color="#E8E8E8", corner_radius=19,
            font=(FONT_NAME, 12),
            command=self.destroy
        )
        self.cancel_btn.pack(side="left", padx=(0, 10))

        self.confirm_btn = ctk.CTkButton(
            btn_frame, text="确定", width=120, height=38,
            fg_color=COLORS["danger"], text_color="white",
            hover_color="#FF7070", corner_radius=19,
            font=(FONT_NAME, 12, "bold"),
            command=self.confirm
        )
        self.confirm_btn.pack(side="right")

    def confirm(self):
        self.on_confirm()
        self.destroy()

class TaskCard(ctk.CTkFrame):
    def __init__(self, master, task, on_edit, on_test, on_delete):
        super().__init__(
            master, 
            fg_color=COLORS["card_bg"], 
            corner_radius=24, 
            border_width=0
        )
        self.task = task
        
        # 布局
        self.grid_columnconfigure(0, weight=1)
        
        # 左侧蓝色装饰条 (匹配图片风格)
        self.accent_bar = ctk.CTkFrame(
            self, width=6, fg_color=COLORS["accent"], corner_radius=3
        )
        self.accent_bar.place(relx=0, rely=0.2, relheight=0.6, x=15)

        # 容器：内容区 (调整内边距，移除圆圈空间)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=(30, 20), pady=16)
        
        self.title_label = ctk.CTkLabel(
            self.content_frame, text=task["title"], 
            font=(FONT_NAME, 16, "bold"), 
            text_color=COLORS["text_main"]
        )
        self.title_label.pack(anchor="w")
        
        self.content_label = ctk.CTkLabel(
            self.content_frame, text=task["content"], 
            font=(FONT_NAME, 13), 
            text_color=COLORS["text_secondary"]
        )
        self.content_label.pack(anchor="w", pady=(2, 4))
        
        self.info_label = ctk.CTkLabel(
            self.content_frame, text=f"每 {task['interval']} 分钟提醒", 
            font=(FONT_NAME, 12), 
            text_color=COLORS["accent"]
        )
        self.info_label.pack(anchor="w")
        
        # 容器：操作区
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=0, column=1, padx=(0, 20))
        
        self.test_btn = ctk.CTkButton(
            self.action_frame, text="试一下", width=60, height=32,
            fg_color=COLORS["accent_light"], text_color=COLORS["accent"],
            hover_color="#D1E8FF",
            corner_radius=16, font=(FONT_NAME, 11, "bold"),
            command=lambda: on_test(task)
        )
        self.test_btn.pack(side="left", padx=3)
        self.test_btn.configure(cursor="hand2")

        self.edit_btn = ctk.CTkButton(
            self.action_frame, text="编辑", width=60, height=32,
            fg_color=COLORS["accent"], text_color="white",
            hover_color=COLORS["accent_hover"],
            corner_radius=16, font=(FONT_NAME, 11, "bold"),
            command=lambda: on_edit(task)
        )
        self.edit_btn.pack(side="left", padx=3)
        self.edit_btn.configure(cursor="hand2")

        # 加载删除图标
        icon_path = os.path.join(BASE_DIR, "delete_icon.png")
        self.del_img = ctk.CTkImage(
            light_image=Image.open(icon_path),
            dark_image=Image.open(icon_path),
            size=(16, 16)
        )

        self.del_btn = ctk.CTkButton(
            self.action_frame, image=self.del_img, text="", width=32, height=32,
            fg_color=COLORS["danger_light"], hover_color="#FFDADA",
            corner_radius=16,
            command=lambda: on_delete(task)
        )
        self.del_btn.pack(side="left", padx=(10, 0))
        self.del_btn.configure(cursor="hand2")

        # 绑定事件
        for widget in [self, self.content_frame, self.title_label, self.content_label, self.info_label]:
            widget.bind("<Double-1>", lambda e: on_edit(task))
            widget.bind("<Button-3>", self.show_menu)
        
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑任务", command=lambda: on_edit(task))
        self.menu.add_command(label="立即测试", command=lambda: on_test(task))
        self.menu.add_separator()
        self.menu.add_command(label="删除任务", command=lambda: on_delete(task), foreground="red")

    def show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, task=None, on_save=None):
        super().__init__(master)
        
        # 1. 基础配置
        self.title("任务设置")
        self.geometry("400x520") # 增加高度
        self.configure(fg_color=COLORS["card_bg"])
        self.on_save = on_save
        self.task_id = task["id"] if task else str(int(time.time() * 1000))
        
        # 2. 窗口行为增强
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        
        # 3. 居中显示
        self.update_idletasks()
        win_w, win_h = 400, 520
        x = master.winfo_x() + (master.winfo_width() // 2) - (win_w // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (win_h // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # 4. 界面构建
        self.setup_ui(task)
        
        # 5. 事件绑定
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

    def setup_ui(self, task):
        # 标题区域 (Top)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(30, 15), padx=40)
        
        ctk.CTkLabel(
            header_frame, text="任务设置", 
            font=(FONT_NAME, 26, "bold"), 
            text_color=COLORS["accent"]
        ).pack(side="left")

        # 底部按钮 (Bottom) - 先 pack 底部，确保不被截断
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=40, pady=(10, 30))

        self.save_btn = ctk.CTkButton(
            footer_frame, text="保存设置", height=46,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="white", font=(FONT_NAME, 14, "bold"), corner_radius=23,
            command=self.save
        )
        self.save_btn.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.cancel_btn = ctk.CTkButton(
            footer_frame, text="取消", height=46, width=90,
            fg_color="#F2F2F7", text_color=COLORS["text_main"],
            hover_color="#E8E8ED", font=(FONT_NAME, 14), corner_radius=23,
            command=self.destroy
        )
        self.cancel_btn.pack(side="right")

        # 内容容器 (Middle) - 填充剩余空间
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40)

        # 封装输入项构建逻辑
        self.title_entry = self.create_input_item(container, "任务名称", "例如：喝水提醒", task["title"] if task else "")
        self.content_entry = self.create_input_item(container, "提醒内容", "例如：该喝水啦！", task["content"] if task else "")
        self.interval_entry = self.create_input_item(container, "循环间隔 (分钟)", "30", str(task["interval"]) if task else "30")

    def create_input_item(self, parent, label_text, placeholder, initial_value):
        item_frame = ctk.CTkFrame(parent, fg_color="transparent")
        item_frame.pack(fill="x", pady=(0, 18)) # 稍微减少间距
        
        ctk.CTkLabel(
            item_frame, text=label_text, 
            font=(FONT_NAME, 13, "bold"), 
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w", pady=(0, 6))
        
        entry = ctk.CTkEntry(
            item_frame, height=44, placeholder_text=placeholder,
            fg_color="#F2F2F7", border_width=0,
            text_color=COLORS["text_main"], corner_radius=10,
            font=(FONT_NAME, 14)
        )
        entry.pack(fill="x")
        if initial_value:
            entry.insert(0, initial_value)
        return entry

    def save(self):
        try:
            title = self.title_entry.get().strip()
            content = self.content_entry.get().strip()
            interval_str = self.interval_entry.get().strip()
            
            if not title or not content:
                raise ValueError("标题和内容不能为空哦~")
            
            try:
                interval = float(interval_str)
            except ValueError:
                raise ValueError("间隔必须是一个数字呢")
                
            if interval <= 0:
                raise ValueError("间隔需要大于 0 呀")
                
            task = {
                "id": self.task_id,
                "title": title,
                "content": content,
                "interval": interval
            }
            if self.on_save:
                self.on_save(task)
            self.destroy()
        except Exception as e:
            messagebox.showwarning("提示", str(e))

class ReminderApp(ctk.CTk):
    def __init__(self, silent=True):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("480x600")
        self.configure(fg_color=COLORS["background"])
        
        # 消息队列
        self.msg_queue = queue.Queue()
        
        # 配置与任务
        self.config = ConfigManager.load()
        self.scheduler = TaskScheduler(self.msg_queue)
        self.scheduler.update_tasks(self.config["tasks"])
        self.scheduler.start()
        
        # 预先创建图标，防止 TaskCard 加载失败
        self.create_delete_icon()
        
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # 快捷方式
        self.create_shortcut()

        # 始终创建托盘图标
        self.create_tray_icon()

        if silent:
            # 初始隐藏
            self.withdraw()

    def setup_ui(self):
        # 顶部标题栏 (仅此处允许拖动窗口)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=30, pady=(40, 20))
        
        # 绑定拖动事件到标题栏及其子组件
        for widget in [self.header_frame]:
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)

        self.title_label = ctk.CTkLabel(
            self.header_frame, text=APP_NAME, 
            font=(FONT_NAME, 32, "bold"), 
            text_color=COLORS["text_main"]
        )
        self.title_label.pack(side="left")
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)

        # 自启动开关
        self.autostart_switch = ctk.CTkSwitch(
            self.header_frame, text="开机自启动", 
            font=(FONT_NAME, 12),
            text_color=COLORS["text_secondary"],
            progress_color=COLORS["accent"],
            command=self.toggle_autostart
        )
        self.autostart_switch.pack(side="left", padx=(20, 0), pady=(8, 0))
        
        # 根据当前状态初始化开关
        if AutoStartManager.is_autostart_enabled():
            self.autostart_switch.select()
        
        self.add_btn = ctk.CTkButton(
            self.header_frame, text="+ 新建任务", width=110, height=38,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="white",
            font=(FONT_NAME, 13, "bold"), corner_radius=19,
            command=self.open_add_dialog
        )
        self.add_btn.pack(side="right")
        self.add_btn.configure(cursor="hand2")

        # 滚动列表
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", 
            scrollbar_button_color="#E0E0E0",
            scrollbar_button_hover_color="#CCCCCC"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        
        self.refresh_list()

    def toggle_autostart(self):
        enable = self.autostart_switch.get() == 1
        AutoStartManager.set_autostart(enable)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def create_delete_icon(self):
        """生成一个精致的红色垃圾桶图标"""
        icon_path = os.path.join(BASE_DIR, "delete_icon.png")
        if os.path.exists(icon_path):
            return
        
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = COLORS["danger"]
        
        # 绘制垃圾桶盖子
        draw.rounded_rectangle([16, 12, 48, 18], radius=2, fill=color)
        draw.rounded_rectangle([26, 8, 38, 12], radius=2, fill=color)
        
        # 绘制垃圾桶桶身
        draw.rounded_rectangle([18, 20, 46, 56], radius=4, fill=color)
        
        # 绘制桶身上的竖线
        for x in [24, 32, 40]:
            draw.line([x, 28, x, 48], fill="white", width=3)
            
        image.save(icon_path)

    def refresh_list(self):
        for child in self.scroll_frame.winfo_children():
            child.destroy()
            
        self.cards = [] # 存储所有卡片引用
        for task in self.config["tasks"]:
            card = TaskCard(
                self.scroll_frame, task, 
                on_edit=self.open_edit_dialog,
                on_test=self.trigger_test,
                on_delete=self.delete_task
            )
            card.pack(fill="x", pady=8, padx=5)
            self.cards.append(card)

    def open_add_dialog(self):
        SettingsDialog(self, on_save=self.save_task)

    def open_edit_dialog(self, task):
        SettingsDialog(self, task=task, on_save=self.save_task)

    def save_task(self, task):
        # 更新或添加
        tasks = self.config["tasks"]
        found = False
        for i, t in enumerate(tasks):
            if t["id"] == task["id"]:
                tasks[i] = task
                found = True
                break
        if not found:
            tasks.append(task)
            
        self.config["tasks"] = tasks
        ConfigManager.save(self.config)
        self.scheduler.update_tasks(tasks)
        self.refresh_list()

    def delete_task(self, task):
        def do_delete():
            self.config["tasks"] = [t for t in self.config["tasks"] if t["id"] != task["id"]]
            ConfigManager.save(self.config)
            self.scheduler.update_tasks(self.config["tasks"])
            self.refresh_list()
            
        CustomConfirmDialog(
            self, 
            title="删除任务", 
            message=f"确定要删除任务 '{task['title']}' 吗？\n删除后将无法恢复。", 
            on_confirm=do_delete
        )

    def trigger_test(self, task):
        self.msg_queue.put({"type": "test_trigger", "task": task})

    def hide_to_tray(self):
        self.withdraw()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def create_tray_icon(self):
        if hasattr(self, 'tray_icon'):
            return
        # 创建一个深蓝色圆角闹钟图标
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # 背景圆角矩形
        draw.rounded_rectangle([4, 4, 60, 60], radius=15, fill="#003366")
        # 简单的闹钟形状
        draw.ellipse([15, 20, 49, 54], outline="white", width=3)
        draw.line([32, 37, 32, 28], fill="white", width=3)
        draw.line([32, 37, 42, 37], fill="white", width=3)
        draw.arc([10, 10, 25, 25], start=180, end=0, fill="white", width=3)
        draw.arc([39, 10, 54, 25], start=180, end=0, fill="white", width=3)

        menu = (
            item('显示主界面', self.show_window, default=True),
            item('退出', self.quit_app)
        )
        self.tray_icon = pystray.Icon("remind_manager", image, "提醒管家", menu)
        # 双击托盘图标显示窗口 (部分平台支持)
        self.tray_icon.on_activate = lambda: self.show_window()
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def quit_app(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.scheduler.running = False
        self.quit()
        sys.exit(0)

    def create_shortcut(self):
        try:
            create_app_icon()
            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{APP_NAME}.lnk")
            
            # 使用 pythonw.exe 隐藏控制台
            python_exe = sys.executable
            pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = python_exe

            # 检查是否需要更新快捷方式
            # 手动点击快捷方式时不带 --silent，以便显示主界面
            should_create = True
            if os.path.exists(path):
                try:
                    shell = Dispatch('WScript.Shell')
                    shortcut = shell.CreateShortCut(path)
                    if "pythonw.exe" in shortcut.Targetpath.lower() and \
                       shortcut.WorkingDirectory == BASE_DIR and \
                       "--silent" not in shortcut.Arguments:
                        should_create = False
                except:
                    pass
            
            if should_create:
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(path)
                shortcut.Targetpath = pythonw_exe
                shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
                shortcut.WorkingDirectory = BASE_DIR
                shortcut.IconLocation = ICON_FILE if os.path.exists(ICON_FILE) else pythonw_exe
                shortcut.Description = "提醒管家 - macOS 风格提醒工具"
                shortcut.save()
        except Exception as e:
            logging.error(f"创建快捷方式失败: {e}")

# ==========================================
# 程序入口
# ==========================================
if __name__ == "__main__":
    # 单例运行检测
    mutex_name = "Global\\ReminderApp_SingleInstance_Mutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_error = win32api.GetLastError()
    
    if last_error == winerror.ERROR_ALREADY_EXISTS:
        # 如果已经存在，尝试寻找并显示已运行的窗口
        # Tkinter 的窗口标题通常就是 APP_NAME
        hwnd = win32gui.FindWindow(None, APP_NAME)
        if hwnd:
            # 如果窗口被隐藏了 (withdraw)，SW_RESTORE 可能不起作用
            # 我们尝试先显示再恢复
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        else:
            # 尝试通过枚举寻找（处理隐藏窗口）
            def callback(hwnd, hwnds):
                if win32gui.GetWindowText(hwnd) == APP_NAME:
                    hwnds.append(hwnd)
                return True
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            if hwnds:
                hwnd = hwnds[0]
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
            else:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo("提示", "提醒管家已经在后台运行中，请在系统托盘查看。")
        sys.exit(0)

    try:
        # 设置外观
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        
        # 默认显示主界面（用户手动点开）
        # 只有在明确带了 --silent 参数时才隐藏（如开机自启）
        silent_mode = "--silent" in sys.argv
        app = ReminderApp(silent=silent_mode)
        app.mainloop()
    except Exception as e:
        show_error_and_exit(str(e))
    finally:
        # 释放 Mutex (虽然系统会自动清理，但显式释放更好)
        if 'mutex' in locals() and mutex:
            win32api.CloseHandle(mutex)
