"""Minimized regressions discovered by seeded mutation/state fuzzing."""

import copy

import numpy as np
import pytest
import figgyplot as figgy


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_failed_heatmap_registration_preserves_entire_document(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.imshow(np.ones((2, 2)), id="existing")
        before, revision, columns = (
            figure.get_settings(),
            figure.revision,
            figure.info["columns"],
        )
        next_id = figure._next_series
        for invalid_id in (0, "existing", "chart_title", ""):
            with pytest.raises(ValueError, match="series ID"):
                ax.imshow(np.array([[10.0, 20.0], [30.0, 40.0]]), id=invalid_id)
            assert figure.get_settings() == before and figure.revision == revision
            assert figure.info["columns"] == columns and figure._next_series == next_id
        ax.set_title("Recovered")
        if backend == "native":
            assert figure.render_rgba().size


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_finite_json_cannot_overflow_renderer_float_fields(backend):
    with figgy.Figure(backend=backend) as figure:
        figure.axes[0].plot([0, 1], id="line")
        before, revision = figure.get_settings(), figure.revision
        bad = copy.deepcopy(before)
        bad["config"]["top_x"]["label_style"]["label_offset_y"] = 1e300
        with pytest.raises(ValueError, match="non-finite or out-of-range"):
            figure.apply_settings(bad)
        bad = copy.deepcopy(before)
        bad["series"][0]["render_type"]["Line"]["line"]["line_width"] = 1e300
        with pytest.raises(ValueError, match="non-finite or out-of-range"):
            figure.apply_settings(bad)
        for size in (0, -1):
            bad = copy.deepcopy(before)
            bad["config"]["chart_title"]["text"]["font_size"] = size
            with pytest.raises(ValueError, match="font_size.*greater than 0"):
                figure.apply_settings(bad)
        assert figure.get_settings() == before and figure.revision == revision
        figure.apply_settings(figure.get_settings())


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_negative_title_margin_cannot_expand_colorbar_raster_outside_canvas(backend):
    with figgy.Figure(backend=backend) as figure:
        figure.axes[0].imshow(np.ones((2, 2), dtype=np.float32))
        before, revision = figure.get_settings(), figure.revision
        for margin in (-1, -1e38):
            bad = copy.deepcopy(before)
            bad["config"]["chart_title"]["top_margin"] = margin
            with pytest.raises(ValueError, match="chart_title.top_margin.*nonnegative"):
                figure.apply_settings(bad)
            assert figure.get_settings() == before and figure.revision == revision
        if backend == "native":
            assert figure.render_rgba().size


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_large_valid_font_is_not_rejected_by_an_arbitrary_size_limit(backend):
    with figgy.Figure(backend=backend) as figure:
        settings = figure.get_settings()
        settings["config"]["chart_title"]["text"]["font_size"] = 8193
        figure.apply_settings(settings)
        assert (
            figure.get_settings()["config"]["chart_title"]["text"]["font_size"] == 8193
        )


def test_invalid_target_types_and_browser_host_methods_have_domain_errors():
    with figgy.Figure(backend="webgpu") as figure:
        for value in (None, 1, [], {}):
            with pytest.raises(ValueError, match="editable target"):
                figure.update(value, text="bad")
            with pytest.raises(ValueError, match="Python identifier"):
                figure.to_code(value)
        for action in (
            lambda: figure.select_object("chart_title"),
            lambda: figure.drag("chart_title", 1, 1),
            lambda: figure.select(1, 1),
        ):
            with pytest.raises(RuntimeError, match="WebGPU widget"):
                action()


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_unrepresentable_source_data_and_all_nonfinite_arrays_are_atomic(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        before, revision = figure.get_settings(), figure.revision
        for values, message in (
            ([1.0, 1e300], "hi/lo representation"),
            ([np.nan, np.inf], "no finite values"),
        ):
            with pytest.raises(ValueError, match=message):
                ax.plot([0, 1], values)
            assert figure.get_settings() == before and figure.revision == revision
            assert figure.info["columns"] == 0
        ax.plot([0, 1], [0, 1])


def test_heatmap_allocation_failure_preserves_existing_chart_and_pool():
    with figgy.Figure(backend="native") as figure:
        figure.axes[0].plot([0, 1], [0, 1])
        limit = figure.info["adapter"]["maximum_column_pool_bytes"]
        if limit > 128 * 1024**2:
            pytest.skip("bound allocation test to software adapter limit")
        before, revision = figure.get_settings(), figure.revision
        used, columns = figure.info["pool_used_bytes"], figure.info["columns"]
        with pytest.raises(MemoryError, match="requested_gpu_bytes"):
            figure.axes[0].imshow(np.zeros((2, limit // 16 + 1), dtype=np.float32))
        assert figure.get_settings() == before and figure.revision == revision
        assert (
            figure.info["pool_used_bytes"] == used and figure.info["columns"] == columns
        )
        assert figure.render_rgba().size


@pytest.mark.parametrize("backend", ["native", "webgpu"])
def test_unsafe_ranges_and_geometry_sizes_are_rejected_without_poisoning(backend):
    with figgy.Figure(backend=backend) as figure:
        ax = figure.axes[0]
        ax.plot([0, 1], [0, 1])
        before, revision = figure.get_settings(), figure.revision
        for action in (lambda: figure.fit(1e300), lambda: ax.set_xlim(-1e300, 1e300)):
            with pytest.raises(ValueError, match="representation range"):
                action()
            assert figure.get_settings() == before and figure.revision == revision
        bad = copy.deepcopy(before)
        bad["series"][0]["render_type"]["Line"]["line"]["line_width"] = -1
        with pytest.raises(ValueError, match="nonnegative"):
            figure.apply_settings(bad)
        assert figure.get_settings() == before and figure.revision == revision
        if backend == "native":
            assert figure.render_rgba().size


def test_wrong_host_flags_and_async_timeouts_fail_before_transfer():
    import asyncio

    with figgy.Figure(backend="webgpu") as figure:
        for value in (None, [], {}, "typo", float("nan"), float("inf"), 0, -1):
            with pytest.raises(ValueError, match="timeout"):
                asyncio.run(figure.prepare_async(timeout=value))
            assert not figure._native.sealed and not figure._widgets
        with pytest.raises(ValueError, match="auto_prepare"):
            figure.widget(auto_prepare="typo")
        with pytest.raises(ValueError, match="widget backend"):
            figure.widget(backend="typo")
        with pytest.raises(ValueError, match="block"):
            figure.show(block="typo")
        assert not figure._native.sealed and not figure._widgets
        with pytest.raises(TimeoutError, match="display the widget"):
            asyncio.run(figure.prepare_async(timeout=0.01))


def test_small_randomized_campaign_in_subprocess(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_randomized.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--seeds",
            "2",
            "--steps",
            "40",
            "--timeout",
            "20",
            "--artifacts",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    report = json.loads((tmp_path / "summary.json").read_text())
    assert result.returncode == 0, (result.stdout, result.stderr, report)
    assert report["passed"] and report["counts"]["threads_joined"] == 16
