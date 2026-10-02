import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from lite.gui import App


def lock_instance(directory):
    """One process per database, lock is released by the OS after a crash."""
    f=open(directory/'app.lock','a+b')
    f.seek(0);f.write(b'0');f.flush();f.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        f.close();raise RuntimeError('AdRadar Lite sudah terbuka untuk folder data ini.')
    return f

if __name__=='__main__':
    directory=Path(os.environ.get('ADRADAR_LITE_DATA',Path(__file__).parent/'data'))
    directory.mkdir(parents=True,exist_ok=True)
    root=tk.Tk()
    try:
        lock=lock_instance(directory)
    except RuntimeError as exc:
        root.withdraw();messagebox.showerror('AdRadar Lite',str(exc));root.destroy()
    else:
        try:App(root,directory);root.mainloop()
        finally:lock.close()
