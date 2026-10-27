"""Current firmware regression entry point."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('test_firmware_async.py')),run_name='__main__')
