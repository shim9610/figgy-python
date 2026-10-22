"""CI must fail closed when collected, selected and executed IDs disagree."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
validate = runpy.run_path(str(ROOT / 'scripts/check_ci_execution.py'))['validate']


@pytest.fixture
def reports(tmp_path):
    ids = [f'tests/test_sample.py::test_case[{i}]' for i in range(6)]
    for index in range(2):
        directory = tmp_path / f'shard-{index}'
        directory.mkdir()
        selected = ids[index::2]
        plan = dict(count=6, original=ids, ordered=ids, selected=selected,
                    shard=dict(index=index, count=2))
        (directory / 'test-plan.json').write_text(json.dumps(plan))
        report = ET.Element('testsuites')
        suite = ET.SubElement(report, 'testsuite')
        for nodeid in selected:
            case = ET.SubElement(suite, 'testcase', name=nodeid.split('::')[1])
            props = ET.SubElement(case, 'properties')
            ET.SubElement(props, 'property', name='ci_nodeid', value=nodeid)
        ET.ElementTree(report).write(directory / 'junit.xml')
    return tmp_path


def test_complete_execution_audit(reports):
    assert validate(reports, 2) == dict(count=6, shards=2, omitted=0, duplicates=0, nonpassing=0)


@pytest.mark.parametrize('fault', ['missing_shard', 'wrong_shard', 'different_plan',
    'duplicate_collection', 'wrong_selection', 'missing_execution', 'duplicate_execution',
    'failure', 'error', 'skipped', 'missing_identity', 'duplicate_identity'])
def test_execution_audit_rejects_incomplete_or_nonpassing_results(reports, fault):
    directory = reports / 'shard-1'
    plan_path, xml_path = directory / 'test-plan.json', directory / 'junit.xml'
    plan = json.loads(plan_path.read_text())
    report = ET.parse(xml_path)
    suite = report.find('testsuite')
    case = suite.find('testcase')
    if fault == 'missing_shard':
        xml_path.unlink()
    elif fault == 'wrong_shard':
        plan['shard']['index'] = 0
    elif fault == 'different_plan':
        plan['ordered'] = list(reversed(plan['ordered']))
    elif fault == 'duplicate_collection':
        plan['original'].append(plan['original'][0])
    elif fault == 'wrong_selection':
        plan['selected'] = plan['ordered'][::2]
    elif fault == 'missing_execution':
        suite.remove(case)
    elif fault == 'duplicate_execution':
        suite.append(case)
    elif fault in ('failure', 'error', 'skipped'):
        ET.SubElement(case, fault)
    elif fault == 'missing_identity':
        case.remove(case.find('properties'))
    else:
        props = case.find('properties')
        ET.SubElement(props, 'property', name='ci_nodeid', value=plan['selected'][0])
    plan_path.write_text(json.dumps(plan))
    if fault != 'missing_shard':
        report.write(xml_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        validate(reports, 2)


def test_actual_pytest_shards_produce_exact_auditable_execution(tmp_path):
    (tmp_path / 'test_sample.py').write_text('import pytest\n'
        '@pytest.mark.parametrize("value", range(6))\n'
        'def test_case(value): assert value >= 0\n')
    # Exercise the actual plugin and pytest JUnit writer, without the unrelated
    # repository priority groups required by the full CI collection.
    for index in range(2):
        directory = tmp_path / f'shard-{index}'
        directory.mkdir()
        code = ('import sys; sys.path.insert(0, sys.argv[1]); '
                'import pytest, run_ci_tests as runner; '
                'runner.PRIORITY=("test_sample.py",); '
                'raise SystemExit(pytest.main(sys.argv[2:], plugins=[runner.PriorityFirst()]))')
        # CI basetemp is inside the repository: fix the nested collection root
        # so parent project discovery cannot prefix the sample node IDs.
        result = subprocess.run([sys.executable, '-c', code, str(ROOT / 'scripts'), '-q',
            f'--rootdir={tmp_path}',
            '--ci-shard-count=2', f'--ci-shard-index={index}',
            f'--ci-test-plan={directory / "test-plan.json"}',
            f'--junitxml={directory / "junit.xml"}', 'test_sample.py'],
            cwd=tmp_path, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
    assert validate(tmp_path, 2)['count'] == 6
