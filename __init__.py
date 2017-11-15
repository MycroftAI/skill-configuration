# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

import os
from adapt.intent import IntentBuilder
from os.path import isfile, expanduser
from requests import HTTPError
from subprocess import check_output, STDOUT

from mycroft.api import DeviceApi
from mycroft.messagebus.message import Message
from mycroft.skills.scheduled_skills import ScheduledSkill

__author__ = 'augustnmonteiro'


class ConfigurationSkill(ScheduledSkill):
    def __init__(self):
        super(ConfigurationSkill, self).__init__("ConfigurationSkill")
        self.max_delay = self.config.get('max_delay')
        self.api = DeviceApi()
        self.config_hash = ''

    def initialize(self):
        intent = IntentBuilder("UpdateConfigurationIntent") \
            .require("ConfigurationSkillKeyword") \
            .require("ConfigurationSkillUpdateVerb") \
            .build()
        self.register_intent(intent, self.handle_update_intent)
        intent = IntentBuilder('SetKeyword') \
            .require('SetKeyword') \
            .require('ListenerKeyword') \
            .require('ListenerType') \
            .build()
        self.register_intent(intent, self.handle_set_listener)
        self.schedule()

    def handle_set_listener(self, message):
        try:
            from mycroft.configuration.config import (
                LocalConf, USER_CONFIG, Configuration
            )
            module = message.data['ListenerType'].replace(' ', '')
            module = module.replace('default', 'pocketsphinx')
            config = Configuration.get()

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

            if config['hotwords']['hey mycroft']['module'] == module:
                self.speak_dialog('listener.same', data={'listener': module})
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
            self.speak_dialog('set.listener', data={'listener': module})
        except (NameError, SyntaxError, ImportError):
            self.speak_dialog('must.update')

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
        config = self.api.find_setting()
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

    def stop(self):
        pass


def create_skill():
    return ConfigurationSkill()
