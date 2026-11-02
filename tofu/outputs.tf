# role-to-assume of aws-actions/configure-aws-credentials in the workflow of the publication
output "publishing_role_arn" {
  value = aws_iam_role.publishing.arn
}

output "opt_in_regions" {
  value = sort(tolist(data.aws_regions.opt_in.names))
}

# role-to-assume of the dry run of the publication in the workflow of a pull request
output "dry_run_role_arn" {
  value = aws_iam_role.dry_run.arn
}
