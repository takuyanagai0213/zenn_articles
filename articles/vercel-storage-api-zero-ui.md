---
title: "Vercel Storage を UI ゼロで setup する — Agent-Driven 開発の Storage 自動化パターン"
emoji: "💾"
type: "tech"
topics: ["vercel", "claudecode", "nextjs", "devops", "agentnative"]
published: true
---

## はじめに

Vercel Blob を Next.js プロジェクトに繋ぐ時、僕は最初 Vercel Dashboard を開いて Storage タブから Connect ボタンを押していた。プロジェクト選んで、scope 選んで、Connect クリック、env が自動で投入されていることを確認、Redeploy。3 分くらいの作業だった。

これを 1 ヶ月で 4-5 回やる羽目になって、ある日「これ、CLI と REST API だけでできるはずだ」と気づいた。実際、できる。Blob も Edge Config も全部、`curl` と Vercel CLI の組合せで UI 操作ゼロのまま完結する。Dashboard を開く時間がそのまま消える。

この記事は、2026 年 4 月末に自社の B2B SaaS の launch marathon を完走した時のメモから、Vercel Storage を完全に Agent から触れる形に圧縮した手順を書く。1 日 13 PR を merge する密度で動いている時、3 分の Dashboard 操作を 4 回やったら 12 分が消える。それを Claude Code に一任して、僕はヨギボーで PR description を読んでいた、というのが結論だ。

---

## 背景: なぜ UI 操作ゼロにこだわるのか

僕が回している自社プロジェクトには、`CLI or MCP, not UI.` という方針がある。エージェンティック運用では全ての操作は CLI か MCP で完結する、UI は **TPS のアンドン発火（異常時のみの人間介入）** に限定する、というルールだ。

理由はシンプルで、Claude Code に作業を委譲する時、Dashboard を開いてボタンを押す手順は agent が触れない領域に落ちるから。「Vercel Dashboard で Storage タブを開いて Connect ボタンを押してください」と書いた時点で、その作業は人間に戻ってくる。1 人 + Claude で動かしている状況では、人間に戻ってくる作業の数だけ throughput が落ちる。

別の言い方をすると、僕が Claude Code に出す指示が「次の PR を作って merge まで進めて」で済む状態を保ちたい。その途中に「Dashboard を開いて Connect 押して」が混ざると、僕の脳が context switch する。8 時間で 13 PR を作る密度で動いている時、context switch のコストは無視できない。

Vercel の場合、初回の Team Token 発行と GitHub App の install だけは UI 必須が残るが、それ以降の全 Storage 操作は API で動く。**life-time 1 回の妥協** として受容して、それ以降は UI を一切開かない設計に倒す。

---

## 4 step workflow（Blob store の例）

実際のコマンドはこれだけだ。production scope に Blob を新規 connect する全 step を書き出す。

```bash
# 認証 token を Vercel CLI の auth.json から拾う
VERCEL_TOKEN_SAML=$(jq -r '.token' "$HOME/Library/Application Support/com.vercel.cli/auth.json")
TEAM=team_xxx
PROJECT=prj_xxx
```

### Step 1: Blob store を作る

```bash
curl -sS -X POST -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-project-blob","billingState":"active"}' \
  "https://api.vercel.com/v1/storage/stores/blob?teamId=$TEAM"
# → { "store": { "id": "store_xxx", ... } } が返る
```

`store_xxx` の id を後で使う。`billingState=active` を指定しないと作成は通るが課金が止まる、という地味な罠がここにある。

### Step 2: project に connect する

```bash
curl -sS -X POST -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  -H "Content-Type: application/json" \
  -d "{\"projectId\":\"$PROJECT\",\"envVarPrefix\":\"\"}" \
  "https://api.vercel.com/v1/storage/stores/<store_id>/connections?teamId=$TEAM"
```

ここが一番混乱しやすい。レスポンスが空で返ってくる。「失敗したのか?」と一瞬思うが、成功している。verify したければ store metadata の `projectsMetadata` を取って connect 状態を確認する。

このステップが終わると `BLOB_READ_WRITE_TOKEN` が project の env に自動投入されている。runtime で `process.env.BLOB_READ_WRITE_TOKEN` が読めるようになる。

### Step 3: env を verify する

```bash
curl -sS -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  "https://api.vercel.com/v10/projects/$PROJECT/env?teamId=$TEAM" \
  | jq '.envs[] | select(.key | contains("BLOB"))'
```

この jq filter で `BLOB_READ_WRITE_TOKEN` が target scope に inject されているか目視する。`target` 配列に `production` / `preview` / `development` のどれが入っているかで scope が分かる。

### Step 4: production redeploy（forceNew=1）

ここが見落とされやすい。**env を inject しただけでは production runtime に反映されない**。Vercel は env を deploy 時に build に焼き込む方式なので、新しい env を runtime に届けるには rebuild が必要だ。git push を伴わない pure な「env だけ反映する rebuild」を `forceNew=1` で叩く。

```bash
CURR_DPL=$(curl -sS -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  "https://api.vercel.com/v6/deployments?projectId=$PROJECT&teamId=$TEAM&target=production&limit=1" \
  | jq -r '.deployments[0].uid')

curl -sS -X POST -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  -H "Content-Type: application/json" \
  -d "{\"deploymentId\":\"$CURR_DPL\",\"name\":\"my-project\",\"target\":\"production\"}" \
  "https://api.vercel.com/v13/deployments?teamId=$TEAM&forceNew=1"
```

これで「直前 main HEAD の commit（= production と同じ）を build、ただし env だけ最新値で読む」が成立する。git history を dummy commit で汚さずに env 反映だけ走らせる、と理解しておく。1-2 分で READY になる。

ここまでが production scope 向けの標準 path。Dashboard を開いていない、ボタンも押していない、git push もしていない、それでも production の Blob が動く状態に到達している。

---

## preview scope 限定の setup と Vercel CLI

production scope の既存 token を上書きせず、preview scope だけで Blob store を connect したい時がある。自社プロダクトでは production token は別 store で運用していて、preview UAT 用に別の sandbox-tier blob store を当てたかった。

API direct path（`POST /v1/storage/stores/<id>/connections`）には scope 指定 field が docs 上明確でなくて、僕が試した時は **全 scope に inject されるリスク**を感じた。production の既存 token を上書きされたら復旧が面倒なので、ここは Vercel CLI の `--environment` flag に倒す。

```bash
export VERCEL_TOKEN=$(jq -r '.token' "$HOME/Library/Application Support/com.vercel.cli/auth.json")

cd apps/my-project
npx --yes vercel@latest blob create-store <product>-preview-blob \
  --access public \
  --environment preview \
  --yes
```

これで preview scope のみに `BLOB_READ_WRITE_TOKEN` が inject される。production scope は touch されない。`--environment` flag は公式 docs で明示されているので、API より CLI が安全という珍しいパターン。

### CLI 副作用: `.env.local` が生まれる

ここで地味な落とし穴がある。`vercel blob create-store --environment <env> --yes` を走らせると、Vercel CLI が **cwd に `.env.local` を新規作成する**。中身は development 環境の env 一式だ。

```bash
# Created by Vercel CLI
DATABASE_URL="postgresql://...production..."
DATABASE_URL_UNPOOLED="..."
VERCEL_OIDC_TOKEN="eyJhbGc..."
```

`.gitignore` には自動で `.env*.local` が追加されるので git commit risk はないが、production credential が一時的に local file system に存在する状態が落ち着かない。CLI 実行直後に `rm -f .env.local` で即時 cleanup する規律を運用に入れている。

注意点として、僕の repo では dev env を `apps/<product>/.env.local` で別途管理している。CLI 副作用で生まれるのは **repo root の `.env.local`** で、別物だ。cleanup 対象は root のみ、apps 内の `.env.local` は触らない。最初これを混同して dev env を消しかけて 5 分溶かしたので、書いておく。

---

## Vercel Storage 全体マップ

Vercel が公式に提供している Storage type と、それぞれの API endpoint と自動投入される env 名を一枚にまとめる。

| Storage type | API endpoint | 自動投入 env | 状態 |
|---|---|---|---|
| Blob | `/v1/storage/stores/blob` | `BLOB_READ_WRITE_TOKEN` | active |
| Edge Config | `/v1/storage/stores/edge-config` | `EDGE_CONFIG` | active |
| Postgres | `/v1/storage/stores/postgres` | `POSTGRES_URL` 系 | deprecated（Neon 推奨） |
| KV | `/v1/storage/stores/kv` | `KV_*` 系 | deprecated（Upstash 推奨） |

Postgres と KV は marketplace integration（Neon / Upstash）に置き換わった。今から新規 setup する時は、Storage tab で出てくる選択肢としては Blob と Edge Config が中心になる。Postgres を使いたければ Neon を別途 install する path（これも別記事の主題になる）に倒す。

ここで対比として置いておきたいのは、Resend や Anthropic API 系は Vercel native の Storage じゃないので、本記事の 4 step workflow は適用できない。それぞれ provider 側で API key を発行して Vercel env に手動 register する path になる。Storage は Vercel が公式に「create + connect + env 自動 inject」の API を出している領域なので、特別に綺麗に automation できる、と理解しておくと境界が見える。

---

## Anti-pattern 4 つ

実際にやらかしたパターンを書き残す。

| Anti-pattern | 問題 |
|---|---|
| Vercel Dashboard UI で Storage タブから Connect | UI 操作、agent 自律実行不能、`CLI or MCP, not UI.` 違反。最初の僕がこれだった |
| Vercel CLI 古い version（`28.x`）で env pull | Storage 関連 endpoint が 28.x に存在しない、`npx vercel@latest` で latest を invoke 必須 |
| store 作成だけして project connect 忘れ | env 自動投入されず、production runtime で `process.env.BLOB_READ_WRITE_TOKEN` が undefined。気づくのは deploy 後 |
| `vercel blob create-store --yes` の `.env.local` 副作用無視 | production credential が cwd に書き出され、cleanup 忘れで漏洩 risk。CLI 実行直後に `rm` する規律を入れる |

最後の `.env.local` 副作用については、一度 git status で `.env.local` が追跡対象外になっていることを確認してから、安心して作業を進めるルーチンを作っておくと良い。`.gitignore` で守られているので commit は走らないが、ファイル自体が disk に残るのは気持ちが悪い。

---

## 実証: 2026-04-29 launch 当日

この記事の手順は、2026 年 4 月末に自社の B2B SaaS を launch する直前の 1 日に詰め込んだ作業から圧縮している。記事チェック業務向けの B2B プロダクトで、画像 / Excel / Word の AI チェック経路を全部 Vercel Blob 経由で扱う設計になっていた。

その 1 日に何をしたかと言うと、ドメイン取得（お名前.com）→ Vercel project setup → Neon project 接続 → Resend domain verify → Anthropic API key register → Vercel Blob 投入 → 13 個の PR を順次 merge、を 1 人で回した。Claude Code が PR を作って CI が通って自動 merge する pipeline を裏で動かしながら、僕は要所だけ判断していた。100+ Skills と 34,000+ memory entries の context 基盤がこの密度を支えていた。

その流れの中で Blob 投入は 4 step workflow で 5 分かからずに完了した。同じ日に Resend の domain verify は marketplace 経由が必須で UI を開いた、Neon の project transfer は org 跨ぎで UI fallback が必要だった、対比で **Storage は完全 API 経由で UI ゼロだった** のが印象に残っている。Storage は Vercel が一番きれいに API 化している領域、と僕の中での評価が定まった。

最初は Resend と同じ感覚で Dashboard を開きかけて、「いや、Storage は API でいけるはずだ」と思い出して 4 step を書いた。その判断 1 つで 3 分が 30 秒に縮んだ。1 日に何回も同じ判断をする日には、こういう小さな短縮が積み上がる。

---

## おわりに

Vercel Storage は、Agent-Driven な開発フローに乗せる時に「ここはまだ UI が要る」と諦めなくていい領域だった。Blob も Edge Config も REST API + CLI で完全に動かせる。Dashboard を開く時間が `curl` 1 行に縮む。

僕が次に欲しいのは、Resend や Anthropic API 系の provider に同じ品質の Setup API が出てくることだ。Resend の domain verify が今でも marketplace 経由の UI 必須なのが地味に効いている。Anthropic API key の発行も console UI を開く必要がある。これらが「provider 側の REST API で create + scope 指定 + Vercel env への inject」まで一発で行ければ、僕の launch day はもう 30 分短くなる。

Vercel Storage は既に解けている。次はその外の領域だ。Storage に始まり、認証 / mail / AI / payment と provider が広がる中で、API ゼロ UI 化がどこまで進むか観察しながら、agent が触れる領域を 1 つずつ広げていく。1 人 + Claude Code で B2B SaaS を 1 日に 13 PR で動かすために、これは静かに効いてくる土台だと思っている。

---

## 関連

私の関連記事(Zenn):

- [ハーネスエンジニアリング入門 — CLAUDE.md 0 行から 420 ファイルまでの 8 ヶ月](https://zenn.dev/takuyanagai0213/articles/harness-engineering-intro-8months) — 本記事の上位概念、ハーネス全体の時系列
- [Vercel env を git push なしで production に反映する — PATCH + forceNew redeploy workflow](https://zenn.dev/takuyanagai0213/articles/vercel-env-hot-fix-workflow) — 同 stack 同 launch marathon の env hot fix deep dive
- [Neon Personal Token は org に bind される — /users/me で 30 秒で見抜く 1 行 verify pattern](https://zenn.dev/takuyanagai0213/articles/neon-personal-token-org-trap) — 同 launch marathon で踏んだ Neon org bound 罠
- [Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー](https://zenn.dev/takuyanagai0213/articles/drizzle-neon-mcp-branching-per-pr) — DB layer 3 ADR + 4 rules で見る Agent-Driven branching
- [Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで](https://zenn.dev/takuyanagai0213/articles/better-auth-magic-link-9days-removal-case) — 認証 layer 6 ADR の時系列
- [Vercel + Neon + Next.js + Drizzle + Better Auth で B2B SaaS を 1 ヶ月で立てた技術選定 — 28 ADR から見える Agent-Driven 開発の主軸](https://zenn.dev/takuyanagai0213/articles/agent-driven-b2b-saas-stack-selection-28-adrs) — 全 stack 俯瞰のメタ flagship
