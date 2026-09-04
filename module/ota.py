#==============================================================================
# File: ota.py
#
# Description:
#     OTA (Over-the-Air) update module for QuecPython application files.
#
#     The module performs file-based OTA updates through app_fota.
#
#     Update lifecycle:
#
#         1. Download and validate remote manifest.
#         2. Compare remote and local versions.
#         3. Determine files that require download.
#         4. Determine obsolete files.
#         5. Download update files through app_fota.
#         6. Persist pending.json with the target version and obsolete files.
#         7. Set the app_fota update flag.
#         8. Restart the module.
#         9. After reboot, verify the target version.
#        10. Delete obsolete files.
#        11. Remove pending.json only after cleanup succeeds.
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

    APP_DIR = config.APP_DIR

    UPDATER_DIR = "/fota/usr/.updater"

    PENDING_FILE = config.PENDING_FILE

    PENDING_TEMP_FILE = PENDING_FILE + ".tmp"

    PENDING_STATE = "pending"

    # Files which must survive a force update.
    # They are protected from deletion, but may still be replaced by
    # app_fota when the remote manifest contains a newer/different copy.
    PROTECTED_FILES = (
        "ota.mpy",
        "app.mpy",
        "config.mpy",
        "manifest.json",
    )

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

        obsolete_files = self.get_obsolete_files(
            update_info["local_manifest"],
            update_info["remote_manifest"]
        )

        print("")
        print("Obsolete files:", len(obsolete_files))

        for filename in obsolete_files:
            print("  REMOVE AFTER REBOOT:", filename)

        if not self.create_pending_update(
            update_info["remote_manifest"]["version"],
            obsolete_files
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
    # Force update
    #
    # This is a recovery/update mode.
    #
    # 1. Download and validate the remote manifest.
    # 2. Clean a previous incomplete APP FOTA update.
    # 3. Delete every file/directory below APP_DIR except PROTECTED_FILES.
    # 4. Check storage.
    # 5. Download the complete remote application through app_fota.
    # 6. Set APP FOTA update flag.
    # 7. Restart the module.
    #
    # Protected files are not deleted. If they are present in the remote
    # manifest and their contents differ, app_fota is still allowed to update
    # them.
    #
    # No pending.json is created here because obsolete files are deliberately
    # removed before the forced installation. Protected files are retained.
    #--------------------------------------------------------------------------

    def force_update(self):
        print("")
        print("Starting force update.")

        remote_manifest = self.download_manifest()

        if remote_manifest is None:
            print("")
            print("Failed to download remote manifest.")
            return False

        if not self.validate_manifest(remote_manifest):
            return False

        # First remove all non-protected application files.
        if not self.remove_unprotected_files():
            print("")
            print("Failed to clean application files.")
            return False

        # Check storage only after cleanup.
        if not self.check_storage_requirements(remote_manifest):
            print("")
            print("Not enough storage for force update.")
            return False

        failed_files = self.download_update(remote_manifest)

        if failed_files:
            print("")
            print("Force update failed.")
            print("Failed files:")

            for filename in failed_files:
                print(" - " + filename)

            return False

        if not self.set_update_flag():
            print("")
            print("Failed to set APP FOTA update flag.")
            return False

        print("")
        print("Force update prepared successfully.")
        print("Restarting device.")

        Power.powerRestart()

        return True

    #--------------------------------------------------------------------------
    # Remove every application file/directory except protected files.
    #
    # The operation is recursive and supports nested directories.
    # Empty directories left after protected files are preserved.
    #--------------------------------------------------------------------------

    def remove_unprotected_files(self):
        print("")
        print("Removing unprotected application files.")

        protected = set(self.PROTECTED_FILES)

        for entry in uos.listdir(self.APP_DIR):
            path = self.APP_DIR + "/" + entry

            # Keep protected files/directories.
            if entry in protected:
                print("Protected:", entry)
                continue

            if not self.remove_unprotected_path(path, entry, protected):
                return False

        return True

    #--------------------------------------------------------------------------
    # Recursively remove a path unless it is protected.
    #--------------------------------------------------------------------------

    def remove_unprotected_path(self, path, relative_path, protected):
        # Keep the protected path itself.
        if relative_path in protected:
            return True

        # Try to read the directory.
        # If listdir() fails, treat the path as a file.
        try:
            entries = uos.listdir(path)
            is_directory = True
        except Exception:
            is_directory = False

        if not is_directory:
            try:
                uos.remove(path)
            except Exception as error:
                print("")
                print("Failed to remove:")
                print(path)
                print(error)
                return False

            if ql_fs.path_exists(path):
                print("")
                print("File was not removed:")
                print(path)
                return False

            return True

        # Recursively remove directory contents.
        for entry in entries:
            child_path = path + "/" + entry
            child_relative_path = relative_path + "/" + entry

            if not self.remove_unprotected_path(
                child_path,
                child_relative_path,
                protected
            ):
                return False

        # Do not remove a directory if it contains
        # a protected file somewhere inside it.
        prefix = relative_path + "/"

        for protected_path in protected:
            if protected_path.startswith(prefix):
                return True

        # Remove now-empty directory.
        try:
            uos.rmdir(path)
        except Exception as error:
            print("")
            print("Failed to remove directory:")
            print(path)
            print(error)
            return False

        if ql_fs.path_exists(path):
            print("")
            print("Directory was not removed:")
            print(path)
            return False

        return True

    #--------------------------------------------------------------------------
    # Process pending update after reboot
    #
    # This method must be called before the network/OTA check.
    #
    # Returns:
    #     True  - pending update was processed successfully.
    #     False - no pending update or cleanup could not be completed.
    #--------------------------------------------------------------------------

    def process_pending_update(self):

        if not ql_fs.path_exists(self.PENDING_FILE):
            return True

        print("")
        print("========================================")
        print("Checking pending OTA update")
        print("========================================")

        pending = self.read_pending_update()

        if pending is None:
            print("")
            print("Pending update is invalid.")
            print("Obsolete files will NOT be removed.")
            return False

        target_version = pending["target_version"]

        local_manifest = self.get_local_manifest()

        local_version = local_manifest["version"]

        print("")
        print("Pending target version :", target_version)
        print("Current application    :", local_version)

        # The new application must be installed before any obsolete
        # files are allowed to be deleted.
        if local_version != target_version:

            print("")
            print("Target version is not installed.")
            print("Keeping pending.json.")
            print("No obsolete files will be removed.")

            return False

        print("")
        print("Target version confirmed.")
        print("Starting obsolete file cleanup.")

        if not self.remove_obsolete_files(
            pending["obsolete_files"]
        ):
            print("")
            print("Obsolete file cleanup is incomplete.")
            print("Keeping pending.json for the next startup.")

            return False

        if not self.remove_pending_update():
            print("")
            print("Could not remove pending.json.")
            print("Cleanup was completed; pending state is retained.")

            return False

        print("")
        print("Pending OTA update completed.")
        print("Obsolete files removed.")
        print("Pending state cleared.")

        return True

    #--------------------------------------------------------------------------
    # Read pending.json
    #--------------------------------------------------------------------------

    def read_pending_update(self):

        try:

            with open(self.PENDING_FILE, "r") as f:
                pending = ujson.load(f)

        except Exception as error:

            print("")
            print("Failed to read pending.json:", error)

            return None

        if not self.validate_pending_update(pending):
            return None

        return pending

    #--------------------------------------------------------------------------
    # Validate pending.json
    #--------------------------------------------------------------------------

    def validate_pending_update(self, pending):

        if not isinstance(pending, dict):
            return False

        if pending.get("state") != self.PENDING_STATE:
            return False

        target_version = pending.get("target_version")

        if (
            not isinstance(target_version, str)
            or not target_version
        ):
            return False

        try:
            self.parse_version(target_version)
        except Exception:
            return False

        obsolete_files = pending.get("obsolete_files")

        if not isinstance(obsolete_files, list):
            return False

        seen = set()

        for filename in obsolete_files:

            if not self.is_safe_relative_path(filename):
                return False

            if filename in seen:
                return False

            seen.add(filename)

        return True

    #--------------------------------------------------------------------------
    # Create pending.json
    #
    # pending.json is written BEFORE the app_fota update flag is set.
    # Therefore a power loss before the flag is set cannot cause deletion
    # of obsolete files during the next startup.
    #--------------------------------------------------------------------------

    def create_pending_update(
        self,
        target_version,
        obsolete_files
    ):

        pending = {
            "state": self.PENDING_STATE,
            "target_version": target_version,
            "obsolete_files": obsolete_files
        }

        print("")
        print("Creating pending OTA state.")
        print("Target version:", target_version)
        print("Obsolete files:", len(obsolete_files))

        try:

            # Remove a stale temporary file left by an interrupted write.
            if ql_fs.path_exists(self.PENDING_TEMP_FILE):
                print("")
                print("Removing stale pending temporary file.")
                uos.remove(self.PENDING_TEMP_FILE)

            with open(self.PENDING_TEMP_FILE, "w") as f:
                ujson.dump(pending, f)
                f.flush()

            # Sync the filesystem before making the state visible.
            try:
                uos.sync()
            except Exception:
                pass

            # Replacing an existing pending state is safe here because
            # the app_fota update flag has not been set yet.
            if ql_fs.path_exists(self.PENDING_FILE):
                uos.remove(self.PENDING_FILE)

            uos.rename(
                self.PENDING_TEMP_FILE,
                self.PENDING_FILE
            )

            if not ql_fs.path_exists(self.PENDING_FILE):
                raise Exception(
                    "pending.json was not created"
                )

            print("")
            print("pending.json created successfully.")

            return True

        except Exception as error:

            print("")
            print("Failed to create pending.json:", error)

            # Do not leave a partially prepared temporary state.
            try:
                if ql_fs.path_exists(self.PENDING_TEMP_FILE):
                    uos.remove(self.PENDING_TEMP_FILE)
            except Exception:
                pass

            return False

    #--------------------------------------------------------------------------
    # Remove pending.json
    #--------------------------------------------------------------------------

    def remove_pending_update(self):

        if not ql_fs.path_exists(self.PENDING_FILE):
            return True

        try:

            uos.remove(self.PENDING_FILE)

            if ql_fs.path_exists(self.PENDING_FILE):
                raise Exception(
                    "pending.json still exists after removal"
                )

            return True

        except Exception as error:

            print("")
            print("Failed to remove pending.json:", error)

            return False

    #--------------------------------------------------------------------------
    # Determine files present in the old manifest but absent from the target
    # manifest.
    #--------------------------------------------------------------------------

    def get_obsolete_files(
        self,
        local_manifest,
        remote_manifest
    ):

        local_files = local_manifest.get("files", [])
        remote_files = remote_manifest.get("files", [])

        remote_names = set()

        for file_info in remote_files:
            remote_names.add(file_info["name"])

        obsolete_files = []

        for file_info in local_files:

            name = file_info.get("name")

            if not isinstance(name, str):
                continue

            if not self.is_safe_relative_path(name):
                raise ValueError(
                    "Invalid local manifest file name: {}".format(name)
                )

            if name not in remote_names:
                obsolete_files.append(name)

        obsolete_files.sort()

        return obsolete_files

    #--------------------------------------------------------------------------
    # Remove obsolete files
    #--------------------------------------------------------------------------

    def remove_obsolete_files(self, obsolete_files):

        if not obsolete_files:
            print("")
            print("No obsolete files to remove.")
            return True

        failed = False

        for filename in obsolete_files:

            if not self.is_safe_relative_path(filename):
                print("")
                print("Unsafe obsolete file path:", filename)
                failed = True
                continue

            path = self.APP_DIR + "/" + filename

            if not self.file_exists(path):
                print("")
                print("Already absent:", filename)
                continue

            print("")
            print("Removing obsolete file:", filename)

            try:

                uos.remove(path)

            except Exception as error:

                print(
                    "Failed to remove {}: {}".format(
                        filename,
                        error
                    )
                )

                failed = True
                continue

            if self.file_exists(path):

                print(
                    "Removal verification failed: {}".format(
                        filename
                    )
                )

                failed = True
                continue

            print("Removed:", filename)

        return not failed

    #--------------------------------------------------------------------------
    # Check whether a relative path is safe for use below APP_DIR
    #--------------------------------------------------------------------------

    def is_safe_relative_path(self, path):

        if not isinstance(path, str) or not path:
            return False

        if path.startswith("/"):
            return False

        if path.startswith("\\"):
            return False

        if "\\" in path:
            return False

        parts = path.split("/")

        for part in parts:

            if part in ("", ".", ".."):
                return False

        return True

    #--------------------------------------------------------------------------
    # Check OTA server for available update
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

        self.manifest_size = len(
            text.encode("utf-8")
        )

        return manifest

    #--------------------------------------------------------------------------
    # Validate remote manifest
    #--------------------------------------------------------------------------

    def validate_manifest(self, manifest):

        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be an object")

        if "version" not in manifest:
            raise ValueError("Manifest version is missing")

        version = manifest["version"]

        if not isinstance(version, str) or not version:
            raise ValueError("Manifest version is invalid")

        if "files" not in manifest:
            raise ValueError("Manifest files are missing")

        files = manifest["files"]

        if not isinstance(files, list):
            raise ValueError("Manifest files must be a list")

        if not files:
            raise ValueError("Manifest files list is empty")

        seen_names = set()

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

            if not self.is_safe_relative_path(name):
                raise ValueError(
                    "Invalid file name: {}".format(name)
                )

            if (
                not isinstance(path, str)
                or not path.startswith("/files/")
                or "\\" in path
            ):
                raise ValueError(
                    "Invalid file path: {}".format(path)
                )

            relative_path = path[len("/files/"):]

            if relative_path != name:
                raise ValueError(
                    "Manifest name/path mismatch: {} != {}".format(
                        name,
                        path
                    )
                )

            if not self.is_safe_relative_path(relative_path):
                raise ValueError(
                    "Invalid file path: {}".format(path)
                )

            if name in seen_names:
                raise ValueError(
                    "Duplicate file name: {}".format(name)
                )

            seen_names.add(name)

            if type(size) is not int or size < 0:
                raise ValueError(
                    "Invalid file size: {}".format(size)
                )

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

    def is_update_available(
        self,
        local_manifest,
        remote_manifest
    ):

        local_version = self.parse_version(
            local_manifest["version"]
        )

        remote_version = self.parse_version(
            remote_manifest["version"]
        )

        return remote_version > local_version

    #--------------------------------------------------------------------------
    # Parse semantic version
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

        except Exception:

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

        for file_info in remote_manifest["files"]:

            if self.file_is_up_to_date(file_info):

                print("")
                print(
                    file_info["name"],
                    "is up to date."
                )

                continue

            download_list.append({
                "url": self.server + file_info["path"],
                "file_name": config.APP_DIR + "/" + file_info["name"]
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

        if not ql_fs.path_exists(self.UPDATER_DIR):
            return True

        print("")
        print("Previous APP FOTA update found.")

        try:

            ql_fs.rmdirs(self.UPDATER_DIR)

        except Exception as error:

            print("")
            print("Failed to remove previous APP FOTA update:")
            print(error)

            return False

        if ql_fs.path_exists(self.UPDATER_DIR):

            print("")
            print("Previous APP FOTA update still exists.")

            return False

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

        except Exception:

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
    # Get free space on /usr
    #--------------------------------------------------------------------------

    def get_free_space(self):

        stat = uos.statvfs("/usr")

        block_size = stat[0]
        free_blocks = stat[3]

        return block_size * free_blocks

    #--------------------------------------------------------------------------
    # Calculate required storage for the update
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

            # Every non-empty file consumes at least one filesystem block.
            if blocks < 1:
                blocks = 1

            required_space += blocks * block_size

        manifest_size = self.manifest_size

        blocks = (
            manifest_size + block_size - 1
        ) // block_size

        if blocks < 1:
            blocks = 1

        required_space += blocks * block_size

        return required_space

    #--------------------------------------------------------------------------
    # Check storage requirements
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
