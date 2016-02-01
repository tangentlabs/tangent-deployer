import os
import datetime

from fabric.api import local, env
from fabric.operations import prompt
from fabric.colors import green, _wrap_with
from fabric.context_managers import lcd

green_bg = _wrap_with('42')
red_bg = _wrap_with('41')


def archive_repo():
    commit_id = get_commit_id()
    archive_filename = '/tmp/build-%s.tar.gz' % str(commit_id)

    local('git archive --format tar HEAD %s | gzip > %s' %
          (env.web_dir, archive_filename))
    return archive_filename


def unpack(archive_path):
    print(green("Creating build folder"))

    commit_id = get_commit_id()
    now = datetime.datetime.now()
    env.build_dir = '%s-%s' % (env.build, now.strftime('%Y-%m-%d-%H-%M'))
    local('sudo mkdir -p %(builds_dir)s' % env)

    with lcd(env.builds_dir):

        local('sudo tar xzf %s' % archive_path)

        # Create new build folder
        local('if [ -d "%(build_dir)s" ]; then sudo rm -rf "%(build_dir)s"; fi' % env)
        local('sudo mv %(web_dir)s %(build_dir)s' % env)

        if hasattr(env, 'media_dir'):
            link_media_dir()

        # Create new symlink
        local('if [ -h %(build)s ]; then sudo unlink %(build)s; fi' % env)
        local('sudo ln -s %(build_dir)s %(build)s' % env)

        # Add file indicating Git commit
        local('echo -e "commit: %s\nuser: %s" | '
              'sudo tee -a %s/build-info > /dev/null' %
              (commit_id, env.user, env.build))

        # Remove archive
        local('sudo rm %s' % archive_path)


def create_directory(directory):
    local('sudo mkdir -p %s' % directory)


def update_virtualenv():
    virtualenv_dir = os.path.join(env.root_dir, 'environments')
    create_directory(virtualenv_dir)
    if not os.path.exists(os.path.join(virtualenv_dir, env.build)):
        with lcd(virtualenv_dir):
            local('sudo virtualenv %s' % env.build)
    with lcd(env.code_dir):
        source_cmd('pip install -r deploy/requirements.txt')


def collect_static_files():
    create_directory(env.code_dir)
    with lcd(env.code_dir):
        manage_py_cmd('collectstatic --noinput')


def run_migrations():
    create_directory(env.code_dir)
    with lcd(env.code_dir):
        manage_py_cmd('migrate')


def syncdb():
    create_directory(env.code_dir)
    with lcd(env.code_dir):
        manage_py_cmd('syncdb --noinput')


def create_logging_dirs():
    logging_directory = os.path.join(env.root_dir, 'logs')
    create_directory(logging_directory)
    local('sudo chown -R www-data:www-data %s' % logging_directory)


def deploy_nginx_config():
    print(green('Moving nginx config into place'))
    with lcd(env.builds_dir):
        local('sudo mv %(build)s/%(nginx_conf)s '
              '/etc/nginx/sites-enabled/%(project)s-%(build)s.conf' % env)
        if 'nginx_users' in env:
            local('sudo mv %(build)s/%(nginx_users)s '
                  '/etc/nginx/%(project)s-%(build)s-users' % env)
    nginx_reload()


def deploy_supervisor_config():
    print(green('Moving supervisor config into place'))
    with lcd(env.builds_dir):
        local('sudo mv %(build)s/%(supervisor_conf)s '
              '/etc/supervisor/conf.d/%(project)s_%(build)s.conf' % env)


def deploy_cronjobs():
    "Deploys the cron jobs"
    print(green('Deploying cronjobs'))
    with lcd(env.builds_dir):
        local('if [ -f %(build)s/deploy/cron.d/*%(build)s ]; then '
              'mv %(build)s/deploy/cron.d/*%(build)s /etc/cron.d/; fi' % env)


def reload_app():
    if 'touch_reload' not in env:
        return
    print(green('Touching uWSGI ini file to reload python code'))
    with lcd(env.builds_dir):
        local('sudo touch %(builds_dir)s/%(build)s/%(touch_reload)s' % env)


def delete_old_builds():
    print(green('Deleting old builds'))
    with lcd(env.builds_dir):
        local('sudo find . -maxdepth 1 -type d -mtime +1 -exec rm -rf {} \;')


def nginx_reload():
    print(green('Reloading nginx config'))
    local('sudo /usr/sbin/nginx -s reload')


def reload_supervisor():
    print(green('Reloading supervisord'))
    local('sudo /usr/bin/supervisorctl reload')


def set_remote_user():
    if 'TANGENT_USER' in os.environ:
        env.user = os.environ['TANGENT_USER']
    else:
        prompt('Username for remote host? ', key='user', default=os.environ['USER'])


def source_cmd(cmd, *args, **kwargs):
    return local("sudo -- bash -c 'source %s/bin/activate && %s'"
                 % (env.virtualenv, cmd), *args, **kwargs)


def manage_py_cmd(cmd, *args, **kwargs):
    return source_cmd("DJANGO_CONF=conf.%s ./manage.py %s"
                      % (env.build, cmd), *args, **kwargs)


def get_commit_id():
    return local('git rev-parse HEAD', capture=True)[:20]


def link_media_dir():
    local('sudo ln -s %(media_dir)s %(build_dir)s/public/media' % env)
