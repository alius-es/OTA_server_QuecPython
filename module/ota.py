#==============================================================================
# File: ota.py
#
# Description:
#     OTA (Over-The-Air) update module.
#
# Responsibilities:
#     - Connect to OTA server
#     - Download manifest.json
#     - Parse manifest
#     - Compare versions
#     - Download update files
#     - Install update
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
    # Check OTA server and install update if available
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


        remote_manifest = ujson.loads(text)

        local_manifest = self.get_local_manifest()

        print("")
        print("Remote version :", remote_manifest["version"])
        print("Local version  :", local_manifest["version"])

        #----------------------------------------------------------
        # Compare versions
        #----------------------------------------------------------

        if remote_manifest["version"] == local_manifest["version"]:

            print("")
            print("Application is up to date.")

        else:

            print("")
            print("New version available.")

            for file in remote_manifest["files"]:

                self.download_file(
                    file["path"],
                    "/usr/" + file["name"] + ".new"
                )

            self.download_file(
                "/manifest.json",
                "/usr/manifest.json.new"
            )
            
            if self.install_update(local_manifest, remote_manifest):

                print("")
                print("Update installed successfully.")

            else:

                print("")
                print("Update installation failed.")


    #--------------------------------------------------------------------------
    # Read local manifest file
    #--------------------------------------------------------------------------
    def get_local_manifest(self):

        try:

            with open(config.LOCAL_MANIFEST_FILE, "r") as f:

                info = ujson.load(f)

            print("")
            print("Local version :", info["version"])

            return info

        except Exception:

            print("")
            print("Local manifest not found.")

            return {
                "project": "",
                "version": "0.0.0",
                "files": []
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
    def install_update(self, local_manifest, remote_manifest):

        print("")
        print("========================================")
        print("Installing update")
        print("========================================")

        #----------------------------------------------------------
        # Verify downloaded files
        #----------------------------------------------------------

        for file in remote_manifest["files"]:

            new_file = "/usr/" + file["name"] + ".new"

            try:

                uos.stat(new_file)

            except:

                print("")
                print("Missing:", new_file)
                print("Installation cancelled.")

                return False

        try:

            uos.stat("/usr/manifest.json.new")

        except:

            print("")
            print("Missing: /usr/manifest.json.new")
            print("Installation cancelled.")

            return False

        print("")
        print("All update files verified.")

        #----------------------------------------------------------
        # Remove obsolete files
        #----------------------------------------------------------

        self.remove_obsolete_files(
            local_manifest, 
            remote_manifest
        )

        #----------------------------------------------------------
        # Install every file except ota.py
        #----------------------------------------------------------

        for file in remote_manifest["files"]:

            if file["name"] == "ota.py":
                continue

            self.replace_file(file["name"])

        #----------------------------------------------------------
        # Install ota.py
        #----------------------------------------------------------

        for file in remote_manifest["files"]:

            if file["name"] != "ota.py":
                continue

            self.replace_file("ota.py")

            break

        #----------------------------------------------------------
        # Install manifest.json
        #----------------------------------------------------------

        self.replace_file("manifest.json")

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

    #--------------------------------------------------------------------------
    # Remove obsolete application files
    #--------------------------------------------------------------------------
    def remove_obsolete_files(self, local_manifest, remote_manifest):

        print("")
        print("Removing obsolete files")

        #----------------------------------------------------------
        # Build list of new files
        #----------------------------------------------------------

        new_files = {}

        for file in remote_manifest["files"]:

            new_files[file["name"]] = True

        #----------------------------------------------------------
        # Remove files that are no longer present
        #----------------------------------------------------------

        for file in local_manifest["files"]:

            filename = file["name"]

            if filename == "main.py":

                continue

            if filename in new_files:

                continue

            filepath = "/usr/" + filename

            print("")
            print("Removing:", filename)

            try:

                uos.remove(filepath)

                print("Removed:", filename)

            except:

                print("Already missing:", filename)

        print("")
        print("Obsolete files removed.")