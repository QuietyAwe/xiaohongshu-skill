---
name: xiaohongshu
description: 小红书图文笔记创作与发布技能。将 Markdown 内容转换为精美的小红书风格图片卡片，支持封面生成、正文分页、一键发布。触发词：小红书、发小红书、小红书笔记、小红书图文、小红书封面。支持：(1) 从 Markdown 生成小红书封面 (2) 将 Markdown 正文分页截图 (3) 浅色/深色双主题输出 (4) Cookie 方式一键发布笔记。
---

# 小红书图文创作

将 Markdown 内容转换为小红书风格的精美图片卡片。

## 快速开始

### 1. 准备 Markdown 文件

确保 Markdown 文件包含 `# 标题` 格式的标题：

```markdown
# 你的标题

正文内容...
```

### 2. 生成封面

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu

# 从 Markdown 提取标题生成封面（默认 3:4 标准比例，作者标记"曲奇"）
node scripts/generate-cover.js --md /path/to/note.md

# 直接指定封面标题（可不同于正文标题，更有吸引力）
node scripts/generate-cover.js --title "🔥 爆款标题"

# 生成 9:16 全屏封面
node scripts/generate-cover.js --md /path/to/note.md --ratio "9:16"

# 不显示滑动引导
node scripts/generate-cover.js --md /path/to/note.md --no-swipe

# 自定义作者标记（覆盖默认"曲奇"）
node scripts/generate-cover.js --md /path/to/note.md --text "自定义名字"
```

**参数说明：**

- `--md`: Markdown 文件路径（自动提取标题作为封面标题）
- `--title`: 直接指定封面标题（可设置更有吸引力的标题，不必与正文相同）
- `--text`: 左下角自定义文字（默认"曲奇"）
- `--ratio`: 图片比例，支持 `3:4`（标准，默认）或 `9:16`（全屏）
- `--no-swipe`: 隐藏"向右滑动查看正文"引导

**输出：**

- `assets/_attachments/cover-light.png` - 浅色主题封面
- `assets/_attachments/cover-dark.png` - 深色主题封面

### 3. 生成正文分页

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu

# 生成正文分页（默认 3:4 标准比例）
node scripts/generate.js

# 生成 9:16 全屏正文
node scripts/generate.js --ratio "9:16"
```

**参数说明：**

- `--ratio`: 图片比例，支持 `3:4`（标准，默认）或 `9:16`（全屏）

**前置步骤：**

编辑 `assets/xhs-preview.html`，将正文内容填入 `<div class="container" id="content">` 中。

**输出：**

- `assets/_attachments/xhs-light-01.png`, `xhs-light-02.png`, ... - 浅色主题分页
- `assets/_attachments/xhs-dark-01.png`, `xhs-dark-02.png`, ... - 深色主题分页

## 自定义配置

### 封面配置 (scripts/generate-cover.js)

```javascript
const CUSTOM_TEXT = "曲奇"; // 左下角自定义文字
const COVER_WIDTH = 675; // 封面宽度
const COVER_HEIGHT = 1200; // 封面高度 (9:16)
```

### 正文配置 (scripts/generate.js)

```javascript
const CUSTOM_TEXT = "曲奇"; // 左下角自定义文字
const PAGE_WIDTH = 600; // 页面宽度
const PAGE_HEIGHT = 1067; // 页面高度 (9:16)
const TOP_PADDING = 60; // 顶部留白
const BOTTOM_PADDING = 60; // 底部留白
```

### 样式模板

- `assets/cover-template.html` - 封面 HTML 模板（思源宋体标题）
- `assets/xhs-preview.html` - 正文 HTML 模板（霞鹜文楷正文）

两个模板都支持 `data-theme="dark"` 属性切换深色主题。

## 工作流程

1. **撰写内容**：用 Markdown 写好笔记内容
2. **生成封面**：`node scripts/generate-cover.js --md /path/to/note.md`
3. **编辑正文模板**：编辑 `assets/xhs-preview.html`，将正文内容填入 `<div class="container" id="content">`
4. **生成正文**：`node scripts/generate.js`
5. **移动图片**：将 `assets/_attachments/` 下的图片移动到笔记目录
6. **上传发布**：使用 `xhs_publish_safe.py` 发布

## 发布笔记

> ⚠️ **重要**：为防止重复发布，**优先使用安全发布脚本** `xhs_publish_safe.py`。该脚本内置防重复机制，避免因输出截断导致的重复发布事故。

### 1. 配置 Cookie

在技能目录下创建 `.env` 文件：

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu
echo 'XHS_COOKIE=your_cookie_string_here' > .env
```

**Cookie 获取方式：**

1. 在浏览器中登录小红书（https://www.xiaohongshu.com）
2. 打开开发者工具（F12）
3. 在 Network 标签中查看任意请求的 Cookie 头
4. 复制完整的 cookie 字符串

### 2. 安装 Python 依赖

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu

# 使用虚拟环境（推荐）
python3 -m venv .venv
.venv/bin/pip install xhs python-dotenv requests

# 或系统级安装
pip install xhs python-dotenv requests --break-system-packages
```

### 3. 标签格式

笔记 Markdown 文件末尾必须添加标签行：

```markdown
# 标题

正文内容...

标签：话题1 话题2 话题3
```

### 4. 发布命令

```bash
cd /root/.picoclaw/workspace/skills/xiaohongshu

# 推荐方式：从 md 文件发布（自动提取标题、标签、正文）
# 正文会自动从 markdown 提取并去掉语法标记（# ** [] 等）
.venv/bin/python scripts/xhs_publish_safe.py --md /path/to/note.md --topics "话题1" "话题2"

# 手动指定标签（覆盖 md 文件中的标签）
.venv/bin/python scripts/xhs_publish_safe.py --md note.md --topics "话题1" "话题2"

# 正文留空（仅发布图片，不包含文字）
.venv/bin/python scripts/xhs_publish_safe.py --md note.md --desc "" --topics "话题1"

# 强制重新发布（忽略重复检查）
.venv/bin/python scripts/xhs_publish_safe.py --md note.md --topics "话题" --force

# 仅验证，不发布
.venv/bin/python scripts/xhs_publish_safe.py --md note.md --topics "话题" --dry-run
```

**安全脚本特性：**

- ✅ 发布前检查本地记录，同名笔记已发布则拒绝
- ✅ 自动从 md 文件底部提取标签（`标签：` 行）
- ✅ 自动从 md 文件提取正文，去掉 markdown 语法
- ✅ 发布命令只执行一次
- ✅ 发布后立即记录笔记 ID
- ✅ 等待后用 API 验证发布状态

#### 备用方式：直接发布脚本

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu

# 基本发布（带话题标签）
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文内容" -i cover.png card_1.png --topics "游戏" "游戏行业"

# 使用通配符选择图片
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文" -i *.png --topics "热梗" "年轻人"

# 设为私密笔记
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文" -i *.png --topics "话题1" "话题2" --private

# 定时发布
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文" -i *.png --topics "话题" --post-time "2024-12-01 10:00:00"

# 使用 API 模式（需要 xhs-api 服务）
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文" -i *.png --topics "话题" --api-mode

# 仅验证，不实际发布
.venv/bin/python scripts/publish_xhs.py -t "标题" -d "正文" -i *.png --topics "话题" --dry-run
```

**发布注意事项：**

- 图片中已包含完整正文内容，但发布时仍会填充纯文本正文（方便搜索和阅读）
- `--topics` 话题标签必须带，增加笔记曝光

## 依赖

### Node.js 依赖（图文生成）

```bash
cd /home/qee/.picoclaw/workspace/skills/xiaohongshu
npm install puppeteer sharp
```

### Python 依赖（笔记发布）

```bash
pip install xhs python-dotenv requests
```

## 文件结构

```
xiaohongshu/
├── SKILL.md
├── package.json
├── requirements.txt        # Python 依赖
├── .env                    # Cookie 配置（需自行创建）
├── scripts/
│   ├── generate.js          # 正文分页生成脚本
│   ├── generate-cover.js    # 封面生成脚本
│   ├── publish_xhs.py      # 笔记发布脚本（备用）
│   └── xhs_publish_safe.py # 安全发布脚本（推荐，防重复）
└── assets/
    ├── cover-template.html  # 封面模板
    ├── xhs-preview.html      # 正文模板
    └── _attachments/         # 输出目录
        ├── cover-light.png
        ├── cover-dark.png
        ├── xhs-light-01.png
        ├── xhs-dark-01.png
        └── ...
```
