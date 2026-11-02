terraform {
  # use_lockfile of the backend s3
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "pyjoyment-tofu-state-959435416781"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"

  # The credentials come from AWS_PROFILE, and a profile of another account fails before it changes anything
  allowed_account_ids = [local.account_id]

  default_tags {
    tags = {
      Repository = local.repository
    }
  }
}

locals {
  account_id = "959435416781"
  repository = "pyjoyment/Pyjoyment-Lambda-Layers"

  # The immutable subject of the OIDC tokens of the repository, with the IDs of its owner and of itself, as
  # sub_claim_prefix of `gh api repos/pyjoyment/Pyjoyment-Lambda-Layers/actions/oidc/customization/sub` gives it
  subject = "repo:pyjoyment@351424207/Pyjoyment-Lambda-Layers@1443233156"
}
