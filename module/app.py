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
#     2. Check OTA server.
#     3. Download update if available.
#     4. Install update.
#     5. Restart device.
#     6. Start the main application.
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import utime
import ujson
from misc import Power
import ota


#------------------------------------------------------------------------------
# Read local manifest
#------------------------------------------------------------------------------

def get_local_manifest():

    try:

        with open("/usr/manifest.json", "r") as file:

            return ujson.load(file)

    except:

        return {
            "project": "Unknown",
            "version": "Unknown",
            "files": []
        }

#------------------------------------------------------------------------------
# Print application banner
#------------------------------------------------------------------------------

def print_banner():

    manifest = get_local_manifest()

    print("")
    print("==================================================")
    print(" Application :", manifest["project"])
    print(" Version     :", manifest["version"])
    print("==================================================")
    print("")

#------------------------------------------------------------------------------
# Main application
#------------------------------------------------------------------------------

def application_loop():

    print("Application is running...")

    while True:

        #--------------------------------------------------------------
        # Place your application code here.
        #--------------------------------------------------------------

        print("Heartbeat")

        utime.sleep(5)


#------------------------------------------------------------------------------
# Application entry
#------------------------------------------------------------------------------

def run():

    print_banner()

    try:

        ota_client = ota.OTA()

        update = ota_client.check_update()

        if update:

            if ota_client.download_update(update["remote_manifest"]):

                if ota_client.install_update(
                    update["local_manifest"],
                    update["remote_manifest"]
                ):
                    restart_device()

                    return

    except Exception as e:

        print("")
        print("OTA Error:", e)

    print("")
    print("Starting application...")
    print("")

    application_loop()


#------------------------------------------------------------------------------
# Restart device
#------------------------------------------------------------------------------

def restart_device():

    print("")
    print("Restart device here.")
    print("")

    Power.powerRestart()