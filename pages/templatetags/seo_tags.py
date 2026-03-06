import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def jsonld_organization():
    """Output Organization structured data for DFS Education."""
    data = {
        "@context": "https://schema.org",
        "@type": "EducationalOrganization",
        "name": "DFS Education",
        "url": "https://dfsscholarships.com",
        "logo": "https://dfsscholarships.com/static/images/og-default.png",
        "description": "DFS Education provides guaranteed scholarships in China for international students.",
        "sameAs": [],
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "availableLanguage": ["English"],
        },
        "areaServed": {
            "@type": "Country",
            "name": "China",
        },
    }
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(data, indent=2)}</script>'
    )


@register.simple_tag
def jsonld_website():
    """Output WebSite structured data with search action."""
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "DFS Education",
        "url": "https://dfsscholarships.com",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": "https://dfsscholarships.com/scholarships/?q={search_term_string}",
            },
            "query-input": "required name=search_term_string",
        },
    }
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(data, indent=2)}</script>'
    )


@register.simple_tag
def jsonld_scholarship(scholarship):
    """Output structured data for an individual scholarship."""
    data = {
        "@context": "https://schema.org",
        "@type": "EducationalOccupationalProgram",
        "name": scholarship.name,
        "description": scholarship.description[:300] if scholarship.description else "",
        "provider": {
            "@type": "CollegeOrUniversity",
            "name": getattr(scholarship, 'university', f"University in {scholarship.city}"),
            "address": {
                "@type": "PostalAddress",
                "addressLocality": scholarship.city,
                "addressCountry": "CN",
            },
        },
        "educationalProgramMode": "full-time",
        "programType": scholarship.get_degree_display(),
        "occupationalCategory": scholarship.major,
        "url": f"https://dfsscholarships.com{scholarship.get_absolute_url()}",
    }
    if scholarship.deadline:
        data["applicationDeadline"] = scholarship.deadline.isoformat()
    if scholarship.scholarship_type:
        data["offers"] = {
            "@type": "Offer",
            "category": scholarship.get_scholarship_type_display(),
            "description": f"{scholarship.get_scholarship_type_display()} scholarship",
        }
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(data, indent=2)}</script>'
    )


@register.simple_tag
def jsonld_breadcrumb(items):
    """
    Output BreadcrumbList structured data.
    items: list of tuples [(name, url), (name, url), ...]
    The last item should have url=None (current page).
    """
    list_items = []
    for i, (name, url) in enumerate(items, 1):
        item = {
            "@type": "ListItem",
            "position": i,
            "name": name,
        }
        if url:
            item["item"] = f"https://dfsscholarships.com{url}"
        list_items.append(item)

    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": list_items,
    }
    return mark_safe(
        f'<script type="application/ld+json">{json.dumps(data, indent=2)}</script>'
    )
