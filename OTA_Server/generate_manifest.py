#==============================================================================
# File: generate_manifest.py
#
# Description:
#     Generate OTA manifest.json.
#
#     Features:
#
#         • Calculates SHA-256 of every file.
#         • Generates manifest.json automatically.
#         • Stores build date and time.
#         • Can automatically increment version.
#
# Usage:
#
#     python generate_manifest.py
#
#         Generate manifest only.
#
#     python generate_manifest.py --patch
#
#         Increment patch version.
#
#     python generate_manifest.py --minor
#
#         Increment minor version.
#
#     python generate_manifest.py --major
#
#         Increment major version.
#
#==============================================================================

import os
import sys
import json
import hashlib
from datetime import datetime


#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------

PROJECT_FILE = "project.json"

MANIFEST_FILE = "manifest.json"

FILES_DIRECTORY = "files"


#------------------------------------------------------------------------------
# Load project information
#------------------------------------------------------------------------------

def load_project():

    with open(PROJECT_FILE, "r", encoding="utf-8") as file:

        return json.load(file)


#------------------------------------------------------------------------------
# Save project information
#------------------------------------------------------------------------------

def save_project(project):

    with open(PROJECT_FILE, "w", encoding="utf-8") as file:

        json.dump(
            project,
            file,
            indent=4
        )


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
# Calculate SHA256
#------------------------------------------------------------------------------

def calculate_sha256(filename):

    sha = hashlib.sha256()

    with open(filename, "rb") as file:

        while True:

            data = file.read(4096)

            if not data:
                break

            sha.update(data)

    return sha.hexdigest()


#------------------------------------------------------------------------------
# Build manifest
#------------------------------------------------------------------------------

def build_manifest(project):

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


    for filename in sorted(os.listdir(FILES_DIRECTORY)):

        full_path = os.path.join(

            FILES_DIRECTORY,

            filename

        )

        if not os.path.isfile(full_path):

            continue


        manifest["files"].append({

            "name": filename,

            "path": "/files/" + filename,

            "size": os.path.getsize(full_path),

            "sha256": calculate_sha256(full_path)

        })

    #----------------------------------------------------------
    # Verify manifest
    #----------------------------------------------------------

    if len(manifest["files"]) == 0:

        raise Exception(
            "The 'files' directory is empty."
        )

    return manifest


#------------------------------------------------------------------------------
# Save manifest
#------------------------------------------------------------------------------

def save_manifest(manifest):

    with open(MANIFEST_FILE, "w", encoding="utf-8") as file:

        json.dump(

            manifest,

            file,

            indent=4

        )


#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

def main():

    project = load_project()

    update_version(project)

    save_project(project)

    manifest = build_manifest(project)

    save_manifest(manifest)

    print()

    print("Manifest generated successfully.")

    print("Version :", manifest["version"])

    print("Build   :", manifest["build"]["date"], manifest["build"]["time"])

    print("Files   :", len(manifest["files"]))

    print()


if __name__ == "__main__":

    main()