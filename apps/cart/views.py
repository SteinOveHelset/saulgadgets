from django.shortcuts import render, redirect

from .cart import Cart

def cart_detail(request):
    cart = Cart(request)

    context = {
        'cart': cart
    }

    return render(request, 'cart.html', context)