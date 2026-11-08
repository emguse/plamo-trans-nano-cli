# plamo-trans

[PLaMo 3 Translate 0.8B GGUF](https://huggingface.co/pfnet/plamo-3-translate-0.8b-GGUF) を使う翻訳CLI。

> [!IMPORTANT]
> モデルは [PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en) で提供されています。**非商用利用は無料ですが、商用利用には条件（登録・ライセンス等）があります。** 利用前に必ずライセンス本文を確認してください。

`llama serve`（または `llama-server`）を自動起動し、HF キャッシュ（`refs/main` の snapshot）のGGUFを優先利用します。

```bash
uv run plamo-trans "会議は来週の月曜日に変更されました。"      # 日⇄英 自動判別
echo "The bank was muddy." | uv run plamo-trans -t ja --form polite --context "雨上がりの川辺"
uv run plamo-trans -f doc.md -o doc.en.md -t en --glossary "管理画面=>dashboard"
uv run plamo-trans -i -t en                                    # REPL（下記参照）
```

主なオプション: `-t/-s` 言語, `--form polite|plain`(-t ja のみ), `--glossary`, `--context`, `--quant`, `--model`,
`--server URL`, `--llama-bin`, `--offline`, `-v`。

## 対話モード (REPL)
`-i` で起動します。**1行だけの入力でも、空行（Enter を2回）を入れて確定**してください。複数行をペーストした場合は、空行までを1つの入力として翻訳します。

```
> 今日はいい天気です。      ← 入力して Enter
                            ← 空行（Enter）で翻訳開始
The weather is nice today.
```

- 直前までの翻訳を文脈として引き継ぎます（用語・文体の一貫性）。
- コマンドは行頭に書くと空行なしで即実行されます: `/target LANG`（翻訳先を変更。履歴もクリア）、`/clear`（履歴クリア）、`/quit`。
- 端末では ←/→（行内編集）、↑/↓（入力履歴）、Home/End などの readline 操作が使えます。履歴は `~/.local/state/plamo-trans/history`（`XDG_STATE_HOME` 優先）に最大1000行保存されます。
- Ctrl-D（EOF）でも入力中のテキストを確定し、終了します。
- プロンプト `> ` は stderr に出るため、stdout をパイプしても翻訳結果だけが流れます。パイプで入力する場合も、入力同士を空行で区切ってください。

## 入力の安全対策
- 1回のリクエストは 30,000 文字まで（超える場合は `-f` で分割翻訳）。stdin / ファイルは 200 万文字まで。
- 本文・`--context`・`--glossary` にPLaMo の予約トークン（`<|plamo` で始まる特殊トークン）を含むとエラー。
- 端末へ出力するときは制御文字（ESC など）を除去します。ファイル（`-o`）やパイプへはそのまま出力します。

## オフライン動作
モデルは常にローカルの HF キャッシュ（`refs/main` が指す snapshot）を優先して使います。
モバイル回線などでダウンロードを避けたい場合:

```bash
uv run plamo-trans --offline "text"     # または環境変数 HF_HUB_OFFLINE=1
```

- ネットワークに一切アクセスしません。`llama serve` にも `--offline` を渡し、`HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` を設定して起動します。
- キャッシュに無い量子化（例: `--quant Q2_K`）を指定するとダウンロードせずエラーで終了します。
- `--model PATH`（ローカルGGUF直指定）と `--server URL`（既存サーバー）はキャッシュ探索もダウンロードもしません。
- 事前にキャッシュしておくには、オンラインで一度 `hf download pfnet/plamo-3-translate-0.8b-GGUF plamo-3-translate-0.8b-Q4_K_M.gguf` を実行します。

## ライセンス
モデルは [PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en)（非商用は無料、商用は条件あり）。
