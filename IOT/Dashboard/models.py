# In your models.py
import datetime
from django.db import models
from django.conf import settings  # Correct import for swapped user model
from django.utils import timezone
from django.db import models
from django.conf import settings 

class Medicine(models.Model):
    name = models.CharField(max_length=100)
    barcode = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default='General')
    dosage = models.CharField(max_length=50, blank=True)
    quantity = models.IntegerField(default=0)
    expiry_date = models.DateField()
    manufacturer = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def is_expired(self):
        """Returns True if the medicine's expiry date is in the past."""
        return self.expiry_date < datetime.date.today()

    @property
    def days_until_expiry(self):
        """Returns the number of days until the medicine expires."""
        return (self.expiry_date - datetime.date.today()).days
    
    @property
    def is_low_stock(self):
        """Returns True if the medicine quantity is at or below the low stock threshold (e.g., 5)."""
        return self.quantity <= 5

class AccessLog(models.Model):
    ACTION_CHOICES = [
        ('unlock', 'Unlock Box'),
        ('dispense', 'Dispense Medicine'),
        ('scan', 'Barcode Scan'),
        ('fail', 'Failed Attempt'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    quantity_dispensed = models.IntegerField(default=0)
    details = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.action} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('low_stock', 'Low Stock'),
        ('expired', 'Expired Medicine'),
        ('system_alert', 'System Alert'),
    ]
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    message = models.TextField()
    
    # 🌟 FIX APPLIED HERE: Must use settings.AUTH_USER_MODEL
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
class MedicineUsage(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    quantity_used = models.PositiveIntegerField(default=1)
    usage_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine.name} used by {self.user.username}"
STATUS_CHOICES = (
    ('idle', 'Idle (Ready to scan ID)'),
    ('scanned', 'ID Scanned (Awaiting medicine choice)'),
    ('requested', 'Medicine Requested (Awaiting dispense confirmation)'),
)
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    roll_no = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_admin = models.BooleanField(default=False)
    face_encoding_path = models.CharField(max_length=255, blank = True, null = True)  # path to saved encoding .npy
    # 🌟 CRITICAL FIX: Add the interaction_status field
    interaction_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='idle',
        help_text='Current interaction state with the IoT box.'
    )

    def __str__(self):
        return self.user.username
    
from django.utils import timezone
from django.db import models
from django.conf import settings

class SystemStatus(models.Model):
    is_locked = models.BooleanField(default=True)
    esp32_connected = models.BooleanField(default=False)
    last_esp32_ping = models.DateTimeField(null=True, blank=True)
    current_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    # NEW fields
    camera_on = models.BooleanField(default=False)
    camera_expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return "System Status"
