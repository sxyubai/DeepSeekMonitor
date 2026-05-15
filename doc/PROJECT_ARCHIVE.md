# DeepSeek Monitor — 项目工作状态存档

> 存档时间：2026-05-15 22:47  
> 打包人：Crow5 (sxyubai)  
> Git HEAD：`0d8a3c2`  
> 项目路径：`E:\Shiraha\Projects\AI\Crow5`

---

## 一、会话周期（2026-05-15）

| 阶段 | 完成内容 | 时间 |
|------|---------|------|
| 初始打包 | 环境检查 + PyInstaller .spec 创建 + exe 首次构建 | 21:23→21:31 |
| Bug修复1 | 三色状态标识（unpolish/polish 强制刷新 QSS） | 21:31→21:57 |
| Bug修复2 | 余额点击打开官网（webbrowser → QDesktopServices） | 同上 |
| Bug修复3 | 拖拽冲突修复（跳过 PointingHandCursor 的 QLabel） | 同上 |
| Bug修复4 | 删除 settings_dialog.py 重复方法 | 同上 |
| 品牌替换 | NZSK → © 2026 sxyubai（7个文件），版权行可点击跳转 GitHub | 22:15→22:34 |
| 最终打包 | `--clean` 重建 exe（含所有修复 + 品牌替换） | 22:34 |
| Git提交 | 9个文件一次性提交（用户手动完成） | 22:47 |

---

## 二、当前状态：打包完成，代码已提交

### ✅ 已完成的全部工作

| 类别 | 内容 | 涉及文件 |
|------|------|---------|
| **打包配置** | PyInstaller .spec（resources/cryptography/keyring/隐藏导入） | `DeepSeekMonitor.spec` |
| **品牌标识** | 全部 NZSK Technology → © 2026 sxyubai | 7个文件 |
| **版权链接** | 托盘菜单版权行改为 HTML 可点击链接 → GitHub | `main.py:154-160` |
| **状态三色** | 加载中（黄）可用（绿）API不可用（红） | `floating_window.py` + `style.qss` |
| **QSS强制刷新** | `setObjectName` 后调用 unpolish/polish | `floating_window.py:450-452` |
| **余额点击** | `QDesktopServices.openUrl(QUrl(...))` 替代 `webbrowser.open` | `floating_window.py:458-460` |
| **拖拽冲突** | `_install_drag_filters` 跳过 PointingHandCursor 的 QLabel | `floating_window.py:394-396` |
| **代码清理** | 删除重复方法 + 无用 import | `settings_dialog.py` + `floating_window.py` |
| **exe构建** | 最终版 `dist/DeepSeekMonitor.exe` (55.9MB, 22:34) | `dist/` |
| **Git提交** | 9文件纳入版本管理 | commit `0d8a3c2` |

### ❌ 未处理 / 待验证

| 项目 | 状态 | 说明 |
|------|:----:|------|
| 双击运行验证 | **待验证** | 用户需双击 exe 检查全部功能 |
| 数据库备份 | **跳过** | 应用未运行过，`%LOCALAPPDATA%/DeepSeekMonitor/` 不存在 |
| 前端代码 | **无** | `project/frontend/.gitkeep` 空目录 |
| .ico 图标 | **可优化** | exe 当前无图标 |
| 单元测试 | **未添加** | 尚无测试模块 |

---

## 三、Git 提交历史

```
0d8a3c2  (HEAD -> master) 存档 Crow5 2026-05-15 22:47   ← 本次完整修复
    ├─ brand: NZSK → © 2026 sxyubai (7 files)
    ├─ fix: 三色状态 + QSS 强制刷新 + 余额跳转 + 拖拽冲突
    ├─ fix: 删除 settings_dialog.py 重复方法
    └─ style: QSS 新增 BalanceStatusLoading/BalanceStatusError

572ebc5  存档: 项目工作状态归档 (打包完成, 待功能验收)
    └─ 项目存档文档

8778e80  存档 Crow5 2026-05-15 21:36
    ├─ .gitignore build/ dist/ 排除规则
    ├─ DeepSeekMonitor.spec 打包配置
    └─ README.md 打包命令更新

203b1ab  chore: initial commit - DeepSeek Monitor v1.0
    └─ 初始项目骨架
```

---

## 四、项目结构

```
Crow5/
├── README.md
├── requirements.txt
├── DeepSeekMonitor.spec          # PyInstaller 打包配置
├── .gitignore
├── doc/                          # 项目文档
│   ├── ARCHIVE.md                # 旧存档（保留参考）
│   └── PROJECT_ARCHIVE.md        # 本次存档（最新）
├── prototype/                    # 产品原型目录
├── project/
│   ├── frontend/                 # 前端（空）
│   └── backend/                  # 全部 Python 源码
│       ├── main.py               # 主入口 + 系统托盘 + 版权链接
│       ├── api_client.py         # DeepSeek API 客户端
│       ├── floating_window.py    # 悬浮窗 + 余额卡片 + 三色状态
│       ├── settings_dialog.py    # 设置对话框 + API Key 管理
│       ├── usage_tracker.py      # SQLite 用量追踪器
│       └── resources/
│           └── style.qss         # 深色毛玻璃主题（三色 QSS）
├── database/
│   └── init.sql                  # DDL 参考脚本
├── utils/
│   └── __init__.py
├── build/                        # PyInstaller 构建缓存（gitignore）
└── dist/                         # 输出 exe（gitignore）
    └── DeepSeekMonitor.exe       # 55.9MB · 独立可运行
```

---

## 五、运行方式

### 源码运行（需 Python）
```bash
pip install -r requirements.txt
python project/backend/main.py
```

### exe 运行（无需 Python）
```bash
dist/DeepSeekMonitor.exe
```

### 重新打包
```bash
pyinstaller --noconfirm DeepSeekMonitor.spec
```

---

## 六、数据存储

| 数据 | 路径 | 当前备份 |
|------|------|---------|
| API Key | `%LOCALAPPDATA%/DeepSeekMonitor/config.json` | 无（未运行） |
| 应用设置 | `%LOCALAPPDATA%/DeepSeekMonitor/app_settings.json` | 无（未运行） |
| 用量数据 | `%LOCALAPPDATA%/DeepSeekMonitor/usage.db` | 无（未运行） |

---

## 七、下一步建议

1. **双击 `dist/DeepSeekMonitor.exe` 功能验收** — 检查三色状态、余额点击跳转、拖拽
2. **推送 GitHub** — `git remote add origin https://github.com/sxyubai/DeepSeekMonitor.git && git push -u origin master`
3. **增补 .ico 图标** — 添加应用图标后更新 spec + 重新打包
4. **运行后备份数据库** — 定期备份 `%LOCALAPPDATA%/DeepSeekMonitor/usage.db`
