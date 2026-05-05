---
title: "Neon Personal Token の org bind 罠 — /users/me で 30 秒 verify"
emoji: "🔑"
type: "tech"
topics: ["neon", "vercel", "claudecode", "devops", "postgres"]
published: true
---

# Neon Personal Token の org bind 罠 — /users/me で 30 秒 verify

## はじめに

僕は Personal Token を 3 回再生成しても、そのたびに 401 を食らった。

ある B2B SaaS の launch marathon の最中だった。Neon の project を一人 org から会社 org へ transfer したあと、CI に渡している API key を更新しようとした。Neon Console の `Account Settings > Personal Tokens` で新しい token を発行する。それを CI に貼る。叩く。`401`。「あ、貼るところを間違えたかな」と思って、もう一度発行する。貼る。`401`。3 回目を発行する直前で、ようやく「これは token を再発行する問題ではない」と気づいた。

結論を先に書く。Neon の **Personal Token** は、文字どおり「Personal」 ではなかった。**生成時にあなたが居た org context に bind されている**。一人 org にいるときに発行した Personal Token は、別の org に transfer された project にはアクセスできない。何度再発行しても変わらない。なぜなら毎回、現在の org context に bind され直しているだけだからだ。

そして、これは token を貼った瞬間に 30 秒で見抜ける。`/users/me` を一度叩くだけでいい。45 分溶かして気づいた話を書く。

---

## 背景: org migration の落とし穴

僕がやろうとしていたのは、ありふれた作業だった。自社の B2B SaaS の Neon project を、僕個人の一人 org から会社 org に transfer する。Neon Console の Project settings に「Transfer to another organization」 ボタンがあって、ぽちっと押せば数秒で完了する。ここまでは何の問題もなかった。

問題はそのあとだ。CI と本番環境で使っている Neon API key を更新する必要があった。token の有効期限管理を兼ねて、launch のタイミングで rotate する運用にしていた。Neon Console の右上、自分のアバターをクリックすると `Account Settings` が開く。サイドバーに `API keys` があって、`Personal Tokens` のタブがある。ここで `Generate new key` を押すと、`napi_xxxxxxxx` から始まる token が払い出される。これを CI の secret に貼って、本番に流す。Neon を 1 年使っていればこの operation は手の動きで覚えている。

ところが、今回はそれが動かなかった。CI のログには `401 Unauthorized` が並んでいる。最初は「貼り間違いかな」 と思った。secret manager の値を見直す。空白も改行も入っていない。じゃあ token 発行の方が swing したのかと思って、もう一度生成する。貼る。`401`。手元の curl で直接叩いてみる。やはり `401`。

ここで僕がハマったメンタルモデルは、こうだった。

> 「Personal Token = 自分というユーザーに紐付いた token = 自分が member であるすべての org の resource にアクセスできる」

公式 docs にもそう読める書き方がある。Neon の API keys のドキュメントを開くと、「Personal keys: All organization projects where the user is a member」 と書かれている。読み込めば「user が member であるすべての org の project にアクセスできる」 と取れる。少なくとも、僕はそう取った。

このメンタルモデルが正しいなら、token を再発行すれば必ず治るはずだった。同じユーザーが、同じ Personal Tokens 画面で、新しい token を発行しているのだから。なのに 3 回連続で `401` が返ってくる。「Neon の障害かな」 と疑い始めるあたりで、僕はようやく Neon の API error response を verbatim で読み返した。

そこに書いてあったのは、僕のメンタルモデルとは違う世界だった。

---

## API error から判明した bind 構造

Neon の API は、`401` だけを返してくれていたわけではなかった。レスポンスボディに、僕がそれまで読み飛ばしていた fields が並んでいた。整形するとこういう構造だ。

```json
{
  "code": "AUTHORIZATION_DENIED",
  "message": "User does not have access to this project",
  "subject_org_id": "org_solo_xxxxx",
  "requested_org_id": "org_company_yyyyy",
  "requested_permission": "Perm:read"
}
```

`subject_org_id` と `requested_org_id` が違う org を指している。これが何を意味しているか、僕はその場で理解できなかった。なんとなく「あ、たぶん org が絡んでいるのね」 と思って、Neon の docs を再度開いた。検索ボックスに `subject_org_id` を入れる。1 件だけヒットする。そこに書いてあった行を読んだ瞬間、ようやく事態がつながった。

要約するとこうなる。Personal Token は、生成時にあなたが見ている画面の **org context** に bind される。つまり token そのものに「この token は org_solo_xxxxx の view から発行されました」 という seal が押されている。あとから別の org に project が移っても、その seal は変わらない。token を再発行しても、そのとき自分が居る org が org_solo_xxxxx のままなら、新しい token もまた org_solo_xxxxx に bind される。同じ場所で何度発行しても、同じ org に向いた key が量産されるだけだ。

そして僕は、その瞬間まで自分の Neon Console が「どの org context にいるのか」 を意識したことが一度もなかった。一人 org の時代から触っていて、URL bar の breadcrumb もろくに見ていなかった。Neon の Console は左上に org switcher があるのだが、僕の視線はずっと右上のアバターメニューに張り付いていた。Account Settings から token を発行する操作は、画面の右上で完結する。左上の org switcher を切り替えなくても、token はちゃんと発行される。発行された token は、左上で表示されている org に sealed されているのに、右上の操作だけで完結するから誰もそれに気づかない。

「Personal」 と書いてあるから personal だと思って疑わなかった。docs は「user が member の全 org にアクセスできる」 と読める書き方だ。UI も org context を意識させない。三重に騙される構造になっていた。

ここで一番効いたのは、`subject_org_id` という field が response に乗っていたことだった。これがなかったら、僕は今でも token を再発行し続けているかもしれない。Neon は、自分の API contract に「この token は実は org bound です」 という事実をきちんと埋めていた。読み飛ばしていたのは僕の方だった。

---

## `/users/me` 1 行 verify pattern

ここから本題に入る。45 分溶かしたあと、僕が脳に焼き付けた verify pattern を書く。新しい Neon token を発行したら、まず最初に叩くのはこの 1 行だ。

```bash
curl -sS -H "Authorization: Bearer $NEON_TOKEN" "https://console.neon.tech/api/v2/users/me"
```

返ってくるレスポンスは、ふた通りに分岐する。真の personal scope (cross-org でアクセスできる token) なら、user info の JSON が返ってくる。

```json
{
  "id": "user_xxxxx",
  "email": "you@example.com",
  "name": "Takuya Nagai",
  ...
}
```

org-scoped (生成時 org に bound された token) なら、エラーメッセージが返ってくる。Neon の場合はこれだ。

```
{ "code": "FORBIDDEN", "message": "This action is not allowed for organization API keys" }
```

これだけで判別できる。30 秒もかからない。

僕がこの pattern を一度 hit してから、新しい SaaS を触るたびに `/users/me` を最初に叩く癖がついた。Linear、GitHub、Vercel、どこでもいい。token を貼って、最初の動作確認を「自分が誰として認証されたか」 から始める。これは health check なんかじゃない。**token の scope を可視化する作業**だ。

なぜ「30 秒の verify」 が「45 分の浪費」 に勝つのか、 もう少し言語化しておく。

token を貼って実装の API を叩くと、`401` か `403` が返ってきたときに、その原因が token そのものなのか、 endpoint の権限不足なのか、 リクエストの body が間違っているのか、すぐには切り分けられない。再発行で治るかもしれないし、治らないかもしれない。判断保留のまま試行錯誤が始まる。これが一番時間を吸う。

`/users/me` のような自分自身を返す endpoint は、「token が valid なら必ず通る」 性質を持っている。ここで `401` が返れば token は構文 OK でも認証で拒否されている。`403` が返れば token は認証されているが scope が足りない、と即座に切り分けられる。Neon はもっと親切で、`organization API keys` のような org bound 専用エラーを返してくれる。token の scope が一発で見える。

つまり `/users/me` は、token を「実装の文脈」 から切り離して、「scope そのもの」 を試す道具として使える。実装側の bug や権限設計の見落としに引きずられずに、 token 単体の素性を裸で見られる。これが効く。

---

## 対処パターン表

Neon に限らないが、Personal token が org に bind されていたとわかったあと、 状況に応じて対処は枝分かれする。僕が踏んだ枝と、 踏まなかったが docs を読み返して妥当そうな枝を、 まとめておく。

| 状況 | 対処 |
| --- | --- |
| 生成時 org と access 先 org が同じ | そのまま使える、 `/users/me` で念のため確認 |
| 別 org に project を transfer した | **その org の context に切り替えてから token を再生成**(URL bar / breadcrumb で確認) |
| 真に cross-org な token が必要 | docs を読み直し、 SSO / OAuth で cross-org な token type が別途あるか確認、 なければ org ごとに token を分ける運用へ |
| Org settings ページに辿り着けない | URL pattern を試行錯誤、Neon は `/app/{org-id}/settings#api-keys`、`/app/orgs/{org-id}/...` ではない、id ベース URL は service ごとに違う |

僕がやったのは 4 つ目の枝の応用だった。Neon の場合、Account Settings 配下の Personal Tokens では org bound しか発行できない。Org-wide な API key を発行したければ、 **その org の Org settings** に行く必要がある。具体的には `https://console.neon.tech/app/{org-id}/settings#api-keys` のような URL で、org 単位の API keys 画面が開く。ここで発行した key は、その org の中で org-wide に使える。

ここでも罠があった。Neon の Console は、Org settings へのナビゲーションが直感的ではない。サイドバーにも上部にも明示的な link が出ていない。breadcrumb で org を切り替えてから設定アイコンを押す、 という 2 段階を踏む必要がある。僕は最終的に URL を直打ちで辿り着いた。これも `id ベース URL は service ごとに違う` の壁で、 Neon は org スラッグではなく `org_xxxxx` の id をそのまま URL に埋める形だった。

最終的に会社 org の Org-wide key を発行して、CI に貼り直したら、当然のように動いた。45 分の混乱に対して、解決そのものは 2 分で終わる作業だった。

---

## SaaS 横断の同型 risk

ここまで Neon の話をしてきたが、僕がこの記事を書いている本当の理由は別のところにある。Neon だけの問題ではない、 という確信がだんだん強くなってきたからだ。

「Personal」 という表記が、 user 横断 (cross-org) を意味するか、 生成時 org に bind されているかは、 SaaS によって違う。表記から実装挙動を推し量れない。docs に「user が member の全 org にアクセスできる」 と書かれていても、 UI の実装が org context に依存している場合がある。

僕が現時点で確認できた範囲、 および docs を眺めて「同じ罠が潜んでいそう」 と推測した SaaS を表にしておく。

| サービス | docs 表記 | 推測される注意点 |
| --- | --- | --- |
| Neon | Personal API key | UI 上 "Personal Tokens"、 生成時 org bound (本記事で確認) |
| Vercel | Personal Access Token | team scope と user scope の境界が曖昧、 要確認 |
| GitHub | Personal Access Token (classic / fine-grained) | fine-grained は repo / org scope 明示型、 classic は曖昧 |
| Linear | Personal API key | workspace scope に bound |

GitHub の fine-grained PAT は、 scope 設計を強制するという意味で良い実装だ。token を発行する画面で repo と org を明示的に選択させる。発行された token がどこで使えるかが、token そのものに張り付いた仕様として可視化されている。これは正しい方向の設計だ。

逆に Neon のような「Personal という名前だが実は org bound」 という UI は、 docs と実装が合っていない時点で罠になる。多くの場合、 docs はサービスを general 化した抽象的な表現で書かれていて、 UI の挙動はもっと specific だ。この乖離は、 token を発行した人が一人 org にいるうちは顕在化しない。マルチ org 運用に入った瞬間に、 ある日突然牙を剥く。僕が踏んだのはまさにそのパターンだった。

そして、AI agent driven な開発をしている人ほど、 この罠は深く効く。エージェントは「key を再発行すれば治る」 という memory を持っている。`401` が返ってきたら新しい key を作る、 という ループに入りやすい。僕の場合も、 自分が手で 3 回 key を発行したのは、 心のどこかで「2 回目で治らないなら 3 回目で治るはず」 という、 統計的に何の根拠もない期待があったからだ。verify ステップを挟まないと、 このループは無限に回せる。

---

## 早期検知 anchor

最後に、実務で使える anchor を 1 つだけ残す。次の組み合わせが揃ったら、 token の scope を疑え。

- key の構文は OK (例: Neon なら `napi_` prefix がついている、 文字数も合っている)
- それでも `401` / `403` / `permission denied` 系が返る
- `not allowed` / `does not have access` のような **scope を匂わせる文言** がエラーメッセージに含まれる

この 3 つが揃ったら、 token を再発行する前に `/users/me` を 1 回叩く。30 秒で済む。これをやらずに 3 回 key を再発行すると、 僕のように 45 分が消える。差は約 90 倍だ。

「key 再発行で治るかも」 という期待は、 token 発行 UI の操作コストが軽いほど強くなる。Neon の Generate Key ボタンは押すのが楽しい。新しい token が降ってくる感覚が気持ちいい。だからこそ、 そこに verify step が挟まらないと、 ループに吸い込まれる。`/users/me` は、 その軽さに対する重しだ。

---

## おわりに

僕がこの 45 分から学んだのは、 docs を信じすぎないことと、 SaaS UI の implementation gap を前提にすることだった。docs には「user が member の全 org の project にアクセスできる」 と書いてある。読めば嘘ではない。「member の全 org」 から意図して発行された token なら、 そのとおり動くのだろう。問題は、 UI が「自分がどの org context で token を発行しているのか」 を可視化してくれない点にある。docs の真と、 UI が誘導する操作の間に、 たいてい数 step の implementation gap が潜む。

ここを 1 行の verify で塞げる。`/users/me` を最初に叩く。これだけで 45 分が 30 秒になる。Agent-Driven な開発で「key を再発行すれば治る」 ループに陥らないための小さな仕組みでもある。

僕は Claude Code を 1 年運用していて、100+ Skills と 34,000+ memory entries が溜まっている。そのうちの 1 entry が、この `/users/me` verify pattern だ。45 分溶かして得られた entry が、 次の launch では 30 秒で再現される。ハーネスエンジニアリングの果実は、 こういう小さい entry の積み重ねで効いてくる。45 分溶かした未来の自分から、30 秒で抜ける今の自分への手紙、みたいなものだ。

次に新しい SaaS の API key を貼るとき、 まず `/users/me` を叩いてから本実装に入ってほしい。それだけで救われる時間がある。

---

## 関連

私の関連記事(Zenn):

- [ハーネスエンジニアリング入門 — CLAUDE.md 0 行から 420 ファイルまでの 8 ヶ月](https://zenn.dev/takuyanagai0213/articles/harness-engineering-intro-8months) — 本記事の上位概念、ハーネス全体の時系列
- [Drizzle + Neon + Neon MCP で『PR ごとに DB を持つ』開発フロー](https://zenn.dev/takuyanagai0213/articles/drizzle-neon-mcp-branching-per-pr) — Neon 同 stack の DB layer deep dive、本記事の org transfer 背景
- [Vercel Storage を UI ゼロで setup する — Agent-Driven 開発の Storage 自動化パターン](https://zenn.dev/takuyanagai0213/articles/vercel-storage-api-zero-ui) — 同 launch marathon の Storage setup
- [Vercel env を git push なしで production に反映する — PATCH + forceNew redeploy workflow](https://zenn.dev/takuyanagai0213/articles/vercel-env-hot-fix-workflow) — 同 launch marathon の env hot fix
- [Better Auth で B2B SaaS を立てて Magic Link を 9 日後に消すまで](https://zenn.dev/takuyanagai0213/articles/better-auth-magic-link-9days-removal-case) — 認証 layer 6 ADR の時系列
- [Vercel + Neon + Next.js + Drizzle + Better Auth で B2B SaaS を 1 ヶ月で立てた技術選定 — 28 ADR から見える Agent-Driven 開発の主軸](https://zenn.dev/takuyanagai0213/articles/agent-driven-b2b-saas-stack-selection-28-adrs) — 全 stack 俯瞰のメタ flagship
