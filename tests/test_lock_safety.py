"""驗收契約：殘留 git lock 的安全清除（1.10.3，WIN-01）。

來源：Windows Git Bash 沒有 pgrep。1.10.2 以前 git-guard／doctor [a]／task-release 都以
`pgrep -x git` 判斷，pgrep 不存在 → 判成「沒有 git 在跑」→ 刪掉活著的 git 持有的 index.lock
（實測：背景跑 git.exe 時 guard 照樣刪鎖）。
修正：tools/lib/procs.sh 的 git_pids 依序用 pgrep／tasklist／ps -W；全部不能用時回報「無法判斷」，
呼叫端一律不刪。TW_PROC_METHOD=none 可模擬「全部不能用」。

執行：python -m pytest -q -p no:cacheprovider tests/test_lock_safety.py
Windows 上需 Git for Windows 的 bash（自動尋找；或以環境變數 DOCTOR_BASH 指定）。
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
GUARD = PLUGIN / "hooks" / "git-guard.sh"
DOCTOR = PLUGIN / "tools" / "doctor.sh"
CLEAR = PLUGIN / "tools" / "clear-stale-lock.sh"
LIB = PLUGIN / "tools" / "lib" / "procs.sh"


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
pytestmark = pytest.mark.skipif(not BASH or not shutil.which("git"), reason="需要 bash 與 git")


def _run(args, env_extra=None, stdin=None, cwd=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [BASH, *args], input=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, cwd=cwd,
    )


def _git_running_now():
    """以 lib 本身判斷此刻是否有其他 git 在跑（給「應該刪」的測試當前提）。"""
    r = _run(["-c", f'. "{LIB.as_posix()}"; git_pids; echo "|$?"'])
    pids, _, rc = r.stdout.strip().rpartition("|")
    return rc != "0" or pids.strip() != ""


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=r, check=True)
    return r


@pytest.fixture
def lock(repo):
    p = repo / ".git" / "index.lock"
    p.write_bytes(b"")
    return p


@pytest.fixture
def live_git(repo):
    """一個真的、持續執行中的 git 程序（等 stdin）。"""
    p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=repo,
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield p
    p.stdin.close()
    p.wait(timeout=10)


def _guard(repo, env_extra=None):
    payload = json.dumps({"tool_input": {"command": "git status"}, "cwd": repo.as_posix()})
    return _run([GUARD.as_posix()], env_extra, stdin=payload)


# L1：git-guard — 有 git 在跑 → 不刪、exit 2（會等約 7 秒）
def test_guard_keeps_lock_while_git_running(repo, lock, live_git):
    r = _guard(repo)
    assert r.returncode == 2, r.stderr
    assert lock.exists(), "git 還在跑卻把 lock 刪了"
    assert "仍被 git 程序持有" in r.stderr


# L2：git-guard — 偵測工具全部不能用 → 不刪、exit 2
def test_guard_keeps_lock_when_undetectable(repo, lock):
    r = _guard(repo, {"TW_PROC_METHOD": "none"})
    assert r.returncode == 2, r.stderr
    assert lock.exists(), "無法判斷卻把 lock 刪了"
    assert "無法判斷" in r.stderr


# L3：git-guard — 確定沒有 git 在跑 → 刪掉殘留、放行
def test_guard_removes_stale_lock(repo, lock):
    if _git_running_now():
        pytest.skip("此刻機器上有其他 git 程序在跑，無法驗證『沒有 git』的情境")
    r = _guard(repo)
    assert r.returncode == 0, r.stderr
    assert not lock.exists()


# L4：doctor --fix — 無法判斷 → [a] WARN、不刪
def test_doctor_fix_keeps_lock_when_undetectable(repo, lock):
    r = _run([DOCTOR.as_posix(), "--fix", "--no-fetch", "--repo", repo.as_posix()], {"TW_PROC_METHOD": "none"})
    out = r.stdout + r.stderr
    assert lock.exists(), out
    assert "無法判斷是否有 git 程序" in out, out


# L5：clear-stale-lock.sh — 有 git 在跑／無法判斷 → 不刪；沒有 git → 刪
def test_clear_stale_lock(repo, lock, live_git):
    r = _run([CLEAR.as_posix(), repo.as_posix()], {"TW_LOCK_MAX_WAIT": "1"})
    assert r.returncode == 2 and lock.exists(), r.stderr
    r = _run([CLEAR.as_posix(), repo.as_posix()], {"TW_PROC_METHOD": "none"})
    assert r.returncode == 2 and lock.exists(), r.stderr


def test_clear_stale_lock_removes_when_idle(repo, lock):
    if _git_running_now():
        pytest.skip("此刻機器上有其他 git 程序在跑")
    r = _run([CLEAR.as_posix(), repo.as_posix()])
    assert r.returncode == 0 and not lock.exists(), r.stderr


# L6：靜態 — 只有 lib 直接呼叫 pgrep；skill／agent／hook 不得再教「pgrep … || rm」
def test_no_direct_pgrep_rm_pattern():
    offenders = []
    for p in PLUGIN.rglob("*"):
        if not p.is_file() or p.suffix not in {".sh", ".md", ".json", ".mjs"} or p == LIB:
            continue
        t = p.read_text(encoding="utf-8")
        if re.search(r"pgrep[^\n]*\|\|\s*rm\b", t.replace("`pgrep … || rm -f`", "").replace("`pgrep … || rm`", "")):
            offenders.append(str(p.relative_to(ROOT)))
        # 以指令形式呼叫（行首、;、&&、||、|、$( 之後接 pgrep -…），訊息文字裡提到 pgrep 不算
        if p.suffix == ".sh" and re.search(r"(?:^|[;&|(]|\$\()\s*pgrep\s+-", "\n".join(
                ln for ln in t.splitlines() if not ln.lstrip().startswith("#")), re.M):
            offenders.append(f"{p.relative_to(ROOT)}（直接呼叫 pgrep，應改用 lib/procs.sh）")
    assert not offenders, offenders
