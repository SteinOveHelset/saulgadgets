from .models import Category

def menu_categories(request):
    categories = Category.objects.filter(parent=None)

    return {'menu_categories': categories}