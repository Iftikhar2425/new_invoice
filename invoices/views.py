from django.shortcuts import render, redirect
from django.http import FileResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.utils.timezone import now

from .models import Customer, Invoice, Item

import fitz
import os
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(BASE_DIR, "template.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_decimal(value, default="0.00"):
    try:
        value = str(value).strip()

        if value == "":
            return Decimal(default)

        return Decimal(value)

    except Exception:
        return Decimal(default)


def wipe_rect(page, rect):
    r = fitz.Rect(rect)
    page.add_redact_annot(r, fill=(1, 1, 1))


def write_in_rect(page, rect, text, fontsize=9):
    r = fitz.Rect(rect)
    page.insert_text((r.x0 + 2, r.y1 - 2), str(text), fontsize=fontsize)


# ✅ FIXED RIGHT ALIGN (DISCOUNT)
def write_in_rect_right(page, rect, text, fontsize=9):
    r = fitz.Rect(rect)
    text = str(text)
    text_width = fitz.get_text_length(text, fontsize=fontsize)
    x = r.x1 - text_width - 2
    y = r.y1 - 3
    page.insert_text((x, y), text, fontsize=fontsize)


def login_view(request):
    if request.method == "POST":

        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password")
        )

        if user:
            login(request, user)
            return redirect("index")

        return render(
            request,
            "invoices/login.html",
            {"error": "Invalid credentials"}
        )

    return render(request, "invoices/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def index(request):
    customers = Customer.objects.all()
    return render(request, "invoices/index.html", {"customers": customers})


@login_required
def generate_invoice(request):

    if request.method == "POST":

        customer, created = Customer.objects.get_or_create(
            name=request.POST.get("customer_name"),
            defaults={
                "address": request.POST.get("address", ""),
                "ntn": request.POST.get("ntn", ""),
                "sales_tax": request.POST.get("sales_tax", "")
            }
        )

        if not created:
            customer.address = request.POST.get("address", "")
            customer.ntn = request.POST.get("ntn", "")
            customer.sales_tax = request.POST.get("sales_tax", "")
            customer.save()

        invoice = Invoice.objects.create(
            customer=customer,
            license_no=request.POST.get("license_no", "")
        )

        names = request.POST.getlist("item_name[]")
        qtys = request.POST.getlist("qty[]")
        prices = request.POST.getlist("price[]")
        discounts = request.POST.getlist("discount[]")

        batches = request.POST.getlist("batch[]")
        expiries = request.POST.getlist("expiry[]")

        total_gross = Decimal("0")
        total_net = Decimal("0")
        total_discount = Decimal("0")

        for i in range(len(names)):

            if not names[i]:
                continue

            qty = safe_decimal(qtys[i])
            price = safe_decimal(prices[i])
            disc = safe_decimal(discounts[i])

            gross = Decimal(price) * Decimal(qty)

            discount_amount = (
                Decimal(price) * Decimal(disc) / Decimal("100")
            ) * Decimal(qty)

            total_gross += gross
            total_discount += discount_amount

            discounted_price = Decimal(price) - (
                Decimal(price) * Decimal(disc) / Decimal("100")
            )

            amount = discounted_price * Decimal(qty)

            total_net += amount

            Item.objects.create(
                invoice=invoice,
                name=names[i],
                qty=int(float(qty)),
                batch=batches[i],
                expiry=expiries[i],
                price=price,
                discount=disc
            )

        doc = fitz.open(PDF_PATH)
        page = doc[0]

        HEADER_COORDS = {
            "customer_name": (125.84, 110.15, 272.87, 122.43),
            "address": (125.84, 124.65, 347.06, 134.70),
            "invoice_no": (482.60, 110.13, 524.41, 120.18),
            "date": (479.85, 120.98, 523.99, 131.03),
            "license_no": (75.06, 181.90, 173.89, 191.95),
        }

        NTN_VALUE = (95, 158, 200, 168)
        SALES_TAX_VALUE = (110, 170, 220, 180)

        TABLE_COLS = {
            "sr": 54.7,
            "name": 72.1,
            "qty": 208.5,
            "batch": 249.7,
            "expiry": 330.3,
            "price": 388.6,
            "discount": 505.6,
            "amount": 546.0,
        }

        ROW_START_Y = 221.4
        ROW_HEIGHT = 9.5

        # ──────── INVOICE BREAKUP RECTANGLES ────────
        GROSS_VALUE_RECT = (535, 260, 590, 280)

        DISCOUNT_VALUE_RECT = (
            535,
            277.58,
            590,
            287.63
        )

        NET_PAYABLE_RECT = (535, 320, 590, 345)

        COMPANY_TOTAL_RECT = (
            535,
            240,
            590,
            260
        )

        data = {
            "customer_name": customer.name,
            "address": customer.address,
            "invoice_no": invoice.invoice_no,
            "date": now().strftime("%d/%m/%Y"),
            "license_no": invoice.license_no,
        }

        for rect in HEADER_COORDS.values():
            wipe_rect(page, rect)

        wipe_rect(page, NTN_VALUE)
        wipe_rect(page, SALES_TAX_VALUE)

        page.apply_redactions()

        for key, rect in HEADER_COORDS.items():
            write_in_rect(page, rect, data.get(key, ""), 9)

        write_in_rect(page, NTN_VALUE, customer.ntn, 9)
        write_in_rect(page, SALES_TAX_VALUE, customer.sales_tax, 9)

        table_rect = fitz.Rect(
            50,
            ROW_START_Y - 2,
            580,
            ROW_START_Y + (len(names) * ROW_HEIGHT) + 5
        )

        wipe_rect(page, table_rect)
        page.apply_redactions()

        for i in range(len(names)):

            if not names[i]:
                continue

            y = ROW_START_Y + i * ROW_HEIGHT

            qty = safe_decimal(qtys[i])
            price = safe_decimal(prices[i])
            disc = safe_decimal(discounts[i])

            discounted_price = Decimal(price) - (
                Decimal(price) * Decimal(disc) / Decimal("100")
            )

            amount = discounted_price * Decimal(qty)

            page.insert_text(
                (TABLE_COLS["sr"], y),
                str(i + 1),
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["name"], y),
                names[i],
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["qty"], y),
                str(qty),
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["batch"], y),
                batches[i],
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["expiry"], y),
                expiries[i],
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["price"], y),
                f"{price:.2f}",
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["discount"], y),
                f"{disc}%",
                fontsize=8
            )

            page.insert_text(
                (TABLE_COLS["amount"], y),
                f"{amount:.2f}",
                fontsize=8
            )

        wipe_rect(page, GROSS_VALUE_RECT)
        wipe_rect(page, DISCOUNT_VALUE_RECT)
        wipe_rect(page, NET_PAYABLE_RECT)
        wipe_rect(page, COMPANY_TOTAL_RECT)

        page.apply_redactions()

        write_in_rect_right(
            page,
            GROSS_VALUE_RECT,
            f"{total_gross:.2f}",
            9
        )

        # ✅ FINAL DISCOUNT FIX
        write_in_rect_right(
            page,
            DISCOUNT_VALUE_RECT,
            f"-{abs(total_discount):.2f}",
            9
        )

        write_in_rect_right(
            page,
            NET_PAYABLE_RECT,
            f"{total_net:.2f}",
            9
        )

        write_in_rect_right(
            page,
            COMPANY_TOTAL_RECT,
            f"{total_net:.2f}",
            9
        )

        output_file = os.path.join(
            OUTPUT_DIR,
            f"{invoice.invoice_no}.pdf"
        )

        doc.save(output_file)
        doc.close()

        return FileResponse(
            open(output_file, "rb"),
            as_attachment=True
        )