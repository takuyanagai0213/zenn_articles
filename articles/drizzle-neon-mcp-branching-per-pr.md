---
title: "Drizzle + Neon MCP で『PR ごとに DB を持つ』 — Agent-Driven branching"
emoji: "🌿"
type: "tech"
topics: ["neon", "drizzle", "claudecode", "postgres", "agentnative"]
published: true
---

# Drizzle + Neon MCP で『PR ごとに DB を持つ』 — Agent-Driven branching

## はじめに

PR を push すると、数秒後には専用の Postgres が立ち上がっている。schema 変更が入っていれば自動で migration が当たる。production data は触らない。PR を close すれば DB ごと消える。

これが今の僕の開発フローだ。1 ヶ月前まではこんな世界が成立するとは思っていなかった。Upstash Redis に「1 キーに JSON 全体を突っ込む」というアンチパターンの DB 構造で動かしていた自社プロダクトを、ある日のブレストで一気に Postgres + Drizzle + Neon に置き換える判断をした。そこから 1 ヶ月で 5/1 production launch まで走り切った。

仕組みの core は 3 点セットだ。**Drizzle ORM** が code-first な schema を提供して LLM に親和し、**Neon** が copy-on-write branching で「PR ごとに DB を持つ」を秒単位で実現し、**Neon MCP server** が「自然言語で DB 操作」を成立させる。この 3 つが揃ったとき、個人 + agent 開発の DB 基盤が initial setup から運用まで一気通貫で組める。

この記事は、ある日本のアフィリエイト広告代理店で僕が PdM × テックリードとして 3 年運用してきた経験と、Claude Code を 1 年運用した過程で蓄積した「PR ごとに DB を持つ」 流派の話だ。失敗込みの時系列で書く。同じ stack を組もうとしている人の罠避けになれば嬉しい。

---

## 背景: Upstash Redis の 1 キー JSON アンチパターンから移行

自社で動かしていた記事チェックツールがある。クライアント企業が記事を審査する側、アフィリエイト企業が記事を提出する側、AI が自動レギュレーション審査を担う、という 3 者の業務を回すサービスだ。最初の MVP は僕が雑に作ったもので、永続化レイヤーは Upstash Redis、しかも「全 submission を 1 キーに JSON で突っ込む」という典型的なアンチパターンだった。検索もできない、トランザクションもない、複数 user で同時に書くと壊れる。

それを Postgres に移行する判断を 2026-04-22 に下した。ADR (Architecture Decision Record) を 2 本同時起票して、ORM は Drizzle、DB は Vercel Postgres (裏は Neon) + Neon MCP Server に決めた。判断の核には僕自身の願いがあった ── 「**ポータブルに起動、破棄してエージェンティックに開発**」 する DB 基盤が欲しい。Claude Code (とそのサブエージェント) が自律で DB branch を作ったり破棄したりできる構造にしたい。

ここから 1 ヶ月、5/1 launch までの marathon が始まった。

---

## Drizzle 採用の判断軸 (ADR-003)

ORM 選定では Prisma 7 / Kysely / @vercel/postgres template tag の 3 つを真剣に比較した。

Prisma 7 は schema-first の DSL で長年定番だった選択肢で、2025-11 に Rust ランタイムを撤廃して WASM 化したことで Edge runtime での起動コストが大きく下がっていた。Kysely は type-safe な query builder で、SQL に近い書き味が好きな人には魅力的だ。@vercel/postgres の template tag は ORM を持たず、SQL を文字列リテラルで書くだけの素朴さがある。

最終的に **Drizzle ORM (v0.45.2 時点)** を採用した。決め手は次の軸だ。

| 軸 | 評価 |
|---|---|
| schema = TypeScript 1 ファイル | `prisma generate` のような中間ステップ不要、`schema.ts` を保存した瞬間に型が反映される |
| エージェンティック親和 | LLM が schema を直接読み書きできる、`llms-full.txt` を Drizzle 公式が配布している |
| Edge runtime 対応 | 25kB ネイティブで動く、WASM/Rust 不要 |
| SQL-like API | `db.select().from(submissions).where(eq(...))` と SQL を書く感覚で LLM が素直にコード生成 |
| Neon branching + MCP との統合 | 公式ガイドあり、PR ごとの DB branch で migration 適用する pattern もドキュメント化されている |
| PlanetScale による後援 | 2026 初頭に Drizzle のコアチームを PlanetScale が雇用、フルタイム開発体制 |

特に大きかったのは **schema が TypeScript 1 ファイル** であることだ。たとえば submissions テーブルはこう書く。

```typescript
// apps/<product>/src/lib/db/schema.ts
import { pgTable, uuid, text, timestamp, jsonb } from "drizzle-orm/pg-core";

export const submissions = pgTable("submissions", {
  id: uuid("id").primaryKey().defaultRandom(),
  organizationId: uuid("organization_id").notNull(),
  status: text("status").notNull(),
  submittedAt: timestamp("submitted_at", { withTimezone: true }),
  issueComments: jsonb("issue_comments"),
  // ...
});
```

これだけで型が立ち上がり、`db.insert(submissions).values({...})` が型推論で守られる。Prisma の `prisma generate` のような中間ステップが要らないので、Claude Code が schema.ts を編集した瞬間にコード補完が反映される。LLM に schema 変更を任せるとき、この「中間ステップなし」 の特性が想像以上に効く。

却下した選択肢はそれぞれ理由があった。Prisma 7 は WASM 化で Drizzle との差は紙一重まで縮まったが、`prisma generate` 中間ステップと PSL (Prisma Schema Language) という独自 DSL が微不利。Kysely は型と migration が分散していて、エージェンティックな schema 変更で摩擦が増える。@vercel/postgres template tag は schema 管理の手段を別で持つ必要があってスケールしない。ZenStack のような Prisma 拡張系はサービスのサイズに対して over-engineering だった。

トレードオフも認識している。relations 記述がまだ成熟途上で、複雑な nested query で詰まる可能性がある。Prisma Studio 相当の GUI もない。`drizzle-kit push` は dev 用で、本番は `generate → migrate` の 2 ステップが推奨される ── ここは後述の罠と運用注意で詳しく書く。

---

## Vercel Postgres (Neon 裏) + Neon MCP の判断軸 (ADR-006)

DB レイヤーでは Vercel Postgres / Supabase / PlanetScale / Railway / Render / 自前 Docker Postgres / Turso / Cloudflare D1 まで一通り並べて検討した。要件はシンプルに 2 つ。

1. PR ごとに DB を分離できること (copy-on-write branching が秒で動く)
2. Vercel との統合が薄くないこと (preview deployment と DB が紐づくこと)

選んだのは **Vercel Postgres (裏は Neon serverless Postgres) + Neon MCP Server** の組み合わせだ。

| 軸 | 内容 |
|---|---|
| エージェンティック開発 | Neon branching により PR ごとに DB branch を切り、agent が独立した DB で作業 → 完了後 drop 可能 (copy-on-write で数秒) |
| Vercel 統合 | Vercel Postgres は裏で Neon、pooled connection / direct connection / preview branch が Vercel ダッシュボードで自動管理 |
| Neon MCP Server | Claude Code から自然言語で DB 操作可能、「ポータブルに起動、破棄」 ビジョンの具体的実装手段 |
| Drizzle との相性 | 公式ガイドあり、PR 別 migration 自動化の example も Drizzle 公式に存在 |
| Edge ランタイム対応 | HTTP driver で Vercel Edge Functions から直接接続可能 |

却下したのは次の通り。Supabase は Auth / Storage と機能重複 (Better Auth / Vercel Blob を採用済) で、必須機能 (Realtime / RLS 管理 UI) が今のサービスのペインを解かない。PlanetScale は MySQL 系で、Drizzle / Better Auth / pgvector を含む PostgreSQL エコシステムに揃えたい意図とずれる。Railway / Render は Vercel 統合が弱く、branching が Neon ほど成熟していない。自前 Postgres (Docker) は運用負担と Vercel デプロイ環境との差分が両方重い。Turso / Cloudflare D1 のような SQLite 系は、扱う案件 (アフィリエイト広告 + 金融) の信頼性要件を満たすかが未検証だった。

導入してみると、Vercel ダッシュボードから自社プロダクトの project の Storage タブを開けば、main branch に対する pooled connection / direct connection の URL が自動で env に injected される。Vercel preview deployment が走るときは、Neon の ephemeral branch URL が動的に DATABASE_URL に inject される ── これが「PR ごとに DB を持つ」 を秒で成立させる仕組みの core だ。

---

## Neon MCP server で自然言語 DB 操作

ADR-006 の決定で外せなかったのが Neon MCP server だ。MCP は Anthropic が定義した Model Context Protocol で、Claude Code から外部ツールを呼び出すための共通インターフェースになる。Neon が公式に MCP server (`neondatabase/mcp-server-neon`) を提供しているので、これを Claude Code に接続すると「自然言語で Neon project を操作する」が成立する。

セットアップは `.mcp.json` に 1 ブロック書くだけだ。

```json
{
  "mcpServers": {
    "neon": {
      "command": "npx",
      "args": ["-y", "@neondatabase/mcp-server-neon", "start"],
      "env": {
        "NEON_API_KEY": "..."
      }
    }
  }
}
```

(注: `env` の罠については後述する。実運用では `.env` 経由で読み込む。)

これだけで Claude Code 内から `mcp__neon__*` 系のツールが呼べるようになる。実際にどう使うかというと、こんなふうに。

```
僕: 「flat-hill-75451034 project の main branch に regulations table の最新 row を 5 件出して」

Claude Code:
  mcp__neon__run_sql({
    projectId: "flat-hill-75451034",
    branchId: "br-late-bonus-...",
    sql: "SELECT * FROM regulations ORDER BY created_at DESC LIMIT 5;"
  })
  → 結果が JSON で返ってくる
```

```
僕: 「PR #34 のために ephemeral branch を作って、main schema だけ copy して、URL 教えて」

Claude Code:
  mcp__neon__create_branch({
    projectId: "flat-hill-75451034",
    name: "pr-34-test",
    init_source: "schema-only"
  })
  → branch_id + connection URL が返る
```

UI を経由せず、Bash で `curl -H "Authorization: Bearer $NEON_API_KEY" https://console.neon.tech/api/v2/...` を叩く必要もなく、自然言語で完結する。自社プロジェクトでは `CLI or MCP, not UI.` という主軸を哲学レベルで掲げていて、UI 操作は **TPS アンドン発火 (異常時のみの人間介入)** に限定する設計にしている。Neon MCP はその思想にぴったりハマった。

主要なツールはこのあたりだ。

| ツール | 用途 |
|---|---|
| `mcp__neon__list_projects` | org 配下の project 一覧 |
| `mcp__neon__list_branches` | project の branch 一覧 |
| `mcp__neon__create_branch` | branch 作成 (init_source で schema-only / parent-data 選択) |
| `mcp__neon__delete_branch` | branch 削除 (test cleanup 用) |
| `mcp__neon__run_sql` | branch に対して raw SQL 実行 |
| `mcp__neon__get_connection_uri` | connection string 取得 |
| `mcp__neon__describe_table_schema` | table の schema を JSON で取得 |

僕が一番使っているのは `run_sql` と `create_branch` の 2 つだ。「production main で発生してる謎の row を Claude Code に解析させる」 とき、Claude が勝手に `run_sql` で raw 取得して、jsonb 列を parse して、原因仮説まで一気に返してくる。個人 1 人運用で、これほど DB 操作の摩擦が低い環境は今までなかった。

---

## PR ごとに DB を持つ workflow

ここが本記事の核だ。Neon-Vercel Native Integration を install 済の前提で、実際の dev workflow を時系列で追う。

```
1. branch 作成 + 実装
   └─ git checkout -b feat/regulations-org-scoped
   ↓
2. push + gh pr create
   ↓
3. Vercel が auto detect → preview deploy 走り出す
   ├─ Neon-Vercel Integration が ephemeral branch 自動作成
   │   (例: preview/feat-regulations-org-scoped、init_source=schema-only)
   ├─ vercel-build hook (scripts/run-migrations.ts) が
   │   MIGRATION_FILES を ephemeral branch に流す
   │   (VERCEL_ENV=preview の時のみ)
   └─ Vercel が build 完了 → preview URL 発行
   ↓
4. Vercel bot が GitHub PR conversation に preview URL コメント投稿
   (例: ✅ Preview Deploy Ready: https://{product}-git-xxx-{team}.vercel.app)
   ↓
5. PR ページから bot コメントの URL 踏む → preview env に access
   ├─ DB は ephemeral branch (production data 不可侵)
   ├─ schema 変更込みの動作確認可能 (vercel-build hook 効果)
   └─ Email / Auth / AI / Blob は env 設定で skip (副作用ゼロ)
   ↓
6. CI 6 check (tsc / vitest / next build / E2E / Vercel / Vercel Preview) green 確認
   ↓
7. UAT OK + CI green で merge
   ↓
8. main → production auto deploy
   └─ migration が PR 内にある場合は僕の手元で psql or Neon MCP で適用
```

ここで何が秒で成立しているか分解しておく。

**Vercel が PR push を検知** すると、Neon-Vercel Native Integration の webhook が発火して、Neon API に「この PR 用の ephemeral branch を作って」 と命令が飛ぶ。Neon は **copy-on-write** で main branch の schema (or schema + data) を秒単位で複製する。pg_dump で 3 分かけてダンプしてリストアするのではなく、Neon の storage layer が「branch ごとに変更点だけ持つ」 構造になっているので、複製コストがほぼゼロになる。

**ephemeral branch URL が Vercel の env に inject** される。この時、Vercel preview scope の `DATABASE_URL` だけが書き換わって、production scope の `DATABASE_URL` は touch されない。これが production data 不可侵の保証になる。

**vercel-build hook で migration auto-apply**。`package.json` の vercel-build script で `tsx scripts/run-migrations.ts && next build` を実行している。`scripts/run-migrations.ts` の中身はこう。

```typescript
// apps/<product>/scripts/run-migrations.ts (抜粋)
import { neon } from "@neondatabase/serverless";
import fs from "node:fs";
import { MIGRATION_FILES } from "./migration-files";

const env = process.env.VERCEL_ENV;

if (env === "production") {
  console.log("[run-migrations] VERCEL_ENV=production, skip");
  process.exit(0);
}

if (env !== "preview") {
  console.log("[run-migrations] VERCEL_ENV not preview, skip");
  process.exit(0);
}

const sql = neon(process.env.DATABASE_URL!);
for (const relPath of MIGRATION_FILES) {
  const migrationSql = fs.readFileSync(relPath, "utf8");
  await sql.query(migrationSql);
  console.log(`[run-migrations] applied: ${relPath}`);
}
```

`MIGRATION_FILES` は別ファイルに export されていて、CI E2E 経路と Vercel build 経路の両方で同じ配列を参照する。新しい schema 変更が入った PR では、SQL ファイルを 1 本足して `MIGRATION_FILES` に追記するだけで、preview UAT で schema 反映済みの動作確認ができる。

**この自動化のキモは `VERCEL_ENV=preview` で gate していること** だ。production には絶対に触らない。次の節で詳しく書くが、production migration は手動運用に倒している。これは migration discipline と呼んでいるルールで、僕 1 人運用 + リコール容易性を優先した判断だ。

---

## 境界設計: production manual migration

vercel-build hook を見て「production も自動で migration かけてくれた方が楽じゃないか」 と思う人もいるかもしれない。実際、ADR を書いた直後はそう倒すか迷った。

最終的に **production migration は手動** に倒した。理由は単純で、「production drift 防止より rollback 容易性を優先する」 思想だ。

production migration を自動化すると、main merge 時に「気づかないうちに schema が変わっている」 状態が生まれる。idempotent guard を完璧に書けば理論上は安全だが、人間が中身を確認してから流せる境界線を残しておきたい。何か事故が起きたとき、「main に merge した PR がどの SQL を実行したか」 を即座に振り返れる体制 ── これが運用上の安全装置になる。

具体的にどう運用しているかというと、PR description に **`⚠️ Migration` マーカー** を必ず付けて、merge 後に僕の手元で 1 行打つ。

```bash
# 僕の手元
psql "$DATABASE_URL_PROD" -f apps/<product>/scripts/migrations/024-regulations-org-scoped.sql

# または Claude Code (Neon MCP 経由)
mcp__neon__run_sql({
  projectId: "flat-hill-75451034",
  branchId: "br-main-...",
  sql: "..."
})
```

merge 後の Slack 通知 + handover doc にも migration apply 手順を書いておく。1 人運用なので forget リスクはあるが、`⚠️` マーカーが目に入る習慣で対処している。

将来 trigger があれば自動化に倒す可能性は残してある。具体的には次のいずれかが起きたら ADR を起票して `drizzle-kit migrate` ベース + GitHub Actions or Vercel deploy hook で「main merge 時にだけ migration 適用」 の仕組み化に進む判断だ。

- メンバー 2 人目: 誰が schema を変えたか追跡が必要
- 監査要件: 金融案件で migration 履歴が要求される
- incident 経験: production drift が原因で問題発生

`Leave flowers for tomorrow.` ── ペインが具体化するまで構造を足さない、というのが自社プロジェクトの哲学だ。

---

## E2E test の schema-only branching (ADR-012)

PR の動作確認だけでなく、CI で動かす E2E test にも Neon ephemeral branch を使っている。Playwright + Neon ephemeral branch の組み合わせだ。

要件はこうだった。アフィリエイト広告 × 金融案件向けのため、**production DB を test で汚してはいけない**。一方で「メール配信なしで Magic Link ログインができる」 という開発体験は維持したい (Better Auth + Magic Link は console.log fallback を持つ)。

仕組みはこう。

```
[main branch (production)]   ← migrate 済 + seed 済
   │
   ├─ init_source: schema-only
   │     ↓
   │  [e2e-<timestamp> branch]   ← テーブル構造だけ、data 空
   │     ↓ (global-setup)
   │  INSERT organizations ('クライアント A', 'client_a')
   │     ↓ (tests)
   │  Magic Link flow: user / session / verification が新規作成
   │     ↓ (global-teardown)
   │  DELETE branch
```

実装ポイントは Playwright の `globalSetup` / `globalTeardown` を使う。

```typescript
// tests/e2e/global-setup.ts (抜粋)
import { neon } from "@neondatabase/serverless";
import { MIGRATION_FILES } from "../../scripts/migration-files";

export default async function globalSetup() {
  // 1. Neon API で schema-only branch 作成
  const branch = await createBranch({
    projectId: "flat-hill-75451034",
    name: `e2e-${Date.now()}`,
    init_source: "schema-only",
  });

  // 2. .env.local を一時 backup + test DB URL に書き換え
  backupEnvLocal();
  writeTestDatabaseUrl(branch.connectionUri);

  // 3. seed (organizations 1 行だけ fixture)
  const sql = neon(branch.connectionUri);
  await sql`INSERT INTO organizations (name, slug) VALUES ('クライアント A', 'client_a')`;

  // 4. PR 内の migration を順次適用
  for (const relPath of MIGRATION_FILES) {
    const migrationSql = fs.readFileSync(relPath, "utf8");
    await sql.query(migrationSql);
  }
}
```

```typescript
// tests/e2e/global-teardown.ts (抜粋)
export default async function globalTeardown() {
  restoreEnvLocal();
  await deleteBranch({ projectId, branchId });
}
```

Magic Link の verify token は Better Auth が `verification` テーブルに直接書く ので、test 内で SQL を引いて取得する。

```typescript
// tests/e2e/helpers/magic-link.ts (抜粋)
const sql = neon(process.env.DATABASE_URL!);
const rows = await sql`
  SELECT identifier, value FROM verification
  WHERE identifier LIKE 'magic-link:%'
  ORDER BY created_at DESC LIMIT 1
`;
const token = rows[0].identifier.replace("magic-link:", "");
```

`identifier` が raw token、`value` が `{email, attempt}` の JSON。これで「メール配信を経由せずに verify URL を叩く」 が test で成立する。

なぜ schema-only なのかというと、production user / session data を test 環境に copy しないことで compliance + security を担保したいからだ。test 開始時の DB 状態が常に predictable なので、「前回 test の残渣が効いて動く」 という flake も排除できる。fixture は code で管理することで「何が test 依存データか」 を明示できる ── documentation as code としても機能する。

---

## 罠と運用注意

ここまでで仕組みの形は見えたと思う。最後に、移行 1 ヶ月の launch marathon で踏んだ罠を 3 つ書いておく。

### 罠 1: `drizzle-kit push --force` の TTY 必須 prompt

CI E2E の global-setup で「最新 schema を ephemeral branch に反映する手段」 として、最初は `drizzle-kit push --force` を使おうとした。これが見事に踏み抜けた罠だった。

`drizzle-kit push --force` は **column rename detection の interactive prompt を skip しない**。`--force` フラグは data 損失系 prompt のみ skip する仕様で、rename 検出は別軸。CI は TTY 無し環境のため次のエラーで fail する。

```
Error: Interactive prompts require a TTY terminal
  at promptColumnsConflicts ...
```

しかも drizzle-kit がエラーで exit しても直後の console.log は走るため、**ログ上は `✓ schema pushed` の偽 success 表示**が出る罠もあった。schema 反映されないまま test に進んで `column "X" does not exist` で fail。原因究明に半日かかった。

最終的に **migration SQL を `sql.query()` で直接実行** する pattern に統一した。

```typescript
const sql = neon(branch.connectionUri);
for (const relPath of MIGRATION_FILES) {
  const migrationSql = fs.readFileSync(relPath, "utf8");
  await sql.query(migrationSql);  // HTTP driver で raw SQL、prompt 不在
}
```

これだと CI E2E と Vercel preview で **同じ migration SQL が走る** ので drift が起きない。新しい ADR で schema 変更が入ったら `MIGRATION_FILES` 配列に 1 行追記するだけで両方に反映される。自社プロジェクトでは「発生源を辿る」 という考え方を持っていて、CI 経路と production 経路の中継地それぞれを fix するのではなく、production と同じ migration SQL に発生源を統一する判断だ。

### 罠 2: Neon Local + HTTP driver の transaction 互換性

dev 環境で Neon Local という docker proxy を試した時期があった。これは Neon serverless driver を local docker container 経由で動かす公式の仕組みで、開発環境でも production と同じ HTTP driver を使えるようにする。

ところが Better Auth の `/api/auth/sign-up/email` endpoint で `NeonDbError: Error connecting to database: TypeError: fetch failed` が出始めた。一方で `/api/auth/get-session` は HTTP 200 で動く。

調査して仮説に至った。Neon Local 公式 docs にこう書かれている。

> For serverless driver usage, the container operates in HTTP-only mode (no websockets), requiring specific configuration.

`drizzle-orm/neon-http` が transaction を batch 化する pattern と、Neon Local の HTTP fetch endpoint が部分的に非互換 ── というのが今のところの推定だ。GET / 単純 SELECT は動くが、Better Auth INSERT 系 (user / account / session 同時 INSERT) は動かない。

完全に解明できないまま、運用としては「dev は Neon Local、E2E test は Neon Cloud に直接接続」 という二重経路で並走させる判断にした。互換性が解消できたら統一する積み残しタスクとして抱えている。

### 罠 3: Preview ephemeral branch は parent_timestamp 後に auto 同期しない

これが一番ハマった罠だ。Neon-Vercel Native Integration の preview branch は **branch 作成時点の main snapshot を copy** する仕組み (Neon 内部では `init_source: parent-data`、各 branch の `parent_timestamp` field で snapshot 時刻が visible)。**snapshot 時刻より後の main 変更は preview branch に自動伝搬しない**。これが Neon の設計仕様だ。

5/1 launch 当日、Magic Link 廃止 (ADR-028) を入れた直後に「Magic Link で signup したけど password を未設定の user が signin できない」 問題が発生した。orphan user 復旧のために production main に対して `account` 行を INSERT した。

ところが、既に open している PR の preview branch には反映されない。dev チームメンバーが「自分の PR の preview で signin 試してるんですが、復旧 user で sign in できません」 と報告してきた。

| user | main INSERT 時刻 (UTC) | 対象 PR | preview parent_timestamp (UTC) | 自動反映 |
|---|---|---|---|---|
| dev member A | 2026-05-01 06:07 | PR #113 | 2026-05-01 06:14 | ✅ あり (main INSERT が snapshot より前) |
| dev member B | 2026-05-01 11:19 | PR #116 | 2026-05-01 06:14 | ❌ なし (main INSERT が snapshot より後) |

同じ admin manual fix でも user ごとに preview への自動反映の有無が分かれた。`parent_timestamp` と fix 実行時刻の前後関係で決まる構造になっている。

復旧のため、各 open PR の preview ephemeral branch にも個別に SQL を流した。Vercel preview deployment の env tab か Neon Console の該当 branch の connection string を取得して、ephemeral branch URL に対して同じ INSERT を実行する。手間ではあるが、parent_timestamp の前後を見れば「どの branch に追加 fix が必要か」 は機械的に判定できる。

この事象をきっかけに、本 rule を `.claude/rules/neon-vercel-integration.md` に永続化した。ephemeral branch の独立性は便利な特性だが、admin manual fix を入れた時は parent_timestamp の境界を意識するというのが運用の anchor になっている。

---

## おわりに

Drizzle + Neon + Neon MCP の 3 点セットを 1 ヶ月運用してみて、「個人 + agent 開発の DB 基盤」 として機能する条件が見えてきた。

要点は 3 つだ。**code-first な ORM** が schema を TypeScript 1 ファイルに集約して LLM に直接読ませる、**copy-on-write branching** が PR ごとの DB 分離を秒で成立させる、**MCP server** が UI を経由しない自然言語 DB 操作を提供する。この 3 つが揃うと、ephemeral branch + schema-only E2E + production manual migration の境界設計が個人 + agent 開発の安全性を担保する形に倒せる。

僕個人の状況は、Claude Code を 1 年運用して 100+ Skills と 34,000+ memory entries で組んだコンテキスト基盤の上で動いている。僕個人の `.claude/` には 420 ファイルがある。だから「PR を push したら DB が立ち上がって migration が当たる」 という体験が、個別の自動化ではなく **積層したハーネスの一部として自然に発火する** 状態になっている。Drizzle + Neon + MCP は単独でも強力だが、ハーネスエンジニアリング全体の一節として組み込むと圧倒的に効く。

ここに書いたのは「PR ごとに DB を持つ」 という単一テーマだけだ。同じ 1 ヶ月の launch marathon で扱った認証 layer (Magic Link 9 日で廃止) や、UI ゼロで Vercel Storage を setup する話、git push なしで env を hot fix する話、Personal Token が org に bind される罠の話などは、別記事で書いている。同じ stack の deep dive を読みたい人は併せて参照してほしい。

---

## 関連

- [ハーネスエンジニアリング入門 — CLAUDE.md 0行から420ファイルまでの8ヶ月](https://zenn.dev/takuyanagai0213/articles/harness-engineering-intro-8months) — 本記事の上位概念、ハーネス全体の時系列
- [Vercel Storage を UI ゼロで setup する — API + CLI で Blob / Edge Config を立ち上げる](https://zenn.dev/takuyanagai0213/articles/vercel-storage-api-zero-ui) — 同 stack 同 launch marathon の deep dive
- [Vercel env を git push なしで production に反映する — PATCH + forceNew redeploy の hot fix workflow](https://zenn.dev/takuyanagai0213/articles/vercel-env-hot-fix-workflow) — 同 stack 同 launch marathon の deep dive
- [Neon Personal Token は org に bind される — UI 表記揺れと cross-org access の罠](https://zenn.dev/takuyanagai0213/articles/neon-personal-token-org-trap) — 同 stack の罠記事、本記事 ADR-023 の background
- [Vercel + Neon + Next.js + Drizzle + Better Auth で B2B SaaS を 1 ヶ月で立てた技術選定 — 28 ADR から見える Agent-Driven 開発の主軸](https://zenn.dev/takuyanagai0213/articles/agent-driven-b2b-saas-stack-selection-28-adrs) — 全 stack 俯瞰のメタ flagship
- [Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで — 認証 6 ADR の時系列](https://zenn.dev/takuyanagai0213/articles/better-auth-magic-link-9days-removal-case) — 認証 layer の deep dive
