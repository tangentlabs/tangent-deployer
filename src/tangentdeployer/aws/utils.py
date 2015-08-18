from jinja2 import Template
from importlib import import_module

from fabric.colors import green, red, yellow
from fabconfig import env


class BotoConnection(object):

    def __new__(cls, profile_name, services):
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(BotoConnection, cls)\
                .__new__(cls, profile_name, services)

        return cls.__instance__

    def __init__(self, profile_name, services):
        self.__connect_to_boto_services(profile_name, services)

    def __connect_to_boto_services(self, profile_name, services):
        for service_name in services:
            attribute_name = service_name.split('.')[-1]

            if hasattr(self, attribute_name):
                raise Exception("'%s' service connection already exists. Did "
                                "you define the same service twice, or have "
                                "two services with the same module "
                                "name?" % attribute_name)

            service = import_module(service_name)
            connection = service.connect_to_region(
                env.region, profile_name=env.profile_name)
            setattr(self, attribute_name, connection)


def message(color, msg):
    bar = '+' + '-' * (len(msg) + 2) + '+'
    print(color(''))
    print(color(bar))
    print(color("| %s |" % msg))
    print(color(bar))
    print(color(''))


def success(msg):
    message(green, msg)


def failure(msg):
    message(red, msg)


def status(msg):
    message(yellow, msg)


def get_app_user_data(env):
    user_data = open('bootstrap/app-user-data.sh').read()
    template = Template(user_data)
    return template.render(**env)


def get_logging_user_data(env):
    user_data = open('bootstrap/logging-user-data.sh').read()
    template = Template(user_data)
    return template.render(**env)


def security_groups():
    security_groups = env.connections.ec2.get_all_security_groups(
        groupnames=env.security_groups)
    return [security_group.id for security_group in security_groups]


class DoesNotExist(Exception):
    pass
