#==============================================================================
# File: build.py
#
# Description:
#     Build QuecPython OTA application files.
#
#     Build process:
#
#         1. Read project.json.
#         2. Optionally increment application version.
#         3. Recursively process all files in src/.
#         4. Compile every .py file to .mpy using mpy-cross.
#         5. Copy all other files without modification.
#         6. Preserve the directory structure from src/.
#         7. Calculate SHA-256 for every generated OTA file.
#         8. Generate manifest.json.
#         9. Replace files/ only after the build has completed successfully.
#
# Usage:
#
#     python build.py
#
#         Build without changing the version.
#
#     python build.py --patch
#
#         Increment patch version and build.
#
#     python build.py --minor
#
#         Increment minor version and reset patch to 0.
#
#     python build.py --major
#
#         Increment major version and reset minor and patch to 0.
#
#==============================================================================

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

BASE_DIRECTORY = Path(__file__).resolve().parent

PROJECT_FILE = BASE_DIRECTORY / "project.json"

MANIFEST_FILE = BASE_DIRECTORY / "manifest.json"

SOURCE_DIRECTORY = BASE_DIRECTORY / "src"

FILES_DIRECTORY = BASE_DIRECTORY / "files"

MPY_CROSS = BASE_DIRECTORY / "tools" / "mpy-cross-amd64.exe"


#------------------------------------------------------------------------------
# Load project information
#------------------------------------------------------------------------------

def load_project():

    with PROJECT_FILE.open("r", encoding="utf-8") as file:

        project = json.load(file)

    validate_project(project)

    return project


#------------------------------------------------------------------------------
# Validate project information
#------------------------------------------------------------------------------

def validate_project(project):

    if not isinstance(project, dict):
        raise ValueError("project.json must contain an object.")

    for field in ("project", "version", "description"):

        if field not in project:
            raise ValueError(
                "Missing field in project.json: {}".format(field)
            )

    version = project["version"]

    if not isinstance(version, dict):
        raise ValueError("project.version must be an object.")

    for field in ("major", "minor", "patch"):

        if field not in version:
            raise ValueError(
                "Missing version field: {}".format(field)
            )

        if not isinstance(version[field], int) or version[field] < 0:
            raise ValueError(
                "Invalid version field: {}".format(field)
            )


#------------------------------------------------------------------------------
# Save project information
#------------------------------------------------------------------------------

def save_project(project):

    with PROJECT_FILE.open("w", encoding="utf-8") as file:

        json.dump(
            project,
            file,
            indent=4
        )

        file.write("\n")


#------------------------------------------------------------------------------
# Update version
#------------------------------------------------------------------------------

def update_version(project):

    version = project["version"]

    if "--patch" in sys.argv:

        version["patch"] += 1

    elif "--minor" in sys.argv:

        version["minor"] += 1
        version["patch"] = 0

    elif "--major" in sys.argv:

        version["major"] += 1
        version["minor"] = 0
        version["patch"] = 0


#------------------------------------------------------------------------------
# Version string
#------------------------------------------------------------------------------

def version_string(project):

    version = project["version"]

    return "{}.{}.{}".format(
        version["major"],
        version["minor"],
        version["patch"]
    )


#------------------------------------------------------------------------------
# Calculate SHA-256
#------------------------------------------------------------------------------

def calculate_sha256(filename):

    sha = hashlib.sha256()

    with filename.open("rb") as file:

        while True:

            data = file.read(4096)

            if not data:
                break

            sha.update(data)

    return sha.hexdigest()


#------------------------------------------------------------------------------
# Validate build tools and source directory
#------------------------------------------------------------------------------

def validate_environment():

    if not SOURCE_DIRECTORY.is_dir():

        raise FileNotFoundError(
            "Source directory not found: {}".format(
                SOURCE_DIRECTORY
            )
        )

    if not MPY_CROSS.is_file():

        raise FileNotFoundError(
            "mpy-cross executable not found: {}".format(
                MPY_CROSS
            )
        )


#------------------------------------------------------------------------------
# Compile Python source file
#------------------------------------------------------------------------------

def compile_python(source_file, output_file):

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    command = [
        str(MPY_CROSS),
        str(source_file),
        "-o",
        str(output_file)
    ]

    result = subprocess.run(
        command,
        cwd=str(BASE_DIRECTORY)
    )

    if result.returncode != 0:

        raise RuntimeError(
            "mpy-cross failed for: {}".format(source_file)
        )


#------------------------------------------------------------------------------
# Build files into temporary directory
#
# A temporary directory is used instead of a permanent build/ directory.
# The final files/ directory is replaced only after all source files have
# been processed successfully.
#------------------------------------------------------------------------------

def build_files(temp_directory):

    file_count = 0

    for source_file in sorted(SOURCE_DIRECTORY.rglob("*")):

        if not source_file.is_file():
            continue

        relative_path = source_file.relative_to(SOURCE_DIRECTORY)

        #----------------------------------------------------------------------
        # Python source -> MPY
        #----------------------------------------------------------------------

        if source_file.suffix.lower() == ".py":

            output_relative_path = relative_path.with_suffix(".mpy")
            output_file = temp_directory / output_relative_path

            print(
                "  PY -> MPY:",
                relative_path,
                "->",
                output_relative_path
            )

            compile_python(
                source_file,
                output_file
            )

        #----------------------------------------------------------------------
        # All other files -> copy without modification
        #----------------------------------------------------------------------

        else:

            output_file = temp_directory / relative_path

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            print(
                "  COPY    :",
                relative_path
            )

            shutil.copy2(
                source_file,
                output_file
            )

        file_count += 1

    if file_count == 0:

        raise RuntimeError(
            "The 'src' directory is empty."
        )

    return file_count


#------------------------------------------------------------------------------
# Build manifest from final OTA files
#------------------------------------------------------------------------------

def build_manifest(project, directory):

    now = datetime.now()

    manifest = {

        "project": project["project"],

        "version": version_string(project),

        "description": project["description"],

        "build":
        {
            "date": now.strftime("%Y-%m-%d"),

            "time": now.strftime("%H:%M:%S")
        },

        "files": []
    }

    for file_path in sorted(directory.rglob("*")):

        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(directory)

        # HTTP paths must always use '/'.
        relative_name = relative_path.as_posix()

        manifest["files"].append({

            "name": relative_name,

            "path": "/files/" + relative_name,

            "size": file_path.stat().st_size,

            "sha256": calculate_sha256(file_path)

        })

    if not manifest["files"]:

        raise RuntimeError(
            "The build contains no OTA files."
        )

    return manifest


#------------------------------------------------------------------------------
# Replace files/ with the successful build
#------------------------------------------------------------------------------

def install_files(temp_directory):

    old_directory = None

    if FILES_DIRECTORY.exists():

        old_directory = FILES_DIRECTORY.with_name(
            FILES_DIRECTORY.name + ".old"
        )

        if old_directory.exists():

            shutil.rmtree(old_directory)

        FILES_DIRECTORY.rename(old_directory)

    try:

        temp_directory.rename(FILES_DIRECTORY)

    except Exception:

        # Restore the previous files directory if installation failed.
        if FILES_DIRECTORY.exists():

            shutil.rmtree(FILES_DIRECTORY)

        if old_directory is not None and old_directory.exists():

            old_directory.rename(FILES_DIRECTORY)

        raise

    # The old OTA files are no longer needed.
    if old_directory is not None and old_directory.exists():

        shutil.rmtree(old_directory)


#------------------------------------------------------------------------------
# Save manifest
#------------------------------------------------------------------------------

def save_manifest(manifest):

    temporary_manifest = MANIFEST_FILE.with_name(
        MANIFEST_FILE.name + ".tmp"
    )

    with temporary_manifest.open("w", encoding="utf-8") as file:

        json.dump(
            manifest,
            file,
            indent=4
        )

        file.write("\n")

    temporary_manifest.replace(MANIFEST_FILE)


#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

def main():

    print()
    print("========================================")
    print("QuecPython OTA Build")
    print("========================================")
    print()

    validate_environment()

    project = load_project()

    # Work on the loaded project first. project.json is saved only after
    # the complete build and manifest generation have succeeded.
    update_version(project)

    print("Version :", version_string(project))
    print("Source  :", SOURCE_DIRECTORY)
    print("Output  :", FILES_DIRECTORY)
    print("Compiler:", MPY_CROSS)
    print()

    # Temporary directory is outside the project. Therefore there is no
    # permanent build/ directory.
    with tempfile.TemporaryDirectory(
        prefix=".ota_build_",
        dir=str(BASE_DIRECTORY)
    ) as temporary_directory:

        temporary_directory = Path(temporary_directory)

        print("Building files...")
        print()

        file_count = build_files(
            temporary_directory
        )

        print()
        print("Generating manifest...")
        print()

        manifest = build_manifest(
            project,
            temporary_directory
        )

        # Only now replace the currently published OTA files.
        install_files(
            temporary_directory
        )

        # The temporary directory has been moved to files/, so prevent
        # TemporaryDirectory from trying to remove the moved directory.
        temporary_directory = None

    # Save version and manifest only after a successful file build.
    save_project(project)
    save_manifest(manifest)

    print()
    print("========================================")
    print("Build completed successfully.")
    print("========================================")
    print()
    print("Version :", manifest["version"])
    print(
        "Build   :",
        manifest["build"]["date"],
        manifest["build"]["time"]
    )
    print("Files   :", file_count)
    print("Output  :", FILES_DIRECTORY)
    print()


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print()
        print("========================================")
        print("BUILD FAILED")
        print("========================================")
        print()
        print(error)
        print()

        sys.exit(1)
