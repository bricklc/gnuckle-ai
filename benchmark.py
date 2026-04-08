"""
Legacy shim -- use `gnuckle benchmark` instead.

  pip install -e .
  gnuckle benchmark

Or run directly:

  python -m gnuckle benchmark

ape keep this file for backwards compatibility. ape thoughtful like that.
"""

from gnuckle.cli import main

if __name__ == "__main__":
    main()
