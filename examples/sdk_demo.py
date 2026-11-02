"""An installed-package embedding smoke test with synthetic data and no network.

The demo itself lives in `sageql.demo` so `sageql demo` works after
`pip install sageql`; this script prints the final reply as JSON.
"""

from sageql.demo import main

if __name__ == "__main__":
    raise SystemExit(main(["--json"]))
