"""Tests for generate.sh - the script that builds the list.

Run for real, offline: the only source is custom/streaming.txt, which
generate.sh reads from the checkout instead of fetching. What is pinned here is
that a step that fails stops the build, because a pipe into tee reports tee's
exit status and a dead step used to look like a finished one.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LOCAL_SOURCE = 'https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/custom/streaming.txt'

pytestmark = pytest.mark.skipif(
    not (shutil.which('bash') and shutil.which('curl')), reason='needs bash and curl')


@pytest.fixture
def workdir(tmp_path):
    for name in ('generate.sh', 'sanitize.py', 'whitelist.py', 'whitelist.txt'):
        shutil.copy(REPO / name, tmp_path / name)
    for name in ('scripts', 'sources', 'custom'):
        shutil.copytree(REPO / name, tmp_path / name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (tmp_path / 'blacklists.fqdn.urls').write_text(LOCAL_SOURCE + '\n', encoding='utf-8')
    return tmp_path


def replace_main(path, body):
    """Keep the module importable and change only what running it does.

    sanitize.py is imported by the protected-name step further down the
    build; replacing the whole file would fail that import and stop the build
    for a reason that has nothing to do with the check under test.
    """
    source = path.read_text(encoding='utf-8')
    head, sep, _ = source.partition('if __name__ == "__main__":')
    assert sep, f'no __main__ block in {path.name}'
    path.write_text(head + sep + '\n' + ''.join(f'    {line}\n' for line in body.splitlines()),
                    encoding='utf-8')


def run_generate(workdir):
    env = dict(os.environ)
    # The python3 generate.sh calls must be the one running the tests, the one
    # that has tldextract.
    env['PATH'] = os.path.dirname(sys.executable) + os.pathsep + env.get('PATH', '')
    return subprocess.run(['bash', 'generate.sh'], cwd=workdir, env=env,
                          capture_output=True, text=True, timeout=300)


def test_a_clean_build_produces_the_list(workdir):
    result = run_generate(workdir)
    assert result.returncode == 0, result.stdout[-2000:]
    lines = (workdir / 'all.fqdn.blacklist').read_text(encoding='utf-8').splitlines()
    domains = [line for line in lines if line and not line.startswith('#')]
    assert '123movies.is' in domains
    assert any(line.startswith('# Domains: ') for line in lines)


def test_a_sanitize_that_dies_mid_write_stops_the_build(workdir):
    """The failure that used to ship: half an output.txt, then a crash.
    Break-test: remove the PIPESTATUS check after sanitize.py and this fails."""
    replace_main(workdir / 'sanitize.py',
                 "open('output.txt', 'w').write('half.example\\n')\n"
                 "raise SystemExit('killed while writing')")
    result = run_generate(workdir)
    assert result.returncode != 0
    assert 'sanitize.py failed' in result.stdout
    assert not (workdir / 'all.fqdn.blacklist').exists()


def test_a_whitelist_step_that_dies_stops_the_build(workdir):
    """Break-test: remove the PIPESTATUS check after whitelist.py and this fails."""
    (workdir / 'whitelist.py').write_text(
        "open('filtered_blacklist.txt', 'w').write('half.example\\n')\n"
        "raise SystemExit('killed while writing')\n", encoding='utf-8')
    result = run_generate(workdir)
    assert result.returncode != 0
    assert 'whitelist.py failed' in result.stdout


def test_a_stale_output_from_an_earlier_run_is_not_shipped(workdir):
    """A sanitize.py that writes nothing must not let last run's file through."""
    (workdir / 'output.txt').write_text('stale.example\n', encoding='utf-8')
    replace_main(workdir / 'sanitize.py', 'pass')
    result = run_generate(workdir)
    assert result.returncode != 0


def test_it_installs_nothing_and_needs_no_sudo():
    """The build used to apt-get install with sudo on every run."""
    script = (REPO / 'generate.sh').read_text(encoding='utf-8')
    code = [line for line in script.splitlines() if not line.lstrip().startswith('#')]
    for forbidden in ('sudo', 'apt-get', 'pip install', 'pip3 install', 'brew install'):
        assert not any(forbidden in line and 'echo' not in line for line in code), forbidden
