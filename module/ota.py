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
import uos
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

        self.manifest_url = self.server + "/manifest.json"


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
    # Download and parse OTA manifest.json
    #--------------------------------------------------------------------------
    def check_update(self):

        print("")
        print("========================================")
        print("Checking OTA server")
        print("========================================")

        text = self.download_text(self.manifest_url)

        print("")
        print("Received manifest.json")
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

            if self.install_update(remote_info):

                print("")
                print("Update installed successfully.")

            else:

                print("")
                print("Update installation failed.")


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


    #--------------------------------------------------------------------------
    # Install downloaded update
    #--------------------------------------------------------------------------
    def install_update(self, manifest):

        print("")
        print("========================================")
        print("Installing update")
        print("========================================")

        #----------------------------------------------------------
        # Verify downloaded files
        #----------------------------------------------------------

        for file in manifest["files"]:

            new_file = "/usr/" + file["name"] + ".new"

            try:

                uos.stat(new_file)

            except:

                print("")
                print("Missing:", new_file)
                print("Installation cancelled.")

                return False

        print("")
        print("All update files verified.")

        #----------------------------------------------------------
        # Install every file except version.json
        #----------------------------------------------------------

        for file in manifest["files"]:

            if file["name"] == "version.json":
                continue

            self.replace_file(file["name"])

        #----------------------------------------------------------
        # Install version.json last
        #----------------------------------------------------------

        for file in manifest["files"]:

            if file["name"] != "version.json":
                continue

            self.replace_file("version.json")

            break

        print("")
        print("Installation completed.")

        return True


    #--------------------------------------------------------------------------
    # Replace old file with downloaded file
    #--------------------------------------------------------------------------
    def replace_file(self, filename):

        old_file = "/usr/" + filename
        new_file = old_file + ".new"

        print("")
        print("Installing:", filename)

        try:

            uos.remove(old_file)

        except:

            pass

        uos.rename(new_file, old_file)

        print("Installed:", filename)