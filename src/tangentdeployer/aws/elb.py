import json
import utils
import boto.ec2.elb

from fabconfig import env
from fabric.api import local


def get_or_create_load_balancer():
    utils.status("Getting %s load balancer" % env.environment)
    load_balancer = get(load_balancer_name=env.load_balancer_name)
    if not load_balancer:
        return create_load_balancer()
    return load_balancer


def create_load_balancer():
    load_balancer = env.connections.elb.create_load_balancer(
        name=env.load_balancer_name,
        zones=env.zones,
        security_groups=utils.security_groups(),
        complex_listeners=[('80', '80', 'http', 'http')]
    )
    utils.success('Finished creating load balancer')

    health_check = create_health_check()
    load_balancer.configure_health_check(health_check=health_check)
    return load_balancer


def create_health_check():
    utils.status('Creating health check for load balancer')
    health_check = boto.ec2.elb.HealthCheck(
        interval=10,
        healthy_threshold=2,
        unhealthy_threshold=3,
        target='HTTP:80/health')
    utils.success('Finished creating health check for load balancer')
    return health_check


def register_instances(load_balancer, autoscaling_group):
    instances = [
        instance.instance_id
        for instance in autoscaling_group.instances
    ]
    env.connections.elb.register_instances(
        load_balancer_name=load_balancer.name, instances=instances)


def deregister_instances(load_balancer, autoscaling_group):
    instances = [
        instance.instance_id
        for instance in autoscaling_group.instances
    ]
    env.connections.elb.deregister_instances(
        load_balancer_name=load_balancer.name, instances=instances)


def get(load_balancer_name):
    utils.status('Getting %s load balancer' % env.environment)
    try:
        load_balancers = env.connections.elb.get_all_load_balancers(
            load_balancer_names=[env.load_balancer_name])
    except boto.exception.BotoServerError:
        return None
    return load_balancers[0]


def has_tag(load_balancer_name, key, value):
    """
    We fall back to using the AWS CLI tool here because boto doesn't
    support adding tags to load balancers yet.

    As soon as https://github.com/boto/boto/issues/2549 is merged we're good
    to change this to use boto.
    """
    response = json.loads(local(
        'aws elb describe-tags '
        '--load-balancer-names %s '
        '--region=%s --profile=%s' % (load_balancer_name,
                                      env.region,
                                      env.profile_name),
        capture=True))
    in_env = False
    if 'TagDescriptions' in response:
        for tag_description in response['TagDescriptions']:
            for tag in tag_description['Tags']:
                if tag['Key'] == 'env' and tag['Value'] == env.environment:
                    in_env = True
            for tag in tag_description['Tags']:
                if tag['Key'] == 'type' and tag['Value'] == value and in_env:
                    return True
    return False


def tag(load_balancer, tags):
    """
    We fall back to using the AWS CLI tool here because boto doesn't
    support adding tags to load balancers yet.

    As soon as https://github.com/boto/boto/issues/2549 is merged we're good
    to change this to use boto
    """
    utils.status('Tagging load balancer')
    tags = make_tags(tags=tags)
    local('aws elb add-tags '
          '--load-balancer-names {lb_name} '
          '--tags {tags} '
          '--region={region} '
          '--profile={profile_name}'.format(lb_name=load_balancer.name,
                                            tags=tags,
                                            region=env.region,
                                            profile_name=env.profile_name)
          )

    utils.success('Finished tagging load balancer')


def make_tags(tags):
    return ' '.join(
        'Key={key},Value={value}'.format(key=key, value=value)
        for key, value in tags.iteritems()
    )
