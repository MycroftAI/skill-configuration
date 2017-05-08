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


from adapt.intent import IntentBuilder
from requests import HTTPError

from mycroft.api import DeviceApi
from mycroft.messagebus.message import Message
from mycroft.skills.scheduled_skills import ScheduledSkill

__author__ = 'augustnmonteiro'


def parse_tts(tts_settings):
    """ Create tts entry from TtsSettings
        Args:
            tts_systems list of tts systems from Tartarus

        Returns: tts entry for config
    """
    for tts_system in tts_settings:
        if tts_system.get('active'):
            used_tts = tts_system
            break
    module = used_tts['@type']

    # remove server specific keys
    if '@type' in used_tts:
        used_tts.pop('@type')
    if 'active' in used_tts:
        used_tts.pop('active')

    # prepare tts entry
    tts = {}
    tts['module'] = module
    tts[module] = used_tts
    return tts


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
        self.schedule()

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
        config["tts"] = parse_tts(config.get("ttsSettings", []))

        if self.config_hash != hash(str(config)):
            self.emitter.emit(Message("configuration.updated", config))
            self.config_hash = hash(str(config))
            return True
        else:
            return False

    def __api_error(self, e):
        if e.response.status_code == 401:
            self.emitter.emit(Message("mycroft.not.paired"))

    def get_times(self):
        return [self.get_utc_time() + self.max_delay]

    def stop(self):
        pass


def create_skill():
    return ConfigurationSkill()
