# The regions that an account has to opt in to, enabled or not yet, so that a new region of AWS is enabled by the next
# apply and the layers are published there too
data "aws_regions" "opt_in" {
  all_regions = true

  filter {
    name   = "opt-in-status"
    values = ["opted-in", "not-opted-in"]
  }
}

resource "aws_account_region" "opt_in" {
  for_each = data.aws_regions.opt_in.names

  region_name = each.value
  enabled     = true

  # A region that is disabled takes the layers published there away from the functions that use them
  lifecycle {
    prevent_destroy = true
  }
}
