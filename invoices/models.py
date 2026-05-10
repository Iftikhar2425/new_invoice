from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    ntn = models.CharField(max_length=50, blank=True, null=True)
    sales_tax = models.CharField(max_length=50, blank=True, null=True)
    license_no = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    # ✅ STRING FORMAT
    invoice_no = models.CharField(max_length=20, unique=True)

    date = models.DateField(auto_now_add=True)
    license_no = models.CharField(max_length=100)

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            last = Invoice.objects.order_by('-id').first()

            if last and last.invoice_no:
                last_num = int(last.invoice_no.split("-")[-1])
                new_num = last_num + 1
            else:
                new_num = 9965   # ✅ START

            self.invoice_no = f"HHC-{str(new_num).zfill(4)}"

        super().save(*args, **kwargs)


class Item(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    qty = models.IntegerField()
    batch = models.CharField(max_length=100, blank=True, null=True)
    expiry = models.CharField(max_length=20, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2)