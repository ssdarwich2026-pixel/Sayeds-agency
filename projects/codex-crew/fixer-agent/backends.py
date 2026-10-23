"""Model backends — design rules 1, 2 and 6 (SPEC.md).

Contract: propose_fix(context: str) -> str, a UNIFIED DIFF or an
exception. Essays are not fixes. Every call is hard-timeout bounded;
a timeout raises BackendTimeout, any other failure BackendError with
the backend's own words preserved. Backends are OURS:

- MockBackend   — deterministic; tests and dry runs.
- CodexBackend  — `codex exec` (read-only sandbox, diff-only prompt)
                  against a logged-in Codex CLI (Pitch primary).
- HttpBackend   — OpenAI-compatible /chat/completions (Pitch/Micro
                  Ollama qwen3:8b: $0, keyless, on-box).
"""
import json
import subprocess
import urllib.request

import envsafe


class BackendError(Exception):
    pass


class BackendTimeout(BackendError):
    pass


class MockBackend:
    name = "mock"

    def __init__(self, diffs):
        """diffs: list of diff strings, returned in order (last repeats)."""
        self._diffs = list(diffs)
        self.calls = 0

    def propose_fix(self, context):
        if not self._diffs:
            raise BackendError("mock backend has no diffs configured")
        diff = self._diffs[min(self.calls, len(self._diffs) - 1)]
        self.calls += 1
        return diff


class ScriptedBackend(MockBackend):
    """Mock whose diff comes from a callable(context) -> diff."""

    name = "scripted"

    def __init__(self, fn):
        super().__init__([])
        self._fn = fn

    def propose_fix(self, context):
        self.calls += 1
        return self._fn(context)


DIFF_INSTRUCTION = (
    "You are a code-fixing engine inside an automated harness. "
    "Output ONLY a unified diff (git format, a/ b/ paths) that fixes "
    "the problem described. No explanation, no markdown fences, no "
    "file edits — the harness applies your diff and re-runs the tests."
)


class CodexBackend:
    name = "codex"

    def __init__(self, codex_cmd="codex", timeout_s=300):
        self.codex_cmd = codex_cmd
        self.timeout_s = timeout_s

    def propose_fix(self, context):
        prompt = DIFF_INSTRUCTION + "\n\n" + context
        try:
            proc = subprocess.run(
                [self.codex_cmd, "exec", "-s", "read-only", prompt],
                capture_output=True, text=True, timeout=self.timeout_s,
                env=envsafe.sanitize_env(),
            )
        except subprocess.TimeoutExpired:
            raise BackendTimeout(
                f"codex exec exceeded {self.timeout_s}s and was killed")
        out = (proc.stdout or "") + (proc.stderr or "")
        diff = extract_diff(out)
        if diff is None:
            raise BackendError(
                f"codex returned no diff (rc={proc.returncode}): "
                f"{out.strip()[-400:]}")
        return diff


class HttpBackend:
    name = "http"

    def __init__(self, base_url, model, api_key="", timeout_s=300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    def propose_fix(self, context):
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": DIFF_INSTRUCTION},
                {"role": "user", "content": context},
            ],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"}
                        if self.api_key else {})})
        # Sanitized env decides proxying; build an opener that reads
        # the sanitized environment, not the raw one.
        clean = envsafe.sanitize_env()
        proxy = clean.get("HTTPS_PROXY") or clean.get("https_proxy")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(
                {"http": proxy, "https": proxy} if proxy else {}))
        try:
            with opener.open(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode())
        except TimeoutError:
            raise BackendTimeout(
                f"http backend exceeded {self.timeout_s}s")
        except Exception as e:  # surface the endpoint's own words
            detail = getattr(e, "read", None)
            text = ""
            if callable(detail):
                try:
                    text = detail().decode()[:400]
                except Exception:
                    text = ""
            raise BackendError(f"http backend error: {e} {text}".strip())
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise BackendError(f"unexpected response shape: {str(data)[:400]}")
        diff = extract_diff(content)
        if diff is None:
            raise BackendError(f"model returned no diff: {content.strip()[-400:]}")
        return diff


def extract_diff(text):
    """Pull a unified diff out of raw model output, or None.

    Tolerates markdown fences and leading prose; requires a real
    '--- a/' + '+++ b/' + '@@' structure (design rule 6).
    """
    if not text:
        return None
    lines = text.replace("```diff", "```").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- a/") or line.startswith("--- /"):
            start = i
            break
    if start is None:
        return None
    diff_lines = []
    for line in lines[start:]:
        if line.startswith("```"):
            break
        diff_lines.append(line)
    diff = "\n".join(diff_lines).strip() + "\n"
    if "+++ b/" not in diff or "@@" not in diff:
        return None
    return diff
