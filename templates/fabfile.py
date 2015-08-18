import sys
import time

from tangentdeployer.aws import s3
from tangentdeployer.aws import ec2
from tangentdeployer.aws import elb
from tangentdeployer.aws import route53
from tangentdeployer.aws import autoscale
from tangentdeployer.aws import utils

from fabric.api import task
from fabconfig import *  # noqa


@task
def deploy():
    utils.status("Deploying to QA %s" % env.environment)
    if autoscale.get(asg_type='QA'):
        utils.failure("There is already a QA autoscaling group, exiting")
        sys.exit(0)
    s3.push_config_to_s3()
    ec2.provision_logging_instance()

    load_balancer = elb.get_or_create_load_balancer()
    autoscaling_group = autoscale.create_autoscaling_group(
        load_balancer=load_balancer)
    if env.environment == 'live':
        autoscale.assign_elastic_ip_addresses(
            autoscaling_group=autoscaling_group)
    route53.link_qa_urls(autoscaling_group=autoscaling_group)
    ec2.deploy_nagios_config(autoscaling_group=autoscaling_group)
    utils.success("Successfully deployed to QA %s" % env.environment)


@task
def confirm():
    utils.status("Confirm QA => %s deployment" % env.environment)
    active_autoscaling_group = autoscale.get(asg_type='Active')
    qa_autoscaling_group = autoscale.get(asg_type='QA')
    if not qa_autoscaling_group:
        utils.failure("There is no QA autoscaling group to confirm, exiting.")
        sys.exit(0)
    autoscale.tag_qa_as_active()
    autoscale.tag_active_as_inactive()
    load_balancer = elb.get(load_balancer_name=env.load_balancer_name)
    elb.register_instances(load_balancer=load_balancer,
                           autoscaling_group=qa_autoscaling_group)
    qa_autoscaling_group.resume_processes(
        scaling_processes=['AddToLoadBalancer'])
    route53.link_base_urls(load_balancer=load_balancer)
    route53.unlink_qa_urls(autoscaling_group=qa_autoscaling_group)

    utils.status('Waiting 15 seconds before removing old instances')
    """
    We sleep here for 15 seconds before removing the currently live
    infrastructure from the load balancer to be on the safe side. Removing the
    live infrastructure before we've properly added the new infrastrucutre to
    the load balancer would result in bad times.
    """
    time.sleep(15)
    ec2.remove_nagios_config(autoscaling_group=active_autoscaling_group)
    elb.deregister_instances(load_balancer=load_balancer,
                             autoscaling_group=active_autoscaling_group)

    utils.status('Scaling down old live autoscaling group')
    autoscale.scale_down(autoscaling_group=active_autoscaling_group)

    utils.status('Shutting down old autoscaling group')
    autoscale.tag_inactive_as_old()
    old_autoscaling_group = autoscale.get(asg_type='Old')
    if old_autoscaling_group:
        old_autoscaling_group.shutdown_instances()
        old_autoscaling_group.delete(force_delete=True)
        autoscale.delete_launch_config(
            autoscaling_group=old_autoscaling_group)
    utils.success("Successfully confirmed the %s deploy" % env.environment)


@task
def abort():
    utils.status("Aborting %s QA deploy" % env.environment)
    qa_autoscaling_group = autoscale.get(asg_type='QA')
    if not qa_autoscaling_group:
        utils.failure('No QA %s environment exists' % env.environment)
        sys.exit(1)
    ec2.remove_nagios_config(autoscaling_group=qa_autoscaling_group)
    qa_autoscaling_group.shutdown_instances()
    qa_autoscaling_group.delete(force_delete=True)
    autoscale.delete_launch_config(autoscaling_group=qa_autoscaling_group)
    utils.success(
        "Successfully aborted the %s QA deploy" % env.environment)


@task
def logging():
    s3.push_config_to_s3()
    ec2.provision_logging_instance()
