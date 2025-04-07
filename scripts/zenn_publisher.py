#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Zenn記事公開自動化スクリプト

記事ファイルをZenn向けに変換し、GitHubリポジトリに公開するための
自動化スクリプトです。

使用方法:
    python zenn_publisher.py --article path/to/article.md --images path/to/images/ [options]

オプション:
    --article  記事ファイルのパス（必須）
    --images   画像ディレクトリのパス（オプション）
    --emoji    記事に使用する絵文字（オプション、自動選定も可能）
    --state    公開状態 published/draft（オプション、デフォルト: draft）
    --push     GitHubにプッシュするかどうか（オプション、デフォルト: False）

環境変数:
    ZENN_USERNAME  Zennのユーザー名（デフォルト: takuyanagai0213）
"""

import os
import sys
import re
import shutil
import argparse
import subprocess
import datetime
import random
import json
import yaml
from pathlib import Path

# 絵文字カテゴリマッピング
EMOJI_CATEGORIES = {
    "AI": ["🤖", "🧠", "🔮", "🎯", "⚙️"],
    "データ分析": ["📊", "📈", "📉", "🧮", "🔍"],
    "Web開発": ["🌐", "💻", "🖥️", "🔌", "🧩"],
    "モバイル": ["📱", "📲", "⌚", "📡", "🔋"],
    "インフラ": ["🛠️", "🔧", "🚀", "☁️", "🏗️"],
    "セキュリティ": ["🔒", "🛡️", "🔐", "🔑", "⚔️"],
    "プログラミング": ["👨‍💻", "👩‍💻", "🧑‍💻", "📝", "💡"]
}

# デフォルト設定
DEFAULT_EMOJI = "💭"
DEFAULT_TYPE = "tech"
DEFAULT_STATE = "draft"
ZENN_ARTICLE_DIR = "articles"
ZENN_USERNAME = os.environ.get("ZENN_USERNAME", "takuyanagai0213")

def parse_args():
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(description="Zenn記事公開自動化ツール")
    parser.add_argument("--article", required=True, help="記事ファイルのパス")
    parser.add_argument("--images", help="画像ディレクトリのパス")
    parser.add_argument("--emoji", help="記事に使用する絵文字")
    parser.add_argument("--state", default=DEFAULT_STATE, choices=["published", "draft"],
                        help="公開状態（published/draft）")
    parser.add_argument("--push", action="store_true", help="GitHubにプッシュするかどうか")

    return parser.parse_args()

def extract_metadata(content):
    """記事内容からメタデータを抽出する"""
    metadata = {
        "title": "",
        "type": DEFAULT_TYPE,
        "topics": [],
        "category": ""
    }

    # タイトル抽出
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # トピック（タグ）抽出 - タグ表記を検索
    tag_matches = re.findall(r'#([a-zA-Z0-9_-]+)', content)
    if tag_matches:
        # 重複を除去して先頭5つのみ取得
        metadata["topics"] = list(dict.fromkeys(tag_matches))[:5]

    # カテゴリ推定 - 頻出単語からカテゴリを推定
    for category, _ in EMOJI_CATEGORIES.items():
        if category.lower() in content.lower():
            metadata["category"] = category
            break

    return metadata

def select_emoji(category, content=""):
    """カテゴリに基づいて絵文字を選択する"""
    if not category and not content:
        return DEFAULT_EMOJI

    # カテゴリが指定されている場合
    if category in EMOJI_CATEGORIES:
        return random.choice(EMOJI_CATEGORIES[category])

    # 内容から推測
    for category, emojis in EMOJI_CATEGORIES.items():
        if category.lower() in content.lower():
            return random.choice(emojis)

    return DEFAULT_EMOJI

def convert_image_paths(content, article_slug, image_dir=None):
    """画像パスをZennに適したパスに変換する"""
    if not image_dir:
        return content

    # 絶対パスを相対パスに変換
    image_dir_path = Path(image_dir).resolve()

    # 画像ファイルのパターンを検出して変換
    def replace_image_path(match):
        img_path = match.group(1)
        img_file = os.path.basename(img_path)
        return f"![](/images/{article_slug}/{img_file})"

    # Markdown画像表記を変換
    content = re.sub(r'!\[.*?\]\((.*?)\)', replace_image_path, content)

    return content

def create_article_slug(title):
    """記事タイトルからスラッグを生成する"""
    # 英数字以外を削除し、空白をハイフンに変換
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s]+', '-', slug)

    # 日本語タイトルの場合はタイトルの最初の数単語とタイムスタンプを使用
    if not slug or len(slug) < 3:
        timestamp = datetime.datetime.now().strftime("%m%d%H%M")
        slug = f"article-{timestamp}"

    return slug

def create_frontmatter(metadata, emoji, state):
    """フロントマターを生成する"""
    frontmatter = {
        "title": metadata["title"],
        "emoji": emoji,
        "type": metadata["type"],
        "topics": metadata["topics"],
        "published": state == "published"
    }

    return yaml.dump(frontmatter, allow_unicode=True)

def copy_images(image_dir, article_slug, zenn_dir):
    """画像ファイルをZennのディレクトリ構造にコピーする"""
    if not image_dir:
        return []

    source_dir = Path(image_dir)
    target_dir = Path(zenn_dir) / "images" / article_slug

    # ターゲットディレクトリが存在しない場合は作成
    os.makedirs(target_dir, exist_ok=True)

    copied_files = []
    for img_file in source_dir.glob("*"):
        if img_file.is_file() and img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.svg']:
            target_file = target_dir / img_file.name
            shutil.copy2(img_file, target_file)
            copied_files.append(str(target_file))

    return copied_files

def git_push(zenn_dir, article_file, image_files, article_slug):
    """GitHubリポジトリに変更をプッシュする"""
    try:
        # カレントディレクトリを保存
        original_dir = os.getcwd()
        os.chdir(zenn_dir)

        # git add
        subprocess.run(["git", "add", article_file], check=True)
        for img_file in image_files:
            subprocess.run(["git", "add", img_file], check=True)

        # git commit
        commit_message = f"Add article: {article_slug}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        # git push
        subprocess.run(["git", "push", "origin", "main"], check=True)

        # 元のディレクトリに戻る
        os.chdir(original_dir)

        return True, "GitHub へのプッシュが完了しました。"
    except subprocess.CalledProcessError as e:
        return False, f"Git コマンドの実行中にエラーが発生しました: {e}"
    except Exception as e:
        return False, f"予期せぬエラーが発生しました: {e}"

def main():
    """メイン処理"""
    args = parse_args()

    try:
        # 記事ファイルを読み込む
        with open(args.article, 'r', encoding='utf-8') as f:
            content = f.read()

        # メタデータを抽出
        metadata = extract_metadata(content)

        # スラッグを生成
        article_slug = create_article_slug(metadata["title"])

        # 絵文字を選択
        emoji = args.emoji if args.emoji else select_emoji(metadata["category"], content)

        # 画像パスを変換
        content = convert_image_paths(content, article_slug, args.images)

        # フロントマターを生成
        frontmatter = create_frontmatter(metadata, emoji, args.state)

        # Zennフォーマットの記事を生成
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        zenn_filename = f"{today}-{article_slug}.md"

        # Zennディレクトリのパスを取得（カレントディレクトリをデフォルトとする）
        zenn_dir = os.getcwd()

        # 記事ディレクトリが存在しない場合は作成
        article_dir = os.path.join(zenn_dir, ZENN_ARTICLE_DIR)
        os.makedirs(article_dir, exist_ok=True)

        # 記事ファイルを作成
        zenn_article_path = os.path.join(article_dir, zenn_filename)
        with open(zenn_article_path, 'w', encoding='utf-8') as f:
            f.write(f"---\n{frontmatter}---\n\n{content}")

        # 画像ファイルをコピー
        copied_images = copy_images(args.images, article_slug, zenn_dir)

        # GitHubにプッシュ
        push_result = (True, "GitHub へのプッシュはスキップされました。")
        if args.push:
            push_result = git_push(zenn_dir, zenn_article_path, copied_images, article_slug)

        # 結果を出力
        print("\n== Zenn公開準備完了レポート ==")
        print(f"記事タイトル: {metadata['title']}")
        print(f"スラッグ: {article_slug}")
        print(f"公開状態: {args.state}")
        print(f"出力ファイル: {zenn_article_path}")
        print(f"コピーした画像: {len(copied_images)}個")
        print(f"GitHubプッシュ: {push_result[1]}")

        # Zenn URLを表示
        if args.state == "published" and push_result[0]:
            print("\n公開後のURL:")
            print(f"https://zenn.dev/{ZENN_USERNAME}/articles/{article_slug}")

        return 0

    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
