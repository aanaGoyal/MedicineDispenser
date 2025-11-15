from django.urls import path
from . import views

urlpatterns = [
    # Main dashboard view
    path('', views.dashboard, name='dashboard'),
    path('medicines/', views.medicines_list, name='medicines_list'),
    path('medicines/<int:medicine_id>/', views.medicine_detail, name='medicine_detail'),
    path('medicines/add/', views.add_medicine, name='add_medicine'),
    path("request_medicines/", views.request_medicines, name="request_medicines"),
    path('profile/', views.profile_view, name='profile_view'),
    # Other URLs for your project would go here
    path('iot/confirm/', views.handle_iot_confirmation, name='handle_iot_confirmation'),
    path('iot/ping/', views.esp32_ping, name='esp32_ping'),
    # path("dispense/<str:medicine_name>/", views.dispense_medicine, name="dispense_medicine"),
    path('toggle-led/', views.toggle_led, name='toggle_led'),
    # path('verify_face/', views.verify_face, name='verify_face'),
]