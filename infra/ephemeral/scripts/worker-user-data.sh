#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker awscli amazon-cloudwatch-agent
systemctl enable docker
systemctl start docker

aws ecr get-login-password --region ${aws_region} \
    | docker login --username AWS --password-stdin ${ecr_registry}

docker pull ${worker_image_url}

docker stop worker || true
docker rm worker || true

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

# Run the container

docker run -d \
    --name worker \
    --restart unless-stopped \
    -e ENVIRONMENT=production \
    -e AWS_REGION=${aws_region} \
    -e S3_BUCKET=${s3_bucket} \
    -e PGBOUNCER_HOST=${pgbouncer_host} \
    -e DB_CREDENTIALS_SECRET_NAME=${db_credentials_secret_name} \
    -e OPENAI_SECRET_NAME=${openai_secret_name} \
    -e BRIGHTDATA_SERP_SECRET_NAME=${brightdata_serp_secret_name} \
    -e BRIGHTDATA_FETCH_SECRET_NAME=${brightdata_fetch_secret_name} \
    -e MAX_CONCURRENT_JOBS=${max_concurrent_jobs} \
    -e START_ROW=${start_row} \
    -e END_ROW=${end_row} \
    ${worker_image_url}
