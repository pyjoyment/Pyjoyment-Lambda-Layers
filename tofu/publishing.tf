resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# Assumed by the jobs of the environment publishing of the repository only
data "aws_iam_policy_document" "publishing_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repository}:environment:publishing"]
    }
  }
}

resource "aws_iam_role" "publishing" {
  name               = "Pyjoyment-Lambda-Layers-publishing"
  assume_role_policy = data.aws_iam_policy_document.publishing_trust.json
}

data "aws_iam_policy_document" "publishing" {
  # The layers of the account and their versions, in every region; nothing deletes a version
  statement {
    actions = [
      "lambda:AddLayerVersionPermission",
      "lambda:GetLayerVersion",
      "lambda:PublishLayerVersion",
    ]
    resources = ["arn:aws:lambda:*:${local.account_id}:layer:*"]
  }

  # Without resources of their own in IAM; account:ListRegions gives the regions that the layers are published in
  statement {
    actions = [
      "account:ListRegions",
      "lambda:ListLayerVersions",
      "lambda:ListLayers",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "publishing" {
  name   = "publishing"
  role   = aws_iam_role.publishing.id
  policy = data.aws_iam_policy_document.publishing.json
}
