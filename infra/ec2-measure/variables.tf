variable "region" {
  type    = string
  default = "us-east-1"
}

variable "run_id" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "use_spot" {
  type    = bool
  default = true
}

variable "key_name" {
  type = string
}

variable "runner_cidr" {
  type = string
}

variable "subnet_id" {
  type = string
}
