terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
  # Remote Backend
  backend "s3" {
    bucket       = "tfstate-dev-us-east-1-jpjtof"
    key          = "vpc/dev/terraform.tfstate" // The specific path and filename inside the S3 bucket where your state is saved.
    region       = "us-east-1"
    encrypt      = true // A boolean flag that enables Server-Side Encryption (SSE) using AES-256
    use_lockfile = true // It enables Native S3 State Locking
  }
}

provider "aws" {
  region = var.aws_region
}
