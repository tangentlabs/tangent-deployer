import os
import utils

from jinja2 import Template
from fabconfig import env


def push_config_to_s3():
    utils.status('Pushing %(environment)s config to S3' % env)
    bucket = env.connections.s3.get_bucket(env.s3_bootstrap_bucket)
    files = {
        'dockercfg': env.dockercfg,
        'kibana.nginx': env.kibana_nginx_config,
        'nrpe.cfg': env.nagios_host_nrpe_config,
        'nrpe_local.cfg': env.nagios_host_local_nrpe_config,
        'logrotate.d/your-app': env.logrotate_config,
    }
    files.update(env.nagios_plugins)
    for filename, file_path in files.items():
        full_key_name = os.path.join(env.environment, 'bootstrap', filename)
        key = bucket.new_key(full_key_name)
        contents = get_bootstrap_file(file_path=file_path)
        key.set_contents_from_string(contents)
        key.set_acl('authenticated-read')
    utils.success('Finished pushing deploy script to S3')


def get_bootstrap_file(file_path):
    with open(file_path, 'r') as opened_file:
        template = Template(opened_file.read())
        return template.render(**env)
