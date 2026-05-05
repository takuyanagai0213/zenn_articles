---
title: "Vercel + Neon + Next.js + Drizzle + Better Auth で B2B SaaS を1ヶ月で立てた技術選定 — 28 ADR から見える Agent-Driven 開発の axis"
emoji: "🧭"
type: "tech"
topics: ["claudecode", "vercel", "neon", "nextjs", "agentnative"]
published: true
---

## はじめに

2026 年 4 月 22 日から 5 月 1 日までの 10 日間で、僕は B2B SaaS をひとつ立ち上げた。記事チェック業務を AI で増幅する社内向けの B2B プロダクトで、production ドメインも自社で立てて運用している。アフィリエイト広告代理店の社内利用が起点で、コンサルがクライアントの規約に従って広告記事を審査する業務を、AI に下読みさせて人間は判断だけに集中する形に変える試みだ。

この 10 日間で書いた Architecture Decision Record(ADR)は 28 本。技術選定や構造判断、却下した選択肢、再検討トリガーまで含めて文書化したものだ。Repo 構造から認証、DB、Email、Deploy、MCP、PR review 自動化、secret 管理、Philosophy の cell 化まで、layer は 8 つ近くに散らばっている。

でも、28 本を並べて俯瞰してみると、ひとつの軸だけは最初から最後まで通っていた。

**`CLI or MCP, not UI.`** — エージェンティック運用では、すべての操作は CLI か MCP で完結する。UI は異常時の避難口に限定する。この一行が、Repo 構造、認証選定、DB branching、PR review、secret 管理、すべての判断に通底していた。

この記事は、ひとつの SaaS を 28 個の独立した技術選定で組み上げた記録を、その 1 軸で串刺しに読み直す試みだ。Layer ごとの deep dive は別記事に分けたので、本記事は俯瞰の総覧として読んでほしい。

---

## 28 ADR の俯瞰 — 10 日間のタイムライン

ADR の採択日を時系列で並べると、こんな分布になる。

| 日付 | ADR # | テーマ |
|------|-------|------|
| 4/21 | 001 | apps/ で実装境界、docs flat |
| 4/22 | 002-014 | Claude Code 専用、Drizzle、Better Auth、Email なし、Neon MCP、PR review 自前禁止、MCP no-browser auth、1Password SA、docs cell 化、secret 管理、E2E 戦略、認証 UX、auto deploy 保留 |
| 4/22 深夜 | 015 | Magic Link + Password 両対応(Resend ブロッカー迂回) |
| 4/23 | 016, 017 | Schema reset、Organization plugin 削除 |
| 4/26 | 019 | dip ナース案件のデータパイプライン戦略 |
| 4/27 | 020 | レギュレーション CSV upload(ADR-018 構想を方向転換) |
| 4/28 | 021 | Philosophy cell 化 |
| 4/29 | 022, 023 | Vercel auto deploy 復活、Neon org 移行 |
| 4/30 | 024-027 | Migration 整備、preview UAT、その他 |
| 5/1 | 028 | Magic Link 廃止 |

最初の 1 日(4/22)に 13 本も ADR が出ているのが目を引く。ここで stack の骨格 — Drizzle / Better Auth / Neon / Resend / Email ライブラリなし / PR review 自前禁止 / MCP は PAT 認証 — が一気に決まった。残りの 8 日は、本番運用を回すための調整(認証 UX、Schema、auto deploy、preview UAT)とドメイン側の判断(レギュレーション取得方法、データパイプライン戦略)が続く。

stack 全体を 8 layer にマッピングするとこうなる。

| Layer | 採択 | 関連 ADR |
|---|---|---|
| Repo / Doc 構造 | apps/ で実装境界、docs/ flat、Philosophy cell 化 | 001, 002, 010, 021 |
| 認証 | Better Auth(Magic Link → 削除、Password 一本化へ) | 004, 013, 015, 028 |
| DB / ORM | Vercel Postgres(Neon)+ Drizzle ORM + Neon MCP | 003, 006 |
| Email | Resend + 素の HTML template literal(ライブラリなし) | 005 |
| Deploy | Vercel auto deploy(自社の Vercel team) | 014(Superseded), 022 |
| Agent / MCP | PAT / API key を標準、ブラウザ認証回避 | 008, 009(Superseded), 011 |
| 何を作らないか | PR review 自動化を自前で作らない | 007 |
| Schema / Domain | annotations / issueComments / clientNote 3 層分離 | 016, 017, 019, 020 |

10 日間で 28 ADR を出した感覚を素直に書くと、「設計判断の高速連鎖」だった。ひとつの判断が次の判断の前提を作って、3-4 段階で構造が立ち上がっていく。例えば「Better Auth を採用」(ADR-004)→「Magic Link 採用」(ADR-013)→「Resend 外部ブロッカー → Magic Link + Password 両対応」(ADR-015)→「9 日後に Magic Link 削除、Password 一本化」(ADR-028)という連鎖は、ひとつの認証 layer のなかで起きた 4 段階の判断だ。最初から正解を狙うのではなく、判断と検証を高速で回すから、結果的に 28 ADR まで膨らんだ。

このテンポは、僕一人と Claude Code(エージェント)で回したから成立している。判断密度を圧縮するときに、人間 1 人 + エージェントの 2 体の組合せが、組織の合議よりも遥かに速い。1 年運用してきたコンテキスト基盤(100+ Skills / 34,000+ memory entries / 420 files)が、判断の前提を毎回作り直さなくて済む状態を支えていた。

---

## 主軸 — `CLI or MCP, not UI.`

28 ADR を 1 軸に圧縮するなら、自社プロジェクトの Philosophy にある一行に行き着く。

> エージェンティック運用では、全ての操作は CLI か MCP で完結する。UI(ブラウザ認証、手動ダッシュボード操作)は **TPS アンドン発火(異常時のみの人間介入)** に限定し、デフォルトにしない。

この一行は、Toyota Production System の「自働化」(人偏の働)を Claude Code 運用に適用した発想だ。通常時は機械が自律で動き、異常を検知したときだけ人間が手を入れる。UI 操作はその「異常時の介入」に相当する。

なぜこれが主軸になるかというと、agent が走り続けられるかどうかが、UI 必須かどうかで決まるからだ。OAuth のブラウザ認証は token 期限切れのたびにリダイレクトを強制する。これは「異常時の介入」ではなく「定常的な介入」であり、agent の自律性を構造的に壊す。同じく、Vercel dashboard で env を手動で書き換える運用、Neon Console で手動で branch を作る運用、GitHub UI で PR を目視で merge する運用 — どれも UI 起点の「定常的介入」になる。

この軸を defaut に置くと、stack 選定の判断が変わる。

- 認証は OAuth より PAT / API key
- DB 操作は dashboard より MCP
- Deploy は手動より git push trigger
- Secret 管理は UI より CLI(`vercel env add`)
- PR review は GitHub UI より MCP 経由のセッション内 review
- Email UI は別 SaaS のダッシュボードより素の template literal

これらは全部、上の主軸の direct な帰結だ。28 ADR を 1 軸で串刺しにすると、`CLI or MCP, not UI.` がほぼ全部の判断の根拠として何度も再登場する。`Leave flowers for tomorrow.`(早すぎる最適化を避ける)や `Translate, don't bypass.`(翻訳を迂回しない)も補助軸として効くが、主軸はこの 1 軸だ。

ただし、life-time 1 回の妥協は受け入れる。GitHub App 登録、Neon Console での初回 API key 発行、Vercel Dashboard での初回 Team Token — この 3 つは構造的に UI 不可避だが、年次の token 更新と違って **生涯 1 回の発火**で済む。主軸の例外として明示的に許容している(ADR-008 / ADR-011)。

---

## Layer 1: Repo / Doc 構造

最初の判断は、コードと文書をどう分けるかだった。

**ADR-001 — apps/ で実装境界、docs は flat**。`apps/<product>/` に Next.js を、`apps/<forecast-app>/` に Streamlit PoC を入れた。並立する 2 つのアプリを対等に隔離し、`packages/shared/` のような共通基盤は今は作らない。理由は YAGNI で、共通化が必要な事例が 2-3 回観測されてから掘れば十分だ。

**ADR-002 — AGENTS.md を採用しない**。自社プロジェクトは Claude Code 専用と位置づけた。Cursor / Codex / Copilot を併用するメンバーが現状いないので、マルチツール対応の AGENTS.md は過剰だ。CLAUDE.md / `.claude/rules/` / `.claude/skills/` の 3 層を使い切るほうが濃い。

**ADR-010 — docs を docs/ 配下に集約**。最初は root 直下に 25 本の Markdown を flat に置いていたが、root に `apps/` `meetings/` `.claude/` と並ぶと視覚的に散乱する痛みが出てきたので、1 段下げて `docs/` 配下に集約した。docs 内は flat を維持して、ドメイン別にも熟成段階別にも切らない。`integration-roadmap.md` のようなドメイン跨ぎ文書が自然に書ける状態を守る判断だ。

**ADR-021 — Philosophy を cell に切り出し**。Philosophy が CLAUDE.md 内で 18 原則 + 15 metaphor 項目まで膨張して、Claude の応答スタイルを汚染しはじめた。自分の中で「何いっているかよくわからんな。CLAUDE.md の思想の強さが悪さしている」と違和感が出て、`docs/philosophy/` cell に切り出して CLAUDE.md には主要 5 原則だけ残した。dense 表記が context に default で居続けないようにする構造的な解だ。

この 4 つの判断はすべて、「構造を先回りで足さない」「痛みが具体化してから cell を切る」という同じ原則の適用だ。`Leave flowers for tomorrow.` を Repo 構造の layer に降ろすとこうなる、という標本でもある。

最初は構造化を最小限にして、痛みが見えてから 1 段ずつ深めていく。逆に最初から `apps/web/` `apps/api/` `packages/shared/` `packages/ui/` のような構造を組むと、まだ動いていない設計仮説に投資することになる。Claude Code が読み書きする repo では、SSOT(Single Source of Truth)が 1 つに収束していない構造は、agent の判断を毎回ぐらつかせる。

---

## Layer 2: 認証 — Better Auth(要約 + 詳細別記事)

認証は 10 日間で 4 段階の判断連鎖になった。

採用は **Better Auth v1.6.5**(ADR-004)。Auth.js の公式後継として 2025-09 にバトンが渡された OSS で、Next.js 16 対応 + Magic Link + organization plugin が揃っている。Clerk のような SaaS 認証は、PII を米国 SaaS に越境させる説明コストが金融案件で重く、却下した。

ADR-013 で「Magic Link メイン + `/signin` `/signup` URL 分離」を採択し、ADR-015 で Resend の外部ブロッカー(domain verify が間に合わない)を迂回するために「Magic Link + Password 両対応(default は password)」に切替えた。そして 9 日後の ADR-028 で、本番運用が始まって「Magic Link は実質使われていない」事実が見えたので、Magic Link plugin を完全削除して Password 一本化に倒した。

この 4 段階(004 → 013 → 015 → 028)は、ひとつの layer のなかで「採用 → UX 確定 → 外部ブロッカーで方針修正 → 運用観察で方針再修正」が 9 日で起きた典型例だ。一度入れた機能を 9 日後に消す判断は、`pre-production-merge-autonomy.md` rule(本番運用前は agent が自律で merge していい)と、`Leave flowers for tomorrow.` 哲学(必要が出てから掘る、不要なら早く戻す)の両方が効いている。

認証 layer の deep dive は私の別記事「Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで」を参照してほしい。Magic Link 削除の orphan user 復旧手順、ephemeral preview branch との snapshot 同期境界、production main + open PR の preview branch への個別 INSERT が必要な構造的理由まで、認証 layer に閉じた 6 ADR の時系列を時間順に追っている。

ここでは「Better Auth は CLI / MCP で完結する認証 stack で、SaaS UI 介入を要求しないから自社プロジェクトの主軸に整合する」という 1 行で要約しておく。Clerk の dashboard を agent が自動操作することは(2026-04 時点では)できないが、Better Auth は session table を Drizzle で扱えるので、agent が SQL レベルで操作できる。これが life-time 1 回の妥協(initial setup 以外)で済む構造を支えている。

---

## Layer 3: DB / ORM — Drizzle + Neon + Neon MCP(要約 + 詳細別記事)

DB layer の採択は **Vercel Postgres(裏は Neon)+ Drizzle ORM + Neon MCP Server** の 3 点セット(ADR-003 / 006)。

Drizzle を選んだ理由は、schema を TypeScript 1 ファイルで定義できる(`prisma generate` のような中間ステップが要らない)から、Claude Code が schema を直接読み書きできる。`@neondatabase/serverless` の HTTP driver で Vercel Edge Functions から直接接続できて、Edge ランタイム対応も成立する。Prisma 7(2025-11 に Rust 撤廃 + WASM 化)との差は紙一重だが、`prisma generate` ステップと PSL 独自 DSL がエージェンティック運用で微不利と判断した。

Neon を選んだ最大の理由は **branching が copy-on-write で数秒**だからだ。PR ごとに DB branch を切って独立した環境で作業し、merge 後に branch を drop する運用が成立する。Vercel Native Integration を入れると、PR push のたびに preview deploy + ephemeral branch + migration 自動適用がワンセットで走る。これは agent が「DB を破壊してもいい sandbox を持っている」状態で、リコール思想 (`git revert` で戻せる粒度で進む) を DB layer にまで降ろした実装になる。

Neon MCP Server を Claude Code に接続すると、自然言語で `mcp__neon__run_sql` を呼んで SQL を実行できる。`mcp__neon__create_branch` で branch を切れる。これが「dashboard を開かずに DB を操作する」主軸の direct な実装だ。

DB layer の deep dive は私の別記事「Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー」を参照してほしい。Neon-Vercel Native Integration の install path、preview ephemeral branch の `parent_timestamp` 同期境界(production main の admin manual fix が既存 PR の preview branch に伝搬しない構造)、`drizzle-kit push` と `drizzle-kit migrate` の使い分け、CI E2E で migration SQL を `sql.query()` で直接流す pattern まで、3 ADR + 4 rules の運用論を扱っている。

ここでは 1 行で要約すると、「Neon は agent が破壊と再生を高速で回せる DB 基盤で、自社プロジェクトの主軸をそのまま DB layer に降ろした実装」だ。

---

## Layer 4: Email — ライブラリを足さない判断

Email UI ライブラリは追加しない(ADR-005)。React Email、JSX Email、MJML、Maizzle といった選択肢があるなかで、素の HTML template literal に倒した。

```typescript
await resend.emails.send({
  html: `<html>...<a href="${url}">ログイン</a>...</html>`,
});
```

理由は単純で、Magic Link + 既存通知 5-6 種規模では template literal で十分だからだ。React Email を入れると、JSX のビルド step、`@react-email/render` の依存追加、メールプレビュー環境の整備、コンポーネント化の判断 — 30 分相当の overhead が増える。それで得られる ROI は、現在の規模ではマイナスだ。

この判断は「ペインが具体化してから掘る」原則の標本でもある。ブランドカラー統一が必要になったら、メール A/B テストが必要になったら、Outlook 古い版対応で詰まったら — そのとき React Email に乗り換える。30 分の作業で済む。先に入れておくと、本番運用前に消費した 30 分が、運用観察フェーズの判断容量を奪っている。

`Leave flowers for tomorrow.` を Email layer に降ろすと、こうなる。

---

## Layer 5: Deploy — ADR-014(保留) → ADR-022(復活)の case study

Deploy layer は、Repo 構造とは違う方向の learning だった。

**ADR-014(2026-04-22)— Vercel auto deploy は Pro まで保留**。Vercel Hobby プランが org 所有の private repo への connection を許可していなかった(`409: not supported on the Hobby plan`)ので、auto deploy を諦めて手動 `vercel --prod` で暫定運用すると決めた。Pro $240/年 vs 手動 30 秒 × 100 回/年 = 50 分、ROI が見合わないので保留にした判断だ。

**ADR-022(2026-04-29)— Vercel auto deploy 採用**。1 週間後、自社の production ドメイン取得 + Vercel project を自社の Vercel team(既存有料 plan)に作成したタイミングで前提が崩れた。team plan は org 所有 private repo への GitHub install が許可されていたので、auto deploy が自動的に有効化された。ADR-014 を supersede して、`main push → production auto deploy` を正式採用した。

この 1 週間の間に何が起きたかというと、「Hobby account への直 install」を諦めて、「会社の team account 経由で project を作る」path に切替えた。会社の既存 Vercel team plan を使うほうが、自社プロジェクト単独で Pro $240/年を払うより筋がよい(会社の team は既に他プロダクトで Vercel 課金している)。前提条件が変わると過去の判断が再評価される良い例だ。

ADR-022 の効果は、`pre-production-merge-autonomy.md` rule(本番運用前は agent が自律で merge していい)と組合せて発揮される。Claude Code が PR を作って、CI 4 job が green になって、agent が自律で squash merge して、Vercel が自動で production に deploy する。僕が見るのは merge 完了通知だけ、という運用が成立した。

ADR-011(secret 管理は Vercel env + `.env.local` で暫定)もこの layer に effective に効く。`vercel env add KEY value --scope production` で secret を投入すると、auto deploy が次の build で env を読み込んで反映する。`vercel.json` を書く必要も、別の secret manager を入れる必要もない。

ただし、env 値の hot fix(末尾改行混入、旧 keyword 残存、placeholder 未置換)が production で発覚したときは、git push を伴わない `PATCH /v10/projects/{id}/env/{env_id}` + `forceNew=1` で redeploy するパターンが必要になる。この運用 hot fix workflow は私の別記事「Vercel env を git push なしで production に反映する」を参照してほしい。

---

## Layer 6: Agent / MCP — PAT を標準にする

MCP layer の 4 ADR(002 / 008 / 009 / 011)は、主軸の direct 実装だ。

**ADR-008 — MCP はブラウザ認証を避け、PAT / API key を標準に**。OAuth remote MCP は token 期限切れ時にブラウザ遷移を強制するので、エージェンティック自律性の根本矛盾になる。代わりに `.mcp.json` の `headers.Authorization` に `Bearer ${GITHUB_PAT}` のような形で PAT を渡す path を採った。GitHub Fine-grained PAT(年次更新)、Neon Project-scoped API key、Vercel は MCP 採用せず CLI 経由(`vercel` コマンド)で代替する。

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_PAT}" }
    },
    "neon": {
      "type": "http",
      "url": "https://mcp.neon.tech/mcp",
      "headers": { "Authorization": "Bearer ${NEON_API_KEY}" }
    }
  }
}
```

`.mcp.json` は commit 対象、PAT 値は `.claude/settings.local.json` の `env` フィールドに入れて gitignore する。secret は repo に出ないし、CI / cron / 非対話環境でも動く。年次の PAT 更新は計画的に発火点を予測できる(Google Calendar に登録しておけば 1 週間前にリマインドが来る)ので、主軸のいう「異常時のみの介入」に整合する。

**ADR-009 — 1Password Service Account を root-of-trust に**。当初はこれを採用しようとしていたが、棚卸ししたら secret が 8-13 個しかなくて、1Password Business $96/年のコストが ROI に合わないので、**ADR-011 で Supersede**された。

**ADR-011 — secret は Vercel env + `.env.local` で暫定**。プロダクト secret は `vercel env` CLI で Vercel 側に投入、開発基盤 secret(`GITHUB_PAT` / `NEON_API_KEY` / `VERCEL_TOKEN`)は `~/.zshrc` export か `.env.local` に置く。1Password SA 等への昇格はメンバー 2 人以上 / secret 30 個以上 / 月次 rotation 発生 / 漏洩 incident、いずれかが具体化したらやる。

この 4 ADR は「ブラウザ認証ゼロ + agent が走り続ける構造を、PAT と CLI で組む」という同一テーマのバリエーションだ。stack に SaaS の dashboard 操作を必要とするものを入れない、という消極的な意思決定が、結果として agent の自律性を最大化する。

---

## Layer 7: 何を作らない判断

ADR-007 と ADR-005 は、「公式が本気で出すものを自前で作らない」という同じ判断軸だ。

**ADR-007 — PR review 自動化は自前で作らない**。`anthropics/claude-code-action` v1.0、Managed Code Review、Claude Code Routines、`@claude` メンション + GitHub App — 候補は複数あったが、どれも採用しなかった。代わりに **GitHub MCP Server 経由のセッション内 review** で運用する。Claude Code がメインセッション内から `mcp__github__pull_request_read` で diff を取って、`pull_request_review_write` でコメントして、`merge_pull_request` で merge する。GitHub UI を開かない運用が成立している。

理由は陳腐化リスクだ。`claude-code-action` は 2025-2026 年の間に beta → v1.0 で breaking change(`mode/direct_prompt` 廃止 → `prompt + claude_args` 統合)が起きた。今 self-managed で workflow を持つと、1 年後に追従コストが残る。Anthropic / Claude Code 側が「PR review の公式構成」を出し切るまでは、自前で作らない方が長期的にコスト低い。

**ADR-005 — Email ライブラリなし**は同じ判断軸の Email 版だ。React Email を自前で organize するより、メール 10 種を超えてから入れる。

これらは「本気を出してくる provider の領域に自分で投資しない」という消極的な意思決定で、自社プロジェクトでは `~/.claude/rules/tool-strategy.md` の「汎用ツール個別最適化の罠を避ける」とリンクしている。注力すべきは N=1 の領域(コンサル業務 moat、ドメイン知識、業務翻訳の value add)で、PR review workflow を磨くことではない。

---

## 28 ADR を貫く 3 哲学

28 個の独立した判断を俯瞰すると、3 つの哲学が繰り返し効いていた。

### 1. `CLI or MCP, not UI.`(主軸)

Repo 構造、認証選定、DB branching、PR review、Deploy、Secret 管理、Email — どれを取っても、UI 介入を default に置かず、CLI / MCP 完結を default にする判断が通っていた。

life-time 1 回の妥協(GitHub App 登録、Neon 初回 API key、Vercel 初回 Team Token、Claude Code 初回認証)は受け入れる。しかし定常運用で UI が必要な構成は採らない。Clerk dashboard、Vercel UI からの env 編集、GitHub UI で PR を目視で merge する — どれも「定常的人間介入」になるので避ける。

### 2. `Leave flowers for tomorrow.`(早すぎる最適化を避ける)

ADR-005(Email ライブラリなし)、ADR-009 → ADR-011(1Password SA を先送り)、ADR-014 → ADR-022(auto deploy を 1 週間保留してから採用)、ADR-001 → ADR-010 → ADR-021(構造を 1 段ずつ深める)— どれも「痛みが具体化してから掘る」適用だ。

これが効くのは、stack に対して agent の判断容量が limited だから。先回りで構造を組むと、まだ起きていないペインに対して context を消費し、本当に解くべき問題に対する判断容量を奪う。自社プロジェクトの 28 ADR は、ほぼすべて「現時点のペイン具体化度」を判断軸の 1 つに含んでいる。

### 3. `Translate, don't bypass.`(翻訳を迂回しない)

ADR-019 / ADR-020 / ADR-024 はドメイン側の判断で、Layer 1-7 とは別軸だ。コンサル業者がクライアント document を記事レギュレーションに翻訳する業務を、AI で「代替」せず「増幅」する設計に倒した。

中継地(Sheets API、ASP 管理画面、ハニカム)を fix する誘惑は強いが、**真の発生源**(コンサル翻訳作業 + クライアント document)を見失うと、表面 fix が次の表面 fix を呼ぶ無限ループに入る。これを `~/.claude/rules/origin-trace-before-surface-fix.md` rule で構造化して、ADR の判断 process に組み込んだ。

この 3 哲学は、AI 時代の B2B SaaS 設計で「人間 1 人 + agent」が組織より速く動く条件として、互いに補強し合っている。主軸(CLI / MCP)で agent が走り続ける状態を保ち、`Leave flowers` で判断容量を確保し、`Translate, don't bypass` で AI が代替できない人間 moat を増幅する設計に倒す。

---

## 既出 deep dive 3 記事との cross-link

stack の運用論は、以下の 3 記事で個別に深掘りしている。本記事の俯瞰と組合せて読むと、layer ごとの運用感が立ち上がる。

- **Vercel Storage を UI ゼロで setup する** — Vercel Blob を CLI + REST API で `store 作成 → project link → env 自動投入 → forceNew redeploy` の 4 step で setup する path。CLI or MCP, not UI を Storage layer に降ろした実装で、`vercel blob create-store --environment preview` の副作用 cleanup まで扱う。
- **Vercel env を git push なしで production に反映する** — env 値の hot fix workflow。`PATCH /v10/projects/{id}/env/{id}` で値を変更して、`forceNew=1` で同 git sha のまま env だけ最新で rebuild する 4 step。10 日間で 4 回踏んだ実証込み。
- **Neon Personal Token は org に bind される** — Neon の Personal Token が UI の現在 org context に bind される罠と、`/users/me` で 30 秒で見抜く 1 行 verify pattern。Neon org migration セッションで 45 分浪費した経験から rule 化した。

そして本記事と並走で執筆した同期 deep dive 2 記事:

- **Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで** — 認証 layer 6 ADR の時系列。Magic Link plugin の orphan user 復旧、preview branch の snapshot 同期境界、production main + open PR の preview branch への個別 INSERT が必要な構造的理由まで、認証 layer に閉じた deep dive。
- **Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー** — DB layer 3 ADR + 4 rules の運用論。Neon-Vercel Native Integration、`drizzle-kit push` と `migrate` の使い分け、CI E2E で migration SQL を `sql.query()` で流す pattern、Vercel preview deploy で migration auto-apply する path まで、DB layer の deep dive。

本記事は俯瞰、deep dive は layer ごと。stack の全体像を掴んだあと、認証 / DB / Storage / env 運用の各論を deep dive で掘る、という 2 段構えで読める構成にしている。

---

## おわりに

10 日間で B2B SaaS をひとつ立ち上げて、28 ADR を発行して、5/1 に production launch した。判断のテンポは、僕一人と Claude Code(エージェント)で回したから成立している。

成立条件は 1 つに絞られる。**stack 選定の各 layer を `CLI or MCP, not UI.` で串刺しに整合させること**。これが崩れると、agent の自律性が定常的な UI 介入で壊れて、判断密度の圧縮が効かなくなる。Clerk のような SaaS 認証を入れた瞬間、UI 介入が default になる。Vercel dashboard で env を編集する運用に倒した瞬間、agent は走り続けられない。Neon Console で手動で branch を作る運用に倒した瞬間、PR ごとの DB 分離が機能しない。

逆に、主軸をすべての layer で守りきると、agent と人間 1 人の組合せで、組織の合議より速く判断連鎖が回る。10 日で 28 ADR、月で 175 PR、1 日に 13 PR を merge した日もある。1 年で 100+ Skills、34,000+ memory entries、420 files。これは個人の作業速度というより、stack 設計が agent を止めない構造になっているから出る数字だ。

最終 launch 後にもいくつか rule が結晶化した。Magic Link plugin の orphan user 復旧手順、preview ephemeral branch の `parent_timestamp` 同期境界、Vercel team SSO + role の問題、Resend test address を使った preview 専用 key 発行 path — どれも本番運用に入ってから初めて見える境界条件で、立ち上げ前には予見できなかった。rule の結晶化は本番運用に入ってから時間をかけて熟成するもので、これはその標本でもある。

個人 + AI agent で B2B SaaS を立てる時代は、もう来ている。条件は主軸をひとつに絞ること。stack の全 layer をその 1 軸で整合させること。あとは判断と検証を高速で回すだけだ。

10 日で 28 ADR が出る。それが現実の速度になる。

---

## 関連記事(私 / 同 stack の deep dive)

- [Vercel Storage を UI ゼロで setup する — Agent-Driven 開発の Storage 自動化パターン](https://zenn.dev/takuyanagai0213/articles/vercel-storage-api-zero-ui) — Vercel Blob を CLI + REST API で UI ゼロで setup する 4 step
- [Vercel env を git push なしで production に反映する — PATCH + forceNew redeploy workflow](https://zenn.dev/takuyanagai0213/articles/vercel-env-hot-fix-workflow) — env hot fix の 4 step workflow
- [Neon Personal Token は org に bind される — /users/me で 30 秒で見抜く 1 行 verify pattern](https://zenn.dev/takuyanagai0213/articles/neon-personal-token-org-trap) — Personal Token の org bound 罠
- [Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで](https://zenn.dev/takuyanagai0213/articles/better-auth-magic-link-9days-removal-case) — 認証 layer 6 ADR 時系列(本記事と同期執筆)
- [Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー](https://zenn.dev/takuyanagai0213/articles/drizzle-neon-mcp-branching-per-pr) — DB layer 3 ADR + 4 rules で見る Agent-Driven branching(本記事と同期執筆)
