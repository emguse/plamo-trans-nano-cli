# plamo-trans

A translation CLI using [PLaMo 3 Translate 0.8B GGUF](https://huggingface.co/pfnet/plamo-3-translate-0.8b-GGUF).

> [!IMPORTANT]
> The model is provided under the [PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en). **Non-commercial use is free, but commercial use is subject to conditions (registration, licensing, etc.).** Please be sure to review the license terms before use.

Automatically launches `llama serve` (or `llama-server`) and prioritizes the use of GGUF from the HF cache (a snapshot of `refs/main`).

```bash
uv run plamo-trans "会議は来週の月曜日に変更されました。"      # 日⇄英 自動判別
echo "The bank was muddy." | uv run plamo-trans -t ja --form polite --context "雨上がりの川辺"
uv run plamo-trans -f doc.md -o doc.en.md -t en --glossary "管理画面=>dashboard"
uv run plamo-trans -i -t en                                    # REPL（下記参照）
```

Main options: `-t/-s` language, `--form polite|plain` (-t ja only), `--glossary`, `--context`, `--quant`, `--model`,
`--server URL`, `--llama-bin`, `--offline`, `-v`.

## Dialogue Mode (REPL)
Launch with `-i`. **Even with a single-line input, enter a blank line (Enter twice) to confirm.** If multiple lines are pasted, up to that blank line is translated as a single input.

```
> 今日はいい天気です。      ← 入力して Enter
                            ← 空行（Enter）で翻訳開始
The weather is nice today.
```

- Previous translations are carried over as context (consistency of terminology and style).
- Commands written at the beginning of a line are executed immediately without blank lines: `/target LANG` (changes the target; clears history), `/clear` (clears history), `/quit`.
- On the terminal, readline operations such as ←/→ (in-line editing), ↑/↓ (input history), and Home/End are available. Up to 1,000 lines of history are saved to `~/.local/state/plamo-trans/history` (priority given to `XDG_STATE_HOME`).
- Ctrl-D (EOF) also confirms the text being entered and exits.
- Since the prompt `>` is output to stderr, piping stdout will only flow the translation results. When piping, separate each input line with a blank line.

## Input Safety Measures
- Each request is limited to 30,000 characters (if exceeded, use `-f` for split translation). stdin / files are limited to 2 million characters.
- An error occurs if the body text, `--context`, or `--glossary` contains PLaMo reserved tokens (special tokens starting with `<|plamo`).
- When outputting to the terminal, remove control characters (such as ESC). Output is output as-is to files (`-o`) and pipes.

## Offline Behavior
The model always prioritizes using the local HF cache (the snapshot pointed to by `refs/main`).
If you wish to avoid downloading via mobile networks, etc.:

```bash
uv run plamo-trans --offline "text"     # または環境変数 HF_HUB_OFFLINE=1
```

- Do not access the network at all. Start `llama serve` by passing `--offline` and setting `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`.
- If quantization not present in the cache (e.g., `--quant Q2_K`) is specified, the model will exit with an error without downloading.
- `--model PATH` (direct local GGUF) and `--server URL` (existing server) neither perform cache lookup nor download.
- To cache the model in advance, run `hf download pfnet/plamo-3-translate-0.8b-GGUF plamo-3-translate-0.8b-Q4_K_M.gguf` online once.

## License
The model follows the [PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en) (free for non-commercial use, subject to conditions for commercial use).

