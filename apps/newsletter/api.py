import json

from django.http import JsonResponse

from .models import Subscriber

def api_add_subscriber(request):
    data = json.loads(request.body)
    email = data['email']

    s = Subscriber.objects.create(email=email)

    return JsonResponse({'success': True})