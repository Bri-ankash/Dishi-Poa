from django.db import models

class GalleryItem(models.Model):
    CATEGORY = [('food','Food'),('kitchen','Kitchen'),('delivery','Delivery'),('general','General')]
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='gallery/')
    category = models.CharField(max_length=20, choices=CATEGORY, default='general')
    uploaded_by = models.ForeignKey('users.DishiUser', on_delete=models.SET_NULL, null=True, blank=True)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.title
    class Meta: ordering = ['-created_at']
