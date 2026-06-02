# * Resource-1: VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "${var.environment_name}-vpc" })
  lifecycle {
    prevent_destroy = true
  }
}

# * Resource-2: Internet Gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "${var.environment_name}-igw" })
}

# * Resource-3: Public Subnets
resource "aws_subnet" "public" {
  for_each          = { for idx, az in local.azs : az => local.public_subnet[idx] }
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value
  availability_zone = each.key
  tags              = merge(var.tags, { Name = "${var.environment_name}-private-${each.key}" })
}
# ! when we use for_each terraform uses the key to name our resource 
# aws_subnet.public["us-east-1a"]
# aws_subnet.public["us-east-1b"]
# aws_subnet.public["us-east-1c"]

# Sample map
# {
#     us-east-1a = 10.0.0.0/24
#     us-east-1b = 10.0.1.0/24
#     us-east-1c = 10.0.2.0/24
# }

# * Resource-4: Private Subnets
resource "aws_subnet" "private" {
  for_each          = { for idx, az in local.azs : az => local.private_subnet[idx] }
  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value
  availability_zone = each.key
  tags              = merge(var.tags, { Name = "${var.environment_name}-public-${each.key}" })
}

# * Resource-5: Elastic IP for NAT-Gateway
resource "aws_eip" "nat_eip" {
  tags = merge(var.tags, { Name = "${var.environment_name}-nat-eip" })
}
# * Resource-6: NAT Gateway
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id     = values(aws_subnet.public)[0].id

  tags = merge(var.tags, { Name = "${var.environment_name}-nat" })

  depends_on = [aws_internet_gateway.igw]
}
# * Resource-7: Public Route Table
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = merge(var.tags, {
    Name = "${var.environment_name}-public-rt"
  })
}
# * Resource-8: Public Route Table Associate to Public Subnet
resource "aws_route_table_association" "public_rt_assoc" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public_rt.id
}
# * Resource-9: Private Route Table
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = merge(var.tags, { Name = "${var.environment_name}-private-rt" })
}
# * Resource-10: Private Route Table Association to Private Subnet
resource "aws_route_table_association" "private_rt_assoc" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private_rt.id
}
