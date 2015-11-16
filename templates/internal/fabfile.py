from fabric.api import local, run, env
from fabric.context_managers import cd

from fabconfig import *  # noqa

from tangentdeployer.internal import utils


def deploy(branch='master'):
    archive_filename = utils.archive_repo(branch)
    utils.unpack(archive_filename, branch)
    utils.update_virtualenv()
    utils.collect_static_files()
    utils.syncdb()
    utils.run_migrations()

    utils.create_logging_dirs()
    utils.deploy_nginx_config()
    utils.deploy_supervisor_config()
    utils.deploy_cronjobs()

    utils.reload_app()
    utils.reload_supervisor()

    utils.delete_old_builds()


def local_deploy(branch=None):
    utils.set_remote_user()
    if not branch:
        branch = local('git rev-parse --abbrev-ref HEAD', capture=True)
    with cd(env.gocd_pipeline_dir):
        run('sudo -su go git checkout %s' % branch)
        run('sudo -su go git pull origin %s --force' % branch)
        run('sudo -su go ./go_deploy_%(build)s.sh' % env)
