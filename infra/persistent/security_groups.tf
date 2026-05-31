resource "aws_security_group" "workers" {
  name        = "worker-sg"
  description = "Security group for worker instances"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "worker-sg"
  }
}

resource "aws_security_group" "nlb" {
  name        = "pgbouncer-nlb-sg"
  description = "Security group for PgBouncer NLB"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "pgbouncer" {
  name        = "pgbouncer-sg"
  description = "Security group for pgbouncer instances"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "pgbouncer-sg"
  }
}

resource "aws_security_group" "postgres" {
  name        = "postgres-sg"
  description = "Security group for RDS Postgres"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "postgres-sg"
  }
}

resource "aws_vpc_security_group_egress_rule" "workers_all_ipv4" {
  security_group_id = aws_security_group.workers.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "workers_all_ipv6" {
  security_group_id = aws_security_group.workers.id
  ip_protocol       = "-1"
  cidr_ipv6         = "::/0"
}

resource "aws_vpc_security_group_ingress_rule" "nlb_from_workers" {
  security_group_id            = aws_security_group.nlb.id
  referenced_security_group_id = aws_security_group.workers.id
  from_port                    = 6432
  to_port                      = 6432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "nlb_to_pgbouncer" {
  security_group_id            = aws_security_group.nlb.id
  referenced_security_group_id = aws_security_group.pgbouncer.id
  from_port                    = 6432
  to_port                      = 6432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "pgbouncer_from_nlb" {
  security_group_id            = aws_security_group.pgbouncer.id
  referenced_security_group_id = aws_security_group.nlb.id
  from_port                    = 6432
  to_port                      = 6432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "pgbouncer_all_ipv4" {
  security_group_id = aws_security_group.pgbouncer.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_pgbouncer" {
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = aws_security_group.pgbouncer.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

# to allow local access
resource "aws_vpc_security_group_ingress_rule" "postgres_from_anywhere" {
  security_group_id = aws_security_group.postgres.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "postgres_all_ipv4" {
  security_group_id = aws_security_group.postgres.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}