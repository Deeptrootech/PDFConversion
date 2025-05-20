from django.db import models


class WhiteLabelConfig(models.Model):
    logo = models.ImageField(upload_to='', null=True, blank=True)
    client_company_name = models.CharField(max_length=100, unique=True)
    company_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.client_company_name
