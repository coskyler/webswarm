provider "aws" {
  region = var.aws_region
}

# IAM ROLES TO ENABLE EC2S TO ACCESS ECR AND SECRETS

resource "aws_iam_role" "compute" {
  name = "compute-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# Allow pulling images from ECR
resource "aws_iam_role_policy_attachment" "compute_ecr" {
  role       = aws_iam_role.compute.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# Allow reading secrets
resource "aws_iam_role_policy_attachment" "compute_secrets" {
  role       = aws_iam_role.compute.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadOnly"
}

# Allow CloudWatch Agent to publish logs and metrics
resource "aws_iam_role_policy_attachment" "compute_cloudwatch" {
  role       = aws_iam_role.compute.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Allow get and put to s3 bucket
resource "aws_iam_role_policy" "compute_html_cache" {
  name = "compute-html-cache"
  role = aws_iam_role.compute.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject"
      ]
      Resource = "arn:aws:s3:::${data.terraform_remote_state.persistent.outputs.html_cache_bucket_name}/*"
    }]
  })
}

# Instance profile

resource "aws_iam_instance_profile" "compute" {
  name = "compute-instance-profile"
  role = aws_iam_role.compute.name
}

# AMI DATA SOURCE

data "aws_ami" "amazon_linux" {
  most_recent = true

  owners = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}
