"""Entry points for the installed package.

- annex13-ui:   minimal Streamlit GUI
- annex13-store: GraphQL store (see store.py)
"""

import os
import subprocess
import sys


def ui():
    port = os.environ.get("ANNEX13_UI_PORT", "8600")
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    sys.exit(subprocess.call([
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.headless", "true", "--server.port", port,
        "--server.address", os.environ.get("ANNEX13_UI_HOST", "0.0.0.0"),
    ]))
