from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class CustomUser(AbstractUser):
    COURSE_CHOICES = [
        ('CSE','Computer Science Engineering'),
        ('CSE_AI_ML', 'Computer Science Engineering with Artificial Intelligence'),
        ('ECE', 'Electronics & Communication Engineering'),
        ('ME', 'Mechanical Engineering'),
        ('EE', 'Electrical Engineering'),
        ('CE', 'Civil Engineering'),
        ('BCA', 'Bachelor of Computer Applications'),
        ('BSC_NS', 'B.Sc in Nautical Sciences'),
        ('MBA_DS_AI', 'MBA in Data Science & Artificial Intelligence'),
        ('BE_CSE_ASU', 'B.E. in CSE with ASU, USA'),
        ('BBA', 'Bachelor of Business Administration'),
        ('BSC_CA', 'B.Sc in Culinary Arts'),
        ('BDes_UX', 'B.Des in User Experience'),
        ('BARCH', 'Bachelor of Architecture'),
        ('BAJMC_AI', 'BAJMC with AI Specialisation'),
        ('BPHARM', 'Bachelor of Pharmacy'),
        ('NURSING', 'Nursing'),
        ('BED', 'Bachelor of Education (B.Ed)'),
    ]

    roll_no = models.CharField(
        max_length=20, 
        unique=True,
        validators=[RegexValidator(r'^[A-Z0-9]+$', 'Roll number should contain only uppercase letters and numbers')]
    )
    phone_no = models.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Phone number must be entered in valid format')]
    )
    date_of_birth = models.DateField()
    course_name = models.CharField(max_length=30, choices=COURSE_CHOICES)
    
    # ✅ Add this new field
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    USERNAME_FIELD = 'roll_no'
    is_admin = models.BooleanField(default=False)
    REQUIRED_FIELDS = ['username', 'email', 'first_name', 'phone_no', 'date_of_birth', 'course_name', 'is_admin']

    def __str__(self):
        return f"{self.roll_no} - {self.get_full_name()}"
