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

if "/usr" not in sys.path:
    sys.path.append("/usr")


import app

#------------------------------------------------------------------------------
# Start application
#------------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()