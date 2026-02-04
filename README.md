# 提醒管家 (Reminder Manager)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6)

专为 Windows 11/10 打造的现代化桌面提醒工具，将 macOS 的优雅美学完美融入 Windows 体验。

✨ **核心亮点**：
- **零门槛即开即用**：提供单文件 `.exe`，无需安装 Python 或任何依赖，双击即可运行。
- **极致轻量化**：后台静默常驻，系统资源占用微乎其微，不打扰您的每一份专注。
- **优雅的 macOS 设计**：像素级复刻 macOS UI 风格，圆角卡片、柔和阴影与流畅交互，让工具也成为桌搭的一部分。
- **无感开机自启**：支持开机自动静默启动并最小化至托盘，忘记打开软件也能准时收到提醒。
- **Windows 原生集成**：深度集成 Win11/Win10 原生通知中心，支持系统级勿扰模式，重要提醒不错过。

## 📸 界面预览

| 主界面 | 设置界面 |
| :---: | :---: |
| <img src="assets/preview.png" width="100%"> | <img src="assets/preview_2.png" width="100%"> |

#### 🔔 通知效果
<img src="assets/preview_3.png" width="60%">

## ✨ 功能特性

- **macOS 风格界面**：极简设计，圆角卡片，流畅交互。
- **后台常驻**：支持最小化到系统托盘，不占用任务栏空间。
- **系统级通知**：集成 Windows 原生通知中心，确保不错过任何提醒。
- **开机自启**：支持设置开机自动启动，无感运行。
- **数据持久化**：自动保存任务配置，防止数据丢失。

## 🛠️ 技术栈

- **GUI 框架**: [customtkinter](https://github.com/TomSchimansky/CustomTkinter)
- **系统集成**: win11toast, pystray, pywin32
- **图像处理**: Pillow

## 📦 安装与运行

### 方式一：直接运行（推荐）

本项目提供了预编译的 `提醒管家.exe` 文件，无需安装 Python 环境即可直接使用：

1. 下载最新发布的 `提醒管家.exe`。
2. 双击直接运行即可。

### 方式二：源码运行

#### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/reminder-manager.git
cd reminder-manager
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

#### 3. 运行程序

```bash
python main.py
```

## 🚀 打包发布

如果你想将其打包为 `.exe` 可执行文件，可以使用 `pyinstaller`：

```bash
pip install pyinstaller
pyinstaller -F -w -i src/app_icon.ico src/main.py -n "提醒管家"
```

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。
