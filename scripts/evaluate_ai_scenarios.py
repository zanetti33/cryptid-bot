from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.scenario_harness import evaluate_scenario_file, format_evaluation_report


def _scenario_paths(raw_paths: Iterable[str]) -> List[Path]:
    paths: List[Path] = []
    for raw_path in raw_paths:
        candidate = Path(raw_path)
        if any(symbol in raw_path for symbol in "*?[]"):
            paths.extend(sorted(Path().glob(raw_path)))
        else:
            paths.append(candidate)
    unique_paths: List[Path] = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)
    return unique_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Cryptid AI scenarios and print a readable report.")
    parser.add_argument(
        "scenario",
        nargs="+",
        help="Scenario JSON file path(s). Globs are supported, for example data/ai_scenarios/*.json",
    )
    parser.add_argument("--seed", type=int, default=None, help="Override simulation seed")
    parser.add_argument("--observations", type=int, default=None, help="Override number of generated observations")
    parser.add_argument("--top-k", type=int, default=None, help="Override number of recommended moves")
    args = parser.parse_args()

    paths = _scenario_paths(args.scenario)
    if not paths:
        raise SystemExit("No scenario files matched the provided input.")

    for index, path in enumerate(paths, start=1):
        result = evaluate_scenario_file(
            path=path,
            seed=args.seed,
            observation_count=args.observations,
            top_k=args.top_k,
        )
        if index > 1:
            print("\n" + "=" * 80 + "\n")
        print(format_evaluation_report(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


