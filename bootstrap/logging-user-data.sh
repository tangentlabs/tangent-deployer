#!/usr/bin/env bash

set -e

export S3_PATH="{{ s3_path }}"
export DOCKER_HOST="{{ docker_host }}"
export KIBANA_DOCKER_IMAGE="{{ kibana_docker_image }}"
export ELASTICSEARCH_DOCKER_IMAGE="{{ elasticsearch_docker_image }}"
export NGINX_DOCKER_IMAGE="{{ nginx_docker_image }}"
export REGION="{{ region }}"
export ENV="{{ env }}"

echo "Installing AWS CLI"
apt-get update
apt-get install -y awscli

echo "aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/dockercfg /ubuntu/home/.dockercfg"
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/dockercfg /ubuntu/home/.dockercfg
sudo cp /ubuntu/home/.dockercfg /root/.dockercfg

# Pull docker image for kibana
su - root -c "docker pull $DOCKER_HOST/$KIBANA_DOCKER_IMAGE"

# Pull docker image for elasticsearch
su - root -c "docker pull $DOCKER_HOST/$ELASTICSEARCH_DOCKER_IMAGE"

# Pull nginx docker image
su - root -c "docker pull $DOCKER_HOST/$NGINX_DOCKER_IMAGE"

# Run elasticsearch container
export ES_CONTAINER=$(su - root -c "docker run --name elasticsearch -d -p 9200:9200 -p 9300:9300 $DOCKER_HOST/$ELASTICSEARCH_DOCKER_IMAGE")

# Run docker image for kibana
su - root -c "docker run -d -p 5601:5601 --link elasticsearch:es $DOCKER_HOST/$KIBANA_DOCKER_IMAGE"

echo "aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/kibana.nginx /tmp/default"
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/kibana.nginx /tmp/default

# Run nginx container
su - root -c "docker run -d -p 80:80 -v /var/log:/var/log -v /tmp/default:/etc/nginx/sites-enabled/default --net=host $DOCKER_HOST/$NGINX_DOCKER_IMAGE"

echo "Bootstrapping complete"
