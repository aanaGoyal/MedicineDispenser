# In your firstaid/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.contrib import messages
import requests
from .models import Medicine, AccessLog, Notification, MedicineUsage, SystemStatus, UserProfile
from datetime import datetime
import os# In your firstaid/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.contrib import messages
import requests
from .models import Medicine, AccessLog, Notification, MedicineUsage, SystemStatus, UserProfile
from datetime import datetime
import os

# --- ADD THESE IMPORTS NEAR THE TOP OF VIEWS.PY ---
import paho.mqtt.client as mqtt
import ssl

# Utility function placeholders
# Placeholder for utility function (ensure this is defined elsewhere in your views.py)
# In your firstaid/views.py (Update the utility function)

# Placeholder for utility function (ensure this is defined elsewhere in your views.py)
def get_esp32_status():
    """Checks the SystemStatus object for connection health."""
    try:
        status_obj = SystemStatus.objects.first() 
        if status_obj:
            # Check if last_esp32_ping is within the last 5 minutes
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            is_online = status_obj.esp32_connected and \
                        status_obj.last_esp32_ping and \
                        status_obj.last_esp32_ping > five_minutes_ago
                        
            # Use 'Online' only if the ping is recent
            status = 'Online' if is_online else 'Offline'
            
            return {
                'status': status, 
                'last_ping': status_obj.last_esp32_ping,
                'is_locked': status_obj.is_locked, # Added for dashboard display
                'camera_on': status_obj.camera_on # Added for dashboard display
            }
        return {'status': 'Unknown', 'last_ping': None, 'is_locked': True, 'camera_on': False}
    except Exception:
        return {'status': 'Error', 'last_ping': None, 'is_locked': True, 'camera_on': False}


@login_required
def dashboard(request):
    """
    Renders the main dashboard. Enforces status reset on login and prompts for medicine selection.
    """

    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found. Please ensure your profile is complete.')
        return redirect('profile_view') 

    # --- FULL INTERACTION RESET (ONLY ONCE PER SESSION) ---
    
    if not request.session.get('interaction_reset_done'):
        # Delete flow-related messages and force status to idle on fresh login/session start
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            # Target both old scan prompt and new select prompt
            title__in=["Scan ID Required", "Please Select Medicine"] 
        ).delete()
        
        # Force status to idle to ensure flow starts from the beginning
        if user_profile.interaction_status != 'idle':
            user_profile.interaction_status = 'idle'
            user_profile.save()
            
        request.session['interaction_reset_done'] = True
    
    # --- NEW NOTIFICATION LOGIC: PROMPT TO SELECT MEDICINE ---
    
    create_select_notification = False
    
    # 1. Check User Status: Only prompt if the user is idle
    if user_profile.interaction_status == 'idle':
        
        # Check if the "Select Medicine" message already exists (prevents spam on refresh)
        select_notification_exists = Notification.objects.filter(
            user=request.user, 
            title="Please Select Medicine", 
            is_read=False
        ).exists()
        
        if not select_notification_exists:
            create_select_notification = True

    # 2. Create Notification if necessary
    if create_select_notification:
        Notification.objects.create(
            user=request.user,
            title="Please Select Medicine",
            message="Welcome! Please select the medicine(s) you need from the list.",
            type='system_alert'
        )
    
    # --- STATS GATHERING ---
    total_medicines = Medicine.objects.count()
    low_stock_count = Medicine.objects.filter(quantity__lte=5).count()
    expired_count = Medicine.objects.filter(expiry_date__lt=timezone.now().date()).count()

    notifications = Notification.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('-created_at')[:5]

    recent_logs = AccessLog.objects.filter(user=request.user).order_by('-timestamp')[:10]
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    usage_stats = MedicineUsage.objects.filter(usage_date__gte=thirty_days_ago, user=request.user) \
        .values('medicine__name') \
        .annotate(total_used=Sum('quantity_used')) \
        .order_by('-total_used')[:5]

    context = {
        'esp32_status': get_esp32_status(),
        'total_medicines': total_medicines,
        'low_stock_count': low_stock_count,
        'expired_count': expired_count,
        'recent_logs': recent_logs,
        'usage_stats': usage_stats,
        'notifications': notifications,
    }
    return render(request, 'dashboard.html', context)

@login_required
def medicines_list(request):
    """
    Renders the list of medicines, handling filtering, searching, and pagination.
    """
    medicines = Medicine.objects.all().order_by('name')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')

    if search_query:
        medicines = medicines.filter(
            Q(name__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    if category_filter:
        medicines = medicines.filter(category=category_filter)

    if stock_filter == 'low':
        medicines = medicines.filter(quantity__lte=5)
    elif stock_filter == 'expired':
        medicines = medicines.filter(expiry_date__lt=timezone.now().date())

    categories = Medicine.objects.values_list('category', flat=True).distinct()

    paginator = Paginator(medicines, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'categories': categories,
    }
    return render(request, 'medicines_list.html', context)

@login_required
def medicine_detail(request, medicine_id):
    """
    Displays detailed information about a single medicine.
    """
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    usage_history = MedicineUsage.objects.filter(medicine=medicine).order_by('-usage_date')[:10]
    access_logs = AccessLog.objects.filter(medicine=medicine).order_by('-timestamp')[:10]
    notifications = Notification.objects.filter(medicine=medicine).order_by('-created_at')[:5]

    context = {
        'medicine': medicine,
        'usage_history': usage_history,
        'access_logs': access_logs,
        'notifications': notifications,
    }
    return render(request, 'firstaid/medicine_detail.html', context)

@login_required
def add_medicine(request):
    """
    Handles adding a new medicine to the inventory.
    Requires admin privileges.
    """
    try:
        if not request.user.is_admin:
            messages.error(request, 'You do not have permission to add medicines.')
            return redirect('medicines_list')
    except UserProfile.DoesNotExist:
        # If the user doesn't have a profile, they can't be an admin.
        messages.error(request, 'You do not have permission to add medicines.')
        return redirect('medicines_list')

    if request.method == 'POST':
        try:
            name = request.POST['name']
            barcode = request.POST['barcode']
            quantity = int(request.POST['quantity'])
            expiry_date_str = request.POST['expiry_date']

            if not name or not barcode or not expiry_date_str:
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'firstaid/add_medicine.html')

            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()

            Medicine.objects.create(
                name=name,
                barcode=barcode,
                description=request.POST.get('description', ''),
                category=request.POST.get('category', 'General'),
                dosage=request.POST.get('dosage', ''),
                quantity=quantity,
                expiry_date=expiry_date
            )
            
            messages.success(request, 'Medicine added successfully!')
            return redirect('medicines_list')

        except (KeyError, ValueError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
            return render(request, 'add_medicine.html')
    
    return render(request, 'add_medicine.html')

@login_required
def request_medicines(request):
    if request.method == 'POST':
        selected_medicine_ids = request.POST.getlist('medicines')
        
        try:
            user_profile = request.user.userprofile
            roll_no = user_profile.roll_no
        except UserProfile.DoesNotExist:
            messages.error(request, 'Your user profile is incomplete.')
            return redirect('medicines_list')

        if not selected_medicine_ids:
            messages.error(request, 'Please select at least one medicine.')
            return redirect('medicines_list')

        selected_medicines = Medicine.objects.filter(id__in=selected_medicine_ids)
        
        # --- INSTANT STOCK CHECK ---
        out_of_stock = []
        in_stock_names = []
        for medicine in selected_medicines:
            if medicine.quantity < 1:
                out_of_stock.append(medicine.name)
            else:
                in_stock_names.append(medicine.name)

        if out_of_stock:
            messages.error(request, f'The following medicines are out of stock: {", ".join(out_of_stock)}.')
            AccessLog.objects.create(user=request.user, action=f"Request failed: {', '.join(out_of_stock)} out of stock.", success=False)
            return redirect('medicines_list')

        # --- STOCK IS AVAILABLE: PROCEED TO PENDING SCAN STATE ---
        
        if not in_stock_names:
             messages.error(request, 'No medicine was selected or available.')
             return redirect('medicines_list')
             
        # Store requested items in the session 
        request.session['requested_medicines'] = in_stock_names
        
        # 1. SET STATUS: Update User Status to 'pending_scan'
        user_profile.interaction_status = 'pending_scan'
        user_profile.save()
        
        # 2. CREATE NEW PROMPT NOTIFICATION
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            title__in=["Please Select Medicine"] # Delete old select prompt
        ).delete()
        
        Notification.objects.create(
            user=request.user,
            title="Scan ID Required",
            message=f"Stock confirmed for {', '.join(in_stock_names)}. Please scan your ID card at the First-Aid Box to dispense.",
            type='system_alert'
        )

        # 3. Log the pending request
        AccessLog.objects.create(
            user=request.user,
            action=f"Request initiated for: {', '.join(in_stock_names)} (Pending ID Scan)",
            success=True,
        )
        
        messages.info(request, 'Stock confirmed. Please scan your ID card at the box to retrieve.')

        return redirect('dashboard')
    
    return redirect('medicines_list')

from django.contrib.auth.decorators import login_required
from .models import MedicineUsage
@login_required
def profile_view(request):
    user = request.user  # current logged-in user

    if request.method == 'POST':
        if 'change_picture' in request.POST and request.FILES.get('profile_picture'):
            # If user uploaded a new picture
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            messages.success(request, "Profile picture updated successfully!")

        elif 'delete_picture' in request.POST:
            # Delete old picture from filesystem
            if user.profile_picture:
                if os.path.isfile(user.profile_picture.path):
                    os.remove(user.profile_picture.path)
                user.profile_picture = None
                user.save()
                messages.info(request, "Profile picture deleted.")

    return render(request, 'profile.html', {'user': user})

# In your firstaid/views.py (Add this section to the bottom of the file)
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction

# Ensure all necessary models are imported at the very top:
# from .models import Medicine, AccessLog, Notification, MedicineUsage, SystemStatus, UserProfile


@csrf_exempt
def handle_iot_confirmation(request):
    """
    Receives confirmation POST request from ESP32.
    Handles the ID Scan (scan_complete) as the final dispense trigger, 
    verifies ID, and adjusts stock based on payload details.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)

    data = {}
    try:
        data = json.loads(request.body)
        roll_no = data.get('roll_no')
        action_type = data.get('action_type')
        details = data.get('details', '') # Details now contains the dispensed medicine list
        
        if not all([roll_no, action_type]):
             return JsonResponse({'status': 'error', 'message': 'Missing roll_no or action_type in payload'}, status=400)
             
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)

    try:
        user_profile = UserProfile.objects.select_related('user').get(roll_no=roll_no)
        user = user_profile.user
    except UserProfile.DoesNotExist:
        AccessLog.objects.create(action=f"IoT Confirmation Failed - Unknown ID: {roll_no}", success=False)
        return JsonResponse({'status': 'error', 'message': 'ID card not recognized (No UserProfile found)'}, status=403)

    # --- Confirmation Logic ---
    
    if action_type == 'scan_complete':
        
        # 1. Check if user is in the 'pending_scan' state
        if user_profile.interaction_status == 'pending_scan':
            
            # --- SECURITY CHECK: ROLL NUMBER VERIFICATION ---
            if str(roll_no) != str(user_profile.roll_no):
                # ID mismatch! Deny dispense and reset status.
                user_profile.interaction_status = 'idle'
                user_profile.save()
                
                Notification.objects.create(user=user, title="SECURITY ALERT", message="ID scan failed: The scanned ID does not match the requesting user.", type='error')
                AccessLog.objects.create(user=user, action=f"SECURITY FAILURE: Scanned ID ({roll_no}) did not match requesting user ID.", success=False)
                
                return JsonResponse({'status': 'denied', 'message': 'ID mismatch. Dispense blocked.'}, status=403)
            # --- END SECURITY CHECK ---

            # --- CRITICAL FIX: RETRIEVE MEDICINES FROM PAYLOAD (details) ---
            if not details:
                 return JsonResponse({'status': 'error', 'message': 'Medicine details missing in scan confirmation payload.'}, status=400)
                 
            # Parse the details string (e.g., "Ibuprofen, Paracetamol") into a list
            requested_items = [name.strip() for name in details.split(',') if name.strip()]

            if not requested_items:
                return JsonResponse({'status': 'error', 'message': 'No valid medicines specified in the payload details.'}, status=400)
            
            # Since the dispense is confirmed, clear the session item (if it exists)
            if 'requested_medicines' in request.session:
                del request.session['requested_medicines']
            
            # --- STOCK ADJUSTMENT AND USAGE LOGGING ---
            try:
                with transaction.atomic():
                    successfully_dispensed = []
                    for name in requested_items:
                        try:
                            medicine = Medicine.objects.get(name__iexact=name)
                            
                            if medicine.quantity >= 1: 
                                medicine.quantity -= 1
                                medicine.save()
                                MedicineUsage.objects.create(user=user, medicine=medicine, quantity_used=1)
                                successfully_dispensed.append(name)
                            else:
                                AccessLog.objects.create(user=user, action=f"Dispense Fail: {name} out of stock during retrieval window.", success=False)
                                
                        except Medicine.DoesNotExist:
                             AccessLog.objects.create(user=user, action=f"Dispense Confirm Error: Unknown medicine name: {name}", success=False)
                             continue
                    # --------------------------------------------

                # Reset status
                user_profile.interaction_status = 'idle'
                user_profile.save()

                # Final Notification and Log
                if successfully_dispensed:
                    msg = f"Medicine(s) dispensed successfully: {', '.join(successfully_dispensed)}. Stock adjusted."
                    Notification.objects.create(user=user, title="Dispense Complete", message=msg, type='success')
                    AccessLog.objects.create(user=user, action=f"Dispense confirmed by box for: {', '.join(successfully_dispensed)} (Stock Adjusted)", success=True)
                else:
                    msg = "Dispense failed. Please check stock and logs."
                    Notification.objects.create(user=user, title="Dispense Failed", message=msg, type='error')
                    AccessLog.objects.create(user=user, action=f"Dispense FAILED for requested items.", success=False)
                
                return JsonResponse({'status': 'ok', 'message': 'Dispense and stock adjustment complete.'})
                
            except Exception as e:
                AccessLog.objects.create(user=user, action=f"FATAL DB ERROR during dispense confirmation: {e}", success=False)
                return JsonResponse({'status': 'error', 'message': f'Server failed to update database: {e}'}, status=500)

        elif user_profile.interaction_status == 'idle':
            # If the user is idle but scans their ID, they need to select medicine first.
            Notification.objects.create(user=user, title="Attention", message="Please select your medicine(s) on the website first.", type='alert')
            AccessLog.objects.create(user=user, action="ID Scan ignored: User not in pending_scan state.", success=False)
            return JsonResponse({'status': 'ignored', 'message': 'User must select medicine first.'}, status=200)

        else:
            return JsonResponse({'status': 'ignored', 'message': 'User was not in pending_scan state. Ignoring confirmation.'}, status=200)

    else:
        # Handle unknown action_type
        AccessLog.objects.create(user=user, action=f"IoT Confirmation Failed - Unknown action_type: {action_type}", success=False)
        return JsonResponse({'status': 'error', 'message': f'Unknown action type: {action_type}'}, status=400)
    
# In your firstaid/views.py (add this new function)
@csrf_exempt
def esp32_ping(request):
    """
    Receives a status ping from the ESP32 module.
    Updates the SystemStatus in the database.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)

    try:
        # Ensure the object exists first
        status_obj, created = SystemStatus.objects.get_or_create(pk=1) 
        
        # Check Camera Timeout Logic (before updating the object)
        should_turn_off_camera = (
            status_obj.camera_on and 
            status_obj.camera_expires_at and 
            status_obj.camera_expires_at < timezone.now()
        )
        
        # Perform the update in one atomic transaction
        SystemStatus.objects.filter(pk=1).update(
            esp32_connected=True,
            last_esp32_ping=timezone.now(),
            # Conditionally set camera_on
            camera_on=False if should_turn_off_camera else status_obj.camera_on
        )
        
        # Retrieve the updated status object to send back
        updated_status = SystemStatus.objects.get(pk=1)

        # Return the current locked status to the ESP32
        return JsonResponse({
            'status': 'ok', 
            'message': 'System status updated',
            'is_locked': updated_status.is_locked,
            'camera_on': updated_status.camera_on
        })

    except Exception as e:
        AccessLog.objects.create(action=f"ESP32 Ping Failed: {e}", success=False)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
# Utility function placeholders
# Placeholder for utility function (ensure this is defined elsewhere in your views.py)
# In your firstaid/views.py (Update the utility function)

# Placeholder for utility function (ensure this is defined elsewhere in your views.py)
def get_esp32_status():
    """Checks the SystemStatus object for connection health."""
    try:
        status_obj = SystemStatus.objects.first() 
        if status_obj:
            # Check if last_esp32_ping is within the last 5 minutes
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            is_online = status_obj.esp32_connected and \
                        status_obj.last_esp32_ping and \
                        status_obj.last_esp32_ping > five_minutes_ago
                        
            # Use 'Online' only if the ping is recent
            status = 'Online' if is_online else 'Offline'
            
            return {
                'status': status, 
                'last_ping': status_obj.last_esp32_ping,
                'is_locked': status_obj.is_locked, # Added for dashboard display
                'camera_on': status_obj.camera_on # Added for dashboard display
            }
        return {'status': 'Unknown', 'last_ping': None, 'is_locked': True, 'camera_on': False}
    except Exception:
        return {'status': 'Error', 'last_ping': None, 'is_locked': True, 'camera_on': False}


@login_required
def dashboard(request):
    """
    Renders the main dashboard. Enforces status reset on login and prompts for medicine selection.
    """

    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found. Please ensure your profile is complete.')
        return redirect('profile_view') 

    # --- FULL INTERACTION RESET (ONLY ONCE PER SESSION) ---
    
    if not request.session.get('interaction_reset_done'):
        # Delete flow-related messages and force status to idle on fresh login/session start
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            # Target both old scan prompt and new select prompt
            title__in=["Scan ID Required", "Please Select Medicine"] 
        ).delete()
        
        # Force status to idle to ensure flow starts from the beginning
        if user_profile.interaction_status != 'idle':
            user_profile.interaction_status = 'idle'
            user_profile.save()
            
        request.session['interaction_reset_done'] = True
    
    # --- NEW NOTIFICATION LOGIC: PROMPT TO SELECT MEDICINE ---
    
    create_select_notification = False
    
    # 1. Check User Status: Only prompt if the user is idle
    if user_profile.interaction_status == 'idle':
        
        # Check if the "Select Medicine" message already exists (prevents spam on refresh)
        select_notification_exists = Notification.objects.filter(
            user=request.user, 
            title="Please Select Medicine", 
            is_read=False
        ).exists()
        
        if not select_notification_exists:
            create_select_notification = True

    # 2. Create Notification if necessary
    if create_select_notification:
        Notification.objects.create(
            user=request.user,
            title="Please Select Medicine",
            message="Welcome! Please select the medicine(s) you need from the list.",
            type='system_alert'
        )
    
    # --- STATS GATHERING ---
    total_medicines = Medicine.objects.count()
    low_stock_count = Medicine.objects.filter(quantity__lte=5).count()
    expired_count = Medicine.objects.filter(expiry_date__lt=timezone.now().date()).count()

    notifications = Notification.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('-created_at')[:5]

    recent_logs = AccessLog.objects.filter(user=request.user).order_by('-timestamp')[:10]
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    usage_stats = MedicineUsage.objects.filter(usage_date__gte=thirty_days_ago, user=request.user) \
        .values('medicine__name') \
        .annotate(total_used=Sum('quantity_used')) \
        .order_by('-total_used')[:5]

    context = {
        'esp32_status': get_esp32_status(),
        'total_medicines': total_medicines,
        'low_stock_count': low_stock_count,
        'expired_count': expired_count,
        'recent_logs': recent_logs,
        'usage_stats': usage_stats,
        'notifications': notifications,
    }
    return render(request, 'dashboard.html', context)

@login_required
def medicines_list(request):
    """
    Renders the list of medicines, handling filtering, searching, and pagination.
    """
    medicines = Medicine.objects.all().order_by('name')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')

    if search_query:
        medicines = medicines.filter(
            Q(name__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    if category_filter:
        medicines = medicines.filter(category=category_filter)

    if stock_filter == 'low':
        medicines = medicines.filter(quantity__lte=5)
    elif stock_filter == 'expired':
        medicines = medicines.filter(expiry_date__lt=timezone.now().date())

    categories = Medicine.objects.values_list('category', flat=True).distinct()

    paginator = Paginator(medicines, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'categories': categories,
    }
    return render(request, 'medicines_list.html', context)

@login_required
def medicine_detail(request, medicine_id):
    """
    Displays detailed information about a single medicine.
    """
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    usage_history = MedicineUsage.objects.filter(medicine=medicine).order_by('-usage_date')[:10]
    access_logs = AccessLog.objects.filter(medicine=medicine).order_by('-timestamp')[:10]
    notifications = Notification.objects.filter(medicine=medicine).order_by('-created_at')[:5]

    context = {
        'medicine': medicine,
        'usage_history': usage_history,
        'access_logs': access_logs,
        'notifications': notifications,
    }
    return render(request, 'firstaid/medicine_detail.html', context)

@login_required
def add_medicine(request):
    """
    Handles adding a new medicine to the inventory.
    Requires admin privileges.
    """
    try:
        if not request.user.is_admin:
            messages.error(request, 'You do not have permission to add medicines.')
            return redirect('medicines_list')
    except UserProfile.DoesNotExist:
        # If the user doesn't have a profile, they can't be an admin.
        messages.error(request, 'You do not have permission to add medicines.')
        return redirect('medicines_list')

    if request.method == 'POST':
        try:
            name = request.POST['name']
            barcode = request.POST['barcode']
            quantity = int(request.POST['quantity'])
            expiry_date_str = request.POST['expiry_date']

            if not name or not barcode or not expiry_date_str:
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'firstaid/add_medicine.html')

            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()

            Medicine.objects.create(
                name=name,
                barcode=barcode,
                description=request.POST.get('description', ''),
                category=request.POST.get('category', 'General'),
                dosage=request.POST.get('dosage', ''),
                quantity=quantity,
                expiry_date=expiry_date
            )
            
            messages.success(request, 'Medicine added successfully!')
            return redirect('medicines_list')

        except (KeyError, ValueError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
            return render(request, 'add_medicine.html')
    
    return render(request, 'add_medicine.html')

@login_required
def request_medicines(request):
    if request.method == 'POST':
        selected_medicine_ids = request.POST.getlist('medicines')
        
        try:
            user_profile = request.user.userprofile
            roll_no = user_profile.roll_no
        except UserProfile.DoesNotExist:
            messages.error(request, 'Your user profile is incomplete.')
            return redirect('medicines_list')

        if not selected_medicine_ids:
            messages.error(request, 'Please select at least one medicine.')
            return redirect('medicines_list')

        selected_medicines = Medicine.objects.filter(id__in=selected_medicine_ids)
        
        # --- INSTANT STOCK CHECK ---
        out_of_stock = []
        in_stock_names = []
        for medicine in selected_medicines:
            if medicine.quantity < 1:
                out_of_stock.append(medicine.name)
            else:
                in_stock_names.append(medicine.name)

        if out_of_stock:
            messages.error(request, f'The following medicines are out of stock: {", ".join(out_of_stock)}.')
            AccessLog.objects.create(user=request.user, action=f"Request failed: {', '.join(out_of_stock)} out of stock.", success=False)
            return redirect('medicines_list')

        # --- STOCK IS AVAILABLE: PROCEED TO PENDING SCAN STATE ---
        
        if not in_stock_names:
             messages.error(request, 'No medicine was selected or available.')
             return redirect('medicines_list')
             
        # Store requested items in the session 
        request.session['requested_medicines'] = in_stock_names
        
        # 1. SET STATUS: Update User Status to 'pending_scan'
        user_profile.interaction_status = 'pending_scan'
        user_profile.save()
        
        # 2. CREATE NEW PROMPT NOTIFICATION
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            title__in=["Please Select Medicine"] # Delete old select prompt
        ).delete()
        
        Notification.objects.create(
            user=request.user,
            title="Scan ID Required",
            message=f"Stock confirmed for {', '.join(in_stock_names)}. Please scan your ID card at the First-Aid Box to dispense.",
            type='system_alert'
        )

        # 3. Log the pending request
        AccessLog.objects.create(
            user=request.user,
            action=f"Request initiated for: {', '.join(in_stock_names)} (Pending ID Scan)",
            success=True,
        )
        
        messages.info(request, 'Stock confirmed. Please scan your ID card at the box to retrieve.')

        return redirect('dashboard')
    
    return redirect('medicines_list')

from django.contrib.auth.decorators import login_required
from .models import MedicineUsage
@login_required
def profile_view(request):
    user = request.user  # current logged-in user

    if request.method == 'POST':
        if 'change_picture' in request.POST and request.FILES.get('profile_picture'):
            # If user uploaded a new picture
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            messages.success(request, "Profile picture updated successfully!")

        elif 'delete_picture' in request.POST:
            # Delete old picture from filesystem
            if user.profile_picture:
                if os.path.isfile(user.profile_picture.path):
                    os.remove(user.profile_picture.path)
                user.profile_picture = None
                user.save()
                messages.info(request, "Profile picture deleted.")

    return render(request, 'profile.html', {'user': user})

# In your firstaid/views.py (Add this section to the bottom of the file)
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction

# Ensure all necessary models are imported at the very top:
# from .models import Medicine, AccessLog, Notification, MedicineUsage, SystemStatus, UserProfile


@csrf_exempt
def handle_iot_confirmation(request):
    """
    Receives confirmation POST request from ESP32.
    Handles the ID Scan (scan_complete) as the final dispense trigger, 
    verifies ID, and adjusts stock based on payload details.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)

    data = {}
    try:
        data = json.loads(request.body)
        roll_no = data.get('roll_no')
        action_type = data.get('action_type')
        details = data.get('details', '') # Details now contains the dispensed medicine list
        
        if not all([roll_no, action_type]):
             return JsonResponse({'status': 'error', 'message': 'Missing roll_no or action_type in payload'}, status=400)
             
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)

    try:
        user_profile = UserProfile.objects.select_related('user').get(roll_no=roll_no)
        user = user_profile.user
    except UserProfile.DoesNotExist:
        AccessLog.objects.create(action=f"IoT Confirmation Failed - Unknown ID: {roll_no}", success=False)
        return JsonResponse({'status': 'error', 'message': 'ID card not recognized (No UserProfile found)'}, status=403)

    # --- Confirmation Logic ---
    
    if action_type == 'scan_complete':
        
        # 1. Check if user is in the 'pending_scan' state
        if user_profile.interaction_status == 'pending_scan':
            
            # --- SECURITY CHECK: ROLL NUMBER VERIFICATION ---
            if str(roll_no) != str(user_profile.roll_no):
                # ID mismatch! Deny dispense and reset status.
                user_profile.interaction_status = 'idle'
                user_profile.save()
                
                Notification.objects.create(user=user, title="SECURITY ALERT", message="ID scan failed: The scanned ID does not match the requesting user.", type='error')
                AccessLog.objects.create(user=user, action=f"SECURITY FAILURE: Scanned ID ({roll_no}) did not match requesting user ID.", success=False)
                
                return JsonResponse({'status': 'denied', 'message': 'ID mismatch. Dispense blocked.'}, status=403)
            # --- END SECURITY CHECK ---

            # --- CRITICAL FIX: RETRIEVE MEDICINES FROM PAYLOAD (details) ---
            if not details:
                 return JsonResponse({'status': 'error', 'message': 'Medicine details missing in scan confirmation payload.'}, status=400)
                 
            # Parse the details string (e.g., "Ibuprofen, Paracetamol") into a list
            requested_items = [name.strip() for name in details.split(',') if name.strip()]

            if not requested_items:
                return JsonResponse({'status': 'error', 'message': 'No valid medicines specified in the payload details.'}, status=400)
            
            # Since the dispense is confirmed, clear the session item (if it exists)
            if 'requested_medicines' in request.session:
                del request.session['requested_medicines']
            
            # --- STOCK ADJUSTMENT AND USAGE LOGGING ---
            try:
                with transaction.atomic():
                    successfully_dispensed = []
                    for name in requested_items:
                        try:
                            medicine = Medicine.objects.get(name__iexact=name)
                            
                            if medicine.quantity >= 1: 
                                medicine.quantity -= 1
                                medicine.save()
                                MedicineUsage.objects.create(user=user, medicine=medicine, quantity_used=1)
                                successfully_dispensed.append(name)
                            else:
                                AccessLog.objects.create(user=user, action=f"Dispense Fail: {name} out of stock during retrieval window.", success=False)
                                
                        except Medicine.DoesNotExist:
                             AccessLog.objects.create(user=user, action=f"Dispense Confirm Error: Unknown medicine name: {name}", success=False)
                             continue
                    # --------------------------------------------

                # Reset status
                user_profile.interaction_status = 'idle'
                user_profile.save()

                # Final Notification and Log
                if successfully_dispensed:
                    msg = f"Medicine(s) dispensed successfully: {', '.join(successfully_dispensed)}. Stock adjusted."
                    Notification.objects.create(user=user, title="Dispense Complete", message=msg, type='success')
                    AccessLog.objects.create(user=user, action=f"Dispense confirmed by box for: {', '.join(successfully_dispensed)} (Stock Adjusted)", success=True)
                else:
                    msg = "Dispense failed. Please check stock and logs."
                    Notification.objects.create(user=user, title="Dispense Failed", message=msg, type='error')
                    AccessLog.objects.create(user=user, action=f"Dispense FAILED for requested items.", success=False)
                
                return JsonResponse({'status': 'ok', 'message': 'Dispense and stock adjustment complete.'})
                
            except Exception as e:
                AccessLog.objects.create(user=user, action=f"FATAL DB ERROR during dispense confirmation: {e}", success=False)
                return JsonResponse({'status': 'error', 'message': f'Server failed to update database: {e}'}, status=500)

        elif user_profile.interaction_status == 'idle':
            # If the user is idle but scans their ID, they need to select medicine first.
            Notification.objects.create(user=user, title="Attention", message="Please select your medicine(s) on the website first.", type='alert')
            AccessLog.objects.create(user=user, action="ID Scan ignored: User not in pending_scan state.", success=False)
            return JsonResponse({'status': 'ignored', 'message': 'User must select medicine first.'}, status=200)

        else:
            return JsonResponse({'status': 'ignored', 'message': 'User was not in pending_scan state. Ignoring confirmation.'}, status=200)

    else:
        # Handle unknown action_type
        AccessLog.objects.create(user=user, action=f"IoT Confirmation Failed - Unknown action_type: {action_type}", success=False)
        return JsonResponse({'status': 'error', 'message': f'Unknown action type: {action_type}'}, status=400)
    
# In your firstaid/views.py (add this new function)
@csrf_exempt
def esp32_ping(request):
    """
    Receives a status ping from the ESP32 module.
    Updates the SystemStatus in the database.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)

    try:
        # Ensure the object exists first
        status_obj, created = SystemStatus.objects.get_or_create(pk=1) 
        
        # Check Camera Timeout Logic (before updating the object)
        should_turn_off_camera = (
            status_obj.camera_on and 
            status_obj.camera_expires_at and 
            status_obj.camera_expires_at < timezone.now()
        )
        
        # Perform the update in one atomic transaction
        SystemStatus.objects.filter(pk=1).update(
            esp32_connected=True,
            last_esp32_ping=timezone.now(),
            # Conditionally set camera_on
            camera_on=False if should_turn_off_camera else status_obj.camera_on
        )
        
        # Retrieve the updated status object to send back
        updated_status = SystemStatus.objects.get(pk=1)

        # Return the current locked status to the ESP32
        return JsonResponse({
            'status': 'ok', 
            'message': 'System status updated',
            'is_locked': updated_status.is_locked,
            'camera_on': updated_status.camera_on
        })

    except Exception as e:
        AccessLog.objects.create(action=f"ESP32 Ping Failed: {e}", success=False)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    
MQTT_BROKER = "2345bdceb5234e968caf872d85c4968c.s1.eu.hivemq.cloud"  # e.g., "abcd1234.s2.eu.hivemq.cloud"
MQTT_PORT = 8884
MQTT_USERNAME = "aanaGoyal"
MQTT_PASSWORD = "Aana123@"
MQTT_TOPIC = "medicine/dispense"

def publish_to_mqtt(medicine_name):
    """
    Publishes a JSON message to the MQTT broker to trigger ESP32 action.
    This function connects securely to HiveMQ Cloud and sends the selected medicine.
    """
    try:
        # 1️⃣ Create MQTT client object
        client = mqtt.Client()

        # 2️⃣ Set username/password (used for HiveMQ Cloud authentication)
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        # 3️⃣ Enable SSL/TLS for secure connection (HiveMQ requires it)
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)

        # 4️⃣ Connect to HiveMQ Cloud broker
        client.connect(MQTT_BROKER, MQTT_PORT, 60)

        # 5️⃣ Construct message payload
        payload = {"medicine": medicine_name}

        # 6️⃣ Publish the payload to the topic
        client.publish(MQTT_TOPIC, str(payload))

        # 7️⃣ Disconnect cleanly
        client.disconnect()

        return True

    except Exception as e:
        print(f"MQTT Publish Failed: {e}")
        return False


@login_required
def dispense_medicine(request, medicine_name):
    """
    Called when a user requests a specific medicine.
    Sends MQTT command to ESP32 to start dispensing process.
    """
    success = publish_to_mqtt(medicine_name)

    if success:
        # Log the dispense request for history
        AccessLog.objects.create(
            user=request.user,
            action=f"MQTT Dispense Request sent for {medicine_name}",
            success=True
        )
        Notification.objects.create(
            user=request.user,
            title="Dispense Request Sent",
            message=f"Cloud request sent for {medicine_name}. Please wait for the ESP32 to respond.",
            type='system_alert'
        )
        messages.success(request, f"Dispense request sent successfully for {medicine_name}.")
    else:
        AccessLog.objects.create(
            user=request.user,
            action=f"MQTT Dispense Request FAILED for {medicine_name}",
            success=False
        )
        Notification.objects.create(
            user=request.user,
            title="Dispense Request Failed",
            message=f"Could not send MQTT request for {medicine_name}. Check server logs or broker status.",
            type='error'
        )
        messages.error(request, f"Failed to send dispense request for {medicine_name}.")

    return redirect('dashboard')

from .mqtt_client import publish_message
from django.http import HttpResponse

def send_command(request):
    publish_message("rotate_30")
    return HttpResponse("Command sent!")
