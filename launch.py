"""One-command cross-platform bootstrap: python launch.py"""
import os
from pathlib import Path
import subprocess
import sys
import venv

def main():
    root=Path(__file__).resolve().parent
    if sys.version_info < (3,11): raise SystemExit('Install Python 3.11 or later first.')
    envdir=root/'.venv'
    python=envdir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists(): venv.EnvBuilder(with_pip=True).create(envdir)
    requirement=root/'requirements.txt'
    import hashlib
    digest=hashlib.sha256(requirement.read_bytes()).hexdigest()
    marker=envdir/'.boardroom-dependencies'
    if not marker.exists() or marker.read_text()!=digest:
        subprocess.check_call([str(python),'-m','pip','install','-r',str(requirement)])
        marker.write_text(digest)
    env=os.environ.copy(); env['BOARDROOM_LOCAL']='1'
    subprocess.call([str(python),'-m','streamlit','run',str(root/'app.py'),'--server.address=127.0.0.1'],cwd=root,env=env)

if __name__=='__main__': main()
