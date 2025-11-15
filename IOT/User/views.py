from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, SignUpForm
from .models import CustomUser
from django.contrib.auth import logout
from Dashboard.models import UserProfile
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            roll_no = form.cleaned_data['roll_no']
            password = form.cleaned_data['password']
            email = form.cleaned_data['email']
            
            try:
                user = CustomUser.objects.get(roll_no=roll_no, email=email)
                if user.check_password(password):
                    login(request, user)
                    messages.success(request, 'Login successful!')
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Invalid credentials')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Invalid credentials')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})
# def signup_view(request):
#     if request.method == 'POST':
#         form = SignUpForm(request.POST)
#         if form.is_valid():
#             roll_no = form.cleaned_data.get('roll_no')
            
#             # Check if a user with this roll number already exists
#             if UserProfile.objects.filter(roll_no=roll_no).exists():
#                 # Add a custom error message to the form's roll_no field
#                 form.add_error('roll_no', 'This roll number is already registered.')
#                 messages.error(request, 'Please correct the errors below.')
#             else:
#                 user = form.save()
#                 messages.success(request, 'Account created successfully! Please login.')
#                 return redirect('login')
#         else:
#             # Add this line for an overall message when other errors occur
#             messages.error(request, 'Please correct the errors below.') 
#     else:
#         form = SignUpForm()
    
#     return render(request, 'signup.html', {'form': form})
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import SignUpForm
from django.db import IntegrityError

def signup_view(request):
    """
    Handles user signup including profile picture upload.
    """
    if request.method == 'POST':
        # ✅ Include both POST and FILES
        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Account created successfully! Please sign in.')
                return redirect('login')
            except IntegrityError:
                messages.error(request, 'A user with this roll number already exists. Please try again.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SignUpForm()
    
    return render(request, 'signup.html', {'form': form})





def logout_view(request):
    """
    Logs out the user and clears the session flag for the interaction reset.
    """
    # CRITICAL: Clear the flag so the dashboard reset runs on the next login
    if 'interaction_reset_done' in request.session:
        del request.session['interaction_reset_done']
        
    logout(request)
    messages.info(request, "You have been logged out.")
    # NOTE: Ensure 'login' is the correct name for your login URL pattern
    return redirect('home') 
def index(request):
    return render(request, 'index.html')

