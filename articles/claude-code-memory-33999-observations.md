---
title: "Claude Code で 33,999 observations を育てた全記録 ── Auto-Memory 実践 3ヶ月半の軌跡"
emoji: "🧠"
type: "tech"
topics: ["claudecode", "ai", "contextengineering", "memory"]
published: true
---

# Claude Code で 33,999 observations を育てた全記録 ── Auto-Memory 実践 3ヶ月半の軌跡

## この記事で伝えたいこと

Claude Code を 3ヶ月半使い込んだ結果、手元に「自分専用の記憶システム」が育っていた。

- **Markdown file 2,538 本**
- **Typed memory 259 本** (user/feedback/project/reference の 4 種)
- **Observation DB 33,999 件** (SQLite + vector-db)
- **セッション要約 7,040 件**
- **User prompts 29,668 件**

これは意識して「メモリを育てよう」と思った結果ではない。普段通り Claude Code で仕事をしていたら、気づいたらこの規模になっていた。

本記事では、この記憶システムの全構造・運用記録・3ヶ月半の成長曲線・ハマったポイント・見えてきた原則を公開する。前作「[Claude Codeで100個のSkillを育てた全記録](https://zenn.dev/takuyanagai0213/articles/claude-code-100-skills-full-record)」の次の章として、**Skill(振る舞い)の外側にある Memory(記憶)の領域**を掘る。

## 先に数字をどうぞ

### Observation Database (claude-mem)

| 指標 | 値 |
|---|---:|
| Total observations | **33,999** |
| User prompts | 29,668 |
| Session summaries | 7,040 |
| SDK sessions | 1,592 |
| Tracked projects | 59 |
| DB size | 2.0 GB |
| 運用期間 | 2025-12-20 〜 2026-04-12 (114 日) |
| 日次平均 | 298 obs/day |

### File-based Memory

| 指標 | 値 |
|---|---:|
| 総ファイル数 | 3,176 |
| Markdown ファイル | 2,538 |
| Typed memories | 259 |
| MEMORY.md 行数 | 269 |
| 総容量 | 881 MB |

### Observation type 分布

```
discovery │████████████████████████████████████ 19,381 (57%)
change    │███████████                           6,297 (18%)
decision  │████████                              4,245 (12%)
feature   │█████                                 2,816 ( 8%)
bugfix    │█                                       746 ( 2%)
refactor  │█                                       514 ( 2%)
```

### 成長曲線

```
2025-12 (12 days): 9,244  ━━━━━━━━━━━━━━ 770/day  ← 導入期フラッド
2026-01 (31 days): 8,784  ━━━━━         283/day
2026-02 (28 days): 9,769  ━━━━━━        349/day
2026-03 (31 days): 4,863  ━━━           157/day
2026-04 (12 days): 1,339  ━━            112/day
```

## Context Engineering の次の章 ── Skill の外側に広がっていた空白

前作で 100 個の Skill を育てた話を書いた。あの記事は「振る舞いの外部化」の話だった。

Skill は**今このセッションで何をすべきか**を定義する。だが、振る舞いを実行するためには、**過去に何があったか**が必要だ。

- 先週 AI 秘書と決めた distribution 戦略は?
- このプロジェクトで過去に直面した pitfall は?
- 1ヶ月前の 1on1 で約束した宿題は?
- この類の問題は以前どう解決したか?

Skill だけでは、これらに答えられない。セッションを跨いで**過去を参照する仕組み**が必要だった。

それが Memory System だ。

Skill が「振る舞いの司令塔」なら、Memory は「経験の貯蔵庫」。両者がセットになって初めて、Claude Code は**継続する同僚**になる。

## 2層構造の Memory System

3ヶ月半育てた Memory は、偶然 2 層構造で落ち着いている。

```
┌─────────────────────────────────────────────┐
│ Layer 1: File-based Memory                  │
│   ~/.claude/projects/{project}/memory/      │
│   ├ MEMORY.md (269 lines, index)            │
│   ├ 259 typed markdown files (core)         │
│   ├ raw-sources/ (849 MB, imports)          │
│   └ brainstorming/, meeting-minutes/, etc.  │
│   → 人間が読む、手動編集可能                │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Layer 2: Observation Database               │
│   ~/.claude-mem/claude-mem.db (2.0 GB)      │
│   ├ observations (33,999 records)           │
│   ├ session_summaries (7,040)               │
│   ├ user_prompts (29,668)                   │
│   └ vector-db (semantic search)             │
│   → 自動抽出、SessionStart で index 呼び戻し│
└─────────────────────────────────────────────┘
```

2 層の役割分担:

| 層 | 誰が書くか | 形式 | 検索方法 | 粒度 |
|---|---|---|---|---|
| File-based | 人間 + AI (手動で確定) | Markdown (frontmatter + 本文) | Grep / Glob | 1 ファイル = 1 トピック |
| Observation DB | 完全自動 (claude-mem) | 構造化 record | SQL + vector search | 1 record = 1 出来事 |

File-based は**意図的に残すもの**、Observation DB は**自動で流れていくもの**。両者はお互いを補完している。

## Layer 1 深堀り: 259 の typed memory

File-based Memory の核は `~/.claude/projects/{project-slug}/memory/` 配下に置かれる。プロジェクトごとに独立。

### 4 つの memory type

すべての記憶ファイルは frontmatter で type を持つ:

```markdown
---
name: 短いタイトル
description: 一行で何の記憶か
type: user | feedback | project | reference
---

本文...
```

4 type の分布:

| type | 件数 | 目的 |
|---|---:|---|
| **project** | 89 | 進行中の仕事、判断、背景 |
| **user** | 85 | ユーザーの役割、専門性、嗜好 |
| **feedback** | 57 | 「こうしないで」「こうやって」の蓄積 |
| **reference** | 28 | 外部リソースへのポインタ |

#### project (89 本)

「あの件どうなった?」を埋めるための記憶。

例:
- `project_distribution_experiment.md` — コンテンツ配信レーン選定の実験フレーム
- `project_autonomous_verification.md` — エージェント完全自律検証の記録

これらは**ある時点の状態**を凍結したスナップショット。進行中プロジェクトの「なぜ」「どこまで」「次は」を後から呼び戻せる。

#### user (85 本)

「あなたは誰ですか」を AI が毎回覚え直さなくていいための記憶。

例:
- `user_personal_profile.md` — 居住地、家族構成、お出かけ履歴、食の好み
- `user_ramen_club.md` — ラーメン部(父息子の週末サークル)
- `thought_*.md` — 世界観、哲学、思想メモ(85 本のうち多数)

85 本もあるのは、user 型を「人となり」から「思考の蓄積」まで広く取っているため。思想記事の断片が全部ここに溜まっている。

#### feedback (57 本)

一番効くのがこの type。「こうしないで」「こうして」を蓄積する場所。

例:
- `feedback_dont_prescribe_rest.md` — フロー中に休憩を強要しないでほしい
- `feedback_perspective_gap.md` — 視座のズレを認識して対話する

feedback は**同じミスを 2 回しないための抗体**のようなもの。書いた瞬間は小さい修正だが、積み上がると「この AI は私のことを本当に理解している」という体感になる。

#### reference (28 本)

外部資源への目印。

例:
- `reference_env_var_memo.md` — 未文書化の環境変数メモ
- `reference_scheduled_post_workaround.md` — スキル運用の Workaround

「あの URL どこだっけ」を解消する。28 本しかないのは、多くは MEMORY.md の index に直接書く方が速いため。

### MEMORY.md ── index としての役割

259 本のファイルを全部読み直すわけではない。`MEMORY.md` がすべての入口になる。

現状:

```
$ wc -l MEMORY.md
269 MEMORY.md
```

269 行。ルール上の上限は 200 行だが、気づけばオーバーしている。

中身は**状況別の参照先**を一行ずつ並べた index。例:

```markdown
### 組織への提案・稟議を準備するとき
- [[competitive-advantage-analysis]], [[ai-adoption-maturity-model]]

### 発信・メディア活動を考えるとき
- [[content-pipeline]] — 発信パイプライン
- [[distribution-experiment]] — レーン選定実験フレーム
```

AI は最初に MEMORY.md を読んで「どこに情報があるか」を把握し、必要になったときだけ個別ファイルを Grep or Read で開く。**index と本体の分離**がコスト管理の鍵。

### 自動 vs 手動

記憶は 2 つの経路で書かれる:

1. **自動**: Claude が会話の中で「覚えておいて」と指示されたとき、あるいは明らかに将来価値のある情報を検出したときに自動記録
2. **手動**: ユーザーが明示的に保存フローで記録、あるいは会話の終盤にまとめて記録

実際には**自動が 7-8 割**。ユーザーが意識して「これ覚えて」と言うよりも、Claude が判断して "saving to memory..." と宣言するパターンが圧倒的に多い。

## Layer 2 深堀り: 33,999 observations

File-based が「意図的な記憶」なら、Observation Database は「副作用としての記憶」だ。

使っているプラグインは [claude-mem](https://github.com/thedotmack/claude-mem) (作者: thedotmack)。インストールすると、Claude Code のツール呼び出しや会話が自動的に SQLite DB に蓄積される。

### Observation の 6 type

observation table の schema は以下のような構造:

```sql
CREATE TABLE observations (
  id INTEGER PRIMARY KEY,
  memory_session_id TEXT,
  project TEXT,
  text TEXT,
  type TEXT CHECK(type IN (
    'decision', 'bugfix', 'feature',
    'refactor', 'discovery', 'change'
  )),
  title TEXT,
  subtitle TEXT,
  facts TEXT,
  narrative TEXT,
  concepts TEXT,
  files_read TEXT,
  files_modified TEXT,
  prompt_number INTEGER,
  created_at TEXT,
  discovery_tokens INTEGER
);
```

6 つの type それぞれの意味と実績:

| type | 意味 | 件数 |
|---|---|---:|
| **discovery** | 調査で何かを発見した | 19,381 |
| **change** | 既存のものを変更した | 6,297 |
| **decision** | 判断を下した | 4,245 |
| **feature** | 新しいものを作った | 2,816 |
| **bugfix** | バグを修正した | 746 |
| **refactor** | リファクタした | 514 |

discovery が 57% を占めていることに注目してほしい。

これは何を意味するか。**Claude Code の時間の半分は「知らないことを知るために何かを読んでいる」**ということ。Code を書いている時間より、Code と周辺を読んでいる時間の方がずっと多い。

decision (12%) と feature (8%) が少ないのは健全。「決める」「作る」は調べた後の最後の 1% でしか起きない。

### SessionStart で呼び戻される index

claude-mem の本領は、**新しいセッションを開いた瞬間**に発揮される。

セッション開始時、こういう context が自動で注入される:

```
# [project] recent context

**Legend:** 🎯 session-request | 🔴 bugfix | 🟣 feature |
            🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision

📊 Context Economics:
- Loading: 50 observations (18,857 tokens to read)
- Work investment: 306,104 tokens spent on research, building, decisions
- Your savings: 287,247 tokens (94% reduction from reuse)
```

この index が毎セッション先頭に貼られる。AI は「昨日何をしていたか」を**ゼロから聞き直す必要がない**。

### Token 経済学

上の context に書かれている数字が実に面白い。

- **Loading**: 50 observations を context に展開するコスト = 18,857 tokens
- **Work investment**: それらを生み出した累積作業量 = 306,104 tokens
- **Savings**: 287,247 tokens (94% 削減)

つまり、**前回の作業の 16 分の 1 のコスト**で、その作業内容を呼び戻せている。

これが Layer 2 の真価だ。File-based Memory は「人間が見に行く」型の記憶だが、Observation DB は「AI が context に持ち込む」型の記憶。**AI 自身の再現性に効く**のはこちら。

### semantic index という設計判断

なぜ全部の observation を context に展開しないか?

33,999 x 平均 400 tokens = 13.6 M tokens。Opus 4.6 の 1M コンテキストでも入らない。

そこで claude-mem は**semantic index** 戦略を取る:

1. 各 observation の title, type, subject を index にだけ載せる(100 tokens 程度)
2. AI が必要になったら mem-search tool で `search()` or `get_observations()` を叩く
3. その時だけ該当 observation の full content をロード

結果、**18,857 tokens で 50 件の index を読み、そのうち必要な 2-3 件だけ詳細を取る**という経済性が成立する。

これは RAG + Index の 2 段構えと考えれば理解しやすい。

## 3ヶ月半の軌跡

### 2025-12-20: 始まり

installed claude-mem. 「なんか面白そうな plugin があるな」程度の軽さで入れた。

初日から月末まで、**9,244 observations** が蓄積された。1 日あたり 770 件のペースだ。これは導入期に Claude Code を集中的に使っていたのもあるが、それ以上に**「記録漏れ」をさせない初期設定**の効果が大きかったと思う。

### 2026-01: 本格運用の 1 ヶ月目

8,784 obs / 283 per day。

1 月中盤に気づいたのは、「あれ、前に似たようなことを調べたはず」という瞬間が**激減した**こと。セッションを跨いで文脈が繋がる感覚は、それまで Context Engineering を 4 ヶ月実践してきた身でもはっきり違いが出た。

### 2026-02: 棚卸し期

9,769 obs / 349 per day。

File-based Memory の整理が進んだ月。Observation DB が自動で流れていく一方、**意図的に残したいもの**を手動で typed memory に転記する作業が増えた。ここで 4 type の使い分けが固まる。

- プロジェクト進行の状況 → project
- 思想・哲学の破片 → user (thought_*)
- 「こうしないで」 → feedback
- 外部資源のポインタ → reference

### 2026-03: 安定期

4,863 obs / 157 per day。

ペースが前月の半分まで落ちた。これは使用量が減ったのではなく、**ノイズが減った**ため。claude-mem の auto-dedup が効き始めたのと、繰り返し調査する必要のあるトピックが減ったのが両方効いた。

3 月末には **2,538 Markdown ファイル**と **27,000 observations** で一旦落ち着く感覚があった。

### 2026-04: 融解期

1,339 obs / 12 日 = 112 per day。

ここで奇妙な現象が起きた。**File-based Memory のどこに何があるかを、身体が覚え始めた**。

MEMORY.md を見なくても「あのファイルは 4/7 に書いたやつ」と思い出す。ファイル名の命名規則が頭の中にあって、grep するよりも直接ファイル名を打つ方が速い。

これは人間側の memory ではなく、**システム側の構造が自分の手に馴染んだ**感覚。道具を使い込んだ職人の「どこに何があるか」に近い。

## ハマったところ (3つ)

### ハマり 1: MEMORY.md が 200 行制約を超える

ルール上の上限は 200 行。現在は **269 行**で、システムから warning が出ている:

```
> WARNING: MEMORY.md is 269 lines (limit: 200).
  Only part of it was loaded.
```

原因は、**新しい状況が出てくるたびに index エントリを追加してしまう**こと。削るより増やす方が速いので、気づけば肥大化する。

教訓: **index は negative pressure で管理する** (何を削れるか常に考える)。MEMORY.md は増え続ける台帳ではなく、**今の関心に直結する入口**であるべき。

### ハマり 2: raw-sources が 849MB まで肥大化

memory/ 配下の容量内訳:

```
memory/ 合計: 881 MB
├ raw-sources/    849 MB (96%)  ← 大部分
├ obsidian-exports/ 23 MB
├ その他 imports/ 5 MB
└ (core memories) 30 MB 程度
```

実は**核となる 259 ファイルはわずか 30MB 程度**しかない。残り 849MB は過去の slack/notion/obsidian からの import で、現在の AI はほぼ参照していない。

教訓: **アーカイブと active memory を分ける**。今の自分が使わないものは別ディレクトリに外出しすべき。全部を memory/ 配下に置くと、diet が困難になる。

### ハマり 3: type 分類のドリフト

feedback なのか user (thought) なのか、判断に迷う記録が増えた。たとえば:

> 「ある視座で物事を語ると噛み合わない相手がいる」

これは feedback (対話の注意点) なのか、user (自分の世界観) なのか。最初は feedback に寄せていたが、途中から thought_* にまとめ直した。

教訓: **分類はツリー構造ではなく tag 的に緩くする**。厳密な排他分類を目指すと、境界ケースで手が止まる。判断に迷ったら雑に一方に入れて、後で気になったときに移動する。

## 見えてきた原則 (3 つ)

### 原則 1: index は concise、本体は detailed

MEMORY.md は 269 行で上限超え。でも個別ファイルは平気で 200 行を超える。

**index は読み捨て、本体は精読**。index に詳細を書き込まない。逆に本体は遠慮なく長くする。これは Notion や Confluence の page structure と逆で、**ファイルシステムの階層に頼らない**設計。

### 原則 2: 自動と手動のハイブリッド

File-based (手動) と Observation DB (自動) は**どちらかに寄せる**のではなく、**並走させる**のが正解。

- 手動のみ → 書き落としが多発、心理的負担
- 自動のみ → ノイズ過多、意図的な決定が埋もれる
- ハイブリッド → 自動が "セーフティネット"、手動が "意図の結晶"

Claude Code Memory の設計思想は、**判断と観察を別の層に置く**こと。判断は手動で確定させ、観察は自動で流す。

### 原則 3: 蓄積は moat、index は負債

33,999 observations は資産だ。これを競合が 1 日で再現することはできない。

しかし、MEMORY.md の肥大化は負債だ。読み込むたびに token を消費し、古い情報が判断を引きずる。

**蓄積は足し続けていい、index は定期的に削らなければいけない**。この非対称性を意識しないと、memory system は重くなるだけで役に立たなくなる。

## 次の章 ── Memory から flywheel へ

ここまで書いてきた Memory System は、現時点の到達点でしかない。

次に見えているのは:

1. **Cross-project Memory** — 59 projects の横断検索(現状、各 project 内で閉じている)
2. **Memory の選択的公開** — 個人記憶の一部をコンテンツとして配信する可能性
3. **記憶の手放し方の設計** — 何を忘れるかの判断基準

そしてもう一つ、本質的な問い:

> Memory を育て続けることは moat だが、
> それを「整理すること」自体が次の仕事になっていく。
> AI は記憶を生成するが、
> 記憶を捨てる判断は今のところ人間にしかできない。

Claude Code Memory は「記憶の蓄積」を解決した。次の課題は「記憶の手放し方」だ。

## まとめ

- File-based Memory: 2,538 Markdown files, 259 typed memories, 881 MB
- Observation DB: 33,999 observations, 29,668 prompts, 2.0 GB
- 運用期間: 3.7 ヶ月 (2025-12-20 〜 2026-04-12)
- Skill(振る舞い) + Memory(経験) = 継続する同僚

Skill だけでも、Memory だけでも、Claude Code は「便利な道具」で止まる。両方が揃ったとき、はじめて**自分の外側にもう一人の自分**がいるような感覚になる。

100 個の Skill を育てる話の次は、33,999 の observation を育てる話だった。次は何を育てることになるのか、まだ分からない。

---

**関連**
- 前作: [Claude Codeで100個のSkillを育てた全記録](https://zenn.dev/takuyanagai0213/articles/claude-code-100-skills-full-record)
- プラグイン: [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)
- 本記事執筆時の環境: Claude Opus 4.6 (1M context), claude-mem, 114 日間の運用データ
