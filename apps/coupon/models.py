from django.db import models

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    value = models.IntegerField()
    active = models.BooleanField(default=True)
    num_available = models.IntegerField(default=1)
    num_used = models.IntegerField(default=0)

    def __str__(self):
        return self.code
    
    def can_use(self):
        is_active = True

        if self.active == False:
            is_active = False
        
        if self.num_used >= self.num_available and self.num_available != 0:
            is_active = False
        
        return is_active
    
    def use(self):
        self.num_used = self.num_used + 1

        if self.num_used == self.num_available:
            self.active = False
        
        self.save()