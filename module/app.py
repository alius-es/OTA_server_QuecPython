#==============================================================================
# File: app.py
#
# Description:
#     Main application module.
#
#     This module controls the application startup sequence.
#
# Startup sequence:
#
#     1. Print application information.
#     2. Check OTA server for a new version.
#     3. If an update exists:
#            - download update
#            - install update
#            - restart device
#     4. Start the main application.
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import utime

import ota


#------------------------------------------------------------------------------
# Application information
#------------------------------------------------------------------------------

APP_NAME = "QuecPython OTA Demo"
APP_VERSION = "1.0.0"


#------------------------------------------------------------------------------
# Print application banner
#------------------------------------------------------------------------------

def print_banner():

    print("")
    print("==================================================")
    print(" Application :", APP_NAME)
    print(" Version     :", APP_VERSION)
    print("==================================================")
    print("")


#------------------------------------------------------------------------------
# Main application
#------------------------------------------------------------------------------

def application_loop():

    print("Application is running...")

    while True:

        # -------------------------------------------------------------
        # Place your application code here.
        # -------------------------------------------------------------

        print("Heartbeat")

        utime.sleep(5)


#------------------------------------------------------------------------------
# Application entry
#------------------------------------------------------------------------------

def run():

    print_banner()

    print("Checking OTA server...")

    try:

        ota_client = ota.OTA()

        ota_client.check_update()

    except Exception as e:

        print("OTA Error:", e)

    print("")

    print("Starting application...")
    print("")

    application_loop()