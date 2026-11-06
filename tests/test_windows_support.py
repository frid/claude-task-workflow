"""驗收契約：Windows 支援（1.10.0，WIN-02～WIN-08，issue #5～#11）。

每節對應一個 WIN 項目。行為測試在 Windows 上需要 Git for Windows 的 bash
（自動尋找；或以環境變數 DOCTOR_BASH 指定），沒有 bash 時跳過；靜態檢查不需要 bash。

執行：python -m pytest -q -p no:cacheprovider tests/test_windows_support.py
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "task-workflow"
TOOLS = PLUGIN / "tools"


def _read(p):
    return Path(p).read_text(encoding="utf-8")


def _find_bash():
    if os.environ.get("DOCTOR_BASH"):
        return os.environ["DOCTOR_BASH"]
    if os.name == "nt":
        # 不能用 PATH 上的 bash：C:\Windows\System32\bash.exe 是 WSL
        git = shutil.which("git")
        if git:
            for root in Path(git).parents[1:3]:
                for cand in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
                    if cand.exists():
                        return str(cand)
        return None
    return shutil.which("bash")


BASH = _find_bash()
needs_bash = pytest.mark.skipif(not BASH, reason="需要 bash")


def _bash(script, env_extra=None, cwd=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=cwd)


# ---------------- WIN-02：hook 涵蓋 PowerShell、以 bash 明確執行 ----------------
def test_w02_hooks_cover_powershell_and_use_bash():
    h = json.loads(_read(PLUGIN / "hooks" / "hooks.json"))["hooks"]
    pre = h["PreToolUse"][0]
    assert set(pre["matcher"].split("|")) >= {"Bash", "PowerShell"}, pre["matcher"]
    for ev in ("SessionStart", "PreToolUse"):
        cmd = h[ev][0]["hooks"][0]["command"]
        assert cmd.startswith('bash "${CLAUDE_PLUGIN_ROOT}/'), f"{ev} 應以 bash 明確執行：{cmd}"
