from django.db import models


class Office(models.Model):
    """
    Represents a physical branch / office location.
    Office-role users and agents are assigned to an Office.
    Applications created by an office belong to that office.
    """
    name = models.CharField(
        max_length=200,
        help_text='Display name, e.g. "Istanbul Office"',
    )
    code = models.SlugField(
        max_length=30, unique=True,
        help_text='Short unique code, e.g. "istanbul", "cairo"',
    )
    city = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    is_default = models.BooleanField(
        default=False,
        help_text='Mark as the default/fallback office for unmatched regions.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'offices'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default office
        if self.is_default:
            Office.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class OfficeRegion(models.Model):
    """
    Maps a country (or country + optional city) to an Office.
    Used for auto-routing students/applications to the correct branch.
    """
    office = models.ForeignKey(
        Office, on_delete=models.CASCADE, related_name='regions',
    )
    country_code = models.CharField(
        max_length=3,
        help_text='ISO 3166-1 alpha-2 country code, e.g. "TR", "EG"',
    )
    country_name = models.CharField(
        max_length=100,
        help_text='Human-readable country name, e.g. "Turkey", "Egypt"',
    )
    city = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Optional city for more specific routing (leave blank for whole country).',
    )

    class Meta:
        db_table = 'office_regions'
        unique_together = ['country_code', 'city']
        ordering = ['country_name', 'city']

    def __str__(self):
        if self.city:
            return f"{self.country_name} ({self.city}) → {self.office.name}"
        return f"{self.country_name} → {self.office.name}"


def get_office_for_location(country, city=''):
    """
    Return the best-matching Office for a given country/city.
    Falls back to the default office, or None if nothing matches.
    """
    # Try city-specific match first
    if city:
        region = OfficeRegion.objects.filter(
            country_name__iexact=country, city__iexact=city, office__is_active=True
        ).select_related('office').first()
        if region:
            return region.office

    # Try country-level match
    region = OfficeRegion.objects.filter(
        country_name__iexact=country, city='', office__is_active=True
    ).select_related('office').first()
    if region:
        return region.office

    # Fallback to default office
    return Office.objects.filter(is_default=True, is_active=True).first()
