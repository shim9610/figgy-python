"""The synchronization guard must reject either one-sided host change."""
import importlib.util
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location('guard', Path(__file__).parents[1]/'scripts/check_interaction_parity.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_rejects_either_one_sided_change_even_with_tests():
    for host in ['src/bounded_host.rs', 'python/figgyplot/webgpu.js']:
        assert any('implementation' in e for e in guard.check([host, 'tests/test_interaction_parity.py']))


def test_requires_behavioral_coverage_not_just_two_files():
    pair = ['src/desktop.rs', 'python/figgyplot/webgpu.js']
    assert guard.check(pair)
    assert not guard.check(pair + ['tests/test_interaction_parity.py'])
    assert guard.check(['python/figgyplot/_charts.py'])
    assert not guard.check(['README.md', 'docs/HOSTS.md'])


def test_deleting_or_renaming_a_host_is_still_a_change(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q'); git('config', 'user.email', 'test@example.invalid'); git('config', 'user.name', 'Test')
    (tmp_path/'src').mkdir(); (tmp_path/'src/desktop.rs').write_text('host')
    git('add', '.'); git('commit', '-qm', 'base'); base=git('rev-parse', 'HEAD')
    git('mv', 'src/desktop.rs', 'src/moved.rs'); git('commit', '-qm', 'move')
    result = subprocess.run([sys.executable, str(Path(guard.__file__).resolve()), '--base', base],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'Jupyter/WebGPU' in result.stderr
