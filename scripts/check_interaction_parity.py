"""Reject host interaction changes without the other host and shared UI coverage."""
import argparse
from pathlib import PurePosixPath
import subprocess

NATIVE = {'src/desktop.rs', 'src/editor.rs', 'src/bounded_host.rs',
          'src/bounded.rs', 'src/interaction.rs', 'src/drawing.rs', 'src/navigation.rs', 'src/radial_host.rs', 'src/radial_editor.rs', 'src/radial.rs', 'src/selection.rs'}
BROWSER = {'python/figgyplot/webgpu.js', 'python/figgyplot/editor.css', 'python/figgyplot/widget.py', 'src/notebook.rs'}
SHARED = {'python/figgyplot/figure.py', 'python/figgyplot/_charts.py',
          'python/figgyplot/notebook.py', 'src/lib.rs'}
CONTRACT = {'tests/test_interaction_parity.py'}


def check(paths):
    paths = set(paths)
    native, browser = paths & NATIVE, paths & BROWSER
    errors = []
    if bool(native) != bool(browser):
        missing = 'Jupyter/WebGPU' if native else 'native desktop'
        errors.append(f'Interaction changes require the {missing} implementation in the same PR.')
    if paths & (NATIVE | BROWSER | SHARED) and not paths & CONTRACT:
        errors.append('Update tests/test_interaction_parity.py with the shared native/browser behavior.')
    return errors


def changed_paths(base, head):
    # Include both old and new names: moving/deleting a host must not bypass the guard.
    result = subprocess.run(['git', 'diff', '--name-only', '--no-renames', '-z',
                             base, head], check=True, capture_output=True)
    return {str(PurePosixPath(p.decode())) for p in result.stdout.split(b'\0') if p}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='PR base SHA (not HEAD~1)')
    parser.add_argument('--head', default='HEAD')
    args = parser.parse_args()
    errors = check(changed_paths(args.base, args.head))
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Native/Jupyter change pairing passed; behavioral parity runs in Linux integration.')


if __name__ == '__main__':
    main()
