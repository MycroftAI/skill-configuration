# Copyright 2017, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import random
from adapt.intent import IntentBuilder
from os.path import isfile, expanduser
from requests import HTTPError
from subprocess import check_output, STDOUT

from mycroft.api import DeviceApi
from mycroft.messagebus.message import Message
from mycroft.skills.core import intent_handler
from mycroft.skills.scheduled_skills import ScheduledSkill


# TODO: Change from ScheduledSkill
class ConfigurationSkill(ScheduledSkill):
    def __init__(self):
        super(ConfigurationSkill, self).__init__("ConfigurationSkill")
        self.max_delay = self.config.get('max_delay')
        self.api = DeviceApi()
        self.config_hash = ''

    def initialize(self):
        self.schedule()

    @intent_handler(IntentBuilder('').require("What").require("Name"))
    def handle_query_name(self, message):
        device = DeviceApi().get()
        self.speak_dialog("my.name.is", data={"name": device["name"]})

    @intent_handler(IntentBuilder('').require("What").require("Location"))
    def handle_what_is_location(self, message):
        # "what is your location" is the same as "where are you", but
        # was difficult to fit into the same intent vocabulary
        self.handle_where_are_you(message)

    @intent_handler(IntentBuilder('').require("WhereAreYou"))
    def handle_where_are_you(self, message):
        from mycroft.configuration.config import Configuration
        config = Configuration.get()
        data = {"city": config["location"]["city"]["name"],
                "state": config["location"]["city"]["state"]["name"],
                "country": config["location"]["city"]["state"]["country"]["name"]}  # nopep8

        self.speak_dialog("i.am.at", data)

    @intent_handler(IntentBuilder('SetListenerIntent').
                    require('SetKeyword').
                    require('ListenerKeyword').
                    require('ListenerType'))
    def handle_set_listener(self, message):
        try:
            from mycroft.configuration.config import (
                LocalConf, USER_CONFIG, Configuration
            )
            module = message.data['ListenerType'].replace(' ', '')
            module = module.replace('default', 'pocketsphinx')
            name = module.replace('pocketsphinx', 'pocket sphinx')
            config = Configuration.get()

            if config['hotwords']['hey mycroft']['module'] == module:
                self.speak_dialog('listener.same', data={'listener': name})
                return

            new_config = {
                'precise': {
                    'dist_url': 'http://bootstrap.mycroft.ai/'
                                'artifacts/static/daily/'
                },
                'hotwords': {'hey mycroft': {'module': module}}
            }
            user_config = LocalConf(USER_CONFIG)
            user_config.merge(new_config)
            user_config.store()

            self.emitter.emit(Message('configuration.updated'))

            if module == 'precise':
                exe_path = expanduser('~/.mycroft/precise/precise-stream')
                if isfile(exe_path):
                    self.enclosure.mouth_text('Checking version...')
                    version = check_output([exe_path, '-v'], stderr=STDOUT)
                    if version.strip() == '0.1.0':
                        os.remove(exe_path)
                    self.enclosure.mouth_reset()
                else:
                    self.speak_dialog('download.started')
                    return

            self.speak_dialog('set.listener', data={'listener': name})
        except (NameError, SyntaxError, ImportError):
            self.speak_dialog('must.update')

    @intent_handler(IntentBuilder('UpdatePrecise').
                    require('ConfigurationSkillUpdateVerb').
                    require('PreciseKeyword'))
    def handle_update_precise(self, message):
        try:
            from mycroft.configuration.config import Configuration
            module = Configuration.get()['hotwords']['hey mycroft']['module']
            model_file = expanduser('~/.mycroft/precise/hey-mycroft.pb')
            if module != 'precise':
                self.speak_dialog('not.precise')
            if isfile(model_file):
                os.remove(model_file)
                new_conf = {'config': {'rand_val': random.random()}}
                self.emitter.emit(Message('configuration.patch', new_conf))
                self.emitter.emit(Message('configuration.updated'))
                self.speak_dialog('models.updated')
            else:
                self.speak_dialog('models.not.found')
        except (NameError, SyntaxError, ImportError):
            self.speak_dialog('must.update')

    @intent_handler(IntentBuilder('GetListenerIntent').
                    require('GetKeyword').
                    require('ListenerKeyword'))
    def handle_get_listener(self, message):
        try:
            from mycroft.configuration.config import Configuration
            module = Configuration.get()['hotwords']['hey mycroft']['module']
            name = module.replace('pocketsphinx', 'pocket sphinx')
            self.speak_dialog('get.listener', data={'listener': name})
        except (NameError, SyntaxError, ImportError):
            self.speak_dialog('must.update')

    @intent_handler(IntentBuilder('UpdateConfigurationIntent').
                    require("ConfigurationSkillKeyword").
                    require("ConfigurationSkillUpdateVerb"))
    def handle_update_intent(self, message):
        try:
            if self.update():
                self.speak_dialog("config.updated")
            else:
                self.speak_dialog("config.no_change")
        except HTTPError as e:
            self.__api_error(e)

    def notify(self, timestamp):
        try:
            self.update()
        except HTTPError as e:
            if e.response.status_code == 401:
                self.log.warn("Impossible to update configuration because "
                              "device isn't paired")
        self.schedule()

    def update(self):
        config = self.api.find_setting() or {}
        location = self.api.find_location()
        if location:
            config["location"] = location

        if self.config_hash != hash(str(config)):
            self.emitter.emit(Message("configuration.updated", config))
            self.config_hash = hash(str(config))
            return True
        else:
            return False

    def __api_error(self, e):
        if e.response.status_code == 401:
            self.speak_dialog('config.not.paired.dialog')

    def get_times(self):
        return [self.get_utc_time() + self.max_delay]


def create_skill():
    return ConfigurationSkill()
