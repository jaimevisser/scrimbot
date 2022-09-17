from typing import Type, Callable

import pytz

import scrimbot


class Setting:

    def __init__(self, setting_type: Type = None, default=None, required=False):
        self.required = required
        self.type = setting_type
        self._default = default
        self.value = None

    def validate(self):
        if self.value is None and not self.required:
            return
        if not isinstance(self.value, self.type):
            raise ParseException("value is the wrong type")

    @property
    def value_or_default(self):
        if self.value is None:
            return self._default
        return self.value


class TimezoneSetting(Setting):

    def __init__(self):
        super().__init__(str, pytz.UTC, required=True)

    def validate(self):
        super(TimezoneSetting, self).validate()
        if self.value not in pytz.all_timezones:
            raise ParseException(f"`{self.value}` is not a valid timezone, check pytz timezones.")


class ChannelSetting(Setting):

    def __init__(self, channels: Callable[[], set[int]]):
        super().__init__(int)
        self.__channels = channels

    def validate(self):
        super(ChannelSetting, self).validate()
        if self.value is not None and self.value not in self.__channels():
            raise ParseException(f"`{self.value}` is not a valid channel.")


class RoleSetting(Setting):

    def __init__(self, roles: Callable[[], set[int]]):
        self.__roles = roles
        super().__init__(int)

    def validate(self):
        super(RoleSetting, self).validate()
        if self.value is not None and self.value not in self.__roles():
            raise ParseException(f"`{self.value}` is not a valid role.")


class ParseException(Exception):
    pass


class Settings:

    def __init__(self, settings_store: scrimbot.Store[dict], channels: Callable[[], set[int]],
                 roles: Callable[[], set[int]]):
        self.__roles = roles
        self.__channels = channels
        self.__settings: scrimbot.Store[dict] = settings_store

    @property
    def __template(self):
        return {
            "server": {
                "mod_channel": ChannelSetting(self.__channels),
                "timezone": TimezoneSetting(),
                "reports_per_day": Setting(int, 2),
                "timeout_role": RoleSetting(self.__roles),
                "invite_channel": ChannelSetting(self.__channels)
            },
            "channel_defaults": {
                "broadcast_channel": ChannelSetting(self.__channels),
                "ping_cooldown": Setting(int, 5),
                "scrimmer_role": RoleSetting(self.__roles),
                "prefix": Setting(str, "Mixed Scrim")
            },
            "channel": {}
        }

    def combined(self, new_data: dict) -> dict:
        template = self.__template

        Settings.__check_keys(new_data.keys(), template.keys())

        if "server" not in new_data.keys():
            raise ParseException("settings need to contain a `server` section.")
        self.__combine_dict(template["server"], new_data["server"])

        if "channel_defaults" in new_data.keys():
            self.__combine_dict(template["channel_defaults"], new_data["channel_defaults"])

        if "channel" in new_data.keys():
            channels = new_data["channel"]
            if not isinstance(channels, dict):
                raise ParseException("`channels` should contain a list of channels")

            for k, v in channels.items():
                if not isinstance(v, dict):
                    raise ParseException(f"channel `{v}` should contain a list of channel-specific settings")
                channel_template = self.__template["channel_defaults"]
                self.__combine_dict(channel_template, v)
                template["channel"][k] = channel_template

        return template

    @staticmethod
    def __combine_dict(template: dict, new_data: dict):
        Settings.__check_keys(new_data.keys(), template.keys())

        for k, v in new_data.items():
            setting = template[k]
            if isinstance(setting, Setting):
                setting.value = v

    @staticmethod
    def __check_keys(data_keys, valid_keys):
        new_keys = set(data_keys)
        template_keys = set(valid_keys)
        if not new_keys.issubset(template_keys):
            raise ParseException("Invalid keys found: " + ", ".join(new_keys - template_keys))

    def __validate(self, data: dict):
        for k, v in data.items():
            if isinstance(v, Setting):
                v.validate()
            if isinstance(v, dict):
                if k == "channel":
                    channels = set([int(c) for c in v.keys()])
                    invalid_channels = channels - self.__channels()
                    if len(invalid_channels) > 0:
                        raise ParseException(
                            "These are not valid channels: `" + "`, `".join([str(c) for c in invalid_channels]) + "`")

                self.__validate(v)

    @staticmethod
    def __flatten(data: dict, use_defaults: bool = False):
        dead_keys = []

        for k, v in data.items():
            if isinstance(v, dict):
                Settings.__flatten(v, use_defaults=use_defaults)
                if len(v) == 0:
                    dead_keys.append(k)
            if isinstance(v, Setting):
                data[k] = v.value_or_default if use_defaults else v.value
                if data[k] is None:
                    dead_keys.append(k)

        for k in dead_keys:
            del data[k]

    def get_filename(self):
        self.__settings.sync()
        return self.__settings.file

    def replace(self, data):
        new_data = self.combined(data)
        self.__validate(new_data)
        self.__flatten(new_data)
        self.__settings.data.clear()
        self.__settings.data.update(new_data)
        self.__settings.sync()

    @property
    def server(self) -> dict:
        data = self.combined(self.__settings.data)
        self.__flatten(data, use_defaults=True)
        return data["server"]

    def channel(self, channel: int) -> dict:
        data = self.combined(self.__settings.data)
        self.__flatten(data, use_defaults=True)
        return data.get('channel', {}).get(str(channel), data["channel_defaults"])

    @property
    def channels(self) -> dict:
        data = self.combined(self.__settings.data)
        self.__flatten(data, use_defaults=True)
        return data.get('channel', {})
