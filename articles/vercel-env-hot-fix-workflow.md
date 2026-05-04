---
title: "Vercel env を git push なしで production に反映する — PATCH + forceNew redeploy workflow"
emoji: "🔁"
type: "tech"
topics: ["vercel", "devops", "claudecode", "nextjs", "agentnative"]
published: true
---

## はじめに

production の env に `\n` が混入していることに気づいたのは、launch 当日の朝だった。Vercel Dashboard でぱっと見、`NEXT_PUBLIC_APP_URL` の末尾が改行で終わっている。値は合っている。改行 1 文字だけが余計に入っている。

最初に頭をよぎったのは「git push しないと反映されないやつだ」だった。env を直す → commit する → push する → CI 待ち → deploy 待ち。launch 直前にこれを 4 回やる気力はない。そもそも env の typo を直すために dummy commit を main に push するのは、git history を汚すアンチパターンだ。

結論を先に言うと、Vercel API は **「env を PATCH で更新 → 既存 deployment を forceNew=1 で redeploy」** という 4 step workflow を提供している。git push は不要、production rebuild は 1-2 分で完了する。僕はこの workflow を自社の B2B プロダクトの launch 当日(2026-04-29)に 4 回回して、git history をひと commit も汚さずに env 関連の hot fix を全部捌いた。

この記事はその workflow の手順と、ハマりどころと、僕が dummy commit を push しかけた話だ。

---

## 背景: env 変更だけで auto deploy は trigger しない

Vercel に少し慣れた人ほど、最初に踏みやすい罠がある。「Vercel は git push したら自動で deploy するから、env も自動で反映されるだろう」と思い込んでしまう罠だ。

実際は違う。Vercel の auto deploy が動く trigger は **git push** だけだ。Dashboard や API から env を更新しても、auto deploy は何も起きない。production は古い env 値のまま走り続ける。env を直しても、そのままでは production runtime には届かない。

僕も最初は知らなかった。env を Dashboard で直して、3 分待って production にアクセスして、まだ古い文言が出ていて「あれ?」となった。リロードを何度かしてキャッシュを疑い、ブラウザを変えてみて、それでも古い。Logs を見たら deployment は更新されていない。当たり前だった。env を変えただけだから。

ここで人間が一番やりがちなのが、**dummy commit を main に push する**ことだ。`git commit --allow-empty -m "redeploy"` みたいなやつ。これで auto deploy は確かに走る。env も最新の値で読まれる。production は直る。

ただ、この方法は git history に「redeploy」「force redeploy」「fix env」みたいな意味のない commit を残す。1 回ならまだしも、launch 当日に env hot fix を 4 回必要とした僕の場合、main の log がそんな commit で埋まる。release notes を書く時に困るし、後で「この日何が起きたんだろう」と振り返る時に何の手がかりも残らない。

正解は、git を全く触らずに env だけを反映する方法を取ることだ。Vercel の API はそれを expose してくれている。

---

## 4 step workflow

ここから手順に入る。前提として `VERCEL_TOKEN_SAML` (ローカルの `~/.local/share/com.vercel.cli/auth.json` から `jq -r '.token'` で抜くか、Account Settings から発行) と `TEAM` (`team_xxx`) と `PROJECT` (`prj_xxx`) を環境変数に持っているとする。

### Step 1: env id を identify する

Vercel API は env を `key` ではなく **id** で参照する。同じ key 名で scope (production / preview / development) ごとに別 id が振られているので、まず一覧から該当 id を引く。

```bash
curl -sS -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  "https://api.vercel.com/v10/projects/$PROJECT/env?teamId=$TEAM" | \
  jq '.envs[] | select(.key == "NEXT_PUBLIC_APP_URL") | {id, target, value}'
```

返ってくる JSON の `id` フィールドを次の step で使う。production と preview の id は別物なので、`target` も併せて確認する。

### Step 2: PATCH で値を更新する

env id が手に入ったら、PATCH で value を上書きする。

```bash
curl -sS -X PATCH -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  -H "Content-Type: application/json" \
  -d '{"value":"https://<production-domain>"}' \
  "https://api.vercel.com/v10/projects/$PROJECT/env/<env_id>?teamId=$TEAM"
```

ここでの注意は、JSON literal で値を渡すので **改行や引用符の escape を間違えない**ことだ。今回の bug の発生源も「以前 env に値を入れた時に、何かのコピペで末尾改行が紛れ込んだ」だった。PATCH の payload を整形する時にも同じことが起きうる。値は最小限の文字列で渡すのが安全だ。

PATCH が成功すると、Dashboard の Settings → Environment Variables で値が更新されたことが確認できる。ただし、これだけでは production は何も変わっていない。次の step で deployment を作り直す。

### Step 3: 現 production deployment id を取る

ここが workflow の鍵になる step だ。

```bash
CURR_DPL=$(curl -sS -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  "https://api.vercel.com/v6/deployments?projectId=$PROJECT&teamId=$TEAM&target=production&limit=1" | \
  jq -r '.deployments[0].uid')
echo "$CURR_DPL"
# dpl_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`target=production&limit=1` で、現在 production として serve されている deployment 1 件だけを取り出している。この id がそのまま「次の redeploy で使う source の指定」になる。

### Step 4: forceNew=1 で redeploy する

最後に、Step 3 の deploymentId を渡して新しい deployment を生成する。

```bash
curl -sS -X POST -H "Authorization: Bearer $VERCEL_TOKEN_SAML" \
  -H "Content-Type: application/json" \
  -d "{\"deploymentId\":\"$CURR_DPL\",\"name\":\"<project-name>\",\"target\":\"production\"}" \
  "https://api.vercel.com/v13/deployments?teamId=$TEAM&forceNew=1"
```

レスポンスに `dpl_xxx` の新 id と `INITIALIZING` 状態が返ってくる。1-2 分待つと READY になり、production が新 deployment に切り替わる。

ここまでで合計の所要時間は、curl 4 発で 5 秒、build 待ちで 1-2 分。env hot fix 全体で **2 分以内**に完了する。git push のサイクル(commit → push → CI → build → deploy)を待つよりずっと速い。

---

## 仕組みの肝

なぜこれで「同じ git commit のまま env だけ最新値」が実現するのか、内部のメンタルモデルを書いておく。

`POST /v13/deployments` の `deploymentId` field は、「**この既存 deployment と同じ git commit、同じ source code を使え**」という指定だ。普段 git push で auto deploy が動く時は、Vercel が新しい commit sha を pull して build する。今回は逆に、既に存在する deployment の sha を「source 指定」として渡す。Vercel はその sha の source を再取得して build に入る。

ここで `forceNew=1` を付けると、cache を一切使わずに fresh build を強制する。普段の build は cache layer を活用して時間を短縮するが、env を変更した時は cache 内に古い env の影響が混入している可能性があるので、**fresh build で env を確実に上書き反映させる**のが安全だ。

結果として「直前の main HEAD の commit (= production と同じ source code) を build、ただし env は最新の PATCH 後の値で読む」という挙動になる。git は触らない。source code は何も変わっていない。env だけが新しい。これがこの workflow の本質だ。

---

## 適用シナリオ

僕が 4/29 の launch 当日に踏んだ env bug は、4 つの異なる種類だった。それぞれ適用シナリオとして整理しておく。

| シナリオ | 修正内容 | 例 |
|---|---|---|
| 末尾 `\n` 混入 | 正しい値で PATCH → redeploy | `NEXT_PUBLIC_APP_URL` / `BETTER_AUTH_URL` / `NOTIFY_EMAIL_FROM` の末尾改行を削除 |
| 旧 keyword 残存 | 新文言で PATCH → redeploy | プロダクト名変更で `NOTIFY_EMAIL_FROM` の表示名を旧名 → 新名へ |
| 新規 env 追加後の反映 | 別途 connect で env 投入 → redeploy | Vercel Blob token (`BLOB_READ_WRITE_TOKEN`) を新規 connect、その後 forceNew で反映 |
| 値の format 変更 | PATCH → redeploy | URL の末尾 slash の有無、scheme の `http` → `https` 等 |

特に 1 番目の改行混入は、過去にどこかの flow でコピペが汚れていると気づきにくい。Dashboard で値を見ると一見正しく見える。`curl https://api.vercel.com/v10/.../env` のレスポンス JSON の `value` field を bytes 単位で確認するか、production 上で実際に出力されている文字列を console で覗くと初めて気づく類のバグだ。

3 番目の「新規 env 追加後の反映」は別の workflow と組み合わせる。たとえば Vercel Blob を connect した時、API 経由で `BLOB_READ_WRITE_TOKEN` が production scope に inject される。inject されただけでは production runtime にはまだ届いていないので、この記事の Step 3-4 と同じ `forceNew=1` redeploy を打って初めて runtime で `process.env.BLOB_READ_WRITE_TOKEN` が読めるようになる。

---

## Anti-pattern

ハマりやすい落とし穴を 4 つ挙げておく。

| Anti-pattern | 何が起きるか |
|---|---|
| env PATCH だけして redeploy を忘れる | production runtime は古い env 値のまま、修正反映されない |
| Vercel auto deploy ON だから自動 redeploy されると思い込む | env 変更単独では auto deploy trigger されない、git push が必須(と思い込んで dummy commit を打ちかける) |
| 適当な dummy commit を push して redeploy を誘発する | git history が dummy commit で汚れる、forceNew API で十分なのに git の log を犠牲にする |
| 旧 vercel CLI (`28.x` 系) で env pull して値確認する | 旧 CLI は SAML 通らないことがある、`npx vercel@latest env pull` で latest を invoke するのが安全 |

特に 1 番目は何度も踏んだ。PATCH のレスポンスが `{"value":"...","updated":true}` 系で返ってくると、つい「終わった」気になって production を見に行ってしまう。production は redeploy するまで古い値で走り続けている。Step 4 を打つまで何も終わっていない、と頭に刻む。

僕が dummy commit を打ちかけたのは 2 番目だった。env を直して、production が変わらず、「あれ、auto deploy 動いてない?」と思って `git commit --allow-empty -m "force redeploy"` まで指がいきかけた。寸前で `forceNew=1` の API があったことを思い出して止まった。launch 当日の main log に「force redeploy」が 4 つ並んでいたら、その日の release notes の見栄えは確実に悪い。

---

## 確認 verify

redeploy が READY になったら、production endpoint へ probe を打って HTTP status を確認する。

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://<production-domain>/
# → 200
```

env の値そのものを直接 production から覗く API はないので、間接的に verify する。たとえば `NOTIFY_EMAIL_FROM` を変えた時は、修正後に届く通知メールの From 表示で確認する。`NEXT_PUBLIC_APP_URL` なら、ページ内の絶対 URL が新値で出力されているかを browser の view-source で確認する。

「PATCH → redeploy → probe → 値の間接確認」を 1 セットの workflow として身体に入れておくと、env 周りの hot fix を回す速度が一気に上がる。

---

## 実証(2026-04-29 launch 当日)

最後に、この workflow を本番で 4 回回した話を書いておく。

僕は日本のアフィリエイト広告代理店で PdM 兼 Tech Lead をしていて、Claude Code を 1 年運用しながら 100+ Skills と 34,000+ memory entries と 420 ファイルのコンテキスト基盤を育てている。自社の B2B SaaS の launch 当日(2026-04-29)、僕は 1 日で 13 PR を merge した。その日の終盤、env hot fix が 4 回必要になった。

1 回目は `NEXT_PUBLIC_APP_URL` / `BETTER_AUTH_URL` / `NOTIFY_EMAIL_FROM` の末尾 `\n` を一気に削除した時。過去の env 投入時に紛れ込んだ改行を、起点を辿らずに直接 PATCH で消した。2 回目はプロダクト名変更で `NOTIFY_EMAIL_FROM` の表示名を旧名から「記事チェック Pro」に切り替えた時。3 回目は Vercel Blob を新規 connect して `BLOB_READ_WRITE_TOKEN` を production に流し込んだ時。4 回目は、3 回目の余波で起きた別 env 関連の小修正だった。

合計で git push は **0 回**。main の history は launch 当日の業務ロジック commit だけで埋まり、「force redeploy」みたいな夾雑物は 1 個も入らなかった。release notes を書く時、main log を eyeball で読むだけでその日の成果が把握できた。

英語圏の Vercel ユーザーで `forceNew=1` の用法を解説している記事はちらほらあるが、env hot fix 専用の標準 workflow として整理した日本語記事は少ない。launch のような短時間で複数の env を直す状況に何度か遭遇してから、この 4 step を頭の中の決まったパターンとして持っておくのは僕にとって明確に価値があった。

---

## おわりに

env の hot fix は、SEV 分類で言えば「revert 容易、影響時間 1-2 分、影響範囲は production runtime のみ」という分類に入る。git history を汚さずに API で完結するなら、それが筋だ。

この workflow が成立しているのは、Vercel が `deploymentId` 指定 + `forceNew=1` という API surface を expose してくれているからだ。自前で deploy infrastructure を持っていたら、env 反映のために build pipeline を 1 から作り直す必要があった。SaaS provider が「source code と env の境界線」を API で扱える形にしてくれている恩恵を、僕は今回 4 回受けた。

「env の値を直すために git の log を犠牲にする」という妥協を、もうしなくていい。

---

## 関連

私の関連記事(Zenn):

- [ハーネスエンジニアリング入門 — CLAUDE.md 0 行から 420 ファイルまでの 8 ヶ月](https://zenn.dev/takuyanagai0213/articles/harness-engineering-intro-8months) — 本記事の上位概念、ハーネス全体の時系列
- [Vercel Storage を UI ゼロで setup する — Agent-Driven 開発の Storage 自動化パターン](https://zenn.dev/takuyanagai0213/articles/vercel-storage-api-zero-ui) — 同 stack 同 launch marathon の Storage setup deep dive
- [Neon Personal Token は org に bind される — /users/me で 30 秒で見抜く 1 行 verify pattern](https://zenn.dev/takuyanagai0213/articles/neon-personal-token-org-trap) — 同 launch marathon で踏んだ Neon org bound 罠
- [Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー](https://zenn.dev/takuyanagai0213/articles/drizzle-neon-mcp-branching-per-pr) — DB layer 3 ADR + 4 rules で見る Agent-Driven branching
- [Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで](https://zenn.dev/takuyanagai0213/articles/better-auth-magic-link-9days-removal-case) — 認証 layer 6 ADR の時系列
- [Vercel + Neon + Next.js + Drizzle + Better Auth で B2B SaaS を 1 ヶ月で立てた技術選定 — 28 ADR から見える Agent-Driven 開発の主軸](https://zenn.dev/takuyanagai0213/articles/agent-driven-b2b-saas-stack-selection-28-adrs) — 全 stack 俯瞰のメタ flagship
