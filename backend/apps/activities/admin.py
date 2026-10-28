from django.contrib import admin

from .models import Interaction, Notification, Task

admin.site.register(Interaction)
admin.site.register(Task)
admin.site.register(Notification)
