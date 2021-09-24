#!/usr/bin/env python3
"""
Check for presence of Terraform (TF) or CloudFormation (CFM) IAC code within a repo.
If found, create the appropriate default configuration to enable Prisma IAC scanning
delivered via Palo Alto's Prisma Scan Github App.

If no supported IAC code is found, create a default TF configuration and dummy TF
file to ensure Prisma Scanning checks on pull requests do not fail.

If valid TF/CFM is ever found AND a dummy.tf file exists, remove the dummy file and
create the appropriate default configuration to enable Prisma IAC scanning.

NOTE: If you are creating CFM via another method - Ansible templates for example - the
resulting CFM templates are not in the repo and will not be found by this tool or scanned
by Prisma IAC scanning.
"""

import os
import io
import sys

from pathlib import Path
from shutil import copyfile


def set_code_path():
    """
    Set path to checked out code repo
    """

    try:
        code_path = os.environ['GITHUB_WORKSPACE']
    except KeyError:
        print("Could not find environment variable GITHUB_WORKSPACE")
        sys.exit(1)

    return code_path


def search_for_iac(code_path):
    """
    Check for presence of TF or CFM IAC files
    """

    print("Path is " + code_path)
    supported_files = ("tf", "yml", "yaml", "json")
    result = []

    for root, dirs, files in os.walk(code_path):
        for name in files:
            if name.lower().endswith(tuple(supported_files)):
                result.append(os.path.join(root, name))

    return result


def check_iac_type(targets):
    """
    Count how many of each IAC type we have and return type
    """

    count_tf = 0
    count_cfm= 0

    for target in targets:
        if target.lower().endswith("tf"):
            count_tf += 1

        if target.lower().endswith(('json','yaml','yml')):
            with io.open(target, encoding="utf-8") as file:
                if "AWSTemplateFormatVersion" in file.read():
                    count_cfm += 1

    if count_tf > 0 and count_cfm > 0:
        # Run away, Prisma IAC scanning does not support this.
        print("Oh no! We have CFM and TF in the same repo. Run away, run away!")
        sys.exit(1)

    if count_tf == 0 and count_cfm == 0:
        iac_type = "none"

    if count_tf > 0:
        iac_type = "tf"

    if count_cfm > 0:
        iac_type = "cfm"

    return iac_type


def configure_dirs(code_path):
    """
    Create required dirs if they do not already exist
    """

    if not os.path.exists(code_path + "/.prismaCloud"):
        os.makedirs(code_path + "/.prismaCloud")

    if not os.path.exists(code_path + "/.github"):
        os.makedirs(code_path + "/.github")


def configure_tf(is_dummy, path):
    """
    Configure Prisma IAC scanner to scan for Terraform
    """

    code_path = path

    if is_dummy:
        print("Configuring for dummy TF")
        Path(code_path + "/dummy.tf").touch()
    else:
        if os.path.exists(code_path + "/dummy.tf"):
            # Real TF IAC content has been found where there previous was none.
            # Remove the dummy file.
            os.remove(code_path + "/dummy.tf")
        print("Configuring for TF")

    copyfile('/config-tf.yml', code_path +'/.prismaCloud/config.yml')
    copyfile('/prisma-cloud-config.yml', code_path + '/.github/prisma-cloud-config.yml')


def configure_cfm(code_path):
    """
    Configure Prisma IAC scanner to scan for CloudFormation
    """

    print("Configuring for CFM")

    copyfile('/config-cfm.yml', code_path + "/.prismaCloud/config.yml")
    copyfile('/prisma-cloud-config.yml', code_path + "/.github/prisma-cloud-config.yml")


def git_commit():
    """
    Commit prisma config to git repo
    """

    os.system('''
    echo "Checking current working dir"
    pwd
    ls -lah
    echo "Configuring git username and email address
    git config --global user.email "actions.public.prismaconfig@github.com/uts-itd/"
    git config --global user.name "Prisma IAC config GitHub Action"
    echo "Running 'git add'"
    git add --all .
    git diff --cached
    echo "Commiting changes..."
    git commit -m 'Adding prisma IAC scan config'
    echo "Pushing changes..."
    git push
    echo "Show git log (may truncate)"
    git log
    ''')

    print("Finished git commit")



if __name__ == "__main__" :

    repo_code_path = set_code_path()
    interesting_files = search_for_iac(repo_code_path)
    scan_type = check_iac_type(interesting_files)

    configure_dirs(repo_code_path)

    if scan_type == "tf":
        configure_tf(is_dummy=False, path=repo_code_path)
    elif scan_type == "cfm":
        configure_cfm(repo_code_path)
    elif scan_type == "none":
        configure_tf(is_dummy=True, path=repo_code_path)

    print("Found IAC code for " + scan_type)

    print("Result list")
    print(interesting_files)

    git_commit()
