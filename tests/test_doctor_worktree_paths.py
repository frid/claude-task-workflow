"""驗收契約：doctor.sh [c] worktree 指標檢查（1.10.2）。

來源：Windows（Git for Windows / Git Bash）上 git 把 gitdir 寫成 `D:/…` 磁碟代號路徑，
舊版用 `case "$gd" in /*)` 判斷絕對路徑，把 `D:/…` 當相對路徑接在目錄後面 → 健康的 worktree
被報「指標失效」；且 `D:/x` 與 `/d/x` 未去重，同一 worktree 重複列出。

執行：python -m pytest -q -p no:cacheprovider tests/test_doctor_worktree_paths.py
Windows 上需 Git for Windows 的 bash（自動尋找；或以環境變數 DOCTOR_BASH 指定）。
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "plugins" / "task-workflow" / "tools" / "doctor.sh"


def _find_bash():
    if os.environ.get("DOCTOR_BASH"):
        return os.environ["DOCTOR_BASH"]
    if os.name == "nt":
        # 不能用 PATH 上的 bash：C:\Windows\System32\bash.exe 是 WSL，路徑語意不同
        git = shutil.which("git")
        if git:  # git.exe 可能在 Git\cmd 或 Git\mingw64\bin → 往上找一層與兩層的 Git 根目錄
            for root in Path(git).parents[1:3]:
                for cand in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
                    if cand.exists():
                        return str(cand)
        return None
    return shutil.which("bash")


BASH = _find_bash()
pytestmark = pytest.mark.skipif(not BASH or not shutil.which("git"), reason="需要 bash 與 git")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _doctor(repo):
    r = subprocess.run(
        [BASH, DOCTOR.as_posix(), "--check", "--no-fetch", "--repo", Path(repo).as_posix()],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.stdout + r.stderr


@pytest.fixture
def repo_with_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "init")
    wt = repo / ".claude" / "worktrees" / "feat"
    _git(repo, "worktree", "add", "-q", "-b", "feat", str(wt))
    return repo, wt


def _c_lines(out):
    return [ln for ln in out.splitlines() if "[c]" in ln or "→" in ln]


# C1：健康的 worktree（Windows 上 gitdir 為 D:/… 絕對路徑）不得被報失效
#     （舊版在 Windows 會報 3 筆：方向 1 一筆、方向 2 因 D:/x 與 /d/x 未去重而重複兩筆）
def test_healthy_worktree_not_reported_broken(repo_with_worktree):
    repo, _ = repo_with_worktree
    out = _doctor(repo)
    assert "雙向都解析得到（1 個 worktree）" in out, out
    assert "指標失效" not in out, out


# C2：worktree 目錄真的不見了仍要報失效（修正不得把真問題蓋掉），且同一 worktree 不重複列出
def test_missing_worktree_still_reported(repo_with_worktree):
    repo, wt = repo_with_worktree
    shutil.rmtree(wt)
    out = _doctor(repo)
    assert "指標失效" in out, out
    gitdir_hints = [ln for ln in _c_lines(out) if "gitdir 指向不存在" in ln]
    assert len(gitdir_hints) == 1, out


# C3：worktree 的 .git 指回的 .git/worktrees/<n> 不見了也要報（方向 2 的真問題），且只報一次
def test_missing_admin_dir_reported_once(repo_with_worktree):
    repo, _ = repo_with_worktree
    shutil.rmtree(repo / ".git" / "worktrees" / "feat")
    out = _doctor(repo)
    hints = [ln for ln in _c_lines(out) if ".git 指向不存在" in ln]
    assert len(hints) == 1, out
