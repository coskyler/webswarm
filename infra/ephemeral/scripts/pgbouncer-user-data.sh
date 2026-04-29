#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker awscli amazon-cloudwatch-agent
systemctl enable docker
systemctl start docker

aws ecr get-login-password --region ${aws_region} \
    | docker login --username AWS --password-stdin ${ecr_registry}

docker pull ${pgbouncer_image_url}

docker stop pgbouncer || true
docker rm pgbouncer || true

# Create the cloudwatch agent

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<EOF
${cloudwatch_config}
EOF

# Run the cloudwatch agent

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
    -s

docker run -d \
    --name pgbouncer \
    --restart unless-stopped \
    -p 6432:6432 \
    -e ENVIRONMENT=production \
    -e AWS_REGION=${aws_region} \
    -e DB_HOST=${db_host} \
    -e DB_CREDENTIALS_SECRET_NAME=${db_credentials_secret_name} \
    ${pgbouncer_image_url}