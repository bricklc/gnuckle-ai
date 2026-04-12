from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from gnuckle.menu import (
    _apply_profile_to_state,
    default_menu_state,
    menu_state_to_profile,
    render_banana_loading_bar,
    render_menu_summary,
    run_benchmark_from_menu_state,
)
from gnuckle.profile import list_profiles, load_profile, profiles_dir, save_profile


class MenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home_patch = patch.dict(os.environ, {"USERPROFILE": self.tmpdir.name, "HOME": self.tmpdir.name})
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def test_render_banana_loading_bar_has_five_slots(self) -> None:
        self.assertEqual(render_banana_loading_bar(0), "[·····]")
        self.assertEqual(render_banana_loading_bar(3), "[🍌🍌🍌··]")
        self.assertEqual(render_banana_loading_bar(5), "[🍌🍌🍌🍌🍌]")

    def test_menu_state_round_trips_to_profile_shape(self) -> None:
        state = default_menu_state()
        state["mode"] = "agentic"
        state["model_path"] = "C:/models/demo.gguf"
        state["sampler_preset"] = "nemotron"
        state["sampler"] = {"temp": 0.7}
        state["quality_bench_ids"] = ["wikitext2_ppl"]
        profile = menu_state_to_profile(state)
        self.assertEqual(profile["benchmark_mode"], "agentic")
        self.assertEqual(profile["sampler_preset"], "nemotron")
        self.assertEqual(profile["quality_bench_ids"], ["wikitext2_ppl"])

        merged = _apply_profile_to_state(default_menu_state(), profile)
        self.assertEqual(merged["mode"], "agentic")
        self.assertEqual(merged["sampler_preset"], "nemotron")
        self.assertEqual(merged["quality_bench_ids"], ["wikitext2_ppl"])

    def test_render_menu_summary_surfaces_key_choices(self) -> None:
        state = default_menu_state()
        state["model_path"] = "C:/models/demo.gguf"
        state["server_path"] = "C:/bin/llama-server.exe"
        state["quality_bench_ids"] = ["wikitext2_ppl"]
        summary = render_menu_summary(state)
        self.assertIn("model=demo.gguf", summary)
        self.assertIn("server=llama-server.exe", summary)
        self.assertIn("quality=wikitext2_ppl", summary)

    def test_profile_save_and_list_helpers_round_trip(self) -> None:
        target = profiles_dir() / "menu-test.json"
        saved = save_profile(
            target,
            {
                "benchmark_mode": "legacy",
                "model_path": "model.gguf",
                "server_path": "server.exe",
            },
        )
        self.assertTrue(target.exists())
        listed = list_profiles()
        self.assertIn(target, listed)
        loaded = load_profile(saved)
        self.assertTrue(loaded["model_path"].endswith("model.gguf"))

    def test_run_benchmark_from_menu_state_forwards_cache_selection(self) -> None:
        state = default_menu_state()
        state["model_path"] = "C:/models/demo.gguf"
        state["server_path"] = "C:/bin/llama-server.exe"
        state["cache_types"] = ["f16", "turbo3"]
        state["quality_bench_ids"] = ["wikitext2_ppl"]
        with patch("gnuckle.menu.run_full_benchmark") as mocked:
            run_benchmark_from_menu_state(state)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["cache_labels"], ["f16", "turbo3"])
        self.assertEqual(kwargs["quality_bench_ids"], ["wikitext2_ppl"])
