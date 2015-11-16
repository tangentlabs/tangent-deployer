import time
import utils
import datetime
import boto.ec2.autoscale

from . import ec2
from fabconfig import env


def create_autoscaling_group(load_balancer):
    launch_configuration = create_launch_configuration()

    utils.status("Create auto scaling group")
    asg_name = 'asg-%s-%s-%d' % (env.project, env.environment, time.time())
    autoscaling_group = boto.ec2.autoscale.AutoScalingGroup(
        connection=env.connections.autoscale,
        name=asg_name,
        load_balancers=[load_balancer.name],
        availability_zones=env.zones,
        desired_capacity=env.asg_desired_capacity,
        default_cooldown=env.asg_default_cooldown,
        launch_config=launch_configuration,
        min_size=env.asg_min_size,
        max_size=env.asg_max_size,
    )
    env.connections.autoscale.create_auto_scaling_group(autoscaling_group)

    """
    We suspend the AddToLoadBalancer process of the Autoscaling group so we
    have time to make sure our instances have provisioned correctly and are
    behaving as expected.

    Suspending this process means the instances will not be added to the load
    balancer when they become healthy, but when we resume this process we need
    to register the instances explicitly.
    """
    utils.status('Suspending AddToLoadBalancer process')
    env.connections.autoscale.suspend_processes(
        autoscaling_group.name, scaling_processes=['AddToLoadBalancer'])

    tag(autoscaling_group=autoscaling_group, key='type', value='QA')
    tag(autoscaling_group=autoscaling_group, key='env', value=env.environment)
    tag(autoscaling_group=autoscaling_group,
        key='Name',
        value='%(project)s-%(environment)s' % env,
        propagate_at_launch=True)

    scale_up_policy = create_scaling_up_policy(
        autoscaling_group=autoscaling_group)
    scale_down_policy = create_scaling_down_policy(
        autoscaling_group=autoscaling_group)
    create_scaling_up_alarm(
        scale_up_policy=scale_up_policy,
        autoscaling_group=autoscaling_group)
    create_scaling_down_alarm(
        scale_down_policy=scale_down_policy,
        autoscaling_group=autoscaling_group)

    """
    Before returning the Autoscaling group, we poll AWS until we have some
    instances to work with as the rest of our provisioning script uses the
    instances attached to the Autoscaling group.
    """
    utils.status('Waiting on some instances...')
    while not autoscaling_group.instances:
        time.sleep(1)
        autoscaling_group = get(asg_type='QA')
    return autoscaling_group


def create_launch_configuration():
    utils.status("Create the launch config")
    launch_configuration = boto.ec2.autoscale.LaunchConfiguration(
        name='lc-%s-%s' % (env.project, time.time()),
        image_id=env.ami_image_id,
        key_name='%s-%s' % (env.project, env.environment),
        security_groups=['%s' % env.environment],
        user_data=utils.get_app_user_data(env=env),
        instance_type=env.instance_type,
        instance_profile_name='%s-ec2-%s' % (env.project, env.environment)
    )
    env.connections.autoscale.create_launch_configuration(launch_configuration)
    return launch_configuration


def create_scaling_up_policy(autoscaling_group):
    utils.status('Creating scaling up policy...')
    name = '%s-%s-scale-up' % (env.project, env.environment)
    scale_up_policy = boto.ec2.autoscale.ScalingPolicy(
        name=name,
        adjustment_type='ChangeInCapacity',
        as_name=autoscaling_group.name,
        scaling_adjustment=env.asg_adjustment_up,
        cooldown=env.asg_default_cooldown
    )
    env.connections.autoscale.create_scaling_policy(scale_up_policy)

    # We need to hit the API for the created policy to get it's new ARN
    scale_up_policy = env.connections.autoscale.get_all_policies(
        as_group=autoscaling_group.name,
        policy_names=[name])[0]
    utils.success('Finished creating scaling up policy.')
    return scale_up_policy


def create_scaling_down_policy(autoscaling_group):
    utils.status('Creating scaling down policy...')
    name = '%s-%s-scale-down' % (env.project, env.environment)
    scale_down_policy = boto.ec2.autoscale.ScalingPolicy(
        name=name,
        adjustment_type='ChangeInCapacity',
        as_name=autoscaling_group.name,
        scaling_adjustment=env.asg_adjustment_down,
        cooldown=env.asg_default_cooldown
    )
    env.connections.autoscale.create_scaling_policy(scale_down_policy)

    # We need to hit the API for the created policy to get it's new ARN
    scale_down_policy = env.connections.autoscale.get_all_policies(
        as_group=autoscaling_group.name,
        policy_names=[name])[0]
    utils.success('Finished creating scaling down policy.')
    return scale_down_policy


def create_scaling_up_alarm(scale_up_policy, autoscaling_group):
    utils.status('Creating scaling up alarm...')
    name = '%s-%s-scale-up-alarm' % (env.project, env.environment)
    scale_up_alarm = boto.ec2.cloudwatch.MetricAlarm(
        name=name,
        namespace=env.cw_namespace,
        metric=env.cw_metric,
        statistic=env.cw_statistic,
        comparison=env.cw_comparison_gt,
        threshold=env.cw_threshold_up,
        period=env.cw_period,
        evaluation_periods=env.cw_evaluation_periods,
        alarm_actions=[scale_up_policy.policy_arn],
        dimensions={'AutoScalingGroupName': autoscaling_group.name})
    env.connections.cloudwatch.create_alarm(scale_up_alarm)
    utils.success('Finished creating scaling up alarm.')


def create_scaling_down_alarm(scale_down_policy, autoscaling_group):
    utils.status('Creating scaling down alarm...')
    name = '%s-%s-scale-down-alarm' % (env.project, env.environment)
    scale_down_alarm = boto.ec2.cloudwatch.MetricAlarm(
        name=name,
        namespace=env.cw_namespace,
        metric=env.cw_metric,
        statistic=env.cw_statistic,
        comparison=env.cw_comparison_lt,
        threshold=env.cw_threshold_down,
        period=env.cw_period,
        evaluation_periods=env.cw_evaluation_periods,
        alarm_actions=[scale_down_policy.policy_arn],
        dimensions={'AutoScalingGroupName': autoscaling_group.name})
    env.connections.cloudwatch.create_alarm(scale_down_alarm)
    utils.success('Finished creating scaling down alarm.')


def tag(autoscaling_group, key, value, propagate_at_launch=False):
    utils.status('Tagging ASG with %s:%s' % (key, value))
    tag = boto.ec2.autoscale.tag.Tag(
        key=key,
        value=value,
        propagate_at_launch=propagate_at_launch,
        resource_id=autoscaling_group.name)
    env.connections.autoscale.create_or_update_tags([tag])


def get(asg_type):
    groups = get_all(asg_type=asg_type)
    if not groups:
        return None
    return groups[0]


def get_all(asg_type):
    return [
        env_group
        for env_group in get_env_groups()
        for tag in env_group.tags
        if tag.key == 'type' and tag.value == asg_type
    ]


def get_env_groups():
    return [
        env_group
        for env_group in env.connections.autoscale.get_all_groups()
        for tag in env_group.tags
        if tag.key == 'env' and tag.value == env.environment
    ]


def scale_down(autoscaling_group):
    env.connections.autoscale.create_scheduled_group_action(
        as_group=autoscaling_group.name,
        name='decrease-minimum-capacity',
        desired_capacity=1,
        min_size=1,
        start_time=datetime.datetime.now() + datetime.timedelta(seconds=30))


def delete_launch_config(autoscaling_group):
    utils.status('Deleting launch config')
    launch_config = env.connections.autoscale.get_all_launch_configurations(
        names=[autoscaling_group.launch_config_name])[0]
    launch_config.delete()
    utils.success('Launch config deleted')


def tag_inactive_as_old():
    inactive_autoscale_group = get(asg_type='Inactive')
    if not inactive_autoscale_group:
        return
    tag(inactive_autoscale_group, 'type', 'Old')


def tag_active_as_inactive():
    active_autoscale_group = get(asg_type='Active')
    if not active_autoscale_group:
        return
    tag(active_autoscale_group, 'type', 'Inactive')


def tag_inactive_as_active():
    inactive_autoscale_group = get(asg_type='Inactive')
    if not inactive_autoscale_group:
        return
    tag(inactive_autoscale_group, 'type', 'Active')


def tag_qa_as_active():
    qa_autoscale_group = get(asg_type='QA')
    tag(qa_autoscale_group, 'type', 'Active')


def delete_old():
    old_autoscale_group = get(asg_type='Old')
    if not old_autoscale_group:
        return
    old_launch_config_name = old_autoscale_group.launch_config_name
    old_autoscale_group.shutdown_instances()
    old_autoscale_group.delete(force_delete=True)
    utils.status("Deleting old launch configuration")
    env.connections.autoscale.delete_launch_configuration(
        old_launch_config_name)


def assign_elastic_ip_addresses(autoscaling_group):
    utils.status("Waiting on the new load balancer to get instances")
    while not autoscaling_group.instances:
        time.sleep(1)
        autoscaling_group = get(asg_type='QA')
    addresses = env.connections.ec2.get_all_addresses()

    free_addresses = filter(lambda x: x.instance_id is None, addresses)
    utils.success("Got the following addresses: %s" % addresses)

    for index, instance in enumerate(autoscaling_group.instances):
        utils.status("Waiting on instances to spin up...")
        instance_obj = ec2.get(instance_id=instance.instance_id)
        while instance_obj.state != 'running':
            time.sleep(1)
            instance_obj = ec2.get(instance_id=instance.instance_id)
            print('Instance status: %s' % instance_obj.state)
        address = free_addresses.pop(index)
        env.connections.ec2.associate_address(
            instance.instance_id, address.public_ip)
        utils.status(
            "Assigned %s to %s" % (address.public_ip, instance.instance_id))
