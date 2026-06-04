from __future__ import annotations

import subprocess
import sys
from typing import List, Optional, Sequence

MIN_PYTHON = (3, 10)
PY_LAUNCHER_CANDIDATES = ("-3.13", "-3.12", "-3.11", "-3.10")


def _is_compatible(version: Sequence[int]) -> bool:
    return tuple(version[:2]) >= MIN_PYTHON


def _find_py_launcher_target() -> Optional[str]:
    for candidate in PY_LAUNCHER_CANDIDATES:
        check = subprocess.run(
            [
                "py",
                candidate,
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if check.returncode == 0:
            return candidate
    return None


def _run_pytest_with_current_interpreter(pytest_args: List[str]) -> int:
    command = [sys.executable, "-m", "pytest", *pytest_args]
    return subprocess.call(command)


def _run_pytest_with_launcher(candidate: str, pytest_args: List[str]) -> int:
    command = ["py", candidate, "-m", "pytest", *pytest_args]
    return subprocess.call(command)


def main(argv: List[str]) -> int:
    pytest_args = argv if argv else ["-q"]

    if _is_compatible(sys.version_info):
        return _run_pytest_with_current_interpreter(pytest_args)

    # If called with an old Python on Windows, auto-forward to a newer interpreter via py launcher.
    candidate = _find_py_launcher_target()
    if candidate is not None:
        print(
            "Current interpreter "
            f"{sys.version_info.major}.{sys.version_info.minor} is not supported; "
            f"running tests with {candidate} instead."
        )
        return _run_pytest_with_launcher(candidate, pytest_args)

    print(
        "Error: tests require Python "
        f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ (dataclass slots support). "
        "Install a compatible Python version and run this script with that interpreter."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

