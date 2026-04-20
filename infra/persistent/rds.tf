# DB SUBNET GROUP

resource "aws_db_subnet_group" "postgres" {
  name       = "postgres-subnets"
  subnet_ids = local.subnet_ids

  tags = {
    Name = "postgres-subnets"
  }
}

# RDS INSTANCE

resource "aws_db_instance" "postgres" {
  identifier        = "postgres-db"
  engine            = "postgres"
  engine_version    = "18"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"

  db_name                     = var.db_name
  username                    = var.db_master_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]

  multi_az            = true
  publicly_accessible = true # easier local access for manual DB operations; low-sensitivity data
  skip_final_snapshot = false
  deletion_protection = false

  tags = {
    Name = "postgres-db"
  }
}
