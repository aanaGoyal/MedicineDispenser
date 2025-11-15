from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('roll_no', 'email', 'first_name', 'last_name', 'course_name', 'is_staff')
    list_filter = ('course_name', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('roll_no', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_no', 'date_of_birth', 'course_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('roll_no', 'email', 'first_name', 'last_name', 'phone_no', 'date_of_birth', 'course_name', 'password1', 'password2'),
        }),
    )
    search_fields = ('roll_no', 'email', 'first_name', 'last_name')
    ordering = ('roll_no',)

admin.site.register(CustomUser, CustomUserAdmin)
