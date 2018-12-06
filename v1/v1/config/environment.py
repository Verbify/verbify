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

import os
import mimetypes

from mako.lookup import TemplateLookup
from pylons.error import handle_mako_error
from pylons.configuration import PylonsConfig

import v1.lib.helpers
from v1.config.paths import (
    get_v1_path,
    get_built_statics_path,
    get_raw_statics_path,
)
from v1.config.routing import make_map
from v1.lib.app_globals import Globals
from v1.lib.configparse import ConfigValue


mimetypes.init()


def load_environment(global_conf={}, app_conf={}, setup_globals=True):
    v1_path = get_v1_path()
    root_path = os.path.join(v1_path, 'v1')

    paths = {
        'root': root_path,
        'controllers': os.path.join(root_path, 'controllers'),
        'templates': [os.path.join(root_path, 'templates')],
    }

    if ConfigValue.bool(global_conf.get('uncompressedJS')):
        paths['static_files'] = get_raw_statics_path()
    else:
        paths['static_files'] = get_built_statics_path()

    config = PylonsConfig()

    config.init_app(global_conf, app_conf, package='v1', paths=paths)

    # don't put action arguments onto c automatically
    config['pylons.c_attach_args'] = False

    # when accessing non-existent attributes on c, return "" instead of dying
    config['pylons.strict_tmpl_context'] = False

    g = Globals(config, global_conf, app_conf, paths)
    config['pylons.app_globals'] = g

    if setup_globals:
        config['v1.import_private'] = \
            ConfigValue.bool(global_conf['import_private'])
        g.setup()
        g.plugins.declare_queues(g.queues)

    g.plugins.load_plugins(config)
    config['v1.plugins'] = g.plugins
    g.startup_timer.intermediate("plugins")

    config['pylons.h'] = v1.lib.helpers
    config['routes.map'] = make_map(config)

    #override the default response options
    config['pylons.response_options']['headers'] = {}

    # when mako loads a previously compiled template file from its cache, it
    # doesn't check that the original template path matches the current path.
    # in the event that a new plugin defines a template overriding a verbify
    # template, unless the mtime newer, mako doesn't update the compiled
    # template. as a workaround, this makes mako store compiled templates with
    # the original path in the filename, forcing it to update with the path.
    if "cache_dir" in app_conf:
        module_directory = os.path.join(app_conf['cache_dir'], 'templates')

        def mako_module_path(filename, uri):
            filename = filename.lstrip('/').replace('/', '-')
            path = os.path.join(module_directory, filename + ".py")
            return os.path.abspath(path)
    else:
        # disable caching templates since we don't know where they should go.
        module_directory = mako_module_path = None

    # set up the templating system
    config["pylons.app_globals"].mako_lookup = TemplateLookup(
        directories=paths["templates"],
        error_handler=handle_mako_error,
        module_directory=module_directory,
        input_encoding="utf-8",
        default_filters=["conditional_websafe"],
        filesystem_checks=getattr(g, "reload_templates", False),
        imports=[
            "from v1.lib.filters import websafe, unsafe, conditional_websafe",
            "from pylons import request",
            "from pylons import tmpl_context as c",
            "from pylons import app_globals as g",
            "from pylons.i18n import _, ungettext",
        ],
        modulename_callable=mako_module_path,
    )

    if setup_globals:
        g.setup_complete()

    return config
