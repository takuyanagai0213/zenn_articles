# 生成AI記事用画像生成プロンプトガイド

## 基本方針

当メディアで使用する画像は、以下の基本方針に基づいて生成・選定します：

1. **一貫性**: メディアの視覚的アイデンティティを保つ一貫したスタイル
2. **正確性**: 技術的内容を正確に表現
3. **親しみやすさ**: 複雑なAI概念を視覚的にわかりやすく
4. **独自性**: 他メディアと差別化できるオリジナル性
5. **倫理性**: バイアスや偏見を避け、多様性を意識

## 画像種別ごとのプロンプト設計

### 1. アイキャッチ画像

**目的**: 記事内容を視覚的に表現し、クリックを促す

**基本構造**:
```
[スタイル指定], [主要オブジェクト/キャラクター], [動作/状態], [背景], [色調], [構図], [技術要素], --ar 16:9 --v 6.0 --q 2
```

**スタイルオプション**:
- デジタルイラスト風: `digital illustration, clean lines, vector art style`
- 3Dレンダリング風: `3D rendering, soft lighting, subtle shadows`
- ミニマルデザイン: `minimalist design, simple shapes, flat colors`
- 技術的図解風: `technical diagram style, blueprint aesthetic`

**例**:
```
Digital illustration, AI neural network visualized as glowing blue nodes connected by energy threads, processing data streams, dark tech background with code patterns, blue and purple color scheme, centered composition with depth, abstract AI concept, --ar 16:9 --v 6.0 --q 2
```

### 2. 技術解説図

**目的**: 複雑なAI概念・アーキテクチャをわかりやすく視覚化

**基本構造**:
```
[図解タイプ], [技術コンセプト], [構成要素], [データフロー], [ラベル指示], [色コード], [背景], --ar 16:9 --v 6.0 --q 2
```

**図解タイプオプション**:
- フローチャート: `flowchart diagram, process visualization`
- アーキテクチャ図: `architecture diagram, system components`
- 概念マップ: `concept map, relationship visualization`
- 比較図: `comparison diagram, side-by-side visualization`

**例**:
```
Architecture diagram, transformer model architecture, attention layers, embeddings, and feed-forward networks, with labeled components and data flow arrows, gradient color coding for different functions, minimal white background with subtle grid, --ar 16:9 --v 6.0 --q 2
```

### 3. データビジュアライゼーション

**目的**: データ・統計情報を視覚的に表現

**基本構造**:
```
[チャートタイプ], [データ内容], [データポイント指示], [比較要素], [カラースキーム], [ラベル指示], [背景], --ar 4:3 --v 6.0 --q 2
```

**チャートタイプオプション**:
- 棒グラフ: `bar chart, vertical/horizontal bars`
- 折れ線グラフ: `line graph, trend visualization`
- 円グラフ: `pie chart, percentage breakdown`
- ヒートマップ: `heatmap visualization, intensity gradient`

**例**:
```
Bar chart visualization, AI model performance comparison, 5 models with accuracy and processing time metrics, side-by-side grouped bars, blue-green gradient color scheme, clearly labeled axes and data points, clean white background with subtle grid, --ar 4:3 --v 6.0 --q 2
```

### 4. コンセプトイラスト

**目的**: 抽象的なAI概念を比喩的・象徴的に表現

**基本構造**:
```
[アートスタイル], [中心メタファー], [AI要素], [人間要素], [相互作用], [象徴的背景], [雰囲気/色調], --ar 16:9 --v 6.0 --q 2
```

**アートスタイルオプション**:
- シンボリック: `symbolic illustration, metaphorical representation`
- サイバーパンク: `cyberpunk aesthetic, high-tech low-life`
- ミニマリスト: `minimalist concept art, essential elements only`
- フュージョン: `fusion of organic and digital elements`

**例**:
```
Symbolic illustration, human hand and robotic hand reaching toward each other, neural network patterns flowing between them, binary code and natural elements in background, balance of blue technology tones and warm human tones, dramatic lighting, representing human-AI collaboration, --ar 16:9 --v 6.0 --q 2
```

### 5. プロセス図解

**目的**: 段階的なプロセスやワークフローを視覚化

**基本構造**:
```
[シーケンスタイプ], [プロセス名], [ステップ数と内容], [接続表現], [進行方向], [アイコン指示], [カラースキーム], --ar 16:9 --v 6.0 --q 2
```

**シーケンスタイプオプション**:
- 水平フロー: `horizontal process flow, left-to-right progression`
- 垂直フロー: `vertical process flow, top-to-bottom steps`
- サイクル: `cyclical process diagram, continuous flow`
- 階層型: `hierarchical workflow, nested processes`

**例**:
```
Horizontal process flow, machine learning pipeline visualization, 5 steps from data collection to model deployment, connected by animated arrows, left-to-right progression, simple iconic representations for each stage, gradient blue-to-green color scheme showing progression, --ar 16:9 --v 6.0 --q 2
```

## スタイル統一ガイドライン

当メディアのビジュアルアイデンティティを維持するために、以下の要素を一貫して使用してください：

### カラーパレット
- **プライマリカラー**: `#0B63E1`（ブルー）- AI技術を表現
- **セカンダリカラー**: `#10B981`（グリーン）- 成長・発展を表現
- **アクセントカラー**: `#7C3AED`（パープル）- 創造性・革新を表現
- **ニュートラル**: `#111827`～`#F9FAFB`（ダークグレー～ライトグレー）

### ビジュアル要素
- **ノードとエッジ**: 神経網を表現する接続点と線
- **デジタル粒子**: データを表現する小さな光の粒子
- **幾何学的形状**: 秩序と構造を表現する多角形・円
- **グラデーション**: 滑らかな移行と進化を表現

### 禁止事項
- ステレオタイプ的なロボット表現（人型メタリックロボットなど）
- 過度に未来的・SF的な表現（現実とかけ離れた表現）
- 恐怖を煽るような表現（人間を支配するAIなど）
- ジェンダー・人種バイアスを含む表現

## 生成AIツール別設定

### Midjourney

**バージョン設定**:
- 通常画像: `--v 6.0` (高品質・多様性)
- 写真風画像: `--v 6.0 --s 100` (写実性強化)
- 図解・チャート: `--v 6.0 --s 250` (クリアな線・テキスト)

**アスペクト比**:
- アイキャッチ: `--ar 16:9`
- 記事内図解: `--ar 4:3`
- ソーシャル用: `--ar 1:1`

**品質設定**:
- 標準: `--q 2`
- 高精細: `--q 5` (重要な詳細図)

### DALL-E 3

**プロンプト構造**:
```
Photo-realistic/Digital art/Technical diagram/Conceptual illustration of [主題], featuring [詳細], with [技術的特徴], [色調指定], high detail, professional lighting, [構図]
```

**スタイル指定追加**:
- `-clear background` (背景透過)
- `-maintain text clarity` (テキスト可読性維持)
- `-consistent style with previous images` (スタイル統一)

### Stable Diffusion

**モデル推奨**:
- 一般的なイラスト: SDXL 1.0
- 技術図解: Juggernaut XL
- 写真風: Realistic Vision V5.1

**追加設定**:
- ネガティブプロンプト: `low quality, blurry, distorted text, incorrect labels, unprofessional, childish`
- サンプリングステップ: 25-30
- CFG Scale: 7.5

## プロンプト作成プロセス

1. **記事分析**: 記事の主題・キーポイントを特定
2. **視覚的要素特定**: 表現すべき技術・概念・データの要素リスト作成
3. **表現方法選択**: 最適な視覚化手法の選定（図解/チャート/イラスト）
4. **プロンプト作成**: 上記テンプレート活用
5. **バリエーション生成**: 2-3パターンのプロンプト作成
6. **評価と選定**: 技術的正確性、視覚的魅力、ブランド一貫性で評価

## 生成後の編集ガイドライン

生成された画像は必要に応じて以下の編集を行います：

1. **テキスト修正**: 生成AIによるテキストは読みづらい場合が多いため、必要に応じてテキストオーバーレイを追加
2. **色調補正**: ブランドカラーに合わせた調整
3. **クロッピング**: 最適な構図へのトリミング
4. **合成・統合**: 複数生成画像の最適部分を組み合わせる
5. **アノテーション追加**: 説明ラベル・矢印などの付加

## 保存・管理ガイドライン

- **ファイル名命名規則**: `[記事ID]_[画像タイプ]_[連番].[拡張子]`
  例: `ai_llm_transformer_hero_01.png`

- **メタデータ追加**:
  - Title: 画像内容の簡潔な説明
  - Description: 使用プロンプトの要約
  - Keywords: 関連技術キーワード

- **解像度要件**:
  - アイキャッチ: 1200×675px (@2x: 2400×1350px)
  - 記事内画像: 800×600px (@2x: 1600×1200px)
  - ソーシャル用: 1080×1080px

- **ファイル形式**:
  - 写真・イラスト: WebP (JPEG代替)
  - 図解・図表: PNG (透明背景必要時)
  - アニメーション: GIF/MP4 (容量最適化)

このガイドラインに従って作成された画像は、`assets/images/[年月]/[記事ID]/` ディレクトリに保存してください。
