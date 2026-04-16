from django.db import models

class SiteSettings(models.Model):
    business_name = models.CharField(max_length=100, default='Dishi Poa')
    tagline = models.CharField(max_length=200, default='Fresh, Hot, On Time.')
    phone = models.CharField(max_length=20, default='+254 700 000 000')
    email = models.EmailField(default='hello@dishipoa.co.ke')
    address = models.TextField(default='Nairobi, Kenya')
    mpesa_till = models.CharField(max_length=20, blank=True)
    mpesa_paybill = models.CharField(max_length=20, blank=True)
    mpesa_account = models.CharField(max_length=50, blank=True, default='DISHIPOA')
    ordering_open_message = models.CharField(max_length=200, default="Order before cutoff time!")
    ordering_closed_message = models.CharField(max_length=200, default="Ordering is closed for today. Check back tomorrow!")
    hero_image = models.ImageField(upload_to='site/', null=True, blank=True)
    logo = models.ImageField(upload_to='site/', null=True, blank=True)
    about_text = models.TextField(blank=True)
    chef_name = models.CharField(max_length=100, blank=True)
    chef_photo = models.ImageField(upload_to='site/', null=True, blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self): return self.business_name
