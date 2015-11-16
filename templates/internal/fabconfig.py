from fabric.api import env

# Environments
env.project = 'tangentsnowball'
env.root_dir = '/var/www/tangentsnowball'
env.builds_dir = '/var/www/tangentsnowball/builds'
env.web_dir = 'www'


def dev():
    env.build = 'dev'
    env.hosts = ['192.168.125.248']
    prepare()


def stage():
    env.hosts = ['192.168.125.248']
    env.build = 'stage'
    prepare()


def production():
    env.build = 'production'
    env.hosts = ['192.168.125.247']
    prepare()


def prepare():
    env.virtualenv = '/%(root_dir)s/environments/%(build)s' % env
    env.code_dir = '/%(builds_dir)s/%(build)s' % env
    env.nginx_conf = 'deploy/nginx/%(build)s.conf' % env
    env.nginx_users = 'deploy/nginx/users'
    env.supervisor_conf = 'deploy/supervisor/%(build)s.conf' % env
    env.supervisor_app_name = '%(project)s-%(build)s' % env
    env.touch_reload = 'conf/uwsgi/%(build)s.ini' % env
    env.gocd_pipeline_dir = '/var/lib/go-agent/pipelines/tangent-snowball'


def local_deploy():
    env.is_local = True
