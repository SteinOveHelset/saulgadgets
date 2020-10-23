from django.shortcuts import render

from apps.store.models import Product, Category

def frontpage(request):
    products = Product.objects.filter(is_featured=True)
    featured_categories = Category.objects.filter(is_featured=True)
    popular_products = Product.objects.all().order_by('-num_visits')[0:4]
    recently_viewed_products = Product.objects.all().order_by('-last_visit')[0:4]

    context = {
        'products': products,
        'featured_categories': featured_categories,
        'popular_products': popular_products,
        'recently_viewed_products': recently_viewed_products
    }

    return render(request, 'frontpage.html', context)

def contact(request):
    return render(request, 'contact.html')

def about(request):
    return render(request, 'about.html')