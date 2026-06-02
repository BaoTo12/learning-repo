# Terraform block
# Terraform block is the foundation block of Terraform configuration
# Includes
# 1. Require Terraform version
# 2. Require Providers

terraform {
  required_version = ">= 1.0.0" # --> argument
  required_providers {          # --> Block has arguments
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

     random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Provider block
# Configure Behavior + Authentication 
provider "aws" {
  # ── 1. REGION ─────────────────────────────────────────────────
  # Required với hầu hết resources.
  # Nếu bỏ qua: Terraform đọc từ env var AWS_DEFAULT_REGION
  # Nếu cả hai đều không có: error lúc plan
  region = "us-east-1"


  # ── 2. CREDENTIALS ────────────────────────────────────────────
  # Option A: Hardcode (KHÔNG dùng trong production)
  # access_key = "AKIAIOSFODNN7EXAMPLE"
  # secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

  # Option B: Profile từ ~/.aws/credentials
  # Terraform đọc section [my-profile] trong credentials file
  # profile = "my-profile"

  # Option C: Không khai báo gì
  # → Terraform tự chạy credential chain (xem mục 3)


  # ── 3. ASSUME ROLE ────────────────────────────────────────────
  # Dùng khi cần switch sang role khác để deploy
  # Phổ biến trong multi-account AWS org
#   assume_role {
#     role_arn     = "arn:aws:iam::123456789012:role/TerraformRole"
#     session_name = "terraform-deploy"          # tên session, dễ trace trong CloudTrail
#     external_id  = "unique-external-id-12345"  # chống confused deputy attack
#     # duration_seconds = 3600                  # default 1h, max 12h
#   }

  # ── 4. DEFAULT TAGS ───────────────────────────────────────────
  # Apply tự động lên TẤT CẢ resources managed bởi provider này
  # Không cần khai báo tags trong từng resource
  # Nếu resource tự định nghĩa tag trùng key → CONFLICT ERROR
#   default_tags {
#     tags = {
#       ManagedBy   = "Terraform"
#       Environment = "production"
#       Team        = "platform"
#       Repository  = "github.com/myorg/infra"
#     }
#   }
}


## 3. Credential Chain — Thứ tự ưu tiên chính xác

# Khi bạn **không** khai báo `access_key`/`secret_key`, AWS provider tự resolve credentials theo thứ tự này:

# 1. Static args trong provider block        (access_key, secret_key)
# 2. Environment variables                   (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
# 3. Shared credentials file                 (~/.aws/credentials)
# 4. Shared config file                      (~/.aws/config)
# 5. Container credentials                   (ECS task role via metadata endpoint)
# 6. Instance Profile / EC2 metadata         (IMDSv2 endpoint)
# 7. EKS Pod Identity / IRSA                 (via projected ServiceAccount token)