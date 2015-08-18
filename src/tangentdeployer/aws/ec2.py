import time
import boto
import boto.s3
import boto.s3.key
import boto.ec2.autoscale
import boto.ec2.cloudwatch
import boto.ec2.elb
import boto.route53

from fabconfig import env
from fabric.operations import run
from fabric.contrib.files import upload_template

import utils


def get(instance_id):
    reservations = env.connections.ec2.get_all_instances(
        instance_ids=[instance_id])
    if not reservations:
        return
    return reservations[0].instances[0]


def provision_logging_instance():
    if is_logger_instance_running():
        return

    utils.status("Deploying logger instance")

    logger_reservation = env.connections.ec2.run_instances(
        image_id=env.logging_ami_id,
        min_count=1,
        max_count=1,
        key_name='%s-%s' % (env.project, env.environment),
        security_groups=['%s' % env.environment],
        user_data=utils.get_logging_user_data(env=env),
        instance_type=env.instance_type,
        instance_profile_name='%s-ec2-%s' % (env.project, env.environment)
    )

    for instance in logger_reservation.instances:

        utils.status("Waiting on logging instance to spin up...")
        instance_status = instance.update()
        while instance_status != 'running':
            time.sleep(5)
            instance_status = instance.update()
            print('Instance status: %s' % instance_status)

        utils.status("Naming instance")
        instance.add_tag('Name', '%s-logger' % env.project)

        utils.status('Getting logging volume')
        volume = get_logging_volume(instance)

        utils.status('Waiting on volume to be available')
        while volume.status != 'available':
            time.sleep(5)
            volume.update()
            print('Volume status: %s' % volume.status)

        utils.status('Attaching volume')
        volume.attach(instance.id, '/dev/sda2')

    utils.status('Linking logs URL')
    route53_zone = env.connections.route53.get_zone(env.zone)
    while not instance.dns_name:
        time.sleep(1)
        instance.update()

    for url in env.logging_urls:
        route53_zone.update_cname(
            name=url,
            value=instance.dns_name,
            ttl=60
        )
    utils.success('Finished provisioning logging instance')


def is_logger_instance_running():
    logger_filters = {
        'tag:Name': '%s-logger' % env.project,
        'instance-state-name': 'running'
    }

    logger_instances = [
        instance
        for reservation in env.connections.ec2.get_all_instances(
            filters=logger_filters)
        for instance in reservation.instances
    ]
    return bool(logger_instances)


def get_logging_volume(instance):
    volume_filters = {'tag:Name': 'logger-volume'}
    volume_status_filters = {'block-device-mapping.status': 'attached'}
    status_filters = dict(
        volume_filters.items() + volume_status_filters.items())
    logger_volumes = env.connections.ec2.get_all_volumes(filters=volume_filters)
    if logger_volumes:
        attached_volumes = boto.ec2.get_all_volumes_status(filters=status_filters)
        if attached_volumes:
            env.connections.ec2.detach_volume(attached_volumes[0].id)
        return attached_volumes[0]
    return create_logging_volume(instance=instance)


def create_logging_volume(instance):
    return env.connections.ec2.create_volume(
        size=env.logging_ebs_volume_size,
        zone=instance.placement,
        volume_type=env.logging_ebs_volume_type)


def deploy_nagios_config(autoscaling_group):
    utils.status("Waiting on all instances to get an IP address")
    for index, instance in enumerate(autoscaling_group.instances):
        instance_obj = get(instance_id=instance.instance_id)
        while not instance_obj.dns_name:
            time.sleep(1)
            instance_obj = get(instance_id=instance.instance_id)
        utils.status('Pushing nagios config files')
        context = {
            'group_name': env.nagios_group_name,
            'host_name': '{project}-{environment}-{instance_id}'.format(
                         project=env.project,
                         environment=env.environment,
                         instance_id=instance.instance_id),
            'alias': instance_obj.dns_name,
            'address': instance_obj.dns_name
        }
        destination = '{nagios_dir}/{project}-{env}-{instance_id}.cfg'.format(
            nagios_dir=env.nagios_master_config_dir,
            project=env.project,
            env=env.environment,
            instance_id=instance.instance_id)
        upload_template(
            filename=env.nagios_master_config_file,
            destination=destination,
            context=context,
            use_jinja=True)
        restart_nagios()


def remove_nagios_config(autoscaling_group):
    utils.status('Removing nagios config...')
    for index, instance in enumerate(autoscaling_group.instances):
        config_file = nagios_config_file_for_instance(instance=instance)
        run('sudo /bin/rm -rf %s' % config_file)
        restart_nagios()


def nagios_config_file_for_instance(instance):
    return '{nagios_dir}/{project}-{env}-{instance_id}.cfg'.format(
        nagios_dir=env.nagios_master_config_dir,
        project=env.project,
        env=env.environment,
        instance_id=instance.instance_id)


def restart_nagios():
    result = run('sudo /etc/nagios/check_config')
    if result.return_code != 0:
        utils.failure('Nagios config check failed, removing nagios config')
        run('rm -rf %(nagios_master_config_dir)s/*%(environment)s*' % env)
    else:
        run('sudo /etc/init.d/nagios3 restart')
