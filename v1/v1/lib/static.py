#!/usr/bin/env python
# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.verbify.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is verbify.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is verbify Inc.
#
# All portions of the code written by verbify are Copyright (c) 2006-2015 verbify
# Inc. All Rights Reserved.
###############################################################################

import sys
import os
import hashlib
import json
import base64
import shutil


def locate_static_file(name):
    from pylons import app_globals as g
    static_dirs = [plugin.static_dir for plugin in g.plugins]
    static_dirs.insert(0, g.paths['static_files'])

    for static_dir in reversed(static_dirs):
        file_path = os.path.join(static_dir, name.lstrip('/'))
        if os.path.exists(file_path):
            return file_path


def static_mtime(name):
    path = locate_static_file(name)
    if path:
        return os.path.getmtime(path)


def generate_static_name(name, base=None):
    """Generate a unique filename.
    
    Unique filenames are generated by base 64 encoding the first 64 bits of
    the SHA1 hash. This hash string is added to the filename before the extension.
    """
    if base:
        path = os.path.join(base, name)
    else:
        path = name

    sha = hashlib.sha1(open(path).read()).digest()
    shorthash = base64.urlsafe_b64encode(sha[0:8]).rstrip("=")
    name, ext = os.path.splitext(name)
    return name + '.' + shorthash + ext


def update_static_names(names_file, files):
    """Generate a unique file name mapping for ``files`` and write it to a
    JSON file at ``names_file``."""
    if os.path.exists(names_file):
        names = json.load(open(names_file))
    else:
        names = {}

    base = os.path.dirname(names_file)
    for path in files:
        name = os.path.relpath(path, base)
        mangled_name = generate_static_name(name, base)
        names[name] = mangled_name

        if not os.path.islink(path):
            mangled_path = os.path.join(base, mangled_name)
            shutil.move(path, mangled_path)
            # When on NFS, cp has a bad habit of turning our symlinks into
            # hardlinks. shutil.move will then call rename which will noop in
            # the case of hardlinks to the same inode.
            if os.path.exists(path):
                os.unlink(path)
            os.symlink(mangled_name, path)

    json_enc = json.JSONEncoder(indent=2, sort_keys=True)
    open(names_file, "w").write(json_enc.encode(names))

    return names


if __name__ == "__main__":
    update_static_names(sys.argv[1], sys.argv[2:])
