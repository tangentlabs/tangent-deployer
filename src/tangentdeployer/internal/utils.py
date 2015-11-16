import os
import datetime

from fabric.api import local, env
from fabric.operations import prompt
from fabric.colors import green, _wrap_with
from fabric.context_managers import lcd

green_bg = _wrap_with('42')
red_bg = _wrap_with('41')


def archive_repo(branch):
    commit_id = get_commit_id()
    archive_filename = '/tmp/build-%s.tar.gz' % str(commit_id)

    local('git archive --format tar %s %s | gzip > %s' %
          (branch, env.web_dir, archive_filename))
    return archive_filename


def unpack(archive_path, branch):
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

        # Symlink in uploads folder
        local('sudo ln -s %(root_dir)s/media/%(build)s %(build_dir)s/public/managed' % env)

        # Create new symlink
        local('if [ -h %(build)s ]; then sudo unlink %(build)s; fi' % env)
        local('sudo ln -s %(build_dir)s %(build)s' % env)

        # Add file indicating Git commit
        local('echo -e "branch: %s\ncommit: %s\nuser: %s" | '
              'sudo tee -a %s/build-info > /dev/null' %
              (branch, commit_id, env.user, env.build))

        # Remove archive
        local('sudo rm %s' % archive_path)


def update_virtualenv():
    with lcd(env.code_dir):
        source_cmd('pip install -r deploy/requirements.txt')


def collect_static_files():
    with lcd(env.code_dir):
        manage_py_cmd('collectstatic --noinput')


def update_permissions():
    with lcd(env.code_dir):
        # Alter permissions to allow FEDs to alter files
        local('sudo chown -R root:www-data %(code_dir)s/templates %(code_dir)s/public' % env)
        local('sudo chmod -R g+w %(code_dir)s/templates %(code_dir)s/public' % env)
        local('sudo chmod +x %(code_dir)s/deploy/scripts/*' % env)


def run_migrations():
    with lcd(env.code_dir):
        manage_py_cmd('migrate')


def syncdb():
    with lcd(env.code_dir):
        manage_py_cmd('syncdb --noinput')


def create_logging_dirs():
    with lcd(env.builds_dir):
        local('sudo mkdir -p ../logs/')
        local('sudo chown -R www-data:www-data ../logs')


def deploy_nginx_config():
    print(green('Moving nginx config into place'))
    with lcd(env.builds_dir):
        local('sudo mv %(build)s/%(nginx_conf)s '
              '/etc/nginx/sites-enabled/%(project)s-%(build)s.conf' % env)
        local('sudo mv %(build)s/%(nginx_users)s '
              '/etc/nginx/%(project)s_%(build)s_users' % env)
    nginx_reload()


def deploy_supervisor_config():
    print(green('Moving supervisor config into place'))
    with lcd(env.builds_dir):
        local('sudo mv %(build)s/%(supervisor_conf)s /etc/supervisor/conf.d/' % env)


def deploy_cronjobs():
    "Deploys the cron jobs"
    print(green('Deploying cronjobs'))
    with lcd(env.builds_dir):
        local('if [ $(ls %(build)s/deploy/cron.d) ]; then mv %(build)s/deploy/cron.d/*%(build)s /etc/cron.d/; fi' % env)


def reload_app():
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
