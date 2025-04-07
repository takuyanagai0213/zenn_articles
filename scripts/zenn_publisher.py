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
    --repo     Zenn用GitHubリポジトリのURL（SSH形式: git@github.com:user/repo.git または HTTPS形式: https://github.com/user/repo.git）
    --check-deps 依存パッケージの確認
    --gen-reqs requirements.txtファイルを生成
    --transliterate 日本語タイトルをローマ字に変換してスラグ生成（オプション、デフォルト: False）
    --published-at 公開日時（形式: YYYY-MM-DDTHH:MM:SS+09:00）- 予約投稿用

環境変数:
    ZENN_USERNAME    Zennのユーザー名
    ZENN_GITHUB_REPO Zenn用GitHubリポジトリのURL (例: git@github.com:username/zenn-content.git)

認証設定:
    - SSH認証: git@github.com:username/repo.git 形式のURLを使用する場合、
      SSHキーが設定されていることを確認してください。
    - HTTPS認証: https://github.com/username/repo.git 形式のURLを使用する場合、
      GitHubのパーソナルアクセストークンを使用するか、Git認証情報ヘルパーを設定してください。
      例: git config --global credential.helper cache

依存パッケージ:
    - GitPython: Git操作のためのPythonライブラリ
    - PyYAML: YAMLファイル処理用ライブラリ
    - pykakasi: 日本語をローマ字に変換するためのライブラリ（--transliterateオプション使用時）

インストール方法:
    pip install GitPython PyYAML pykakasi
    または
    pip install -r requirements.txt
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
import tempfile
from pathlib import Path
import git  # GitPythonライブラリをインポート
import uuid
import unicodedata

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
ZENN_GITHUB_REPO = os.environ.get("ZENN_GITHUB_REPO", "https://github.com/takuyanagai0213/zenn_articles.git")

def parse_args():
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(description="Zenn記事公開自動化ツール")
    parser.add_argument("--article", required=True, help="記事ファイルのパス")
    parser.add_argument("--images", help="画像ディレクトリのパス")
    parser.add_argument("--emoji", help="記事に使用する絵文字")
    parser.add_argument("--state", default=DEFAULT_STATE, choices=["published", "draft"],
                        help="公開状態（published/draft）")
    parser.add_argument("--push", action="store_true", help="GitHubにプッシュするかどうか")
    parser.add_argument("--repo", help="Zenn用GitHubリポジトリのURL（SSH形式: git@github.com:user/repo.git または HTTPS形式: https://github.com/user/repo.git）")
    parser.add_argument("--check-deps", action="store_true", help="依存パッケージの確認")
    parser.add_argument("--use-https", action="store_true",
                        help="HTTPSを使用してGitHubとやり取りする（URLがSSH形式の場合はHTTPS形式に変換）")
    parser.add_argument("--gen-reqs", action="store_true",
                        help="requirements.txtファイルを生成する")
    parser.add_argument("--transliterate", action="store_true",
                        help="日本語タイトルをローマ字に変換してスラグ生成")
    parser.add_argument("--published-at",
                        help="公開日時（形式: YYYY-MM-DDTHH:MM:SS+09:00）- 予約投稿用")

    return parser.parse_args()

def check_dependencies():
    """依存パッケージの確認"""
    missing_deps = []

    try:
        import git
    except ImportError:
        missing_deps.append("GitPython")

    try:
        import yaml
    except ImportError:
        missing_deps.append("PyYAML")

    # pykakasiの確認（オプションですが、transliterateオプションで必要）
    try:
        import pykakasi
    except ImportError:
        if "--transliterate" in sys.argv:
            missing_deps.append("pykakasi")

    if missing_deps:
        print("以下の依存パッケージがインストールされていません:")
        for dep in missing_deps:
            print(f"- {dep}")
        print("\nインストール方法:")
        print("pip install " + " ".join(missing_deps))
        return False

    return True

def generate_requirements_file(filename="requirements.txt"):
    """requirements.txtファイルを生成する"""
    requirements = [
        "GitPython>=3.1.0",
        "PyYAML>=6.0",
        "pykakasi>=2.2.0",  # 日本語をローマ字に変換するためのライブラリ
    ]

    try:
        with open(filename, "w", encoding="utf-8") as f:
            for req in requirements:
                f.write(f"{req}\n")
        print(f"requirements.txtファイルを生成しました: {filename}")
        print("インストール方法: pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"requirements.txtファイルの生成中にエラーが発生しました: {e}")
        return False

def transliterate_japanese(text, max_length=50):
    """日本語テキストをローマ字に変換する"""
    try:
        import pykakasi

        kks = pykakasi.kakasi()
        result = kks.convert(text)

        # ローマ字に変換
        romaji = ""
        for item in result:
            romaji += item['hepburn']

        # 英数字以外を削除し、空白をハイフンに変換
        romaji = re.sub(r'[^\w\s-]', '', romaji.lower())
        romaji = re.sub(r'[\s]+', '-', romaji)

        # 長さを制限
        if len(romaji) > max_length:
            romaji = romaji[:max_length]

        return romaji
    except ImportError:
        print("警告: pykakasiライブラリがインストールされていません。ローマ字変換をスキップします。")
        return None
    except Exception as e:
        print(f"ローマ字変換中にエラーが発生しました: {e}")
        return None

def extract_metadata(content):
    """記事内容からメタデータを抽出する"""
    metadata = {
        "title": "",
        "type": DEFAULT_TYPE,
        "topics": [],
        "category": "",
        "emoji": DEFAULT_EMOJI,
        "published": False,
        "published_at": None
    }

    # フロントマターがあるか確認
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if frontmatter_match:
        try:
            # YAMLとしてフロントマターを解析
            frontmatter_content = frontmatter_match.group(1)
            frontmatter_data = yaml.safe_load(frontmatter_content)

            # 各メタデータを抽出
            if frontmatter_data:
                # タイトル抽出（クォーテーションを削除）
                if "title" in frontmatter_data:
                    title = frontmatter_data["title"]
                    if isinstance(title, str):
                        # クォーテーションを削除（存在する場合）
                        metadata["title"] = title.strip('"\'')

                # タイプ抽出（tech/idea）
                if "type" in frontmatter_data:
                    article_type = frontmatter_data["type"]
                    if article_type in ["tech", "idea"]:
                        metadata["type"] = article_type

                # トピック（タグ）抽出
                if "topics" in frontmatter_data and isinstance(frontmatter_data["topics"], list):
                    metadata["topics"] = frontmatter_data["topics"][:5]  # 最大5つまで

                # 絵文字抽出
                if "emoji" in frontmatter_data:
                    emoji = frontmatter_data["emoji"]
                    if isinstance(emoji, str):
                        metadata["emoji"] = emoji.strip('"\'')

                # 公開状態抽出
                if "published" in frontmatter_data:
                    metadata["published"] = bool(frontmatter_data["published"])

                # 公開日時抽出
                if "published_at" in frontmatter_data:
                    metadata["published_at"] = frontmatter_data["published_at"]

                # フロントマターを持つ記事からコンテンツ部分を抽出
                content = content[frontmatter_match.end():]

            print("既存のフロントマターからメタデータを抽出しました")
        except Exception as e:
            print(f"フロントマターの解析中にエラーが発生しました: {e}")

    # フロントマターがない場合やフロントマターから抽出できなかった項目を補完

    # タイトルがない場合は見出しから抽出
    if not metadata["title"]:
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()

    # トピックがない場合はタグ表記から抽出
    if not metadata["topics"]:
        tag_matches = re.findall(r'#([a-zA-Z0-9_-]+)', content)
        if tag_matches:
            # 重複を除去して先頭5つのみ取得
            metadata["topics"] = list(dict.fromkeys(tag_matches))[:5]

    # カテゴリ推定 - 頻出単語からカテゴリを推定（絵文字選択に使用）
    if not metadata["category"]:
        for category, _ in EMOJI_CATEGORIES.items():
            if category.lower() in content.lower():
                metadata["category"] = category
                break

    return metadata, content

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

def create_article_slug(title, use_transliteration=False):
    """記事タイトルからスラッグを生成する

    Zennの仕様に合わせて:
    - 半角英数字（a-z0-9）、ハイフン（-）、アンダースコア（_）のみ使用
    - 12〜50字の組み合わせ
    """
    # タイトルがない場合はランダムなスラッグを生成
    if not title:
        timestamp = datetime.datetime.now().strftime("%m%d%H%M")
        return f"article-{timestamp}-{uuid.uuid4().hex[:6]}"

    # Unicode正規化
    title = unicodedata.normalize('NFKC', title)

    # 日本語タイトルをローマ字に変換（指定された場合）
    romaji = None
    if use_transliteration and re.search(r'[ぁ-んァ-ン一-龥]', title):
        romaji = transliterate_japanese(title)

    # ローマ字変換が成功した場合はそれを使用
    if romaji:
        # 英数字、ハイフン、アンダースコア以外の文字を削除
        slug = re.sub(r'[^\w\s-]', '', romaji.lower())
        slug = re.sub(r'[\s]+', '-', slug)
    else:
        # 通常の処理（英数字、ハイフン、アンダースコア以外の文字を削除し、空白をハイフンに変換）
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug)

    # 英語のタイトルの場合、そのまま使用（パターンに合えば）
    if re.match(r'^[a-z0-9_-]+$', slug):
        # 長さが十分であればそのまま使用
        if len(slug) >= 12:
            return slug[:50]  # 50文字以内に制限

    # 日本語や他の非英数字のタイトルの場合、またはスラッグが短すぎる場合
    # タイムスタンプとUUIDを組み合わせて一意のスラッグを生成
    timestamp = datetime.datetime.now().strftime("%m%d%H%M")

    # 元のタイトルから少なくとも英数字部分を抽出
    alphanumeric_part = re.sub(r'[^a-z0-9]', '', slug.lower())

    # 英数字部分がある場合は使用、なければ「article」をプレフィックスとする
    prefix = alphanumeric_part if alphanumeric_part else "article"

    # スラッグの構成: プレフィックス-タイムスタンプ-UUID
    # スラッグの長さが12文字未満の場合、UUIDを追加して長さを確保
    slug = f"{prefix}-{timestamp}"

    # スラッグの長さが12文字未満の場合、UUIDを追加
    if len(slug) < 12:
        slug = f"{slug}-{uuid.uuid4().hex[:12 - len(slug)]}"

    # 50文字以内に制限
    return slug[:50]

def create_frontmatter(metadata, emoji, state):
    """フロントマターを生成する

    Zennの仕様に従って:
    - title: 記事のタイトル（必須）- クォーテーションで囲む
    - emoji: アイキャッチとして使われる絵文字（1文字）（必須）
    - type: tech（技術記事）か idea（アイデア記事）のどちらか（必須）
    - topics: タグ（配列、最大5つまで）（任意）
    - published: 公開設定（true: 公開、false: 下書き）（必須）
    - published_at: 公開日時（過去または未来の日時）（任意）
    """
    # typeが有効な値かチェック
    valid_types = ["tech", "idea"]
    article_type = metadata["type"]
    if article_type not in valid_types:
        print(f"警告: 無効なtype '{article_type}' が指定されました。デフォルト値 'tech' を使用します。")
        article_type = "tech"

    # topicsを最大5つに制限
    topics = metadata["topics"]
    if len(topics) > 5:
        print(f"警告: topicsは最大5つまでです。最初の5つのみを使用します：{topics[:5]}")
        topics = topics[:5]

    # タイトルからクォーテーションを削除（二重クォーテーションを防ぐため）
    title = metadata["title"].strip('"\'')

    # 絵文字から余分なクォーテーションを削除
    emoji = emoji.strip('"\'')

    # 手動でYAML形式のフロントマターを構築する
    # この方法により、引用符の制御が容易になる
    fm_lines = []
    fm_lines.append(f'title: "{title}"')
    fm_lines.append(f'emoji: "{emoji}"')
    fm_lines.append(f'type: {article_type}')

    # トピックの追加
    if topics:
        fm_lines.append('topics:')
        for topic in topics:
            fm_lines.append(f'- {topic}')
    else:
        fm_lines.append('topics: []')

    # 公開状態
    fm_lines.append(f'published: {str(state == "published").lower()}')

    # フロントマターをYAML形式の文字列に変換
    return '\n'.join(fm_lines)

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

def convert_ssh_to_https(url):
    """SSH形式のGitURLをHTTPS形式に変換する"""
    if not url or not isinstance(url, str):
        return url

    # SSH形式 (git@github.com:username/repo.git) をHTTPS形式に変換
    ssh_pattern = r"git@github\.com:([^/]+)/(.+)\.git"
    match = re.match(ssh_pattern, url)
    if match:
        username, repo = match.groups()
        return f"https://github.com/{username}/{repo}.git"

    return url

def convert_https_to_ssh(url):
    """HTTPS形式のGitURLをSSH形式に変換する"""
    if not url or not isinstance(url, str):
        return url

    # HTTPS形式 (https://github.com/username/repo.git) をSSH形式に変換
    https_pattern = r"https://github\.com/([^/]+)/(.+)\.git"
    match = re.match(https_pattern, url)
    if match:
        username, repo = match.groups()
        return f"git@github.com:{username}/{repo}.git"

    return url

def git_push(zenn_dir, article_file, image_files, article_slug, repo_url=None, use_https=False):
    """GitHubリポジトリに変更をプッシュする（GitPythonを使用）"""
    try:
        # 元のカレントディレクトリを保存
        original_dir = os.getcwd()

        # リポジトリURLの決定と変換
        repo_url = repo_url or ZENN_GITHUB_REPO

        if use_https and repo_url:
            repo_url = convert_ssh_to_https(repo_url)
            print(f"HTTPS形式のURLを使用します: {repo_url}")

        try:
            # リポジトリオブジェクトの取得
            repo = git.Repo(zenn_dir)

            # 現在のリモートURLを保存
            original_remote_url = None
            if repo_url and repo.remotes:
                try:
                    original_remote_url = repo.remotes.origin.url
                    # リモートURLを一時的に変更
                    print(f"一時的にリモートURLを変更: {repo_url}")
                    repo.remotes.origin.set_url(repo_url)
                except Exception as e:
                    print(f"リモートURL変更中にエラー: {e}")

            # ファイルをステージング
            relative_article_file = os.path.relpath(article_file, zenn_dir)
            repo.git.add(relative_article_file)

            for img_file in image_files:
                relative_img_file = os.path.relpath(img_file, zenn_dir)
                repo.git.add(relative_img_file)

            # コミット
            commit_message = f"Add article: {article_slug}"
            repo.git.commit('-m', commit_message)

            # 現在のブランチ名を取得
            current_branch = repo.active_branch.name

            # リモートの変更を取得
            print("リモートの変更を取得中...")
            repo.git.fetch('origin')

            try:
                # リベースでリモートの変更を取り込む
                print(f"リモートの変更をリベース中...")
                repo.git.pull('--rebase', 'origin', current_branch)
            except git.GitCommandError as e:
                print(f"リベース中にエラー: {e}")

            # プッシュ
            print("変更をプッシュ中...")
            try:
                # 通常のプッシュを試す
                repo.git.push('origin', current_branch)
            except git.GitCommandError:
                # 通常のプッシュが失敗した場合はforce-with-leaseを使用
                print("通常のプッシュに失敗しました。force-with-leaseオプションでプッシュを試みます...")
                repo.git.push('--force-with-lease', 'origin', current_branch)

            # 元のリモートURLに戻す
            if original_remote_url and repo_url and repo.remotes:
                print(f"リモートURLを元に戻します: {original_remote_url}")
                repo.remotes.origin.set_url(original_remote_url)

            return True, "GitHub へのプッシュが完了しました。"

        except git.InvalidGitRepositoryError:
            return False, "指定されたディレクトリはGitリポジトリではありません。"
        except git.NoSuchPathError:
            return False, "指定されたパスが存在しません。"

    except Exception as e:
        # 元のリモートURLに戻す（エラー時も）
        try:
            if 'repo' in locals() and original_remote_url and repo_url and repo.remotes:
                repo.remotes.origin.set_url(original_remote_url)
        except:
            pass

        return False, f"予期せぬエラーが発生しました: {e}"
    finally:
        # 元のディレクトリに戻る（エラー時も）
        try:
            os.chdir(original_dir)
        except:
            pass

def validate_slug(slug):
    """スラグがZennの仕様に合っているか検証する"""
    # 半角英数字、ハイフン、アンダースコアのみで構成されているか
    if not re.match(r'^[a-z0-9_-]+$', slug):
        return False, "スラグには半角英数字（a-z0-9）、ハイフン（-）、アンダースコア（_）のみ使用できます"

    # 12〜50字の長さか
    if len(slug) < 12:
        return False, f"スラグは12字以上である必要があります（現在: {len(slug)}字）"
    if len(slug) > 50:
        return False, f"スラグは50字以下である必要があります（現在: {len(slug)}字）"

    return True, "スラグはZennの仕様に準拠しています"

def main():
    """メイン処理"""
    args = parse_args()

    # requirements.txtファイルの生成
    if args.gen_reqs:
        generate_requirements_file()
        sys.exit(0)

    # 依存パッケージの確認
    if args.check_deps:
        if check_dependencies():
            print("すべての依存パッケージがインストールされています。")
        sys.exit(0)

    # 依存パッケージの確認
    if not check_dependencies():
        print("依存パッケージのインストールが必要です。以下のコマンドを実行してください:")
        print("pip install GitPython PyYAML pykakasi")
        print("または、次のコマンドを実行してrequirements.txtを生成してください:")
        print(f"python {sys.argv[0]} --gen-reqs")
        sys.exit(1)

    try:
        # 記事ファイルを読み込む
        with open(args.article, 'r', encoding='utf-8') as f:
            content = f.read()

        # メタデータを抽出（コンテンツもフロントマターが除去された状態で返される）
        metadata, content = extract_metadata(content)

        # スラッグを生成
        article_slug = create_article_slug(metadata["title"], args.transliterate)

        # スラグを検証
        is_valid, slug_message = validate_slug(article_slug)
        if not is_valid:
            print(f"警告: {slug_message}")
            print("Zennの仕様に合わせて自動的にスラグを修正します。")
            article_slug = create_article_slug(f"article-{datetime.datetime.now().strftime('%m%d%H%M')}")
            is_valid, slug_message = validate_slug(article_slug)
            if not is_valid:
                print(f"エラー: スラグの自動修正に失敗しました。{slug_message}")
                sys.exit(1)
            else:
                print(f"修正されたスラグ: {article_slug}")

        # 絵文字を選択（メタデータに既に絵文字がある場合はそれを使用）
        if args.emoji:
            emoji = args.emoji
        elif metadata["emoji"] and metadata["emoji"] != DEFAULT_EMOJI:
            emoji = metadata["emoji"]
        else:
            emoji = select_emoji(metadata["category"], content)

        # 画像パスを変換
        content = convert_image_paths(content, article_slug, args.images)

        # フロントマターを生成
        frontmatter = create_frontmatter(metadata, emoji, args.state)

        # published_atが指定されている場合、frontmatterに追加
        if args.published_at:
            published_at = args.published_at
        elif metadata["published_at"]:
            published_at = metadata["published_at"]
        else:
            published_at = None

        if published_at:
            try:
                # 日時形式をチェック
                datetime.datetime.fromisoformat(str(published_at).replace('Z', '+00:00'))
                # フロントマターに追加
                frontmatter += f'\npublished_at: "{published_at}"'
            except ValueError:
                print(f"警告: 無効な日時形式です: {published_at}")
                print("正しい形式: YYYY-MM-DDTHH:MM:SS+09:00")

        # Zennフォーマットの記事を生成
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        zenn_filename = f"{today}-{article_slug}.md"

        # リポジトリURLを決定
        repo_url = args.repo if args.repo else ZENN_GITHUB_REPO

        # Zennディレクトリのパスを取得（カレントディレクトリをデフォルトとする）
        zenn_dir = os.getcwd()

        # 記事ディレクトリが存在しない場合は作成
        article_dir = os.path.join(zenn_dir, ZENN_ARTICLE_DIR)
        os.makedirs(article_dir, exist_ok=True)

        # 記事ファイルを作成
        zenn_article_path = os.path.join(article_dir, zenn_filename)
        with open(zenn_article_path, 'w', encoding='utf-8') as f:
            f.write(f"---\n{frontmatter}\n---\n\n{content}")

        # 画像ファイルをコピー
        copied_images = copy_images(args.images, article_slug, zenn_dir)

        # GitHubにプッシュ
        push_result = (True, "GitHub へのプッシュはスキップされました。")
        if args.push:
            push_result = git_push(zenn_dir, zenn_article_path, copied_images, article_slug, repo_url, args.use_https)

        # 結果を出力
        print("\n== Zenn公開準備完了レポート ==")
        print(f"記事タイトル: {metadata['title']}")
        print(f"スラッグ: {article_slug}")
        print(f"公開状態: {args.state}")
        print(f"出力ファイル: {zenn_article_path}")
        print(f"コピーした画像: {len(copied_images)}個")
        print(f"GitHubプッシュ: {push_result[1]}")

        if repo_url:
            print(f"リポジトリURL: {repo_url}")

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
