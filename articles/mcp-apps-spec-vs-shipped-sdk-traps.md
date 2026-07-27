---
title: "MCP Apps を仕様書どおりに書いたら動かなかった ── 2 ホストで描画するまでに踏んだ罠 4 件"
emoji: "🧩"
type: "tech"
topics: ["mcp", "claudecode", "typescript", "aiagent"]
published: false
---

チャットの中に自分のツールの画面を出せる、という話を聞いて、実際に書いてみました。

結論から 3 行で書きます。

- **MCP Apps は「これから来るもの」ではありません。** 2026-01-26 に MCP 初の公式拡張として出荷済みで、今日ローカルで動きます
- **仕様ドラフトの本文どおりに書くと動きません。** 出荷されている SDK の型と食い違っています
- **Claude Code(CLI)はホスト未対応です。** バイナリを走査して確かめました

以下は、Factory のライン一覧を出すパネルを 1 個作って、2 つのホストで描画するまでのログです。踏んだ罠を全部書きます。

## そもそも今どこにあるのか

きっかけは [2026-07-28 の RC 告知](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)でした。ここに MCP Apps が載っていたので「RC の新機能か」と思ったのですが、違いました。

- 2025-11-21 に SEP-1865 として提案
- **2026-01-26 に MCP 初の公式拡張として一般提供開始**([告知](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/))
- [SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp) の Status は既に **Final**

インストールした SDK の `LATEST_PROTOCOL_VERSION` も `"2026-01-26"` でした。つまり半年前から出荷されています。

**ホスト側の対応状況**は、自分で確かめたものと告知ベースのものを分けるとこうなります。

| ホスト | 描画 | 根拠 |
|---|---|---|
| MCP Inspector v1.0.0 | **対応** | 自分で起動して描画・スクショ取得 |
| ext-apps basic-host(参照実装) | **対応** | 自分でビルドして描画・スクショ取得 |
| **Claude Code CLI 2.1.219** | **未対応** | 実バイナリの文字列走査(後述) |
| claude.ai(Web) / Claude Desktop | 対応と告知 | 公式ブログ |
| Goose / VS Code Insiders / ChatGPT | 対応と告知 | 公式ブログ |

上 3 行が自分で動かして確かめたもの、下 2 行は告知を読んだだけです。この区別を混ぜると、後で自分が困ります。

**書くなら SDK は `@modelcontextprotocol/ext-apps`(1.7.5)** です。コミュニティ先行実装の `@mcp-ui/server` は SEP-1865 の母体として歴史的に重要ですが、公式化後は ext-apps が本線で、更新も 2 月で止まっています。今から新規に書く理由はありません。

## 作ったもの

`factory/lines/*.json` を読んで、ライン名・チケット・結論の有無・成果物数を一覧表示するだけのパネルです。

```
lines.mjs          — ライン読み取り
build-server.mjs   — MCP サーバ本体(トランスポート非依存)
server.mjs         — stdio 版
server-http.mjs    — Streamable HTTP 版(ホストが繋ぐのはこちら)
panel.html         — 配信する UI(自己完結 HTML)
smoke.mjs          — プロトコル検証
```

プロトコルが正しく流れているかは、ホストなしで検証できます。`smoke.mjs` の出力がこれです。

```
PASS  initialize → {"name":"factory-lines","version":"0.1.0"}
PASS  tools/list に UI メタが載る → _meta={"ui":{"resourceUri":"ui://factory/lines.html","visibility":["model","app"]}}
PASS  resources/list に ui:// がある → {"uri":"ui://factory/lines.html","mimeType":"text/html;profile=mcp-app"}
PASS  mimeType が MCP Apps 用 → text/html;profile=mcp-app
PASS  resources/read が HTML を返す → 6635 bytes
PASS  tools/call が structuredContent を返す → 27 lines / open 16 / concluded 11
PASS  テキストフォールバックがある → 27 ライン(進行中 16 / 結論あり 11)
```

**ホストを立ち上げる前にここまで確かめられる**ので、描画が出ないときに「プロトコルの問題か、ホストの問題か」を切り分けられます。最初にこれを書いておくと後が楽でした。

## 罠 1: 仕様ドラフトの本文と、出荷済み SDK の型が食い違う

いちばん時間を溶かしたのがこれです。

[仕様ドラフト](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx)の `ui/initialize` の例には `clientInfo` と `capabilities` が書かれています。そのとおりに実装したら、こう返ってきました。

```
{"code":-32603,"message":"...expected: object, code: invalid_type, path: [params, appInfo] ... Invalid input"}
```

出荷されている `@modelcontextprotocol/ext-apps` 1.7.5 が要求するのは `appInfo` / `appCapabilities` / `protocolVersion` の 3 つでした。

```ts
// dist/src/spec.types.d.ts より(出荷物の型が正)
export interface McpUiInitializeRequest {
    method: "ui/initialize";
    params: {
        appInfo: Implementation;
        appCapabilities: McpUiAppCapabilities;
        protocolVersion: string;
    };
}
```

`clientInfo` を送ると弾かれます。**仕様書の本文より、インストールした SDK の `.d.ts` と `generated/schema.json` が正**でした。

この手の罠は「ドキュメントの要約を信じずに raw を見ろ」という話としてよく語られますが、今回は**仕様書そのものが raw ではなかった**という形で出ました。ドラフト段階の仕様と出荷物にはズレがあるという、当たり前だけど忘れがちな話です。

## 罠 2: 2 つのホストとも、UI 拡張を宣言せずに描画してくる

仕様には「拡張は `io.modelcontextprotocol/ui` で明示的にネゴシエートされなければならない」と書いてあります。素直に読むと、**クライアントが宣言してきたときだけ UI ツールを出す**サーバ実装になります。

サーバ側で受信した `initialize` を全部記録してみました。

```
MCP Apps Host      v1.0.0   ui-ext=no   caps_keys=[]
inspector-client   v1.0.0   ui-ext=no   caps_keys=['elicitation', 'roots', 'sampling', 'tasks']
```

**どちらも宣言していません。** それでも描画されます。両者ともツールの `_meta.ui.resourceUri` を見て動いていました。

つまり、**仕様どおりに capability でゲートするサーバを書くと、この 2 ホストでは何も出ません。** 現時点ではゲートを厳密にしないほうが安全です。

ただしこれは「この 2 ホストのこのバージョンでの観測」であって、他ホストは確かめていません。そしてホスト側が仕様準拠を強めた瞬間に、この判断は逆転します。

## 罠 3: `express.sendFile` はパスにドット始まりのディレクトリがあると 404 になる

参照ホストを `~/.claude/jobs/...` の下に clone したら、本家の `examples/basic-host/serve.ts` が `dist/sandbox.html` を 404 で返し続けました。

原因は `send` の `dotfiles: "ignore"` 既定です。**パスの途中に `.claude` というセグメントがあるだけで反応します。** ファイルは存在するのに `NotFoundError` になるので、原因が見えません。

`readFileSync` + `res.send` に書き換えて回避しました。Claude Code のワークツリーも `.claude/worktrees/...` の下に作られるので、静的配信を伴う試作をすると同じ罠を踏みます。

## 罠 4: サンプルはルートの `npm run build` だけでは動かない

`npm install && npm run build` は SDK をビルドするだけで、`examples/basic-host/dist` は作られません。

```bash
INPUT=index.html npx vite build
INPUT=sandbox.html npx vite build
```

を個別に走らせる必要があります。`INPUT` を設定しないと `vite.config.ts` が例外を投げます。`npm start` は bun 依存です。

## Claude Code(CLI)は今日は無理

ここがいちばん知りたかったところです。普段使っている CLI セッションの中にパネルを出せるのか。

実行中の Claude Code 本体(`2.1.219`、Mach-O arm64、257MB)を文字列走査しました。

| 文字列 | 出現数 |
|---|---|
| `io.modelcontextprotocol/ui` | **0** |
| `text/html;profile=mcp-app` | **0** |
| `ui/resourceUri` | **0** |
| `ui/initialize` | **0** |
| (対照)`resources/read` | 9 |
| (対照)`tools/call` | 18 |
| (対照)`elicitation` | 163 |
| (対照)`notifications/initialized` | 9 |

`mcp-app` に 4 件ヒットしますが、中身は `mcp-approval-persist-failed` 等のテレメトリ文字列で無関係でした。

**対照群の標準 MCP メソッド名は素直に文字列として埋まっている**のに、MCP Apps のマーカーだけが 1 つもありません。ホスト実装を持っていないと判断してよさそうです。公式のローンチ告知でも、対応ホストは Claude の web / desktop であって CLI は挙がっていません。

手法の限界も書いておくと、難読化・分割された文字列は走査に掛かりません。ただし対照が素直に出ている以上、この結論はかなり堅いはずです。

## ついでに: 手持ちの MCP サーバに UI 配信はあるか

自分が常用しているサーバが既に UI を返しているなら、書かなくてもいい話です。プローブスクリプトを書いて 11 件当たりました。

`io.modelcontextprotocol/ui` を**宣言した状態で**接続して(サーバが「UI 対応クライアントにだけ UI を出す」実装でも拾えるように)、3 点を見ています。

1. `tools/list` の各ツールの `_meta` に `ui.resourceUri` があるか
2. `resources/list` に `ui://` スキームがあるか
3. `initialize` の応答 capability に UI 拡張があるか

```
playwright (pw)    ❌ UI 配信なし | tools=24 resources=非対応 uiTools=0 uiRes=0
context7           ❌ UI 配信なし | tools=2  resources=0      uiTools=0 uiRes=0
linear             ❓ 判定不能 — 401 認証が必要
sentry / vercel / github / neon / tactiq ほか  ❓ 判定不能 — 401
```

**確定的に「なし」と言えたのは 2 件、残りは認証壁で到達できませんでした。** ここは「対応していない」ではなく「確かめられなかった」です。

Linear だけは認証済みの接続があるので、Linear 自身のドキュメント検索ツールで公式ドキュメント 54KB を引いて数えました。

| 語 | 出現数 |
|---|---|
| `MCP Apps` | **0** |
| `ui://` | **0** |
| `widget` | **0** |
| `SEP-1865` | **0** |
| (対照)`MCP server` | 20 |
| (対照)`OAuth` | 8 |

MCP サーバの説明は充実しているのに、UI 系の語が 1 つもありません。可能性は高いですが、**記載がないことは非対応の証明ではない**ので断定はしません。

### なぜ 0 件なのか

構造的な理由がありそうです。MCP Apps のローンチパートナー 9 社は **Amplitude / Asana / Box / Canva / Clay / Figma / Hex / monday.com / Slack**。

僕が常用しているのは **Linear / Sentry / Neon / Vercel / GitHub / BigQuery / Playwright / context7** です。**1 社も重なっていません。**

MCP Apps が今刺さっているのは「業務 SaaS の画面をチャットに出す」領域です。デザインファイルを編集する、タスクをドラッグする、ダッシュボードを描く。一方で開発インフラ系は、**出力が構造化テキストで足りてしまう**のでツール側に UI を付ける動機が弱い。この非重複は偶然ではなく、当面続くと見るのが自然だと思っています。

### 検索結果に注意

「Sentry / Vercel / Neon / GitHub の MCP Apps 対応」を検索すると、**「これらは全て対話的ウィジェットに対応している」という趣旨の要約が返ってくることがありますが、誤りです。**

リンク先の実体は [vercel-labs/mcp-apps-nextjs-starter](https://github.com/vercel-labs/mcp-apps-nextjs-starter)、つまり **Vercel が「MCP Apps を作るためのテンプレート」を配っている**という話でした。「MCP Apps を作れる基盤を出している」ことと「自社の MCP サーバが UI を返す」ことは別です。

## 今日できること / 待つべきこと

**今日できること。** MCP Apps サーバを書いて、ローカルで描画しながら開発するところまでは普通に回ります。`node server-http.mjs` を上げて MCP Inspector の Apps タブに繋げば、編集してリロードのループが回ります。

**待つべきこと。** Claude Code(CLI)でのパネル表示です。ホストが対応していないので、今日はどうやっても出ません。

そのうえで、僕が選んだ落としどころを 1 つだけ書いておきます。

**今は MCP Apps に移さず、`panel.html` の形の自己完結 HTML を 1 枚持っておく。** `structuredContent` を渡されたら描画するだけの、外部依存ゼロの HTML です。これなら今すぐ別経路で使えて、Claude Code がホスト対応した日に `registerAppResource` で配信するだけで MCP App になります。二重実装になりません。

## 負け条件

この記事の「待つべきこと」は、**Claude Code が MCP Apps ホスト対応を出した時点で死にます。**

確認日は **2026-10-27**(3 ヶ月後)。確認方法は同じで、`strings -a <claude binary> | grep -c 'io.modelcontextprotocol/ui'` が 1 以上になるかを見るだけです。

同じく、罠 2(ホストが capability を宣言しない)は**ホスト側が仕様準拠を強めた時点で逆転します。** そのときはサーバ側の非ゲート実装のままで問題ないかを見直すことになります。

## 再現手順

```bash
npm install

# プロトコル検証(ホスト不要)
node smoke.mjs

# HTTP サーバを起動
node server-http.mjs           # → http://localhost:3001/mcp

# 別シェル: MCP Inspector で描画確認
DANGEROUSLY_OMIT_AUTH=true npx -y @modelcontextprotocol/inspector@1.0.0
# → http://localhost:6274 で Streamable HTTP / http://localhost:3001/mcp に Connect
# → Apps タブ → list_factory_lines
```

環境は macOS(darwin 25.5.0)、Node v24.2.0、Claude Code 2.1.219 です。

---

一次情報として価値があったのは、**罠 1(仕様書より出荷物の型が正)** と **罠 2(2 ホストとも宣言なしで描画)** の 2 つでした。どちらも仕様書を読むだけでは絶対に出てこず、動かして初めて出ました。

新しいプロトコルの出たての時期は、仕様書と実装のどちらを信じるかで作業時間が変わります。今回に関しては、**インストールした `.d.ts` を正とするのが正解**でした。
