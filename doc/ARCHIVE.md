# DeepSeek Monitor — 项目工作状态存档

> 存档时间：2026-05-15
> 项目路径：E:\Shiraha\Projects\AI\Crow5

---

## 一、项目概述

Windows 桌面悬浮窗应用，实时显示 DeepSeek API 账户余额与 Token 用量统计。  
采用 PySide6 (Qt6) 原生桌面框架，深色毛玻璃商用视觉风格。

---

## 二、已完成功能

### ✅ 核心功能
| 功能 | 状态 | 说明 |
|------|:----:|------|
| 余额实时显示 | ✅ | DeepSeek API `/user/balance` 接口，总余额/赠送/充值 |
| 每日消耗追踪 | ✅ | 基于余额差额计算（SQLite 持久化） |
| 7天消耗弹窗 | ✅ | Hover 今日消耗数字 → 渐显弹窗 |
| 深色毛玻璃 UI | ✅ | 原生 PySide6 实现，圆角/阴影/渐变顶光 |
| 系统托盘驻留 | ✅ | 关闭窗口隐藏到托盘，双击恢复 |
| API Key 管理 | ✅ | keyring / Fernet 加密存储 + 手动保存 |
| 设置持久化 | ✅ | 透明度 / 刷新间隔 自动保存到 app_settings.json |

### ✅ 交互体验
| 功能 | 状态 | 说明 |
|------|:----:|------|
| 左键拖拽 | ✅ | Windows 原生拖拽（SendMessageW） |
| Aero Snap 分屏 | ✅ | 兼容 Windows 分屏 / 贴边吸附 |
| 右键菜单 | ✅ | 自定义深色右键菜单（无白闪） |
| 折叠/展开 | ✅ | 标题栏 ─ 按钮 |
| 窗口透明度 | ✅ | 设置滑块即时生效 + 持久化 |

### ✅ 安全与健壮性
| 功能 | 状态 |
|------|:----:|
| 线程安全（QObject 信号桥） | ✅ |
| API 重试防重入（_balance_busy 标记） | ✅ |
| API 异常处理（401/超时/断网） | ✅ |
| SQLite WAL 模式 + busy_timeout | ✅ |

---

## 三、项目结构

```
Crow5/
├── README.md                         # 项目文档
├── requirements.txt                  # 依赖清单
├── doc/                              # 文档目录
├── prototype/                        # 产品原型目录
├── project/
│   ├── frontend/                     # 前端资源目录
│   └── backend/                      # 全部 Python 源码
│       ├── main.py                   # 340 行 — 主入口 + 系统托盘 + 信号桥
│       ├── api_client.py             # 114 行 — DeepSeek API 客户端
│       ├── floating_window.py        # 721 行 — 悬浮窗 + 余额卡片 + 消耗弹窗
│       ├── settings_dialog.py        # 551 行 — 设置对话框 + API Key 管理
│       ├── usage_tracker.py          # 294 行 — SQLite 用量追踪器
│       └── resources/
│           └── style.qss             # 383 行 — 深色毛玻璃主题
├── database/
│   └── init.sql                      # 38 行 — DDL 参考脚本
└── utils/
    └── __init__.py                   # 工具包占位

总计：2523 行源代码
```

---

## 四、数据存储位置

| 数据 | 路径 | 说明 |
|------|------|------|
| API Key | 系统凭据管理器 (keyring) / `%LOCALAPPDATA%\DeepSeekMonitor\config.json` | 加密存储 |
| 应用设置 | `%LOCALAPPDATA%\DeepSeekMonitor\app_settings.json` | 透明度/刷新间隔 |
| 用量记录 | `%LOCALAPPDATA%\DeepSeekMonitor\usage.db` | SQLite WAL 模式 |
| 数据库备份 | `%LOCALAPPDATA%\DeepSeekMonitor\usage.db.backup` | 本次存档生成 |

---

## 五、待修复问题

### 🔴 P0 — 界面元素不可见
1. **余额数字 (`_amount_label`)** — 缺少 `#BalanceAmount` QSS 样式规则 → REM 已补
2. **● 可用标识 (`_status_label`)** — 缺少 `#BalanceStatus` QSS 样式规则
3. **最后同步时间 (`_sync_label`)** — 缺少 QSS 样式 + 未设 objectName
4. **可用状态分色** — 可用=绿、加载中=黄、错误=红
5. **设置页状态条位置** — "已保存"提示应移到"API Key 安全存储..."文字下方
6. **`settings_dialog.py` 重复方法** — `_on_action_clicked` 定义了两次（L445/L479）

### 🟡 P1 — 代码质量
- 无单元测试
- `_get_weekly_consumption()` 直接调用 `_usage_tracker._get_conn()`（私有方法）
- 跨天首次余额追踪可能漏记消耗
- 存在 QSS 残留规则 `#TitleAmountLabel`（无对应控件）

---

## 六、下一步建议

1. **修复 P0 问题** — 补全 QSS 样式（#BalanceStatus / #SyncTimeLabel）、状态分色、设置页布局
2. **安装依赖** — `pip install -r requirements.txt`
3. **启动验证** — `python project/backend/main.py`
4. **删除冗余文件** — 根目录下 `nul` 文件
5. **添加单元测试** — `tests/test_usage_tracker.py`

---

*本存档由 Crow5 多Agent协同引擎自动生成*
