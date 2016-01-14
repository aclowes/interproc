"""
InterProc provides tools for reading from and writing to subprocesses.
"""
from .async import run_subprocess_shell
from .polling import UnixInteractiveProcess
