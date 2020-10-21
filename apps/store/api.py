import json
import stripe
import razorpay

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string

from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCaptureRequest

from apps.cart.cart import Cart
from apps.order.views import render_to_pdf

from apps.order.utils import checkout

from .models import Product
from apps.order.models import Order
from apps.coupon.models import Coupon

from .utilities import decrement_product_quantity, send_order_confirmation

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

        decrement_product_quantity(order)
        send_order_confirmation(order)

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
    payment_intent = ''
    
    if gateway == 'stripe':
        stripe.api_key = settings.STRIPE_API_KEY_HIDDEN
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

    orderid = checkout(request, data['first_name'], data['last_name'], data['email'], data['address'], data['zipcode'], data['place'], data['phone'])

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
    
    # PayPal

    if gateway == 'paypal':
        order_id = data['order_id']
        environment = SandboxEnvironment(client_id=settings.PAYPAL_API_KEY_PUBLISHABLE, client_secret=settings.PAYPAL_API_KEY_HIDDEN)
        client = PayPalHttpClient(environment)

        request = OrdersCaptureRequest(order_id)
        response = client.execute(request)

        order = Order.objects.get(pk=orderid)
        order.paid_amount = total_price
        order.used_coupon = coupon_code

        if response.result.status == 'COMPLETED':
            order.paid = True
            order.payment_intent = order_id
            order.save()

            decrement_product_quantity(order)
            send_order_confirmation(order)
        else:
            order.paid = False
            order.save()
    else:
        order = Order.objects.get(pk=orderid)
        if gateway == 'razorpay':
            order.payment_intent = payment_intent['id']
        else:
            order.payment_intent = payment_intent
        order.paid_amount = total_price
        order.used_coupon = coupon_code
        order.save()

    #

    return JsonResponse({'session': session, 'order': payment_intent})

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