# USER DATA SCRIPT

locals {
  worker-cloudwatch_config = templatefile("${path.module}/scripts/cloudwatch-agent.json", {
    log_group_name = "workers"
  })

  worker_user_data = base64encode(templatefile("${path.module}/scripts/worker-user-data.sh", {
    aws_region                   = var.aws_region
    ecr_registry                 = var.ecr_registry
    worker_image_url             = var.worker_image_url
    s3_bucket                    = data.terraform_remote_state.persistent.outputs.html_cache_bucket_name
    pgbouncer_host               = aws_lb.pgbouncer.dns_name
    db_credentials_secret_name   = var.db_credentials_secret_name
    openai_secret_name           = var.openai_secret_name
    brightdata_serp_secret_name  = var.brightdata_serp_secret_name
    brightdata_fetch_secret_name = var.brightdata_fetch_secret_name
    cloudwatch_config            = local.worker-cloudwatch_config
  }))
}

# LAUNCH TEMPLATE

resource "aws_launch_template" "workers" {
  name_prefix   = "worker-"
  image_id      = data.aws_ssm_parameter.amazon_linux.value
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

  # Increase hop limit to 2, so containers can access IMDS over Docker network bridge
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
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
