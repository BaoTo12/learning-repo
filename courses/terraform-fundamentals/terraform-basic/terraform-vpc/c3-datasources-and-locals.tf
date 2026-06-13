# data block
data "aws_availability_zones" "available" {
  state = "available"
}



# local block
locals {
  public_offset = 0
  private_offset = 10

  azs = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnet = [for k, az in local.azs : cidrsubnet(var.vpc_cidr, var.subnet_newbits, k + local.public_offset)]
  private_subnet = [for k, az in local.azs: cidrsubnet(var.vpc_cidr, var.subnet_newbits, k + local.private_offset)]
}