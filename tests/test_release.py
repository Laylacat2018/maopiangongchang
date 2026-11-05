"""Release metadata stays consistent across backend, frontend and Git tags."""
import json
from pathlib import Path
from catstudio import __version__

def test_version_is_consistent():
    root=Path(__file__).resolve().parents[1]
    assert (root/'VERSION').read_text().strip()==__version__
    assert json.loads((root/'web/package.json').read_text())['version']==__version__
    lock=json.loads((root/'web/package-lock.json').read_text())
    assert lock['version']==__version__
    assert lock['packages']['']['version']==__version__
