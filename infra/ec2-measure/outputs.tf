output "instance_id" {
  value = aws_instance.measure.id
}

output "public_ip" {
  value = aws_instance.measure.public_ip
}

output "instance_type" {
  value = var.instance_type
}

output "security_group_id" {
  value = aws_security_group.measure.id
}
