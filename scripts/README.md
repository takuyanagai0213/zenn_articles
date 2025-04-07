# AI Tech Media スクリプト集

このディレクトリには、AI Tech Media 記事制作プロセスを自動化するためのスクリプトが含まれています。

## zenn_publisher.py

Zenn記事公開を自動化するスクリプトです。記事ファイルをZenn向けに変換し、GitHubリポジトリに公開するための機能を提供します。

### 使用方法

```bash
python zenn_publisher.py --article path/to/article.md --images path/to/images/ [options]
```

### オプション

- `--article` (必須): 記事ファイルのパス
- `--images`: 画像ディレクトリのパス（オプション）
- `--emoji`: 記事に使用する絵文字（オプション、自動選定も可能）
- `--state`: 公開状態 published/draft（オプション、デフォルト: draft）
- `--push`: GitHubにプッシュするかどうか（フラグ、指定すると実行）

### 実行例

```bash
# 下書きとして記事を準備（GitHubにはプッシュしない）
python zenn_publisher.py --article final_drafts/ai-trends-2023.md --images final_drafts/images/

# 公開記事として準備してGitHubにプッシュ
python zenn_publisher.py --article final_drafts/ai-trends-2023.md --images final_drafts/images/ --state published --push

# 絵文字を指定して下書き準備
python zenn_publisher.py --article final_drafts/ai-trends-2023.md --emoji 🤖
```

### 必要なパッケージ

このスクリプトを実行するには以下のパッケージが必要です：

```
pyyaml
```

インストール：

```bash
pip install pyyaml
```

### 出力物

スクリプトの実行後、以下のものが生成されます：

1. `articles/YYYY-MM-DD-[記事スラッグ].md` - Zenn形式の記事ファイル
2. `images/[記事スラッグ]/` - 記事に含まれる画像ファイル
3. コンソールに出力される「Zenn公開準備完了レポート」

### トラブルシューティング

#### GitHubプッシュに関する問題

- エラー「not a git repository」: スクリプトはカレントディレクトリがGitリポジトリであることを前提としています。正しいディレクトリで実行しているか確認してください。
- エラー「Authentication failed」: GitHubへの認証が失敗しています。SSHキーまたはGitの資格情報が正しく設定されているか確認してください。

#### 画像に関する問題

- 画像が表示されない場合: 画像のパスが正しく変換されているか確認してください。また、`images/[記事スラッグ]/`ディレクトリに画像ファイルが正しくコピーされているか確認してください。

---

## 共通事項

### ログ

各スクリプトはコンソールにログを出力します。詳細なログが必要な場合は、`--verbose`または`-v`オプションを指定してください（実装されている場合）。

### 設定ファイル

設定が必要なスクリプトは、同じディレクトリ内の`.env`ファイルから環境変数を読み込みます。`.env.example`をコピーして`.env`を作成し、必要な設定を行ってください。
