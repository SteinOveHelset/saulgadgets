import json
import stripe
import razorpay

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string

from apps.cart.cart import Cart
from apps.order.views import render_to_pdf

from apps.order.utils import checkout

from .models import Product
from apps.order.models import Order
from apps.coupon.models import Coupon

def validate_payment(request):
    data = json.loads(request.body)
    razorpay_payment_id = data['razorpay_payment_id']
    razorpay_order_id = data['razorpay_order_id']
    razorpay_signature = data['razorpay_signature']

    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY_PUBLISHABLE, settings.RAZORPAY_API_KEY_HIDDEN))

    params_dict = {
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_order_id': razorpay_order_id,
        'razorpay_signature': razorpay_signature
    }

    res = client.utility.verify_payment_signature(params_dict)

    print(res)

    if not res:
        order = Order.objects.get(payment_intent=razorpay_order_id)
        order.paid = True
        order.save()

        for item in order.items.all():
            product = item.product
            product.num_available = product.num_available - item.quantity
            product.save()
        
        subject = 'Order confirmation'
        from_email = 'noreply@saulgadgets.com'
        to = ['mail@saulgadgets.com', order.email]
        text_content = 'Your order is successful!'
        html_content = render_to_string('order_confirmation.html', {'order': order})

        pdf = render_to_pdf('order_pdf.html', {'order': order})

        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")

        if pdf:
            name = 'order_%s.pdf' % order.id
            msg.attach(name, pdf, 'application/pdf')
        
        msg.send()

    return JsonResponse({'success': True})

def create_checkout_session(request):
    data = json.loads(request.body)

    # Coupon 

    coupon_code = data['coupon_code']
    coupon_value = 0

    if coupon_code != '':
        coupon = Coupon.objects.get(code=coupon_code)

        if coupon.can_use():
            coupon_value = coupon.value
            coupon.use()

    #

    cart = Cart(request)

    stripe.api_key = settings.STRIPE_API_KEY_HIDDEN

    items = []
    
    for item in cart:
        product = item['product']

        price = int(product.price * 100)

        if coupon_value > 0:
            price = int(price * (int(coupon_value) / 100))

        obj = {
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': product.title
                },
                'unit_amount': price
            },
            'quantity': item['quantity']
        }

        items.append(obj)

    gateway = data['gateway']
    session = ''
    order_id = ''
    
    if gateway == 'stripe':
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=items,
            mode='payment',
            success_url='http://127.0.0.1:8000/cart/success/',
            cancel_url='http://127.0.0.1:8000/cart/'
        )
        payment_intent = session.payment_intent

    #
    # Create order

    first_name = data['first_name']
    last_name = data['last_name']
    email = data['email']
    address = data['address']
    zipcode = data['zipcode']
    place = data['place']
    phone = data['phone']

    orderid = checkout(request, first_name, last_name, email, address, zipcode, place, phone)

    total_price = 0.00

    for item in cart:
        product = item['product']
        total_price = total_price + (float(product.price) * int(item['quantity']))

    if coupon_value > 0:
        total_price = total_price * (coupon_value / 100)
    
    if gateway == 'razorpay':
        order_amount = total_price * 100
        order_currency = 'INR'
        client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY_PUBLISHABLE, settings.RAZORPAY_API_KEY_HIDDEN))
        data = {
            'amount': order_amount,
            'currency': order_currency
        }

        payment_intent = client.order.create(data=data)

    order = Order.objects.get(pk=orderid)
    order.payment_intent = payment_intent['id']
    order.paid_amount = total_price
    order.used_coupon = coupon_code
    order.save()

    #

    return JsonResponse({'session': session, 'order': payment_intent})

def api_checkout(request):
    cart = Cart(request)

    data = json.loads(request.body)
    jsonresponse = {'success': True}
    first_name = data['first_name']
    last_name = data['last_name']
    email = data['email']
    address = data['address']
    zipcode = data['zipcode']
    place = data['place']
    
    orderid = checkout(request, first_name, last_name, email, address, zipcode, place)

    paid = True

    if paid == True:
        order = Order.objects.get(pk=orderid)
        order.paid = True
        order.paid_amount = cart.get_total_cost()
        order.save()

        cart.clear()
    
    return JsonResponse(jsonresponse)

def api_add_to_cart(request):
    data = json.loads(request.body)
    jsonresponse = {'success': True}
    product_id = data['product_id']
    update = data['update']
    quantity = data['quantity']

    cart = Cart(request)

    product = get_object_or_404(Product, pk=product_id)

    if not update:
        cart.add(product=product, quantity=1, update_quantity=False)
    else:
        cart.add(product=product, quantity=quantity, update_quantity=True)
    
    return JsonResponse(jsonresponse)

def api_remove_from_cart(request):
    data = json.loads(request.body)
    jsonresponse = {'success': True}
    product_id = str(data['product_id'])

    cart = Cart(request)
    cart.remove(product_id)

    return JsonResponse(jsonresponse)