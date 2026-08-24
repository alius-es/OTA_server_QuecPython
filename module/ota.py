#==============================================================================
# File: ota.py
#
# Description:
#     OTA (Over-The-Air) update module for QuecPython application files.
#
# Responsibilities:
#     - Connect to OTA server
#     - Download and parse manifest.json
#     - Validate manifest
#     - Compare local and remote versions
#     - Determine files that require update
#     - Download update files using app_fota
#     - Set application update flag
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import request
import ujson
import uos
import uhashlib
import app_fota
import ql_fs
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
        
        self.fota = app_fota.new()


    #--------------------------------------------------------------------------
    # Perform complete OTA update
    #--------------------------------------------------------------------------
    def update(self):

        update_info = self.check_update()

        if update_info is None:
            return False

        if not self.cleanup_previous_update():
            return False

        if not self.download_update(
            update_info["remote_manifest"]
        ):
            return False

        if not self.set_update_flag():
            return False

        return True


    #--------------------------------------------------------------------------
    # Check OTA server for available update
    #
    # Responsibilities:
    #     - Download manifest.json
    #     - Parse JSON
    #     - Validate manifest
    #     - Read local manifest
    #     - Compare versions
    #
    # Returns:
    #     Update information or None.
    #--------------------------------------------------------------------------

    def check_update(self):

        print("")
        print("========================================")
        print("Checking OTA server")
        print("========================================")

        remote_manifest = self.download_manifest()

        local_manifest = self.get_local_manifest()

        print("")
        print("Remote version :", remote_manifest["version"])
        print("Local version  :", local_manifest["version"])

        if not self.is_update_available(
            local_manifest,
            remote_manifest
        ):

            print("")
            print("Application is up to date.")

            return None

        print("")
        print("New version available.")

        return {
            "local_manifest": local_manifest,
            "remote_manifest": remote_manifest
        }


    #--------------------------------------------------------------------------
    # Download manifest.json from OTA server
    #--------------------------------------------------------------------------

    def download_manifest(self):

        print("")
        print("GET:", self.manifest_url)

        response = request.get(self.manifest_url)

        if response.status_code != 200:

            response.close()

            raise Exception(
                "HTTP Error: {}".format(response.status_code)
            )

        text = ""

        for chunk in response.text:
            text += chunk

        response.close()

        return ujson.loads(text)


    #--------------------------------------------------------------------------
    # Validate remote manifest
    #
    # Responsibilities:
    #     - Validate required fields
    #     - Validate version
    #     - Validate files list
    #     - Validate file names and paths
    #     - Validate SHA-256 values
    #--------------------------------------------------------------------------

    def validate_manifest(self, manifest):
        pass


    #--------------------------------------------------------------------------
    # Read local manifest
    #--------------------------------------------------------------------------
    def get_local_manifest(self):

        try:

            with open(config.LOCAL_MANIFEST_FILE, "r") as f:
                return ujson.load(f)

        except Exception:

            print("")
            print("Local manifest not found.")

            return {
                "project": "",
                "version": "0.0.0",
                "files": []
            }


    #--------------------------------------------------------------------------
    # Check whether an update is available
    #--------------------------------------------------------------------------
    def is_update_available(self, local_manifest, remote_manifest):

        return (
            remote_manifest["version"]
            != local_manifest["version"]
        )


    #--------------------------------------------------------------------------
    # Build app_fota download list
    #--------------------------------------------------------------------------
    def build_download_list(self, remote_manifest):

        download_list = []

        for file in remote_manifest["files"]:

            if self.file_is_up_to_date(file):

                print("")
                print(file["name"], "is up to date.")

                continue

            download_list.append({
                "url": self.server + file["path"],
                "file_name": "/usr/" + file["name"]
            })

        download_list.append({
            "url": self.manifest_url,
            "file_name": "/usr/manifest.json"
        })

        return download_list

    #--------------------------------------------------------------------------
    # Download update files using app_fota
    #--------------------------------------------------------------------------
    def download_update(self, remote_manifest):

        print("")
        print("========================================")
        print("Downloading update")
        print("========================================")

        download_list = self.build_download_list(
            remote_manifest
        )

        if not download_list:

            print("")
            print("No files need to be downloaded.")

            return True

        print("")
        print("Files to download:", len(download_list))

        result = self.fota.bulk_download(
            download_list
        )

        if result is not None:

            print("")
            print("APP FOTA download failed:")
            print(result)

            return False

        print("")
        print("APP FOTA download completed.")

        return True

    #--------------------------------------------------------------------------
    # Set Application FOTA update flag
    #--------------------------------------------------------------------------
    def set_update_flag(self):

        print("")
        print("Setting APP FOTA update flag")

        self.fota.set_update_flag()

        print("")
        print("APP FOTA update flag set.")

        return True


    #--------------------------------------------------------------------------
    # Clean up previous incomplete Application FOTA
    #--------------------------------------------------------------------------
    def cleanup_previous_update(self):

        updater_path = "/usr/.updater"

        if not ql_fs.path_exists(updater_path):
            return True

        print("")
        print("Previous APP FOTA update found.")

        ql_fs.rmdirs(updater_path)

        print("")
        print("Previous APP FOTA update removed.")

        return True

    #--------------------------------------------------------------------------
    # Check whether a file exists
    #--------------------------------------------------------------------------
    def file_exists(self, filename):

        try:
            uos.stat(filename)
            return True

        except:
            return False

    #--------------------------------------------------------------------------
    # Calculate SHA-256 of a local file
    #--------------------------------------------------------------------------
    def calculate_sha256(self, filename):

        sha256 = uhashlib.sha256()

        with open(filename, "rb") as f:

            while True:

                data = f.read(512)

                if not data:
                    break

                sha256.update(data)

        result = ""

        for byte in sha256.digest():
            result += "{:02x}".format(byte)

        return result

    #--------------------------------------------------------------------------
    # Check whether local file already matches manifest
    #--------------------------------------------------------------------------
    def file_is_up_to_date(self, file_info):

        filename = "/usr/" + file_info["name"]

        if not self.file_exists(filename):
            return False

        return (
            self.calculate_sha256(filename)
            == file_info["sha256"]
        )