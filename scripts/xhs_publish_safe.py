#!/usr/bin/env python3
"""
小红书安全发布脚本 - 防重复发布

核心规则：
1. 发布前检查本地记录，同名笔记已发布则拒绝
2. 发布命令只执行一次
3. 发布后立即记录笔记 ID
4. 等待后用 API 验证发布状态

使用方法：
    python xhs_publish_safe.py --md /path/to/note.md --topics "话题1" "话题2"
    python xhs_publish_safe.py --title "标题" --desc "正文" --images *.png --topics "话题1"
"""

import argparse
import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    from publish_xhs import (
        load_cookie, parse_cookie, validate_cookie, 
        validate_images, search_topics, LocalPublisher
    )
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


# 配置
PUBLISH_RECORD_FILE = Path("/root/.picoclaw/workspace/小红书笔记/已发布记录.txt")
NOTES_DIR = Path("/root/.picoclaw/workspace/小红书笔记")


def ensure_record_file():
    """确保发布记录文件存在"""
    PUBLISH_RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PUBLISH_RECORD_FILE.exists():
        PUBLISH_RECORD_FILE.write_text("# 小红书发布记录\n# 格式: 时间 | 标题 | note_id | 链接\n\n")


def get_published_titles() -> Dict[str, Dict[str, str]]:
    """获取已发布的笔记标题及其信息
    
    Returns:
        {标题: {"note_id": ..., "time": ..., "url": ...}}
    """
    if not PUBLISH_RECORD_FILE.exists():
        return {}
    
    records = {}
    with open(PUBLISH_RECORD_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # 格式: 2026-03-09 12:00 | 标题 | note_id | url
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                title = parts[1]
                records[title] = {
                    "time": parts[0],
                    "note_id": parts[2],
                    "url": parts[3] if len(parts) > 3 else ""
                }
    return records


def check_duplicate(title: str) -> Optional[Dict[str, str]]:
    """检查是否已发布过同名笔记
    
    Returns:
        如果已发布，返回记录信息；否则返回 None
    """
    published = get_published_titles()
    return published.get(title)


def record_publish(title: str, note_id: str, url: str):
    """记录发布信息"""
    ensure_record_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(PUBLISH_RECORD_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | {title} | {note_id} | {url}\n")
    print(f"📝 已记录发布信息: {title}")


def extract_title_from_md(md_path: str) -> Optional[str]:
    """从 Markdown 文件提取标题"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取第一个 # 标题
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def extract_desc_from_md(md_path: str) -> str:
    """从 Markdown 文件提取正文（去掉标题、标签行和 markdown 语法）"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 去掉标题行
    lines = content.split('\n')
    # 跳过开头的 # 标题行
    start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('# '):
            start_idx = i + 1
            break
    
    # 跳过空行
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1
    
    # 去掉末尾的标签行（格式：标签：xxx）
    end_idx = len(lines)
    for i in range(len(lines) - 1, start_idx - 1, -1):
        if lines[i].strip().startswith('标签：') or lines[i].strip().startswith('标签:'):
            end_idx = i
            break
    
    desc = '\n'.join(lines[start_idx:end_idx])
    
    # 去掉 markdown 语法
    desc = strip_markdown(desc)
    
    return desc.strip()


def strip_markdown(text: str) -> str:
    """去掉 markdown 语法，保留纯文本"""
    # 去掉标题标记 # ## ### 等
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 去掉加粗 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # 去掉斜体 *text* 或 _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # 去掉行内代码 `code`
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # 去掉链接 [text](url)，保留 text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # 去掉图片 ![alt](url)
    text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
    
    # 去掉引用标记 >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # 去掉无序列表标记 - * +
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    
    # 去掉有序列表标记 1. 2. 等
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 去掉分隔线 --- *** ___
    text = re.sub(r'^[\-\*]{3,}$', '', text, flags=re.MULTILINE)
    
    # 去掉 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 合并多个连续空行为单个空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def extract_tags_from_md(md_path: str) -> List[str]:
    """从 Markdown 文件提取标签（末尾的 `标签：xxx yyy zzz` 行）"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    # 从末尾找标签行
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line.startswith('标签：') or line.startswith('标签:'):
            # 提取标签（用空格分隔）
            tags_str = line.split('：', 1)[-1] if '：' in line else line.split(':', 1)[-1]
            tags = [t.strip() for t in tags_str.split() if t.strip()]
            return tags
    
    return []


def find_images_for_md(md_path: str) -> List[str]:
    """找到与 Markdown 文件同目录的图片文件"""
    md_dir = Path(md_path).parent
    images = []
    
    # 优先顺序：cover.png -> cover-light.png -> cover-dark.png -> xhs-light -> xhs-dark -> 其他 png
    cover = md_dir / "cover.png"
    cover_light = md_dir / "cover-light.png"
    cover_dark = md_dir / "cover-dark.png"
    
    if cover.exists():
        images.append(str(cover))
    elif cover_light.exists():
        images.append(str(cover_light))
    elif cover_dark.exists():
        images.append(str(cover_dark))
    
    # 添加正文图片
    for f in sorted(md_dir.glob("xhs-light-*.png")):
        images.append(str(f))
    
    if not images:
        # 回退：查找所有 png
        images = [str(f) for f in sorted(md_dir.glob("*.png"))]
    
    return images


def verify_note_published(client, note_id: str, max_retries: int = 3) -> bool:
    """验证笔记是否发布成功
    
    Args:
        client: XhsClient 实例
        note_id: 笔记 ID
        max_retries: 最大重试次数
        
    Returns:
        是否发布成功
    """
    for i in range(max_retries):
        try:
            time.sleep(3)  # 等待 3 秒
            note = client.get_note_by_id(note_id)
            if note and note.get('note_id'):
                print(f"✅ 验证成功: 笔记 {note_id} 已发布")
                return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"⏳ 验证中... ({i+1}/{max_retries})")
            else:
                print(f"⚠️ 无法验证笔记状态: {e}")
                return False
    return False


def publish_safe(
    title: str,
    desc: str,
    images: List[str],
    topics: List[str] = None,
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """安全发布笔记
    
    Args:
        title: 笔记标题
        desc: 笔记正文
        images: 图片路径列表
        topics: 话题关键词列表
        force: 强制发布（忽略重复检查）
        dry_run: 仅验证，不发布
        
    Returns:
        发布结果
    """
    # 1. 检查重复
    if not force:
        existing = check_duplicate(title)
        if existing:
            print(f"⚠️ 笔记已发布过: {title}")
            print(f"   发布时间: {existing['time']}")
            print(f"   笔记链接: {existing['url']}")
            print(f"\n如需重新发布，请使用 --force 参数")
            return {"status": "duplicate", "existing": existing}
    
    # 2. 验证图片
    valid_images = validate_images(images)
    if not valid_images:
        return {"status": "error", "message": "没有有效的图片文件"}
    
    # 3. 加载 Cookie
    cookie = load_cookie()
    validate_cookie(cookie)
    
    if dry_run:
        print("\n🔍 验证模式 - 不会实际发布")
        print(f"  📌 标题: {title}")
        print(f"  📝 描述: {desc[:50]}..." if len(desc) > 50 else f"  📝 描述: {desc}")
        print(f"  🖼️ 图片: {len(valid_images)} 张")
        print(f"  🏷️ 话题: {topics or '无'}")
        print("\n✅ 验证通过，可以发布")
        return {"status": "dry_run", "valid": True}
    
    # 4. 初始化客户端
    publisher = LocalPublisher(cookie)
    publisher.init_client()
    
    # 5. 搜索话题
    topic_list = None
    if topics:
        try:
            topic_list = search_topics(publisher.client, topics)
        except Exception as e:
            print(f"⚠️ 搜索话题失败: {e}")
            print("将继续发布，但不带话题标签")
    
    # 6. 发布（只执行一次！）
    print(f"\n🚀 发布笔记...")
    print(f"  📌 标题: {title}")
    print(f"  🖼️ 图片: {len(valid_images)} 张")
    
    try:
        result = publisher.publish(
            title=title,
            desc=desc,
            images=valid_images,
            topics=topic_list
        )
        
        # 7. 提取 note_id 并记录
        note_id = None
        if isinstance(result, dict):
            note_id = result.get('note_id') or result.get('id')
        
        if note_id:
            url = f"https://www.xiaohongshu.com/explore/{note_id}"
            record_publish(title, note_id, url)
            
            # 8. 验证发布状态
            print(f"\n⏳ 等待 10 秒后验证发布状态...")
            time.sleep(10)
            verify_note_published(publisher.client, note_id)
            
            return {
                "status": "success",
                "note_id": note_id,
                "url": url
            }
        else:
            print("⚠️ 无法获取笔记 ID")
            return {"status": "error", "message": "无法获取笔记 ID", "result": result}
            
    except Exception as e:
        print(f"❌ 发布失败: {e}")
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description='小红书安全发布脚本（防重复）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 从 Markdown 文件发布（自动提取标题、正文、查找图片，正文会自动去掉 markdown 语法）
  python xhs_publish_safe.py --md /path/to/note.md --topics "游戏" "二次元"
  
  # 手动指定标题和图片
  python xhs_publish_safe.py --title "标题" --images cover.png card1.png --topics "话题"
  
  # 正文留空（仅发布图片，不包含文字）
  python xhs_publish_safe.py --md note.md --desc "" --topics "话题"
  
  # 强制重新发布（忽略重复检查）
  python xhs_publish_safe.py --md note.md --topics "话题" --force
  
  # 仅验证，不发布
  python xhs_publish_safe.py --md note.md --topics "话题" --dry-run

注意:
  默认会将 markdown 正文转为纯文本发布（去掉 # ** [] 等语法）。
  如需正文留空，请使用 --desc ""。
'''
    )
    
    # 方式一：从 Markdown 文件发布
    parser.add_argument('--md', help='Markdown 文件路径（自动提取标题、正文、查找图片）')
    
    # 方式二：手动指定
    parser.add_argument('--title', '-t', help='笔记标题')
    parser.add_argument('--desc', '-d', default=None, help='笔记正文（传空字符串则不发布正文，仅发布图片）')
    parser.add_argument('--images', '-i', nargs='+', help='图片文件路径')
    
    # 通用参数
    parser.add_argument('--topics', nargs='+', help='话题标签关键词')
    parser.add_argument('--force', action='store_true', help='强制发布（忽略重复检查）')
    parser.add_argument('--dry-run', action='store_true', help='仅验证，不实际发布')
    
    args = parser.parse_args()
    
    # 参数校验
    if args.md:
        # 从 Markdown 文件发布
        if not os.path.exists(args.md):
            print(f"❌ 文件不存在: {args.md}")
            sys.exit(1)
        
        title = extract_title_from_md(args.md)
        if not title:
            print(f"❌ 无法从文件提取标题: {args.md}")
            sys.exit(1)
        
        # --desc "" 表示正文留空（正文已做成图片）
        if args.desc == "":
            desc = ""
        else:
            desc = extract_desc_from_md(args.md)
        
        images = find_images_for_md(args.md)
        
        # 从 md 文件提取标签（如果未手动指定 --topics）
        if not args.topics:
            args.topics = extract_tags_from_md(args.md)
        
        if not images:
            print(f"❌ 未找到图片文件: {Path(args.md).parent}")
            sys.exit(1)
        
        print(f"📄 从文件读取: {args.md}")
        print(f"  标题: {title}")
        print(f"  图片: {len(images)} 张")
        if args.topics:
            print(f"  标签: {' '.join(args.topics)}")
        
    elif args.title and args.images:
        # 手动指定
        title = args.title
        desc = args.desc
        images = args.images
    else:
        parser.print_help()
        print("\n❌ 请指定 --md 或同时指定 --title 和 --images")
        sys.exit(1)
    
    # 执行发布
    result = publish_safe(
        title=title,
        desc=desc,
        images=images,
        topics=args.topics,
        force=args.force,
        dry_run=args.dry_run
    )
    
    # 返回状态码
    if result.get('status') == 'success':
        print(f"\n✨ 发布成功！")
        print(f"🔗 {result['url']}")
        sys.exit(0)
    elif result.get('status') == 'duplicate':
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()