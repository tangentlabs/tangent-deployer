import time
import utils
from . import ec2

from fabconfig import env


def link_qa_urls(autoscaling_group):
    utils.status("Linking the QA URLs to the new instances")
    route53_zone = env.connections.route53.get_zone(env.zone)

    for index, instance in enumerate(autoscaling_group.instances):
        utils.status('Waiting on a public DNS name for instances')
        instance_obj = ec2.get(instance_id=instance.instance_id)
        while not instance_obj.dns_name:
            time.sleep(1)
            instance_obj = ec2.get(instance_id=instance.instance_id)
        [
            route53_zone.update_cname(
                name=qa_url % str(index + 1),
                value=instance_obj.dns_name,
                ttl=env.ttl_in_seconds
            )
            for qa_url
            in env.qa_urls
        ]
    utils.success('Finished linking the instances to the QA URLs')


def link_base_urls(load_balancer):
    utils.status('Link base URLs')
    route53_zone = env.connections.route53.get_zone(env.zone)

    # We have to operate on rrsets because the main url can't be
    # changed with CNAME
    rrsets = env.connections.route53.get_all_rrsets(
        hosted_zone_id=route53_zone.id,
        name=env.zone,
        type='A'
    )
    rrsets.add_change(
        'UPSERT',
        env.base_url,
        type='A',
        alias_dns_name=load_balancer.dns_name,
        alias_hosted_zone_id=load_balancer.canonical_hosted_zone_name_id,
        alias_evaluate_target_health=False
    )
    rrsets.commit()
    for url in env.urls:
        route53_zone.update_cname(
            name=url,
            value=load_balancer.dns_name,
            ttl=env.ttl_in_seconds
        )


def unlink_qa_urls(autoscaling_group):
    utils.status('Un-linking QA URLs')
    route53_zone = env.connections.route53.get_zone(env.zone)
    for index, instance in enumerate(autoscaling_group.instances):
        route53_zone.update_cname(
            name=env.qa_url % str(index + 1),
            value='NOQA.',
            ttl=env.ttl_in_seconds
        )
    utils.success('Finished un-linking URLs')
