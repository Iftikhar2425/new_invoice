from django.contrib import admin
from .models import Customer, Invoice, Item


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'customer', 'date', 'license_no')
    inlines = [ItemInline]


admin.site.register(Customer)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Item)