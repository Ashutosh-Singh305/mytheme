from django.urls import reverse


def build_breadcrumbs(editing, slug, step, report=None, view_type=None):

    # Determine design step label
    if report:
        is_tabular = (report.view_type == "tabular")
    else:
        is_tabular = (view_type == "tabular")

    design_label = "Select Fields" if is_tabular else "Groupings & Measures"

    step_labels = {
        "basic": "Basic Info",
        "design": design_label,
        "filters": "Filters",
    }

    crumbs = [("All Reports", reverse("reports:list"))]

    if editing:
        crumbs.append((report.name, reverse("reports:detail", args=[slug])))
        base_url = reverse("reports:edit", args=[slug])
    else:
        crumbs.append(("New Report", reverse("reports:new")))
        base_url = reverse("reports:new")

    for key, label in step_labels.items():
        url = f"{base_url}?step={key}"
        if key == step:
            crumbs.append((label, None))
            break
        else:
            crumbs.append((label, url))

    return crumbs
