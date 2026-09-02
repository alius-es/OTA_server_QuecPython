#==============================================================================
# File: main.py
#
# Description:
#     Entry point of the QuecPython application.
#
#     This file should remain as small as possible.
#     All application logic is located in app.py.
#
#==============================================================================


#------------------------------------------------------------------------------
# Import application module
#------------------------------------------------------------------------------

import sys

APP_DIR = "/usr/app"

if "/usr" not in sys.path:
    sys.path.append("/usr")

if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

import app

#------------------------------------------------------------------------------
# Start application
#------------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()