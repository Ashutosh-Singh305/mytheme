from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'theme/base.html')

def index(request):
    return render(request, 'theme/base.html')

def list(request):
    return render(request, 'theme/list.html')
