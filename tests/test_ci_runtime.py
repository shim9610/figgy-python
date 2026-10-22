"""CI package setup must ignore image vendor feeds without ignoring APT errors."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/install_ci_runtime.sh'


def run_setup(tmp_path,fail=False):
    log=tmp_path/'apt-calls.jsonl'
    sudo=tmp_path/'sudo'
    sudo.write_text('#!'+sys.executable+'\n'+'''
import json,os,pathlib,sys
args=sys.argv[1:]
source=next(v.split('=',1)[1] for v in args if v.startswith('Dir::Etc::sourcelist='))
with open(os.environ['APT_CALLS'],'a') as f:
 f.write(json.dumps(dict(args=args,sources=pathlib.Path(source).read_text()))+'\\n')
if os.environ.get('APT_FAIL')=='1':sys.exit(100)
''')
    sudo.chmod(0o755)
    env={**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ['PATH'],'APT_CALLS':str(log),'APT_FAIL':str(int(fail))}
    result=subprocess.run(['bash',str(SCRIPT)],env=env,capture_output=True,text=True,timeout=10)
    return result,[json.loads(line) for line in log.read_text().splitlines()]


def apt_plan(tmp_path,call,isolate):
    if shutil.which('apt-get') is None:pytest.skip('APT URI planning requires Linux APT')
    source=tmp_path/'runtime.sources';source.write_text(call['sources'])
    vendor=tmp_path/'image-sources';vendor.mkdir(exist_ok=True)
    # These reproduce two image-owned feeds. --print-uris never contacts them.
    (vendor/'vendor.list').write_text('deb https://packages.microsoft.com/ubuntu/24.04/prod noble main\ndeb http://azure.archive.ubuntu.com/ubuntu noble main\n')
    lists=tmp_path/'lists';lists.mkdir(exist_ok=True)
    options=call['args'][1:-1]
    options=[('Dir::Etc::sourcelist='+str(source)) if v.startswith('Dir::Etc::sourcelist=') else v for v in options]
    if not isolate:
        at=options.index('Dir::Etc::sourceparts=-');del options[at-1:at+1]
    command=['apt-get','-o','Dir::State::lists='+str(lists),'-o','Dir::Etc::sourceparts='+str(vendor),*options,'--print-uris','update']
    result=subprocess.run(command,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    return result.stdout


def test_actual_apt_plan_uses_only_official_signed_ubuntu_sources(tmp_path):
    result,calls=run_setup(tmp_path)
    assert result.returncode==0,result.stderr
    assert len(calls)==2 and calls[0]['args'][-1]=='update'
    assert 'install' in calls[1]['args'] and 'fonts-noto-cjk' in calls[1]['args']
    assert calls[0]['sources']==calls[1]['sources']
    assert calls[0]['sources'].count('Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg')==2
    plan=apt_plan(tmp_path,calls[0],True)
    for suite in ['noble','noble-updates','noble-backports','noble-security']:assert '/'+suite+'/InRelease' in plan
    assert 'https://archive.ubuntu.com/ubuntu/' in plan and 'https://security.ubuntu.com/ubuntu/' in plan
    assert 'azure.archive' not in plan and 'packages.microsoft' not in plan


def test_apt_plan_oracle_detects_vendor_sources_if_isolation_is_removed(tmp_path):
    result,calls=run_setup(tmp_path);assert result.returncode==0,result.stderr
    plan=apt_plan(tmp_path,calls[0],False)
    assert 'azure.archive.ubuntu.com' in plan and 'packages.microsoft.com' in plan


def test_official_repository_failure_stops_before_package_installation(tmp_path):
    result,calls=run_setup(tmp_path,True)
    assert result.returncode==100
    assert len(calls)==1 and calls[0]['args'][-1]=='update'
