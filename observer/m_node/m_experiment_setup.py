# -*- coding: utf-8 -*-
"""Sensorlab experiment module.

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/12
Copyright 2015 Orange

# Overview
-----------
This module handles the experiment archive, checks its integrity and configure
the experiment module.

### Experiment configuration archive
-------------------------------------
The configuration archive is of type **tar.gz** and contains the following directories and files:

    - `firmwares/`: firmwares used for the experiment.

    - `manifest.yml`: experiment schedule and experiment configuration.

#### Manifest.yml
-----------------
The manifest file complies to the YAML specification.
It must contain the following structure: 

    `configuration`(dict):
            - node_id:  '{...}'

            - schedule:
                * time:		{'origin', 'on-last-event-completion', duration}
                  action:	{...}
                  parameters:
                    {...}:        {...}

                * {...}

            - firmwares:
                  * node_id:           {...}
                    file:         {...}
                    brief:        {...}

        `base_directory`(string): {...}

Controller node_commands may contain two types of placeholders :
    - executable placeholders           : identified by a <!name> tag where name is the executable ID.
    - configuration file placeholders   : identified by a <#name> tag where name is the configuration file ID.

Placeholders are resolved when the manifest is parsed for the first time.

"""

import os
import tempfile
import shutil
import tarfile
import yaml

from .. import m_common

PROFILE_FILENAME = 'behavior.tar.gz'
# archive members
FIRMWARES_SUBDIR = 'firmwares'
EXPERIMENT_MANIFEST = 'manifest.yml'

CONFIGURATION_MANDATORY_MEMBERS = [
    FIRMWARES_SUBDIR,
    EXPERIMENT_MANIFEST
]

# archive related errors
ERROR_MISSING_ELEMENT = 'missing element in archive: {0}\nprovided: {1}'
# manifest members
MANIFEST_MANDATORY_MEMBERS = [
    'firmwares',
    'schedule'
]


class Loader:
    def __init__(self, behavior_archive):
        self.temp_directory = None
        self.manifest = None
        self.firmwares = {}
        self.schedule = None

        # create a temporary directory and extract the content of the archive
        self.temp_directory = tempfile.mkdtemp()
        archive_path = os.path.join(self.temp_directory, PROFILE_FILENAME)
        try:
            # file upload
            behavior_archive.save(archive_path)
        except AttributeError:
            # file on m_system
            shutil.copy(behavior_archive, archive_path)

        with tarfile.open(archive_path) as archive:
            # validate the archive content
            archive_contents = archive.getnames()
            if any(elt not in archive_contents for elt in CONFIGURATION_MANDATORY_MEMBERS):
                # invalid archive content, raise an exception
                missing_elements = [elt for elt in CONFIGURATION_MANDATORY_MEMBERS if elt not in archive_contents]
                raise m_common.ExperimentSetupException(
                    m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(
                        'missing elements: ' + str(missing_elements) +
                        ' of archive_contents: ' + str(archive_contents)
                    )
                )
            # decompress the archive
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(archive, self.temp_directory)

        # read the manifest
        with open(os.path.join(self.temp_directory, EXPERIMENT_MANIFEST), 'r') as manifest_file:
            self.manifest = yaml.load(manifest_file.read())
        # validate the manifest
        for path in MANIFEST_MANDATORY_MEMBERS:
            # let's walk the manifest and check that mandatory members do exist
            iterator = self.manifest
            path_elements = path.split('/')
            for element in path_elements:
                try:
                    iterator = iterator[element]
                except:
                    raise m_common.ExperimentSetupException(
                        m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(
                            'element missing: ' + element + ' in: ' + path
                        )
                    )

        # register firmwares
        firmwares_dir = os.path.join(self.temp_directory, FIRMWARES_SUBDIR)
        for firmware in self.manifest['firmwares']:
            fid = firmware['id']
            ffile = firmware['file']
            self.firmwares[fid] = os.path.join(firmwares_dir, ffile)
            # check if node_firmware file is present
            if not os.path.isfile(self.firmwares[fid]):
                raise m_common.ExperimentSetupException(m_common.ERROR_MISSING_ARGUMENT_IN_ARCHIVE.format(ffile))
        # register the schedule
        self.schedule = self.manifest['schedule']

    def clean(self):
        shutil.rmtree(self.temp_directory)
