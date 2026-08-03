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
import uhashlib


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

        #----------------------------------------------------------
        # Validate manifest
        #----------------------------------------------------------

        if len(remote_manifest["files"]) == 0:

            print("")
            print("Invalid manifest: no files.")

            return

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

            return

        print("")
        print("New version available.")

        #----------------------------------------------------------
        # Download changed files only
        #----------------------------------------------------------
        for file in remote_manifest["files"]:

            if self.file_is_up_to_date(file):
                print("")
                print(file["name"], "is up to date.")

                continue

            self.download_file(
                file["path"],
                "/usr/" + file["name"] + ".new"
            )

        #----------------------------------------------------------
        # Download new manifest
        #----------------------------------------------------------
        self.download_file(
            "/manifest.json",
            "/usr/manifest.json.new"
        )

        #----------------------------------------------------------
        # Install update
        #----------------------------------------------------------
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

            if not self.file_exists(new_file):
                continue

            if not self.verify_download(file):
                print("")
                print("Verification failed:", file["name"])
                print("Installation cancelled.")

                return False

        if not self.file_exists("/usr/manifest.json.new"):
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

            if not self.file_exists("/usr/" + file["name"] + ".new"):
                continue

            self.replace_file(file["name"])

        #----------------------------------------------------------
        # Install ota.py
        #----------------------------------------------------------

        for file in remote_manifest["files"]:

            if file["name"] != "ota.py":
                continue

            if not self.file_exists("/usr/ota.py.new"):
                break
            
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


    #--------------------------------------------------------------------------
    # Calculate SHA-256 of file
    #--------------------------------------------------------------------------
    def calculate_sha256(self, filename):

        sha256 = uhashlib.sha256()

        file = open(filename, "rb")

        while True:

            data = file.read(512)

            if not data:
                break

            sha256.update(data)

        file.close()

        digest = sha256.digest()

        result = ""

        for byte in digest:
            result += "{:02x}".format(byte)

        return result

    #--------------------------------------------------------------------------
    # Check if file exists
    #--------------------------------------------------------------------------
    def file_exists(self, filename):

        try:

            uos.stat(filename)

            return True

        except:

            return False

    #--------------------------------------------------------------------------
    # Check whether local file is up to date
    #--------------------------------------------------------------------------
    def file_is_up_to_date(self, file_info):

        filename = "/usr/" + file_info["name"]

        if not self.file_exists(filename):
            return False

        local_sha256 = self.calculate_sha256(filename)

        if local_sha256 == file_info["sha256"]:
            return True

        return False

    #--------------------------------------------------------------------------
    # Verify downloaded file
    #--------------------------------------------------------------------------
    def verify_download(self, file_info):

        filename = "/usr/" + file_info["name"] + ".new"

        sha256 = self.calculate_sha256(filename)

        if sha256 == file_info["sha256"]:
            return True

        return False