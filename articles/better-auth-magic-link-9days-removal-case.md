---
title: "Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで — 認証 6 ADR の時系列"
emoji: "🔐"
type: "tech"
topics: ["betterauth", "nextjs", "claudecode", "authentication", "agentnative"]
published: false
---

# Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで — 認証 6 ADR の時系列

## はじめに

2026 年 4 月 22 日、僕は Better Auth で B2B SaaS の認証 layer を組んだ。Magic Link を主軸に置いて、URL を `/signin` と `/signup` に分離して、組織モデルは plugin に任せた。「これで 5/1 の本番までに onboarding できる」と思った。

そして 2026 年 5 月 1 日、launch 直前の UAT で Magic Link を消した。

9 日後の話だ。

その間に書いた認証関連の ADR は 6 本ある。組織モデル plugin を削除し、membership pattern で復活させ、Magic Link を「両対応」にしてから「片対応」に戻して、最終的に「単対応」に絞った。動かす度に判断が変わった。

これは「Better Auth のチュートリアル」ではない。**認証 layer がなぜ 9 日で 6 回変わったか**の時系列だ。OSS の認証 lib を選ぶと、こういう動き方ができる。SaaS 認証(Clerk 等)では同じ判断密度で動けない。同じく日本のアフィリエイト広告代理店で B2B SaaS を立ち上げる人、エージェント駆動開発で認証選定を考えている人、「pain が見えてから消す」を哲学として持っている人 ── そういう人に向けて書いた。

僕は 1 年間 Claude Code を運用していて、100+ Skills と 34,000+ memory entries と 420 ファイルのコンテキストを持っている。その上で動く認証 layer の作り方の話だ。

---

## 背景: 自前 Base64「hash」と命名された欠陥認証

Better Auth に乗り換える前の状態から始めたい。自社の記事チェックツール(後に B2B プロダクト名で rebrand)の認証は自前実装だった。`src/lib/auth.ts` に書かれたコードはおおよそこんな雰囲気だった。

```typescript
// 旧実装 (廃止予定)
const hash = Buffer.from(raw).toString("base64");
```

変数名は `hash` になっている。だが実態は Base64 エンコードだ。secret が token にほぼ平文で含まれていた。`hash` という名前を信じてレビューを通した過去の僕がいて、本人もこの欠陥に気づいていなかった。気づいたのは、5/1 に金融案件(アフィリエイト広告主側のクライアント)で本番運用予定が立った時だ。「金融に持っていく前に作り直さないと、説明できない」と思った。

ここから認証選定が始まった。2026 年 4 月 22 日のことだ。

---

## ADR-004 採択: なぜ Better Auth か (2026-04-22)

選択肢は次の通りだった。

- Better Auth (OSS、self-hosted library、v1.6.5 当時)
- Auth.js v5 (NextAuth 後継、ただし 2025-09 に Better Auth へ公式バトン)
- Clerk (SaaS、UI component 充実)
- Lucia Auth (2025-03 EOL)
- Stack Auth、WorkOS、Kinde、Supabase Auth

最初に Clerk を真剣に検討した。UI component が `<SignIn />` 一発で出る、ダッシュボードで user 一覧が見える、MFA も組み込み済み。「速い」が圧倒的だ。しかし金融案件で詰まった。Clerk は米国 SaaS で、PII (個人識別情報) が国境を越える。金融案件のクライアントに「ユーザーの email がどこに保管されるか」を説明する時、「Clerk という米国の SaaS に転送されます」と言うコストがどれだけになるか想像がつかなかった。100K MAU で月 $2,025 のコストも痛い。さらに、エージェント駆動で開発している以上、**ダッシュボードに往復するワークフローが致命的**だった。Claude Code に `user の状態を確認して` と指示した時、Clerk の場合は「ダッシュボードを開いて確認してください」と返ってくる。MCP server が公式で出るまで、Clerk はエージェント駆動と相性が悪い。

Auth.js v5 は別の理由で外した。2025 年 9 月に NextAuth から Better Auth へ公式バトンが渡されており、security patch のみで Next.js 16 の対応も追従していなかった。もう「過去の遺物」になっていた。Lucia は EOL 済。Supabase Auth は別の DB layer (Supabase) を引き連れてくる ── ADR-006 で Vercel Postgres (Neon) を採用していたので矛盾していた。

Better Auth に決めた根拠を 3 軸で整理した。

| 軸 | 評価 |
|---|---|
| 2026 年のメンテナンス | Auth.js 公式後継、活発 (毎期 70+ 新機能) |
| 金融案件 PII 境界 | データは Vercel Postgres (Neon) に留まる ── 米国 SaaS 越境なし |
| Next.js 16 対応 | `middleware.ts → proxy.ts` 公式対応済 |
| Magic Link + Resend | `sendMagicLink` コールバック 6 行で完結 |
| エージェンティック親和 | 設定が TS 1 ファイル、plugin 配列で明示、UI 往復なし |
| RBAC / Organizations | `organization` plugin で標準サポート |

特に効いたのは「エージェンティック親和」だ。Better Auth の設定は `auth.ts` という 1 つの TypeScript ファイルに集約される。plugin を配列で並べて、option object で挙動を指定する。Claude Code がこのファイルを Read すれば、認証の全構造が読める。Clerk のように「dashboard で設定変更しました」というレイヤーが存在しない。「発生源を辿る」 という考え方を僕は使うことがあるが、認証の発生源 (真の SSOT) がコードベースに留まる構造は、エージェント駆動と決定的に相性がいい。

トレードオフは正直にあった。v1.6.5 当時の成熟度は Clerk に及ばない (v1.5.0 では Magic Link の `verifications` テーブルに schema bug があった)。`<SignIn />` のような UI component は無く、自前で書く必要がある。ドキュメント量も Clerk に劣る。だが「コードベースで完結する」という構造的優位を、僕は他のすべてに優先させた。

---

## ADR-013 + ADR-015: Magic Link 入れた経緯 (2026-04-22)

Better Auth を採択した同じ日、認証 UX を詰めた。ここで僕は **Magic Link 主軸 + URL 分離 (`/signin` と `/signup`)** を選んだ。

URL 分離は僕の体感ベースだ。「URL 分離で使いづらさを感じたことはない」という生のフィードバックが手元にあった。新規 user と既存 user の心的モデルが URL で分かれる方が直感的だ ── そう判断した。backend は Magic Link 1 本、UI は `/signin` と `/signup` の 2 枚で共通 component (`<MagicLinkForm />`) を共有して、CTA 文言だけ差し替える形にした。

ところが同じ日の深夜、別の問題が浮上した。Resend の本番化が外部ブロッカーで止まっていた。Magic Link を実 email で配送するには、独自ドメインの取得 → Resend の domain verify → DNS 設定 (SPF/DKIM/DMARC) が必要で、ドメイン名そのものが**外部の関係者のサービス名決定待ち**だった。5/1 launch まで間に合うか不確実。`better-auth.ts` は `RESEND_API_KEY` 未設定時に `console.log` fallback で Magic Link URL を出す実装になっており、**僕以外の誰も production で signin できない**状態だった。

ここで自分の中から逆向きの問いが出た。「Resend って必須だったっけ。シンプルに Email/Password で Better Auth できないの」。

Better Auth の `emailAndPassword` を再確認すると、標準 plugin で追加依存ゼロ、`autoSignIn: true` で signup 即 session 発行、`requireEmailVerification: false` で Resend 未稼働でも完結する。設計選択肢が 3 つに整理された。

- 案 α: Magic Link を外して Email/Password 一本化
- 案 β: Magic Link + Email/Password 両対応
- 案 γ: 現行 (Magic Link のみ) を Resend で押し切る

α か β か γ か。この α/β/γ pattern は自社プロジェクト全体で繰り返し出てくる判断 frame だ。**大工事 (α) / 中規模 (β) / 保留 (γ)** の 3 軸で並べて、pain 具体化度で決定する。Resend ブロッカーで困っている pain は具体化していたので γ は外した。α と β で迷ったが、僕の既存 Magic Link session (7 日 valid) を無効化したくない非破壊性、Resend 稼働後に Magic Link を本活用できる余地、外部パートナーがどちらの方式を選べるかという UX 余白 ── 全部勘案して **β (両対応)** を選んだ。default tab は `password` にした。

ADR-015 で β を採択した時の僕は、こう書いている。

> **当時の却下理由 (案 α、Magic Link 廃止)**:
> - 僕の既存 Magic Link session (7 日 valid) を無効化、非破壊性損失
> - Magic Link を本活用できる余地を残しておきたい (Resend 稼働後)

この「余地を残す」判断が、9 日後にひっくり返ることになる。

---

## ADR-017: organization plugin drop (case γ、2026-04-23)

翌日の話だ。schema 診断セッションで、Better Auth の `organization` plugin 由来の table 群がほぼ未参照だと分かった。

- `organization` table — member list 表示 / 組織切替 UI 未実装、insert は signup 時の default org 作成のみ
- `member` table — member check 未実装、select ゼロ
- `invitation` table — 招待フロー UI / API 未実装、insert/select ゼロ
- `session.active_organization_id` column — lookup クエリ未実装、write のみ

加えて ADR-013 で **open signup** を採択していた。誰でも `/signup` から Magic Link を取得して user record が作れる、という前提だ。これと「member 未チェック」が組み合わさると、構造的に次のことが言える。

> open signup + member 未チェック = signup した user 全員が default org のデータにアクセスできる

これは tenant isolation が無い状態だ。ただし 5/1 までに外部パートナー招待予定はゼロ ── クライアント 1 社のみ、僕と同僚レビュアーと数名のチームで使う想定。Phase 1 で組織境界を作り込む pain は具体化していなかった。

選択肢は再び α/β/γ で整理した。

- 案 α: Better Auth 正統化 (member check 実装 + 組織切替 UI + 招待 flow 完全実装)
- 案 β: 自前 member check 最小移行 (organization table 残し、API route で organization_id 突合)
- 案 γ: organization plugin 完全削除 (schema / plugin config / activeOrganizationId すべて削除)

僕は **案 γ** を選んだ。pain 未具体化 + 5/1 deadline タイト + 「未使用 plugin を残すと『後で考える』で先送りされ続ける、削除することで次に具体化した時に正面から設計できる」という哲学的判断だ。「今のスコープ外の問いは今解かない」 という考え方を僕は持っている。組織境界問題は「そもそも何を作るべきだったか」のスコープ外の問いだった。

外部パートナー招待が具体化した段階で **案 α (Better Auth 正統化) に昇格する余地を残す** と ADR に書いた。「migration + plugin 再追加 + UI 実装で 1-2 週間規模の工事になる想定」と但し書きを付けて。pain が来たらやればいい、と思った。

---

## ADR-026: membership pattern で 017 を supersede (2026-04-29)

8 日後、その「pain」が来た。

5/1 launch 直前の dogfooding で、同僚レビュアーから次の FB が飛んできた。

> 「(c) 登録さえすれば誰でも見れる(私用アドレスでクライアント画面ログイン)」

具体的には:

- 旧挙動: signup form は任意 email を受け付ける、`better-auth.ts` の hook で email ドメインから `role` を自動付与するが、**signup 自体は誰でも可能**
- 結果: `@gmail.com` / `@yahoo.co.jp` 等の私用 email で signup → user 作成成功 → role=client → クライアント画面が見える
- 影響: クライアントの業務 review 内容 / レギュレーション CSV / 通知設定 等が外部漏洩

ADR-017 の前提が崩れた。「5/1 までに外部パートナー招待予定なし」は守られていたが、「全員が無条件で signup 可能」は許容できないと顕在化した。

ここで僕が選んだのは **membership-minimum pattern** だった。重い 3 table (organization / member / invitation) を再導入するのは scope 過大だが、最小限の `memberships` table (組織 × user の関係を表す 1 行) と `requireMembership()` helper だけで認可境界を構造的に引く ── ADR-017 で削除した plugin を呼び戻すのではなく、自前の薄い layer で代替する選択肢だ。

```typescript
// auth-helpers.ts (抜粋)
export async function requireMembership(req: Request) {
  const user = await getCurrentUser(req);
  const ms = await db.select()
    .from(memberships)
    .where(eq(memberships.userId, user.id));
  if (ms.length === 0) throw new HTTPException(403);
  return { user, memberships: ms };
}
```

既存 `requireRole()` を全 API route で `requireMembership()` に置き換えて、認可されない user (orphan) は 403 で弾く。membership 付与は admin role を持つ管理者が `/memberships` UI で明示的に行う。member 一覧は単一の組織に集約、判断は admin の手元に集める。

最初の Phase 1 設計では、signup hook で「許可 domain の user は AIFUL org に自動 add」というロジックを入れていた。ところが launch 直前 (T-5h) で僕の判断が変わった。

> 「invitation 機能は不要である」
> 「メンバー管理機能にアクセスできるのは admin ロールを持っているユーザのみにする」
> 「自動でメンバーに追加しない」
> 「メンバー管理を行う機能を作る想定である」

auto-add を廃止して、`/memberships` UI 経由で明示的に admin が付与する flow に切り替えた。Phase 1.5 と命名して同じ branch に追加 commit した。「翻訳を迂回しない」 という考え方を自社プロジェクトでは大事にしている。「誰を入れるか」の判断は admin の value add そのもので、自動追加で迂回するとそれが消える。

membership pattern が完成すると、認可の真の境界が `requireMembership()` 一点に絞られた。signup がどうあれ、orphan user は実データに到達不能になる。これが 2 日後の判断 (ADR-028) を可能にした。

---

## ADR-028: 5/1 launch 直前 UAT で消した Magic Link (2026-05-01)

5/1 launch 前日の 20:49、同僚レビュアーから別の FB が来た。

> 個人的にはログイン画面が 2 種類ある理由がよく分かっておらず、あれらはどういった違いがあるものになりますでしょうか？
> 同じくメールアドレスを使うなら、パスワードがある方だけで良い気がしていまして...

ADR-015 で β (両対応) を採択した時、僕は「両対応の UI 複雑化はトレードオフ」として受容していた。method tab UI が `password` と `magic-link` を切り替える ── あれだ。僕はその tab に慣れていて、外部パートナーも「使い分けの value」を理解してくれると無自覚に思っていた。

3 分後、僕は返答した。

> 「メールでログインリンク」のやつですかね？
> あれば便利かなと思って入れただけで特に深い理由はないので不要であれば消します！

「便利かなと思って入れただけで特に深い理由はない」── 振り返るとこの一文が全部だった。Magic Link は将来昇格させる余地として残したつもりだったが、9 日経った時点で本活用される pain は見えていなかった。Resend は自社の production ドメインで本番化済、僕自身も password 経路で運用中、Magic Link 経由の active session はゼロ。「便利かな」で入れた要素が、外部パートナーから見て「2 種類ある理由が分からない、ユーザーが迷う」という具体的 pain として返ってきた。

翌朝 10:25 に同僚レビュアーから「ユーザーが迷いそうなので、こちら削除で大丈夫です！」と明示的合意が来て、10:52 に僕は「承知しました！」と返した。ここから ADR-028 の起票が始まった。

ADR-015 当時の α 却下理由 2 つを再点検した。

| 当時の却下理由 | 2026-05-01 時点の状況 |
|---|---|
| 僕の既存 Magic Link session (7 日 valid) を無効化 | session は既に expire 済 (9 日経過)。permission 経路で運用中 |
| Magic Link を本活用できる余地を残す | Resend 本番化は完了したが、Magic Link を「便利だから入れた」域から昇格させる pain が見えない |

両方とも消滅 or 弱体化していた。α 採択を阻む構造的障壁はもう無い。

実装は 1 PR で完結した。

- `signin` / `signup` page の method tab UI / `Method` state / `MethodTab` component を削除
- `MagicLinkForm` component ファイル削除
- `lib/better-auth.ts` の `magicLink` plugin import / `sendMagicLinkEmail` 関数 / `Resend` import 削除 (ただし Resend 本体は通知メール経路 `lib/email.ts` で継続使用)
- `lib/auth-client.ts` の `magicLinkClient` plugin 削除
- E2E test の Magic Link 経路 4 test を password 経路に rewrite、tab 切替 spec 削除、`helpers/magic-link.ts` 削除

Better Auth が plugin 削除で `/api/auth/magic-link/*` endpoint を自動 reject するので、明示的な route 削除は不要だった。これは plugin 構造の柔軟性そのものだ。**plugin を外せば endpoint も消える** ── attack surface が削減される。Clerk のような SaaS だと「ダッシュボードで Magic Link を disable する」操作になり、コード差分として残らない。

ADR-026 (membership-minimum) と本 ADR-028 が完全に独立な点も書いておきたい。signup / signin 経路がどうあれ、orphan user は `requireMembership()` 経由 403 で弾かれて、admin が `/memberships` UI で明示付与する flow は変わらない。**認可境界が membership 一点に絞られていたから、Magic Link を消すという認証 UX の判断が独立に下せた**。レイヤーが綺麗に分離されていた。

YAGNI(今やらなくていいことは今やらない) を自社プロジェクトでは大事にしている。Magic Link は当日必要な機能じゃなかった。9 日後に消すまでの間、機能は存在していたが実用される機会はほとんど来なかった。

---

## 副作用: orphan user の復旧 (2026-05-01 同日)

同じ日に予期しない発見があった。**Magic Link plugin で signup された user は `account` 行が作成されない**。Better Auth の仕様だ。

ADR-028 採択時、僕は「Magic Link 経由 signup user は僕 1 名のみ (既に password 経路へ切替済)」と把握していた。だが同日中に、同僚レビュアーと別の dev チームメンバーの 2 名が `account` 行ゼロ (=password 未設定 = signin 不能) であることが判明した。

検出 SQL はこう書いた。

```sql
SELECT
  u.id AS user_id,
  u.email,
  u.created_at,
  COUNT(a.id) FILTER (WHERE a.provider_id = 'credential') AS has_credential,
  COUNT(a.id) AS account_count
FROM "user" u
LEFT JOIN "account" a ON a.user_id = u.id
WHERE u.email IN ('XXX@example.com', 'YYY@example.com')
GROUP BY u.id, u.email, u.created_at;
```

`account_count` と `has_credential` が両方 `0` の user が orphan だ。Magic Link plugin 削除済で、verification email 経由の自動復旧は不可能。password reset (forgot-password flow) も credential account 行が無いと初期 hash を当てる対象が無い。**`account` 行を admin で直接 INSERT する以外の path は構造的に存在しない**。

復旧には Better Auth の internal hash 関数を直接呼ぶ必要があった。

```js
// .tmp-hash.mjs (gitignored、生成後 rm)
import { hashPassword } from "better-auth/crypto";
const password = process.argv[2];
const hash = await hashPassword(password);
console.log(hash);
```

`scrypt`-based の hash で、Better Auth の forgot-password flow / credential signin と完全互換だ。出力は `salt:hash` 形式の hex 文字列。これを `account` table に直接 INSERT する。

```sql
INSERT INTO "account" (
  id,
  account_id,
  provider_id,
  user_id,
  password,
  created_at,
  updated_at
)
VALUES (
  gen_random_uuid(),
  '<user_id>',           -- account_id = user_id (Better Auth の credential 慣習)
  'credential',
  '<user_id>',
  '<scrypt_hash>',       -- 'salt:hash' hex
  NOW(),
  NOW()
);
```

ここで一手間ハマった。production main DB に INSERT を流しても、**既存 PR の preview branch には反映されない**。Neon-Vercel Native Integration の preview branch は branch 作成時点の main snapshot copy で、後の main 変更は伝搬しない仕様だ ── `parent_timestamp` field で snapshot 時刻が visible になっており、main INSERT の時刻が parent_timestamp の後だと反映されない。orphan user 2 名のうち 1 名は preview branch の作成時刻が main INSERT より早かったため、該当 PR を UAT 中の dev member が復旧 user で signin できない事態が起きた。

→ **production main + 該当する全 open PR の preview ephemeral branch、両方に個別 INSERT** が必要になった。Vercel preview deployment の env tab か、Neon Console の該当 branch の connection string で `DATABASE_URL` を切替えながら同じ SQL を順次流す。手順を `.claude/rules/magic-link-orphan-recovery.md` に永続化した ── 同じ罠を 2 度は踏みたくない。

復旧後、temp password を Slack DM で本人に通知して、本人が forgot-password flow で自分の password に変更して終わり。Magic Link plugin を消した日に、Magic Link plugin が残した 2 つの孤児を救出する作業をしていた。皮肉だが、`account` 行が作られないという仕様を 9 日間気づかず使っていた事実そのものが、認証選定の発見だった。

---

## 6 ADR を貫く 2 哲学

9 日間の動きを支えていた哲学が 2 つある。

**1 つ目**: YAGNI(今やらなくていいことは今やらない)。

ADR-013 で organization plugin を「将来昇格余地」として残した。ADR-015 で Magic Link を「将来本活用余地」として残した。どちらも「pain が具体化したらやる」という前提だ。9 日後、organization plugin は ADR-026 で部分復活したが (membership-minimum)、Magic Link は ADR-028 で完全削除になった。**pain 駆動で削除する**判断が両方できたのは、最初から「将来余地」と「現時点の運用」を分離していたからだ。pain が見えていない要素を「念のため残す」と、それが 9 日後に「便利かな」のまま残り続ける ── 削除するという選択肢自体が消える。

**2 つ目**: α/β/γ pattern による時系列での動的判断。

| ADR | 案 | 採択 | 状態 |
|---|---|---|---|
| ADR-015 | β (Magic Link + Password 両対応) | 4/22 | Superseded by ADR-028 |
| ADR-017 | γ (organization plugin 削除) | 4/23 | Superseded by ADR-026 |
| ADR-026 | α (membership-minimum 自前実装) | 4/29 | Accepted |
| ADR-028 | α (Magic Link 廃止) | 5/1 | Accepted |

α/β/γ は同じ問題に対する大工事 / 中規模 / 保留の 3 段階だ。**pain 具体化度** + **scope** + **deadline 整合**の 3 軸で時系列で動的に決まる。ADR-015 で β を採った時の僕と、ADR-028 で α を採った時の僕は、同じ 1 人だ。だが 9 日間の運用と外部パートナーの FB で、判断軸の値が変わった。判断は時間をかけて熟成するもの、と自社プロジェクトでは捉えている。最初から正解が出せるわけじゃない。動かして、痛みが見えて、構造が変わる。

OSS lib (Better Auth) はこの動き方に耐える。plugin の add / remove で構造が動的に変わる柔軟性、自前 schema と auth lib の境界が `auth.ts` に集約される明示性、エージェントが Read で全構造を把握できる透明性。SaaS 認証 (Clerk 等) では「ダッシュボードを開いて Magic Link を disable」となり、コード差分として残らない。9 日後に消す判断を ADR として残す習慣も、コードベースに痕跡を残す Plugin 削除も、SaaS だと別の workflow になる。

---

## おわりに

認証 layer を 9 日で 6 ADR 動かした話を書いた。

要点を 3 つに絞る。

1. **OSS lib は plugin の add / remove で構造が動的に変わる**。Magic Link を入れた 9 日後に消すような判断密度で動ける。SaaS 認証 (Clerk 等) では同じ動き方ができない ── ダッシュボードで disable しても、コード差分として残らない、認証選定が後から振り返れない、エージェントから debug 不可能という 3 重のコストがある。

2. **α/β/γ pattern は「pain 未具体化なら γ (保留)、具体化なら α / β」を時系列で動的に判断する frame**。最初から正解を出さない。動かして、外部パートナーの FB を浴びて、判断軸の値が変わる前提で、判断履歴を ADR として残す。

3. **Magic Link plugin で signup された user は `account` 行が作成されない**。削除後は admin の手動 fix (account 行 INSERT + scrypt hash 直書き) が唯一の復旧 path で、production main + 既存 preview branches 両方への個別 INSERT が必要 (Neon-Vercel Native Integration の preview branch 仕様)。同じ罠を 2 度踏まない仕組みとして rules ファイルに手順を永続化した。

僕は 1 年間 Claude Code を運用していて、`.claude/` ディレクトリに 100+ Skills と 34,000+ memory entries を持っている。その上で動く認証 layer が、9 日で 6 回変わるという速度に耐えた事実が、この記事で残したかったことだ。**判断密度を圧縮するのは、認証 lib の選定から始まる**。コードベースに留まる OSS lib を選んだ瞬間に、後で消せる自由が残る。

組織や運用が変わっても、Better Auth の `auth.ts` は手元にあって、plugin を 1 つ抜くだけで挙動が変わる。これは SaaS 認証では手に入らない構造だ。

---

## 関連

- 私の関連記事(Zenn):
  - [ハーネスエンジニアリング入門 — CLAUDE.md 0 行から 420 ファイルまでの 8 ヶ月](#)
  - [エージェント駆動の B2B SaaS スタック選定 — 28 ADR の俯瞰](#)
  - [Drizzle + Neon MCP で PR ごとに ephemeral branch を回す DB layer](#)
- Better Auth 公式: https://www.better-auth.com/
- Auth.js → Better Auth 移譲アナウンス: https://github.com/nextauthjs/next-auth/discussions/13252
