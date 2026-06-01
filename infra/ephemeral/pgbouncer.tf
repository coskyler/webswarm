# USER DATA SCRIPT

locals {
  pgbouncer-cloudwatch_config = templatefile("${path.module}/scripts/cloudwatch-agent.json", {
    log_group_name = "pgbouncer"
  })

  pgbouncer_user_data = base64encode(templatefile("${path.module}/scripts/pgbouncer-user-data.sh", {
    aws_region                 = var.aws_region
    ecr_registry               = var.ecr_registry
    pgbouncer_image_url        = var.pgbouncer_image_url
    db_host                    = data.terraform_remote_state.persistent.outputs.db_host
    db_credentials_secret_name = var.db_credentials_secret_name
    cloudwatch_config          = local.pgbouncer-cloudwatch_config
  }))
}

# LAUNCH TEMPLATE

resource "aws_launch_template" "pgbouncer" {
  name_prefix   = "pgbouncer-"
  image_id      = data.aws_ami.amazon_linux.id
  instance_type = var.pgbouncer_instance_type

  vpc_security_group_ids = [data.terraform_remote_state.persistent.outputs.pgbouncer_security_group_id]

  iam_instance_profile {
    name = aws_iam_instance_profile.compute.name
  }

  user_data = local.pgbouncer_user_data

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "pgbouncer"
    }
  }

  tags = {
    Name = "pgbouncer-template"
  }
}

# AUTOSCALING GROUP

resource "aws_autoscaling_group" "pgbouncer" {
  name                = "pgbouncer-asg"
  min_size            = var.pgbouncer_min_size
  max_size            = var.pgbouncer_max_size
  desired_capacity    = var.pgbouncer_desired_capacity
  vpc_zone_identifier = data.terraform_remote_state.persistent.outputs.subnet_ids
  health_check_type   = "ELB"

  target_group_arns = [aws_lb_target_group.pgbouncer.arn]

  launch_template {
    id      = aws_launch_template.pgbouncer.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "pgbouncer"
    propagate_at_launch = true
  }
}

resource "aws_lb" "pgbouncer" {
  name               = "pgbouncer-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = data.terraform_remote_state.persistent.outputs.subnet_ids
  security_groups    = [data.terraform_remote_state.persistent.outputs.nlb_security_group_id]

  tags = {
    Name = "pgbouncer-nlb"
  }
}

# LB TARGET GROUP

resource "aws_lb_target_group" "pgbouncer" {
  name        = "pgbouncer-tg"
  port        = 6432
  protocol    = "TCP"
  target_type = "instance"
  vpc_id      = data.terraform_remote_state.persistent.outputs.vpc_id

  health_check {
    protocol = "TCP"
    port     = "6432"
  }

  tags = {
    Name = "pgbouncer-tg"
  }
}

# LB LISTENER

resource "aws_lb_listener" "pgbouncer" {
  load_balancer_arn = aws_lb.pgbouncer.arn
  port              = 6432
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.pgbouncer.arn
  }
}
