#==============================================================================
# File: ota.py
#
# Description:
#     OTA (Over-The-Air) update module.
#
# Responsibilities:
#     - Connect to OTA server
#     - Download version.json
#     - Parse JSON
#     - Compare versions (later)
#     - Download update files (later)
#     - Install update (later)
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import request
import ujson

import config


#------------------------------------------------------------------------------
# OTA Class
#------------------------------------------------------------------------------

class OTA:

    #--------------------------------------------------------------------------
    # Constructor
    #--------------------------------------------------------------------------
    def __init__(self):

        self.server = config.OTA_SERVER

        self.version_url = self.server + "/version.json"


    #--------------------------------------------------------------------------
    # Download text file from server
    #--------------------------------------------------------------------------
    def download_text(self, url):

        print("")
        print("GET:", url)

        response = request.get(url)

        if response.status_code != 200:

            response.close()

            raise Exception("HTTP Error: {}".format(response.status_code))

        text = ""

        for chunk in response.text:

            text += chunk

        response.close()

        return text


    #--------------------------------------------------------------------------
    # Download and parse version.json
    #--------------------------------------------------------------------------
    def check_update(self):

        print("")
        print("========================================")
        print("Checking OTA server")
        print("========================================")

        text = self.download_text(self.version_url)

        print("")
        print("Received version.json")
        print("----------------------------------------")
        print(text)
        print("----------------------------------------")

        info = ujson.loads(text)

        print("")
        print("Project     :", info["project"])
        print("Version     :", info["version"])
        print("Description :", info["description"])

        print("")
        print("Files:")

        for file in info["files"]:

            print("  {}".format(file["name"]))

        print("")

        return info