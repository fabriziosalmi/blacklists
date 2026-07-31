"""Make the repository's modules importable from the tests.

The pipeline scripts live at the repository root and in scripts/, neither of
which is a package. Adding both to sys.path here keeps the imports in the test
modules plain, and keeps the scripts runnable as standalone commands - which is
how the workflows invoke them.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

for path in (REPO_ROOT, REPO_ROOT / 'scripts'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
