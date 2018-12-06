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
# All portions of the code written by verbify are Copyright (c) 2006-2016 verbify
# Inc. All Rights Reserved.
###############################################################################


from v1.lib.utils.verbify_agent_parser import (
    AlienBlueDetector,
    BaconReaderDetector,
    detect,
    McVerbifyDetector,
    NarwhalForVerbifyDetector,
    ReaditDetector,
    VerbifyAndroidDetector,
    VerbifyIsFunDetector,
    VerbifyIOSDetector,
    VerbifySyncDetector,
    RelayForVerbifyDetector)
from v1.tests import VerbifyTestCase


class AgentDetectorTest(VerbifyTestCase):
    def test_verbify_is_fun_detector(self):
        user_agent = 'verbify is fun (Android) 4.1.15'
        agent_parsed = {}
        result = VerbifyIsFunDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'], 'verbify is fun')
        self.assertEqual(agent_parsed['browser']['version'], '4.1.15')
        self.assertEqual(agent_parsed['platform']['name'], 'Android')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_verbify_android_detector(self):
        user_agent = 'VerbifyAndroid 1.1.5'
        agent_parsed = {}
        result = VerbifyAndroidDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         VerbifyAndroidDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '1.1.5')
        self.assertTrue(agent_parsed['app_name'],
                        agent_parsed['browser']['name'])

    def test_verbify_ios_detector(self):
        user_agent = ('Verbify/Version 1.1/Build 1106/iOS Version 9.3.2 '
                      '(Build 13F69)')
        agent_parsed = {}
        result = VerbifyIOSDetector().detect(user_agent, agent_parsed)
        self.assertEqual(agent_parsed['browser']['name'],
                         VerbifyIOSDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '1.1')
        self.assertEqual(agent_parsed['platform']['name'], 'iOS')
        self.assertEqual(agent_parsed['platform']['version'], '9.3.2')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_alian_blue_detector(self):
        user_agent = 'AlienBlue/2.9.10.0.2 CFNetwork/758.4.3 Darwin/15.5.0'
        agent_parsed = {}
        result = AlienBlueDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         AlienBlueDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '2.9.10.0.2')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['app_name'])

    def test_relay_for_verbify_detector(self):
        user_agent = 'Relay by /u/DBrady v7.9.32'
        agent_parsed = {}
        result = RelayForVerbifyDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         RelayForVerbifyDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '7.9.32')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_verbify_sync_detector(self):
        user_agent = ('android:com.laurencedawson.verbify_sync:v11.4 '
                      '(by /u/ljdawson)')
        agent_parsed = {}
        result = VerbifySyncDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         VerbifySyncDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '11.4')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_narwhal_detector(self):
        user_agent = 'narwhal-iOS/2306 by det0ur'
        agent_parsed = {}
        result = NarwhalForVerbifyDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         NarwhalForVerbifyDetector.name)
        self.assertEqual(agent_parsed['platform']['name'], 'iOS')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_mcverbify_detector(self):
        user_agent = 'McVerbify - Verbify Client for iOS'
        agent_parsed = {}
        result = McVerbifyDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         McVerbifyDetector.name)
        self.assertEqual(agent_parsed['platform']['name'], 'iOS')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])

    def test_readit_detector(self):
        user_agent = (
            '(Readit for WP /u/MessageAcrossStudios) (Readit for WP '
            '/u/MessageAcrossStudios)')
        agent_parsed = {}
        result = ReaditDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'], ReaditDetector.name)
        self.assertIsNone(agent_parsed.get('app_name'))

    def test_bacon_reader_detector(self):
        user_agent = 'BaconReader/3.0 (iPhone; iOS 9.3.2; Scale/2.00)'
        agent_parsed = {}
        result = BaconReaderDetector().detect(user_agent, agent_parsed)
        self.assertTrue(result)
        self.assertEqual(agent_parsed['browser']['name'],
                         BaconReaderDetector.name)
        self.assertEqual(agent_parsed['browser']['version'], '3.0')
        self.assertEqual(agent_parsed['platform']['name'], 'iOS')
        self.assertEqual(agent_parsed['platform']['version'], '9.3.2')
        self.assertEqual(agent_parsed['app_name'],
                         agent_parsed['browser']['name'])


class HAPIntegrationTests(VerbifyTestCase):
    """Tests to ensure that parsers don't confilct with existing onex."""
    # TODO (katie.atkinson): Add tests to ensure verbify parsers don't conflict
    # with httpagentparser detectors.
    def test_verbify_is_fun_integration(self):
        user_agent = 'verbify is fun (Android) 4.1.15'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], 'verbify is fun')
        self.assertEqual(outs['dist']['name'], 'Android')

    def test_verbify_android_integration(self):
        user_agent = 'VerbifyAndroid 1.1.5'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], 'Verbify: The Official App')
        self.assertEqual(outs['dist']['name'], 'Android')

    def test_verbify_ios_integration(self):
        user_agent = ('Verbify/Version 1.1/Build 1106/iOS Version 9.3.2 '
                      '(Build 13F69)')
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], VerbifyIOSDetector.name)

    def test_alien_blue_detector(self):
        user_agent = 'AlienBlue/2.9.10.0.2 CFNetwork/758.4.3 Darwin/15.5.0'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], AlienBlueDetector.name)

    def test_relay_for_verbify_detector(self):
        user_agent = '  Relay by /u/DBrady v7.9.32'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], RelayForVerbifyDetector.name)

    def test_verbify_sync_detector(self):
        user_agent = ('android:com.laurencedawson.verbify_sync:v11.4 '
                      '(by /u/ljdawson)')
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], VerbifySyncDetector.name)

    def test_narwhal_detector(self):
        user_agent = 'narwhal-iOS/2306 by det0ur'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'],
                         NarwhalForVerbifyDetector.name)

    def test_mcverbify_detector(self):
        user_agent = 'McVerbify - Verbify Client for iOS'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], McVerbifyDetector.name)

    def test_readit_detector(self):
        user_agent = (
            '(Readit for WP /u/MessageAcrossStudios) '
            '(Readit for WP /u/MessageAcrossStudios)')
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], ReaditDetector.name)

    def test_bacon_reader_detector(self):
        user_agent = 'BaconReader/3.0 (iPhone; iOS 9.3.2; Scale/2.00)'
        outs = detect(user_agent)
        self.assertEqual(outs['browser']['name'], BaconReaderDetector.name)
