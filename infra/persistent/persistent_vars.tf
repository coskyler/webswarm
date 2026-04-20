variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "app_name" {
  type = string
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance class for the Postgres database"
  type        = string
}

variable "db_allocated_storage" {
  description = "Allocated storage for the RDS database in GB"
  type        = number
}

variable "db_master_username" {
  description = "Master username for the RDS database"
  type        = string
}
