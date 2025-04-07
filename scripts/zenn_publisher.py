import os
import re
import frontmatter
from github import Github
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

class ZennPublisher:
    def __init__(self):
        load_dotenv()
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_repo = os.getenv('ZENN_GITHUB_REPO')  # format: "username/repo"
        self.gh = Github(self.github_token)

    def generate_valid_slug(self, title):
        """
        タイトルから有効なslugを生成します

        - 半角英数字（a-z0-9）、ハイフン（-）、アンダースコア（_）のみ使用可能
        - 12〜50字の制限
        - グローバルでユニークになるようにタイムスタンプを付与
        """
        # タイトルを小文字に変換し、英数字以外をハイフンに置換
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)

        # 先頭と末尾のハイフンを削除
        slug = slug.strip('-')

        # タイムスタンプを生成（YYYYMMDDHHmmss形式）
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        # タイトルが長すぎる場合は切り詰める（タイムスタンプ用に余裕を持たせる）
        max_title_length = 35  # 50 - 15（タイムスタンプ用）
        if len(slug) > max_title_length:
            slug = slug[:max_title_length].rstrip('-')

        # slugが短すぎる場合は、タイトルを繰り返して長さを調整
        min_title_length = 12 - len(timestamp) - 1  # 12 - タイムスタンプ長 - ハイフン
        while len(slug) < min_title_length:
            slug = f"{slug}-{slug}"

        # タイムスタンプを付与して最終的なslugを生成
        final_slug = f"{slug}-{timestamp}"

        return final_slug

    def validate_article_type(self, type):
        """記事タイプを検証します"""
        valid_types = ["tech", "idea"]
        if type not in valid_types:
            raise ValueError(f"記事タイプは{valid_types}のいずれかである必要があります")
        return type

    def validate_topics(self, topics):
        """トピックスを検証します"""
        if not topics or not isinstance(topics, list):
            return ["Tech"]
        return topics[:5]  # Zennは最大5つまで

    def publish_article(self, title, content, topics=None, type="tech", published=False, emoji="✨", published_at=None):
        """
        Zennの記事を作成してGitHubリポジトリにプッシュします

        Args:
            title (str): 記事のタイトル
            content (str): 記事の本文（Markdown形式）
            topics (list): 記事のトピックス（最大5つ）
            type (str): 記事タイプ（"tech" or "idea"）
            published (bool): 公開するかどうか
            emoji (str): アイキャッチ用の絵文字（1文字）
            published_at (str): 公開日時（YYYY-MM-DD or YYYY-MM-DD HH:mm形式、オプション）
        """
        # 各パラメータを検証
        type = self.validate_article_type(type)
        topics = self.validate_topics(topics)

        # Zennの記事メタデータを作成
        metadata = {
            "title": title,
            "emoji": emoji,
            "type": type,
            "topics": topics,
            "published": published,
        }

        # 公開予約時のみpublished_atを設定
        if published and published_at:
            metadata["published_at"] = published_at

        # frontmatterとコンテンツを結合
        article = frontmatter.Post(content, **metadata)

        # 有効なslugを生成
        slug = self.generate_valid_slug(title)
        filename = f"articles/{slug}.md"

        try:
            # GitHubリポジトリに接続
            repo = self.gh.get_repo(self.github_repo)

            # 記事をプッシュ
            repo.create_file(
                path=filename,
                message=f"Add new article: {title}",
                content=frontmatter.dumps(article),
                branch="main"
            )
            return f"記事が正常に作成されました: {filename}"
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    def update_article(self, slug, title=None, content=None, topics=None, type=None, published=None, emoji=None, published_at=None):
        """
        既存の記事を更新します

        Args:
            slug (str): 記事のスラッグ（ファイル名から.mdを除いたもの）
            title (str): 新しいタイトル（オプション）
            content (str): 新しい本文（オプション）
            topics (list): 新しいトピックス（オプション）
            type (str): 記事タイプ（"tech" or "idea"）（オプション）
            published (bool): 公開状態の変更（オプション）
            emoji (str): アイキャッチ用の絵文字（1文字）（オプション）
            published_at (str): 公開日時（YYYY-MM-DD or YYYY-MM-DD HH:mm形式、オプション）
        """
        try:
            repo = self.gh.get_repo(self.github_repo)
            file_path = f"articles/{slug}.md"

            # 既存のファイルを取得
            file = repo.get_contents(file_path)
            current_article = frontmatter.loads(file.decoded_content.decode())

            # 更新するフィールドを設定
            if title:
                current_article.metadata['title'] = title
            if topics:
                current_article.metadata['topics'] = self.validate_topics(topics)
            if type:
                current_article.metadata['type'] = self.validate_article_type(type)
            if published is not None:
                current_article.metadata['published'] = published
            if emoji:
                current_article.metadata['emoji'] = emoji
            if content:
                current_article.content = content

            # 公開予約時のみpublished_atを設定
            if published and published_at:
                current_article.metadata['published_at'] = published_at
            elif not published and 'published_at' in current_article.metadata:
                del current_article.metadata['published_at']

            # 更新をプッシュ
            repo.update_file(
                path=file_path,
                message=f"Update article: {current_article.metadata['title']}",
                content=frontmatter.dumps(current_article),
                sha=file.sha,
                branch="main"
            )
            return f"記事が正常に更新されました: {file_path}"
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

if __name__ == "__main__":
    # 記事の情報を設定
    publisher = ZennPublisher()
    result = publisher.publish_article(
        title="Zenn Publisher APIのテスト記事",
        content="これはテスト記事です。\n\n# はじめに\n\nこれはZenn Publisher APIのテストです。",
        topics=["Python", "API"],
        type="tech",
        published=False,  # 下書きとして保存
        emoji="🚀"  # アイキャッチ絵文字を設定
    )
    print(result)
