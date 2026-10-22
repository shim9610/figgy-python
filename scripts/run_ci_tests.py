#!/usr/bin/env python3
"""Run the complete pytest collection once, with past failures first."""
import json
from pathlib import Path
import sys

import pytest


PRIORITY = (
    'tests/test_interaction_parity.py::test_surface_readiness_rejects_matching_pre_resize_css_and_backing',
    'tests/test_interaction_parity.py::test_annotation_mouse_input_uses_live_layout_after_resize',
    'tests/test_interaction_parity.py::test_inline_editor_resize_uses_current_units_and_applies_real_edits[1]',
    'tests/test_interaction_parity.py::test_inline_editor_resize_uses_current_units_and_applies_real_edits[2]',
    'tests/test_interaction_parity.py::test_inline_text_resize_multiline_and_existing_format_in_both_hosts[radial]',
    'tests/test_interaction_parity.py::test_inactive_overlay_objects_can_be_edited_and_dragged_directly[native]',
    'tests/test_packaged_assets.py',
    'tests/test_radial_desktop.py::test_click_remains_a_short_press_when_frames_are_slow',
    'tests/test_interaction_parity.py::test_radial_detail_tree_selection_edits_only_the_chosen_child[native]',
    'tests/test_interaction_parity.py::test_annotation_drawing_editing_and_cancel_in_both_hosts[radial]',
)


class PriorityFirst:
    def pytest_addoption(self, parser):
        parser.addoption('--ci-test-plan', default='ci-results/test-plan.json',
                         help='Record every collected node ID before and after ordering')

    def pytest_collection_modifyitems(self, config, items):
        original = [item.nodeid for item in items]
        if len(set(original)) != len(original):
            raise pytest.UsageError('CI collection contains duplicate test node IDs')

        def rank(item):
            return next((i for i, key in enumerate(PRIORITY)
                         if item.nodeid == key or item.nodeid.startswith(key + '::')), len(PRIORITY))

        found = {rank(item) for item in items}
        missing = [key for i, key in enumerate(PRIORITY) if i not in found]
        if missing:
            raise pytest.UsageError('CI collection is missing required priority cases: ' + ', '.join(missing))
        items.sort(key=rank)
        ordered = [item.nodeid for item in items]
        plan = Path(config.getoption('--ci-test-plan'))
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(json.dumps(dict(count=len(items), original=original, ordered=ordered), indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(pytest.main(sys.argv[1:], plugins=[PriorityFirst()]))
