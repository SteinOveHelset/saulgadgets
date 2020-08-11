from .models import Category

def menu_categories(request):
    categories = Category.objects.all()

    return {'menu_categories': categories}