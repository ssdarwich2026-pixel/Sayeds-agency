"""P15 FIXER — the fix loop (SPEC.md).

INTENT packet + failing tests in -> investigate -> backend proposes
a unified diff -> apply inside a git checkpoint -> re-run tests ->
loop or stop -> honest report. A fix is FIXED only when the project's
own tests pass. A run that never passes restores the workdir to its
checkpoint and keeps the last diff in the report — nothing half-fixed
is ever left behind or claimed.

Usage:
  python3 fixer.py --dir <repo> --test-cmd "python3 -m unittest -v" \
      --backend mock|codex|http [--model M] [--base-url U] \
      [--max-attempts 3] [--timeout-s 300] [--report PATH]
"""
import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backends as backends_mod
import envsafe

MAX_FILE_BYTES = 20000
MAX_OUTPUT_CHARS = 6000


@dataclass
class FixReport:
    status: str = "FAILED"   # FIXED | ALREADY-PASSING | FAILED |
    #                          NO-PROGRESS | BACKEND-ERROR | TIMEOUT
    attempts: int = 0
    before: str = ""
    after: str = ""
    diff: str = ""
    backend: str = ""
    log: list = field(default_factory=list)

    def to_dict(self):
        return {"status": self.status, "attempts": self.attempts,
                "backend": self.backend, "before": self.before,
                "after": self.after, "diff": self.diff, "log": self.log}


def _run(cmd, cwd, timeout_s, shell=False):
    """Run with sanitized env + hard timeout (design rule 2)."""
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), shell=shell,
                              capture_output=True, text=True,
                              timeout=timeout_s, env=envsafe.sanitize_env())
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode() if isinstance(e.stdout, bytes)
               else (e.stdout or ""))
        return None, out + f"\n[TIMEOUT after {timeout_s}s — killed]"


def _test_summary(output):
    """One-line honest summary from unittest-style output."""
    for line in reversed(output.splitlines()):
        if line.startswith(("OK", "FAILED")):
            return line.strip()
    return output.strip().splitlines()[-1][:120] if output.strip() else "(no output)"


def _fail_count(output):
    import re
    m = re.search(r"failures=(\d+)", output)
    e = re.search(r"errors=(\d+)", output)
    if "OK" in output and not (m or e):
        return 0
    if m or e:
        return (int(m.group(1)) if m else 0) + (int(e.group(1)) if e else 0)
    return 999  # unparseable failure counts as worst


def _git(cwd, *args):
    rc, out = _run(["git", *args], cwd, 30)
    return rc, out.strip()


def build_context(workdir, intent, test_output):
    """Bounded context for the backend (design rule 5)."""
    parts = ["# TASK: fix the failing tests. Output ONLY a unified diff.",
             "", "## INTENT", intent or "(no INTENT.md provided)", "",
             "## FAILING TEST OUTPUT", test_output[-MAX_OUTPUT_CHARS:], "",
             "## FILES"]
    for path in sorted(workdir.rglob("*")):
        if path.is_dir() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix not in (".py", ".md", ".txt", ".json", ".cfg", ".toml"):
            continue
        try:
            data = path.read_bytes()[:MAX_FILE_BYTES].decode(errors="replace")
        except OSError:
            continue
        parts.append(f"\n### {path.relative_to(workdir)}\n{data}")
    return "\n".join(parts)


class Fixer:
    def __init__(self, workdir, backend, test_cmd,
                 max_attempts=3, timeout_s=300):
        self.workdir = Path(workdir)
        self.backend = backend
        self.test_cmd = test_cmd
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s

    def run(self):
        rep = FixReport(backend=getattr(self.backend, "name", "?"))
        rc, head = _git(self.workdir, "rev-parse", "HEAD")
        if rc != 0:
            rep.status = "BACKEND-ERROR"
            rep.log.append("workdir is not a git repo — cage requires a checkpoint")
            return rep
        rep.log.append(f"checkpoint: {head[:12]}")

        intent_path = self.workdir / "INTENT.md"
        intent = intent_path.read_text() if intent_path.exists() else ""

        rc, out = _run(self.test_cmd, self.workdir, self.timeout_s, shell=True)
        rep.before = _test_summary(out)
        if rc == 0:
            rep.status = "ALREADY-PASSING"
            rep.after = rep.before
            return rep
        last_fail = _fail_count(out)
        no_progress = 0
        last_diff = ""

        for attempt in range(1, self.max_attempts + 1):
            rep.attempts = attempt
            context = build_context(self.workdir, intent, out)
            try:
                diff = self.backend.propose_fix(context)
            except backends_mod.BackendTimeout as e:
                rep.status = "TIMEOUT"
                rep.log.append(f"attempt {attempt}: {e}")
                break
            except backends_mod.BackendError as e:
                rep.status = "BACKEND-ERROR"
                rep.log.append(f"attempt {attempt}: {e}")
                break
            last_diff = diff
            rc, apply_out = self._apply(diff)
            if rc != 0:
                rep.log.append(f"attempt {attempt}: diff did not apply: "
                               f"{apply_out.strip()[-200:]}")
                no_progress += 1
            else:
                rc2, out = _run(self.test_cmd, self.workdir,
                                self.timeout_s, shell=True)
                rep.after = _test_summary(out)
                if rc2 == 0:
                    rep.status = "FIXED"
                    _, rep.diff = _git(self.workdir, "diff", "HEAD")
                    rep.log.append(f"attempt {attempt}: tests pass")
                    return rep
                now_fail = _fail_count(out)
                if now_fail < last_fail:
                    last_fail = now_fail
                    no_progress = 0
                    rep.log.append(f"attempt {attempt}: progress, "
                                   f"{now_fail} failing")
                else:
                    no_progress += 1
                    rep.log.append(f"attempt {attempt}: no progress, "
                                   f"{now_fail} failing")
                # undo this attempt before the next one / the end
                _git(self.workdir, "checkout", "--", ".")
            if no_progress >= 2:
                rep.status = "NO-PROGRESS"
                break
        else:
            rep.status = "FAILED"

        # cage discipline: restore the checkpoint, keep the last diff
        _git(self.workdir, "checkout", "--", ".")
        rep.diff = last_diff
        if not rep.after:
            rep.after = rep.before
        return rep

    def _apply(self, diff):
        try:
            proc = subprocess.run(["git", "apply", "--whitespace=nowarn"],
                                  cwd=str(self.workdir), input=diff,
                                  capture_output=True, text=True, timeout=30,
                                  env=envsafe.sanitize_env())
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            return None, "[TIMEOUT applying diff]"


def make_backend(args):
    if args.backend == "mock":
        raise SystemExit("mock backend is for tests/dry runs — "
                         "configure diffs in code, not the CLI")
    if args.backend == "codex":
        return backends_mod.CodexBackend(args.codex_cmd, args.timeout_s)
    if args.backend == "http":
        if not args.base_url or not args.model:
            raise SystemExit("http backend needs --base-url and --model")
        return backends_mod.HttpBackend(args.base_url, args.model,
                                        args.api_key, args.timeout_s)
    raise SystemExit(f"unknown backend {args.backend!r}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="P15 Fixer")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--test-cmd", required=True)
    ap.add_argument("--backend", default="codex", choices=["codex", "http", "mock"])
    ap.add_argument("--codex-cmd", default="codex")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--timeout-s", type=int, default=300)
    ap.add_argument("--report", default="")
    args = ap.parse_args(argv)
    fixer = Fixer(args.dir, make_backend(args), args.test_cmd,
                  args.max_attempts, args.timeout_s)
    rep = fixer.run()
    text = json.dumps(rep.to_dict(), indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n")
    return 0 if rep.status in ("FIXED", "ALREADY-PASSING") else 1


if __name__ == "__main__":
    raise SystemExit(main())
