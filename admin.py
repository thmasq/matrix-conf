#!/usr/bin/env python3
"""Matrix Server Administration Tool - Entry Point.

Simple entry point that imports and runs the main application.
"""

from admin.app import MatrixAdminApp

if __name__ == "__main__":
    app = MatrixAdminApp()
    app.run()
