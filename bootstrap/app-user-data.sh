#!/bin/sh

set -e

echo "Europe/London" > /etc/timezone

dpkg-reconfigure -f noninteractive tzdata

export DOCKER_HOST="{{ docker_host }}"

export DOCKER_IMAGE="{{ app_docker_image }}"
export NGINX_DOCKER_IMAGE="{{ nginx_docker_image }}"
export CONSUMER_DOCKER_IMAGE="{{ goldmine_consumer_docker_image }}"

export ELASTICSEARCH_HOST="{{ elasticsearch_host }}"

export S3_PATH="{{ s3_path }}"
export REGION="{{ region }}"
export ENV="{{ env }}"
export MEMCACHED="{{ use_memcached }}"
export LOGSTASH="{{ use_logstash }}"
export RABBITMQ="{{ use_rabbitmq }}"

export DJANGO_SETTINGS_MODULE=conf.stage

echo "Installing AWS CLI"
apt-get update
apt-get install -y awscli

apt-get install -y nagios-nrpe-server

echo "Update docker"
wget -qO- https://get.docker.com/ | sh
service docker restart

echo "Make sure we have a proper directory structure first"
[ -d /var/log/app/emails ] || mkdir -p /var/log/app/emails
[ -d /var/log/app/uwsgi ] || mkdir -p /var/log/app/uwsgi
[ -d /var/log/supervisor ] || mkdir -p /var/log/supervisor
[ -d /var/log/nginx ] || mkdir -p /var/log/nginx
[ -d /var/log/logstash ] || mkdir -p /var/log/logstash
[ -d /var/log/rabbitmq ] || mkdir -p /var/log/rabbitmq

touch /var/log/app/errors.log
chown -R www-data:www-data /var/log/app

# We create our own RabbitMQ user here so we can have the same GID and UID 
# bits set on the logfiles as our docker container
groupadd -g 1100 rabbitmq
useradd -g 1100 -u 1100 rabbitmq
chown -R rabbitmq:rabbitmq /var/log/rabbitmq

# fetch docker config
echo "aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/dockercfg /home/ubuntu/.dockercfg"
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/dockercfg /home/ubuntu/.dockercfg
sudo cp /home/ubuntu/.dockercfg /root/.dockercfg

# fetch nagios config
echo "aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/nrpe_local.cfg /etc/nagios/nrpe_local.cfg"
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/nrpe.cfg /etc/nagios/nrpe.cfg
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/nrpe_local.cfg /etc/nagios/nrpe_local.cfg

# fetch logrotate config
echo "aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/logrotate.d/your-app /etc/logrotate.d/your-app"
aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/logrotate.d/your-app /etc/logrotate.d/your-app

echo "Restarting nagios nrpe server"
sudo /etc/init.d/nagios-nrpe-server restart

PLUGINS="check_connections check_cpu check_mem"

for PLUGIN in $PLUGINS; do
    aws s3 cp --region=$REGION s3://$S3_PATH/$ENV/bootstrap/$PLUGIN /usr/lib/nagios/plugins/$PLUGIN
    chmod +x /usr/lib/nagios/plugins/$PLUGIN
done

export BASE_URL={{ base_url }}

cat > /root/app.nginx.conf << EOF
upstream application {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name ptfs.$BASE_URL;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    location / {
        return 301 http://www.$BASE_URL\$request_uri?ptfs=true;
    }
}

server {
    listen 80;
    server_name $BASE_URL;
    access_log off;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    return 301 http://www.$BASE_URL\$request_uri;
}

server {
    listen 80;
    server_name qa1.$BASE_URL;
    access_log off;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    return 301 http://www.qa1.$BASE_URL\$request_uri;
}

server {
    listen 80;
    server_name qa2.$BASE_URL;
    access_log off;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    return 301 http://www.qa2.$BASE_URL\$request_uri;
}

server {
    listen 80;
    server_name qa3.$BASE_URL;
    access_log off;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    return 301 http://www.qa3.$BASE_URL\$request_uri;
}

server {
    listen 80;
    server_name localhost 127.0.0.1;
    access_log local_access_log.log;
    error_log local_error_log.log;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }


    location / {
        include uwsgi_params;
        uwsgi_pass application;
    }
}

server {
    listen 80;
    server_name www.$BASE_URL;

    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    location /loadstorm-196e60a677.html {
        return 200;
    }

    location /health {
        include uwsgi_params;
        uwsgi_pass application;
    }

    location / {
        {{ basic_auth }}
        include uwsgi_params;
        uwsgi_pass application;
    }
}

server {
    listen 80;
    server_name www.qa1.$BASE_URL www.qa2.$BASE_URL www.qa3.$BASE_URL;

    if (\$http_user_agent ~* (libwww-perl) ) {
        return 403;
    }

    location /health {
        include uwsgi_params;
        uwsgi_pass application;
    }

    location / {
        {{ basic_auth }}
        include uwsgi_params;
        uwsgi_pass application;
    }
}

server {
    listen 80 default_server;
    listen [::]:80 default_server ipv6only=on;

    location /health {
        include uwsgi_params;
        uwsgi_pass application;
    }
 
    if (\$http_user_agent ~* (libwww-perl) ) {
            return 403;
    }

    location / {
        {{ basic_auth }}
        try_files $uri $uri/ =404;
    }
}
EOF


# Pull main app docker image
echo "Pulling Docker image $DOCKER_IMAGE"
echo "su - root -c docker pull $DOCKER_HOST/$DOCKER_IMAGE"
su - root -c "docker pull $DOCKER_HOST/$DOCKER_IMAGE"

echo "docker run --rm -v /var/log:/var/log -e DJANGO_SETTINGS_MODULE=conf.$ENV $DOCKER_HOST/$DOCKER_IMAGE /www/manage.py collectstatic --noinput"
su - root -c "docker run --rm -v /var/log:/var/log -e DJANGO_SETTINGS_MODULE=conf.$ENV $DOCKER_HOST/$DOCKER_IMAGE /www/manage.py collectstatic --noinput"

if [ ! -z $LOGSTASH ]
then
    export LOGSTASH_DOCKER_IMAGE="{{ logstash_docker_image }}"

    # Pull logstash docker image
    echo "Pulling Docker image $DOCKER_HOST/$LOGSTASH_DOCKER_IMAGE"
    su - root -c "docker pull $DOCKER_HOST/$LOGSTASH_DOCKER_IMAGE"

    # Run logstash container
    su - root -c "docker run -d -P --name logstash -v /var/log:/var/log -e ES_HOST='$ELASTICSEARCH_HOST' $DOCKER_HOST/$LOGSTASH_DOCKER_IMAGE"
fi

# Pull nginx docker image
su - root -c "docker pull $DOCKER_HOST/$NGINX_DOCKER_IMAGE"

# Run nginx container
su - root -c "docker run -d -p 80:80 -v /var/log:/var/log -v /root/app.nginx.conf:/etc/nginx/sites-enabled/default  --net=host $DOCKER_HOST/$NGINX_DOCKER_IMAGE"

if [ ! -z $MEMCACHED ]
then
    export MEMCACHED_DOCKER_IMAGE="{{ memcached_docker_image }}"

    # Run memcached container
    echo "Running memcached container"
    su - root -c "docker run --name memcached -m 256m -d $DOCKER_HOST/$MEMCACHED_DOCKER_IMAGE"
fi 

if [ ! -z $RABBITMQ ]
then
    export RABBITMQ_DOCKER_IMAGE="{{ rabbitmq_docker_image }}"

    # Pull rabbitmq image
    echo "Pulling rabbitmq image"
    echo "su - root -c 'docker pull $DOCKER_HOST/$RABBITMQ_DOCKER_IMAGE'"
    su - root -c "docker pull $DOCKER_HOST/$RABBITMQ_DOCKER_IMAGE"

    # Run rabbitmq container
    echo "Running rabbitmq container"
    su - root -c "docker run -d -p 5672:5672 -p 4369:4369 -p 15672:15672 --name rabbitmq -v /var/log:/var/log $DOCKER_HOST/$RABBITMQ_DOCKER_IMAGE"
fi

# Run app container
su - root -c "docker run -d -v /var/log:/var/log --link rabbitmq:rabbitmq --link memcached:memcached -p 8000:8000 -e DJANGO_SETTINGS_MODULE='conf.$ENV' -e ENV=$ENV $DOCKER_HOST/$DOCKER_IMAGE"
