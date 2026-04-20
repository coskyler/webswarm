output "vpc_id" {
  value = aws_vpc.main.id
}

output "subnet_ids" {
  value = local.subnet_ids
}

# SECURITY GROUPS

output "workers_security_group_id" {
  value = aws_security_group.workers.id
}

output "nlb_security_group_id" {
  value = aws_security_group.nlb.id
}

output "pgbouncer_security_group_id" {
  value = aws_security_group.pgbouncer.id
}

# HOSTNAMES

output "db_host" {
  value = aws_db_instance.postgres.address
}