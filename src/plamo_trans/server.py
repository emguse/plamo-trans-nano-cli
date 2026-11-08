"""Model resolution (HF cache first) and llama serve lifecycle."""
from __future__ import annotations

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = "pfnet/plamo-3-translate-0.8b-GGUF"
QUANTS = ("Q4_K_M", "Q4_0", "Q3_K_M", "Q2_K")
ALIAS = "plamo-3-translate"


class SetupError(RuntimeError):
    pass


def _hub_cache() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    return home / "hub"


def resolve_model(quant: str, offline: bool = False) -> Path:
    """Prefer the snapshot that refs/main points to (older snapshots may carry a stale chat template)."""
    fname = f"plamo-3-translate-0.8b-{quant}.gguf"
    repo_dir = _hub_cache() / ("models--" + REPO.replace("/", "--"))
    ref = repo_dir / "refs" / "main"
    if ref.is_file():
        p = repo_dir / "snapshots" / ref.read_text().strip() / fname
        if p.exists():
            return p
    if offline:
        raise SetupError(f"{fname} not found in HF cache ({repo_dir}) and --offline is set")
    from huggingface_hub import hf_hub_download

    print(f"downloading {fname} ...", file=sys.stderr)
    return Path(hf_hub_download(REPO, fname))


def find_llama(explicit: str | None = None) -> list[str]:
    """Return the command prefix that runs the server: ['llama','serve'] or ['llama-server']."""
    cands = [explicit, os.environ.get("PLAMO_LLAMA_BIN")]
    for c in cands:
        if c:
            path = shutil.which(c) or (c if Path(c).exists() else None)
            if not path:
                raise SetupError(f"llama binary not found: {c}")
            return _prefix(path)
    for name in ("llama", "llama-server"):
        path = shutil.which(name)
        if path:
            return _prefix(path)
    raise SetupError("`llama` / `llama-server` not found in PATH; use --llama-bin or PLAMO_LLAMA_BIN")


def _prefix(path: str) -> list[str]:
    return [path] if Path(path).name.startswith("llama-server") else [path, "serve"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, cmd_prefix: list[str], model: Path, ctx: int = 16384, verbose: bool = False,
                 offline: bool = False):
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.cmd = cmd_prefix + [
            "-m", str(model), "-c", str(ctx), "--host", "127.0.0.1", "--port", str(self.port),
            "--alias", ALIAS, "--jinja", "--no-prefill-assistant",
        ]
        self.env = None
        if offline:  # never let llama.cpp or huggingface_hub touch the network
            self.cmd.append("--offline")
            self.env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        self.verbose = verbose
        self.proc: subprocess.Popen | None = None

    def start(self, timeout: float = 120) -> None:
        out = None if self.verbose else subprocess.DEVNULL
        self.proc = subprocess.Popen(self.cmd, stdout=out, stderr=out, stdin=subprocess.DEVNULL,
                                     start_new_session=True, env=self.env)
        atexit.register(self.stop)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise SetupError(f"llama server exited early (code {self.proc.returncode}); rerun with --verbose")
            try:
                if httpx.get(self.base_url + "/health", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        self.stop()
        raise SetupError("timed out waiting for llama server")

    def stop(self) -> None:
        p, self.proc = self.proc, None
        if not p or p.poll() is not None:
            return
        try:
            os.killpg(p.pid, signal.SIGTERM)
            p.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
