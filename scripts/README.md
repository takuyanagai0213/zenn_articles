# Scripts

このディレクトリには、AI Tech Mediaで使用される様々な自動化スクリプトが含まれています。

## Zenn投稿機能

### セットアップ
1. Zennアカウントを作成し、GitHubリポジトリと連携します
2. `.env.example`をコピーして`.env`を作成し、必要な情報を設定します：
   - `GITHUB_TOKEN`: GitHubのパーソナルアクセストークン
   - `ZENN_GITHUB_REPO`: ZennのGitHubリポジトリ（例：`username/zenn-content`）
3. 必要なパッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```

### 使用方法

```python
from scripts.zenn_publisher import ZennPublisher

# 初期化
publisher = ZennPublisher()

# 新規記事の投稿
result = publisher.publish_article(
    title="テスト記事",
    content="# はじめに\nこれはテスト記事です。",
    topics=["Python", "AI"],
    type="tech",  # "tech" または "idea"
    published=False  # Trueで公開、Falseで下書き
)
print(result)

# 既存記事の更新
result = publisher.update_article(
    slug="テスト記事",  # 記事のスラッグ（ファイル名から.mdを除いたもの）
    title="更新後のタイトル",
    content="# 更新後の内容\nこれは更新されたコンテンツです。",
    topics=["Python", "AI", "Tutorial"],
    published=True
)
print(result)
```

### 注意事項
- GitHubトークンには`repo`スコープが必要です
- Zennの記事は`articles/`ディレクトリに保存されます
- トピックスは最大5つまで設定可能です
- 記事タイプは`tech`または`idea`のみ指定可能です
- ファイル名（スラッグ）は自動的に生成されます
