"""驗收契約：Windows 支援（1.11.0，WIN-02～WIN-08，issue #5～#11）。

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



@needs_bash
@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_w02_guard_handles_powershell_payload(tmp_path):
    """PowerShell 工具送來的 git 指令也要經過 lock 守護（有殘留 lock 且無法判斷程序 → 擋下）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".git" / "index.lock").write_bytes(b"")
    payload = json.dumps({"tool_name": "PowerShell",
                          "tool_input": {"command": "git status; Get-ChildItem"}, "cwd": repo.as_posix()})
    guard = (PLUGIN / "hooks" / "git-guard.sh").as_posix()
    r = subprocess.run([BASH, guard], input=payload, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, TW_PROC_METHOD="none"))
    assert r.returncode == 2, r.stderr
    assert (repo / ".git" / "index.lock").exists()

# ---------------- WIN-07：.gitattributes、check-js 不得假 PASS ----------------
def test_w07_gitattributes_forces_lf_for_scripts():
    t = _read(ROOT / ".gitattributes")
    for ext in ("sh", "mjs", "py"):
        assert re.search(rf"^\*\.{ext}\s+text\s+eol=lf", t, re.M), f"*.{ext} 應 eol=lf"


@needs_bash
@pytest.mark.skipif(not shutil.which("node"), reason="需要 node")
def test_w07_check_js_fails_on_syntax_error(tmp_path):
    bad = tmp_path / "bad.html"
    bad.write_text("<html><script>let x = ;</script></html>", encoding="utf-8")
    good = tmp_path / "good.html"
    good.write_text("<html><script>let x = 1;</script></html>", encoding="utf-8")
    cj = (TOOLS / "check-js.sh").as_posix()
    env = {"CLAUDE_JOB_DIR": tmp_path.as_posix()}
    r = _bash(f'"{cj}" "{bad.as_posix()}"', env)
    assert r.returncode != 0, f"語法錯卻 exit 0：{r.stdout}{r.stderr}"
    r = _bash(f'"{cj}" "{good.as_posix()}"', env)
    assert r.returncode == 0 and "JS OK" in r.stdout, r.stdout + r.stderr


# ---------------- WIN-03：Python 偵測（實際執行）與 UTF-8 ----------------
@pytest.fixture
def broken_bin(tmp_path):
    """放一個「存在但執行失敗」的 python3 與 jq（模擬 Windows Store 空殼）。"""
    d = tmp_path / "fakebin"
    d.mkdir()
    for name in ("python3", "jq"):
        p = d / name
        p.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8", newline="\n")
        p.chmod(0o755)
    return d


def _path_with(d):
    return d.as_posix() if os.name != "nt" else subprocess.run(
        [BASH, "-c", f'cygpath -u "{d}"'], capture_output=True, text=True).stdout.strip()


@needs_bash
def test_w03_pick_py_skips_broken_python3(broken_bin):
    lib = (TOOLS / "lib" / "platform.sh").as_posix()
    if not shutil.which("python") and not shutil.which("py"):
        pytest.skip("需要 python 或 py 當替代候選")
    r = _bash(f'export PATH="{_path_with(broken_bin)}:$PATH"; . "{lib}"; pick_py')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() in ("python", "py -3"), f"應跳過壞掉的 python3：{r.stdout!r}"
    r = _bash(f'. "{lib}"; TW_PY_CANDIDATES="nonexistent_a|nonexistent_b" pick_py')
    assert r.returncode == 1 and r.stdout.strip() == ""


@needs_bash
@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_w03_guard_parses_when_jq_and_python3_broken(tmp_path, broken_bin):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".git" / "index.lock").write_bytes(b"")
    payload = json.dumps({"tool_input": {"command": "git commit -m \"中文訊息 ✓\""},
                          "cwd": repo.as_posix()}, ensure_ascii=False)
    guard = (PLUGIN / "hooks" / "git-guard.sh").as_posix()
    env = dict(os.environ, TW_PROC_METHOD="none")
    r = subprocess.run([BASH, "-c", f'export PATH="{_path_with(broken_bin)}:$PATH"; "{guard}"'],
                       input=payload, capture_output=True, text=True, encoding="utf-8", env=env)
    # 解析成功 → 認出 git 指令 → 有 lock 且無法判斷程序 → exit 2；解析失敗會變成 CMD 空白 → exit 0 放行
    assert r.returncode == 2, f"jq／python3 壞掉時 guard 沒認出 git 指令：rc={r.returncode} {r.stderr}"
    assert (repo / ".git" / "index.lock").exists()


def test_w03_no_bare_python3_calls_in_scripts():
    offenders = []
    for p in list(PLUGIN.rglob("*.sh")):
        for i, ln in enumerate(_read(p).splitlines(), 1):
            s = ln.strip()
            if s.startswith("#"):
                continue
            if re.search(r"(?:^|[;&|(]|\$\()\s*python3\s", s):
                offenders.append(f"{p.relative_to(ROOT)}:{i}")
    assert not offenders, f"直接呼叫 python3（應改用 pick_py）：{offenders}"


# ---------------- WIN-04：依平台給安裝提示 ----------------
@needs_bash
@pytest.mark.parametrize("os_name,expect", [
    ("windows", "winget install jqlang.jq OpenJS.NodeJS.LTS Python.Python.3.12 ArtifexSoftware.GhostScript"),
    ("macos", "brew install jq node python ghostscript"),
    ("linux", "sudo apt-get install -y jq nodejs python3 ghostscript"),
    ("wsl", "sudo apt-get install -y jq nodejs python3 ghostscript"),
])
def test_w04_install_hint_per_platform(os_name, expect):
    lib = (TOOLS / "lib" / "platform.sh").as_posix()
    r = _bash(f'. "{lib}"; install_hint jq node python gs', {"TW_OS": os_name})
    assert r.stdout.strip() == expect, r.stdout + r.stderr


def test_w04_apt_get_only_in_platform_lib():
    offenders = [str(p.relative_to(ROOT)) for p in PLUGIN.rglob("*.sh")
                 if p.name != "platform.sh" and "apt-get" in _read(p)]
    assert not offenders, f"apt-get 應只出現在 lib/platform.sh 的 install_hint：{offenders}"


@needs_bash
@pytest.mark.skipif(os.name != "nt", reason="Windows 專屬：從 PATH 拿掉 node 目錄")
@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_w04_doctor_missing_node_hints_winget(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    doctor = (TOOLS / "doctor.sh").as_posix()
    r = _bash('export PATH="$(printf %s "$PATH" | tr : "\n" | grep -vi nodejs | paste -sd:)"; '
              f'"{doctor}" --check --no-fetch --repo "{repo.as_posix()}"')
    out = r.stdout + r.stderr
    assert "缺套件：node" in out, out
    assert "winget install OpenJS.NodeJS.LTS" in out, out
    assert "apt-get" not in out, out


# ---------------- WIN-06：worklog YAML 驗證不綁平台、UTF-8 ----------------
VALIDATE = TOOLS / "validate-yaml.sh"


@needs_bash
def test_w06_validate_yaml_utf8_and_exit_codes(tmp_path):
    pytest.importorskip("yaml")  # 讓 validate-yaml 用目前這個有 PyYAML 的 python
    import sys
    env = {"TW_YAML_PY": Path(sys.executable).as_posix()}
    good = tmp_path / "good.yaml"
    good.write_text('schema: pa-worklog/v1\nsummary: "完成 Windows 支援：測試 ✓"\nitems:\n  - title: 中文標題\n',
                    encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text("summary: [未關閉\n", encoding="utf-8")
    v = VALIDATE.as_posix()
    r = _bash(f'"{v}" "{good.as_posix()}"', env)
    assert r.returncode == 0 and "YAML OK" in r.stdout, r.stdout + r.stderr
    r = _bash(f'"{v}" "{bad.as_posix()}"', env)
    assert r.returncode == 1, r.stdout + r.stderr


@needs_bash
@pytest.mark.skipif(Path("/home/nas/miniconda3/envs/NAS/bin/python").exists(), reason="NAS 機器上一定找得到 PyYAML")
def test_w06_validate_yaml_without_pyyaml_is_not_a_pass(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("a: 1\n", encoding="utf-8")
    r = _bash(f'"{VALIDATE.as_posix()}" "{f.as_posix()}"',
              {"TW_YAML_PY": "", "TW_PY_CANDIDATES": "nonexistent_py_a|nonexistent_py_b"})
    assert r.returncode == 3, r.stdout + r.stderr
    assert "pip install --user pyyaml" in r.stderr


def test_w06_skill_uses_validate_script_not_stdin():
    t = _read(PLUGIN / "skills" / "task-submit-worklog" / "SKILL.md")
    assert "tools/validate-yaml.sh" in t
    code = "\n".join(re.findall(r"```bash\n(.*?)```", t, re.S))
    assert "safe_load(sys.stdin)" not in code, "bash 區塊仍教 stdin 讀 YAML（cp950 會誤判）"


# ---------------- WIN-05：開瀏覽器／找 Chrome 依平台處理 ----------------
@needs_bash
def test_w05_find_chrome_respects_chrome_path(tmp_path):
    fake = tmp_path / "mychrome"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    lib = (TOOLS / "lib" / "platform.sh").as_posix()
    p = _path_with(fake)
    r = _bash(f'. "{lib}"; find_chrome', {"CHROME_PATH": p})
    assert r.returncode == 0 and r.stdout.strip() == p, r.stdout + r.stderr


@needs_bash
def test_w05_open_browser_print_converts_local_path(tmp_path):
    page = tmp_path / "variants.html"
    page.write_text("<html></html>", encoding="utf-8")
    ob = (TOOLS / "open-browser.sh").as_posix()
    r = _bash(f'"{ob}" --print "{_path_with(page)}"', {"TW_BROWSER": "mybrowser"})
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    assert out.startswith("mybrowser "), out
    if os.name == "nt":
        assert re.search(r"[A-Za-z]:\\\\", out), f"Windows 上應轉成 C:\ 路徑：{out}"
    assert "variants.html" in out
    r = _bash(f'"{ob}" --print "{_path_with(tmp_path)}/nope.html"', {"TW_BROWSER": "mybrowser"})
    assert r.returncode == 2


def test_w05_no_linux_only_browser_commands_in_docs():
    explore = _read(PLUGIN / "skills" / "task-explore" / "SKILL.md")
    code = "\n".join(re.findall(r"```bash\n(.*?)```", explore, re.S))
    assert not re.search(r"^\s*chrome\s", code, re.M), "task-explore 仍用 chrome alias"
    assert "tools/open-browser.sh" in explore
    verifier = _read(PLUGIN / "agents" / "verifier-sonnet.md")
    assert "`google-chrome --headless" not in verifier
    assert "tools/find-chrome.sh" in verifier


def test_w05_explore_shots_uses_dirname():
    t = _read(TOOLS / "explore-shots.mjs")
    assert "replace(/\/index\.html$/" not in t, "仍以 regex 去掉 /index.html（Windows 反斜線比對不到）"
    assert re.search(r"\bdirname\(v\.file\)", t)


# ---------------- WIN-08：雲端磁碟偵測、hook 精簡、node_modules 不用 junction ----------------
def _doctor_fn(fn_call, env_extra=None):
    """只 source doctor.sh 的函式（不執行檢查）：擷取 is_drvfs 等定義後呼叫。"""
    d = (TOOLS / "doctor.sh").as_posix()
    script = (f'eval "$(sed -n \'/^is_drvfs() {{/,/^}}/p\' "{d}")"; {fn_call}')
    return _bash(script, env_extra)


@needs_bash
@pytest.mark.parametrize("path,letters,expect", [
    ("/mnt/g/proj", "", 0),
    ("/g/proj", "G", 0), ("G:/proj", "g", 0), ("G:\proj", "G H", 0),
    ("/d/proj", "G", 1), ("D:/proj", "", 1), ("/home/u/proj", "G", 1),
])
def test_w08_is_drvfs_drive_letters(path, letters, expect):
    r = _doctor_fn(f'is_drvfs "{path}"; echo "rc=$?"', {"DOCTOR_DRIVE_LETTERS": letters, "DOCTOR_ASSUME_DRVFS": "0"})
    assert f"rc={expect}" in r.stdout, (path, letters, r.stdout, r.stderr)


def test_w08_messages_platform_neutral():
    d = _read(TOOLS / "doctor.sh")
    assert "repo 不在 /mnt 掛載上" not in d and "（/mnt 掛載）" not in d
    assert "/mnt 掛載的 Windows 權限" not in _read(PLUGIN / "hooks" / "git-guard.sh")


def test_w08_no_junction_for_node_modules():
    for p in (PLUGIN / "skills" / "task-next" / "SKILL.md", PLUGIN / "agents" / "verifier-sonnet.md"):
        t = _read(p)
        assert "mklink /J" not in t, f"{p.name}：junction 會讓 git worktree remove --force 刪到來源"
        assert "不要用 junction" in t, f"{p.name} 應警告不要用 junction"


@needs_bash
@pytest.mark.skipif(os.name != "nt", reason="Windows hook 模式專屬")
@pytest.mark.skipif(not shutil.which("git"), reason="需要 git")
def test_w08_windows_hook_skips_drive_sync_unless_cloud(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "TODO.md").write_text("# TODO\n", encoding="utf-8")
    doctor = (TOOLS / "doctor.sh").as_posix()
    # 非 hook：[d] 照常跑
    r = _bash(f'"{doctor}" --check --no-fetch --repo "{repo.as_posix()}"')
    assert "[d] TODO.md 工作區=" in r.stdout, r.stdout
    # hook＋不在雲端：略過；hook＋指定該磁碟為雲端：照跑
    drive = repo.as_posix()[0]
    src = Path(doctor).read_text(encoding="utf-8")
    assert "Windows hook 模式：repo 不在雲端掛載，略過同步比對" in src
    r = _bash(f'"{doctor}" --check --hook --no-fetch --repo "{repo.as_posix()}"', {"DOCTOR_DRIVE_LETTERS": drive})
    assert "環境醫生" in r.stdout, r.stdout + r.stderr
