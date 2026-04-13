"""gnuckle CLI -- benchmark runner entry point."""

import argparse
import json

from gnuckle import __version__
from gnuckle.splash import print_splash

try:
    import argcomplete
except ImportError:
    argcomplete = None


def cmd_benchmark(args):
    """Run the agentic benchmark."""
    from gnuckle.benchmark import run_full_benchmark

    selected_ids = None
    if args.workflows:
        selected_ids = [w.strip() for w in args.workflows.split(",") if w.strip()]

    session_ids = None
    if args.session_bench:
        session_ids = [s.strip() for s in args.session_bench.split(",") if s.strip()]

    quality_ids = None
    if args.quality_bench:
        quality_ids = [q.strip() for q in args.quality_bench.split(",") if q.strip()]

    run_full_benchmark(
        benchmark_mode=args.mode,
        model_path=args.model,
        server_path=args.server,
        scan_dir=args.scan_dir,
        output_dir=args.output,
        num_turns=args.turns,
        port=args.port,
        profile_path=args.profile,
        workflow_suite=args.workflow_suite,
        session_mode=args.session_mode,
        use_jinja=not args.no_jinja,
        live_trace=args.live_trace,
        trace_prompts=args.trace_prompts,
        trace_style=args.trace_style,
        selected_workflow_ids=selected_ids,
        session_bench_ids=session_ids,
        cache_labels=None,
        quality_bench_ids=quality_ids,
        skip_quality=args.skip_quality,
    )


def cmd_visualize(args):
    """Visualize benchmark results."""
    from gnuckle.visualize import run_visualize

    run_visualize(args.results_dir)


def cmd_menu(_args):
    from gnuckle.menu import run_interactive_menu

    run_interactive_menu()


def cmd_update(_args):
    """Update gnuckle in place."""
    from gnuckle.update import run_update

    raise SystemExit(run_update())


def cmd_bench_update(args):
    from gnuckle.bench_pack import sync_registry

    entries = sync_registry(index_url=args.index_url)
    print(json.dumps({"updated": len(entries)}, indent=2))


def cmd_bench_list(_args):
    from gnuckle.bench_pack.registry import list_available_packs, list_registry_benchmarks
    from gnuckle.bench_pack.trust import benchmarks_dir

    installed = sorted([path.name for path in benchmarks_dir().iterdir() if path.is_dir()] if benchmarks_dir().exists() else [])
    print(json.dumps({"installed": installed, "available": list_available_packs(), "benchmarks": list_registry_benchmarks()}, indent=2))


def cmd_bench_search(args):
    from gnuckle.bench_pack import search_packs

    print(json.dumps({"results": search_packs(args.query)}, indent=2))


def cmd_bench_info(args):
    from gnuckle.bench_pack.registry import get_pack_info

    info = get_pack_info(args.pack_id)
    print(json.dumps(info or {}, indent=2))


def cmd_bench_install(args):
    from gnuckle.bench_pack import install_pack

    result = install_pack(args.pack_id, assume_yes=args.yes, trust_url=args.trust_url)
    print(json.dumps(result, indent=2))


def cmd_bench_remove(args):
    from gnuckle.bench_pack import remove_pack

    print(json.dumps(remove_pack(args.pack_id), indent=2))


def cmd_bench_verify(_args):
    from gnuckle.bench_pack import verify_installed_packs

    print(json.dumps(verify_installed_packs(), indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="gnuckle",
        description=f"Gnuckle AI v{__version__} - Agentic AI Benchmark. ape drag knuckle on keyboard. benchmark happen.",
        epilog="accidentally GNU, intentionally simian.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gnuckle {__version__}",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="update this gnuckle clone in place",
    )

    subparsers = parser.add_subparsers(dest="command", help="available commands")

    bench = subparsers.add_parser(
        "benchmark",
        aliases=["run"],
        help="run the agentic KV cache benchmark",
        description="Benchmark llama.cpp KV cache quantization on agentic tool-calling workloads.",
    )
    bench.add_argument(
        "--mode",
        choices=["legacy", "agentic", "session"],
        default=None,
        help="benchmark mode: legacy (raw turns), agentic (workflow suite), session (persistent session benchmarks)",
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
    bench.add_argument(
        "--no-jinja",
        action="store_true",
        help="disable --jinja when launching llama-server",
    )
    bench.add_argument(
        "--workflow-suite",
        type=str,
        default=None,
        help="agentic workflow suite name (default: default)",
    )
    bench.add_argument(
        "--session-mode",
        choices=["fresh_session", "full_history"],
        default=None,
        help="agentic session reuse mode",
    )
    bench.add_argument(
        "--workflows",
        type=str,
        default=None,
        help="comma-separated workflow IDs to run (e.g. 'cb_01_tool_call_validity,cb_02_tool_selection')",
    )
    bench.add_argument(
        "--session-bench",
        type=str,
        default=None,
        help="comma-separated session benchmark IDs (e.g. 'persistent_tool_stress')",
    )
    bench.add_argument(
        "--live-trace",
        action="store_true",
        help="show a live terminal harness trace for agentic runs",
    )
    bench.add_argument(
        "--trace-prompts",
        choices=["off", "summary", "full"],
        default="summary",
        help="how much prompt text to show in live trace mode",
    )
    bench.add_argument(
        "--trace-style",
        choices=["theater", "log"],
        default="theater",
        help="terminal presentation style for live trace mode",
    )
    bench.add_argument(
        "--skip-quality",
        action="store_true",
        help="skip quality benchmarks (llama-perplexity / WikiText-2 PPL); useful when the binary is missing or for fast iteration",
    )
    bench.add_argument(
        "--quality-bench",
        type=str,
        default=None,
        help="comma-separated installed benchmark pack IDs to run (for example 'wikitext2_ppl,kld_vs_f16')",
    )
    bench.set_defaults(func=cmd_benchmark)

    benchpacks = subparsers.add_parser(
        "bench",
        help="manage installed benchmark packs",
        description="Registry and install commands for declarative benchmark packs.",
    )
    bench_subparsers = benchpacks.add_subparsers(dest="bench_command", help="bench pack commands")

    bench_update = bench_subparsers.add_parser("update", help="sync local registry index")
    bench_update.add_argument("--index-url", type=str, default=None, help="override registry index URL")
    bench_update.set_defaults(func=cmd_bench_update)

    bench_list = bench_subparsers.add_parser("list", help="show installed and available benchmark packs")
    bench_list.set_defaults(func=cmd_bench_list)

    bench_search = bench_subparsers.add_parser("search", help="search available benchmark packs")
    bench_search.add_argument("query", nargs="?", default="", help="search keyword")
    bench_search.set_defaults(func=cmd_bench_search)

    bench_info = bench_subparsers.add_parser("info", help="show one pack from the local registry")
    bench_info.add_argument("pack_id", help="pack identifier")
    bench_info.set_defaults(func=cmd_bench_info)

    bench_install = bench_subparsers.add_parser("install", help="install a pack from the registry or a local manifest path")
    bench_install.add_argument("pack_id", help="registry pack ID or local manifest path")
    bench_install.add_argument("--yes", action="store_true", help="skip interactive confirmation")
    bench_install.add_argument("--trust-url", action="store_true", help="allow dataset URLs outside the trusted host list")
    bench_install.set_defaults(func=cmd_bench_install)

    bench_remove = bench_subparsers.add_parser("remove", help="remove an installed benchmark pack")
    bench_remove.add_argument("pack_id", help="pack identifier")
    bench_remove.set_defaults(func=cmd_bench_remove)

    bench_verify = bench_subparsers.add_parser("verify", help="re-verify installed pack hashes against the lockfile")
    bench_verify.set_defaults(func=cmd_bench_verify)

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

    menu = subparsers.add_parser(
        "menu",
        aliases=["interactive"],
        help="open the interactive benchmark menu",
        description="Interactive model/profile/benchmark picker with save-and-run flow.",
    )
    menu.set_defaults(func=cmd_menu)

    if argcomplete is not None:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.update:
        cmd_update(args)

    if args.command is None:
        print_splash()
        parser.print_help()
        print()
        return

    if args.command == "bench" and getattr(args, "bench_command", None) is None:
        print_splash()
        benchpacks.print_help()
        print()
        return

    print_splash()
    args.func(args)
