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
from misc import Power
import utime

#------------------------------------------------------------------------------
# OTA Class
#------------------------------------------------------------------------------

class OTA:

    #--------------------------------------------------------------------------
    # Constants
    #--------------------------------------------------------------------------

    APP_DIR = "/usr/app"

    UPDATER_DIR = "/fota/usr/.updater"

    PENDING_FILE = "/usr/pending.json"

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

        if not self.check_storage_requirements(
            update_info["remote_manifest"]
        ):
            return False

        if not self.download_update(
            update_info["remote_manifest"]
        ):
            return False

        if not self.set_update_flag():
            return False

        print("")
        print("Restarting module...")

        Power.powerRestart()

        utime.sleep(5)
        return


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

        self.validate_manifest(remote_manifest)

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

        manifest = ujson.loads(text)

        self.manifest_size = len(text.encode("utf-8"))

        return manifest

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

        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be an object")

        #----------------------------------------------------------------------
        # Version
        #----------------------------------------------------------------------

        if "version" not in manifest:
            raise ValueError("Manifest version is missing")

        version = manifest["version"]

        if not isinstance(version, str) or not version:
            raise ValueError("Manifest version is invalid")

        #----------------------------------------------------------------------
        # Files
        #----------------------------------------------------------------------

        if "files" not in manifest:
            raise ValueError("Manifest files are missing")

        files = manifest["files"]

        if not isinstance(files, list):
            raise ValueError("Manifest files must be a list")

        if not files:
            raise ValueError("Manifest files list is empty")

        #----------------------------------------------------------------------
        # File entries
        #----------------------------------------------------------------------

        for file_info in files:

            if not isinstance(file_info, dict):
                raise ValueError("Invalid file entry")

            if "name" not in file_info:
                raise ValueError("File name is missing")

            if "path" not in file_info:
                raise ValueError("File path is missing")

            if "size" not in file_info:
                raise ValueError("File size is missing")

            if "sha256" not in file_info:
                raise ValueError("File SHA-256 is missing")

            name = file_info["name"]
            path = file_info["path"]
            size = file_info["size"]
            sha256 = file_info["sha256"]

            #------------------------------------------------------------------
            # Name
            #------------------------------------------------------------------

            if (
                not isinstance(name, str)
                or not name
                or "/" in name
                or "\\" in name
                or name in (".", "..")
            ):
                raise ValueError(
                    "Invalid file name: {}".format(name)
                )

            #------------------------------------------------------------------
            # Path
            #------------------------------------------------------------------

            if (
                not isinstance(path, str)
                or not path.startswith("/files/")
                or ".." in path
                or "\\" in path
            ):
                raise ValueError(
                    "Invalid file path: {}".format(path)
                )

            #------------------------------------------------------------------
            # Size
            #------------------------------------------------------------------

            if (
                not isinstance(size, int)
                or size < 0
            ):
                raise ValueError(
                    "Invalid file size: {}".format(size)
                )

            #------------------------------------------------------------------
            # SHA-256
            #------------------------------------------------------------------

            if (
                not isinstance(sha256, str)
                or len(sha256) != 64
            ):
                raise ValueError(
                    "Invalid SHA-256: {}".format(sha256)
                )

            for char in sha256:

                if char not in "0123456789abcdef":
                    raise ValueError(
                        "Invalid SHA-256: {}".format(sha256)
                    )

        return True


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

        local_version = self.parse_version(
            local_manifest["version"]
        )

        remote_version = self.parse_version(
            remote_manifest["version"]
        )

        return remote_version > local_version

    #--------------------------------------------------------------------------
    # Parsing the version to help method is_update_available
    #--------------------------------------------------------------------------
    def parse_version(self, version):

        parts = version.split(".")

        if len(parts) != 3:
            raise ValueError(
                "Invalid version: {}".format(version)
            )

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
        except:
            raise ValueError(
                "Invalid version: {}".format(version)
            )

        if major < 0 or minor < 0 or patch < 0:
            raise ValueError(
                "Invalid version: {}".format(version)
            )

        return (major, minor, patch)


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
                "file_name": config.APP_DIR + "/" + file["name"]
            })

        download_list.append({
            "url": self.manifest_url,
            "file_name": config.LOCAL_MANIFEST_FILE
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

        updater_path = "/fota/usr/.updater"

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

        filename = config.APP_DIR + "/" + file_info["name"]

        if not self.file_exists(filename):
            return False

        return (
            self.calculate_sha256(filename)
            == file_info["sha256"]
        )

    #--------------------------------------------------------------------------
    # Obtaining free space of /usr folder
    #--------------------------------------------------------------------------    
    def get_free_space(self):

        stat = uos.statvfs("/usr")

        block_size = stat[0]
        free_blocks = stat[3]

        return block_size * free_blocks

    #--------------------------------------------------------------------------
    # Calculate required space for update
    #--------------------------------------------------------------------------
    def get_required_space(self, remote_manifest):

        stat = uos.statvfs("/usr")

        block_size = stat[0]

        required_space = 0

        for file_info in remote_manifest["files"]:

            if self.file_is_up_to_date(file_info):
                continue

            file_size = file_info["size"]

            blocks = (
                file_size + block_size - 1
            ) // block_size

            required_space += blocks * block_size

        #----------------------------------------------------------------------
        # Manifest
        #----------------------------------------------------------------------

        manifest_size = self.manifest_size

        blocks = (
            manifest_size + block_size - 1
        ) // block_size

        required_space += blocks * block_size

        return required_space

    #--------------------------------------------------------------------------
    # Check whether enough space is available
    #--------------------------------------------------------------------------
    def check_storage_requirements(self, remote_manifest):

        required_space = self.get_required_space(
            remote_manifest
        )

        free_space = self.get_free_space()

        print("")
        print("Required space:", required_space)
        print("Free space    :", free_space)

        if required_space > free_space:

            print("")
            print("Not enough space for OTA update.")

            return False

        print("")
        print("Enough space for OTA update.")

        return True