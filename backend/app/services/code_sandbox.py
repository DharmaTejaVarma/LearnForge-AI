"""Isolated Python code execution sandbox for LearnForge AI interactive coding/debugging exercises.

Never executes untrusted student code in the main FastAPI process: parses the code with
``ast`` first to block dangerous imports and builtins, then executes inside a short-lived
isolated subprocess (``python -I``) in a temporary directory with a strict timeout.
"""
from __future__ import annotations

import ast
import collections
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional
from fastapi import HTTPException, status


_FORBIDDEN_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "pathlib", "shutil", "ctypes",
    "importlib", "urllib", "http", "requests", "httpx", "aiohttp", "builtins",
    "io", "multiprocessing", "threading", "concurrent", "pickle", "marshal",
    "tempfile", "glob", "pty", "signal", "resource", "gc", "inspect",
})

_FORBIDDEN_CALLS = frozenset({
    "open", "eval", "exec", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
})

_MAX_OUTPUT_CHARS = 4000
_TIMEOUT_SECONDS = 3
_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024  # 256 MB per sandbox execution

_RATE_LOCK = threading.Lock()
_USER_RUN_TIMESTAMPS: Dict[int, Deque[float]] = {}


def check_sandbox_rate_limit(user_id: int, max_per_minute: int = 20) -> None:
    """Enforce per-user sliding-window rate limit on sandbox code execution."""
    now = time.monotonic()
    cutoff = now - 60.0
    with _RATE_LOCK:
        dq = _USER_RUN_TIMESTAMPS.setdefault(user_id, collections.deque())
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Sandbox execution rate limit exceeded. Please wait a moment before running again.",
            )
        dq.append(now)


def _create_windows_job_object(memory_limit_bytes: int = _MEMORY_LIMIT_BYTES) -> Optional[int]:
    """Create a Windows Job Object enforcing 1 active process, memory cap, and kill-on-close."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        # KILL_ON_JOB_CLOSE (0x2000) | PROCESS_MEMORY (0x0100) | ACTIVE_PROCESS (0x0008)
        info.BasicLimitInformation.LimitFlags = 0x2000 | 0x0100 | 0x0008
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.ProcessMemoryLimit = memory_limit_bytes

        ok = kernel32.SetInformationJobObject(
            job,
            9,  # JobObjectExtendedLimitInformation
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            kernel32.CloseHandle(job)
            return None
        return int(job)
    except Exception:
        return None


def validate_python_code(code: str) -> tuple[bool, Optional[str]]:
    """Validate syntax and reject unsafe imports or builtin calls using Python's AST."""
    if not code or not code.strip():
        return False, "Code cannot be empty."
    if len(code) > 15000:
        return False, "Submitted code exceeds maximum allowed length (15,000 characters)."

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line_info = f"line {exc.lineno}" if exc.lineno else "unknown line"
        return False, f"SyntaxError at {line_info}: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in _FORBIDDEN_IMPORTS:
                    return False, f"Restricted module import '{root_pkg}' is not allowed in the sandbox."
        elif isinstance(node, ast.ImportFrom):
            root_pkg = (node.module or "").split(".")[0]
            if root_pkg in _FORBIDDEN_IMPORTS:
                return False, f"Restricted module import '{root_pkg}' is not allowed in the sandbox."
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_CALLS:
                return False, f"Restricted builtin '{func.id}()' is not allowed in the sandbox."
            elif isinstance(func, ast.Attribute) and func.attr.startswith("__"):
                return False, f"Dunder attribute access '{func.attr}' is restricted in the sandbox."
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False, f"Restricted dunder attribute '{node.attr}' is not allowed in the sandbox."

    return True, None


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "\n...[output truncated]"


def execute_python_sandbox(
    code: str,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    timeout_seconds: int = _TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute validated Python code in an isolated subprocess and evaluate optional test cases."""
    ok, err = validate_python_code(code)
    if not ok:
        return {
            "passed": False,
            "passed_tests": 0,
            "total_tests": len(test_cases or []),
            "stdout": "",
            "stderr": err or "Validation failed",
            "results": [],
            "timed_out": False,
        }

    tests = test_cases or []
    for t in tests:
        ac = t.get("assert_code")
        if ac:
            ac_ok, ac_err = validate_python_code(str(ac))
            if not ac_ok:
                return {
                    "passed": False,
                    "passed_tests": 0,
                    "total_tests": len(tests),
                    "stdout": "",
                    "stderr": ac_err or "Invalid test assertion code",
                    "results": [],
                    "timed_out": False,
                }

    harness = (
        "import builtins, contextlib, io, json, sys, traceback\n"
        "sys.setrecursionlimit(250)\n"
        f"_BLOCKED_MODS = {json.dumps(sorted(_FORBIDDEN_IMPORTS))}\n"
        "_orig_import = builtins.__import__\n"
        "def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
        "    if str(name).split('.')[0] in _BLOCKED_MODS:\n"
        "        raise ImportError(f'Restricted module import {name!r} is not allowed in the sandbox.')\n"
        "    return _orig_import(name, globals, locals, fromlist, level)\n"
        "_safe_builtins = {k: v for k, v in vars(builtins).items() if k not in {'open','eval','exec','compile','input','breakpoint','globals','locals','vars','getattr','setattr','delattr'}}\n"
        "_safe_builtins['__import__'] = _safe_import\n"
        f"_STUDENT_CODE = {json.dumps(code)}\n"
        f"_TESTS = {json.dumps(tests)}\n"
        "_stdout_buf = io.StringIO()\n"
        "_env = {'__builtins__': _safe_builtins}\n"
        "_results = []\n"
        "_runtime_err = ''\n"
        "try:\n"
        "    with contextlib.redirect_stdout(_stdout_buf):\n"
        "        exec(compile(_STUDENT_CODE, '<student_code>', 'exec'), _env, _env)\n"
        "except Exception:\n"
        "    _runtime_err = traceback.format_exc()\n"
        "_out = _stdout_buf.getvalue()\n"
        "if not _runtime_err and _TESTS:\n"
        "    for idx, t in enumerate(_TESTS):\n"
        "        desc = str(t.get('description') or f'Test {idx + 1}')\n"
        "        assert_code = t.get('assert_code') or ''\n"
        "        expected_contains = t.get('expected_contains')\n"
        "        passed_case = True\n"
        "        msg = 'Passed'\n"
        "        try:\n"
        "            if assert_code:\n"
        "                exec(compile(assert_code, f'<test_{idx}>', 'exec'), _env, _env)\n"
        "            if expected_contains is not None:\n"
        "                if str(expected_contains) not in _out:\n"
        "                    passed_case = False\n"
        "                    msg = f'Expected output to contain {expected_contains!r}'\n"
        "        except AssertionError as ae:\n"
        "            passed_case = False\n"
        "            msg = str(ae) or 'Assertion failed'\n"
        "        except Exception as te:\n"
        "            passed_case = False\n"
        "            msg = f'{type(te).__name__}: {te}'\n"
        "        _results.append({'description': desc, 'passed': passed_case, 'message': msg})\n"
        "elif _runtime_err and _TESTS:\n"
        "    for idx, t in enumerate(_TESTS):\n"
        "        _results.append({'description': str(t.get('description') or f'Test {idx + 1}'), 'passed': False, 'message': 'Runtime error before test evaluation'})\n"
        "print('__SANDBOX_RESULT__' + json.dumps({'stdout': _out, 'stderr': _runtime_err, 'results': _results}))\n"
    )

    with tempfile.TemporaryDirectory(prefix="lf_sandbox_") as tmpdir:
        runner_path = Path(tmpdir) / "runner.py"
        runner_path.write_text(harness, encoding="utf-8")

        try:
            popen_kwargs: Dict[str, Any] = {}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
                )
            else:
                def _limit_posix_resources() -> None:
                    try:
                        import resource
                        mem_bytes = 256 * 1024 * 1024
                        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds + 1, timeout_seconds + 1))
                        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
                    except Exception:
                        pass
                popen_kwargs["preexec_fn"] = _limit_posix_resources

            sandbox_env = {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if sys.platform == "win32" and os.environ.get("SYSTEMROOT"):
                sandbox_env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

            job_handle = _create_windows_job_object(_MEMORY_LIMIT_BYTES)
            proc_obj = subprocess.Popen(
                [sys.executable, "-I", str(runner_path)],
                cwd=tmpdir,
                env=sandbox_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **popen_kwargs,
            )
            try:
                if job_handle is not None:
                    ctypes.windll.kernel32.AssignProcessToJobObject(job_handle, int(proc_obj._handle))
                raw_stdout, raw_stderr = proc_obj.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc_obj.kill()
                proc_obj.communicate()
                raise
            finally:
                if job_handle is not None:
                    ctypes.windll.kernel32.CloseHandle(job_handle)

            class _ProcResult:
                stdout = raw_stdout
                stderr = raw_stderr
            proc = _ProcResult()
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "passed_tests": 0,
                "total_tests": len(tests),
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds} seconds (possible infinite loop).",
                "results": [
                    {"description": str(t.get("description") or f"Test {i + 1}"), "passed": False, "message": "Timed out"}
                    for i, t in enumerate(tests)
                ],
                "timed_out": True,
            }

    marker = "__SANDBOX_RESULT__"
    raw_out = proc.stdout or ""
    if marker in raw_out:
        json_part = raw_out.split(marker, 1)[1].strip()
        try:
            parsed = json.loads(json_part)
            results = parsed.get("results", [])
            passed_tests = sum(1 for r in results if r.get("passed"))
            stderr_txt = _truncate(parsed.get("stderr", "") or proc.stderr or "")
            stdout_txt = _truncate(parsed.get("stdout", ""))
            overall_passed = (
                not stderr_txt
                and (passed_tests == len(tests) if tests else True)
            )
            return {
                "passed": overall_passed,
                "passed_tests": passed_tests,
                "total_tests": len(tests),
                "stdout": stdout_txt,
                "stderr": stderr_txt,
                "results": results,
                "timed_out": False,
            }
        except json.JSONDecodeError:
            pass

    return {
        "passed": False,
        "passed_tests": 0,
        "total_tests": len(tests),
        "stdout": _truncate(raw_out),
        "stderr": _truncate(proc.stderr or "Sandbox execution did not produce a valid result."),
        "results": [],
        "timed_out": False,
    }
