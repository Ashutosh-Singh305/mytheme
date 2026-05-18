from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'theme/base.html')

def topmenu(request):
    return render(request, 'theme/topmenu.html')

def list(request):
    return render(request, 'theme/list.html')
