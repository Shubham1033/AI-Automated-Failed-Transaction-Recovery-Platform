from __future__ import annotations

import argparse
import json

from .config import settings
from .database import Database
from .service import RecoveryService
from .simulator import run_benchmark, seed_demo


def main() -> None:
    parser = argparse.ArgumentParser(description="ReviveAI development CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed")
    seed_parser.add_argument("--count", type=int, default=30)
    seed_parser.add_argument("--seed", type=int, default=42)
    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--count", type=int, default=100)
    benchmark_parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.command == "benchmark":
        print(json.dumps(run_benchmark(args.count, args.seed), indent=2))
        return
    database = Database(settings.sqlite_path)
    service = RecoveryService(database)
    print(json.dumps(seed_demo(service, args.count, args.seed), indent=2))


if __name__ == "__main__":
    main()

