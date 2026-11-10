import multiprocessing as mp
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import numpy as np
from lisa2.checkpoint import read_checkpoint
from lisa2.train import save


def reader(path,stop,errors):
    try:
        while not stop.is_set():
            d=read_checkpoint(path)
            assert np.all(d['vertices']==int(d['step']))
    except Exception as e:
        errors.put(repr(e))


if __name__=='__main__':
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/'best.npz'
        save(path,np.zeros((8,3,3)),np.zeros((8,3)),0,[],{})
        stop=mp.Event();errors=mp.Queue();p=mp.Process(target=reader,args=(path,stop,errors));p.start()
        time.sleep(1)
        for i in range(1,31):
            save(path,np.full((8,3,3),i),np.zeros((8,3)),i,[],{})
            time.sleep(.015)
        stop.set();p.join(10)
        assert not p.is_alive() and p.exitcode==0
        assert errors.empty(), errors.get()
        assert int(read_checkpoint(path)['step'])==30
    print('PASS: concurrent checkpoint reads/writes and complete latest snapshot.')
