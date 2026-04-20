# USER DATA SCRIPT

locals {
  worker_user_data = base64encode(<<-EOF
    #!/bin/bash
    set -euxo pipefail

    dnf update -y
    dnf install -y docker awscli
    systemctl enable docker
    systemctl start docker

    aws ecr get-login-password --region ${var.aws_region} \
      | docker login --username AWS --password-stdin ${var.ecr_registry}

    docker pull ${var.worker_image_url}

    docker stop worker || true
    docker rm worker || true

    docker run -d \
      --name worker \
      --restart unless-stopped \
      -e AWS_REGION=${var.aws_region} \
      -e PGBOUNCER_HOST=${aws_lb.pgbouncer.dns_name} \
      -e DB_CREDENTIALS=${var.db_credentials_secret_name} \
      -e OPENAI_SECRET_NAME=${var.openai_secret_name} \
      -e BRIGHTDATA_SERP_SECRET_NAME=${var.brightdata_serp_secret_name} \
      -e BRIGHTDATA_FETCH_SECRET_NAME=${var.brightdata_fetch_secret_name} \
      ${var.worker_image_url}
  EOF
  )
}

# LAUNCH TEMPLATE

resource "aws_launch_template" "workers" {
  name_prefix   = "worker-"
  image_id      = data.aws_ami.amazon_linux.id
  instance_type = var.worker_instance_type

  vpc_security_group_ids = [data.terraform_remote_state.persistent.outputs.workers_security_group_id]

  iam_instance_profile {
    name = aws_iam_instance_profile.compute.name
  }

  user_data = local.worker_user_data

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "worker"
    }
  }

  tags = {
    Name = "worker-template"
  }
}

# AUTOSCALING GROUP

resource "aws_autoscaling_group" "workers" {
  name                = "worker-asg"
  min_size            = var.worker_min_size
  max_size            = var.worker_max_size
  desired_capacity    = var.worker_desired_capacity
  vpc_zone_identifier = data.terraform_remote_state.persistent.outputs.subnet_ids
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.workers.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "worker"
    propagate_at_launch = false
  }
}
