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


        remote_info = ujson.loads(text)

        local_info = self.get_local_version()

        print("")
        print("Remote version :", remote_info["version"])
        print("Local version  :", local_info["version"])

        #----------------------------------------------------------
        # Compare versions
        #----------------------------------------------------------

        if remote_info["version"] == local_info["version"]:

            print("")
            print("Application is up to date.")

        else:

            print("")
            print("New version available.")

            for file in remote_info["files"]:

                self.download_file(
                    file["path"],
                    "/usr/" + file["name"] + ".new"
                )

        return remote_info

    #--------------------------------------------------------------------------
    # Read local version file
    #--------------------------------------------------------------------------
    def get_local_version(self):

        try:

            with open(config.LOCAL_VERSION_FILE, "r") as f:

                info = ujson.load(f)

            print("")
            print("Local version :", info["version"])

            return info

        except Exception:

            print("")
            print("Local version file not found.")

            return {
                "project": "",
                "version": "0.0.0"
            }

    #--------------------------------------------------------------------------
    # Download file from OTA server
    #--------------------------------------------------------------------------
    def download_file(self, remote_path, local_path):

        url = self.server + remote_path

        print("")
        print("Downloading:", url)

        response = request.get(url)

        if response.status_code != 200:

            response.close()

            raise Exception(
                "HTTP Error: {}".format(response.status_code)
            )

        file = open(local_path, "w")

        for chunk in response.text:

            file.write(chunk)

        file.close()

        response.close()

        print("Saved:", local_path)