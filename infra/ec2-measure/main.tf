data "aws_vpc" "default" {
  default = true
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  tags = {
    Name  = "tsdhn-ec2-measure-${var.run_id}"
    RunId = var.run_id
  }

  cloud_init = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    compose_b64 = base64encode(file("${path.root}/../../deploy/compose.prod.yml"))
  })
}

resource "aws_security_group" "measure" {
  name        = "tsdhn-ec2-measure-${var.run_id}"
  description = "SSH for the tsdhn EC2 measurement runner"
  vpc_id      = data.aws_vpc.default.id

  tags = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.measure.id
  cidr_ipv4         = var.runner_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "Measurement runner only"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.measure.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Bootstrap and pull public dependencies"
}

resource "aws_instance" "measure" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.measure.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data                   = local.cloud_init
  user_data_replace_on_change = true

  dynamic "instance_market_options" {
    for_each = var.use_spot ? [true] : []
    content {
      market_type = "spot"
      spot_options {
        instance_interruption_behavior = "terminate"
        spot_instance_type             = "one-time"
      }
    }
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 50
    delete_on_termination = true
  }

  volume_tags = local.tags
  tags        = local.tags
}
