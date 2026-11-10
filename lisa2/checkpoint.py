"""Read snapshots without keeping a Windows file handle open during training."""
from io import BytesIO
from pathlib import Path
import os
import time
import numpy as np


def read_checkpoint(path):
    for attempt in range(30):
        try:
            payload=Path(path).read_bytes()
            break
        except (PermissionError,FileNotFoundError):
            if attempt==29: raise
            time.sleep(.05)
    with np.load(BytesIO(payload)) as data:
        return {key:data[key] for key in data.files}


def atomic_replace(source,destination):
    for attempt in range(30):
        try:
            os.replace(source,destination)
            return
        except PermissionError:
            if attempt==29: raise
            time.sleep(.05)
