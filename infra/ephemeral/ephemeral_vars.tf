variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "ecr_registry" {
  description = "ECR registry URL, e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com"
  type        = string
}

variable "worker_image_url" {
  description = "Full ECR image URL, including tag"
  type        = string
}

variable "pgbouncer_image_url" {
  description = "ECR image URL for the PgBouncer container"
  type        = string
}

variable "worker_instance_types" {
  description = "EC2 instance types for worker spot instances, in fallback order"
  type        = list(string)
}

variable "worker_min_size" {
  description = "Minimum number of worker instances in the ASG"
  type        = number
}

variable "worker_max_size" {
  description = "Maximum number of worker instances in the ASG"
  type        = number
}

variable "worker_desired_capacity" {
  description = "Desired number of worker instances in the ASG"
  type        = number
}

variable "pgbouncer_instance_type" {
  description = "EC2 instance type for PgBouncer instances"
  type        = string
}

variable "pgbouncer_min_size" {
  description = "Minimum number of PgBouncer instances in the ASG"
  type        = number
}

variable "pgbouncer_max_size" {
  description = "Maximum number of PgBouncer instances in the ASG"
  type        = number
}

variable "pgbouncer_desired_capacity" {
  description = "Desired number of PgBouncer instances in the ASG"
  type        = number
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_credentials_secret_name" {
  description = "Secrets Manager secret name for database credentials"
  type        = string
}

variable "openai_secret_name" {
  description = "Secrets Manager secret containing the OpenAI API key"
  type        = string
}

variable "brightdata_serp_secret_name" {
  description = "Secrets Manager secret containing BrightData SERP API key"
  type        = string
}

variable "brightdata_fetch_secret_name" {
  description = "Secrets Manager secret containing BrightData FETCH API key"
  type        = string
}

variable "max_concurrent_jobs" {
  description = "Maximum number of concurrent jobs for one worker"
  type        = number
}

variable "page_pool_size" {
  description = "Worker page pool size"
  type        = number
}

variable "start_row" {
  description = "Starting postgres row for worker jobs (should generally be 0)"
  type        = number
}

variable "end_row" {
  description = "Ending postgres row for worker jobs (should be >= start_row)"
  type        = number
}
