import os
import utils

from jinja2 import Template
from fabconfig import env


def push_config_to_s3():
    utils.status('Pushing %(environment)s config to S3' % env)
    bucket = env.connections.s3.get_bucket(env.s3_bootstrap_bucket)
    for (dirpath, dirname, filenames) in os.walk(env.bootstrap_folder):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            key_name = os.path.join(env.environment, filepath)
            key = bucket.new_key(key_name)
            contents = get_bootstrap_file(filepath)
            key.set_contents_from_string(contents)
            key.set_acl('authenticated-read')
    utils.success('Finished pushing deploy script to S3')


def get_bootstrap_file(file_path):
    with open(file_path, 'r') as opened_file:
        template = Template(opened_file.read())
        return template.render(**env)
