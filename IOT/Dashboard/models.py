# firstaid/models.py
import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone


# -----------------------
# Medicine Model
# -----------------------
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
        return self.expiry_date < datetime.date.today()

    @property
    def days_until_expiry(self):
        return (self.expiry_date - datetime.date.today()).days

    @property
    def is_low_stock(self):
        return self.quantity <= 5


# -----------------------
# Access Log
# -----------------------
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
        return f"{self.user.username if self.user else 'System'} - {self.action}"


# -----------------------
# Notification
# -----------------------
class Notification(models.Model):
    TYPE_CHOICES = [
        ('low_stock', 'Low Stock'),
        ('expired', 'Expired Medicine'),
        ('system_alert', 'System Alert'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('alert', 'Alert'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    message = models.TextField()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# -----------------------
# Medicine Usage History
# -----------------------
class MedicineUsage(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    quantity_used = models.PositiveIntegerField(default=1)
    usage_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine.name} used by {self.user.username}"


# -----------------------
# User Profile
# -----------------------
STATUS_CHOICES = (
    ('idle', 'Idle'),
    ('scanned', 'ID Scanned'),
    ('requested', 'Medicine Requested'),
    ('pending_scan', 'Pending Scan'),
)

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    roll_no = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_admin = models.BooleanField(default=False)

    interaction_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='idle'
    )

    def __str__(self):
        return self.user.username


# -----------------------
# System Status
# -----------------------
class SystemStatus(models.Model):
    is_locked = models.BooleanField(default=True)
    esp32_connected = models.BooleanField(default=False)
    last_esp32_ping = models.DateTimeField(null=True, blank=True)
    current_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    camera_on = models.BooleanField(default=False)
    camera_expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return "System Status"
