#!/usr/bin/env python3
"""Require every collected test to pass exactly once across CI shards."""
import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def validate(root, shards):
    expected = None
    executed = []
    selected = []
    for index in range(shards):
        directory = Path(root) / f'shard-{index}'
        plan = json.loads((directory / 'test-plan.json').read_text())
        if plan['shard'] != {'index': index, 'count': shards}:
            raise ValueError(f'Wrong shard identity: {index}')
        original, ordered = plan['original'], plan['ordered']
        if len(set(original)) != len(original) or Counter(original) != Counter(ordered):
            raise ValueError('Duplicate or omitted collection IDs')
        if plan['count'] != len(ordered):
            raise ValueError('Wrong collection count')
        if not original:
            raise ValueError('Empty collection')
        if expected is None:
            expected = ordered
        if ordered != expected:
            raise ValueError('Shards collected different test plans')
        if plan['selected'] != ordered[index::shards]:
            raise ValueError('Wrong shard selection')
        selected.extend(plan['selected'])
        report = ET.parse(directory / 'junit.xml')
        cases = report.findall('.//testcase')
        for case in cases:
            if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')):
                raise ValueError('Nonpassing test in JUnit report')
        actual = []
        for case in cases:
            ids = [prop.get('value') for prop in case.findall('./properties/property')
                   if prop.get('name') == 'ci_nodeid']
            if len(ids) != 1:
                raise ValueError('Missing or duplicate exact JUnit node ID')
            actual.append(ids[0])
        if actual != plan['selected']:
            raise ValueError(f'JUnit execution differs from selected test IDs: {index}')
        executed.extend(actual)
    if Counter(selected) != Counter(expected) or Counter(executed) != Counter(expected):
        raise ValueError('Execution omits or duplicates test IDs')
    return {'count': len(expected), 'shards': shards, 'omitted': 0, 'duplicates': 0,
            'nonpassing': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--shards', type=int, required=True)
    args = parser.parse_args()
    if args.shards < 1:
        parser.error('--shards must be positive')
    result = validate(args.root, args.shards)
    args.root.joinpath('execution-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
