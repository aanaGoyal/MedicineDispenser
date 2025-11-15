from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from .validators import strong_password

class LoginForm(forms.Form):
    roll_no = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Roll Number', 'required': True})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email', 'required': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter Password', 'required': True})
    )

    def clean(self):
        cleaned_data = super().clean()
        roll_no = cleaned_data.get('roll_no')
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if roll_no and email and password:
            try:
                user = CustomUser.objects.get(roll_no=roll_no, email=email)
                if not user.check_password(password):
                    raise forms.ValidationError("Invalid credentials")
            except CustomUser.DoesNotExist:
                raise forms.ValidationError("Invalid credentials")
        return cleaned_data


class SignUpForm(UserCreationForm):
    roll_no = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Roll Number'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email'})
    )
    phone_no = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Phone Number'})
    )
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter First Name'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Last Name'})
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    course_name = forms.ChoiceField(
        choices=CustomUser.COURSE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ✅ Add image upload field
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        if password:
            try:
                strong_password(password)
            except forms.ValidationError as e:
                self.add_error('password2', e.message)
        return cleaned_data

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            'roll_no', 'email', 'phone_no', 'first_name', 'last_name',
            'date_of_birth', 'course_name', 'profile_picture'
        )

    def clean_roll_no(self):
        roll_no = self.cleaned_data['roll_no']
        if CustomUser.objects.filter(roll_no=roll_no).exists():
            raise forms.ValidationError("Roll number already exists")
        return roll_no

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['roll_no']
        if self.cleaned_data.get('profile_picture'):
            user.profile_picture = self.cleaned_data['profile_picture']
        if commit:
            user.save()
        return user
