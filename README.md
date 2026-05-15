# DeepSeek Monitor

Windows 桌面悬浮窗 — 实时显示 DeepSeek 账户余额与 API Token 用量统计。

## 技术栈

- **语言**: Python 3.10+
- **GUI 框架**: PySide6 ≥ 6.5
- **HTTP 客户端**: requests ≥ 2.31
- **数据存储**: SQLite（本地文件）
- **加密**: cryptography ≥ 41.0 / keyring ≥ 24.0
- **开发单位**: © 2026 sxyubai

## 项目结构

```
├── doc/                    # 文档目录
├── prototype/              # 产品原型
├── project/
│   └── backend/            # 后端源代码
│       ├── main.py              # 应用入口
│       ├── api_client.py        # DeepSeek API 客户端
│       ├── floating_window.py   # 悬浮窗界面
│       ├── settings_dialog.py   # 设置对话框
│       ├── usage_tracker.py     # 用量追踪
│       └── resources/
│           └── style.qss        # QSS 样式表
├── database/               # 数据库脚本目录
├── utils/                  # 工具包目录
└── requirements.txt        # Python 依赖
```

## 启动方式

```bash
pip install -r requirements.txt
python project/backend/main.py
```

## 端口信息

桌面 GUI 应用，无需 HTTP 端口。

## 数据库

- 类型: SQLite（自动创建）
- 路径: `%LOCALAPPDATA%/DeepSeekMonitor/usage.db`
- 表结构: `usage_records`（调用记录）、`daily_stats`（日统计）

## 配置存储

- 路径: `%LOCALAPPDATA%/DeepSeekMonitor/config.json`
- 加密方式: keyring 或 Fernet 加密存储
- 回退: 明文（仅开发环境）

## 交互操作

| 操作 | 行为 |
|------|------|
| 左键拖拽标题栏 | 移动悬浮窗位置 |
| 拖拽到屏幕边缘 | 自动贴边吸附 |
| 点击 `─` 按钮 | 折叠/展开悬浮窗 |
| 点击 `✕` 按钮 | 隐藏到系统托盘 |
| 双击托盘图标 | 恢复显示悬浮窗 |
| 右键托盘图标 | 打开功能菜单 |
| 悬浮窗 `⟳ 刷新` | 立即刷新余额和用量数据 |

## 打包为独立 exe（可选）

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean DeepSeekMonitor.spec
```

打包后的 exe 位于 `dist/DeepSeekMonitor.exe`（~56MB），无需 Python 环境即可运行。

> `.spec` 文件已处理好 PySide6 动态链接、`style.qss` 资源文件、`cryptography`/`keyring` 隐藏导入等细节，请勿用裸 `pyinstaller` 命令替代。
