# Resource Block: Random String
resource "random_string" "random" {
  length = 6
  special = false
  upper = false
}

# Resource Block: AWS S3 bucket
resource "aws_s3_bucket" "demo_bucket" {
  bucket = "devops_demo-${random_string.random.result}"
  tags = {
    Name = "Devops Demo Bucket"
    Environment = "Dev"
  }
}

