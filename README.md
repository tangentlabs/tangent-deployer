Tangent Deployer
================

Fabric script for deploying projects to AWS.

Installation and Usage
----------------------

Installing and using the tangent deployer is easy. Install the package:

    pip install tangent-deployer

And create your ``deploy/fabconfig.py`` and ``deploy/fabfile.py`` based on the 
templates below, and then deploy with:

    fab <environment> deploy


**fabfile.py**
```python
import sys
import time

import aws.s3
import aws.ec2
import aws.autoscale
import aws.elb
import aws.route53
import aws.utils

from fabric.api import task
from fabconfig import *  # noqa


@task
def deploy():
    aws.utils.status("Deploying to QA %s" % env.environment)
    if aws.autoscale.get(asg_type='QA'):
        utils.failure("There is already a QA autoscaling group, exiting")
        sys.exit(0)
    aws.s3.push_config_to_s3()
    aws.ec2.provision_logging_instance()

    load_balancer = aws.elb.get_or_create_load_balancer()
    autoscaling_group = aws.autoscale.create_autoscaling_group(
        load_balancer=load_balancer)
    if env.environment == 'live':
        aws.autoscale.assign_elastic_ip_addresses(
            autoscaling_group=autoscaling_group)
    aws.route53.link_qa_urls(autoscaling_group=autoscaling_group)
    aws.ec2.deploy_nagios_config(autoscaling_group=autoscaling_group)
    aws.utils.success("Successfully deployed to QA %s" % env.environment)


@task
def confirm():
    aws.utils.status("Confirm QA => %s deployment" % env.environment)
    active_autoscaling_group = aws.autoscale.get(asg_type='Active')
    qa_autoscaling_group = aws.autoscale.get(asg_type='QA')
    if not qa_autoscaling_group:
        utils.failure("There is no QA autoscaling group to confirm, exiting.")
        sys.exit(0)
    aws.autoscale.tag_qa_as_active()
    aws.autoscale.tag_active_as_inactive()
    load_balancer = aws.elb.get(load_balancer_name=env.load_balancer_name)
    aws.elb.register_instances(load_balancer=load_balancer,
                               autoscaling_group=qa_autoscaling_group)
    qa_autoscaling_group.resume_processes(
        scaling_processes=['AddToLoadBalancer'])
    aws.route53.link_base_urls(load_balancer=load_balancer)
    aws.route53.unlink_qa_urls(autoscaling_group=qa_autoscaling_group)

    aws.utils.status('Waiting 15 seconds before removing old instances')
    """
    We sleep here for 15 seconds before removing the currently live
    infrastructure from the load balancer to be on the safe side. Removing the
    live infrastructure before we've properly added the new infrastrucutre to
    the load balancer would result in bad times.
    """
    time.sleep(15)
    aws.ec2.remove_nagios_config(autoscaling_group=active_autoscaling_group)
    aws.elb.deregister_instances(load_balancer=load_balancer,
                                 autoscaling_group=active_autoscaling_group)

    aws.utils.status('Scaling down old live autoscaling group')
    aws.autoscale.scale_down(autoscaling_group=active_autoscaling_group)

    aws.utils.status('Shutting down old autoscaling group')
    aws.autoscale.tag_inactive_as_old()
    old_autoscaling_group = aws.autoscale.get(asg_type='Old')
    if old_autoscaling_group:
        old_autoscaling_group.shutdown_instances()
        old_autoscaling_group.delete(force_delete=True)
        aws.autoscale.delete_launch_config(
            autoscaling_group=old_autoscaling_group)
    aws.utils.success("Successfully confirmed the %s deploy" % env.environment)


@task
def abort():
    aws.utils.status("Aborting %s QA deploy" % env.environment)
    qa_autoscaling_group = aws.autoscale.get(asg_type='QA')
    if not qa_autoscaling_group:
        aws.utils.failure('No QA %s environment exists' % env.environment)
        sys.exit(1)
    aws.ec2.remove_nagios_config(autoscaling_group=qa_autoscaling_group)
    qa_autoscaling_group.shutdown_instances()
    qa_autoscaling_group.delete(force_delete=True)
    aws.autoscale.delete_launch_config(autoscaling_group=qa_autoscaling_group)
    aws.utils.success(
        "Successfully aborted the %s QA deploy" % env.environment)


@task
def logging():
    aws.s3.push_config_to_s3()
    aws.ec2.provision_logging_instance()
```


**fabconfig.py**
```python
from fabric.api import task, env
import utils

# CONSTANTS
"""
The region you want your machines provisioned and your config set on
"""
env.region = 'eu-west-1'

"""
The name of your project, this is used later on in a number of variable names
"""
env.project = ''

"""
The name of your docker applications docker image
"""
env.app_docker_image = '%s-app' % env.project

"""
The name of your logstash docker image
"""
env.logstash_docker_image = '%s-logstash' % env.project

"""
The name of your nginx docker image
"""
env.nginx_docker_image = '%s-nginx' % env.project

"""
The name of your elasticsearch docker image
"""
env.elasticsearch_docker_image = '%s-elasticsearch' % env.project

"""
The name of your kibana docker image
"""
env.kibana_docker_image = '%s-kibana' % env.project

"""
The name of the boto / awscli profile you have configured for this project.
See:

* http://boto.readthedocs.org/en/latest/boto_config_tut.html#credentials
* http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#cli-multiple-profiles

For more details on how to set up a profile
"""
env.profile_name = env.project

"""
The ID of your logging instance AMI. Having a base logging AMI will speed up
your deployment process.
"""
env.logging_ami_id = ''

"""
The availability zones you want your instances to be provisioned in.
"""
env.zones = ['eu-west-1a', 'eu-west-1b', 'eu-west-1c']

"""
S3 bucket to keep all bootstrap files, this bucket should not be public.
"""
env.s3_bootstrap_bucket = ''

"""
The location of your dockercfg file with your registry credentials.

This will be copied to ~/.dockercfg on your application machines.
"""
env.dockercfg = 'bootstrap/dockercfg'

"""
The location of your Kibana nginx config.

This will be mounted to /etc/nginx/sites/enabled inside your nginx container
"""
env.kibana_nginx_config = 'bootstrap/kibana.nginx'

"""
The URL you will use to hit your Kibana box
"""
env.logging_urls = ['']

env.memcached_docker_image = ''

"""
The size of the EBS volume your Kibana instance will have (in GB)
"""
env.logging_ebs_volume_size = 100
env.logging_ebs_volume_type = 'gp2'

"""
The URL logstash will hit on your application boxes to post their logs to
ElasticSearch.
"""
env.elasticsearch_host = ''

"""
The location of your logrotate config
"""
env.logrotate_config = 'bootstrap/logrotate.d/your-app.conf'

"""
Time to live for zone records - note some DNS relays don't honour the TTL
so it's best to not rely on it for anything important.
"""
env.ttl_in_seconds = 60


# Nagios config
env.user = ''
env.password = ''
env.hosts = ['']  # This is the nagios master host
env.nagios_master_config_file = 'bootstrap/nagios/nagios.cfg'
env.nagios_group_name = ''

env.nagios_host_local_nrpe_config = 'bootstrap/nagios/nrpe_local.cfg'
env.nagios_host_nrpe_config = 'bootstrap/nagios/nrpe.cfg'
env.nagios_plugins = {
    'check_connections': 'bootstrap/nagios/check_connections',
    'check_cpu': 'bootstrap/nagios/check_cpu',
    'check_mem': 'bootstrap/nagios/check_mem'
}
env.nagios_plugin_location = '/usr/lib/nagios/plugins'

# Cloudwatch alarm settings
env.cw_namespace = 'AWS/EC2'
env.cw_metric = 'CPUUtilization'
env.cw_statistic = 'Average'
env.cw_comparison_gt = '>'
env.cw_comparison_lt = '<'
env.cw_threshold_up = '50'
env.cw_threshold_down = '20'
env.cw_period = '60'
env.cw_evaluation_periods = 1

# Boto connections
services = [
    'boto.ec2',
    'boto.ec2.elb',
    'boto.ec2.autoscale',
    'boto.ec2.cloudwatch',
    'boto.route53',
    'boto.s3']
env.connections = utils.BotoConnection(
    profile_name=env.profile_name, services=services)


@task
def stage():
    utils.status("Setting up STAGE")
    env.zone = 'your-domain.co.uk.'  # Base R53 zone, the dot is significant
    env.qa_url = 'www.qa%s.your-domain.co.uk.'
    env.urls = ['www.your-domain.co.uk']
    env.base_url = 'your-domain.co.uk'
    env.environment = 'stage'
    env.load_balancer_name = '%s-%s' % (env.project, env.environment)
    env.instance_type = 't2.medium'
    env.docker_host = 'docker-images-dev.tangentlabs.co.uk'
    env.security_groups = ['stage']
    env.basic_auth = ("auth_basic 'Restricted'; "
                      "auth_basic_user_file /etc/nginx/users;")
    env.asg_desired_capacity = 1
    env.asg_adjustment_up = 1
    env.asg_adjustment_down = -1
    env.nagios_master_config_dir = '/etc/nagios3/aws.%s' % env.project
    env.r53_ttl = 60

    """
    The ID of your application base AMI. Having a base application AMI will speed
    up your deployment process.
    """
    env.ami_image_id = ''

    """
    The URL you will use to hit your Kibana box
    """
    env.logging_urls = ['logs.%s-%s.co.uk' % (env.project, env.environment)]

    """
    Amount of time in seconds to wait before attempting another scaling
    activity

    env.asg_default_cooldown = 180
    """
    env.asg_default_cooldown = 180

    """
    The minimum size of your autoscaling group.
    """
    env.asg_min_size = 1

    """
    The maximum size that your autoscaling group can grow to.
    """
    env.asg_max_size = 1


@task
def live():
    utils.status("Setting up LIVE")
    env.zone = 'your-domain.co.uk.'  # Base R53 zone, the dot is significant
    env.qa_url = 'www.qa%s.your-domain.co.uk.'
    env.urls = ['www.your-domain.co.uk', 'ptfs.national-accident-helpline.co.uk']
    env.base_url = 'your-domain.co.uk'
    env.environment = 'live'
    env.load_balancer_name = '%s-%s' % (env.project, env.environment)
    env.instance_type = 't2.medium'
    env.docker_host = 'docker.tangentlabs.co.uk'
    env.security_groups = ['live']
    env.basic_auth = ''
    env.asg_desired_capacity = 2
    env.asg_adjustment_up = 2
    env.asg_adjustment_down = -1
    env.nagios_master_config_dir = '/etc/nagios3/aws.%s' % env.project
    env.r53_ttl = 60

    """
    The URL you will use to hit your Kibana box
    """
    env.logging_urls = ['logs.%s' % env.base_url]

    """
    Amount of time in seconds to wait before attempting another scaling
    activity

    env.asg_default_cooldown = 180
    """
    env.asg_default_cooldown = 180

    """
    The minimum size of your autoscaling group.
    """
    env.asg_min_size = 2

    """
    The maximum size that your autoscaling group can grow to.
    """
    env.asg_max_size = 2
    env.ami_image_id = ''
```
