from fabric.api import task, env
from tangent_deployer import utils

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
env.nagios_client_allowed_hosts = ['']
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
    env.docker_host = ''
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
    env.urls = ['www.your-domain.co.uk']
    env.base_url = 'your-domain.co.uk'
    env.environment = 'live'
    env.load_balancer_name = '%s-%s' % (env.project, env.environment)
    env.instance_type = 't2.medium'
    env.docker_host = ''
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
