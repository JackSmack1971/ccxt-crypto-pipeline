"""Print the declared scientific benchmark contract."""

import json

from . import BENCHMARK_VERSION, benchmark_cases, benchmark_identity


def main() -> None:
    print(json.dumps({"version": BENCHMARK_VERSION, "identity": benchmark_identity(),
                      "cases": [case.__dict__ for case in benchmark_cases()]},
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
