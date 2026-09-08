#==============================================================================
# File: app.py
#
# Description:
#     Main application module.
#
#     This module demonstrates how the OTA library can be integrated
#     into the application startup sequence.
#
# Startup sequence:
#
#     1. Print application information.
#     2. Wait for network.
#     3. Process the result of a previous OTA update.
#     4. Start the main application.
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import utime
import ujson
import ota
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

        with open(ota.LOCAL_MANIFEST_FILE, "r") as file:

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

    if not wait_for_network():
    
        print("")
        print("Starting application without OTA.")
        print("")

        application_loop()

        return

    ota_client = ota.OTA()

    #------------------------------------------------------------------
    # Process a previously started OTA operation.
    #
    # If an OTA update was performed before the reboot, this verifies
    # the result and reports it to the server.
    #
    # If reporting fails, ota_state.json is kept and no new OTA update
    # is started.
    #------------------------------------------------------------------

    if not ota_client.process_ota():

        print("")
        print("OTA processing failed.")
        print("Starting application without new OTA.")
        print("")

        application_loop()

        return

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
    print("Failed stage:", NETWORK_STAGES.get(stage, "Unknown"))
    print("State:", state)

    return False
