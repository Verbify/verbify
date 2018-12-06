import os

from v1.lib.translation import I18N_PATH
from v1.lib.plugin import PluginLoader
from v1.lib import js

print 'POTFILE := ' + os.path.join(I18N_PATH, 'v1.pot')

plugins = PluginLoader()
print 'PLUGINS := ' + ' '.join(plugin.name for plugin in plugins
                               if plugin.needs_static_build)

print 'PLUGIN_I18N_PATHS := ' + ','.join(os.path.relpath(plugin.path)
                                         for plugin in plugins
                                         if plugin.needs_translation)

import sys
for plugin in plugins:
    print 'PLUGIN_PATH_%s := %s' % (plugin.name, plugin.path)

js.load_plugin_modules(plugins)
modules = dict((k, m) for k, m in js.module.iteritems())
print 'JS_MODULES := ' + ' '.join(modules.iterkeys())
outputs = []
for name, module in modules.iteritems():
    outputs.extend(module.outputs)
    print 'JS_MODULE_OUTPUTS_%s := %s' % (name, ' '.join(module.outputs))
    print 'JS_MODULE_DEPS_%s := %s' % (name, ' '.join(module.dependencies))

print 'JS_OUTPUTS := ' + ' '.join(outputs)
print 'DEFS_SUCCESS := 1'
