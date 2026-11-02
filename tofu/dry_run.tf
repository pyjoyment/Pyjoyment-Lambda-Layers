# Assumed by the jobs of the pull requests of the repository, which show what the publication would do
data "aws_iam_policy_document" "dry_run_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.subject}:pull_request"]
    }
  }
}

resource "aws_iam_role" "dry_run" {
  name               = "Pyjoyment-Lambda-Layers-dry-run"
  assume_role_policy = data.aws_iam_policy_document.dry_run_trust.json

  # The provider of the principal of the trust, whose ARN the document builds itself
  depends_on = [aws_iam_openid_connect_provider.github]
}

# Only what the publication reads
data "aws_iam_policy_document" "dry_run" {
  statement {
    actions   = ["lambda:GetLayerVersion"]
    resources = ["arn:aws:lambda:*:${local.account_id}:layer:*"]
  }

  statement {
    actions = [
      "account:ListRegions",
      "lambda:ListLayerVersions",
      "lambda:ListLayers",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "dry_run" {
  name   = "dry-run"
  role   = aws_iam_role.dry_run.id
  policy = data.aws_iam_policy_document.dry_run.json
}
