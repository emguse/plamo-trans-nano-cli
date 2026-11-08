# plamo-trans

A translation CLI using [PLaMo 3 Translate 0.8B GGUF](https://huggingface.co/pfnet/plamo-3-translate-0.8b-GGUF).
It automatically launches `llama serve` (or `llama-server`) and prioritizes the use of GGUF from the HF cache (a snapshot of `refs/main`).

```bash
uv run plamo-trans "会議は来週の月曜日に変更されました。"      # 日⇄英 自動判別
echo "The bank was muddy." | uv run plamo-trans -t ja --form polite --context "雨上がりの川辺"
uv run plamo-trans -f doc.md -o doc.en.md -t en --glossary "管理画面=>dashboard"
uv run plamo-trans -i -t en                                    # REPL（下記参照）
```

Main options: `-t/-s` language, `--form polite|plain` (-t ja only), `--glossary`, `--context`, `--quant`, `--model`,
`--server URL`, `--llama-bin`, `--offline`, `-v`.

## Dialogue Mode (REPL)
Launch with `-i`. **Even with a single-line input, enter a blank line (Enter twice) to confirm**. If multiple lines are pasted, up to that blank line is translated as a single input.

```
> 今日はいい天気です。      ← 入力して Enter
                            ← 空行（Enter）で翻訳開始
The weather is nice today.
```

- Previous translations are carried over as context (consistency of terminology and style).
- Commands written at the beginning of a line are executed immediately without blank lines: `/target LANG` (change target; clear history), `/clear` (clear history), `/quit`.
- Ctrl-D (EOF) also confirms the text currently being entered and exits.
- Since the `>` prompt is output to stderr, piping stdout will only flow the translation results. When piping, separate entries with blank lines.

## Offline Operation
The model always prioritizes using the local HF cache (the snapshot pointed to by `refs/main`).
To avoid downloads on mobile networks, etc.:

```bash
uv run plamo-trans --offline "text"     # または環境変数 HF_HUB_OFFLINE=1
```

- Do not access the network at all. Pass `--offline` to `llama serve` and set `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` to start.
- Specifying quantization not present in the cache (e.g., `--quant Q2_K`) will cause the model to exit with an error instead of downloading.
- `--model PATH` (direct to local GGUF) and `--server URL` (existing server) neither perform cache lookups nor downloads.
- To cache the model in advance, run `hf download pfnet/plamo-3-translate-0.8b-GGUF plamo-3-translate-0.8b-Q4_K_M.gguf` online once.

## License
The model follows the [PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en) (free for non-commercial use, subject to conditions for commercial use).

