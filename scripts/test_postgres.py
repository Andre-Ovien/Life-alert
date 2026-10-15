"""Run the suite in a temporary, socket-only PostgreSQL cluster; requires local PostgreSQL tools."""
from pathlib import Path
import os, socket, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
(root/'.runtime').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='pg-check-', dir=root/'.runtime') as temp:
    base=Path(temp); data=base/'data'; log=base/'postgres.log'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    subprocess.run(['initdb','-D',str(data),'-A','trust','-U','lifealert_test','--no-locale','--encoding=UTF8'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['pg_ctl','-D',str(data),'-l',str(log),'-o',f"-p {port} -k {base} -h ''",'-w','start'],check=True,stdout=subprocess.DEVNULL)
    try:
        env={**os.environ,'POSTGRES_DB':'postgres','POSTGRES_USER':'lifealert_test','POSTGRES_HOST':str(base),'POSTGRES_PORT':str(port),'POSTGRES_PASSWORD':''}
        result=subprocess.run([str(root/'.venv/bin/python'),'manage.py','test','--verbosity','1'],cwd=root/'backend',env=env)
    finally:
        subprocess.run(['pg_ctl','-D',str(data),'-m','fast','-w','stop'],check=True,stdout=subprocess.DEVNULL)
    raise SystemExit(result.returncode)
