# AI Tech Media 記事制作プロセス

## 概要

このドキュメントでは、AI Tech Mediaにおける生成AI関連記事の情報収集から公開までの一連のプロセスを詳述します。本プロセスは2025年の生成AI技術動向を効率的かつ正確に伝えるための標準的な手順として確立されたものです。

## フォルダ構成

```
ai_tech_media/
├── logs/                          # 制作プロセスの記録
│   ├── meeting_minutes/           # 会議議事録
│   ├── article_drafts/            # 記事ドラフトのバージョン履歴
│   ├── structure_plans/           # 記事構成案の履歴
│   ├── reviews/                   # レビュー記録
│   ├── progress/                  # 進捗報告書
│   ├── process_artifacts/         # プロセス成果物の保管
│   └── analytics/                 # パフォーマンス分析
│       ├── article_metrics/       # 記事指標分析
│       ├── audience_insights/     # 読者インサイト
│       ├── content_element_effects/ # コンテンツ要素効果測定
│       ├── engagement_patterns/   # エンゲージメントパターン
│       └── a_b_test_results/      # A/Bテスト結果
├── templates/                     # テンプレート集約ディレクトリ
│   ├── article/                   # 記事テンプレート
│   ├── agent/                     # エージェントテンプレート
│   └── zenn/                      # Zenn特化テンプレート
└── prompts/                      # AIエージェント用プロンプト
    ├── planning_agents.md         # 企画・編集会議プロセス用エージェント
    ├── research_agents.md         # 情報収集プロセス用エージェント
    ├── structure_agents.md        # 記事構成作成プロセス用エージェント
    ├── draft_agents.md            # 記事ドラフト作成プロセス用エージェント
    ├── edit_publish_agents.md     # 編集・公開準備プロセス用エージェント
    ├── framework_agents.md        # エージェント連携フレームワーク
    └── zenn_agents.md             # Zenn特化プロセス用エージェント
```

## 制作プロセス

### 1. 企画・編集会議プロセス (所要時間: 40-55分)

#### a. トレンド分析と企画立案
- **実行プロンプト**: `prompts/planning_agents.md#トレンド分析エージェント`
- **入力データ**: 最新の検索データ、アクセス解析データ
- **実行コマンド**:
```
mcp_brave_brave_web_search (query: "生成AI トレンド 最新 技術動向", count: 5)
```
- **出力**: トレンド分析レポートと記事企画案

#### b. 記事プランニング
- **実行プロンプト**: `prompts/planning_agents.md#オーディエンス分析エージェント`
- **入力データ**: トレンド分析レポート、読者行動データ
- **実行メソッド**: オーディエンス分析エージェントに読者ニーズを分析させ、企画案とマッチング
- **人間レビュー**: 企画案の最終決定と方向性の承認

#### c. リソース配分と担当者決定
- **実行プロンプト**: `prompts/planning_agents.md#リソースマネージャーエージェント`
- **入力データ**: 承認された企画案、担当者のスキルマトリックス
- **出力**: リソース配分表と担当者アサイン案

#### d. 編集スケジュールの設定
- **実行プロンプト**: `prompts/planning_agents.md#タイムラインエージェント`
- **入力データ**: リソース配分表、公開カレンダー
- **出力**: 詳細スケジュールと締切設定

#### e. Zenn特化分析（該当する場合）
- **実行プロンプト**: `prompts/zenn_agents.md#Zennスキャンエージェント`
- **入力データ**: Zennプラットフォームの最新データ
```
mcp_brave_brave_web_search (query: "Zenn 人気記事 [カテゴリ名] 最新", count: 5)
```
- **出力**: Zenn特化型トレンドレポート
- **拡張実装**: 週3回の定期スキャン（月・水・金）
- **追加出力**: `zenn/trend_analysis/weekly_reports/YYYY-MM-DD_trends.md`
- **トレンド予測**: 次週トレンド予測データ生成（`zenn/trend_analysis/weekly_reports/YYYY-MM-DD_prediction.md`）

### 2. 情報収集 (所要時間: 30-40分)

#### a. 最新情報の取得と時間設定
- **実行プロンプト**: `prompts/research_agents.md#検索エージェント`
- **前処理**: 現在時刻の取得
```
mcp_Time_MCP_Server_get_current_time (timezone: "Asia/Tokyo")
```
- **実行コマンド**:
```
mcp_brave_brave_web_search (query: "最新 生成AI ニュース トピック [日付範囲]", count: 15)
```

#### b. データ検証と整理
- **実行プロンプト**: `prompts/research_agents.md#データ検証エージェント`
- **入力データ**: 検索結果JSON
- **処理方法**: 情報の信頼性評価、重複排除、関連性ランキング
- **出力**: 検証済みデータセット（`research/search_results/YYYY-MM-DD_[記事ID]_verified.json`）

#### c. コンテンツキュレーション
- **実行プロンプト**: `prompts/research_agents.md#コンテンツキュレーターエージェント`
- **入力データ**: 検証済みデータセット
- **処理方法**: トピック優先度判定アルゴリズムによる重要情報抽出
- **出力**: 記事素材ダイジェスト（`research/reference_materials/YYYY-MM-DD_[記事ID]_digest.md`）

#### d. 視覚素材収集
- **実行プロンプト**: `prompts/research_agents.md#画像探索エージェント`
- **実行コマンド**:
```
mcp_brave_brave_web_search (query: "[トピック名] 画像 スクリーンショット 公式", count: 3)
```
- **出力**: 画像素材情報リスト（`assets/images/YYYY-MM-DD_[記事ID]_image_list.md`）

#### e. SEO調査
- **実行プロンプト**: `prompts/research_agents.md#SEOリサーチエージェント`
- **実行コマンド**:
```
mcp_brave_brave_web_search (query: "生成AI トレンド キーワード [年] SEO", count: 5)
```
- **出力**: SEOキーワードレポート（`seo/keywords/YYYY-MM-DD_[記事ID]_keywords.md`）

#### f. Zennプラットフォーム特化調査
- **実行プロンプト**: `prompts/zenn_agents.md#Zennデータ分析エージェント`
- **入力データ**: Zenn特化型トレンドレポート
- **処理方法**: タグ人気度分析とカテゴリ別パフォーマンス評価
- **出力**: Zenn特化データレポート（`zenn/trend_analysis/tag_popularity/YYYY-MM-DD_tags.md`）

### 3. 記事構成作成 (所要時間: 15-20分)

#### a. 基本構造の決定
- **実行プロンプト**: `prompts/structure_agents.md#構成設計エージェント`
- **入力データ**: 記事素材ダイジェスト、SEOキーワードレポート
- **処理方法**: 階層的構造設計アルゴリズムによる最適構成生成
- **出力**: 記事構成案（`logs/structure_plans/YYYY-MM-DD_[記事ID]_structure.md`）

#### b. SEO最適化
- **実行プロンプト**: `prompts/structure_agents.md#SEO最適化エージェント`
- **入力データ**: 記事構成案、SEOキーワードレポート
- **処理方法**: キーワード配置最適化とSEO評価
- **出力**: SEO最適化構成（`logs/structure_plans/YYYY-MM-DD_[記事ID]_seo_structure.md`）

#### c. コンテンツバランス調整
- **実行プロンプト**: `prompts/structure_agents.md#コンテンツバランスエージェント`
- **入力データ**: SEO最適化構成
- **処理方法**: セクション別情報量分析と調整
- **出力**: 詳細情報マップ（`logs/structure_plans/YYYY-MM-DD_[記事ID]_content_map.md`）

#### d. フック設計
- **実行プロンプト**: `prompts/structure_agents.md#フック設計エージェント`
- **入力データ**: 詳細情報マップ
- **処理方法**: エンゲージメント最大化ポイント特定
- **出力**: フック設計プラン（`logs/structure_plans/YYYY-MM-DD_[記事ID]_hooks.md`）

#### e. 人間レビュー
- 構成案の最終確認と修正指示
- レビューコメント記録（`logs/reviews/YYYY-MM-DD_[記事ID]_structure_review.md`）

#### f. Zenn最適化構成調整
- **実行プロンプト**: `prompts/zenn_agents.md#Zenn構成最適化エージェント`
- **入力データ**: 記事構成案、Zenn特化データレポート
- **出力**: Zenn最適化構成（`logs/structure_plans/YYYY-MM-DD_[記事ID]_zenn_structure.md`）

### 4. 記事ドラフト作成 (所要時間: 40-60分)

#### a. テンプレート適用
- **実行プロンプト**: `prompts/draft_agents.md#執筆エージェント`
- **入力データ**: 最終構成案、記事テンプレート
- **処理方法**: テンプレート自動適用と構成マッピング
- **出力**: 記事ドラフト初期版（`articles/drafts/YYYY-MM-DD_[記事ID]_draft_v1.md`）

#### b. セクション執筆
- **実行プロンプト**: `prompts/draft_agents.md#技術解説エージェント`
- **入力データ**: 記事素材ダイジェスト、セクション構成
- **処理方法**: 段階的技術解説生成アルゴリズム
- **出力**: セクション別コンテンツ（`articles/drafts/YYYY-MM-DD_[記事ID]_sections/`）

#### c. 例示生成
- **実行プロンプト**: `prompts/draft_agents.md#例示生成エージェント`
- **入力データ**: 技術解説セクション
- **処理方法**: コンテキスト適応型例示生成
- **出力**: コード例・ユースケース（`articles/drafts/YYYY-MM-DD_[記事ID]_examples.md`）

#### d. ビジュアル設計
- **実行プロンプト**: `prompts/draft_agents.md#ビジュアル設計エージェント`
- **入力データ**: セクション別コンテンツ、画像素材情報
- **処理方法**: 視覚情報最適配置アルゴリズム
- **出力**: ビジュアル要素配置プラン（`assets/infographics/YYYY-MM-DD_[記事ID]_visual_plan.md`）

#### e. 引用管理
- **実行プロンプト**: `prompts/draft_agents.md#引用管理エージェント`
- **入力データ**: 記事全文、参考資料リスト
- **処理方法**: 引用適正化と参考文献形式統一
- **出力**: 引用管理表（`logs/article_drafts/YYYY-MM-DD_[記事ID]_citations.md`）

#### f. ドラフト統合
- **実行プロンプト**: `prompts/framework_agents.md#編集長エージェント`
- **入力データ**: 全セクション、例示、ビジュアル計画
- **処理方法**: 一貫性確保統合アルゴリズム
- **出力**: 完全ドラフト（`articles/drafts/YYYY-MM-DD_[記事ID]_draft_complete.md`）

#### g. Zenn特化マークダウン最適化
- **実行プロンプト**: `prompts/zenn_agents.md#マークダウン最適化エージェント`
- **入力データ**: 完全ドラフト
- **処理方法**: Zenn特化マークダウン記法の適用
- **出力**: Zenn最適化ドラフト（`articles/drafts/YYYY-MM-DD_[記事ID]_zenn_optimized.md`）

### 5. 編集・最適化 (所要時間: 20-30分)

#### a. 校閲
- **実行プロンプト**: `prompts/edit_publish_agents.md#校閲エージェント`
- **入力データ**: 完全ドラフト
- **処理方法**: 文章品質向上アルゴリズム
- **出力**: 校閲済みドラフト（`articles/drafts/YYYY-MM-DD_[記事ID]_edited.md`）

#### b. ファクトチェック
- **実行プロンプト**: `prompts/edit_publish_agents.md#ファクトチェックエージェント`
- **入力データ**: 校閲済みドラフト、参考資料
- **処理方法**: 事実検証アルゴリズムによる正確性確認
- **出力**: 検証レポート（`logs/reviews/YYYY-MM-DD_[記事ID]_fact_check.md`）

#### c. リーダビリティ向上
- **実行プロンプト**: `prompts/edit_publish_agents.md#リーダビリティエージェント`
- **入力データ**: 校閲済みドラフト
- **処理方法**: 読みやすさ最適化アルゴリズム
- **出力**: 読みやすさ向上ドラフト（`articles/drafts/YYYY-MM-DD_[記事ID]_readable.md`）

#### d. SEO最終調整
- **実行プロンプト**: `prompts/edit_publish_agents.md#SEO最終調整エージェント`
- **入力データ**: 読みやすさ向上ドラフト、SEOキーワードレポート
- **処理方法**: 最終SEOスコア最適化
- **出力**: SEO最適化記事（`articles/drafts/YYYY-MM-DD_[記事ID]_seo_final.md`）

#### e. 内部リンク設定
- **実行プロンプト**: `prompts/edit_publish_agents.md#内部リンク提案エージェント`
- **入力データ**: SEO最適化記事、過去記事データベース
- **処理方法**: 関連性ベース内部リンク提案
- **出力**: 内部リンク提案リスト（`logs/reviews/YYYY-MM-DD_[記事ID]_internal_links.md`）

#### f. 人間最終レビュー
- 最終記事レビューと承認
- フィードバック記録（`logs/reviews/YYYY-MM-DD_[記事ID]_final_review.md`）

#### g. 最終公開設定
- **実行プロンプト**: `prompts/framework_agents.md#品質管理エージェント`
- **入力データ**: 全成果物と設定
- **処理方法**: 公開前最終チェック
- **出力**: 公開確認リスト（`logs/progress/YYYY-MM-DD_[記事ID]_publish_checklist.md`）
- **人間承認**: 公開承認と実行

### 6. 公開準備 (所要時間: 15-20分)

#### a. メタデータ設定
- **実行プロンプト**: `prompts/edit_publish_agents.md#メタデータ設定エージェント`
- **入力データ**: 最終記事、SEOキーワードレポート
- **処理方法**: メタデータ最適化アルゴリズム
- **出力**: メタデータ設定ファイル（`seo/YYYY-MM-DD_[記事ID]_metadata.md`）

#### b. SNS投稿文生成
- **実行プロンプト**: `prompts/edit_publish_agents.md#SNS最適化エージェント`
- **入力データ**: 最終記事、プラットフォーム別特性データ
- **処理方法**: プラットフォーム最適化テキスト生成
- **出力**: SNS投稿文セット（`social/YYYY-MM-DD_[記事ID]_sns_posts.md`）

#### c. メールマガジン用要約
- **実行プロンプト**: `prompts/edit_publish_agents.md#メールマーケティングエージェント`
- **入力データ**: 最終記事
- **処理方法**: 要約最適化アルゴリズム
- **出力**: メールマガジン用テキスト（`social/newsletter/YYYY-MM-DD_[記事ID]_newsletter.md`）

#### d. 画像最終調整
- **実行プロンプト**: `prompts/edit_publish_agents.md#画像最適化エージェント`
- **入力データ**: 画像素材、ビジュアル要素配置プラン
- **処理方法**: 画像最適化処理とAlt属性設定
- **出力**: 最終画像セット（`assets/images/YYYY-MM-DD_[記事ID]_final/`）

#### e. 公開スケジュール設定
- **実行プロンプト**: `prompts/edit_publish_agents.md#公開スケジュールエージェント`
- **入力データ**: 公開カレンダー、分析データ
- **処理方法**: 最適公開時間決定アルゴリズム
- **出力**: 公開スケジュール（`logs/progress/YYYY-MM-DD_[記事ID]_publish_schedule.md`）

#### f. 最終公開設定
- **実行プロンプト**: `prompts/framework_agents.md#品質管理エージェント`
- **入力データ**: 全成果物と設定
- **処理方法**: 公開前最終チェック
- **出力**: 公開確認リスト（`logs/progress/YYYY-MM-DD_[記事ID]_publish_checklist.md`）
- **人間承認**: 公開承認と実行

## logsディレクトリの重要性

各制作プロセスで生成される記録は、logsディレクトリに保存し、必ず保持する必要があります。これらのファイルは以下の目的で重要です：

1. **意思決定の透明性確保**：企画・編集会議の議事録（`meeting_minutes/`）は、なぜその記事トピックが選ばれたのか、どのような方向性で進めることになったのかの根拠を示します。

2. **情報の追跡可能性**：情報収集プロセスの成果物（`process_artifacts/`）は、記事の事実的根拠となるデータソースとその検証プロセスを証明します。

3. **品質管理**：構成案（`structure_plans/`）やレビュー記録（`reviews/`）は、記事の構造的一貫性と正確性を保証するためのチェックポイントとして機能します。

4. **継続的改善**：過去の記事制作プロセスのログを分析することで、効率化やクオリティ向上のための改善点を特定できます。

5. **法的保護**：引用管理表など（`article_drafts/`内）は、著作権遵守の証拠となり、法的問題から組織を保護します。

6. **知識の共有と継承**：新しいチームメンバーが過去のプロセスを学ぶための教材として活用できます。

これらのログファイルは、少なくとも記事公開から1年間は保持し、定期的なアーカイブを行うことを推奨します。特に重要な記事や大きな反響があった記事に関するログは、より長期間保存してください。

## ツール活用ガイド

### 1. Brave MCP Server
- **主な用途**: 情報収集、最新トレンド把握、競合記事調査
- **効果的なクエリ構築法**:
  - 時期指定: "[トピック] [年月]"
  - 詳細検索: "[製品名] 機能 詳細 最新"
  - 画像検索: "[トピック] 画像 公式"
- **結果のフィルタリング**:
  - 情報源の信頼性確認
  - 公開日の確認
  - 内容の独自性チェック

### 2. Time MCP Server
- **主な用途**: 記事の時間軸設定、現在時刻の取得
- **タイムゾーン設定**: "Asia/Tokyo"を指定して日本時間を取得
- **公開日時の整合性**: 記事内の日付情報と現在時刻の整合性確認
