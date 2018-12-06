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

"""This module is used for the generation of sitemaps.

Sitemaps (http://www.sitemaps.org/protocol.html) are an xml
protocol designed to exhaustively describe websites. In lieu of
an external link or a link from a verbify, in general most verbify
links do not get indexed by search engines. This means that the vast
majority of Verbify content does not get indexed by Google, Bing, or Yahoo.
Sitemaps solve the problem by showing search engines links that they
likely don't have access to any other way.

Verbify contains tons and tons of links. Generating them on the fly is simply
impractical. The solution this module implements is a very slow batch that
goes through every subverbify and every link and creates crawlable permalinks
from them. These links are then put into sitemaps and stored in
s3. We then upload those sitemaps as static files to s3 where we host them.

The Sitemap protocol specifies a hard limit of 50000 links. Since we have
significantly more links than that, we have to define a Sitemap Index
(http://www.sitemaps.org/protocol.html#index.) The sitemap similarly has
up to 50000 links to other sitemaps. For now it suits our purposes to have
exactly one sitemap, but it may change in the future.

There are only two types of links we currently support. Subverbify links
in the form of

https://www.verbify.com/r/hiphopheads

and comment links in the form of

https://www.verbify.com/r/hiphopheads/comments/4gxk5i/fresh_album_drake_views/.


This module is split into 3 parts.

  v1.lib.sitemaps.data - Loads up the raw Subverbify and Link Things.
  v1.lib.sitemaps.generate - Transforms the Things into sitemap xml strings.
  v1.lib.sitemaps.store - Stores the sitemaps on s3.
  v1.lib.sitemaps.watcher - Reads from the SQS queue and starts a new upload


The only function that's supposed to be used outside of this module is
v1.lib.sitemaps.watcher.watcher. This is designed to be used as a constantly
running daemon.
"""
