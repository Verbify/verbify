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

import os
import fnmatch
import sys
from setuptools import setup, find_packages, Extension


commands = {}


try:
    from Cython.Build import cythonize
except ImportError:
    print "Cannot find Cython. Skipping Cython build."
    pyx_extensions = []
else:
    pyx_files = []
    for root, directories, files in os.walk('.'):
        for f in fnmatch.filter(files, '*.pyx'):
            pyx_files.append(os.path.join(root, f))
    pyx_extensions = cythonize(pyx_files)


# guard against import errors in case this is the first run of setup.py and we
# don't have any dependencies (including baseplate) yet
try:
    from baseplate.integration.thrift.command import ThriftBuildPyCommand
except ImportError:
    print "Cannot find Baseplate. Skipping Thrift build."
else:
    commands["build_py"] = ThriftBuildPyCommand


setup(
    name="v1",
    version="",
    install_requires=[
        "Pylons",
        "Routes",
        "mako>=0.5",
        "boto >= 2.0",
        "pytz",
        "pycrypto",
        "Babel>=1.0",
        "cython>=0.14",
        "SQLAlchemy",
        "BeautifulSoup",
        "chardet",
        "psycopg2",
        "pycassa>=1.7.0",
        "pycaptcha",
        "amqplib",
        "py-bcrypt",
        "snudown>=1.1.0",
        "l2cs>=2.0.2",
        "lxml",
        "kazoo",
        "stripe",
        "requests",
        "tinycss2",
        "unidecode",
        "PyYAML",
        "Pillow",
        "pylibmc==1.2.2",
        "webob",
        "webtest",
        "python-snappy",
        "httpagentparser==1.7.8",
        "raven",
    ],
    # setup tests (allowing for "python setup.py test")
    tests_require=['mock', 'nose', 'coverage'],
    test_suite="nose.collector",
    dependency_links=[
        "https://github.com/verbify/snudown/archive/v1.1.3.tar.gz#egg=snudown-1.1.3",
        "https://s3.amazonaws.com/code.verbify.com/pycaptcha-0.4.tar.gz#egg=pycaptcha-0.4",
    ],
    packages=find_packages(exclude=["ez_setup"]),
    cmdclass=commands,
    ext_modules=pyx_extensions + [
        Extension(
            "Cfilters",
            sources=[
                "v1/lib/c/filters.c",
            ]
        ),
    ],
    entry_points="""
    [paste.app_factory]
    main=v1:make_app
    [paste.paster_command]
    run = v1.commands:RunCommand
    shell = pylons.commands:ShellCommand
    [paste.filter_app_factory]
    gzip = v1.lib.gzipper:make_gzip_middleware
    [v1.provider.media]
    s3 = v1.lib.providers.media.s3:S3MediaProvider
    filesystem = v1.lib.providers.media.filesystem:FileSystemMediaProvider
    [v1.provider.cdn]
    fastly = v1.lib.providers.cdn.fastly:FastlyCdnProvider
    cloudflare = v1.lib.providers.cdn.cloudflare:CloudFlareCdnProvider
    null = v1.lib.providers.cdn.null:NullCdnProvider
    [v1.provider.auth]
    cookie = v1.lib.providers.auth.cookie:CookieAuthenticationProvider
    http = v1.lib.providers.auth.http:HttpAuthenticationProvider
    [v1.provider.support]
    zendesk = v1.lib.providers.support.zendesk:ZenDeskProvider
    [v1.provider.search]
    cloudsearch = v1.lib.providers.search.cloudsearch:CloudSearchProvider
    solr = v1.lib.providers.search.solr:SolrSearchProvider
    [v1.provider.image_resizing]
    imgix = v1.lib.providers.image_resizing.imgix:ImgixImageResizingProvider
    no_op = v1.lib.providers.image_resizing.no_op:NoOpImageResizingProvider
    unsplashit = v1.lib.providers.image_resizing.unsplashit:UnsplashitImageResizingProvider
    [v1.provider.email]
    null = v1.lib.providers.email.null:NullEmailProvider
    mailgun = v1.lib.providers.email.mailgun:MailgunEmailProvider
    """,
)