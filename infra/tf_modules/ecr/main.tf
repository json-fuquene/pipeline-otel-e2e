locals { image_set = toset(var.image_names) }

resource "aws_ecr_repository" "images" {
  for_each             = local.image_set
  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  force_delete = true
}
