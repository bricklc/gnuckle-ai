"""gnuckle CLI -- benchmark runner entry point."""

import argparse

from gnuckle import __version__
from gnuckle.splash import print_splash

try:
    import argcomplete
except ImportError:
    argcomplete = None


def cmd_benchmark(args):
    """Run the agentic benchmark."""
    from gnuckle.benchmark import run_full_benchmark

    run_full_benchmark(
        model_path=args.model,
        server_path=args.server,
        scan_dir=args.scan_dir,
        output_dir=args.output,
        num_turns=args.turns,
        port=args.port,
        profile_path=args.profile,
    )


def cmd_visualize(args):
    """Visualize benchmark results."""
    from gnuckle.visualize import run_visualize

    run_visualize(args.results_dir)


def main():
    parser = argparse.ArgumentParser(
        prog="gnuckle",
        description="Gnuckle AI - Agentic AI Benchmark. ape drag knuckle on keyboard. benchmark happen.",
        epilog="accidentally GNU, intentionally simian.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gnuckle {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="available commands")

    bench = subparsers.add_parser(
        "benchmark",
        aliases=["run", "bench"],
        help="run the agentic KV cache benchmark",
        description="Benchmark llama.cpp KV cache quantization on agentic tool-calling workloads.",
    )
    bench.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="path to .gguf model file (interactive picker if omitted)",
    )
    bench.add_argument(
        "--server",
        "-s",
        type=str,
        default=None,
        help="path to llama-server executable (prompted if omitted)",
    )
    bench.add_argument(
        "--scan-dir",
        type=str,
        default=None,
        help="directory to scan for .gguf files (defaults to cwd)",
    )
    bench.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="output directory for results JSON (default: ./benchmark_results/)",
    )
    bench.add_argument(
        "--turns",
        "-t",
        type=int,
        default=None,
        help="number of conversation turns per cache type (default: 20)",
    )
    bench.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="llama-server port (default: 8080)",
    )
    bench.add_argument(
        "--profile",
        type=str,
        default=None,
        help="path to a gnuckle profile JSON file",
    )
    bench.set_defaults(func=cmd_benchmark)

    viz = subparsers.add_parser(
        "visualize",
        aliases=["viz", "chart"],
        help="visualize benchmark results",
        description="Read benchmark JSONs and produce a static HTML dashboard.",
    )
    viz.add_argument(
        "results_dir",
        nargs="?",
        default="./benchmark_results/",
        help="directory containing benchmark JSON files",
    )
    viz.set_defaults(func=cmd_visualize)

    if argcomplete is not None:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.command is None:
        print_splash()
        parser.print_help()
        print()
        return

    print_splash()
    args.func(args)
