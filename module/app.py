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
#     2. Check for a completed pending OTA update.
#     3. Remove obsolete files only after the target version is confirmed.
#     4. Check the network.
#     5. Check OTA server.
#     6. Download update if available.
#     7. Install update.
#     8. Restart device.
#     9. Start the main application.
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import utime
import ujson
import ota
import config
import checkNet


#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

NETWORK_STAGES = {
    1: "SIM card",
    2: "Network registration",
    3: "PDP context"
}


#------------------------------------------------------------------------------
# Read local manifest
#------------------------------------------------------------------------------

def get_local_manifest():

    try:

        with open(config.LOCAL_MANIFEST_FILE, "r") as file:

            return ujson.load(file)

    except Exception:

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

        #--------------------------------------------------------------
        # Complete the post-reboot phase of a pending OTA update.
        #
        # This is deliberately executed before network initialization.
        # Cleanup must not depend on the network being available.
        #--------------------------------------------------------------

        if not ota_client.process_ota_state():
            print("")
            print("OTA state processing failed.")
            print("Application will not start.")
            return

    except Exception as e:

        print("")
        print("OTA state Error:", e)

        ota_client = None

    if not wait_for_network():

        print("")
        print("Starting application without OTA.")
        print("")

        application_loop()

        return

    try:

        if ota_client is None:
            ota_client = ota.OTA()

        if ota_client.update():
            return

    except Exception as e:

        print("")
        print("OTA Error:", e)

    print("")
    print("Starting application...")
    print("")

    application_loop()


#------------------------------------------------------------------------------
# Wait until cellular network is ready
#------------------------------------------------------------------------------

def wait_for_network(timeout=60):

    print("")
    print("Waiting for network...")

    stage, state = checkNet.waitNetworkReady(timeout)

    if stage == 3 and state == 1:

        print("Network is ready.")

        return True

    print("Network initialization failed.")
    print(
        "Failed stage:",
        NETWORK_STAGES.get(stage, "Unknown")
    )
    print("State:", state)

    return False
