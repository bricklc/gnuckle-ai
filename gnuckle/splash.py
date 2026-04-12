"""The splash screen. The first thing ape see."""

from gnuckle import __version__
from gnuckle.ape import ape_phrase

BOX_WIDTH = 70

TITLE_ART = [
    "   ██████╗ ███╗   ██╗██╗   ██╗ ██████╗██╗  ██╗██╗     ███████╗",
    "  ██╔════╝ ████╗  ██║██║   ██║██╔════╝██║ ██╔╝██║     ██╔════╝",
    "  ██║  ███╗██╔██╗ ██║██║   ██║██║     █████╔╝ ██║     █████╗  ",
    "  ██║   ██║██║╚██╗██║██║   ██║██║     ██╔═██╗ ██║     ██╔══╝  ",
    "  ╚██████╔╝██║ ╚████║╚██████╔╝╚██████╗██║  ██╗███████╗███████╗",
    "   ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝",
]

CONTENT_LINES = [
    "",
    "       A G E N T I C   A I   B E N C H M A R K",
    "       ape drag knuckle on keyboard. benchmark happen.",
    "",
    "  ┌──────────────────────────────────────────────────────────┐",
    "  │  KV Cache Quantization  ·  Tool-Call Stress Test         │",
    "  │  f16 -> q8_0 -> q4_0 -> turbo3                           │",
    "  │                                                          │",
    "  │  Metrics: tok/s · TTFT · VRAM · Tool Accuracy            │",
    "  │  also: banana consumption per token (theoretical)        │",
    "  └──────────────────────────────────────────────────────────┘",
    "",
    "  Usage:",
    "    gnuckle benchmark --model my_model.gguf",
    "    gnuckle visualize ./benchmark_results/",
    "    gnuckle --help",
    "    gnuckle menu",
    "",
    "  Install:",
    "    pip install gnuckle",
    "",
    "      🍌 vibe-coded by apes with reckless optimism 🍌",
    "      accidentally GNU, intentionally simian",
]


def _boxed_line(text: str = "") -> str:
    return f"║{text:<{BOX_WIDTH}}║"


def build_splash(version: str) -> str:
    lines = ["╔" + ("═" * BOX_WIDTH) + "╗"]
    lines.append(_boxed_line())
    for line in TITLE_ART:
        lines.append(_boxed_line(line))
    for line in CONTENT_LINES:
        lines.append(_boxed_line(line))
    lines.append(_boxed_line(f"                                    v{version}  gnuckle.ai"))
    lines.append("╚" + ("═" * BOX_WIDTH) + "╝")
    return "\n".join(lines)


def print_splash():
    print(build_splash(__version__))
    print(f"  {ape_phrase('startup')}\n")
